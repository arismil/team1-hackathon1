from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from team1_hackathon1.models import SupportTicket

app = FastAPI(
    title="team1-hackathon1",
    version="0.1.0",
    description="Tiny FastAPI service scaffolded for Dockerized deployment.",
)

_tickets: dict[str, SupportTicket] = {}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "team1-hackathon1 is running"}


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "team1-hackathon1"}


@app.post("/tickets", status_code=201)
def create_ticket(ticket: SupportTicket) -> SupportTicket:

    stored_ticket = SupportTicket(
        incident_id=ticket.incident_id,
        service=ticket.service,
        description=ticket.description,
        severity=ticket.severity,
        error=ticket.error,
    )
    _tickets[ticket.incident_id] = stored_ticket
    return stored_ticket


@app.get("/tickets")
def list_tickets() -> list[SupportTicket]:
    return list(_tickets.values())


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> SupportTicket:
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def main() -> None:
    import uvicorn

    uvicorn.run("team1_hackathon1.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
