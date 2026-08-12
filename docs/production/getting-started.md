# Getting Started Guide

_Intelligent Email Service — Production & Integration Quickstart_

Welcome to the Intelligent Email Service! This guide will help you set up, configure, and execute the email ingestion and prompt context reduction pipeline in **under 5 minutes**.

---

## 📋 Prerequisites

- **Python**: `>= 3.11`
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`)
- **Credentials** (For Live Production mode): Azure AD App Registration with `Mail.Read` or `Mail.ReadBasic` permissions.

---

## ⚡ 1. Installation & Environment Setup

### Clone & Install Dependencies

```bash
# Clone repository
git clone <repository-url>
cd email_service

# Install dependencies into virtual environment using uv
uv sync --all-extras
```

### Configure Environment Variables

Copy the template `.env.example` file to `.env`:

```bash
cp .env.example .env
```

Open `.env` and configure your target environment profile:

```ini
# Profile: 'dev' (uses Mockoon mock server) or 'test_prod' / 'production' (uses Azure AD Microsoft Graph API)
APP_ENV=dev

# Azure AD Credentials (Required for 'test_prod' / 'production')
AZURE_TENANT_ID=your_tenant_id_here
AZURE_CLIENT_ID=your_client_id_here
AZURE_CLIENT_SECRET=your_client_secret_here

# Service Tuning
LOG_LEVEL=INFO
MAX_CONCURRENCY=10
```

---

## 🚀 2. Running Your First Pipeline Execution

### Option A: Programmatic Integration (Python API)

You can invoke the end-to-end pipeline driver directly in your application:

```python
import asyncio
from intelligent_email_service import (
    EmailQueryFilter,
    PipelineConfig,
    process_client_emails,
)


async def main():
    # 1. Define query target (Advisor ID & Client Email)
    query = EmailQueryFilter(
        advisor_id="advisor@example.com",
        client_id="client@example.com",
    )

    # 2. Pipeline automatically loads configuration from .env
    config = PipelineConfig()

    # 3. Execute pipeline (automatically selects provider based on APP_ENV)
    compressed_threads = await process_client_emails(query=query, config=config)

    # 4. Inspect outputs
    for thread in compressed_threads:
        print(f"\n--- Subject: {thread.subject} ---")
        print(f"Format:            {thread.format}")
        print(f"Total Messages:    {thread.total_messages}")
        print(f"Est. Tokens:       {thread.estimated_tokens}")
        print(f"Compressed Body:\n{thread.compressed_body}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Option B: Command Line Interface (CLI)

Execute the built-in driver CLI script:

```bash
# Process emails for advisor 'advisor@example.com' & client 'client@example.com'
uv run python -m intelligent_email_service.pipeline advisor@example.com client@example.com
```

The output will be displayed in stdout and saved to `compressed_threads.json`.

---

## 🔄 3. Provider Modes: Local Mock vs. Live Microsoft Graph API

The service uses `EmailProviderManager` to instantiate the appropriate provider based on `APP_ENV`:

| Environment (`APP_ENV`) | Provider Used | Data Source |
| :--- | :--- | :--- |
| **`dev`** | `MockGraphProvider` | Local Mockoon HTTP endpoint (`MOCK_SERVER_URL`, default `http://localhost:3000`) |
| **`test_prod` / `production`** | `MicrosoftGraphProvider` | Live Microsoft Graph API (`https://graph.microsoft.com/v1.0`) via Azure AD OAuth |

---

## 🧪 4. Testing & Verification

Run the test suite to verify project health:

```bash
# Run pytest unit & integration tests
uv run pytest

# Check code formatting & linting rules
uv run ruff check .
```

---

## 📚 Next Steps

- **[System Architecture](architecture.md)** — Learn how DAG thread reconstruction and topological ordering work.
- **[Data Schemas](data-structure.md)** — Inspect `EmailNode` and `CompressedThread` payload definitions.
- **[Preprocessing & Compression](preprocessing.md)** — Understand HTML cleaning, signature stripping, and LLMLingua compression rules.
