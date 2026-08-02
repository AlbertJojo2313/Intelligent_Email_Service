"""Intelligent Email Service.

A package for email retrieval, ingestion, and preprocessing/compression
designed for LLM context optimization.
"""

from .config import (
    CleanerConfig,
    CompressorConfig,
    EmailQueryFilter,
    PipelineConfig,
)
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
from .logging_config import setup_logging
from .pipeline import process_client_emails
from .retrieval import (
    EmailRetrievalService,
    ProcessedThread,
    ThreadFormat,
    ThreadProcessor,
)

__version__ = "0.1.0"

__all__ = [
    "CleanerConfig",
    "CompressorConfig",
    "EmailProvider",
    "EmailProviderError",
    "EmailProviderManager",
    "EmailQueryFilter",
    "EmailRetrievalError",
    "EmailRetrievalService",
    "EmailServiceError",
    "MicrosoftGraphProvider",
    "MockGraphProvider",
    "PipelineConfig",
    "ProcessedThread",
    "ProviderAuthenticationError",
    "ProviderNotFoundError",
    "ProviderRateLimitError",
    "ThreadFormat",
    "ThreadProcessor",
    "process_client_emails",
    "setup_logging",
]
