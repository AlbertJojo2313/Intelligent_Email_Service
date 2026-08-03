"""Retrieval package for filtering and grouping emails."""

from .email_node import EmailNode
from .email_retrieval import EmailRetrievalService
from .reconstructors import (
    ConversationReconstructor,
    GraphConversationReconstructor,
    LinearConversationReconstructor,
)
from .thread_processor import ProcessedThread, ThreadFormat, ThreadProcessor

__all__ = [
    "EmailNode",
    "EmailRetrievalService",
    "ProcessedThread",
    "ThreadFormat",
    "ThreadProcessor",
    "ConversationReconstructor",
    "GraphConversationReconstructor",
    "LinearConversationReconstructor",
]

