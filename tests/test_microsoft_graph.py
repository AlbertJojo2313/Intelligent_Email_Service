from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from intelligent_email_service.config import AzureADCredentials, MicrosoftGraphConfig
from intelligent_email_service.email_connectors.microsoft_graph import (
    REQUIRED_GRAPH_FIELDS,
    MicrosoftGraphProvider,
)
from intelligent_email_service.exceptions import (
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
)


@pytest.fixture
def dummy_credentials():
    return AzureADCredentials(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
    )


@pytest.fixture
def graph_config():
    return MicrosoftGraphConfig(
        base_url="https://graph.microsoft.com/v1.0",
        page_size=25,
        select_fields=["id", "subject", "customField"],
    )


def test_provider_init_requires_credentials_or_token():
    with pytest.raises(ProviderAuthenticationError):
        MicrosoftGraphProvider()


def test_provider_select_params_merging(dummy_credentials, graph_config):
    provider = MicrosoftGraphProvider(
        credentials=dummy_credentials, access_token="static-token", config=graph_config
    )
    select_str = provider._get_select_param()
    selected_fields = set(select_str.split(","))

    # Must contain custom config fields
    assert "customField" in selected_fields
    assert "subject" in selected_fields

    # Must defensively contain all REQUIRED_GRAPH_FIELDS
    assert REQUIRED_GRAPH_FIELDS.issubset(selected_fields)


@pytest.mark.asyncio
async def test_get_emails_with_select_and_filters(dummy_credentials, graph_config):
    provider = MicrosoftGraphProvider.with_token("test-token", config=graph_config)

    mock_response = httpx.Response(
        status_code=200,
        json={"value": [{"id": "msg-1", "subject": "Test"}]},
        request=httpx.Request(
            "GET", "https://graph.microsoft.com/v1.0/users/user1/messages"
        ),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = datetime(2026, 8, 10, tzinfo=UTC)
        emails = await provider.get_emails(
            "user1", start_date=start, end_date=end, page_size=25
        )

        assert len(emails) == 1
        assert emails[0]["id"] == "msg-1"

        # Check call params
        assert mock_get.called
        call_kwargs = mock_get.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("$top") == "25"
        assert "$select" in params
        assert "receivedDateTime ge 2026-08-01T00:00:00Z" in params.get("$filter", "")


@pytest.mark.asyncio
async def test_get_emails_by_conversation_id_escapes_single_quotes(dummy_credentials):
    provider = MicrosoftGraphProvider.with_token("test-token")

    mock_response = httpx.Response(
        status_code=200,
        json={"value": [{"id": "msg-2", "conversationId": "conv'123"}]},
        request=httpx.Request(
            "GET", "https://graph.microsoft.com/v1.0/users/user1/messages"
        ),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        emails = await provider.get_emails_by_conversation_id("user1", "conv'123")

        assert len(emails) == 1
        params = mock_get.call_args.kwargs.get("params", {})
        assert params.get("$filter") == "conversationId eq 'conv''123'"


@pytest.mark.asyncio
async def test_get_attachment_bytes(dummy_credentials):
    provider = MicrosoftGraphProvider.with_token("test-token")

    mock_response = httpx.Response(
        status_code=200,
        content=b"PDF-BINARY-CONTENT",
        request=httpx.Request("GET", "http://test"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        data = await provider.get_attachment_bytes("user1", "msg123", "att456")
        assert data == b"PDF-BINARY-CONTENT"


@pytest.mark.asyncio
async def test_429_rate_limit_retry(dummy_credentials):
    provider = MicrosoftGraphProvider.with_token("test-token")

    resp_429 = httpx.Response(
        status_code=429,
        headers={"Retry-After": "0"},
        request=httpx.Request("GET", "http://test"),
    )
    resp_200 = httpx.Response(
        status_code=200,
        json={"value": [{"id": "msg-retry"}]},
        request=httpx.Request("GET", "http://test"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [resp_429, resp_200]
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            emails = await provider.get_emails("user1")
            assert len(emails) == 1
            assert emails[0]["id"] == "msg-retry"
            assert mock_sleep.called


@pytest.mark.asyncio
async def test_404_not_found_error_mapping(dummy_credentials):
    provider = MicrosoftGraphProvider.with_token("test-token")

    resp_404 = httpx.Response(
        status_code=404,
        text="User not found",
        request=httpx.Request("GET", "http://test"),
    )

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = resp_404
        with pytest.raises(ProviderNotFoundError):
            await provider.get_emails("nonexistent-user")
