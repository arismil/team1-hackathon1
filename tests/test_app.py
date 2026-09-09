from fastapi.testclient import TestClient

from team1_hackathon1.app import app

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
