import asyncio
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from ..email_connectors.base import EmailProvider
from ..utils import get_message_datetime
from .email_retrieval import EmailRetrievalService

logger = logging.getLogger(__name__)


class ThreadFormat(StrEnum):
    """Represents how the email thread was originally stored."""

    FULL_QUOTED = "full_quoted"
    MODIFIED = "modified"


@dataclass
class ProcessedThread:
    """
    Represents a complete, reconstructed email thread.

    Attributes:
        subject: Subject of the thread.
        conversation_id: Microsoft Graph conversation ID.
        format: Whether the original thread was full_quoted or modified.
        messages: Messages representing the complete thread.
    """

    subject: str
    conversation_id: str | None
    format: ThreadFormat
    reconstructed: bool
    messages: list[dict[str, Any]]


DEFAULT_MAX_CONCURRENCY: int = 10


class ThreadProcessor:
    """
    Determines whether a subject group contains a full quoted thread
    or a modified thread and reconstructs modified threads when needed.

    Workflow:
     Subject Group
            ↓
        Sort chronologically
            ↓
        Inspect latest message
            ↓
        full_quoted?
          /       \
        yes       no
         ↓         ↓
    Use latest   Get conversation_id
    message      ↓
                 Fetch full conversation
                 ↓
                 Sort chronologically
    """

    QUOTED_HEADER_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"(?:<p[^>]*>|<div[^>]*>)?\s*On\s+.+?\s+wrote:", re.IGNORECASE | re.DOTALL),
        re.compile(r"-{3,}\s*Original Message\s*-{3,}", re.IGNORECASE),
        re.compile(
            r"(?:From|De):\s*.*?(?:<br\s*/?>|<\/div>|<\/p>|\n)\s*(?:Sent|Date|Envoyé):",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(r"id=[\"']?divRplyFwdMsg[\"']?", re.IGNORECASE),
    ]

    def __init__(
        self,
        provider: EmailProvider,
        user_id: str,
        client_id: str | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,  # cap parallel network requests
    ):
        self.provider = provider
        self.user_id = user_id
        self.client_id = client_id
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def process_subject_group(
        self,
        messages: list[dict[str, Any]],
    ) -> ProcessedThread | None:
        """
        Process a group of messages belonging to the same subject.

        Workflow:
            1. Sort messages chronologically.
            2. Inspect the latest message.
            3. Determine whether the latest message contains quoted history.
            4. If full_quoted, use the latest message because it contains
               the complete quoted thread history.
            5. If modified, retrieve the complete conversation using
               conversation_id.
            6. Return the complete thread chronologically ordered.
        """

        if not messages:
            return None

        self._sort_chronologically(messages)

        latest_message = messages[-1]
        conv_id = latest_message.get("conversationId") or latest_message.get(
            "conversation_id"
        )

        if self._is_full_quoted(latest_message):
            logger.debug(
                "Subject '%s' resolved as FULL_QUOTED thread (conv_id: %s)",
                latest_message.get("subject"),
                conv_id,
            )
            return ProcessedThread(
                subject=latest_message.get("subject", ""),
                conversation_id=conv_id,
                format=ThreadFormat.FULL_QUOTED,
                messages=[latest_message],
                reconstructed=False,
            )

        logger.debug(
            "Subject '%s' resolved as MODIFIED thread; fetching conversation_id '%s'",
            latest_message.get("subject"),
            conv_id,
        )
        complete_messages = await self._reconstruct_conversation(
            conversation_id=conv_id,
            fallback_messages=messages,
        )

        return ProcessedThread(
            subject=latest_message.get("subject", ""),
            conversation_id=conv_id,
            format=ThreadFormat.MODIFIED,
            messages=complete_messages,
            reconstructed=True,
        )

    @classmethod
    def _is_full_quoted(
        cls,
        message: dict[str, Any],
    ) -> bool:
        """
        Determine whether the email contains quoted email history.
        """

        body = message.get("body", {})

        if not isinstance(body, dict):
            return False
        content = body.get("content", "")
        if not isinstance(content, str):
            return False
        return any(
            pattern.search(content) is not None for pattern in cls.QUOTED_HEADER_PATTERNS
        )

    async def _reconstruct_conversation(
        self, conversation_id: str | None, fallback_messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Retrieve and reconstruct a complete modified conversation.
        """

        if not conversation_id:
            # Cannot reconstruct the conversation without an ID.
            return fallback_messages
        async with self._semaphore:
            messages = await self.provider.get_emails_by_conversation_id(
                self.user_id,
                conversation_id,
            )

        if self.client_id:
            messages = [
                msg
                for msg in messages
                if EmailRetrievalService._message_matches_client(msg, self.client_id)
            ]

        self._sort_chronologically(messages)

        return messages or fallback_messages

    async def process_subject_groups(
        self,
        subject_groups: dict[str, list[dict[str, Any]]],
    ) -> list[ProcessedThread]:
        """Process multiple subject groups concurrently."""
        tasks = [
            self.process_subject_group(messages) for messages in subject_groups.values()
        ]
        results = await asyncio.gather(*tasks)
        return [res for res in results if res is not None]

    @staticmethod
    def _sort_chronologically(
        messages: list[dict[str, Any]],
    ) -> None:
        """
        Sort messages in-place from oldest to newest using Schwartzian transform.
        """
        decorated = [
            (get_message_datetime(msg, default_to_min=True), msg) for msg in messages
        ]
        decorated.sort(key=lambda item: item[0])
        messages[:] = [msg for _, msg in decorated]
