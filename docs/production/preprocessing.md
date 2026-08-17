# Email Preprocessing & Context Compression Specifications

_Last updated: August 12, 2026_

---

## Purpose

Raw email payloads retrieved via email providers contain noise:
- Complex HTML/CSS formatting tags
- Quoted email reply chains (`On [Date]... wrote:`, `From:... Sent:...`)
- Corporate signature blocks, legal disclaimers, and footers
- Excess whitespace and redundant formatting

The preprocessing module extracts readable attachment text, strips HTML noise, normalizes body text, and compresses historical conversation threads into a single streamlined `compressed_body` representation designed for downstream LLM prompt context injection.

---

## Architecture & Module Overview

```
src/intelligent_email_service/
├── preprocessing/
│   ├── __init__.py        # Module exports (EmailCleaner, EmailCompressor, CompressedThread)
│   ├── cleaner.py         # EmailCleaner: HTML stripping, signature removal, whitespace normalization
│   └── compressor.py      # EmailCompressor & CompressedThread: LLMLingua & rule-based compression
└── retrieval/
    └── attachment_processor.py # process_node_attachments: Plain-text attachment extraction
```

---

## 1. Attachment Processing (`attachment_processor.py`)

The [`process_node_attachments()`](file:///Users/aj/Documents/Cognicor_Internship/email_service/src/intelligent_email_service/retrieval/attachment_processor.py#L84) function inspects attachments associated with each `EmailNode`. If an attachment is a plain text format (`.txt`, `.csv`, `.tsv`, `.json`, `.md`, `.xml`, `.log`, `.yaml`), it fetches the raw binary content via `provider.get_attachment_bytes()` and decodes it directly into `attach["content"]`.

```python
from intelligent_email_service.retrieval import process_node_attachments

await process_node_attachments(provider=provider, user_id=advisor_id, node=node)
```

---

## 2. Cleaner Module (`cleaner.py`)

The `EmailCleaner` class processes individual `EmailNode` objects or raw message dictionaries using `CleanerConfig`.

```python
from intelligent_email_service import CleanerConfig
from intelligent_email_service.preprocessing import EmailCleaner

# Config settings automatically load defaults from .env (e.g. CLEANER_STRIP_SIGNATURES)
config = CleanerConfig()
cleaner = EmailCleaner(config=config)
```

#### `CleanerConfig` Attributes:

| Parameter | Type | Default | Environment Variable | Description |
| :--- | :--- | :--- | :--- | :--- |
| `strip_signatures` | `bool` | `True` | `CLEANER_STRIP_SIGNATURES` | Truncates text at detected email signature blocks. |
| `max_blank_lines` | `int` | `1` | `CLEANER_MAX_BLANK_LINES` | Maximum consecutive blank lines allowed. |
| `preserve_links` | `bool` | `False` | `CLEANER_PRESERVE_LINKS` | Extracts and formats HTML links (e.g. `Link Text (https://example.com)`). |
| `custom_signature_patterns` | `list[re.Pattern] \| None` | `None` | N/A | Optional compiled regex patterns for custom signature matching. |

---

## 3. Compressor Module (`compressor.py`)

The `EmailCompressor` class optimizes reconstructed `ProcessedThread` objects into a single `CompressedThread` payload using `CompressorConfig`.

```python
from intelligent_email_service import CompressorConfig
from intelligent_email_service.preprocessing import EmailCompressor

# Config settings automatically load defaults from .env (e.g. USE_LLMLINGUA, LLMLINGUA_MODEL)
config = CompressorConfig()
compressor = EmailCompressor(config=config)
```

#### `CompressorConfig` Attributes:

| Parameter | Type | Default | Environment Variable | Description |
| :--- | :--- | :--- | :--- | :--- |
| `use_llmlingua` | `bool` | `True` | `USE_LLMLINGUA` | Enable/disable neural prompt compression via LLMLingua. |
| `llmlingua_model` | `str` | `"microsoft/llmlingua-2..."` | `LLMLINGUA_MODEL` | Hugging Face model path. |
| `llmlingua_device` | `str` | `"cpu"` | `LLMLINGUA_DEVICE` | Compute device (`cpu`, `cuda`, `mps`). |
| `llmlingua_rate` | `float` | `0.75` | `LLMLINGUA_RATE` | Target token retention ratio (`0.65` - `0.75`). |
| `max_full_body_chars` | `int` | `300` | `COMPRESSOR_MAX_FULL_BODY_CHARS` | Character truncation cap for messages when LLMLingua is inactive. |
| `recent_full_count` | `int` | `2` | `COMPRESSOR_RECENT_FULL_COUNT` | Number of recent messages preserved without aggressive reduction. |

---

### Handling Rules:
* **`FULL_QUOTED` Threads**: Takes the single latest `EmailNode` (which contains embedded quoted history), cleans and compresses its body, and sets top-level `compressed_body`.
* **`MODIFIED` Threads**: Combines all chronological `EmailNode` bodies into a unified thread text, cleans and compresses the combined text, and sets top-level `compressed_body`.
