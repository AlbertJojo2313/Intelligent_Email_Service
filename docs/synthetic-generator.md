# Synthetic Email Generator

_Last updated: 2026-07-27_

> [!IMPORTANT]
> **Implementation Status**: Microsoft Graph API support is currently **just a planned outline and is not implemented yet**. The generator constructs datasets to feed a **Mockoon server** simulating the endpoints, and specs **may change**.

The Synthetic Email Generator is a utility tool designed to simulate advisor-client email conversations. It programmatically constructs mock email datasets matching the schema expected by the Microsoft Graph API connector.

The tool utilizes the **NVIDIA AI Cloud / NIM API** (for realistic, LLM-generated conversation bodies) combined with **Faker** and rule-based constraints (for deterministic headers, IDs, and chronological timestamps). It includes a rule-based template fallback mechanism (`FallbackGenerator`) if an NVIDIA API key is not configured or if an API call fails.

---

## Architecture & Code Structure

The generator modules are located in `tools/synthetic_generator/`:

```
tools/
├── generate_synthetic_emails.py   # CLI entry point script
├── topics.json                    # Conversation topics configuration
└── synthetic_generator/
    ├── __init__.py                # Package exports
    ├── client_pool.py             # ClientPool generator (Faker / JSON loader)
    ├── fallback_generator.py      # Local template fallback generator
    ├── generator.py               # SyntheticEmailGenerator orchestrator
    ├── llm_client.py              # NvidiaClient HTTP client (OpenAI SDK integration)
    └── models.py                 # ClientProfile data class
```

---

## Setup & Configuration

### 1. Install Dependencies

Ensure project dependencies are installed (using `uv` or `pip`):

```bash
pip install faker python-dotenv httpx openai tenacity
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` in the root of the project:

```bash
cp .env.example .env
```

Inside `.env`, configure the NVIDIA API parameters:

```env
NVIDIA_API_KEY=nvapi-your_nvidia_api_key_here
NVIDIA_MODEL=deepseek-ai/deepseek-v4-flash
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

> **Note**: If `NVIDIA_API_KEY` is omitted, the tool automatically falls back to local template-based generation (`FallbackGenerator`) without throwing errors.

### 3. Customize Topics

You can modify conversation topics in [`tools/topics.json`](../tools/topics.json). The generator selects topics randomly from this list to guide LLM thread drafting (e.g., portfolio rebalancing, IRA contributions, onboarding documents).

---

## Usage

Run the generator CLI script from the project root:

```bash
python3 tools/generate_synthetic_emails.py [options]
```

### CLI Arguments

| Argument | Description | Default |
|---|---|---|
| `--output` | File path to write the generated JSON dataset | `mock_emails.json` |
| `--conversations` | Number of conversation threads to generate | `5` |
| `--advisor-email` | Email address of the financial advisor | `advisor@example.com` |
| `--advisor-name` | Name of the financial advisor | `John Advisor` |
| `--client-email` | Email address of the client (for single-client fallback) | `client@example.com` |
| `--client-name` | Name of the client (for single-client fallback) | `Sarah Client` |
| `--num-clients` | Number of distinct clients to dynamically generate in the pool | `5` |
| `--client-pool` | Path to a custom JSON file containing a predefined client pool | `None` |
| `--nvidia-key` | NVIDIA API key | `$NVIDIA_API_KEY` |
| `--model` | NVIDIA NIM model to invoke | `$NVIDIA_MODEL` (`deepseek-ai/deepseek-v4-flash`) |
| `--url` | Base URL of the NVIDIA API | `$NVIDIA_BASE_URL` (`https://integrate.api.nvidia.com/v1`) |

---

## Usage Examples

**Generate a dataset with 10 conversation threads across a pool of 5 synthetic clients:**

```bash
python3 tools/generate_synthetic_emails.py --conversations 10 --num-clients 5 --output mock_emails.json
```

**Generate threads for predefined specific clients loaded from a JSON file:**

```bash
python3 tools/generate_synthetic_emails.py --conversations 8 --client-pool path/to/clients.json --output mock_emails.json
```

The client pool JSON format should be structured as a JSON array of objects:

```json
[
  {"name": "Alice Smith", "email": "alice.smith@example.com"},
  {"name": "Bob Jones", "email": "bob.jones@example.com"}
]
```

---

## Features

### 1. Concurrent Async Generation

The generator uses `asyncio.gather` to execute LLM API requests concurrently, significantly speeding up dataset generation.

### 2. Strict Chronological Timestamps

Timestamps (`createdDateTime`, `lastModifiedDateTime`, `receivedDateTime`, and `sentDateTime`) are guaranteed to be in strict chronological order for each reply within a thread (spaced by configurable hour intervals).

### 3. Unmodified vs. Modified Threads

To validate the email parser's thread-resolution logic:
- **Unmodified threads** (50% probability): The latest message in the thread contains the full trailing quoted history of all previous messages in standard format (`On [Date], [Sender] wrote: > ...`).
- **Modified threads** (50% probability): Messages are stored as individual clean bodies sharing a common `conversation_id`.

---

## Output JSON Schema

The generated JSON file mirrors the Microsoft Graph API `/v1.0/users/{user_id}/messages` list response format wrapped in a `"value"` array:

```json
{
  "value": [
    {
      "id": "AAMkAGa1b2c3d4e5f6",
      "createdDateTime": "2026-07-16T18:00:00Z",
      "lastModifiedDateTime": "2026-07-16T18:00:00Z",
      "categories": [],
      "receivedDateTime": "2026-07-16T18:00:00Z",
      "sentDateTime": "2026-07-16T18:00:00Z",
      "hasAttachments": false,
      "conversation_id": "807e0e68-1234-5678-9abc-def012345678",
      "message_id": "AAMkAGa1b2c3d4e5f6",
      "subject": "Portfolio Rebalancing",
      "body": {
        "content_type": "html",
        "content": "Hi John Advisor,\n\nI was looking at my portfolio..."
      },
      "sender": {
        "emailAddress": {
          "name": "Sarah Client",
          "address": "client@example.com"
        }
      },
      "from": {
        "emailAddress": {
          "name": "Sarah Client",
          "address": "client@example.com"
        }
      },
      "toRecipients": [
        {
          "emailAddress": {
            "name": "John Advisor",
            "address": "advisor@example.com"
          }
        }
      ]
    }
  ]
}
```
