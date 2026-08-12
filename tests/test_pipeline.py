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
                {
                    "id": "att-1",
                    "name": "statement.pdf",
                    "size": 2048,
                    "contentType": "application/pdf",
                }
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
        assert (
            compressed_thread.compressed_body
            == "Hi Bob, let's proceed with portfolio rebalancing."
        )
        assert len(compressed_thread.attachments_summary) == 1
        assert compressed_thread.attachments_summary[0]["name"] == "statement.pdf"


@pytest.mark.asyncio
async def test_main_success(tmp_path, monkeypatch):
    from intelligent_email_service.pipeline import main
    from intelligent_email_service.preprocessing.compressor import CompressedThread

    mock_threads = [
        CompressedThread(
            subject="Test Subject",
            conversation_id="conv-123",
            format="full_quoted",
            total_messages=1,
            compressed_body="Test compressed body",
            attachments_summary=[],
            estimated_tokens=50,
            used_llmlingua=False,
        )
    ]

    monkeypatch.chdir(tmp_path)
    with patch(
        "intelligent_email_service.pipeline.process_client_emails", new_callable=AsyncMock
    ) as mock_process:
        mock_process.return_value = mock_threads
        await main()

    output_file = tmp_path / "compressed_threads.json"
    assert output_file.exists()


@pytest.mark.asyncio
async def test_main_email_provider_error(tmp_path, monkeypatch):
    from intelligent_email_service.exceptions import EmailProviderError
    from intelligent_email_service.pipeline import main

    monkeypatch.chdir(tmp_path)
    with patch(
        "intelligent_email_service.pipeline.process_client_emails", new_callable=AsyncMock
    ) as mock_process:
        mock_process.side_effect = EmailProviderError("Connection failed")
        await main()

    output_file = tmp_path / "compressed_threads.json"
    assert not output_file.exists()
