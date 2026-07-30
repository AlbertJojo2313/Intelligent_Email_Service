# Email Preprocessing & Compression Module Specification

_Last updated: 2026-07-30_

> [!NOTE]
> **Implementation Status**: Both the cleaning module (`cleaner.py`: `EmailCleaner`) and the context compression module (`compressor.py`: `EmailCompressor`, `CompressedThread`) are fully implemented and exported in `intelligent_email_service.preprocessing`.

---

## Purpose

Raw email payloads retrieved via email providers contain significant noise:
- Complex HTML/CSS formatting tags
- Quoted email reply chains (`On [Date]... wrote:`, `From:... Sent:...`)
- Corporate signature blocks, legal disclaimers, and footers
- Excess whitespace and redundant formatting

Feeding raw email HTML into LLM context windows causes excessive token consumption, higher API latency, and degraded prompt adherence. The preprocessing module strips noise, normalizes body text, and compresses historical conversation threads into a structured representation designed for downstream LLM prompt context injection.

---

## Architecture & Module Overview

The package consists of two primary modules within `src/intelligent_email_service/preprocessing/`:

```
src/intelligent_email_service/preprocessing/
├── __init__.py        # Module exports (EmailCleaner, EmailCompressor, CompressedThread)
├── cleaner.py         # EmailCleaner: HTML stripping, signature removal, whitespace normalization
└── compressor.py      # EmailCompressor & CompressedThread: LLMLingua & rule-based thread compression
```

---

## 1. Cleaner Module (`cleaner.py`)

The `EmailCleaner` class processes individual email message bodies to extract normalized text.

### `EmailCleaner` Interface & Configuration

```python
from intelligent_email_service.preprocessing import EmailCleaner

cleaner = EmailCleaner(
    strip_signatures=True,
    max_blank_lines=1,
    preserve_links=False,
    custom_signature_patterns=None,
)
```

#### Initialization Arguments:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `strip_signatures` | `bool` | `True` | Whether to truncate text at detected email signature blocks. |
| `max_blank_lines` | `int` | `1` | Maximum consecutive blank lines allowed (`-1` disables collapsing). |
| `preserve_links` | `bool` | `False` | Whether to extract and format HTML links (e.g. `Link Text (https://example.com)`). |
| `custom_signature_patterns` | `list[re.Pattern]` | `None` | Optional list of additional compiled regex patterns for signature matching. |

> **Note**: Quoted history header detection (`QUOTED_HEADER_PATTERNS`) and multi-message thread reconstruction are handled upstream by `ThreadProcessor` (`intelligent_email_service.retrieval`).

---

### Core Pipeline Steps

1. **HTML Parsing & Tag Stripping (`_clean_html`)**:
   - Parses HTML using BeautifulSoup (`lxml` parser).
   - Decomposes non-content elements (`script`, `style`, `head`, `title`, `meta`, `noscript`).
   - Formats `<a>` links if `preserve_links=True` (e.g., `Text (URL)`).
   - Decodes HTML entities (`html.unescape`).

2. **Signature Block Removal (`DEFAULT_SIGNATURE_PATTERNS`)**:
   - Removes common advisor/firm sign-offs, disclaimers, and mobile device notices:
     - `^--(?: \r?\n|\r?\n)`
     - `CONFIDENTIALITY NOTICE:...`
     - `This email and any attachments are intended only for...`
     - `Sent from my iPhone / Android`
     - `Best regards, / Sincerely, / Regards, / Thanks,`

3. **Whitespace Normalization (`_normalize_whitespace`)**:
   - Replaces non-breaking space characters (`&nbsp;`, `\xa0`) with standard spaces.
   - Trims trailing whitespace from each line.
   - Collapses consecutive blank lines exceeding `max_blank_lines`.

---

## 2. Cleaner Usage Example

```python
from intelligent_email_service.preprocessing import EmailCleaner

cleaner = EmailCleaner(strip_signatures=True, preserve_links=True)

raw_message = {
    "id": "AAMkAG123...",
    "subject": "Re: Portfolio Rebalancing",
    "body": {
        "contentType": "html",
        "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>Best regards,<br>Jane</div>",
    },
}

cleaned_message = cleaner.clean_message(raw_message)
print(cleaned_message["cleaned_body"])
# Output: "Hi John,\n\nLet's proceed with rebalancing."
```

---

## 3. Cleaner Schemas

### Input (Message Object with Body)

```json
{
  "id": "AAMkAG123...",
  "subject": "Re: Portfolio Rebalancing",
  "body": {
    "contentType": "html",
    "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>Best regards,<br>Jane</div>"
  }
}
```

### Output (Cleaned Message Object)

```json
{
  "id": "AAMkAG123...",
  "subject": "Re: Portfolio Rebalancing",
  "body": {
    "contentType": "html",
    "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>Best regards,<br>Jane</div>"
  },
  "cleaned_body": "Hi John,\n\nLet's proceed with rebalancing."
}
```

---

## 4. Compressor Module (`compressor.py`)

The `EmailCompressor` class optimizes reconstructed `ProcessedThread` objects for downstream LLM prompt context windows.

### `EmailCompressor` Interface & Configuration

```python
from intelligent_email_service.preprocessing import EmailCompressor

compressor = EmailCompressor(
    recent_full_count=2,
    max_older_chars=300,
    use_llmlingua=True,
    llmlingua_rate=0.5,
    llmlingua_model="microsoft/llmlingua-2-bert-base-multilingual-cased-meeting",
)
```

#### Initialization Arguments:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `recent_full_count` | `int` | `2` | Number of most recent messages kept in full-text without truncation/compression. |
| `max_older_chars` | `int` | `300` | Fallback character cap for older historical messages when LLMLingua is disabled or unavailable. |
| `use_llmlingua` | `bool` | `True` | Whether to attempt prompt compression on older messages via `llmlingua.PromptCompressor`. |
| `llmlingua_rate` | `float` | `0.5` | Compression target ratio for LLMLingua (e.g. 0.5 = 50% target token reduction). |
| `llmlingua_model` | `str` | `"microsoft/llmlingua-2-..."` | Hugging Face model identifier for LLMLingua-2 context compression. |

---

### Compression Pipeline Logic

1. **Subject Prefix Normalization (`clean_subject`)**:
   - Strips redundant leading `Re:`, `Fwd:`, `FW:` prefixes from thread subjects.
2. **`FULL_QUOTED` & Short Thread Bypass**:
   - If thread format is `FULL_QUOTED` or total message count is $\le$ `recent_full_count`, compression is bypassed and full cleaned body text is returned directly.
3. **`MODIFIED` Multi-Message Thread Context Reduction**:
   - Keeps the newest `recent_full_count` messages in full text (`is_historical=False`).
   - For older historical messages (`is_historical=True`):
     - Uses **LLMLingua** (`_compress_llmlingua`) if enabled and body length $\ge 100$ chars.
     - Falls back to character truncation (`_truncate_text`) appending `[... truncated]` if LLMLingua fails or is disabled.
4. **Attachment Metadata Extraction (`_extract_attachments`)**:
   - Extracts attachment metadata (`id`, `name`, `contentType`, `size`) into `attachments_summary` while stripping binary payloads.
5. **Token Estimation**:
   - Estimates token count per message using `math.ceil(len(body) / 4.0)`.

---

### `CompressedThread` Output Data Structure

```python
@dataclass
class CompressedThread:
    subject: str
    conversation_id: str | None
    total_messages: int
    compressed_messages: list[dict[str, Any]]
    attachments_summary: list[dict[str, Any]]
    estimated_tokens: int
    used_llmlingua: bool
```

---

### Compressor Usage Example

```python
from intelligent_email_service.preprocessing import EmailCompressor
from intelligent_email_service.retrieval import ProcessedThread, ThreadFormat

compressor = EmailCompressor(recent_full_count=2, max_older_chars=100, use_llmlingua=False)

# Assuming thread is a ProcessedThread returned from ThreadProcessor
compressed = compressor.compress_processed_thread(thread)

print(f"Subject: {compressed.subject}")
print(f"Total Messages: {compressed.total_messages}")
print(f"Estimated Tokens: {compressed.estimated_tokens}")
for msg in compressed.compressed_messages:
    print(f"Historical: {msg['is_historical']} | Body: {msg['compressed_body']}")
```


