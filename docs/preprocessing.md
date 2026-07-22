# Email Preprocessing & Compression Module Specification

_Last updated: 2026-07-22_

> [!IMPORTANT]
> **Implementation Status**: The preprocessing and compression modules (`cleaner.py` and `compressor.py`) are currently **planned architecture specifications and skeleton modules**. This document defines the design and interfaces for their upcoming implementation.

---

## Purpose

Raw email payloads retrieved via the Microsoft Graph API contain significant noise:
- Complex HTML/CSS formatting tags
- Quoted email reply chains (`> On [Date], [User] wrote:...`)
- Corporate signature blocks, legal disclaimers, and footers
- Redundant header lines across multi-turn threads

Feeding raw email HTML into LLM context windows causes excessive token consumption, higher API latency, and degraded prompt adherence. The preprocessing module strips noise and compresses body text into a clean, structured representation designed for downstream LLM context windows.

---

## Architecture & Module Overview

The package consists of two primary modules within `src/intelligent_email_service/preprocessing/`:

```
src/intelligent_email_service/preprocessing/
├── __init__.py        # Module exports
├── cleaner.py         # HTML stripping, header parsing, quote detection (Skeleton)
└── compressor.py      # Rule-based & LLM context compression (Skeleton)
```

---

## 1. Cleaner Module (`cleaner.py`)

The cleaning pipeline processes individual email message bodies to extract clean text.

### Key Responsibilities:

1. **HTML Parsing & Tag Stripping**:
   - Converts HTML email bodies (`"content_type": "html"`) to clean plain text using HTML parser utilities (e.g., BeautifulSoup or `html2text`).
   - Normalizes inline links and table formatting while removing scripts, styles, and decorative elements.

2. **Quoted History Detection & Extraction**:
   - Identifies quote markers (e.g., lines starting with `>`, `From:`, `Sent:`, `On [Date]... wrote:`).
   - Differentiates between **unmodified threads** (where trailing quote chains are present) and **modified threads** (clean individual responses).
   - Strips redundant trailing quotes when assembling full conversation thread histories.

3. **Signature & Boilerplate Removal**:
   - Uses heuristic regex patterns to trim common advisor/firm email sign-offs (e.g., "Best regards,", "CONFIDENTIALITY NOTICE:", phone numbers, physical addresses).

4. **Text Normalization**:
   - Collapses duplicate newlines, trailing spaces, and unicode control characters.

---

## 2. Compressor Module (`compressor.py`)

The compressor optimizes clean email threads for LLM prompt context windows.

### Key Responsibilities:

1. **Rule-Based Compression**:
   - Eliminates conversational filler while retaining key financial entities (dollar amounts, account types, ticker symbols, dates, key requests).
   - Prunes duplicate subject prefix lines (`Re: Re: Re:` -> `Re:`).

2. **Hybrid LLM Prompt Compression**:
   - Applies extractive summarization or prompt compression techniques (such as LLMLingua) for lengthy historical email chains.
   - Preserves high-density information points while reducing total token count by up to 50–70%.

3. **Attachment Metadata Preservation**:
   - Preserves attachment metadata (filename, MIME type, size, attachment ID) in output metadata.
   - Binary attachment payloads are excluded from LLM context to prevent window overflow.

---

## Input / Output Schemas

### Input (Raw Graph API Message Body)

```json
{
  "id": "AAMkAG123...",
  "subject": "Re: Portfolio Rebalancing",
  "body": {
    "content_type": "html",
    "content": "<div>Hi John,<br><br>Let's proceed with rebalancing.<br><br>On 2026-07-15, John wrote:<br>&gt; Should we rebalance?</div>"
  }
}
```

### Output (Processed & Compressed Object)

```json
{
  "message_id": "AAMkAG123...",
  "conversation_id": "807e0e68-...",
  "client_id": "client@example.com",
  "subject": "Portfolio Rebalancing",
  "timestamp": "2026-07-16T18:00:00Z",
  "sender": "client@example.com",
  "recipient": "advisor@example.com",
  "cleaned_body": "Hi John, Let's proceed with rebalancing.",
  "compressed_body": "Client approves portfolio rebalancing.",
  "token_count_original": 145,
  "token_count_compressed": 6,
  "has_attachments": false,
  "attachments": []
}
```
