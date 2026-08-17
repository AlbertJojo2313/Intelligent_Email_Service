"""Unit tests for validating top-level package imports and public API exports."""

from intelligent_email_service import (
    CleanerConfig,
    CompressorConfig,
    EmailProvider,
    EmailProviderError,
    EmailProviderManager,
    EmailQueryFilter,
    EmailRetrievalError,
    EmailRetrievalService,
    EmailServiceError,
    MicrosoftGraphProvider,
    MockGraphProvider,
    PipelineConfig,
    ProcessedThread,
    ProviderAuthenticationError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ThreadFormat,
    ThreadProcessor,
    process_client_emails,
)
from synthetic_generator import NvidiaClient, SyntheticEmailGenerator


def test_package_imports():
    """Verify top-level submodules, exceptions, and provider exports."""
    assert process_client_emails is not None
    assert CleanerConfig is not None
    assert CompressorConfig is not None
    assert EmailQueryFilter is not None
    assert PipelineConfig is not None
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
