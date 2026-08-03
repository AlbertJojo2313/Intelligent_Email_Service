# Email Preprocessing & Compression Module Specification

_Last updated: August 3, 2026_

> [!NOTE]
> **Implementation Status**: Both the cleaning module (`cleaner.py`: `EmailCleaner`) and the context compression module (`compressor.py`: `EmailCompressor`, `CompressedThread`) are fully implemented and exported in `intelligent_email_service.preprocessing`.

---

## Purpose

Raw email payloads retrieved via email providers contain significant noise:
- Complex HTML/CSS formatting tags
- Quoted email reply chains (`On [Date]... wrote:`, `From:... Sent:...`)
- Corporate signature blocks, legal disclaimers, and footers
- Excess whitespace and redundant formatting

The preprocessing module strips noise, normalizes body text, and compresses historical conversation threads into a single streamlined `compressed_body` representation designed for downstream LLM prompt context injection.

---

## Architecture & Module Overview

```
src/intelligent_email_service/preprocessing/
├── __init__.py        # Module exports (EmailCleaner, EmailCompressor, CompressedThread)
├── cleaner.py         # EmailCleaner: HTML stripping, signature removal, whitespace normalization
└── compressor.py      # EmailCompressor & CompressedThread: LLMLingua & rule-based thread compression
```

---

## 1. Cleaner Module (`cleaner.py`)

The `EmailCleaner` class processes individual `EmailNode` objects or raw message dictionaries to extract normalized text using `CleanerConfig`.

```python
from intelligent_email_service import CleanerConfig
from intelligent_email_service.preprocessing import EmailCleaner

config = CleanerConfig(
    strip_signatures=True,
    max_blank_lines=1,
    preserve_links=False,
    custom_signature_patterns=None,
)

cleaner = EmailCleaner(config=config)
```

#### `CleanerConfig` Attributes:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `strip_signatures` | `bool` | `True` | Whether to truncate text at detected email signature blocks. |
| `max_blank_lines` | `int` | `1` | Maximum consecutive blank lines allowed. |
| `preserve_links` | `bool` | `False` | Whether to extract and format HTML links (e.g. `Link Text (https://example.com)`). |
| `custom_signature_patterns` | `list[re.Pattern]` | `None` | Optional list of additional compiled regex patterns for signature matching. |

---

## 2. Compressor Module (`compressor.py`)

The `EmailCompressor` class optimizes reconstructed `ProcessedThread` objects for downstream LLM prompt context windows using `CompressorConfig`.

```python
from intelligent_email_service import CompressorConfig
from intelligent_email_service.preprocessing import EmailCompressor

config = CompressorConfig(
    recent_full_count=2,
    max_full_body_chars=300,
    use_llmlingua=True,
    llmlingua_rate=0.5,
    llmlingua_model="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
    llmlingua_device="cpu",
)

compressor = EmailCompressor(config=config)
```

#### Handling Rules:
* **`FULL_QUOTED` Threads**: Takes the latest `EmailNode` (which contains the embedded quoted history), cleans and compresses its body, and sets top-level `compressed_body`.
* **`MODIFIED` Threads**: Combines all chronological `EmailNode` objects into a unified thread text, cleans and compresses that combined text, and sets top-level `compressed_body`.

---

### `CompressedThread` Output Data Structure

```python
@dataclass
class CompressedThread:
    subject: str
    conversation_id: str | None
    format: str
    total_messages: int
    compressed_body: str
    attachments_summary: list[dict[str, Any]]
    estimated_tokens: int
    used_llmlingua: bool
```
