# team1-hackathon1
Hackathon Project for the Get Trained Get Hired 2026 Classgi

## Observability

Run the local observability stack:

```bash
docker compose up --build
```

- FastAPI: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3002 (`admin` / `admin` by default)
- Langfuse: http://localhost:3003 (`admin@example.com` / `admin` by default)

The application exposes Prometheus metrics at `/metrics`. Langfuse tracing is
Langfuse runs locally in Docker with PostgreSQL, ClickHouse, Redis, and MinIO.
The app sends traces to the internal `langfuse-web` service. This local stack
uses more containers than the API-only setup because Langfuse requires these
storage and queue services.
