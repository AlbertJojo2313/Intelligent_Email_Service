import re
import pytest

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
    cleaner_no_links = EmailCleaner(preserve_links=False)
    cleaner_links = EmailCleaner(preserve_links=True)

    html = '<p>Check <a href="https://example.com">this link</a> for details.</p>'

    cleaned_no_links = cleaner_no_links._clean_html(html)
    assert cleaned_no_links == "Check this link for details."

    cleaned_links = cleaner_links._clean_html(html)
    assert cleaned_links == "Check this link (https://example.com) for details."


def test_strip_signatures():
    cleaner = EmailCleaner(strip_signatures=True)

    email = (
        "Hi Team,\n\n"
        "Let's schedule the meeting.\n\n"
        "Best regards,\n"
        "Jane Doe\n"
        "CONFIDENTIALITY NOTICE: This email is private."
    )

    cleaned = cleaner._clean_content(email, content_type="text")
    assert "Let's schedule the meeting." in cleaned
    assert "Best regards" not in cleaned
    assert "CONFIDENTIALITY NOTICE" not in cleaned


def test_normalize_whitespace_and_blank_lines():
    cleaner = EmailCleaner(max_blank_lines=1)

    text = "Hello\xa0World&nbsp;   \n\n\n\n\nNext line."
    cleaned = cleaner._normalize_whitespace(text)

    assert "Hello World" in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned == "Hello World\n\nNext line."


def test_clean_message_dict():
    cleaner = EmailCleaner()

    raw_msg = {
        "id": "msg-123",
        "subject": "Portfolio Update",
        "body": {
            "contentType": "html",
            "content": "<div>Hello,<br><br>Portfolio is updated.<br><br>Thanks,<br>Jane</div>",
        },
    }

    cleaned_msg = cleaner.clean_message(raw_msg)

    assert "cleaned_body" in cleaned_msg
    assert cleaned_msg["cleaned_body"] == "Hello,\n\nPortfolio is updated."
    assert cleaned_msg["id"] == "msg-123"
    # Ensure original is not mutated
    assert "cleaned_body" not in raw_msg


def test_clean_message_string_body():
    cleaner = EmailCleaner()

    raw_msg = {
        "id": "msg-456",
        "body": "Plain text email body.\n\nSent from my iPhone",
    }

    cleaned_msg = cleaner.clean_message(raw_msg)
    assert cleaned_msg["cleaned_body"] == "Plain text email body."


def test_clean_message_null_content():
    cleaner = EmailCleaner()

    raw_msg = {
        "id": "msg-789",
        "body": {"contentType": "text", "content": None},
    }

    cleaned_msg = cleaner.clean_message(raw_msg)
    assert cleaned_msg["cleaned_body"] == ""


def test_custom_signature_patterns():
    custom_pattern = re.compile(r"^---\s*My Custom Signature\s*---", re.MULTILINE)
    cleaner = EmailCleaner(
        strip_signatures=True,
        custom_signature_patterns=[custom_pattern],
    )

    email = "Some text.\n\n--- My Custom Signature ---\nExtra info"
    cleaned = cleaner._clean_content(email, content_type="text")
    assert cleaned.strip() == "Some text."


def test_mid_body_thanks_does_not_over_truncate():
    cleaner = EmailCleaner(strip_signatures=True)

    email = (
        "Hi Jane,\n\n"
        "Thanks,\n"
        "I received your documents and will review them tomorrow.\n"
        "Please let me know if you need any additional statements.\n"
        "We can also schedule a call next week.\n\n"
        "Best regards,\n"
        "John Doe"
    )

    cleaned = cleaner._clean_content(email, content_type="text")
    assert "received your documents" in cleaned
    assert "schedule a call next week" in cleaned
    assert "John Doe" not in cleaned

