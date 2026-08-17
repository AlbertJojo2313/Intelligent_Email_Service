import os
from enum import StrEnum
from typing import Any

from intelligent_email_service.config import AzureADCredentials, MicrosoftGraphConfig

from .base import EmailProvider
from .microsoft_graph import MicrosoftGraphProvider
from .mock_graph import MockGraphProvider


class ProviderType(StrEnum):
    MOCK = "mock"
    MICROSOFT = "microsoft"


class EmailProviderManager:
    @staticmethod
    def create(
        provider_type: str | ProviderType = ProviderType.MOCK,
        app_env: str = "dev",
        base_url: str | None = None,
        credentials: AzureADCredentials | None = None,
        access_token: str | None = None,
        config: MicrosoftGraphConfig | None = None,
        **kwargs: Any,
    ) -> EmailProvider:
        """
        Factory method to instantiate an EmailProvider (Mock or Microsoft Graph).

        Args:
            provider_type: 'mock' or 'microsoft' (ProviderType enum or string).
            app_env: Environment string ('dev', 'test_prod', 'prod', 'production').
            base_url: Optional base URL override.
            credentials: Optional AzureADCredentials for client credentials grant.
            access_token: Optional pre-issued Bearer token.
            config: Optional MicrosoftGraphConfig dataclass settings.
            **kwargs: Additional keyword arguments passed to the provider constructor.
        """
        provider_type_str = str(provider_type).lower()

        if app_env in ("test_prod", "prod", "production") and provider_type == "mock":
            raise ValueError(
                "MockGraphProvider is disabled in 'test_prod' mode."
                "Set provider_type='microsoft' and configure Azure AD credentials."
            )
        match provider_type_str:
            case ProviderType.MOCK | "mock":
                mock_url = base_url or os.getenv("MOCK_SERVER_URL", "http://localhost:3000")
                return MockGraphProvider(
                    base_url=mock_url,
                    **kwargs,
                )
            case ProviderType.MICROSOFT | "microsoft":
                graph_url = base_url or os.getenv("GRAPH_API_BASE_URL", "https://graph.microsoft.com/v1.0")
                if credentials or access_token:
                    return MicrosoftGraphProvider(
                        credentials=credentials,
                        access_token=access_token,
                        base_url=graph_url,
                        config=config,
                        **kwargs,
                    )
                return MicrosoftGraphProvider.from_env(
                    base_url=graph_url,
                    config=config,
                    **kwargs,
                )
            case _:
                raise ValueError(f"Unsupported Email Provider: {provider_type}")
