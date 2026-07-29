# Email Preprocessing & Compression Module Specification

_Last updated: 2026-07-28_

> [!NOTE]
> **Implementation Status**: The cleaning module (`cleaner.py`) is fully implemented with `EmailCleaner`. The compression module (`compressor.py`) remains a planned architecture specification.

---

## Purpose

Raw email payloads retrieved via email providers contain significant noise:
- Complex HTML/CSS formatting tags
- Quoted email reply chains (`On [Date]... wrote:`, `From:... Sent:...`)
- Corporate signature blocks, legal disclaimers, and footers
- Excess whitespace and redundant formatting

Feeding raw email HTML into LLM context windows causes excessive token consumption, higher API latency, and degraded prompt adherence. The preprocessing module strips noise and normalizes body text into a clean representation designed for downstream LLM context windows.

---

## Architecture & Module Overview

The package consists of two primary modules within `src/intelligent_email_service/preprocessing/`:

```
src/intelligent_email_service/preprocessing/
├── __init__.py        # Module exports (EmailCleaner)
├── cleaner.py         # EmailCleaner: HTML stripping, signature/quote removal, normalization
└── compressor.py      # Rule-based & LLM context compression (Planned)
```

---

## 1. Cleaner Module (`cleaner.py`)

The `EmailCleaner` class processes individual email message bodies to extract normalized text.

### `EmailCleaner` Interface & Configuration

```python
from intelligent_email_service.preprocessing import EmailCleaner

cleaner = EmailCleaner(
    strip_signatures=True,
    strip_quotes=True,
    max_blank_lines=1,
    preserve_links=False,
    custom_signature_patterns=None
)
```

#### Initialization Arguments:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `strip_signatures` | `bool` | `True` | Whether to truncate text at detected email signature blocks. |
| `strip_quotes` | `bool` | `True` | Whether to truncate text at quoted conversation history boundaries. |
| `max_blank_lines` | `int` | `1` | Maximum consecutive blank lines allowed (`-1` disables collapsing). |
| `preserve_links` | `bool` | `False` | Whether to extract and format HTML links (e.g. `Link Text (https://example.com)`). |
| `custom_signature_patterns` | `list[re.Pattern]` | `None` | Optional list of additional compiled regex patterns for signature matching. |

---

### Core Pipeline Steps

1. **HTML Parsing & Tag Stripping (`_clean_html`)**:
   - Parses HTML using BeautifulSoup (`lxml` parser).
   - Decomposes non-content elements (`script`, `style`, `head`, `title`, `meta`, `noscript`).
   - Formats `<a>` links if `preserve_links=True` (e.g., `Text (URL)`).
   - Decodes HTML entities (`html.unescape`).

2. **Quoted History Truncation (`QUOTED_PATTERNS`)**:
   - Matches standard quote headers:
     - `On <date> <user> wrote:`
     - `--- Original Message ---`
     - `From: ... Sent: ...`

3. **Signature Block Removal (`DEFAULT_SIGNATURE_PATTERNS`)**:
   - Removes common advisor/firm sign-offs, disclaimers, and mobile device notices:
     - `^--(?: \r?\n|\r?\n)`
     - `CONFIDENTIALITY NOTICE:...`
     - `This email and any attachments are intended only for...`
     - `Sent from my iPhone / Android`
     - `Best regards, / Sincerely, / Regards, / Thanks,`

4. **Whitespace Normalization (`_normalize_whitespace`)**:
   - Replaces non-breaking space characters (`&nbsp;`, `\xa0`) with standard spaces.
   - Trims trailing whitespace from each line.
   - Collapses consecutive blank lines exceeding `max_blank_lines`.

---

## 2. Usage Examples

### Cleaning a Raw Message Object

```python
from intelligent_email_service.preprocessing import EmailCleaner

cleaner = EmailCleaner(strip_signatures=True, strip_quotes=True)

raw_message = {
    "id": "AAMkAG123...",
    "subject": "Re: Portfolio Rebalancing",
    "body": {
        "contentType": "html",
        "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>Best regards,<br>Jane</div>"
    }
}

cleaned_message = cleaner.clean_message(raw_message)
print(cleaned_message["cleaned_body"])
# Output: "Hi John,\n\nLet's proceed with rebalancing."
```

---

## 3. Input / Output Schemas

### Input (Message Object with Body)

```json
{
  "id": "AAMkAG123...",
  "subject": "Re: Portfolio Rebalancing",
  "body": {
    "contentType": "html",
    "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>On 2026-07-15, John wrote:<br>&gt; Should we rebalance?</div>"
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
    "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>On 2026-07-15, John wrote:<br>&gt; Should we rebalance?</div>"
  },
  "cleaned_body": "Hi John,\n\nLet's proceed with rebalancing."
}
```

---

## 4. Compressor Module (`compressor.py` - Planned)

The compressor will optimize clean email threads for LLM prompt context windows:
1. **Rule-Based Compression**: Eliminates filler words, duplicate subject prefixes, and retains financial entities.
2. **Hybrid LLM Prompt Compression**: Applies prompt compression techniques (such as LLMLingua) for historical email chains.
3. **Attachment Metadata Preservation**: Preserves metadata while excluding binary payloads.

