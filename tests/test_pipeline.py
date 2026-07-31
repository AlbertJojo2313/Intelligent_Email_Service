from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intelligent_email_service import (
    CompressorConfig,
    EmailQueryFilter,
    MockGraphProvider,
    PipelineConfig,
    process_client_emails,
)


@pytest.mark.asyncio
async def test_process_client_emails_end_to_end():
    provider = MockGraphProvider(base_url="http://localhost:3000")

    query = EmailQueryFilter(
        advisor_id="bob@advisor.com",
        client_id="jane@client.com",
    )

    config = PipelineConfig(
        compressor=CompressorConfig(use_llmlingua=False),
    )

    mock_messages = [
        {
            "id": "msg-001",
            "subject": "Re: Portfolio Review Q3",
            "conversationId": "conv-100",
            "receivedDateTime": "2026-07-28T10:00:00Z",
            "from": {
                "emailAddress": {
                    "name": "Jane Client",
                    "address": "jane@client.com",
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "name": "Advisor Bob",
                        "address": "bob@advisor.com",
                    }
                }
            ],
            "body": {
                "contentType": "html",
                "content": "<p>Hi Bob, let's proceed with portfolio rebalancing.</p><br>Best regards,<br>Jane",
            },
            "attachments": [
                {"id": "att-1", "name": "statement.pdf", "size": 2048, "contentType": "application/pdf"}
            ],
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
        compressed_thread = threads[0]
        assert compressed_thread.subject == "Portfolio Review Q3"
        assert compressed_thread.total_messages == 1
        assert len(compressed_thread.compressed_messages) == 1

        msg = compressed_thread.compressed_messages[0]
        assert msg["cleaned_body"] == "Hi Bob, let's proceed with portfolio rebalancing."
        assert msg["compressed_body"] == "Hi Bob, let's proceed with portfolio rebalancing."
        assert len(compressed_thread.attachments_summary) == 1
        assert compressed_thread.attachments_summary[0]["name"] == "statement.pdf"
