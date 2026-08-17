# Intelligent Email Service

This project is an email intelligence service that ingests mailbox data via Microsoft Graph API (or local mock endpoints) and transforms it into a structured, compressed format optimized for LLM context windows at scale.



---

## Key Features & Capabilities

- **FastAPI REST Microservice**: Provides high-throughput async endpoints (`/compress`, `/health`, `/docs`) for on-demand LLM context preparation.
- **Mailbox Ingestion**: Pulls email metadata, message bodies, and attachment descriptors via Microsoft Graph API (`MicrosoftGraphProvider` with Azure AD / `DefaultAzureCredential` & `@odata.nextLink` pagination).
- **Domain Model (`EmailNode`)**: Replaces raw dictionaries with strongly-typed `EmailNode` objects for end-to-end type safety and timezone-aware UTC dates.
- **In-Memory DAG Thread Reconstruction**: Uses `GraphConversationReconstructor` (Strategy pattern via `typing.Protocol`) to build an in-memory DAG from `In-Reply-To` and `Message-ID` headers, correctly ordering branching replies without message loss.
- **Attachment Processing**: Extracts uncompressed plain text content from readable text attachments (`.txt`, `.csv`, `.json`, `.md`, `.log`, `.yaml`, etc.) via `process_node_attachments()`.
- **Preprocessing & Cleaning**: Strips HTML tags, email signatures, disclaimers, and normalizes whitespace via `EmailCleaner` ([`docs/production/preprocessing.md`](docs/production/preprocessing.md)).
- **Unified Context Compression**: Applies character truncation and hybrid prompt compression via **LLMLingua** (`EmailCompressor`) to output a single top-level `compressed_body` per subject thread ([`docs/production/preprocessing.md`](docs/production/preprocessing.md)).
- **Domain Exception Handling**: Uniform error handling mapping HTTP status codes (401/403 auth, 404, 429 rate limits with retry-after handling) into domain exceptions (`EmailServiceError`, `EmailProviderError`, `ProviderRateLimitError`).
- **Environment-Driven Configuration**: Every parameter (`LOG_LEVEL`, `MAX_CONCURRENCY`, `GRAPH_API_BASE_URL`, `USE_LLMLINGUA`, `LLMLINGUA_MODEL`, `LLMLINGUA_DEVICE`) can be configured via `.env` or overridden programmatically.
- **Synthetic Email Generator**: Includes an asynchronous multi-client generator using the **NVIDIA AI Cloud / NIM API** (`deepseek-ai/deepseek-v4-flash`) and template fallbacks to build test datasets (*Note: Verify the LLM model is available on the NVIDIA AI platform*) ([`docs/development/synthetic-generator.md`](docs/development/synthetic-generator.md)).

---

## 🛠️ Step-by-Step Guide: Running & Deploying to Azure via Docker

Follow these steps to build, run, and deploy the service for Microsoft Azure using Docker.

> 💡 **Offline / Local Mock Testing**: If you want to run the service locally without Azure credentials using mock data, follow the **[Local Docker Development Guide](docs/development/local-docker-setup.md)**.

---

### Step 1: Clone Repository & Configure Azure Environment

```bash
# 1. Clone the repository
git clone <repository-url>
cd email_service

# 2. Copy the environment configuration template
cp .env.example .env
```

Configure your Azure AD credentials in `.env` (or `.env.test_prod`):

```ini
APP_ENV=test_prod
EMAIL_PROVIDER=microsoft
GRAPH_API_BASE_URL=https://graph.microsoft.com/v1.0
AZURE_TENANT_ID=<your-azure-tenant-id>
AZURE_CLIENT_ID=<your-azure-client-id>
AZURE_CLIENT_SECRET=<your-azure-client-secret>
LOG_LEVEL=INFO
USE_LLMLINGUA=false
```

---

### Step 2: Build & Start the Production Container

Start the service container using Docker Compose:

```bash
docker compose up app-prod --build
```

The container builds using the lean [Dockerfile.prod](Dockerfile.prod) and starts Uvicorn bound to port `8001` (mapped to container port `8000`).

---

### Step 3: Verify & Test the Endpoints

Once the container is running:

#### 1. Interactive Swagger UI
Open your browser to:
👉 **`http://localhost:8001/docs`**

#### 2. Test the Health Endpoint
```bash
curl http://localhost:8001/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "env": "test_prod"
}
```

#### 3. Test Email Compression (`POST /compress`)
Send a test request with an advisor and client email:
```bash
curl -X POST http://localhost:8001/compress \
  -H "Content-Type: application/json" \
  -d '{
    "advisor_id": "advisor@firm.com",
    "client_id": "client@household.com"
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
    "compressed_body": "[client@household.com] Hi, can we review the portfolio allocation?\n\n---\n\n[advisor@firm.com] Hello Jane, I have reviewed the portfolio...",
    "sender": "advisor@firm.com",
    "senders": ["client@household.com", "advisor@firm.com"],
    "participants": ["advisor@firm.com", "client@household.com"],
    "attachments_summary": [],
    "estimated_tokens": 42,
    "used_llmlingua": false
  }
]
```

---

### Step 4: Run Automated Tests Inside Docker

To verify all 52 unit and integration tests inside Docker:

```bash
docker compose run --rm app-prod pytest
```

---

### Step 5: Deploying Container to Microsoft Azure

#### Option A: Azure Container Apps / Azure Kubernetes (AKS)
1. **Build and Tag the Image**:
   ```bash
   docker build -f Dockerfile.prod -t <your-acr-name>.azurecr.io/intelligent-email-service:latest .
   ```
2. **Push to Azure Container Registry (ACR)**:
   ```bash
   az acr login --name <your-acr-name>
   docker push <your-acr-name>.azurecr.io/intelligent-email-service:latest
   ```
3. **Configure Ingress**: Set the container ingress target port to **`8000`**.

#### Option B: Azure App Service (Custom Container)
1. In Azure Portal &rarr; **App Services** &rarr; **Create Web App (Docker Container)**.
2. Select your Azure Container Registry image.
3. In **Configuration &rarr; Application Settings**, add:
   * `WEBSITES_PORT`: `8000`
   * `APP_ENV`: `test_prod`
   * `EMAIL_PROVIDER`: `microsoft`
   * `AZURE_TENANT_ID`: `<tenant-id>`
   * `AZURE_CLIENT_ID`: `<client-id>`
   * `AZURE_CLIENT_SECRET`: `<client-secret>`

---

## Architecture Overview

```
HTTP Client / LLM Agent
       │ (POST /compress)
       ▼
FastAPI Service Layer (intelligent_email_service.app)
       │
       ▼
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

### 🟢 Production & Azure Environment
- **[Architecture & System Design](docs/production/architecture.md)**: Data flow pipeline, configuration objects, DAG reconstruction, and component design.
- **[Output Schema & Data Structure](docs/production/data-structure.md)**: Streamlined output payload schema (`compressed_body`) and field specifications.
- **[Preprocessing & Compression](docs/production/preprocessing.md)**: Detailed cleaner, attachment processor, and compressor specifications.

### 🟡 Local Development & Testing
- **[Local Docker Setup Guide](docs/development/local-docker-setup.md)**: Step-by-step guide for local development and offline mock testing with Docker Compose.
- **[Mock Setup Guide](docs/development/mock-setup.md)**: Guide for running Mockoon and local API simulation.
- **[Synthetic Email Generator](docs/development/synthetic-generator.md)**: Usage guide for synthetic email thread generation with NVIDIA LLM / Fallback templates.

---

## Testing & Quality Assurance

Run the test suite using `uv`:

```bash
uv run pytest
```
