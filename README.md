
# ResolveAI — Autonomous Multi-Agent Customer Support & Resolution System

ResolveAI is an autonomous multi-agent customer support system designed to investigate customer issues, reason over evidence, and propose policy-compliant resolutions.

## Architecture

The planned system has four core agents:

- **Triage:** classifies issues, identifies missing information, and plans next steps.
- **Investigation:** gathers and analyses evidence using authorized tools.
- **Resolution:** proposes candidate actions and selects a policy-compliant resolution.
- **Critic:** independently evaluates proposals against policy evidence and can approve, reject, or request additional evidence.

LangGraph will execute the agents using shared case state and agent-selected routing. n8n will handle workflow triggers, integrations, transport, and notifications rather than business reasoning.

## Technology

Python 3.12, Pydantic v2, FastAPI, HTTPX, LangGraph, SQLite, ChromaDB, local embeddings, n8n, Docker, and pytest.

The LLM layer supports OpenAI-compatible endpoints, including compatible cloud providers and local Ollama. Provider and model availability must be verified before use.

## Current Implementation Status

Features are listed as implemented only when code exists and has been tested.

### Implemented and locally tested

- Environment-based configuration and settings validation.
- Ticket, agent decision, critic feedback, case state, and case result schemas.
- Initial state ownership checks and restricted state views.
- JSONL tracing utilities and trace event tests.
- Untrusted-input wrapping utilities and tests.
- OpenAI-compatible LLM client with retries and JSON-mode fallback.
- Provider fallback and structured-output validation utilities.
- Scripted LLM for deterministic offline testing.
- FastAPI `GET /health` endpoint.
- JSON Schema export script.
- LLM configuration-check script.
- Automated tests for the foundation and utility scripts.

The latest reported test run completed with **43 passed**. A Starlette/httpx deprecation warning was present. Repeat the test suite after changes to confirm the current result.

### Not implemented yet

- SQLite database schema and synthetic ticket data.
- Authorized customer-support tools and their failure/timeout handling.
- Policy document ingestion and retrieval-augmented generation (RAG).
- Complete triage, investigation, resolution, and critic agents.
- LangGraph execution and adaptive routing.
- Full end-to-end agent evaluation and metrics.
- n8n workflows and integrations.
- Frontend, deployment, and final evaluation.
- Final project documentation, presentation, and viva preparation.

## Development Setup

Use a supported Python version and run these commands from the repository root.

### Windows — Command Prompt

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pytest -q
```

### Windows — PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
```

### Start the API

```cmd
python -m uvicorn resolveai.api:app --host 127.0.0.1 --port 8000
```

Health endpoint: http://127.0.0.1:8000/health

### Export JSON Schemas

```cmd
python scripts\export_schemas.py
```

The generated schemas are saved in `schemas_export/`.

### Check LLM Configuration

```cmd
python scripts\check_llm.py
```

This checks provider configuration without making a network request. To send a real test request to configured providers:

```cmd
python scripts\check_llm.py --probe
```

The probe requires a configured model and the appropriate credentials, or a running local Ollama endpoint. Never commit real credentials.

## Environment Configuration

Copy `.env.example` to `.env` and fill in the settings needed for your selected provider. Local Ollama can be used without a cloud API key when its endpoint and model are configured.

## Academic Integrity

Execution traces, benchmark results, test outcomes, and deployment status must reflect actual executions. Expected behaviour is not evidence that a feature works.
