import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

DATA_DIR = Path(__file__).parent


def _load(filename: str) -> Any:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


LOGS = _load("mock_data/logs.json")
METRICS = _load("mock_data/metrics.json")
REMEDIATION_EFFECTS = _load("mock_data/remediation_effects.json")
INCIDENT_HISTORY = _load("mock_data/incident_history.json")
KNOWLEDGE_BASE = _load("mock_data/knowledge_base.json")

SERVICES = sorted(k for k in LOGS if k != "_default")


def _format_log_entry(entry: dict) -> str:
    return f"[{entry['timestamp']}] {entry['level']}: {entry['message']}"


def _unknown_service_error(service: str) -> str:
    return f"Error: Unknown service '{service}'. Known services: {', '.join(SERVICES)}."


def _normalize_service(service: str) -> str:
    """Normalize harmless whitespace/control characters from model tool args."""
    return service.replace("\x00", "").strip()


def _apply_remediation(
    action: str, service: str, verb: str, use_default_fallback: bool = False
) -> str:
    """Shared implementation for restart_service / scale_database / rotate_signing_key.

    Looks up REMEDIATION_EFFECTS[action][service] (falling back to "_default"
    only when use_default_fallback is True), applies its metric_changes to the
    live METRICS for that service, and reports whether it resolved the root
    cause. Returns a plain "not applicable" message, not an error, when the
    action has no modeled effect for that service -- that's a legitimate
    answer for a targeted fix like rotate_signing_key on a non-identity
    service.
    """
    effects = REMEDIATION_EFFECTS.get(action, {})
    effect = effects.get(service)
    if effect is None and use_default_fallback:
        effect = effects.get("_default")
    if effect is None:
        return (
            f"{verb}: not applicable -- no modeled effect for this action/service pair."
        )

    metric_changes = effect.get("metric_changes", {})
    METRICS[service].update(metric_changes)

    resolved = effect.get("resolves_root_cause", False)
    verdict = (
        "This resolved the root cause."
        if resolved
        else "This did NOT resolve the root cause."
    )
    note = effect.get("note", "")
    return f"{verb}. {verdict}\nNote: {note}\nUpdated metrics: {metric_changes}"


@tool
def search_logs(service: str) -> str:
    """Search recent logs for a specific service to identify errors and warnings."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)

        entries = LOGS.get(service, [])
        if not entries:
            return f"No log entries found for {service}."

        formatted = "\n".join(_format_log_entry(e) for e in entries)
        return f"Logs for {service}:\n{formatted}"
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def get_service_metrics(service: str) -> str:
    """Fetch current operational metrics (CPU, memory, latency, error rate, etc.) for a given service."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)

        metrics = METRICS[service]
        lines = "\n".join(f"- {key}: {value}" for key, value in metrics.items())
        return f"Metrics for {service}:\n{lines}"
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for runbooks and articles relevant to a symptom, error message, or metric anomaly."""
    try:
        if not query or not query.strip():
            return "Error: query must be a non-empty string."

        terms = [t.lower() for t in query.split()]
        scored = []
        for doc in KNOWLEDGE_BASE:
            haystack = " ".join(
                [doc["title"], doc["snippet"], " ".join(doc["keywords"])]
            ).lower()
            score = sum(haystack.count(term) for term in terms)
            if score > 0:
                scored.append((score, doc))

        if not scored:
            return f"No knowledge base articles found for query '{query}'."

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_results = "\n\n".join(
            f"[{doc['doc_id']}] {doc['title']}\n{doc['snippet']}"
            for _, doc in scored[:3]
        )
        return f"Knowledge base results for '{query}':\n\n{top_results}"
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def get_incident_history(service: str) -> str:
    """Retrieve past incidents recorded for a service, including their root cause and resolution."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)

        incidents = INCIDENT_HISTORY.get(service, [])
        if not incidents:
            return f"No incident history found for {service}."

        formatted = "\n\n".join(
            f"{inc['incident_id']} ({inc['date']})\n"
            f"Root cause: {inc['root_cause']}\n"
            f"Resolution: {inc['resolution']}"
            for inc in incidents
        )
        return f"Incident history for {service}:\n\n{formatted}"
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def restart_service(service: str) -> str:
    """Restart a service. A low-risk first mitigation that clears stale connections and in-memory state,
    but does not fix problems rooted in configuration or the database -- follow up with
    check_service_health to confirm whether it actually worked."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)
        return _apply_remediation(
            "restart_service",
            service,
            f"Restarted {service}",
            use_default_fallback=True,
        )
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def check_service_health(service: str) -> str:
    """Evaluate a service's current metrics against baseline thresholds and report whether it is healthy, degraded, or critical."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)

        m = METRICS[service]
        issues = []

        error_rate = m.get("error_rate_pct", 0)
        if error_rate > 10:
            issues.append(("CRITICAL", f"error rate {error_rate}% is very high"))
        elif error_rate > 2:
            issues.append(("DEGRADED", f"error rate {error_rate}% is above baseline"))

        response_time = m.get("response_time_ms", 0)
        if response_time > 2000:
            issues.append(("CRITICAL", f"response time {response_time}ms is very high"))
        elif response_time > 500:
            issues.append(
                ("DEGRADED", f"response time {response_time}ms is above baseline")
            )

        pool_pct = m.get("db_connection_pool_pct", 0)
        if pool_pct > 90:
            issues.append(("CRITICAL", f"DB connection pool at {pool_pct}%"))
        elif pool_pct > 70:
            issues.append(("DEGRADED", f"DB connection pool at {pool_pct}%"))

        token_err = m.get("token_validation_error_rate_pct")
        if token_err is not None and token_err > 5:
            issues.append(("CRITICAL", f"token validation error rate {token_err}%"))

        if not issues:
            return f"{service} is HEALTHY. Metrics: {m}"

        status = (
            "CRITICAL" if any(sev == "CRITICAL" for sev, _ in issues) else "DEGRADED"
        )
        details = "; ".join(msg for _, msg in issues)
        return f"{service} is {status}: {details}\nFull metrics: {m}"
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def scale_database(service: str) -> str:
    """Increase database capacity. This is a high-risk production change."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)
        return _apply_remediation(
            "scale_database",
            service,
            f"Scaled database capacity for {service}",
        )
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


@tool
def rotate_signing_key(service: str) -> str:
    """Rotate authentication signing keys. This is a high-risk production change."""
    try:
        service = _normalize_service(service)
        if service not in SERVICES:
            return _unknown_service_error(service)
        return _apply_remediation(
            "rotate_signing_key",
            service,
            f"Rotated signing key for {service}",
        )
    except Exception as e:
        return f"Tool execution failed: {str(e)}"


# Read-only tools the investigation model is allowed to call. Remediation tools
# are intentionally excluded until the workflow reaches its approval gate.
INVESTIGATION_TOOLS = [
    search_logs,
    get_service_metrics,
    search_knowledge_base,
    get_incident_history,
]

REMEDIATION_TOOLS = {
    "restart_service": restart_service,
    "scale_database": scale_database,
    "rotate_signing_key": rotate_signing_key,
}
