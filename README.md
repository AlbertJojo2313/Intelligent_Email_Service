# Intelligent Email Service

This project is an email intelligence service that ingests mailbox data via Microsoft Graph API (or local mock endpoints) and transforms it into a structured, compressed format optimized for LLM context windows at scale.

Given a financial advisor's mailbox and a target client's (household's) email address, it retrieves historical correspondence, converts incoming payloads into a strongly-typed `EmailNode` domain model, resolves conversation threads using an **in-memory Directed Acyclic Graph (DAG)** via `ConversationReconstructor` strategies, extracts readable text attachments, cleans and compresses the content, and outputs streamlined JSON payloads containing a single `compressed_body` per subject ready for downstream LLM context injection.

---

## Key Features & Capabilities

- **Mailbox Ingestion**: Pulls email metadata, message bodies, and attachment descriptors via Microsoft Graph API (`MicrosoftGraphProvider` with Azure AD / `DefaultAzureCredential` & `@odata.nextLink` pagination).
- **Domain Model (`EmailNode`)**: Replaces raw dictionaries with strongly-typed `EmailNode` objects for end-to-end type safety and timezone-aware UTC dates.
- **In-Memory DAG Thread Reconstruction**: Uses `GraphConversationReconstructor` (Strategy pattern via `typing.Protocol`) to build an in-memory DAG from `In-Reply-To` and `Message-ID` headers, correctly ordering branching replies without message loss.
- **Attachment Processing**: Extracts uncompressed plain text content from readable text attachments (`.txt`, `.csv`, `.json`, `.md`, `.log`, `.yaml`, etc.) via `process_node_attachments()`.
- **Preprocessing & Cleaning**: Strips HTML tags, email signatures, disclaimers, and normalizes whitespace via `EmailCleaner` ([`docs/production/preprocessing.md`](docs/production/preprocessing.md)).
- **Unified Context Compression**: Applies character truncation and hybrid prompt compression via **LLMLingua** (`EmailCompressor`) to output a single top-level `compressed_body` per subject thread ([`docs/production/preprocessing.md`](docs/production/preprocessing.md)).
- **Domain Exception Handling**: Uniform error handling mapping HTTP status codes (401/403 auth, 404, 429 rate limits with retry-after handling) into domain exceptions (`EmailServiceError`, `EmailProviderError`, `ProviderRateLimitError`).
- **Environment-Driven Configuration**: Every parameter (`LOG_LEVEL`, `MAX_CONCURRENCY`, `GRAPH_API_BASE_URL`, `USE_LLMLINGUA`, `LLMLINGUA_MODEL`, `LLMLINGUA_DEVICE`) can be configured via `.env` or overridden programmatically.
- **End-to-End Driver Pipeline**: Programmatic API driver and executable CLI script (`process_client_emails` in [`pipeline.py`](src/intelligent_email_service/pipeline.py)).
- **Synthetic Email Generator**: Includes an asynchronous multi-client generator using the **NVIDIA AI Cloud / NIM API** (`deepseek-ai/deepseek-v4-flash`) and template fallbacks to build test datasets ([`docs/development/synthetic-generator.md`](docs/development/synthetic-generator.md)).

---

## 🟢 Integration Status: Fully Implemented

Core processing modules (`EmailRetrievalService`, `ThreadProcessor`, `EmailCleaner`, `EmailCompressor`, `process_client_emails`) and network provider integrations (`MicrosoftGraphProvider` and `MockGraphProvider`) are **fully implemented and covered by unit tests**.

To get started in under 5 minutes, follow the **[Getting Started Guide](docs/production/getting-started.md)**.

---

## Installation & Environment Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for fast, reliable Python package and dependency management using `pyproject.toml` and `uv.lock`.

### Prerequisites

- Python >= 3.11
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`)

### Setup & Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd email_service

# Install all dependencies (including dev tools) into virtual environment
uv sync --all-extras

# Copy environment variables template
cp .env.example .env
```

---

## Usage & Pipeline Integration

The primary entry point of the package is [`process_client_emails`](src/intelligent_email_service/pipeline.py), an `async` pipeline driver that orchestrates end-to-end processing across 5 distinct stages:

1. **Retrieval**: Queries the email provider for messages matching `advisor_id` and `client_id`.
2. **Grouping**: Normalizes subject lines and groups messages into subject-based threads.
3. **Thread Reconstruction**: Uses `ThreadProcessor` to reconstruct modified & full-quoted threads via in-memory DAG modeling.
4. **Attachment Extraction & Preprocessing**: Extracts text attachment content via `process_node_attachments()` and strips HTML noise/signatures via `EmailCleaner`.
5. **Context Compression**: Applies LLMLingua neural prompt compression or character truncation via `EmailCompressor`.

---

### 1. Basic Programmatic Usage

```python
import asyncio
from intelligent_email_service import (
    EmailQueryFilter,
    PipelineConfig,
    process_client_emails,
)


async def main():
    # 1. Define query filters
    query = EmailQueryFilter(
        advisor_id="advisor@example.com",
        client_id="jane.household@example-clients.com",
    )

    # 2. Pipeline automatically loads settings from .env
    config = PipelineConfig()

    # 3. Execute the pipeline
    compressed_threads = await process_client_emails(query=query, config=config)

    # 4. Inspect compressed outputs
    for thread in compressed_threads:
        print(f"Subject:         {thread.subject}")
        print(f"Conversation ID: {thread.conversation_id}")
        print(f"Total Messages:  {thread.total_messages}")
        print(f"Est. Tokens:     {thread.estimated_tokens}")
        print(f"Compressed Body:\n{thread.compressed_body}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 2. Executable CLI Driver

The module can also be executed directly as a CLI script via [`pipeline.py`](src/intelligent_email_service/pipeline.py). It processes matching emails and exports results to `compressed_threads.json`.

```bash
# Run with custom Advisor ID and Client ID
uv run python -m intelligent_email_service.pipeline "advisor@firm.com" "client@household.com"
```

---

## Architecture Overview

```
Connector Layer (MicrosoftGraphProvider [prod] / MockGraphProvider [dev])
       │
       ▼
Retrieval & Domain Conversion (EmailNode: ID / Message-ID / In-Reply-To / UTC received_at)
       │
       ▼
Thread Resolution (Strategy Layer: GraphConversationReconstructor In-Memory DAG)
       │
       ▼
Attachment Extraction & Cleaning (process_node_attachments / EmailCleaner HTML & Signatures)
       │
       ▼
Context Compression (EmailCompressor: LLMLingua & Truncation -> Single compressed_body)
       │
       ▼
Structured Payload Output (CompressedThread / LLM Context Prompt Payload)
```

See [`docs/production/architecture.md`](docs/production/architecture.md) for detailed data flow diagrams and component specifications.

---

## 📚 Documentation Directory

### 🟢 Production Environment
- **[Getting Started Guide](docs/production/getting-started.md)**: Setup, `.env` configuration, and pipeline quickstart.
- **[Architecture & System Design](docs/production/architecture.md)**: Data flow pipeline, configuration objects, DAG reconstruction, and component design.
- **[Output Schema & Data Structure](docs/production/data-structure.md)**: Streamlined output payload schema (`compressed_body`) and field specifications.
- **[Preprocessing & Compression](docs/production/preprocessing.md)**: Detailed cleaner, attachment processor, and compressor specifications.

### 🟡 Local Development & Testing
- **[Mock Setup & Local Development](docs/development/mock-setup.md)**: Guide for running Mockoon and local API simulation.
- **[Synthetic Email Generator](docs/development/synthetic-generator.md)**: Usage guide for synthetic email thread generation with NVIDIA LLM / Fallback templates.

---

## Testing & Quality Assurance

Run the test suite using `uv`:

```bash
uv run pytest
```
