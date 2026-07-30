# Intelligent Email Service

This project is an email intelligence service that ingests mailbox data via the Microsoft Graph API (or local mock endpoints) and transforms it into a structured, compressed format optimized for LLM prompting at scale.

Given a financial advisor's mailbox and a target client's (household's) email address, it retrieves historical correspondence, filters and groups it, resolves conversation threads, cleans and compresses the content, and outputs structured JSON payloads ready for downstream LLM context injection.

---

## Key Features & Capabilities

- **Mailbox Ingestion**: Pulls email metadata, message bodies, and attachment descriptors via Microsoft Graph API abstraction (`EmailProvider`).
- **Domain Exception Handling**: Uniform error handling mapping HTTP status codes (401/403, 404, 429 rate limits) into domain exceptions (`EmailServiceError`, `EmailProviderError`, `ProviderRateLimitError`).
- **Thread Resolution**: Handles both **unmodified threads** (containing inline quoted history) and **modified threads** (split individual messages sharing a `conversation_id`) via `ThreadProcessor`.
- **Preprocessing & Cleaning**: Strips HTML tags, email signatures, disclaimers, and normalizes whitespace via `EmailCleaner` ([`docs/preprocessing.md`](docs/preprocessing.md)).
- **Context Compression**: Applies rule-based character truncation and hybrid prompt compression via **LLMLingua** (`EmailCompressor`) to minimize token consumption while keeping recent context intact ([`docs/preprocessing.md`](docs/preprocessing.md)).
- **Synthetic Email Generator**: Includes an asynchronous multi-client generator using the **NVIDIA AI Cloud / NIM API** (`deepseek-ai/deepseek-v4-flash`) and template fallbacks to build Graph API-compliant test datasets ([`docs/synthetic-generator.md`](docs/synthetic-generator.md)).

---

## ⚠️ Current Integration Status: Mocked (Planned Graph API Outline)

> [!IMPORTANT]
> The current architecture for Microsoft Graph API support is **a planned outline (`MicrosoftGraphProvider`) and is not implemented for live endpoints yet**. Currently, the project uses a **Mockoon server** (`MockGraphProvider`) to simulate the API endpoints (`GET /v1.0/users/{user-id}/messages`), allowing offline development. Core processing modules (`EmailRetrievalService`, `ThreadProcessor`, `EmailCleaner`, `EmailCompressor`) are fully implemented.

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

Alternatively, if managing virtual environments manually:

```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install package in editable mode with dev dependencies
uv pip install -e ".[dev]"
```

---

## Architecture Overview

```
Connector Layer (EmailProvider / MockGraphProvider / MicrosoftGraphProvider Outline)
       │
       ▼
Exception Layer (Domain Exceptions: EmailProviderError / ProviderRateLimitError)
       │
       ▼
Thread Grouping & Resolution (ThreadProcessor: Unmodified vs Modified email threads)
       │
       ▼
Preprocessing & Cleaning (EmailCleaner: HTML Stripping / Signature Removal)
       │
       ▼
Context Compression (EmailCompressor: LLMLingua & Character Truncation)
       │
       ▼
Structured Payload Output (CompressedThread / LLM Context Prompt Payload)
```

See [`docs/architecture.md`](docs/architecture.md) for detailed data flow diagrams and component design specifications.

---

## Documentation Quick Links

- [**Architecture & System Design**](docs/architecture.md): Data flow pipeline, identity model, exception layer, and component interactions.
- [**Mock Setup & Local Development**](docs/mock-setup.md): Guide for running Mockoon and local API simulation.
- [**Preprocessing & Compression**](docs/preprocessing.md): Detailed cleaner and compressor module specifications.
- [**Synthetic Email Generator**](docs/synthetic-generator.md): Usage guide for synthetic email thread generation with NVIDIA LLM / Fallback templates.

---

## Testing & Quality Assurance

Run the test suite using `uv`:

```bash
uv run pytest
```

Or inside an activated virtual environment:

```bash
pytest
```
