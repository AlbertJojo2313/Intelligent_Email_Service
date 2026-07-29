import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar

from ..email_connectors.base import EmailProvider
from .email_retrieval import EmailRetrievalService


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
    messages: list[dict[str, Any]]


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

    QUOTED_HEADER_PATTERNS: ClassVar = [
        re.compile(r"(?:<p>|<div>)?\s*On\s+.+?\s+wrote:", re.IGNORECASE | re.DOTALL),
        re.compile(r"-----Original Message-----", re.IGNORECASE),
        re.compile(r"(?:From|De):\s*.+?\n\s*(?:Sent|Date|Envoyé):", re.IGNORECASE),
    ]

    def __init__(
        self,
        provider: EmailProvider,
        user_id: str,
        client_id: str | None = None,
        max_concurrency: int = 10,  # cap parallel network requests
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
            return ProcessedThread(
                subject=latest_message.get("subject", ""),
                conversation_id=conv_id,
                format=ThreadFormat.FULL_QUOTED,
                messages=[latest_message],
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
            self.process_subject_group(messages)
            for messages in subject_groups.values()
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

        def _get_dt(msg: dict[str, Any]) -> datetime:
            dt_str = msg.get("receivedDateTime")
            if not dt_str:
                return datetime.min.replace(tzinfo=UTC)
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                return datetime.min.replace(tzinfo=UTC)

        decorated = [(_get_dt(msg), msg) for msg in messages]
        decorated.sort(key=lambda item: item[0])
        messages[:] = [msg for _, msg in decorated]

