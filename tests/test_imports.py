"""Unit tests for validating top-level package imports and public API exports."""

from intelligent_email_service import (
    EmailProvider,
    EmailProviderError,
    EmailProviderManager,
    EmailRetrievalError,
    EmailRetrievalService,
    EmailServiceError,
    MicrosoftGraphProvider,
    MockGraphProvider,
    ProcessedThread,
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ThreadFormat,
    ThreadProcessor,
)
from synthetic_generator import NvidiaClient, SyntheticEmailGenerator


def test_package_imports():
    """Verify top-level submodules, exceptions, and provider exports."""
    assert EmailProvider is not None
    assert EmailProviderManager is not None
    assert MockGraphProvider is not None
    assert MicrosoftGraphProvider is not None
    assert EmailRetrievalService is not None
    assert ThreadProcessor is not None
    assert ProcessedThread is not None
    assert ThreadFormat is not None
    assert EmailServiceError is not None
    assert EmailProviderError is not None
    assert EmailRetrievalError is not None
    assert ProviderAuthenticationError is not None
    assert ProviderRateLimitError is not None
    assert ProviderNotFoundError is not None
    assert NvidiaClient is not None
    assert SyntheticEmailGenerator is not None

