import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import chain
from typing import Any

from intelligent_email_service.email_connectors.base import EmailProvider
from intelligent_email_service.exceptions import EmailProviderError, EmailRetrievalError

# Pre-compile regex at module level to avoid re-compiling per function invocation
RE_ALL_PREFIXES = re.compile(
    r"^(?:(?:\[[^\]]+\]\s*)|(?:re|fwd|fw|aw|sv|wg|tr|rv)(?:\[\d+\])?:\s*)+",
    re.IGNORECASE,
)
RE_BRACKETS = re.compile(r"^\[[^\]]+\]\s*", re.IGNORECASE)


class EmailRetrievalService:
    """
    Retrieve emails from an advisor's mailbox and organizes them by client and subject.

    Responsibilities:
        1. Retrieve mailbox messages
        2. Filter messages associated with a client
        3. Group the client's messages by normalized subject

    Thread reconstruction is handled by ThreadProcessor
    """

    def __init__(self, provider: EmailProvider):
        self.provider = provider

    async def get_client_emails(
        self,
        advisor_id: str,
        client_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve all emails involving a specific client with sanitized attachments."""

        try:
            messages = await self.provider.get_emails(
                user_id=advisor_id,
                start_date=start_date,
                end_date=end_date,
            )
        except EmailProviderError:
            raise
        except Exception as err:
            raise EmailRetrievalError(
                f"Failed to retrieve client emails for advisor '{advisor_id}': {err}"
            ) from err

        messages = messages or []

        return [
            self._sanitize_attachment_metadata(message)
            for message in messages
            if self._message_matches_client(message, client_id)
        ]

    async def get_client_email_groups(
        self,
        advisor_id: str,
        client_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Retrieve client emails and group them by normalized subject."""
        messages = await self.get_client_emails(
            advisor_id=advisor_id,
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
        )
        return self._group_by_subject(messages)

    @staticmethod
    def _parse_dt(dt_str: str | None) -> datetime:
        if not dt_str:
            return datetime.min.replace(tzinfo=UTC)
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except (ValueError, AttributeError):
            return datetime.min.replace(tzinfo=UTC)

    @staticmethod
    def _message_matches_client(message: dict[str, Any], client_id: str) -> bool:
        client_id = client_id.lower()

        matches = EmailRetrievalService._email_address_matches
        recipients = chain(
            [message.get("from")],
            message.get("toRecipients") or [],
            message.get("ccRecipients") or [],
        )
        return any(matches(recipient, client_id) for recipient in recipients)

    @staticmethod
    def _email_address_matches(
        participant: dict[str, Any] | None, client_id: str
    ) -> bool:
        if not isinstance(participant, dict):
            return False
        email_address = participant.get("emailAddress")
        if not isinstance(email_address, dict):
            return False
        address = email_address.get("address") or ""
        return address.lower() == client_id

    @staticmethod
    def _group_by_subject(
        messages: Iterable[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for message in messages:
            subject = message.get("subject") or ""
            normalized_subject = EmailRetrievalService._normalize_subject(subject)
            groups[normalized_subject].append(message)

        parse_dt = EmailRetrievalService._parse_dt
        for thread_messages in groups.values():
            decorated = [
                (
                    parse_dt(msg.get("receivedDateTime") or msg.get("recievedDateTime")),
                    msg,
                )
                for msg in thread_messages
            ]
            decorated.sort(key=lambda item: item[0])
            thread_messages[:] = [msg for _, msg in decorated]

        return dict(groups)

    @staticmethod
    def _normalize_subject(subject: str | None) -> str:
        if not subject:
            return ""
        return RE_ALL_PREFIXES.sub("", subject.strip()).strip().lower()

    @staticmethod
    def _sanitize_attachment_metadata(message: dict[str, Any]) -> dict[str, Any]:
        """Ensures message attachment objects only contain clean metadata."""
        has_attachments = message.get("hasAttachments")
        raw_attach = message.get("attachments")

        # Fast path: Return immediately if there are no attachments
        if not has_attachments and not raw_attach:
            return message

        clean_msg = dict(message)
        clean_attach: list[dict[str, Any]] = []
        if isinstance(raw_attach, list):
            clean_attach = [
                {
                    "id": att.get("id"),
                    "name": att.get("name") or att.get("fileName") or "attachment",
                    "contentType": att.get("contentType")
                    or att.get("content_type")
                    or "application/octet-stream",
                    "size": att.get("size") or 0,
                    "isInline": att.get("isInline", False),
                }
                for att in raw_attach
                if isinstance(att, dict)
            ]
        clean_msg["attachments"] = clean_attach
        return clean_msg
