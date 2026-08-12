import asyncio
import html
import logging
import re
from typing import Any, ClassVar

import bs4

from intelligent_email_service.config import CleanerConfig

logger = logging.getLogger(__name__)

# Max non-empty lines following a generic salutation (e.g. "Thanks,") before treating it as mid-body content
MAX_SALUTATION_TRAILING_LINES: int = 3


class EmailCleaner:
    """
    Cleans email bodies while preserving conversational context.

    Responsibilities:
        • Remove HTML/CSS/scripts
        • Normalize whitespace
        • Remove signatures/disclaimers
        • Preserve quoted thread history
    """

    DEFAULT_SIGNATURE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^--(?: \r?\n|\r?\n)", re.MULTILINE),
        re.compile(
            r"^CONFIDENTIALITY NOTICE:.*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^This email and any attachments are intended only for.*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^\s*(?:Best regards|Regards|Kind regards|Sincerely|Thanks),\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^\s*Sent from my (?:iPhone|iPad|Android|mobile device)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]

    _SIGNATURE_RE: ClassVar[re.Pattern[str]]

    def __init__(self, config: CleanerConfig | None = None):
        self.config = config or CleanerConfig()

        if self.config.custom_signature_patterns:
            patterns = [
                *self.DEFAULT_SIGNATURE_PATTERNS,
                *self.config.custom_signature_patterns,
            ]
            self._signature_re = self._combine_patterns(patterns)
        else:
            self._signature_re = self._SIGNATURE_RE

    @staticmethod
    def _combine_patterns(
        patterns: list[re.Pattern[str]],
    ) -> re.Pattern[str]:
        combined = "|".join(f"(?:{p.pattern})" for p in patterns)
        return re.compile(
            combined,
            re.IGNORECASE | re.MULTILINE,
        )

    def clean_message(
        self,
        message: dict[str, Any] | Any,
    ) -> Any:
        """Return a cleaned copy of an email message or EmailNode."""
        if hasattr(message, "body_content"):
            raw = getattr(message, "body_content", "") or ""
            content_type = getattr(message, "content_type", "text") or "text"
            cleaned_text = self._clean_content(raw, content_type)
            message.cleaned_body = cleaned_text
            return message

        cleaned = dict(message)
        body = message.get("body", {})

        if isinstance(body, dict):
            raw = body.get("content") or ""
            content_type = body.get("contentType") or body.get("content_type") or "text"
        elif isinstance(body, str):
            raw = body
            content_type = "text"
        else:
            raw = ""
            content_type = "text"

        cleaned["cleaned_body"] = self._clean_content(
            raw,
            content_type,
        )
        return cleaned

    async def clean_messages_async(
        self,
        messages: list[Any],
    ) -> list[Any]:
        """Clean a batch of messages concurrently using Python's default thread pool."""
        if not messages:
            return []
        tasks = [asyncio.to_thread(self.clean_message, msg) for msg in messages]
        return await asyncio.gather(*tasks)

    def _clean_content(
        self,
        raw_content: str | None,
        content_type: str,
    ) -> str:
        raw_text = raw_content or ""

        if content_type.lower() == "html":
            text = self._clean_html(raw_text)
        else:
            text = self._normalize_whitespace(raw_text)

        if self.config.strip_signatures:
            text = self._remove_signature(text)

        return text.strip()

    def _clean_html(
        self,
        html_content: str,
    ) -> str:

        if not html_content.strip():
            return ""

        soup = bs4.BeautifulSoup(html_content, "lxml")

        for tag in soup([
            "script",
            "style",
            "head",
            "meta",
            "title",
            "noscript",
        ]):
            tag.decompose()

        if self.config.preserve_links:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text().strip()

                if href and text and href != text:
                    a.replace_with(f"{text} ({href})")
                elif href:
                    a.replace_with(href)

        for tag in soup.find_all([
            "br",
            "div",
            "p",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        ]):
            tag.append("\n")

        text = soup.get_text()

        return self._normalize_whitespace(
            html.unescape(text),
        )

    def _normalize_whitespace(
        self,
        text: str,
    ) -> str:

        text = text.replace("\xa0", " ")
        text = text.replace("&nbsp;", " ")

        lines = (line.rstrip() for line in text.splitlines())
        text = "\n".join(lines).strip()

        pattern = r"\n{" + str(self.config.max_blank_lines + 2) + r",}"
        replacement = "\n" * (self.config.max_blank_lines + 1)

        return re.sub(pattern, replacement, text)

    SALUTATION_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*(?:Best regards|Regards|Kind regards|Sincerely|Thanks),\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def _remove_signature(
        self,
        text: str,
    ) -> str:
        for match in self._signature_re.finditer(text):
            matched_str = match.group(0)
            # If the match is a generic salutation (e.g. "Thanks,"), verify it's near the end
            if self.SALUTATION_RE.match(matched_str):
                remaining_text = text[match.end() :]
                remaining_lines = [
                    line for line in remaining_text.splitlines() if line.strip()
                ]
                # If more than MAX_SALUTATION_TRAILING_LINES non-empty lines follow, "Thanks," is mid-body content
                if len(remaining_lines) > MAX_SALUTATION_TRAILING_LINES:
                    continue

            return text[: match.start()]

        return text


EmailCleaner._SIGNATURE_RE = EmailCleaner._combine_patterns(
    EmailCleaner.DEFAULT_SIGNATURE_PATTERNS
)
