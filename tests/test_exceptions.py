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
async def test_provider_authentication_error():
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )
        with pytest.raises(ProviderAuthenticationError) as exc_info:
            await provider.get_emails(user_id="user1")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_provider_not_found_error():
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )
        with pytest.raises(ProviderNotFoundError) as exc_info:
            await provider.get_emails(user_id="user1")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_provider_rate_limit_error():
    provider = MockGraphProvider(base_url="http://localhost:3000")
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "30"}
    mock_response.text = "Rate limited"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError(
            "429 Rate Limit", request=MagicMock(), response=mock_response
        )
        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider.get_emails(user_id="user1")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == 30


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
