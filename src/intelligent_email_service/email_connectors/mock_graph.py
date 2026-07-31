from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, NoReturn

import httpx

from ..exceptions import (
    EmailProviderError,
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
)
from ..utils import get_message_datetime, parse_iso_datetime
from .base import EmailProvider


HTTP_UNAUTHORIZED: int = 401
HTTP_FORBIDDEN: int = 403
HTTP_NOT_FOUND: int = 404
HTTP_TOO_MANY_REQUESTS: int = 429


def _handle_httpx_error(exc: httpx.HTTPError, context_msg: str) -> NoReturn:
    """Map raw httpx exceptions to domain-specific EmailProviderError subclasses using pattern matching."""
    if not isinstance(exc, httpx.HTTPStatusError):
        raise EmailProviderError(
            f"{context_msg}: Network request failed - {exc}"
        ) from exc

    status = exc.response.status_code
    body = exc.response.text

    match status:
        case status if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            raise ProviderAuthenticationError(
                f"{context_msg}: Authentication failed ({status})",
                status_code=status,
                response_body=body,
            ) from exc
        case status if status == HTTP_NOT_FOUND:
            raise ProviderNotFoundError(
                f"{context_msg}: Resource not found ({status})",
                status_code=status,
                response_body=body,
            ) from exc
        case status if status == HTTP_TOO_MANY_REQUESTS:
            retry_header = exc.response.headers.get("Retry-After")
            retry_after = (
                int(retry_header) if retry_header and retry_header.isdigit() else None
            )
            raise ProviderRateLimitError(
                f"{context_msg}: Rate limit exceeded ({status})",
                retry_after=retry_after,
                status_code=status,
                response_body=body,
            ) from exc
        case _:
            raise EmailProviderError(
                f"{context_msg}: Provider HTTP error ({status})",
                status_code=status,
                response_body=body,
            ) from exc


class MockGraphProvider(EmailProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_emails(
        self,
        user_id: str = "advisor@example.com",
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve messages from an advisor's mailbox with error handling and date filtering."""
        try:
            client = self._get_client()
            response = await client.get(
                f"{self.base_url}/v1.0/users/{user_id}/messages"
            )
            response.raise_for_status()
            messages = response.json()["value"]
        except httpx.HTTPError as exc:
            _handle_httpx_error(exc, f"Failed to retrieve messages for user '{user_id}'")

        return self._filter_by_date(
            messages=messages,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_advisors_list(self) -> list[dict[str, Any]]:
        try:
            client = self._get_client()
            response = await client.get(f"{self.base_url}/v1.0/users/")
            response.raise_for_status()
            return response.json()["value"]
        except httpx.HTTPError as exc:
            _handle_httpx_error(exc, "Failed to retrieve advisors list")

    async def get_advisor_info(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        try:
            client = self._get_client()
            response = await client.get(f"{self.base_url}/v1.0/users/{user_id}")
            response.raise_for_status()
            res_data = response.json()
            return (
                res_data.get("value", res_data)
                if isinstance(res_data, dict)
                else res_data
            )
        except httpx.HTTPError as exc:
            _handle_httpx_error(exc, f"Failed to retrieve info for advisor '{user_id}'")

    async def get_emails_by_conversation_id(
        self, user_id: str, conversation_id: str
    ) -> list[dict[str, Any]]:
        """
        Retrieve all messages belonging to a conversation.

        Mockoon endpoint:
            GET /v1.0/users/{user-id}/messages?$filter=conversationId eq '{conversation_id}'
        """
        try:
            client = self._get_client()
            response = await client.get(
                f"{self.base_url}/v1.0/users/{user_id}/messages",
                params={"$filter": f"conversationId eq '{conversation_id}'"},
            )
            response.raise_for_status()
            return response.json()["value"]
        except httpx.HTTPError as exc:
            _handle_httpx_error(
                exc, f"Failed to retrieve conversation '{conversation_id}'"
            )

    _parse_iso_date = staticmethod(parse_iso_datetime)

    @staticmethod
    def _normalize_date(date: datetime) -> datetime:
        if date.tzinfo is None:
            return date.replace(tzinfo=UTC)
        return date.astimezone(UTC)

    @staticmethod
    def _in_date_range(
        message_date: datetime,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> bool:
        message_date = MockGraphProvider._normalize_date(message_date)
        if start_date:
            start_date = MockGraphProvider._normalize_date(start_date)
        if end_date:
            end_date = MockGraphProvider._normalize_date(end_date)
        if start_date and message_date < start_date:
            return False
        return not (end_date and message_date > end_date)

    @staticmethod
    def _filter_by_date(
        messages: Iterable[dict[str, Any]],
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[dict[str, Any]]:
        if start_date is None and end_date is None:
            return list(messages)

        filtered: list[dict[str, Any]] = []
        for message in messages:
            dt = get_message_datetime(message, default_to_min=False)
            if dt and MockGraphProvider._in_date_range(dt, start_date, end_date):
                filtered.append(message)
        return filtered
