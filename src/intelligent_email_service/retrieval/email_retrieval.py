import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import chain
from typing import Any

from intelligent_email_service.email_connectors.base import EmailProvider
from intelligent_email_service.exceptions import EmailProviderError, EmailRetrievalError
from intelligent_email_service.utils import normalize_subject, sanitize_attachments

from .email_node import EmailNode

logger = logging.getLogger(__name__)


class EmailRetrievalService:
    """Retrieve emails from an advisor's mailbox and organize them by client and subject."""

    def __init__(self, provider: EmailProvider):
        self.provider = provider

    async def get_client_emails(
        self,
        advisor_id: str,
        client_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[EmailNode]:
        """Retrieve all emails involving a specific client as EmailNode objects."""
        try:
            logger.debug("Fetching emails for advisor '%s'...", advisor_id)
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
        filtered = [
            EmailNode.from_dict(self._sanitize_message(msg))
            for msg in messages
            if self._message_matches_client(msg, client_id)
        ]
        logger.info(
            "Retrieved %d total message(s) from provider; %d match client '%s'",
            len(messages),
            len(filtered),
            client_id,
        )
        return filtered

    async def get_client_email_groups(
        self,
        advisor_id: str,
        client_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, list[EmailNode]]:
        """Retrieve client emails and group them by normalized subject."""
        nodes = await self.get_client_emails(
            advisor_id=advisor_id,
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
        )
        return self._group_by_subject(nodes)

    @staticmethod
    def _message_matches_client(message: dict[str, Any], client_id: str) -> bool:
        client_id = client_id.lower()
        recipients = chain(
            [message.get("from")],
            message.get("toRecipients") or [],
            message.get("ccRecipients") or [],
        )
        return any(
            EmailRetrievalService._email_address_matches(r, client_id) for r in recipients
        )

    @staticmethod
    def _email_address_matches(participant: Any, client_id: str) -> bool:
        if isinstance(participant, str):
            return participant.lower() == client_id
        if not isinstance(participant, dict):
            return False
        email_address = participant.get("emailAddress")
        if isinstance(email_address, str):
            return email_address.lower() == client_id
        if isinstance(email_address, dict):
            addr = email_address.get("address") or email_address.get("name") or ""
            return addr.lower() == client_id
        addr = participant.get("address") or participant.get("name") or ""
        return addr.lower() == client_id if addr else False

    @staticmethod
    def _group_by_subject(nodes: Iterable[EmailNode]) -> dict[str, list[EmailNode]]:
        groups: dict[str, list[EmailNode]] = defaultdict(list)

        for node in nodes:
            norm_subj = normalize_subject(node.subject, lower=True)
            groups[norm_subj].append(node)

        min_utc = datetime.min.replace(tzinfo=UTC)
        for thread_nodes in groups.values():
            thread_nodes.sort(key=lambda n: n.received_at or min_utc)

        return dict(groups)

    @staticmethod
    def _sanitize_message(message: dict[str, Any]) -> dict[str, Any]:
        clean_msg = dict(message)
        clean_msg["attachments"] = sanitize_attachments(
            message.get("attachments"), include_is_inline=True
        )
        return clean_msg
