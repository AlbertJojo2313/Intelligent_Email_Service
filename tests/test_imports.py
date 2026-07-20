import pytest

def test_imports():
    """Verify that all main submodules and classes can be imported correctly."""
    from intelligent_email_service.email_connectors import (
        EmailProvider,
        EmailProviderManager,
        MockGraphProvider,
        MicrosoftGraphProvider,
    )
    
    # Simple assertion to verify classes are loaded
    assert EmailProvider is not None
    assert EmailProviderManager is not None
    assert MockGraphProvider is not None
    assert MicrosoftGraphProvider is not None
