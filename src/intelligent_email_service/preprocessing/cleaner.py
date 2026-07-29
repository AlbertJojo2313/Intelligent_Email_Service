import html
import re
from typing import Any, ClassVar

import bs4


class EmailCleaner:
    """
    Strips HTML tags, CSS styling, headers, signatures, and noise from email bodies
    """


    DEFAULT_SIGNATURE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^--(?: \r?\n|\r?\n)", re.MULTILINE),
        re.compile(r"^CONFIDENTIALITY NOTICE:.*$", re.IGNORECASE | re.MULTILINE),
        re.compile(
            r"^This email and any attachments are intended only for.*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^\s*(?:Best regards|Sincerely|Kind regards|Regards|Thanks),\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
        re.compile(
            r"^\s*Sent from my (?:iPhone|iPad|Android|mobile device)\s*$",
            re.IGNORECASE | re.MULTILINE,
        ),
    ]
    QUOTED_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^On\s+.*?\s+wrote:\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^-+\s*Original Message\s*-+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*From:\s+.*?\n\s*Sent:\s+", re.IGNORECASE | re.MULTILINE),
    ]

    # Pre-combined regexes for the *default* pattern sets, built once at class definition
    _DEFAULT_SIGNATURE_RE: ClassVar[re.Pattern[str]]
    _QUOTED_RE: ClassVar[re.Pattern[str]]
    _DEFAULT_COMBINED_RE: ClassVar[re.Pattern[str]]

    def __init__(
        self,
        strip_signatures: bool = True,
        strip_quotes: bool = True,
        max_blank_lines: int = 1,
        preserve_links: bool = False,
        custom_signature_patterns: list[re.Pattern[str]] | None = None,
    ):
        """
        Initialize cleaner with configurable options
        Args:
            strip_signatures (bool, optional): Whether to remove common email signature blocks. Defaults to True.
            strip_quotes (bool, optional): Whether to remove quoted email thread history. Defaults to True.
            max_blank_lines (int, optional): Maximum consecutive blank lines. Defaults to 1.
            preserve_links (bool, optional): Whether to extract link URLS. Defaults to False.
            custom_signature_patterns (list[re.Pattern[str]] | None, optional): Custom regexes. Defaults to None.
        """
        self.strip_signatures = strip_signatures
        self.strip_quotes = strip_quotes
        self.max_blank_lines = max_blank_lines
        self.preserve_links = preserve_links
        if custom_signature_patterns:
            self.signature_patterns = [
                *self.DEFAULT_SIGNATURE_PATTERNS,
                *custom_signature_patterns,
            ]
            self._signature_re = self._combine_patterns(self.signature_patterns)
            self._combined_re = self._combine_patterns(
                [*self.signature_patterns, *self.QUOTED_PATTERNS]
            )
        else:
            self.signature_patterns = self.DEFAULT_SIGNATURE_PATTERNS
            self._signature_re = self._DEFAULT_SIGNATURE_RE
            self._combined_re = self._DEFAULT_COMBINED_RE
        self._quoted_re = self._QUOTED_RE

    @staticmethod
    def _combine_patterns(patterns: list[re.Pattern[str]]) -> re.Pattern[str]:
        combined = "|".join(f"(?:{p.pattern})" for p in patterns)
        return re.compile(combined, re.IGNORECASE | re.MULTILINE | re.DOTALL)

    def _clean_content(self, raw_content: str, content_type: str) -> str:
        cleaners = {"html": self._clean_html, "text": self._normalize_whitespace}

        # default to _normalize_whitespace
        clean_func = cleaners.get(content_type.lower(), self._normalize_whitespace)
        text = clean_func(raw_content)

        if self.strip_signatures or self.strip_quotes:
            text = self._truncate_at_earliest(
                text, use_signatures=self.strip_signatures, use_quotes=self.strip_quotes
            )
        return text.strip()

    def clean_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Cleans a single email message dictionary and adds 'cleaned_body'"""
        cleaned_msg = dict(message)
        body_obj = message.get("body", {})

        match body_obj:
            case dict():
                raw_content = body_obj.get("content") or ""
                content_type = (
                    body_obj.get("contentType") or body_obj.get("content_type") or "text"
                )
            case str():
                raw_content = body_obj
                content_type = "text"
            case _:
                raw_content = ""
                content_type = "text"

        clean_text = self._clean_content(raw_content, content_type)
        cleaned_msg["cleaned_body"] = clean_text
        return cleaned_msg

    def _clean_html(self, html_content: str) -> str:
        """Extract plain text from HTML, removing scripts/styles and formatting links."""
        if not html_content or not html_content.strip():
            return ""
        soup = bs4.BeautifulSoup(html_content, "lxml")

        for element in soup(["script", "style", "head", "title", "meta", "noscript"]):
            element.decompose()

        # Extract and format links if enabled
        if self.preserve_links:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                link_text = a.get_text().strip()
                if href and link_text and href != link_text:
                    a.replace_with(f"{link_text} ({href})")
                elif href:
                    a.replace_with(href)

        for block in soup.find_all(
            ["br", "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"]
        ):
            block.append("\n")

        text = soup.get_text()
        unescaped = html.unescape(text)
        return self._normalize_whitespace(unescaped)


    def _normalize_whitespace(self, text: str) -> str:
        text = text.replace("\xa0", " ").replace("&nbsp;", " ")

        # Trim trailing spaces on each line
        lines = [line.rstrip() for line in text.splitlines()]
        text = "\n".join(lines).strip()

        # Collapse excess blank lines according to max_blank_lines
        if self.max_blank_lines >= 0:
            pattern = r"\n{" + str(self.max_blank_lines + 2) + r",}"
            replacement = "\n" * (self.max_blank_lines + 1)
            text = re.sub(pattern, replacement, text)
        return text

    def _truncate_at_earliest(
        self, text: str, use_signatures: bool = True, use_quotes: bool = True
    ) -> str:
        """
        Truncates text at the earliest match of either a signature or a
        quoted history boundary using a single combined regex scan.
        """
        if use_signatures and use_quotes:
            match = self._combined_re.search(text)
            return text[: match.start()] if match else text
        if use_signatures:
            match = self._signature_re.search(text)
            return text[: match.start()] if match else text
        if use_quotes:
            match = self._quoted_re.search(text)
            return text[: match.start()] if match else text
        return text



EmailCleaner._DEFAULT_SIGNATURE_RE = EmailCleaner._combine_patterns(
    EmailCleaner.DEFAULT_SIGNATURE_PATTERNS
)
EmailCleaner._QUOTED_RE = EmailCleaner._combine_patterns(EmailCleaner.QUOTED_PATTERNS)
EmailCleaner._DEFAULT_COMBINED_RE = EmailCleaner._combine_patterns(
    [*EmailCleaner.DEFAULT_SIGNATURE_PATTERNS, *EmailCleaner.QUOTED_PATTERNS]
)
