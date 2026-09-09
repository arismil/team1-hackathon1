import os
from collections.abc import Callable
from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
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


def _trace_value(value: Any) -> Any:
    """Convert graph state values into data accepted by Langfuse."""
    if isinstance(value, dict):
        return {str(key): _trace_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_trace_value(item) for item in value]
    if hasattr(value, "content"):
        return {"type": type(value).__name__, "content": _trace_value(value.content)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _state_after_update(
    state: dict[str, Any], update: dict[str, Any]
) -> dict[str, Any]:
    """Reconstruct the state snapshot after LangGraph applies a node update."""
    merged = dict(state)
    reducer_fields = {"evidence", "messages", "remediation_attempts", "errors"}
    for key, value in update.items():
        if key in reducer_fields and isinstance(value, list):
            previous = merged.get(key, [])
            merged[key] = [*previous, *value] if isinstance(previous, list) else value
        else:
            merged[key] = value
    return merged


def trace_node_state(name: str, function: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Trace each node's input and update, including the state accumulated so far."""
    @wraps(function)
    def traced_node(state: dict[str, Any]) -> dict[str, Any]:
        if os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() != "true":
            return function(state)

        from langfuse import get_client

        with get_client().start_as_current_observation(
            name=f"state:{name}",
            as_type="chain",
            input={"state_before": _trace_value(state)},
        ) as span:
            update = function(state)
            span.update(
                output={
                    "state_update": _trace_value(update),
                    "state_after": _trace_value(_state_after_update(state, update)),
                }
            )
            return update

    return traced_node


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
