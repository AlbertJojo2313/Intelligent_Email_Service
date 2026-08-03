from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intelligent_email_service import (
    CleanerConfig,
    CompressorConfig,
    EmailQueryFilter,
    MockGraphProvider,
    PipelineConfig,
    process_client_emails,
)


@pytest.mark.asyncio
async def test_process_client_emails_with_config_objects():
    provider = MockGraphProvider(base_url="http://localhost:3000")

    query = EmailQueryFilter(
        advisor_id="bob@advisor.com",
        client_id="jane@client.com",
    )

    config = PipelineConfig(
        cleaner=CleanerConfig(strip_signatures=True),
        compressor=CompressorConfig(recent_full_count=1, max_full_body_chars=200, use_llmlingua=False),
        max_concurrency=5,
    )

    mock_messages = [
        {
            "id": "msg-101",
            "subject": "Tax Planning 2026",
            "conversationId": "conv-200",
            "receivedDateTime": "2026-07-29T11:00:00Z",
            "from": {"emailAddress": {"address": "jane@client.com"}},
            "toRecipients": [{"emailAddress": {"address": "bob@advisor.com"}}],
            "body": {"contentType": "text", "content": "Let's review tax strategies for 2026."},
        }
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"value": mock_messages}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        threads = await process_client_emails(
            query=query,
            config=config,
            provider=provider,
        )

        assert len(threads) == 1
        assert threads[0].subject == "Tax Planning 2026"
        assert threads[0].compressed_body == "Let's review tax strategies for 2026."
