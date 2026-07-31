"""Shared utility functions for Intelligent Email Service."""

import re
from datetime import UTC, datetime
from typing import Any

# Regex to strip email subject prefixes including re:, fwd:, [ticket], etc.
RE_ALL_PREFIXES = re.compile(
    r"^(?:(?:\[[^\]]+\]\s*)|(?:re|fwd|fw|aw|sv|wg|tr|rv)(?:\[\d+\])?:\s*)+",
    re.IGNORECASE,
)


def parse_iso_datetime(
    dt_str: str | None, default_to_min: bool = False
) -> datetime | None:
    """Safely parse ISO date strings into timezone-aware UTC datetime objects."""
    if not dt_str or not isinstance(dt_str, str):
        return datetime.min.replace(tzinfo=UTC) if default_to_min else None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, AttributeError, TypeError):
        return datetime.min.replace(tzinfo=UTC) if default_to_min else None


def get_message_datetime(
    message: dict[str, Any], default_to_min: bool = True
) -> datetime | None:
    """Extract receivedDateTime (handling typos) from message and parse into UTC datetime."""
    dt_str = message.get("receivedDateTime") or message.get("recievedDateTime")
    return parse_iso_datetime(dt_str, default_to_min=default_to_min)


def extract_message_body(message: dict[str, Any]) -> str:
    """Extract raw body text from message object."""
    cleaned = message.get("cleaned_body")
    if isinstance(cleaned, str):
        return cleaned
    body_obj = message.get("body")
    if isinstance(body_obj, dict):
        return str(body_obj.get("content") or "")
    if isinstance(body_obj, str):
        return body_obj
    return ""


def sanitize_attachments(
    raw_attachments: list[dict[str, Any]] | None, include_is_inline: bool = False
) -> list[dict[str, Any]]:
    """Sanitize raw attachment list into standard clean metadata dicts."""
    if not isinstance(raw_attachments, list):
        return []
    clean_attach: list[dict[str, Any]] = []
    for att in raw_attachments:
        if isinstance(att, dict):
            item = {
                "id": att.get("id"),
                "name": att.get("name") or att.get("fileName") or "attachment",
                "contentType": att.get("contentType")
                or att.get("content_type")
                or "application/octet-stream",
                "size": att.get("size") or 0,
            }
            if include_is_inline:
                item["isInline"] = att.get("isInline", False)
            clean_attach.append(item)
    return clean_attach


def normalize_subject(subject: str | None, lower: bool = False) -> str:
    """Strip email subject prefixes (re:, fwd:, [ticket], etc.) and normalize text."""
    if not subject:
        return ""
    cleaned = RE_ALL_PREFIXES.sub("", subject.strip()).strip()
    return cleaned.lower() if lower else cleaned
