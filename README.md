# Email Intelligence Service

This project is an email intelligence service that ingests mailbox data via the Microsoft Graph API and transforms it into a structured, compressed format suitable for LLM prompting at scale.

Given an advisor's mailbox and a client's (household's) email address, it retrieves the relevant historical correspondence, filters and groups it, and compresses it for downstream use.

Specifically, it:

- Pulls email data (metadata, body, attachments, etc.) from Microsoft Graph API
- Applies preprocessing (see */docs/preprocessing.md* for more information)
- Applies compression/summarization techniques to reduce volume while preserving context for downstream LLM tasks
- Outputs structured data (e.g. JSON schema - *link it*) designed to fit within LLM context limits / minimize token cost.

---

## ⚠️ Current Integration Status: Mocked

This project currently uses **Mockoon** to simulate the Microsoft Graph API (no production API access yet). See */docs/mock-setup.md* for more details on what's mocked, known gaps vs. the real API, and how to switch over once access is available.

---

## Architecture

This service searches an advisor's mailbox for correspondence involving agiven client, resolves and compresses the relevant email thread content, and outputs structured data suitable for LLM prompting.

High-Level Data Flow:

`Connector -> client search & grouping -> thread resolution -> body/attachment extraction -> compression -> structured JSON output`

See [`docs/architecture.md`](docs/architecture.md) for the full diagram, step-by-step data flow, and design rationale.

---

