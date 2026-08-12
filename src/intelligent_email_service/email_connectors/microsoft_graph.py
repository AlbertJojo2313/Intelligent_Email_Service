import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, NoReturn

import httpx
from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from intelligent_email_service.config import AzureADCredentials, MicrosoftGraphConfig
from intelligent_email_service.exceptions import (
    EmailProviderError,
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
)

from .base import EmailProvider

logger = logging.getLogger(__name__)

HTTP_UNAUTHORIZED: int = 401
HTTP_TOO_MANY_REQUESTS: int = 429
HTTP_FORBIDDEN: int = 403
HTTP_NOT_FOUND: int = 404

DEFAULT_PAGE_SIZE: int = 50

# Core OData properties strictly required by EmailNode and DAG reconstructor
REQUIRED_GRAPH_FIELDS: set[str] = {
    "id",
    "conversationId",
    "internetMessageId",
    "internetMessageHeaders",
    "from",
    "toRecipients",
    "receivedDateTime",
    "body",
}


def _should_retry_graph_exception(exc: BaseException) -> bool:
    """Predicate for tenacity: retry on transport failures, 429 rate limits, and 5xx errors."""
    if isinstance(exc, httpx.TransportError):
        return True
    if not (isinstance(exc, httpx.HTTPStatusError) and exc.response is not None):
        return False
    return exc.response.status_code in (
        HTTP_TOO_MANY_REQUESTS,
        500,
        502,
        503,
        504,
    )


def _extract_retry_after(exc: BaseException) -> float | None:
    """Helper to safely extract numeric Retry-After header from 429 HTTP status errors."""
    if not (isinstance(exc, httpx.HTTPStatusError) and exc.response is not None):
        return None
    if exc.response.status_code != HTTP_TOO_MANY_REQUESTS:
        return None

    retry_header = exc.response.headers.get("Retry-After")
    if retry_header and retry_header.isdigit():
        return float(retry_header)
    return None


def _wait_graph_rate_limit_or_exponential(retry_state: RetryCallState) -> float:
    """Tenacity wait strategy: respects Graph API Retry-After header if 429, else exponential backoff."""
    if retry_state.outcome and retry_state.outcome.failed:
        retry_after = _extract_retry_after(retry_state.outcome.exception())
        if retry_after is not None:
            return retry_after
    return wait_exponential(min=1, max=30)(retry_state)


def _handle_httpx_error(
    exc: httpx.HTTPError,
    context_msg: str,
    partial_results: list[dict[str, Any]] | None = None,
) -> NoReturn:
    """Map httpx exceptions to custom exceptions for better error handling."""
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response is None:
        logger.warning("%s: transport-level failure - %s", context_msg, exc)
        raise EmailProviderError(
            f"{context_msg}: Network Request Failed - {exc}",
            partial_results=partial_results,
        ) from exc

    status = exc.response.status_code
    body = exc.response.text

    match status:
        case status if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            logger.warning(
                "%s: authentication error (%s) - %s", context_msg, status, body
            )
            raise ProviderAuthenticationError(
                f"{context_msg}: Authentication Error - {body}",
                partial_results=partial_results,
            ) from exc
        case status if status == HTTP_NOT_FOUND:
            logger.warning("%s: not found - %s", context_msg, body)
            raise ProviderNotFoundError(
                f"{context_msg}: Not Found - {body}",
                partial_results=partial_results,
            ) from exc
        case status if status == HTTP_TOO_MANY_REQUESTS:
            retry_header = exc.response.headers.get("Retry-After")
            retry_after = (
                int(retry_header) if retry_header and retry_header.isdigit() else None
            )
            logger.warning(
                "%s: rate limited (retry_after=%s) - %s", context_msg, retry_after, body
            )
            raise ProviderRateLimitError(
                f"{context_msg}: Rate Limit Exceeded - {body}",
                retry_after=retry_after,
                partial_results=partial_results,
            ) from exc
        case _:
            logger.warning("%s: HTTP %s - %s", context_msg, status, body)
            raise EmailProviderError(
                f"{context_msg}: HTTP Error {status} - {body}",
                partial_results=partial_results,
            ) from exc


class MicrosoftGraphProvider(EmailProvider):
    def __init__(
        self,
        *,
        credentials: AzureADCredentials | None = None,
        credential: Any | None = None,
        access_token: str | None = None,
        base_url: str = "https://graph.microsoft.com/v1.0",
        config: MicrosoftGraphConfig | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 5,
    ):
        """
        Args:
            credentials: Azure AD tenant/client/secret used to acquire tokens.
            credential: An azure.identity TokenCredential instance (e.g. ClientSecretCredential).
            access_token: A pre-issued Bearer token.
            base_url: Graph API base URL.
            config: Optional MicrosoftGraphConfig dataclass.
            client: Optional pre-configured httpx.AsyncClient.
            max_retries: Maximum number of tenacity retries for rate limits / transient errors.
        """
        if not credentials and not credential and not access_token:
            raise ProviderAuthenticationError(
                "MicrosoftGraphProvider requires either `credentials`, `credential`, or `access_token`."
            )

        self.credentials = credentials
        if credential is not None:
            self._credential = credential
        elif credentials is not None:
            self._credential = ClientSecretCredential(
                tenant_id=credentials.tenant_id,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
            )
        else:
            self._credential = None

        self._token_cache = access_token
        self.config = config or MicrosoftGraphConfig(base_url=base_url)
        if base_url != "https://graph.microsoft.com/v1.0":
            self.config.base_url = base_url
        self.base_url = self.config.base_url.rstrip("/")
        self.max_retries = max_retries

        self._external_client = client is not None
        self._client_kwargs: dict[str, Any] = {"base_url": self.base_url}
        if client is not None:
            self._client_kwargs["timeout"] = client.timeout

        self._client = client

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        config: MicrosoftGraphConfig | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 5,
    ) -> "MicrosoftGraphProvider":
        """Build a provider using Azure AD credentials or DefaultAzureCredential from environment."""
        try:
            credentials = AzureADCredentials.from_env()
            credential = ClientSecretCredential(
                tenant_id=credentials.tenant_id,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
            )
        except ValueError:
            credential = DefaultAzureCredential()

        return cls(
            credential=credential,
            base_url=base_url,
            config=config,
            client=client,
            max_retries=max_retries,
        )

    @classmethod
    def with_token(
        cls,
        access_token: str,
        *,
        base_url: str = "https://graph.microsoft.com/v1.0",
        config: MicrosoftGraphConfig | None = None,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 5,
    ) -> "MicrosoftGraphProvider":
        """Build a provider from a pre-issued access token."""
        return cls(
            access_token=access_token,
            base_url=base_url,
            config=config,
            client=client,
            max_retries=max_retries,
        )

    def _get_select_param(self) -> str:
        """Combine user-configured select_fields with mandatory core Graph fields."""
        fields = set(self.config.select_fields) | REQUIRED_GRAPH_FIELDS
        return ",".join(sorted(fields))

    async def get_access_token(self) -> str:
        """Acquire or return Bearer token via Azure Identity or static token."""
        if self._token_cache:
            return self._token_cache

        if self._credential:
            try:
                token_obj = await self._credential.get_token(
                    "https://graph.microsoft.com/.default"
                )
                return token_obj.token
            except Exception as exc:
                raise ProviderAuthenticationError(
                    f"Failed to acquire Azure AD token: {exc}"
                ) from exc

        raise ProviderAuthenticationError(
            "No Azure AD credential or access token available."
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Return an AsyncClient with a fresh token and base_url, updating headers in-place if needed."""
        token = await self.get_access_token()
        auth_header = f"Bearer {token}"

        if self._client is None or self._client.is_closed:
            headers = {"Authorization": auth_header}
            self._client = httpx.AsyncClient(headers=headers, **self._client_kwargs)
        else:
            self._client.headers["Authorization"] = auth_header

        return self._client

    async def _get_with_retry(
        self,
        url: str,
        params: dict[str, str] | None = None,
        context_msg: str = "Graph API request failed",
    ) -> httpx.Response:
        """Execute HTTP GET with tenacity exponential backoff & 429 Retry-After handling."""
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=_wait_graph_rate_limit_or_exponential,
            retry=retry_if_exception(_should_retry_graph_exception),
            reraise=True,
        ):
            with attempt:
                client = await self._get_client()
                try:
                    res = await client.get(url, params=params)
                    res.raise_for_status()
                    return res
                except httpx.HTTPError as exc:
                    if _should_retry_graph_exception(exc):
                        logger.warning(
                            "%s: transient error (attempt %d/%d) - %s",
                            context_msg,
                            attempt.retry_state.attempt_number,
                            self.max_retries,
                            exc,
                        )
                    raise
        raise EmailProviderError(
            f"{context_msg}: Request retries exhausted without a response."
        )

    async def close_client(self) -> None:
        """Close internal httpx HTTP client if not provided externally."""
        if self._client and not self._client.is_closed and not self._external_client:
            await self._client.aclose()

    async def close(self) -> None:
        """Close HTTP client and Azure Identity credential session."""
        await self.close_client()
        if self._credential:
            await self._credential.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @staticmethod
    def _format_iso_datetime(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    async def _iter_pages(
        self, initial_url: str, initial_params: dict[str, str], context_msg: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url: str | None = initial_url
        params = initial_params
        accumulated: list[dict[str, Any]] = []

        while url:
            try:
                res = await self._get_with_retry(
                    url, params=params, context_msg=context_msg
                )
                data = res.json()
                page_items = data.get("value") or []
                accumulated.extend(page_items)
                yield page_items
                url = data.get("@odata.nextLink")
                params = {}
            except httpx.HTTPError as exc:
                _handle_httpx_error(exc, context_msg, partial_results=accumulated)

    async def get_emails(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Retrieves raw messages from the advisor's mailbox, optionally filtered by date range."""
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date.")

        filters = []
        if start_date:
            filters.append(f"receivedDateTime ge {self._format_iso_datetime(start_date)}")
        if end_date:
            filters.append(f"receivedDateTime le {self._format_iso_datetime(end_date)}")

        effective_page_size = (
            page_size if page_size != DEFAULT_PAGE_SIZE else self.config.page_size
        )
        params: dict[str, str] = {
            "$top": str(effective_page_size),
            "$select": self._get_select_param(),
        }
        if filters:
            params["$filter"] = " and ".join(filters)

        url = f"{self.base_url}/users/{user_id}/messages"
        context_msg = f"Failed to retrieve messages for user '{user_id}'"

        return [
            msg
            async for page in self._iter_pages(url, params, context_msg)
            for msg in page
        ]

    async def get_emails_by_conversation_id(
        self,
        user_id: str,
        conversation_id: str,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """Retrieve all messages in a specific conversation thread."""
        escaped_conversation_id = conversation_id.replace("'", "''")

        effective_page_size = (
            page_size if page_size != DEFAULT_PAGE_SIZE else self.config.page_size
        )
        url = f"{self.base_url}/users/{user_id}/messages"
        params = {
            "$filter": f"conversationId eq '{escaped_conversation_id}'",
            "$top": str(effective_page_size),
            "$select": self._get_select_param(),
        }
        context_msg = (
            f"Failed to retrieve messages for user '{user_id}' "
            f"and conversation '{conversation_id}'"
        )

        return [
            msg
            async for page in self._iter_pages(url, params, context_msg)
            for msg in page
        ]

    async def get_attachment_bytes(
        self, user_id: str, message_id: str, attachment_id: str | None = None
    ) -> bytes:
        """Fetch raw attachment binary content using the Graph API message item ID."""
        if attachment_id:
            url = (
                f"{self.base_url}/users/{user_id}/messages/"
                f"{message_id}/attachments/{attachment_id}/$value"
            )
        else:
            url = f"{self.base_url}/users/{user_id}/messages/{message_id}/attachments/$value"

        context_msg = f"Failed to retrieve attachment content for message '{message_id}'"
        try:
            res = await self._get_with_retry(url, context_msg=context_msg)
            return res.content
        except httpx.HTTPError as exc:
            _handle_httpx_error(exc, context_msg)
