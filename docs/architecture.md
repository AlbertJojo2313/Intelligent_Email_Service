# Architecture

_Last updated: 2026-07-20_

> [!IMPORTANT]
> **Implementation Status**: The current architecture for Microsoft Graph API support is **just a planned outline and is not implemented yet**. The project is currently using a **Mockoon server** to simulate the API endpoints. Anything in the architecture and specifications **may change**.

The Intelligent Email Service is designed to ingest email mailbox data (via local mock endpoints or planned Microsoft Graph API integration), resolve and filter thread history, preprocess and compress email contents, and output structured data optimized for downstream LLM context windows.

---

## Overview

Given a financial advisor's mailbox and a target client (or household) email address, this service:
1. Connects to the mailbox via an extensible provider interface (`EmailProvider`).
2. Queries historical email messages matching client identifiers (From/To/Cc).
3. Groups correspondence by topic/subject and resolves multi-message email threads (handling both modified and unmodified quote formats).
4. Preprocesses and compresses email message bodies while handling attachments.
5. Emits structured JSON payloads tailored for LLM prompt context injection.

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
        
        MGP --> DataPipeline[Ingestion & Thread Resolution]
        MSGP -.-> DataPipeline
        
        DataPipeline --> Prep[Preprocessing Module]
        subgraph Preprocessing [intelligent_email_service.preprocessing]
            Prep --> Cleaner[cleaner.py: HTML / Quote Stripper]
            Prep --> Compressor[compressor.py: Context Compressor]
        end
        
        Compressor --> Output[Structured JSON / LLM Prompt Payload]
    end
    
    subgraph Tools [tools/]
        SynthGen[synthetic_generator] -->|NvidiaClient / LLM| NVIDIA[NVIDIA NIM Cloud API]
        SynthGen -->|FallbackGenerator| Fallback[Local Templates]
        SynthGen -->|generates| MockData[mock_emails.json]
        MockData -->|feeds| MockServer
    end
```

---

## Data Flow Pipeline

1. **Request Reception**: Input parameters specify the Advisor mailbox credentials, target `ClientID` (client/household email address), and date search window (e.g., 3–5 years).
2. **Provider Selection**: `EmailProviderManager` initializes either `MockGraphProvider` (for local simulation) or `MicrosoftGraphProvider` (for live Azure/Graph API access).
3. **Mailbox Search & Retrieval**: Query the advisor's mailbox for messages where `ClientID` appears in sender (`from`), recipient (`toRecipients`), or CC fields.
4. **Subject & Thread Grouping**:
   - Group matched messages by conversation identifier (`conversation_id`) and subject.
   - Analyze thread structure for **unmodified** vs. **modified** messages:
     - **Unmodified Thread**: The latest email retains the full trailing quoted history (`On [Date], X wrote: > ...`). No extra thread fetch required.
     - **Modified Thread**: Quoted history is stripped/absent. Retrieve all messages under `conversation_id`, sort chronologically, and merge.
5. **Preprocessing & Cleaning** (`intelligent_email_service.preprocessing.cleaner`):
   - Strip HTML formatting, signatures, and redundant email headers.
   - Extract raw text bodies and attachment metadata.
6. **Compression & Optimization** (`intelligent_email_service.preprocessing.compressor`):
   - Perform rule-based token reduction and hybrid LLM prompt compression (e.g., LLMLingua / summary heuristic).
   - Preserve attachment metadata while excluding binary payloads from LLM context.
7. **Structured Output**: Produce JSON structured output containing client metadata, chronological thread history, and compressed message content.

---

## Identity & Integration Model

- **Advisor Mailbox**: The mailbox authenticated by the service (Outlook / Azure AD app registration).
- **Client ID**: The target client/household email address used strictly as a search and filtering criterion within the advisor's mailbox.
- **Provider Layer**:
  - `EmailProvider`: Abstract base class defining the connector contract (`get_emails`).
  - `MockGraphProvider`: Active provider fetching mock message payloads from local Mockoon server (`http://localhost:3000`).
  - `MicrosoftGraphProvider`: Planned outline for live Graph API integration (currently unimplemented; specifications may change).

---

## Synthetic Data & Testing Tooling

For testing and local development without active Microsoft Graph API credentials, the project includes a synthetic dataset generator located in `tools/synthetic_generator`:
- Generates realistic advisor-client conversation threads.
- Uses `NvidiaClient` (NVIDIA AI Cloud / LLM) with local `FallbackGenerator` templates.
- Supports randomized or custom client pools via `ClientPool` and Faker.
- Emits schema-compliant Graph API JSON arrays (`mock_emails.json`) for Mockoon ingestion.

---

## Related Documentation

- [`docs/mock-setup.md`](./mock-setup.md): Guide for Mockoon local API simulation setup.
- [`docs/preprocessing.md`](./preprocessing.md): Detailed cleaner and compressor module specifications.
- [`docs/synthetic-generator.md`](./synthetic-generator.md): Usage guide for the synthetic email dataset generator.
