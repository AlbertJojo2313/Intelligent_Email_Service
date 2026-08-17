from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intelligent_email_service.config import MicrosoftGraphConfig
from intelligent_email_service.email_connectors.email_manager import (
    EmailProviderManager,
    ProviderType,
)
from intelligent_email_service.email_connectors.microsoft_graph import (
    MicrosoftGraphProvider,
)
from intelligent_email_service.retrieval.attachment_processor import (
    fetch_attachment_text,
    is_text_readable_attachment,
    process_node_attachments,
)
from intelligent_email_service.retrieval.email_node import EmailNode


def test_email_provider_manager_passes_config():
    config = MicrosoftGraphConfig(
        base_url="https://graph.microsoft.com/v1.0",
        page_size=10,
        select_fields=["id", "subject"],
    )
    provider = EmailProviderManager.create(
        provider_type=ProviderType.MICROSOFT,
        access_token="mock-token",
        config=config,
    )
    assert isinstance(provider, MicrosoftGraphProvider)
    assert provider.config.page_size == 10
    assert "subject" in provider._get_select_param()


def test_is_text_readable_attachment():
    txt_att = {"name": "report.txt", "contentType": "text/plain"}
    csv_att = {"name": "data.csv", "contentType": "application/octet-stream"}
    bin_att = {"name": "image.png", "contentType": "image/png"}

    assert is_text_readable_attachment(txt_att) is True
    assert is_text_readable_attachment(csv_att) is True
    assert is_text_readable_attachment(bin_att) is False


@pytest.mark.asyncio
async def test_fetch_attachment_text():
    mock_provider = MagicMock()
    mock_provider.get_attachment_bytes = AsyncMock(return_value=b"Col1,Col2\nVal1,Val2")

    attach = {"id": "att1", "name": "data.csv", "contentType": "text/csv"}
    text = await fetch_attachment_text(mock_provider, "user1", "msg1", attach)

    assert text == "Col1,Col2\nVal1,Val2"
    mock_provider.get_attachment_bytes.assert_called_once_with(
        user_id="user1", message_id="msg1", attachment_id="att1"
    )


@pytest.mark.asyncio
async def test_process_node_attachments_does_not_mutate_message_body():
    mock_provider = MagicMock()
    mock_provider.get_attachment_bytes = AsyncMock(return_value=b"Line 1\nLine 2")

    node = EmailNode(
        id="node1",
        subject="Test",
        body_content="Initial Body",
        cleaned_body="Initial Body",
        attachments=[
            {"id": "att1", "name": "notes.txt", "contentType": "text/plain"},
            {"id": "att2", "name": "photo.jpg", "contentType": "image/jpeg"},
        ],
    )

    summaries = await process_node_attachments(mock_provider, "user1", node)

    assert len(summaries) == 2
    assert "Uncompressed text content preserved" in summaries[0]
    assert "photo.jpg" in summaries[1]
    # Verify attachment content is stored uncompressed on the attachment dict
    assert node.attachments[0]["content"] == "Line 1\nLine 2"
    # Verify message body is left completely unpolluted for email body compression
    assert node.body_content == "Initial Body"
    assert node.cleaned_body == "Initial Body"


@pytest.mark.asyncio
async def test_fetch_attachment_empty_bytes():
    mock_provider = MagicMock()
    mock_provider.get_attachment_bytes = AsyncMock(return_value=b"")

    attach = {"id": "att-empty", "name": "empty.txt", "contentType": "text/plain"}
    result = await fetch_attachment_text(mock_provider, "u1", "m1", attach)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_attachment_latin1_fallback():
    mock_provider = MagicMock()
    mock_provider.get_attachment_bytes = AsyncMock(
        return_value="Resum\xe9 details".encode("latin-1")
    )

    attach = {"id": "att-latin", "name": "doc.txt", "contentType": "text/plain"}
    result = await fetch_attachment_text(mock_provider, "u1", "m1", attach)
    assert result is not None
    assert "Resum" in result


@pytest.mark.asyncio
async def test_process_node_attachments_provider_exception_resilience():
    mock_provider = MagicMock()
    mock_provider.get_attachment_bytes = AsyncMock(
        side_effect=RuntimeError("Transient network drop")
    )

    node = EmailNode(
        id="node-err",
        subject="Test Error Handling",
        attachments=[{"id": "att-err", "name": "notes.txt", "contentType": "text/plain"}],
    )

    summaries = await process_node_attachments(mock_provider, "u1", node)
    assert len(summaries) == 1
    assert "notes.txt" in summaries[0]
    assert "content" not in node.attachments[0]
