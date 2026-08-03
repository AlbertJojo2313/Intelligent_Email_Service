"""EmailNode domain object replacing loose dictionaries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EmailNode:
    """Strongly-typed representation of an email message in a thread graph."""

    id: str
    conversation_id: str | None = None
    message_id: str | None = None          # RFC 822 Message-ID header
    in_reply_to: str | None = None         # Parent Message-ID header
    subject: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    received_at: datetime | None = None
    body_content: str = ""
    content_type: str = "text"
    cleaned_body: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailNode":
        """Factory method constructing an EmailNode from Graph API / Mock dict payload."""
        msg_id = data.get("id") or ""
        conv_id = data.get("conversationId") or data.get("conversation_id")
        headers = data.get("internetMessageHeaders") or []

        internet_msg_id = data.get("internetMessageId")
        in_reply_to = None

        if isinstance(headers, list):
            for h in headers:
                if isinstance(h, dict):
                    name = str(h.get("name") or "").lower()
                    if name == "message-id" and not internet_msg_id:
                        internet_msg_id = h.get("value")
                    elif name == "in-reply-to":
                        in_reply_to = h.get("value")

        sender_obj = data.get("from") or {}
        sender = ""
        if isinstance(sender_obj, dict):
            addr_info = sender_obj.get("emailAddress") or {}
            if isinstance(addr_info, dict):
                sender = addr_info.get("address") or addr_info.get("name") or ""

        recipients = []
        for r in (data.get("toRecipients") or []):
            if isinstance(r, dict):
                addr_info = r.get("emailAddress") or {}
                if isinstance(addr_info, dict):
                    addr = addr_info.get("address")
                    if addr:
                        recipients.append(addr)

        body_obj = data.get("body") or {}
        if isinstance(body_obj, dict):
            content = body_obj.get("content") or ""
            ctype = body_obj.get("contentType") or body_obj.get("content_type") or "text"
        elif isinstance(body_obj, str):
            content = body_obj
            ctype = "text"
        else:
            content = ""
            ctype = "text"

        raw_attach = data.get("attachments") or []
        attachments = []
        if isinstance(raw_attach, list):
            attachments = [
                {
                    "id": a.get("id"),
                    "name": a.get("name") or a.get("fileName") or "attachment",
                    "contentType": a.get("contentType") or a.get("content_type") or "application/octet-stream",
                    "size": a.get("size") or 0,
                }
                for a in raw_attach if isinstance(a, dict)
            ]

        dt_str = data.get("receivedDateTime") or data.get("recievedDateTime")
        received_at = None
        if dt_str:
            try:
                received_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                received_at = None

        return cls(
            id=msg_id,
            conversation_id=conv_id,
            message_id=internet_msg_id or msg_id,
            in_reply_to=in_reply_to,
            subject=data.get("subject") or "",
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            body_content=content,
            content_type=ctype,
            attachments=attachments,
        )
