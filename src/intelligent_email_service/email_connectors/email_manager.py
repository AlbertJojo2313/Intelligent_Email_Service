from enum import StrEnum

from .microsoft_graph import MicrosoftGraphProvider
from .mock_graph import MockGraphProvider


class ProviderType(StrEnum):
    MOCK = "mock"
    MICROSOFT = "microsoft"


class EmailProviderManager:
    @staticmethod
    def create(
        provider_type: str = ProviderType.MOCK,
        base_url: str | None = None,
    ):
        match provider_type:
            case ProviderType.MOCK:
                return MockGraphProvider(base_url=base_url or "http://localhost:3000")
            case ProviderType.MICROSOFT:
                return MicrosoftGraphProvider(base_url=base_url or "https://graph.microsoft.com/v1.0")
            case _:
                raise ValueError(f"Unsupported Email Provider: {provider_type}")

