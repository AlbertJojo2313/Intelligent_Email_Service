# Local Docker Development & Testing Guide

_Intelligent Email Service — Local Setup using Docker Compose_

This guide provides step-by-step instructions for running and testing the Intelligent Email Service locally using **Docker Compose** with mock endpoints (no Azure credentials required).

---

## 📋 Prerequisites

- **Docker Desktop** / **Docker Engine** (`>= 24.0.0`)
- **Docker Compose** (`>= 2.20.0`)

---

## 🛠️ Step-by-Step Local Docker Setup

### Step 1: Clone Repository & Configure Environment

```bash
# 1. Clone the repository
git clone <repository-url>
cd email_service

# 2. Copy the environment configuration template
cp .env.example .env
```

Ensure your `.env` (or `.env.dev`) has local development settings:

```ini
APP_ENV=dev
EMAIL_PROVIDER=mock
MOCK_SERVER_URL=http://host.docker.internal:3000
LOG_LEVEL=INFO
USE_LLMLINGUA=false
```

---

### Step 2: Start Mockoon & Launch Docker Container

1. **Start Mockoon (Required for `POST /compress` in Dev Mode)**:
   Follow the **[Mock Setup Guide](mock-setup.md)** to start your Mockoon mock server on port `3000` with sample email data.

2. **Start the Development Container**:
   ```bash
   docker compose up app-dev --build
   ```

The service will start and bind to `http://localhost:8000`.

> 💡 **Note on Testing**:
> * `GET /health` and Swagger UI (`/docs`) work immediately.
> * `POST /compress` requires Mockoon running on port `3000` (in `dev` mode) or Azure credentials (in `test_prod` mode).
> * The test suite (`docker compose run --rm app-dev pytest`) uses internal fixtures and does **not** require Mockoon.

---

### Step 3: Verify & Test Local Endpoints

#### 1. Interactive Swagger UI
Open your browser to:
👉 **`http://localhost:8000/docs`**

#### 2. Health Check
```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "env": "dev"
}
```

#### 3. Test Email Compression (`POST /compress`)
```bash
curl -X POST http://localhost:8000/compress \
  -H "Content-Type: application/json" \
  -d '{
    "advisor_id": "tst_ad-001",
    "client_id": "jane.household@example-clients.com"
  }'
```

**Expected Response Structure:**
```json
[
  {
    "subject": "Portfolio Review Q2",
    "conversation_id": "conv-abc-123",
    "format": "modified",
    "total_messages": 2,
    "compressed_body": "[jane.household@example-clients.com] Hi, can we review the portfolio allocation?\n\n---\n\n[advisor@firm.com] Hello Jane, I have reviewed the portfolio...",
    "sender": "advisor@firm.com",
    "senders": ["jane.household@example-clients.com", "advisor@firm.com"],
    "participants": ["advisor@firm.com", "jane.household@example-clients.com"],
    "attachments_summary": [],
    "estimated_tokens": 42,
    "used_llmlingua": false
  }
]
```

---

### Step 4: Run Automated Tests Inside Docker

To run the full 69-test suite inside the Docker container:

```bash
docker compose run --rm app-dev pytest
```

---

### Step 5: Stop the Container

To stop the running container:
```bash
docker compose down
```
