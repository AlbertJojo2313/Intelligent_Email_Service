"""EmailNode domain object replacing loose dictionaries."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from intelligent_email_service.utils import parse_iso_datetime


@dataclass
class EmailNode:
    """Strongly-typed representation of an email message in a thread graph."""

    id: str
    conversation_id: str | None = None
    message_id: str | None = None  # RFC 822 Message-ID header
    in_reply_to: str | None = None  # Parent Message-ID header
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

        internet_msg_id = data.get("internetMessageId")
        hdr_msg_id, in_reply_to = cls._extract_headers(data.get("internetMessageHeaders"))
        final_msg_id = internet_msg_id or hdr_msg_id or msg_id

        sender = cls._extract_sender(data.get("from"))
        recipients = cls._extract_recipients(data.get("toRecipients"))
        content, ctype = cls._extract_body(data.get("body"))
        attachments = cls._extract_attachments(data.get("attachments"))

        dt_str = data.get("receivedDateTime") or data.get("recievedDateTime")
        received_at = parse_iso_datetime(dt_str)

        return cls(
            id=msg_id,
            conversation_id=conv_id,
            message_id=final_msg_id,
            in_reply_to=in_reply_to,
            subject=data.get("subject") or "",
            sender=sender,
            recipients=recipients,
            received_at=received_at,
            body_content=content,
            content_type=ctype,
            attachments=attachments,
        )

    @staticmethod
    def _extract_headers(headers: Any) -> tuple[str | None, str | None]:
        internet_msg_id = None
        in_reply_to = None
        if isinstance(headers, list):
            for h in headers:
                if isinstance(h, dict):
                    name = str(h.get("name") or "").lower()
                    if name == "message-id" and not internet_msg_id:
                        internet_msg_id = h.get("value")
                    elif name == "in-reply-to":
                        in_reply_to = h.get("value")
        return internet_msg_id, in_reply_to

    @staticmethod
    def _extract_sender(sender_obj: Any) -> str:
        if isinstance(sender_obj, str):
            return sender_obj
        if isinstance(sender_obj, dict):
            addr_info = sender_obj.get("emailAddress") or {}
            if isinstance(addr_info, str):
                return addr_info
            if isinstance(addr_info, dict):
                return addr_info.get("address") or addr_info.get("name") or ""
            return sender_obj.get("address") or sender_obj.get("name") or ""
        return ""

    @staticmethod
    def _extract_recipients(to_recipients: Any) -> list[str]:
        recipients = []
        for r in to_recipients or []:
            if isinstance(r, str):
                recipients.append(r)
            elif isinstance(r, dict):
                addr_info = r.get("emailAddress") or {}
                if isinstance(addr_info, str):
                    recipients.append(addr_info)
                elif isinstance(addr_info, dict):
                    addr = addr_info.get("address") or addr_info.get("name")
                    if addr:
                        recipients.append(addr)
                else:
                    addr = r.get("address") or r.get("name")
                    if addr:
                        recipients.append(addr)
        return recipients

    @staticmethod
    def _extract_body(body_obj: Any) -> tuple[str, str]:
        if isinstance(body_obj, dict):
            content = body_obj.get("content") or ""
            ctype = body_obj.get("contentType") or body_obj.get("content_type") or "text"
            return content, ctype
        if isinstance(body_obj, str):
            return body_obj, "text"
        return "", "text"

    @staticmethod
    def _extract_attachments(raw_attach: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_attach, list):
            return []
        return [
            {
                "id": a.get("id"),
                "name": a.get("name") or a.get("fileName") or "attachment",
                "contentType": (
                    a.get("contentType")
                    or a.get("content_type")
                    or "application/octet-stream"
                ),
                "size": a.get("size") or 0,
            }
            for a in raw_attach
            if isinstance(a, dict)
        ]
