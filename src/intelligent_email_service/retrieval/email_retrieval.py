import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from itertools import chain
from typing import Any

from intelligent_email_service.email_connectors.base import EmailProvider
from intelligent_email_service.exceptions import EmailProviderError, EmailRetrievalError

# Pre-compile regex at module level to avoid re-compiling per function invocation
RE_SUBJECT_PREFIX = re.compile(
    r"^(?:\[[^\]]+\]\s*)*(?:re|fwd|fw|aw|sv|wg|tr|rv)(?:\[\d+\])?:\s*", re.IGNORECASE
)
RE_BRACKETS = re.compile(r"^\[[^\]]+\]\s*", re.IGNORECASE)


class EmailRetrievalService:
    """
    Retrieve emails from an advisor's mailbox and organizes them by client and subject

    Responsibilites:
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
        """Retrieve all emails involving a specific client"""

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

        return [
            message
            for message in messages
            if self._message_matches_client(message, client_id)
        ]

    async def get_client_email_groups(
        self,
        advisor_id: str,
        client_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ):
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
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return datetime.min.replace(tzinfo=timezone.utc)

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

        for thread_messages in groups.values():
            thread_messages.sort(
                key=lambda msg: EmailRetrievalService._parse_dt(
                    msg.get("receivedDateTime") or msg.get("recievedDateTime")
                )
            )

        return dict(groups)

    @staticmethod
    def _normalize_subject(subject: str | None) -> str:
        if not subject:
            return ""
        cleaned = subject.strip()
        while True:
            stripped = RE_SUBJECT_PREFIX.sub("", cleaned).strip()
            stripped = RE_BRACKETS.sub("", stripped).strip()
            if stripped == cleaned:
                break
            cleaned = stripped
        return cleaned.lower()
