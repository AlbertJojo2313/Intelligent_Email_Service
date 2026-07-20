# Synthetic Email Generator

The synthetic email generator is a tool designed to simulate advisor-client email conversations. It programmatically constructs mock email datasets that match the schema expected by the Microsoft Graph API connector.

The tool utilizes **OpenRouter** (for realistic, LLM-generated conversation bodies) combined with **Faker** and rule-based constraints (for deterministic headers, IDs, and chronological dates). It also includes a rule-based template fallback mechanism if OpenRouter is not configured or fails.

---

## Setup & Configuration

### 1. Install Dependencies

Before running the generator, ensure the required Python packages are installed:

```bash
pip install faker python-dotenv httpx
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` in the root of the project:

```bash
cp .env.example .env
```

Inside `.env`, configure the OpenRouter connection parameters:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3-8b-instruct:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### 3. Customize Topics

You can modify the conversation topics in [`tools/topics.json`](../tools/topics.json). The generator selects topics randomly from this list to guide the LLM's drafting context (e.g. portfolio rebalancing, IRA contributions, quarterly scheduling).

---

## Usage

Run the generator script using Python:

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
| `--client-email` | Email address of the client (fallback for single-client mode) | `client@example.com` |
| `--client-name` | Name of the client (fallback for single-client mode) | `Sarah Client` |
| `--num-clients` | Number of distinct clients to dynamically generate in the pool | `5` |
| `--client-pool` | Path to a JSON file containing a predefined list of clients | `None` |
| `--openrouter-key` | OpenRouter API key | `$OPENROUTER_API_KEY` |
| `--model` | OpenRouter model to invoke | `$OPENROUTER_MODEL` (or `meta-llama/llama-3-8b-instruct:free`) |
| `--url` | Base URL of the OpenRouter API | `$OPENROUTER_BASE_URL` (or `https://openrouter.ai/api/v1`) |

### Examples

**Generate a mailbox for a pool of 5 clients:**

```bash
python3 tools/generate_synthetic_emails.py --conversations 10 --num-clients 5 --output docs/mock_emails.json
```

**Generate a mailbox for predefined specific clients loaded from a file:**

```bash
python3 tools/generate_synthetic_emails.py --conversations 8 --client-pool path/to/clients.json --output docs/mock_emails.json
```

The client pool JSON format should be:

```json
[
  {"name": "Alice Smith", "email": "alice.smith@example.com"},
  {"name": "Bob Jones", "email": "bob.jones@example.com"}
]
```

---

## Features

### 1. Concurrent Generation

The script uses `asyncio.gather` to send LLM requests to OpenRouter concurrently, significantly speeding up generation times for large datasets.

### 2. Chronological Threading

Timestamps (`created_datetime`, `last_modifiedDateTime`, `recievedDateTime`, and `sentDateTime`) are guaranteed to be in strict chronological order for each reply in a thread (spaced by several hours/days).

### 3. Unmodified vs. Modified Threads

To test the email parser's thread-resolution logic:
* **Unmodified threads** (50% probability): The latest message in the thread contains the full trailing quoted history of all previous messages in standard email format (`On [Date], [Sender] wrote: > ...`).

* **Modified threads** (50% probability): Messages are saved individually with clean bodies. The downstream system must fetch all messages sharing the same `conversation_id` and merge them chronologically.

---

## Output JSON Schema

The generated JSON file mirrors the Microsoft Graph API `/me/messages` list response format, wrapped in a `"value"` array:

```json
{
  "value": [
    {
      "id": "AAMkAG...",
      "created_datetime": "2026-07-16T18:00:00Z",
      "last_modifiedDateTime": "2026-07-16T18:00:00Z",
      "categories": [],
      "recievedDateTime": "2026-07-16T18:00:00Z",
      "sentDateTime": "2026-07-16T18:00:00Z",
      "hasAttachemnts": false,
      "conversation_id": "807e0e68-...",
      "message_id": "AAMkAG...",
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
