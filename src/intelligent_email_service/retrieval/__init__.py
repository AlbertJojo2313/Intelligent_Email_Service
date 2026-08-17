"""Retrieval package for filtering and grouping emails."""

from .attachment_processor import (
    fetch_attachment_text,
    is_text_readable_attachment,
    process_node_attachments,
)
from .email_node import EmailNode
from .email_retrieval import EmailRetrievalService
from .reconstructors import (
    ConversationReconstructor,
    GraphConversationReconstructor,
    LinearConversationReconstructor,
)
from .thread_processor import ProcessedThread, ThreadFormat, ThreadProcessor

__all__ = [
    "ConversationReconstructor",
    "EmailNode",
    "EmailRetrievalService",
    "GraphConversationReconstructor",
    "LinearConversationReconstructor",
    "ProcessedThread",
    "ThreadFormat",
    "ThreadProcessor",
    "fetch_attachment_text",
    "is_text_readable_attachment",
    "process_node_attachments",
]
