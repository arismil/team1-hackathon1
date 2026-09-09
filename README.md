# team1-hackathon1
Hackathon Project for the Get Trained Get Hired 2026 Classgi

## Observability

Run the local observability stack:

```bash
docker compose up --build
```

- FastAPI: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (`admin` / `admin` by default)

The application exposes Prometheus metrics at `/metrics`. Langfuse tracing is
enabled when `LANGFUSE_TRACING_ENABLED=true` and
`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set in the environment. The
default Langfuse host is
`https://cloud.langfuse.com`; set `LANGFUSE_HOST` for another deployment.
