"""Configuration objects for Intelligent Email Service."""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AppEnvironment(StrEnum):
    DEV = "dev"
    TEST_PROD = "test_prod"
    PROD = "prod"
    PRODUCTION = "production"


@dataclass
class AzureADCredentials:
    """Azure AD credentials for Microsoft Graph API access."""

    tenant_id: str
    client_id: str
    client_secret: str

    @classmethod
    def from_env(cls) -> "AzureADCredentials":
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        if not all([tenant_id, client_id, client_secret]):
            raise ValueError(
                "Missing Azure AD credentials in environment variables. "
                "Please set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET."
            )
        return cls(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)


@dataclass
class MicrosoftGraphConfig:
    """Configuration settings for Microsoft Graph API"""

    base_url: str = field(
        default_factory=lambda: os.getenv(
            "GRAPH_API_BASE_URL", "https://graph.microsoft.com/v1.0"
        )
    )
    page_size: int = field(
        default_factory=lambda: int(os.getenv("GRAPH_PAGE_SIZE", "50"))
    )
    select_fields: list[str] = field(
        default_factory=lambda: [
            "id",
            "conversationId",
            "internetMessageId",
            "subject",
            "from",
            "toRecipients",
            "ccRecipients",
            "receivedDateTime",
            "body",
            "hasAttachments",
            "internetMessageHeaders",
        ]
    )

    def get_select_param(self) -> str:
        return ",".join(self.select_fields)


@dataclass
class CleanerConfig:
    """Grouped settings for HTML cleaning and signature removal."""

    strip_signatures: bool = field(
        default_factory=lambda: os.getenv("CLEANER_STRIP_SIGNATURES", "true").lower()
        == "true"
    )
    max_blank_lines: int = field(
        default_factory=lambda: int(os.getenv("CLEANER_MAX_BLANK_LINES", "1"))
    )
    preserve_links: bool = field(
        default_factory=lambda: os.getenv("CLEANER_PRESERVE_LINKS", "false").lower()
        == "true"
    )
    custom_signature_patterns: list[re.Pattern[str]] | None = None


@dataclass
class CompressorConfig:
    """Grouped settings for context window compression and LLMLingua."""

    recent_full_count: int = field(
        default_factory=lambda: int(os.getenv("COMPRESSOR_RECENT_FULL_COUNT", "2"))
    )
    max_full_body_chars: int = field(
        default_factory=lambda: int(os.getenv("COMPRESSOR_MAX_FULL_BODY_CHARS", "300"))
    )
    use_llmlingua: bool = field(
        default_factory=lambda: os.getenv("USE_LLMLINGUA", "true").lower() == "true"
    )
    llmlingua_rate: float = field(
        default_factory=lambda: float(os.getenv("LLMLINGUA_RATE", "0.75"))
    )
    llmlingua_model: str = field(
        default_factory=lambda: os.getenv(
            "LLMLINGUA_MODEL",
            "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
        )
    )
    llmlingua_device: str = field(
        default_factory=lambda: os.getenv("LLMLINGUA_DEVICE", "cpu")
    )
    activate_compressor_message_length: int = field(
        default_factory=lambda: int(os.getenv("COMPRESSOR_ACTIVATION_LENGTH", "100"))
    )
    force_tokens: list[str] = field(
        default_factory=lambda: ["\n", ".", "?", "[", "]", ":", "!"]
    )
    token_budget_ratio: float = field(
        default_factory=lambda: float(os.getenv("COMPRESSOR_TOKEN_BUDGET_RATIO", "1.8"))
    )
    keep_first_sentence: bool = field(
        default_factory=lambda: os.getenv("COMPRESSOR_KEEP_FIRST_SENTENCE", "true").lower()
        == "true"
    )


@dataclass
class EmailQueryFilter:
    """Query parameters for email retrieval filtering."""

    advisor_id: str
    client_id: str
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass
class PipelineConfig:
    """Unified configuration object grouping all service processing settings."""

    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "dev").lower())
    cleaner: CleanerConfig = field(default_factory=CleanerConfig)
    compressor: CompressorConfig = field(default_factory=CompressorConfig)
    graph: MicrosoftGraphConfig = field(default_factory=MicrosoftGraphConfig)
    max_concurrency: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENCY", "10"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
