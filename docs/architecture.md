# Architecture

_Last updated: 2026-07-30_

> [!IMPORTANT]
> **Implementation Status**: The core processing, retrieval, cleaning, and context compression modules are fully implemented (`intelligent_email_service`). Microsoft Graph API support is currently an outline (`MicrosoftGraphProvider`), and local development uses `MockGraphProvider` pointing to a local mock endpoint (e.g., Mockoon).

The Intelligent Email Service is designed to ingest email mailbox data (via local mock endpoints or planned Microsoft Graph API integration), resolve and filter thread history, preprocess and compress email contents, and output structured data optimized for downstream LLM context windows.

---

## Overview

Given a financial advisor's mailbox and a target client (or household) email address, this service:
1. Connects to the mailbox via an extensible provider interface (`EmailProvider`).
2. Queries historical email messages matching client identifiers (From/To/Cc).
3. Groups correspondence by topic/subject and resolves multi-message email threads (handling both modified and unmodified quote formats via `ThreadProcessor`).
4. Preprocesses email bodies (stripping HTML, signatures, and whitespace via `EmailCleaner`).
5. Compresses historical thread context and preserves attachment metadata via `EmailCompressor`.
6. Emits structured `CompressedThread` JSON payloads tailored for LLM prompt context injection.

---

## System Component Architecture

```mermaid
flowchart TD
    subgraph Core Package [intelligent_email_service]
        PM[EmailProviderManager] -->|instantiates| Provider{EmailProvider Interface}
        Provider --> MGP[MockGraphProvider (Active)]
        Provider --> MSGP[MicrosoftGraphProvider (Planned Outline)]
        
        MGP -->|GET /v1.0/users/{user_id}/messages| MockServer[Mockoon / Local Mock Server]
        MSGP -.->|Graph API REST (Planned)| MSGraph[Microsoft Graph API (Unimplemented)]
        
        MGP --> DataPipeline[EmailRetrievalService & ThreadProcessor]
        MSGP -.-> DataPipeline
        
        DataPipeline --> Prep[Preprocessing Module]
        subgraph Preprocessing [intelligent_email_service.preprocessing]
            Prep --> Cleaner[cleaner.py: EmailCleaner]
            Prep --> Compressor[compressor.py: EmailCompressor]
        end
        
        Compressor --> Output[CompressedThread / LLM Context Payload]
    end
    
    subgraph Tools [tools/]
        SynthGen[synthetic_generator] -->|NvidiaClient / LLM| NVIDIA[NVIDIA NIM Cloud API]
        SynthGen -->|FallbackGenerator| Fallback[Local Templates]
        SynthGen -->|generates| MockData[mock_emails.json]
        MockData -->|feeds| MockServer
    end
```

---

## Data Flow Pipeline & Performance Design

1. **Request Reception**: Input parameters specify the Advisor mailbox credentials (`user_id`), target `client_id` (client/household email address), and optional date search window (`start_date`, `end_date`).
2. **Provider Selection & Connection Pooling**: `EmailProviderManager` initializes either `MockGraphProvider` (with HTTP connection pooling via persistent `httpx.AsyncClient`) or `MicrosoftGraphProvider`.
3. **Mailbox Search & Retrieval**: Query the advisor's mailbox for messages where `client_id` appears in sender (`from`), recipient (`toRecipients`), or CC fields via `EmailRetrievalService.get_client_emails`.
4. **Subject & Thread Grouping**:
   - Normalize subject lines using single-pass anchored regex `RE_ALL_PREFIXES`.
   - Group matched messages by normalized subject via `_group_by_subject` using **Schwartzian transform** for single-pass $O(N)$ ISO date parsing.
   - Analyze thread structure for **unmodified** vs. **modified** messages using `ThreadProcessor(provider, user_id, client_id)`:
     - **Unmodified Thread (`FULL_QUOTED`)**: The latest email retains the full trailing quoted history matched against `QUOTED_HEADER_PATTERNS`. Returns a `ProcessedThread` containing the latest message.
     - **Modified Thread (`MODIFIED`)**: Quoted history is stripped/absent. Retrieve all messages under `conversation_id` concurrently across groups via `process_subject_groups()` bounded by semaphore, apply `client_id` participant filtering to enforce client data isolation, and sort chronologically.

5. **Preprocessing & Cleaning** (`intelligent_email_service.preprocessing.cleaner`):
   - Perform signature removal via `EmailCleaner` matching `DEFAULT_SIGNATURE_PATTERNS` and custom patterns.
   - Convert HTML to clean text with BeautifulSoup (`lxml` parser) and normalize whitespace/blank lines.
   - Extract raw text bodies, decode HTML entities, and sanitize attachment metadata.
6. **Compression & Optimization** (`intelligent_email_service.preprocessing.compressor`):
   - `EmailCompressor.compress_processed_thread()` normalizes subject prefixes (`clean_subject`).
   - Retains the `recent_full_count` (default 2) newest messages in full text.
   - Compresses older historical messages using **LLMLingua** (`PromptCompressor`) or fallback character truncation (`max_older_chars`).
   - Preserves attachment metadata (`id`, `name`, `contentType`, `size`) while excluding binary payloads.
   - Computes estimated token counts per message (`math.ceil(len / 4.0)`).
7. **Structured Output**: Emits `CompressedThread` payload ready for downstream LLM prompt construction.


---

## Identity & Integration Model

- **Advisor Mailbox**: The mailbox authenticated by the service (`user_id`).
- **Client ID**: The target client/household email address used strictly as a search and filtering criterion within the advisor's mailbox.
- **Provider Layer**:
  - `EmailProvider`: Abstract base class defining the connector contract (`get_emails`, `get_emails_by_conversation_id`).
  - `MockGraphProvider`: Active provider fetching mock message payloads from local Mockoon server (`http://localhost:3000`).
  - `MicrosoftGraphProvider`: Planned outline for live Graph API integration (`https://graph.microsoft.com/v1.0`).

---

## Synthetic Data & Testing Tooling

For testing and local development without active Microsoft Graph API credentials, the project includes a synthetic dataset generator located in `tools/synthetic_generator`:
- Generates realistic advisor-client conversation threads (`generate_synthetic_emails.py`).
- Uses `NvidiaClient` (NVIDIA AI Cloud / LLM) with local `FallbackGenerator` templates.
- Supports randomized or custom client pools via `ClientPool` and Faker.
- Supports `--thread-format` selection (`full_quoted` vs `modified`).
- Emits schema-compliant Graph API JSON arrays (`mock_emails.json`) for Mockoon ingestion.

---

## Related Documentation

- [`docs/mock-setup.md`](./mock-setup.md): Guide for Mockoon local API simulation setup.
- [`docs/preprocessing.md`](./preprocessing.md): Detailed cleaner and compressor module specifications.
- [`docs/synthetic-generator.md`](./synthetic-generator.md): Usage guide for the synthetic email dataset generator.

