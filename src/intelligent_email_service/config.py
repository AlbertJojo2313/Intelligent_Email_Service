"""Configuration objects for Intelligent Email Service."""

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CleanerConfig:
    """Grouped settings for HTML cleaning and signature removal."""

    strip_signatures: bool = True
    max_blank_lines: int = 1
    preserve_links: bool = False
    custom_signature_patterns: list[re.Pattern[str]] | None = None


@dataclass
class CompressorConfig:
    """Grouped settings for context window compression and LLMLingua."""

    recent_full_count: int = 2
    max_full_body_chars: int = 300
    use_llmlingua: bool = True
    llmlingua_rate: float = 0.5
    llmlingua_model: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
    llmlingua_device: str = "cpu"
    activate_compressor_message_length: int = 100


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

    cleaner: CleanerConfig = field(default_factory=CleanerConfig)
    compressor: CompressorConfig = field(default_factory=CompressorConfig)
    max_concurrency: int = 10
