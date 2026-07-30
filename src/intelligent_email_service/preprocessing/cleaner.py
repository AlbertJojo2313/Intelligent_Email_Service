import html
import re
from typing import Any, ClassVar

import bs4


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

    def __init__(
        self,
        *,
        strip_signatures: bool = True,
        max_blank_lines: int = 1,
        preserve_links: bool = False,
        custom_signature_patterns: list[re.Pattern[str]] | None = None,
    ):
        self.strip_signatures = strip_signatures
        self.max_blank_lines = max_blank_lines
        self.preserve_links = preserve_links

        if custom_signature_patterns:
            patterns = [
                *self.DEFAULT_SIGNATURE_PATTERNS,
                *custom_signature_patterns,
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
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )

    def clean_message(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Return a cleaned copy of an email message.

        Adds:
            cleaned_body
        """

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

        if self.strip_signatures:
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

        if self.preserve_links:
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

        pattern = r"\n{" + str(self.max_blank_lines + 2) + r",}"
        replacement = "\n" * (self.max_blank_lines + 1)

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
                remaining_text = text[match.end():]
                remaining_lines = [
                    line for line in remaining_text.splitlines() if line.strip()
                ]
                # If more than 3 non-empty lines follow, "Thanks," is mid-body content
                if len(remaining_lines) > 3:
                    continue

            return text[: match.start()]

        return text


EmailCleaner._SIGNATURE_RE = EmailCleaner._combine_patterns(
    EmailCleaner.DEFAULT_SIGNATURE_PATTERNS
)
