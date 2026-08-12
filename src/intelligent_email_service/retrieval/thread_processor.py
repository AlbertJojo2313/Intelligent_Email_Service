import asyncio
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from intelligent_email_service.email_connectors.base import EmailProvider

from .email_node import EmailNode
from .email_retrieval import EmailRetrievalService
from .reconstructors import ConversationReconstructor, GraphConversationReconstructor

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
        messages: EmailNode objects representing the complete thread.
    """

    subject: str
    conversation_id: str | None
    format: ThreadFormat
    reconstructed: bool
    messages: list[EmailNode]


DEFAULT_MAX_CONCURRENCY: int = 10


class ThreadProcessor:
    """
    Determines whether a subject group contains a full quoted thread
    or a modified thread and reconstructs modified threads when needed.
    """

    QUOTED_HEADER_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(
            r"(?:<p[^>]*>|<div[^>]*>)?\s*On\s+.+?\s+wrote:", re.IGNORECASE | re.DOTALL
        ),
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
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        reconstructor: ConversationReconstructor | None = None,
    ):
        self.provider = provider
        self.user_id = user_id
        self.client_id = client_id
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self.reconstructor = reconstructor or GraphConversationReconstructor()

    async def process_subject_group(
        self,
        messages: list[dict[str, Any] | EmailNode],
    ) -> ProcessedThread | None:
        """Process a group of messages belonging to the same subject."""

        if not messages:
            return None

        nodes = [
            m if isinstance(m, EmailNode) else EmailNode.from_dict(m) for m in messages
        ]
        nodes = self.reconstructor.reconstruct(nodes)

        latest_node = nodes[-1]
        conv_id = latest_node.conversation_id

        if self._is_full_quoted(latest_node):
            logger.debug(
                "Subject '%s' resolved as FULL_QUOTED thread (conv_id: %s)",
                latest_node.subject,
                conv_id,
            )
            return ProcessedThread(
                subject=latest_node.subject,
                conversation_id=conv_id,
                format=ThreadFormat.FULL_QUOTED,
                messages=[latest_node],
                reconstructed=False,
            )

        logger.debug(
            "Subject '%s' resolved as MODIFIED thread; fetching conversation_id '%s'",
            latest_node.subject,
            conv_id,
        )
        complete_nodes = await self._reconstruct_conversation(
            conversation_id=conv_id,
            fallback_nodes=nodes,
        )

        return ProcessedThread(
            subject=latest_node.subject,
            conversation_id=conv_id,
            format=ThreadFormat.MODIFIED,
            messages=complete_nodes,
            reconstructed=True,
        )

    @classmethod
    def _is_full_quoted(
        cls,
        node: EmailNode | dict[str, Any],
    ) -> bool:
        """Determine whether the email contains quoted email history."""
        if isinstance(node, dict):
            body = node.get("body", {})
            if isinstance(body, dict):
                content = body.get("content", "")
            elif isinstance(body, str):
                content = body
            else:
                content = ""
        elif hasattr(node, "body_content"):
            content = getattr(node, "body_content", "") or ""
        else:
            content = ""

        if not content or not isinstance(content, str):
            return False
        return any(
            pattern.search(content) is not None for pattern in cls.QUOTED_HEADER_PATTERNS
        )

    async def _reconstruct_conversation(
        self, conversation_id: str | None, fallback_nodes: list[EmailNode]
    ) -> list[EmailNode]:
        """Retrieve and reconstruct a complete modified conversation."""

        if not conversation_id:
            return fallback_nodes

        async with self._semaphore:
            raw_messages = await self.provider.get_emails_by_conversation_id(
                self.user_id,
                conversation_id,
            )

        if self.client_id:
            raw_messages = [
                msg
                for msg in raw_messages
                if EmailRetrievalService._message_matches_client(msg, self.client_id)
            ]

        nodes = [
            m
            if isinstance(m, EmailNode)
            else EmailNode.from_dict(EmailRetrievalService._sanitize_message(m))
            for m in raw_messages
        ]
        reconstructed = self.reconstructor.reconstruct(nodes) if nodes else fallback_nodes
        return reconstructed or fallback_nodes

    async def process_subject_groups(
        self,
        subject_groups: dict[str, list[dict[str, Any]]],
    ) -> list[ProcessedThread]:
        """Process multiple subject groups concurrently."""
        tasks = [
            self.process_subject_group(messages) for messages in subject_groups.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed: list[ProcessedThread] = []
        for res in results:
            if isinstance(res, Exception):
                logger.error("Failed to process subject group: %s", res)
            elif res is not None:
                processed.append(res)
        return processed
