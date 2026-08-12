import logging
from pathlib import Path

from intelligent_email_service.email_connectors.base import EmailProvider

from .email_node import EmailNode

logger = logging.getLogger(__name__)

# Content types and extensions that can be safely decoded as text
TEXT_CONTENT_TYPES: set[str] = {
    "text/plain",
    "text/csv",
    "text/tab-separated-values",
    "text/html",
    "text/markdown",
    "application/json",
    "application/x-yaml",
    "application/xml",
    "text/xml",
}

TEXT_EXTENSIONS: set[str] = {
    ".txt",
    ".csv",
    ".tsv",
    ".json",
    ".log",
    ".md",
    ".yaml",
    ".yml",
    ".xml",
}


def is_text_readable_attachment(attachment: dict) -> bool:
    """Determine whether an attachment contains plain text that can be decoded."""
    content_type = str(attachment.get("contentType") or "").lower()
    name = str(attachment.get("name") or "").lower()

    if any(ct in content_type for ct in TEXT_CONTENT_TYPES):
        return True

    ext = Path(name).suffix
    return ext in TEXT_EXTENSIONS


async def fetch_attachment_text(
    provider: EmailProvider, user_id: str, message_id: str, attachment: dict
) -> str | None:
    """Fetch raw binary content of a text-readable attachment and decode to string."""
    if not is_text_readable_attachment(attachment):
        return None

    if not hasattr(provider, "get_attachment_bytes"):
        logger.debug(
            "Provider '%s' does not implement `get_attachment_bytes`.",
            type(provider).__name__,
        )
        return None

    attachment_id = attachment.get("id")
    try:
        raw_bytes = await provider.get_attachment_bytes(  # type: ignore[attr-defined]
            user_id=user_id, message_id=message_id, attachment_id=attachment_id
        )
        if not raw_bytes:
            return None

        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin1", errors="replace")
    except Exception as exc:
        logger.warning(
            "Failed to fetch attachment '%s' (%s) for message '%s': %s",
            attachment.get("name"),
            attachment_id,
            message_id,
            exc,
        )
        return None


async def process_node_attachments(
    provider: EmailProvider, user_id: str, node: EmailNode
) -> list[str]:
    """
    Fetch readable attachment contents for an EmailNode.

    Stores uncompressed attachment text inside each attachment dictionary in `node.attachments`
    without modifying `node.body_content` or `node.cleaned_body`, leaving message body compression
    isolated from attachment processing.
    """
    if not node.attachments or not node.id:
        return []

    extracted_summaries: list[str] = []

    for attach in node.attachments:
        name = attach.get("name") or "attachment"
        text_content = await fetch_attachment_text(
            provider=provider, user_id=user_id, message_id=node.id, attachment=attach
        )
        if text_content is not None:
            attach["content"] = text_content
            summary = f"[Attachment: {name} (Uncompressed text content preserved)]"
        else:
            summary = f"[Attachment: {name} ({attach.get('contentType', 'unknown')})]"
        extracted_summaries.append(summary)

    return extracted_summaries
