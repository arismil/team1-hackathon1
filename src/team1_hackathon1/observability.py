import os
from collections.abc import Generator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from prometheus_client import Counter, Histogram

GRAPH_RUNS = Counter(
    "incident_graph_runs_total",
    "Number of incident graph executions.",
    ["status"],
)
GRAPH_DURATION = Histogram(
    "incident_graph_duration_seconds",
    "Duration of incident graph executions.",
)


def langfuse_callbacks() -> list[Any]:
    """Return Langfuse callbacks when tracing is configured, otherwise none."""
    if os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() != "true" or not all(
        os.getenv(name)
        for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    ):
        return []

    from langfuse.langchain import CallbackHandler

    return [CallbackHandler()]


@contextmanager
def observe_graph_run() -> Generator[None, None, None]:
    started = perf_counter()
    try:
        yield
    except Exception:
        GRAPH_RUNS.labels(status="error").inc()
        raise
    else:
        GRAPH_RUNS.labels(status="success").inc()
    finally:
        GRAPH_DURATION.observe(perf_counter() - started)
