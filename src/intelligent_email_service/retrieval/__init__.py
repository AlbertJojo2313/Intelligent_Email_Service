"""Retrieval package for filtering and grouping emails."""

from .email_retrieval import EmailRetrievalService
from .thread_processor import ProcessedThread, ThreadFormat, ThreadProcessor

__all__ = [
    "EmailRetrievalService",
    "ProcessedThread",
    "ThreadFormat",
    "ThreadProcessor",
]

