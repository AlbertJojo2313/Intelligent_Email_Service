from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from intelligent_email_service.email_connectors import MockGraphProvider
from intelligent_email_service.exceptions import (
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
)
from intelligent_email_service.retrieval.email_retrieval import EmailRetrievalService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, expected_exc",
    [
        (401, ProviderAuthenticationError),
        (404, ProviderNotFoundError),
        (429, ProviderRateLimitError),
    ],
)
async def test_provider_http_status_exceptions(status_code, expected_exc):
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = {"Retry-After": "30"} if status_code == 429 else {}
    mock_response.text = "Error"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            f"{status_code} Error", request=MagicMock(), response=mock_response
        )
        with pytest.raises(expected_exc) as exc_info:
            await provider.get_emails(user_id="user1")
        assert exc_info.value.status_code == status_code


@pytest.mark.asyncio
async def test_retrieval_service_propagates_provider_error():
    mock_provider = MagicMock()
    mock_provider.get_emails = AsyncMock(
        side_effect=ProviderAuthenticationError("Auth failed", status_code=401)
    )
    service = EmailRetrievalService(provider=mock_provider)

    with pytest.raises(ProviderAuthenticationError):
        await service.get_client_emails(
            advisor_id="adv1", client_id="client@example.com"
        )
