# Intelligent Email Service

This project is an email intelligence service that ingests mailbox data via the Microsoft Graph API (or local mock endpoints) and transforms it into a structured, compressed format optimized for LLM prompting at scale.

Given a financial advisor's mailbox and a target client's (household's) email address, it retrieves historical correspondence, converts incoming payloads into a strongly-typed `EmailNode` domain model, resolves conversation threads using an **in-memory Directed Acyclic Graph (DAG)** via `ConversationReconstructor` strategies, cleans and compresses the content, and outputs streamlined JSON payloads containing a single `compressed_body` per subject ready for downstream LLM context injection.

---

## Key Features & Capabilities

- **Mailbox Ingestion**: Pulls email metadata, message bodies, and attachment descriptors via Microsoft Graph API abstraction (`EmailProvider`).
- **Domain Model (`EmailNode`)**: Replaces raw dictionaries with strongly-typed `EmailNode` objects for end-to-end type safety.
- **In-Memory DAG Thread Reconstruction**: Uses `GraphConversationReconstructor` (Strategy pattern via `typing.Protocol`) to build an in-memory DAG from `In-Reply-To` and `Message-ID` headers, correctly ordering branching replies.
- **Preprocessing & Cleaning**: Strips HTML tags, email signatures, disclaimers, and normalizes whitespace via `EmailCleaner` ([`docs/preprocessing.md`](docs/preprocessing.md)).
- **Unified Context Compression**: Applies character truncation and hybrid prompt compression via **LLMLingua** (`EmailCompressor`) to output a single top-level `compressed_body` per subject thread ([`docs/preprocessing.md`](docs/preprocessing.md)).
- **Domain Exception Handling**: Uniform error handling mapping HTTP status codes (401/403, 404, 429 rate limits) into domain exceptions (`EmailServiceError`, `EmailProviderError`, `ProviderRateLimitError`).
- **Configuration Object Pattern**: Uses typed dataclass configuration objects (`EmailQueryFilter`, `PipelineConfig`, `CleanerConfig`, `CompressorConfig`) for modular setting management.
- **End-to-End Driver Pipeline**: Programmatic API driver and executable CLI script (`process_client_emails` in [`pipeline.py`](src/intelligent_email_service/pipeline.py)).
- **Synthetic Email Generator**: Includes an asynchronous multi-client generator using the **NVIDIA AI Cloud / NIM API** (`deepseek-ai/deepseek-v4-flash`) and template fallbacks to build Graph API-compliant test datasets ([`docs/synthetic-generator.md`](docs/synthetic-generator.md)).

---

## ⚠️ Current Integration Status: Mocked (Planned Graph API Outline)

> [!IMPORTANT]
> The current architecture for Microsoft Graph API support is **a planned outline (`MicrosoftGraphProvider`) and is not implemented for live endpoints yet**. Currently, the project uses a **Mockoon server** (`MockGraphProvider`) to simulate the API endpoints (`GET /v1.0/users/{user-id}/messages`), allowing offline development. Core processing modules (`EmailRetrievalService`, `ThreadProcessor`, `EmailCleaner`, `EmailCompressor`, `process_client_emails`) are fully implemented.

For details on local mock server configuration, synthetic dataset generation, and the planned transition to Microsoft Graph API access, see [`docs/mock-setup.md`](docs/mock-setup.md).

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
```

---

## Running the Pipeline

### 1. Programmatic Usage (Python)

```python
import asyncio
from intelligent_email_service import (
    EmailQueryFilter,
    MockGraphProvider,
    PipelineConfig,
    process_client_emails,
)

async def main():
    provider = MockGraphProvider(base_url="http://localhost:3000")

    query = EmailQueryFilter(
        advisor_id="tst_ad-001",
        client_id="jane.household@example-clients.com",
    )
    config = PipelineConfig()

    compressed_threads = await process_client_emails(
        query=query,
        config=config,
        provider=provider,
    )

    for thread in compressed_threads:
        print(f"Subject: {thread.subject} | Format: {thread.format} | Tokens: {thread.estimated_tokens}")
        print(f"Compressed Body:\n{thread.compressed_body}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Executable CLI Command

Run `pipeline.py` directly from the command line:

```bash
# Run with default arguments
uv run python -m intelligent_email_service.pipeline

# Run with custom Advisor ID and Client ID
uv run python -m intelligent_email_service.pipeline "advisor@firm.com" "client@household.com"
```

---

## Architecture Overview

```
Connector Layer (EmailProvider / MockGraphProvider / MicrosoftGraphProvider Outline)
       │
       ▼
Retrieval & Domain Conversion (EmailNode: ID / Message-ID / In-Reply-To headers)
       │
       ▼
Thread Resolution (Strategy Layer: GraphConversationReconstructor In-Memory DAG)
       │
       ▼
Preprocessing & Cleaning (EmailCleaner: HTML Stripping / Signature Removal)
       │
       ▼
Context Compression (EmailCompressor: LLMLingua & Truncation -> Single compressed_body)
       │
       ▼
Structured Payload Output (CompressedThread / LLM Context Prompt Payload)
```

See [`docs/architecture.md`](docs/architecture.md) for detailed data flow diagrams and component design specifications.

---

## Documentation Quick Links

- [**Architecture & System Design**](docs/architecture.md): Data flow pipeline, configuration objects, identity model, in-memory DAG reconstruction, and component interactions.
- [**Output Schema & Data Structure**](docs/data-structure.md): Streamlined output payload schema (`compressed_body`) and field specifications.
- [**Mock Setup & Local Development**](docs/mock-setup.md): Guide for running Mockoon and local API simulation.
- [**Preprocessing & Compression**](docs/preprocessing.md): Detailed cleaner and compressor module specifications.
- [**Synthetic Email Generator**](docs/synthetic-generator.md): Usage guide for synthetic email thread generation with NVIDIA LLM / Fallback templates.

---

## Testing & Quality Assurance

Run the test suite using `uv`:

```bash
uv run pytest
```
