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
