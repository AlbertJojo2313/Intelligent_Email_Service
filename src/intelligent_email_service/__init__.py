"""Intelligent Email Service.

A package for email retrieval, ingestion, and preprocessing/compression
designed for LLM context optimization.
"""

from .email_connectors import (
    EmailProvider,
    EmailProviderManager,
    MicrosoftGraphProvider,
    MockGraphProvider,
)
from .exceptions import (
    EmailProviderError,
    EmailRetrievalError,
    EmailServiceError,
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
)
from .retrieval import (
    EmailRetrievalService,
    ProcessedThread,
    ThreadFormat,
    ThreadProcessor,
)

__version__ = "0.1.0"

__all__ = [
    "EmailProvider",
    "EmailProviderError",
    "EmailProviderManager",
    "EmailRetrievalError",
    "EmailRetrievalService",
    "EmailServiceError",
    "MicrosoftGraphProvider",
    "MockGraphProvider",
    "ProcessedThread",
    "ProviderAuthenticationError",
    "ProviderNotFoundError",
    "ProviderRateLimitError",
    "ThreadFormat",
    "ThreadProcessor",
]
