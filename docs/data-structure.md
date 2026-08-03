# Data Structure & Output Schema

_Last updated: August 3, 2026_

This document specifies the exact output data structure produced by the Intelligent Email Service pipeline (`intelligent_email_service`).

---

## Output Pipeline Data Flow

```
EmailProvider (Graph API / Mock)
       │
       ▼
EmailRetrievalService (Participant Filtering & EmailNode Domain Conversion)
       │
       ▼
ThreadProcessor (Strategy Layer: GraphConversationReconstructor In-Memory DAG)
       │
       ▼
EmailCleaner (HTML Stripping & Signature Removal)
       │
       ▼
EmailCompressor (Unified Context Compression via LLMLingua / Truncation)
       │
       ▼
CompressedThread (Final Streamlined Output Object)
```

---

## Output Data Structure (`CompressedThread`)

The final output is encapsulated in a `CompressedThread` object (or JSON dictionary) containing **one single top-level `compressed_body` per subject**:

```json
{
  "subject": "Portfolio Rebalancing Options",
  "conversation_id": "AAQkAGM3...",
  "format": "full_quoted",
  "total_messages": 1,
  "compressed_body": "Hi Jane, can we review my Q3 portfolio rebalancing options?",
  "attachments_summary": [
    {
      "id": "att-101",
      "name": "Q3_Portfolio_Summary.pdf",
      "contentType": "application/pdf",
      "size": 245800
    }
  ],
  "estimated_tokens": 16,
  "used_llmlingua": false
}
```

---

## Field Specifications

### Top-Level Attributes (`CompressedThread`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `subject` | `str` | Normalized thread subject (prefixes like `Re:`, `Fwd:` stripped). |
| `conversation_id` | `str \| None` | Microsoft Graph conversation thread ID. |
| `format` | `str` | Thread format type (`"full_quoted"` or `"modified"`). |
| `total_messages` | `int` | Total count of messages in the thread. |
| `compressed_body` | `str` | Single unified compressed body for the entire thread, ready for LLM prompt injection. |
| `estimated_tokens` | `int` | Estimated tokens for `compressed_body` (`ceil(len / 4.0)`). |
| `used_llmlingua` | `bool` | Flag indicating whether LLMLingua neural prompt compression executed successfully. |
| `attachments_summary` | `list[dict]` | Aggregated list of all sanitized attachment metadata across the thread. |

---

## Domain Model (`EmailNode`)

Internal thread processing consumes strongly-typed `EmailNode` objects instead of raw dictionaries:

```python
@dataclass
class EmailNode:
    id: str
    conversation_id: str | None
    message_id: str | None
    in_reply_to: str | None
    subject: str
    sender: str
    recipients: list[str]
    received_at: datetime | None
    body_content: str
    content_type: str
    cleaned_body: str
    attachments: list[dict[str, Any]]
```
