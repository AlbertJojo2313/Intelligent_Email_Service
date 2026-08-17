# Intelligent Email Service — Production Documentation

Welcome to the production documentation for the **Intelligent Email Service**.

This package ingests email correspondence from financial advisors' mailboxes via Microsoft Graph API (or local mock servers), converts incoming payloads into a strongly-typed `EmailNode` domain model, reconstructs thread history using an in-memory Directed Acyclic Graph (DAG), cleans HTML and signatures, extracts text attachments, and compresses context using LLMLingua into streamlined `CompressedThread` payloads ready for LLM context windows.

---

## 📚 Documentation Index

- **[System Architecture](architecture.md)** — End-to-end component diagrams, DAG reconstruction logic, and execution stages.
- **[Data Schemas & Output Specification](data-structure.md)** — Field-by-field definitions for `EmailNode` and `CompressedThread`.
- **[Preprocessing & Compression Module](preprocessing.md)** — Specifications for `EmailCleaner`, `EmailCompressor`, and `process_node_attachments()`.

---

## ⚙️ Environment Configuration Quick Reference

All service parameters can be configured via environment variables or specified programmatically in `PipelineConfig`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `dev` | Profile mode: `dev`, `test_prod`, `prod`, or `production`. |
| `LOG_LEVEL` | `INFO` | Package logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `MAX_CONCURRENCY` | `10` | Maximum concurrent thread processing operations. |
| `AZURE_TENANT_ID` | *Required in Prod* | Azure AD Tenant ID. |
| `AZURE_CLIENT_ID` | *Required in Prod* | Azure AD Client App ID. |
| `AZURE_CLIENT_SECRET` | *Required in Prod* | Azure AD Client Secret. |
| `GRAPH_API_BASE_URL` | `https://graph.microsoft.com/v1.0` | Base endpoint for Microsoft Graph API. |
| `MOCK_SERVER_URL` | `http://localhost:3000` | Mock server endpoint for `dev` mode. |
| `USE_LLMLINGUA` | `true` | Enable/disable LLMLingua neural prompt compression. |
| `LLMLINGUA_MODEL` | `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | Hugging Face model for prompt compression. |
| `LLMLINGUA_DEVICE` | `cpu` | Target device (`cpu`, `cuda`, `mps`). |
