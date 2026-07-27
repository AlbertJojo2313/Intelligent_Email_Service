"""Email connectors module supporting multiple Graph/mock sources."""

from .base import EmailProvider
from .email_manager import EmailProviderManager
from .microsoft_graph import MicrosoftGraphProvider
from .mock_graph import MockGraphProvider

__all__ = [
    "EmailProvider",
    "EmailProviderManager",
    "MicrosoftGraphProvider",
    "MockGraphProvider",
]
