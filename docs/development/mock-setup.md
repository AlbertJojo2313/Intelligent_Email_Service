# Mock Graph API Setup & Local Development Guide

_Last updated: August 12, 2026_

This document outlines the local mock environment for the Intelligent Email Service, enabling offline development and testing without live Microsoft Azure / Graph API credentials.

---

## Overview

For local offline development (`APP_ENV=dev`), the service utilizes `MockGraphProvider` and local HTTP endpoint simulation (via **Mockoon** or standard HTTP mock servers).

The mock environment consists of three components:
1. **Synthetic Email Generator** (`tools/generate_synthetic_emails.py`): Programmatically produces Graph API-formatted message JSON datasets.
2. **Mockoon Server**: Exposes endpoints to simulate advisors and Graph API mailbox resources:
    - **Users Endpoint**: Retrieves advisors `http://localhost:3000/v1.0/users`.
    - **Advisor Info Endpoint**: Retrieves advisor info `{BASE_URL}/v1.0/users/:user_id`.
    - **Mailbox Endpoint**: Retrieves corresponding messages `{BASE_URL}/v1.0/users/:user_id/messages`.
3. **Mock Client Provider** (`intelligent_email_service.email_connectors.MockGraphProvider`): Asynchronously fetches email messages from the local mock server (`MOCK_SERVER_URL`).

---

## Step-by-Step Setup Guide

### Step 1: Generate Synthetic Email Dataset

Generate a mock email dataset containing threaded conversations using the synthetic generator tool:

```bash
# Generate 10 conversation threads across 5 synthetic clients
uv run python tools/generate_synthetic_emails.py --conversations 10 --num-clients 5 --output mock_emails.json
```

For full options (such as using NVIDIA LLM vs template fallbacks, or selecting `--thread-format full_quoted` / `modified`), see [`synthetic-generator.md`](./synthetic-generator.md).

### Step 2: Configure Mock Server (Mockoon)

1. Download and install [Mockoon](https://mockoon.com/) or run Mockoon CLI.
2. Create a new Mockoon environment listening on port `3000`.
3. Add a GET route: `/v1.0/users/:user_id/messages`.
4. Set response body type to `JSON` and paste contents of `mock_emails.json`.
5. Set HTTP Response Code to `200 OK` and Header `Content-Type: application/json`.
6. Start the environment server (`http://localhost:3000`).

---

## Code Usage Example

Use `EmailProviderManager` and configuration objects for local mock workflow execution:

```python
import asyncio
from intelligent_email_service import (
    CleanerConfig,
    CompressorConfig,
    EmailCleaner,
    EmailCompressor,
    EmailProviderManager,
    EmailRetrievalService,
    ThreadProcessor,
)


async def main():
    advisor_id = "tst_ad-001"
    client_id = "jessica.ayala@example.com"

    # 1. Instantiate provider ('mock' connects to MOCK_SERVER_URL, default http://localhost:3000)
    provider = EmailProviderManager.create(provider_type="mock", app_env="dev")
    retrieval_service = EmailRetrievalService(provider=provider)
    cleaner = EmailCleaner(config=CleanerConfig(strip_signatures=True))
    compressor = EmailCompressor(config=CompressorConfig(recent_full_count=2))

    # 2. Retrieve client email groups
    subject_groups = await retrieval_service.get_client_email_groups(
        advisor_id=advisor_id, client_id=client_id
    )

    # 3. Process, clean, and compress threads
    processor = ThreadProcessor(
        provider=provider,
        user_id=advisor_id,
        client_id=client_id,
    )

    for group in subject_groups.values():
        thread = await processor.process_subject_group(group)
        if not thread:
            continue

        thread.messages = await cleaner.clean_messages_async(thread.messages)
        compressed = compressor.compress_processed_thread(thread)

        print(
            f"Subject: {compressed.subject} | "
            f"Format: {compressed.format} | "
            f"Messages: {compressed.total_messages} | "
            f"Est. Tokens: {compressed.estimated_tokens}"
        )


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Mock Provider vs. Live Microsoft Graph API Comparison

| Feature | `MockGraphProvider` | `MicrosoftGraphProvider` (Live API) |
|---|---|---|
| **Endpoint Base URL** | `http://localhost:3000` (`MOCK_SERVER_URL`) | `https://graph.microsoft.com/v1.0` (`GRAPH_API_BASE_URL`) |
| **Authentication** | None (Local dev) | OAuth2 Bearer Tokens (Azure AD / `DefaultAzureCredential`) |
| **Message Retrieval** | `GET /v1.0/users/{user-id}/messages` | `GET /users/{user-id}/messages` |
| **Filtering & Retry** | In-memory date filter | Tenacity exponential retry logic for HTTP 429 rate limits |
| **Pagination** | Single response payload | Auto-paginated via `@odata.nextLink` tokens |
| **Attachments** | Simulates attachment metadata | Binary attachment fetching via `get_attachment_bytes()` |

---

## Transitioning to Live Microsoft Graph API

To switch to production Microsoft Graph API access:
1. Register Azure AD App with `Mail.Read` or `Mail.ReadBasic` permissions.
2. Set credentials (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`) in `.env`.
3. Set `APP_ENV=test_prod` or `APP_ENV=production` in `.env`.
