import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.types import Command

from team1_hackathon1.app import app
from team1_hackathon1 import nodes
from team1_hackathon1.tools import (
    check_service_health,
    get_incident_history,
    get_service_metrics,
    restart_service,
    search_logs,
)

client = TestClient(app)


def test_root_returns_message() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "team1-hackathon1 is running"}


def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "team1-hackathon1"}


def test_create_and_get_tickets() -> None:

    assert client.get("/tickets").json() == []

    response = client.post(
        "/tickets",
        json={
            "incident_id": "TKT-1",
            "service": "payment-service​",
            "description": "Customers report payment failures for approximately 15 minutes.​",
            "severity": "unknown",
            "error": "Database connection timeout.",
        },
    )

    assert response.status_code == 201
    created = response.json()
    assert created["incident_id"] == "TKT-1"
    assert created["severity"] == "unknown"
    assert created["service"] == "payment-service​"
    assert (
        created["description"]
        == "Customers report payment failures for approximately 15 minutes.​"
    )
    assert created["error"] == "Database connection timeout."

    list_response = client.get("/tickets")
    assert list_response.status_code == 200
    assert list_response.json() == [created]

    detail_response = client.get(f"/tickets/{created['incident_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == created


def test_invalid_ticket_severity_is_rejected() -> None:
    response = client.post(
        "/tickets",
        json={
            "service": "auth",
            "description": "Bad severity value",
            "severity": "urgent",
        },
    )

    assert response.status_code == 422


def test_service_tools_normalize_model_generated_nul_character() -> None:
    service = "payment-service\x00"

    assert "Logs for payment-service:" in search_logs.invoke({"service": service})
    assert "Metrics for payment-service:" in get_service_metrics.invoke(
        {"service": service}
    )
    assert "Incident history for payment-service:" in get_incident_history.invoke(
        {"service": service}
    )
    assert "payment-service is" in check_service_health.invoke({"service": service})


def test_restart_service_normalizes_zero_width_space() -> None:
    result = restart_service.invoke({"service": "payment-service\u200b"})

    assert "Unknown service" not in result
    assert "Restarted payment-service" in result


def test_triage_graph_retries_failed_remediation_with_approval(
    monkeypatch,
) -> None:
    replies = iter(
        [
            AIMessage(content="high"),
            AIMessage(content="database"),
            AIMessage(
                content=json.dumps(
                    [
                        {
                            "tool": "search_logs",
                            "args": {"service": "payment-service"},
                        },
                        {
                            "tool": "get_service_metrics",
                            "args": {"service": "payment-service"},
                        },
                        {
                            "tool": "search_knowledge_base",
                            "args": {"query": "database timeout payment-service"},
                        },
                        {
                            "tool": "get_incident_history",
                            "args": {"service": "payment-service"},
                        },
                    ]
                )
            ),
            AIMessage(content="Database connection pool exhaustion."),
            AIMessage(
                content=json.dumps(
                    {
                        "action": "restart_service",
                        "risk_level": "low",
                        "steps": ["Restart the service"],
                        "rationale": "Release stale connections.",
                    }
                )
            ),
            AIMessage(
                content=json.dumps(
                    {
                        "action": "scale_database",
                        "risk_level": "high",
                        "steps": ["Increase database capacity"],
                        "rationale": "The restart did not resolve pool exhaustion.",
                    }
                )
            ),
        ]
    )

    class MockLLM:
        def invoke(self, prompt):
            assert isinstance(prompt, str)
            return next(replies)

    monkeypatch.setattr(nodes, "model", MockLLM())
    graph = nodes.build_triage_graph()
    initial_state = {
        "incident_id": "TKT-INTEGRATION-RETRY",
        "service": "payment-service",
        "description": "Payments are failing.",
        "error": "Database connection timeout.",
        "classification": None,
        "severity": None,
        "evidence": [],
        "messages": [],
        "root_cause": None,
        "remediation_plan": None,
        "risk_level": None,
        "approval_status": None,
        "execution_result": None,
        "verification_result": None,
        "remediation_attempts": [],
        "errors": [],
        "retry_count": 0,
        "final_status": None,
        "final_report": None,
    }
    config = {"configurable": {"thread_id": "TKT-INTEGRATION-RETRY"}}

    interrupted = graph.invoke(initial_state, config=config)

    assert interrupted["retry_count"] == 1
    assert interrupted["risk_level"] == "high"
    assert interrupted["approval_status"] == "pending"
    assert interrupted["__interrupt__"][0].value["risk_level"] == "high"
    assert json.loads(interrupted["remediation_plan"])["action"] == "scale_database"

    completed = graph.invoke(Command(resume=True), config=config)

    assert completed["approval_status"] == "approved"
    assert completed["retry_count"] == 2
    assert "This resolved the root cause." in completed["execution_result"]
