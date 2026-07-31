# Data Structure & Output Schema

_Last updated: 2026-07-31_

This document specifies the exact output data structure produced by the Intelligent Email Service pipeline (`intelligent_email_service`) and highlights duplicate/redundant fields that can be pruned before downstream LLM context injection.

---

## Output Pipeline Data Flow

```
EmailProvider (Graph API / Mock)
       │
       ▼
EmailRetrievalService (Participant Filtering & Subject Grouping)
       │
       ▼
ThreadProcessor (Thread Re-construction: FULL_QUOTED vs MODIFIED)
       │
       ▼
EmailCleaner (HTML Stripping & Signature Removal)
       │
       ▼
EmailCompressor (Context Compression via LLMLingua / Truncation)
       │
       ▼
CompressedThread (Final Output Object)
```

---

## Full Output Data Structure (`CompressedThread`)

The final output is encapsulated in a `CompressedThread` object (or JSON dictionary):

```json
{
  "subject": "Portfolio Rebalancing Options",
  "conversation_id": "AAQkAGM3...",
  "total_messages": 2,
  "estimated_tokens": 142,
  "used_llmlingua": false,
  "attachments_summary": [
    {
      "id": "att-101",
      "name": "Q3_Portfolio_Summary.pdf",
      "contentType": "application/pdf",
      "size": 245800
    }
  ],
  "compressed_messages": [
    {
      "id": "AAMkAGM3...",
      "subject": "Portfolio Rebalancing Options",
      "conversationId": "AAQkAGM3...",
      "receivedDateTime": "2026-07-28T14:30:00Z",
      "from": {
        "emailAddress": {
          "name": "John Client",
          "address": "john.client@example.com"
        }
      },
      "toRecipients": [
        {
          "emailAddress": {
            "name": "Advisor Jane",
            "address": "advisor.jane@firm.com"
          }
        }
      ],
      "ccRecipients": [],
      "attachments": [
        {
          "id": "att-101",
          "name": "Q3_Portfolio_Summary.pdf",
          "contentType": "application/pdf",
          "size": 245800
        }
      ],

      "body": {
        "contentType": "html",
        "content": "<html><body><p>Hi Jane, can we review my Q3 portfolio rebalancing options?</p></body></html>"
      },
      "cleaned_body": "Hi Jane, can we review my Q3 portfolio rebalancing options?",
      "compressed_body": "Hi Jane, can we review my Q3 portfolio rebalancing options? [... truncated]",

      "is_historical": true,
      "estimated_tokens": 28
    },
    {
      "id": "AAMkAGM4...",
      "subject": "Re: Portfolio Rebalancing Options",
      "conversationId": "AAQkAGM3...",
      "receivedDateTime": "2026-07-29T09:15:00Z",
      "from": {
        "emailAddress": {
          "name": "Advisor Jane",
          "address": "advisor.jane@firm.com"
        }
      },
      "toRecipients": [
        {
          "emailAddress": {
            "name": "John Client",
            "address": "john.client@example.com"
          }
        }
      ],
      "ccRecipients": [],
      "attachments": [],

      "body": {
        "contentType": "text",
        "content": "Sure John, attached is the proposal..."
      },
      "cleaned_body": "Sure John, attached is the proposal. Let me know if you approve.",
      "compressed_body": "Sure John, attached is the proposal. Let me know if you approve.",

      "is_historical": false,
      "estimated_tokens": 20
    }
  ]
}
```

---

## Field Specifications

### Top-Level Attributes (`CompressedThread`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `subject` | `str` | Normalized thread subject (prefixes like `Re:`, `Fwd:` stripped). |
| `conversation_id` | `str \| None` | Microsoft Graph conversation thread ID. |
| `total_messages` | `int` | Total count of messages in the thread. |
| `estimated_tokens` | `int` | Sum of estimated tokens across all compressed messages (`ceil(len/4)`). |
| `used_llmlingua` | `bool` | Flag indicating whether LLMLingua neural compression was executed. |
| `attachments_summary` | `list[dict]` | Aggregated list of all sanitized attachment metadata across all messages in the thread. |
| `compressed_messages` | `list[dict]` | Chronologically ordered list of enriched email message dictionaries. |

### Message Attributes (Inside `compressed_messages`)

| Field | Type | Source Module | Description |
| :--- | :--- | :--- | :--- |
| `id` | `str` | Connector (`EmailProvider`) | Unique Graph API message identifier. |
| `subject` | `str` | Connector (`EmailProvider`) | Original message subject line. |
| `conversationId` | `str` | Connector (`EmailProvider`) | Microsoft Graph conversation ID. |
| `receivedDateTime` | `str` | Connector (`EmailProvider`) | ISO-8601 timestamp of message receipt. |
| `from` | `dict` | Connector (`EmailProvider`) | Sender object: `{"emailAddress": {"name": "...", "address": "..."}}`. |
| `toRecipients` | `list[dict]` | Connector (`EmailProvider`) | List of recipient objects. |
| `ccRecipients` | `list[dict]` | Connector (`EmailProvider`) | List of CC recipient objects. |
| `attachments` | `list[dict]` | `EmailRetrievalService` | Per-message sanitized attachment metadata list. |
| `body` | `dict \| str` | Connector (`EmailProvider`) | Original raw body object/HTML string. |
| `cleaned_body` | `str` | `EmailCleaner` | Text body after HTML parsing and signature removal. |
| `compressed_body` | `str` | `EmailCompressor` | Final compressed/truncated text ready for LLM injection. |
| `is_historical` | `bool` | `EmailCompressor` | `True` if message is older than `recent_full_count` cutoff; `False` if recent. |
| `estimated_tokens` | `int` | `EmailCompressor` | Estimated token count for this message's `compressed_body`. |

---

## ⚠️ Redundant / Duplicate Fields Analysis

When transforming this output into a prompt payload for LLM consumption, several fields are redundant and should be pruned to maximize token efficiency:

### 1. Body Field Triplication (`body` vs. `cleaned_body` vs. `compressed_body`)
- **Duplicates**: Each message contains three versions of the body content:
  - `body`: Raw HTML/text (largest size).
  - `cleaned_body`: Stripped plain text.
  - `compressed_body`: Truncated/compressed text for LLM injection.
- **Recommendation for LLM Payload**: Remove `body` and `cleaned_body`. Only include `compressed_body` in the context window.

### 2. Attachment List Duplication (`attachments` vs. `attachments_summary`)
- **Duplicates**: Attachments are listed per-message inside `compressed_messages[].attachments` AND globally in top-level `attachments_summary`.
- **Recommendation for LLM Payload**: Keep `attachments_summary` at the top level for a quick overview and prune `attachments` from individual messages (or vice-versa).

### 3. Subject Redundancy (`CompressedThread.subject` vs. `message["subject"]`)
- **Duplicates**: Top-level `subject` holds the normalized subject line ("Portfolio Rebalancing Options"), while every message in `compressed_messages` retains its original subject ("Re: Portfolio Rebalancing Options").
- **Recommendation for LLM Payload**: Omit individual message `subject` fields in the LLM prompt, as they repeat the thread topic and add unnecessary tokens.

### 4. Conversation ID Duplication (`conversation_id` vs. `message["conversationId"]`)
- **Duplicates**: The top-level `conversation_id` matches `conversationId` on every message dict.
- **Recommendation for LLM Payload**: Omit `conversationId` from individual messages.

### 5. Typo Alias Keys (`receivedDateTime` vs. `recievedDateTime`)
- **Duplicates**: In legacy/mock provider data, `recievedDateTime` (misspelled) may exist alongside `receivedDateTime`.
- **Recommendation for LLM Payload**: Normalize all date fields to `receivedDateTime` and strip `recievedDateTime`.

---

## Recommended Minimal Payload for Downstream LLM Prompting

For feeding into downstream LLM context windows, prune redundant fields into this optimized structure:

```json
{
  "subject": "Portfolio Rebalancing Options",
  "conversation_id": "AAQkAGM3...",
  "total_messages": 2,
  "attachments": [
    { "name": "Q3_Portfolio_Summary.pdf", "contentType": "application/pdf" }
  ],
  "messages": [
    {
      "from": "john.client@example.com",
      "to": ["advisor.jane@firm.com"],
      "date": "2026-07-28T14:30:00Z",
      "content": "Hi Jane, can we review my Q3 portfolio rebalancing options? [... truncated]",
      "is_historical": true
    },
    {
      "from": "advisor.jane@firm.com",
      "to": ["john.client@example.com"],
      "date": "2026-07-29T09:15:00Z",
      "content": "Sure John, attached is the proposal. Let me know if you approve.",
      "is_historical": false
    }
  ]
}
```
