# team1-hackathon1

A FastAPI + LangGraph incident triage service built for the Get Trained Get Hired 2026 hackathon. The app accepts support tickets, investigates the incident with mock operational tooling, diagnoses the likely root cause, proposes a remediation plan, and requires human approval for higher-risk changes.

## What this project does

- Accepts incident tickets through a REST API
- Classifies ticket severity and incident category
- Gathers evidence from mock logs, metrics, incident history, and a knowledge base
- Builds a LangGraph workflow for investigation and diagnosis
- Produces a remediation plan with approval gating
- Exposes Prometheus metrics and Langfuse tracing for observability

## Architecture at a glance

- FastAPI app: API layer and in-memory ticket storage
- LangGraph workflow: orchestrates investigation, diagnosis, and remediation
- Azure OpenAI: model used for severity classification, diagnosis, and remediation planning
- Langfuse: trace execution of model calls and workflow steps
- Prometheus/Grafana: metrics collection and dashboards
- Docker Compose: local orchestration for app + observability services

## Repository layout

```text
.
├── src/
│   └── team1_hackathon1/
│       ├── app.py               # FastAPI service and endpoints
│       ├── llm.py               # Azure OpenAI model configuration
│       ├── nodes.py             # LangGraph incident triage flow
│       ├── state.py             # Typed workflow state
│       ├── tools.py             # Investigation/remediation tool implementations
│       ├── models.py            # Pydantic data model
│       └── mock_data/           # Simulated logs, metrics, KB, incident history
├── deploy/                      # Prometheus/Grafana config
├── tests/                       # Pytest coverage for API and graph behavior
├── docker-compose.yml           # Local observability stack
├── Dockerfile                   # Container definition for the app
├── .env-example                 # Example environment file
├── pyproject.toml               # Python project metadata and dependencies
├── README.md                    # Project documentation
└── uv.lock                      # Lockfile for uv-managed dependencies
```

## Requirements

- Python 3.14+
- Docker and Docker Compose
- Azure OpenAI access with a valid deployment name
- Optional: uv for local dependency management

## Environment configuration

Copy the example file and fill in the required values:

```bash
cp .env-example .env
```

Key variables:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `OPENAI_API_VERSION`
- `AZURE_OPENAI_DEPLOYMENT_NAME`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_TRACING_ENABLED`

The included `.env-example` uses local defaults for the Langfuse setup and a sample Azure configuration.

## Run the full local stack

Start the application and observability services:

```bash
docker compose up --build
```

Then open:

- FastAPI: http://localhost:8000
- Health check: http://localhost:8000/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3002 (`admin` / `admin` by default)
- Langfuse: http://localhost:3003 (`admin@example.com` / `admin1234` by default)
- Metrics endpoint: http://localhost:8000/metrics

## Local development without Docker

Install dependencies and run the API locally:

```bash
uv sync
uv run uvicorn team1_hackathon1.app:app --host 0.0.0.0 --port 8000
```

If you do not use uv, you can also install with pip using the project metadata from `pyproject.toml`.

## API usage

### Create a ticket

```bash
curl -X POST http://localhost:8000/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "incident_id": "TKT-001",
    "service": "payment-service",
    "description": "Customers are reporting payment failures.",
    "severity": "high",
    "error": "Database connection timeout."
  }'
```

### List tickets

```bash
curl http://localhost:8000/tickets
```

### Fetch one ticket

```bash
curl http://localhost:8000/tickets/TKT-001
```

### Approve a remediation plan

```bash
curl -X POST http://localhost:8000/tickets/TKT-001/approval \
  -H 'Content-Type: application/json' \
  -d '{"approved": true}'
```

The workflow pauses for approval when the selected remediation is high risk, then resumes once a human approves it.

## Observability

The service exposes structured metrics via `/metrics` and sends trace data to Langfuse. Langfuse runs locally with PostgreSQL, ClickHouse, Redis, and MinIO in Docker to support traces, queues, and object storage.

## Testing

Run the project tests with:

```bash
pytest
```

The suite covers root and health endpoints, validation behavior, tool normalization, and the LangGraph retry/approval flow.

## Notes

- Ticket data is stored in memory while the app is running; it is not persisted across restarts.
- The mock investigation tools simulate IT operations data and are intentionally deterministic for local demos and testing.
- The project is designed for a hackathon/demo environment rather than production deployment.
