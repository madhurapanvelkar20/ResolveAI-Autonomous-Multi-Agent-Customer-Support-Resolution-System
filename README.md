# ResolveAI — Autonomous Multi-Agent Customer Support & Resolution System

ResolveAI is an autonomous multi-agent customer support and resolution system built with Python, LangGraph, Pydantic v2, ChromaDB, and FastAPI. It investigates customer support cases, queries evidence from databases and enterprise policies via local RAG, proposes bounded customer resolutions, and validates all proposals through an independent critic agent before approval.

---

## 1. System Architecture

ResolveAI coordinates four specialized autonomous agents inside a stateful LangGraph graph (`resolveai.workflow.create_support_graph`):

```
                       +-----------------------+
                       |    Incoming Ticket    |
                       +-----------+-----------+
                                   |
                                   v
                       +-----------------------+
                +----->|      Triage Agent     |<----+
                |      +-----------+-----------+     |
                |                  |                 |
                |                  v                 |
                |      +-----------------------+     |
                +----->|  Investigation Agent  |     |
                |      +-----------+-----------+     |
                |                  | (Tool calls: DB |
                |                  |  & Policy RAG)  |
                |                  v                 |
                |      +-----------------------+     |
                +----->|   Resolution Agent    |     |
                       +-----------+-----------+     |
                                   |                 |
                                   v                 |
                       +-----------------------+     |
                       |     Critic Agent      |-----+ (reject / request_evidence)
                       +-----------+-----------+
                                   | (approve)
                                   v
                       +-----------------------+
                       |    Approved / Final   |
                       +-----------------------+
```

### Core Agents

1. **Triage Agent:**
   - Evaluates incoming ticket metadata, customer sentiment, urgency, and core claim.
   - Identifies high-risk fraud or missing information early and routes to Investigation, Resolution, or immediate Escalation.
2. **Investigation Agent:**
   - Formulates targeted queries and calls authorized tools (`lookup_order`, `lookup_payment`, `search_knowledge_base`).
   - Extracts objective facts, transaction timestamps, and policy clauses.
3. **Resolution Agent:**
   - Formulates concrete, policy-compliant resolution proposals (`refund`, `replacement`, `return`, `explanation`, or `escalation`).
   - Assesses financial impact, provides rationale, and references relevant policy citations.
4. **Critic Agent:**
   - Independently reviews proposed actions against retrieved policy evidence, eligibility windows, financial caps, and fraud indicators.
   - Emits structured feedback: `approve`, `reject` (route back to Resolution), or `request_evidence` (route back to Investigation).

### Safety & Guardrails

- **Maximum Iterations:** Hard limit (default: 15) prevents infinite conversational loops.
- **Maximum Tool Calls:** Per-case limit (default: 10) prevents runaway tool execution.
- **Wall-Clock Duration:** Injectable timeout ceiling (default: 60s) prevents hung executions.
- **Agent Tool Permissions:** Strictly enforced tool allowlists (`AGENT_TOOL_ALLOWLIST`). Triage and Resolution cannot invoke database tools; only Investigation can access raw operational lookups.
- **Untrusted Content Wrapping:** Customer inputs and retrieved policy texts are tagged as untrusted context to resist prompt injection.

---

## 2. Policy Knowledge Base & Local RAG

### 2.1 Standardized Policy Documents

Located under `docs/policies/`:
- [`refunds.md`](docs/policies/refunds.md): Policy `POL-REF-001` (v1.2.0) — Automatic approval limit $100.00, 30-day reporting window.
- [`cancellations.md`](docs/policies/cancellations.md): Policy `POL-CAN-001` (v1.1.0) — Only `processing` orders, strict 24-hour cutoff before shipment.
- [`returns.md`](docs/policies/returns.md): Policy `POL-RET-001` (v1.2.0) — 30-day delivery window, auto return label cap $250.00.
- [`payments.md`](docs/policies/payments.md): Policy `POL-PAY-001` (v1.1.0) — 72-hour duplicate charge reporting, minor adjustment cap $20.00.
- [`delivery.md`](docs/policies/delivery.md): Policy `POL-DEL-001` (v1.2.0) — 5 business day delay threshold, 10-day no-scan Lost in Transit declaration.
- [`damaged_products.md`](docs/policies/damaged_products.md): Policy `POL-DAM-001` (v1.1.0) — 7-day reporting, photo evidence mandatory, <=$50.00 instant replacement.
- [`escalations.md`](docs/policies/escalations.md): Policy `POL-ESC-001` (v1.3.0) — Suspected fraud, legal/chargeback threats, policy override rules.

### 2.2 Ingestion & Vector Retrieval Pipeline

- **Section-Aware Chunking:** Splits policies along markdown `##` section headings, preserving policy identifiers, versions, section titles, and source paths.
- **Stable Content Hashes:** Deterministic chunk IDs (`{slug}-c{hash}`) guarantee idempotent ingestion without duplicating embeddings.
- **Local Persistent Vector Store:** ChromaDB collection stored in `data/chroma/` using offline sentence-transformer models (`all-MiniLM-L6-v2`) or zero-network deterministic mock embeddings for hermetic unit testing.
- **Search Tool (`search_knowledge_base`):** Registered in tool registry with strict Pydantic schemas, returning ranked citations, similarity distances, and policy text.

---

## 3. Demonstration Scenarios

Five end-to-end evaluation scenarios are implemented in `resolveai/scenarios.py`:

| Scenario ID | Name / Description | Expected Outcome | Agents Involved |
|:---|:---|:---|:---|
| `eligible_refund` | Duplicate charge under $100 within 30-day window (`POL-REF-001`). | `RESOLVED` (Refund approved) | Triage, Investigation, Resolution, Critic |
| `ineligible_refund` | Refund request >$100 past 30 days without return. | `ESCALATED` (Manual Review) | Triage, Investigation, Resolution |
| `damaged_product` | Damaged goods report lacking mandatory photo evidence (`POL-DAM-001`). | `ESCALATED` / Information Requested | Triage |
| `delivery_delay` | Package in transit with no scans for 11 days declared Lost in Transit (`POL-DEL-001`). | `RESOLVED` (Replacement authorized) | Triage, Investigation, Resolution, Critic |
| `fraud_high_risk` | Fresh account threatening chargebacks and demanding immediate payout (`POL-ESC-001`). | `ESCALATED` (Security flag) | Triage |

---

## 4. Setup and Quickstart (Windows PowerShell)

Ensure Python 3.11 or 3.12 is installed.

### 4.1 Environment Setup

```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4.2 Ingest Policy Documents

Ingest all Markdown policies into the local ChromaDB vector store:

```powershell
python scripts\ingest_policies.py --policy-dir docs/policies --db-dir data/chroma --recreate
```

### 4.3 Run Automated Test Suite

Run the full automated test suite (101 unit and integration tests):

```powershell
python -m pytest
```

Run specific test modules:

```powershell
# Phase 3 RAG tests
python -m pytest tests/test_rag.py -v

# Phase 4 Multi-agent orchestration tests
python -m pytest tests/test_multiagent.py -v

# Phase 4 Demo scenario tests
python -m pytest tests/test_demo_scenarios.py -v
```

### 4.4 Run Demonstration Scenarios

Execute all 5 scenarios and view the evaluation scorecard:

```powershell
python scripts\run_demo_scenarios.py
```

Execute a single scenario with detailed step-by-step agent trace output:

```powershell
python scripts\run_case.py --scenario eligible_refund --verbose-trace
```

Execute with a custom ticket file:

```powershell
python scripts\run_case.py --ticket-path path\to\ticket.json --verbose-trace
```

### 4.5 Start API Server

Launch the FastAPI backend service:

```powershell
python -m uvicorn resolveai.api:app --host 127.0.0.1 --port 8000 --reload
```

Health check:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

### 4.6 Safe n8n Webhook Workflow Integration

ResolveAI provides an opt-in integration to dispatch approved resolution events to n8n for demonstration workflows. The importable workflow definition is located at [`n8n/resolution_event_demo.json`](n8n/resolution_event_demo.json). When a case resolves with an approved resolution (e.g. `refund`, `replacement`), the backend sends a minimal, authenticated event to the n8n Webhook node.

The sample workflow safely validates the incoming payload and returns a **simulated notification** (`demo_result: "simulated_notification"`). It never triggers live financial charges or actual customer emails.

#### Environment Variables Configuration

Set these variables in your local `.env` file (never commit live tokens):

```dotenv
# Enable or disable the n8n integration (default: false)
N8N_ENABLED=true

# Webhook URL for event delivery
# For local Windows host development:
N8N_WEBHOOK_URL=http://localhost:5678/webhook/resolveai-case-event
# For Docker Compose networking:
# N8N_WEBHOOK_URL=http://n8n:5678/webhook/resolveai-case-event
# For containerized backend to host n8n:
# N8N_WEBHOOK_URL=http://host.docker.internal:5678/webhook/resolveai-case-event

# Webhook Authorization token (private secret)
N8N_WEBHOOK_TOKEN=your_private_webhook_token_here

# Timeout in seconds (default: 5)
N8N_TIMEOUT_SECONDS=5
```

#### How to Start the Services

1. **Start the n8n Container:**
   ```powershell
   docker compose up -d n8n
   ```
   n8n will be accessible at `http://localhost:5678`.

2. **Start the FastAPI Backend:**
   ```powershell
   .venv\Scripts\python.exe -m uvicorn resolveai.api:app --host 127.0.0.1 --port 8000 --reload
   ```
   Backend documentation: `http://127.0.0.1:8000/docs`

3. **Start the React Frontend:**
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
   Frontend interface: `http://localhost:5173`

#### Configuring the n8n Workflow

1. Open `http://localhost:5678` in your browser.
2. In n8n, click **Workflows** → **Import from File...** and select [`n8n/resolution_event_demo.json`](n8n/resolution_event_demo.json).
3. In the **Approved Case Event Webhook** node:
   - Ensure the path is set to `resolveai-case-event` and method is `POST`.
   - Set Authentication to **Header Auth**.
   - Create a new Header Auth credential with:
     - **Name:** `Authorization`
     - **Value:** `Bearer <your_private_webhook_token_here>`
4. Toggle the workflow switch to **Active** (required for production webhook delivery at `/webhook/resolveai-case-event`).
   *(If testing interactively with an inactive workflow, use `/webhook-test/resolveai-case-event` and click "Listen for test event" in n8n).*

#### Live Integration Mode vs Mock Demo Mode

The frontend Customer Intake form features a clear **Integration Mode** switch:
- **Live Integration Mode (Default):** Sends `mock: false`. Upon case resolution, the backend dispatches the resolution event to n8n, and the frontend displays the verified outcome (`completed`, `not_configured`, `failed`, or `timed_out`).
- **Mock Demo Mode:** Toggle the switch to enable mock mode (`mock: true`). The case executes offline deterministically and reports `mock_skipped`, making zero outbound network calls.
- **Benchmark Scenarios Tab:** Always executes in deterministic mock mode to preserve reproducible evaluation scoring.

#### Troubleshooting Missing n8n Executions

If you submit a case and no execution appears in n8n:
1. **Check the Frontend Integration Status:**
   - `Mock mode; no external workflow was called.`: The case was run in mock mode (`mock: true`). Ensure the Integration Mode toggle is set to Live Integration.
   - `n8n is not configured; no external workflow was called.`: `N8N_ENABLED` is `false` or missing in your `.env`. Set `N8N_ENABLED=true` and restart FastAPI.
   - `No eligible approved result was sent to an external workflow.`: The case was escalated or rejected by the Critic (e.g. high-risk fraud). Only approved resolutions emit webhook events.
   - `The safe n8n workflow failed`: Connection refused or HTTP 401 Unauthorized. Check that n8n is running and that `N8N_WEBHOOK_TOKEN` matches the credential configured in n8n.
2. **Verify Workflow Activation:** Production webhooks (`/webhook/...`) require the workflow to be toggled to **Active** in n8n. If inactive, n8n rejects production webhooks.
3. **Verify Host URL:** If running FastAPI inside a Docker container, use `http://n8n:5678/...` instead of `localhost`. If running FastAPI on host Windows, use `http://localhost:5678/...`.

---

## 5. Observability & Tracing

Every case execution logs structured JSONL events under `traces/<trace_id>.jsonl`. Events include:
- `case_start`: Initial state and input payload.
- `agent_decision`: Agent thoughts, routing choice, and proposed actions.
- `tool_call` & `tool_result`: Exact tool name, input arguments, and structured return data.
- `critic_review`: Critic evaluation, approved status, and feedback rationale.
- `safety_limit`: Triggers when iteration, tool count, or timeout bounds are exceeded.
- `case_completion`: Final case resolution or escalation reason.

Inspect generated traces:
```powershell
Get-ChildItem traces\*.jsonl | Select-Object -Last 1 | Get-Content
```

---

## 6. Project Layout

```
ResolveAI-Project/
├── docs/
│   └── policies/                  # 7 standardized company policy documents
│       ├── cancellations.md
│       ├── damaged_products.md
│       ├── delivery.md
│       ├── escalations.md
│       ├── payments.md
│       ├── refunds.md
│       └── returns.md
├── resolveai/
│   ├── api.py                     # FastAPI application endpoints
│   ├── config.py                  # Pydantic Settings configuration
│   ├── database.py                # SQLite database and seeded tables
│   ├── llm.py                     # LLM abstraction with retry & fallback
│   ├── policies.py                # Section-aware chunking & ChromaDB RAG
│   ├── scenarios.py               # 5 deterministic demonstration scenarios
│   ├── schemas.py                 # Core Pydantic data schemas
│   ├── security.py                # Prompt injection defence & input sanitizer
│   ├── state.py                   # CaseState model and update operations
│   ├── tools.py                   # Tool registry, schemas & access control
│   ├── tracing.py                 # Structured JSONL case tracer
│   └── workflow.py                # LangGraph 4-agent multi-agent StateGraph
├── scripts/
│   ├── check_llm.py               # Provider configuration probe
│   ├── export_schemas.py          # Export JSON Schemas
│   ├── ingest_policies.py         # Policy ingestion CLI script
│   ├── run_case.py                # Single-case CLI executor
│   └── run_demo_scenarios.py      # End-to-end 5-scenario evaluation runner
└── tests/
    ├── test_api.py
    ├── test_database.py
    ├── test_demo_scenarios.py     # End-to-end scenario assertions
    ├── test_llm.py
    ├── test_multiagent.py        # LangGraph transitions, safety limits & critic
    ├── test_policies.py
    ├── test_rag.py               # Chunking, metadata, ChromaDB, search tool
    ├── test_schemas.py
    ├── test_scripts.py
    ├── test_security.py
    ├── test_state.py
    ├── test_tools.py
    ├── test_tracing.py
    └── test_workflow.py
```
