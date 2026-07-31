import pytest

from intelligent_email_service import CompressorConfig
from intelligent_email_service.preprocessing.compressor import CompressedThread, EmailCompressor
from intelligent_email_service.retrieval.thread_processor import ProcessedThread, ThreadFormat


def test_compress_full_quoted_thread_bypasses_compression():
    compressor = EmailCompressor(config=CompressorConfig(recent_full_count=2, use_llmlingua=False))

    msg = {
        "id": "msg-1",
        "subject": "Re: Portfolio Review",
        "cleaned_body": "Hello John, let's proceed with rebalancing.",
        "attachments": [{"id": "att-1", "name": "report.pdf", "size": 1024}],
    }

    thread = ProcessedThread(
        subject="Re: Re: Portfolio Review",
        conversation_id="conv-123",
        format=ThreadFormat.FULL_QUOTED,
        reconstructed=False,
        messages=[msg],
    )

    result = compressor.compress_processed_thread(thread)

    assert isinstance(result, CompressedThread)
    assert result.subject == "Portfolio Review"
    assert result.total_messages == 1
    assert result.used_llmlingua is False
    assert len(result.compressed_messages) == 1
    assert result.compressed_messages[0]["compressed_body"] == "Hello John, let's proceed with rebalancing."
    assert len(result.attachments_summary) == 1
    assert result.attachments_summary[0]["name"] == "report.pdf"


def test_compress_modified_multi_message_thread():
    compressor = EmailCompressor(
        config=CompressorConfig(recent_full_count=2, max_full_body_chars=50, use_llmlingua=False)
    )

    msg1 = {"id": "m1", "cleaned_body": "This is an older message that should be truncated because it is long."}
    msg2 = {"id": "m2", "cleaned_body": "This is another older message that should also be truncated."}
    msg3 = {"id": "m3", "cleaned_body": "This is recent message 1, keep full text."}
    msg4 = {"id": "m4", "cleaned_body": "This is recent message 2, keep full text."}

    thread = ProcessedThread(
        subject="Re: Account Inquiry",
        conversation_id="conv-456",
        format=ThreadFormat.MODIFIED,
        reconstructed=True,
        messages=[msg1, msg2, msg3, msg4],
    )

    result = compressor.compress_processed_thread(thread)

    assert result.total_messages == 4
    # Recent 2 messages kept full text
    assert result.compressed_messages[2]["compressed_body"] == "This is recent message 1, keep full text."
    assert result.compressed_messages[3]["compressed_body"] == "This is recent message 2, keep full text."

    # Older 2 messages truncated
    assert "[... truncated]" in result.compressed_messages[0]["compressed_body"]
    assert "[... truncated]" in result.compressed_messages[1]["compressed_body"]


def test_clean_subject():
    assert EmailCompressor.clean_subject("Re: Fwd: FW: re: Financial Statement") == "Financial Statement"
    assert EmailCompressor.clean_subject("Quarterly Planning") == "Quarterly Planning"
