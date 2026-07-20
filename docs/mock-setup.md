# Mock Graph API Setup & Local Development Guide

_Last updated: 2026-07-20_

> [!IMPORTANT]
> **Implementation Status**: Microsoft Graph API support is currently **just a planned outline and is not implemented yet**. The project currently relies entirely on a **Mockoon server** to simulate endpoints, and all specifications **may change**.

This document outlines the local mock environment for the Intelligent Email Service, enabling development and testing without live Microsoft Azure / Graph API credentials.

---

## Overview

Until production Microsoft Graph API credentials are configured, the service utilizes a mock provider (`MockGraphProvider`) and local HTTP endpoint simulation (e.g., via **Mockoon** or standard mock HTTP servers).

The mock environment consists of three components:
1. **Synthetic Email Generator** (`tools/generate_synthetic_emails.py`): Programmatically produces Graph API-formatted message JSON datasets.
2. **Mock Server Endpoint**: Hosts the generated dataset at `http://localhost:3000/v1.0/me/messages`.
3. **Mock Client Provider** (`intelligent_email_service.email_connectors.MockGraphProvider`): Asynchronously fetches email messages from the local mock server.

---

## Step-by-Step Setup Guide

### Step 1: Generate Synthetic Email Dataset

Generate a realistic mock email dataset containing threaded conversations using the synthetic generator tool:

```bash
# Generate 10 conversation threads across 5 synthetic clients
python3 tools/generate_synthetic_emails.py --conversations 10 --num-clients 5 --output mock_emails.json
```

For full options and configuration (such as using NVIDIA LLM vs template fallbacks), see [`docs/synthetic-generator.md`](./synthetic-generator.md).

### Step 2: Configure Mock Server (Mockoon)

1. Download and install [Mockoon](https://mockoon.com/) or run Mockoon CLI.
2. Create a new Mockoon environment listening on port `3000`.
3. Add a GET route: `/v1.0/me/messages`.
4. Set the response body type to `JSON` and paste the contents of `mock_emails.json` (or reference the file as a dynamic mock response).
5. Set HTTP Response Code to `200 OK` and Header `Content-Type: application/json`.
6. Start the environment server (`http://localhost:3000`).

---

## Code Usage Example

Use `EmailProviderManager` to instantiate the provider in Python:

```python
import asyncio
from intelligent_email_service.email_connectors import EmailProviderManager

async def main():
    # Instantiate the provider ('mock' connects to http://localhost:3000)
    provider = EmailProviderManager.create("mock")
    
    # Fetch messages from the mock endpoint
    messages = await provider.get_emails(user_id="advisor@example.com")
    print(f"Retrieved {len(messages)} messages from mock provider.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Mock Provider vs. Live Microsoft Graph API Comparison

| Feature | `MockGraphProvider` | `MicrosoftGraphProvider` (Live API) |
|---|---|---|
| **Endpoint Base URL** | `http://localhost:3000` | `https://graph.microsoft.com/v1.0` |
| **Authentication** | None (Local dev) | OAuth2 Bearer Tokens (MSAL / Azure AD) |
| **Message Retrieval** | `GET /v1.0/me/messages` | `GET /users/{user-id}/messages` or `/me/messages` |
| **OData Search / Filtering** | Full list in memory | `$filter=contains(singleValueExtendedProperties/...)` |
| **Pagination** | Single response payload | Handled via `@odata.nextLink` tokens |
| **Delta Sync** | Not implemented in mock | Handled via `@odata.deltaLink` |

---

## Transitioning to Live Microsoft Graph API

When production Microsoft Graph API access is granted:
1. Set up Azure AD App Registration with required scopes (`Mail.Read`, `Mail.ReadBasic`).
2. Configure credentials (`CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`) in `.env`.
3. Switch provider creation from `"mock"` to `"microsoft"` in `EmailProviderManager`:

```python
provider = EmailProviderManager.create("microsoft")
```
