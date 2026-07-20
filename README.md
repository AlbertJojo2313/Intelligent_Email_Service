# Intelligent Email Service

This project is an email intelligence service that ingests mailbox data via the Microsoft Graph API (or local mock endpoints) and transforms it into a structured, compressed format optimized for LLM prompting at scale.

Given a financial advisor's mailbox and a target client's (household's) email address, it retrieves historical correspondence, filters and groups it, resolves conversation threads, cleans and compresses the content, and outputs structured JSON payloads ready for downstream LLM context injection.

---

## Key Features & Capabilities

- **Mailbox Ingestion**: Pulls email metadata, message bodies, and attachment descriptors via Microsoft Graph API abstraction (`EmailProvider`).
- **Thread Resolution**: Handles both **unmodified threads** (containing inline quoted history) and **modified threads** (split individual messages sharing a `conversation_id`).
- **Preprocessing & Cleaning**: Strips HTML tags, email headers, disclaimers, and signature blocks ([`docs/preprocessing.md`](docs/preprocessing.md)).
- **Context Compression**: Applies rule-based and hybrid summarization/compression to minimize token consumption and API cost.
- **Synthetic Email Generator**: Includes an asynchronous multi-client generator using the **NVIDIA AI Cloud / NIM API** and template fallbacks to build Graph API-compliant test datasets ([`docs/synthetic-generator.md`](docs/synthetic-generator.md)).

---

## ⚠️ Current Integration Status: Mocked (Planned Graph API Outline)

> [!IMPORTANT]
> The current architecture for Microsoft Graph API support is **just a planned outline and is not implemented yet**. Currently, the project is using a **Mockoon server** to simulate the API endpoints (`GET /v1.0/me/messages`), allowing offline development. Anything in the architecture and specifications **may change**.

For details on local mock server configuration, synthetic dataset generation, and the planned transition to Microsoft Graph API access, see [`docs/mock-setup.md`](docs/mock-setup.md).

---

## Architecture Overview

```
Connector Layer (EmailProvider / MockGraphProvider / MicrosoftGraphProvider)
       │
       ▼
Thread Grouping & Resolution (Unmodified vs Modified email threads)
       │
       ▼
Preprocessing & Cleaning (HTML Stripping / Quote Parsing)
       │
       ▼
Compression (Rule-based & LLM context reduction)
       │
       ▼
Structured JSON Output (LLM Context Prompt Payload)
```

See [`docs/architecture.md`](docs/architecture.md) for detailed data flow diagrams and component design specifications.

---

## Documentation Quick Links

- [**Architecture & System Design**](docs/architecture.md): Data flow pipeline, identity model, and component interactions.
- [**Mock Setup & Local Development**](docs/mock-setup.md): Guide for running Mockoon and local API simulation.
- [**Preprocessing & Compression**](docs/preprocessing.md): Detailed cleaner and compressor module specifications.
- [**Synthetic Email Generator**](docs/synthetic-generator.md): Usage guide for synthetic email thread generation with NVIDIA LLM / Fallback templates.

---

## Testing & Quality Assurance

Run test suite using `pytest`:

```bash
pytest
```
