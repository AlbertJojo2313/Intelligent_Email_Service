import re
import pytest

from intelligent_email_service import CleanerConfig
from intelligent_email_service.preprocessing.cleaner import EmailCleaner


def test_clean_html_basic():
    cleaner = EmailCleaner()
    html_raw = """
    <html>
        <head><title>Test Title</title><style>body { color: red; }</style></head>
        <body>
            <script>alert("test");</script>
            <div>Hi <b>John</b>,</div>
            <p>Please review &amp; approve the document &gt; $100k.</p>
        </body>
    </html>
    """
    cleaned = cleaner._clean_html(html_raw)
    assert "<script>" not in cleaned
    assert "style" not in cleaned
    assert "Test Title" not in cleaned
    assert "Hi John," in cleaned
    assert "review & approve the document > $100k." in cleaned


def test_clean_html_preserve_links():
    cleaner_no_links = EmailCleaner(config=CleanerConfig(preserve_links=False))
    cleaner_links = EmailCleaner(config=CleanerConfig(preserve_links=True))

    html = '<p>Check <a href="https://example.com">this link</a> for details.</p>'

    assert cleaner_no_links._clean_html(html) == "Check this link for details."
    assert cleaner_links._clean_html(html) == "Check this link (https://example.com) for details."


def test_strip_signatures():
    cleaner = EmailCleaner(config=CleanerConfig(strip_signatures=True))
    email = "Hi Team,\n\nMeeting at 3pm.\n\nBest regards,\nJane Doe\nCONFIDENTIALITY NOTICE: Private."

    cleaned = cleaner._clean_content(email, content_type="text")
    assert "Meeting at 3pm." in cleaned
    assert "Best regards" not in cleaned
    assert "CONFIDENTIALITY NOTICE" not in cleaned


def test_normalize_whitespace_and_blank_lines():
    cleaner = EmailCleaner(config=CleanerConfig(max_blank_lines=1))
    text = "Hello\xa0World&nbsp;   \n\n\n\n\nNext line."
    assert cleaner._normalize_whitespace(text) == "Hello World\n\nNext line."


@pytest.mark.parametrize(
    "raw_body, expected_cleaned",
    [
        (
            {"contentType": "html", "content": "<div>Hello,<br><br>Updated.<br><br>Thanks,<br>Jane</div>"},
            "Hello,\n\nUpdated.",
        ),
        ("Plain text email body.\n\nSent from my iPhone", "Plain text email body."),
        ({"contentType": "text", "content": None}, ""),
    ],
)
def test_clean_message_body_variations(raw_body, expected_cleaned):
    cleaner = EmailCleaner()
    cleaned_msg = cleaner.clean_message({"id": "msg-1", "body": raw_body})
    assert cleaned_msg["cleaned_body"] == expected_cleaned


def test_custom_signature_patterns():
    custom_pattern = re.compile(r"^---\s*My Custom Signature\s*---", re.MULTILINE)
    cleaner = EmailCleaner(
        config=CleanerConfig(strip_signatures=True, custom_signature_patterns=[custom_pattern])
    )
    email = "Some text.\n\n--- My Custom Signature ---\nExtra info"
    assert cleaner._clean_content(email, content_type="text").strip() == "Some text."


@pytest.mark.asyncio
async def test_clean_messages_async():
    cleaner = EmailCleaner()
    msgs = [
        {"id": "1", "body": {"contentType": "html", "content": "<div>Hello <b>World</b></div>"}},
        {"id": "2", "body": "Plain text email\n\nBest regards,\nJane"},
    ]
    cleaned = await cleaner.clean_messages_async(msgs)
    assert len(cleaned) == 2
    assert cleaned[0]["cleaned_body"] == "Hello World"
    assert "Best regards" not in cleaned[1]["cleaned_body"]
