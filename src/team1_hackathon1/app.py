from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel
from prometheus_client import make_asgi_app

from team1_hackathon1.models import SupportTicket
from team1_hackathon1.nodes import build_triage_graph
from team1_hackathon1.observability import langfuse_callbacks, observe_graph_run

app = FastAPI(
    title="team1-hackathon1",
    version="0.1.0",
    description="Tiny FastAPI service scaffolded for Dockerized deployment.",
)
app.mount("/metrics", make_asgi_app())

triage_graph = build_triage_graph()
_tickets: dict[str, SupportTicket] = {}


class ApprovalDecision(BaseModel):
    approved: bool


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
    with observe_graph_run():
        triage_graph.invoke(
            stored_ticket.model_dump(),
            config={
                "configurable": {"thread_id": stored_ticket.incident_id},
                "callbacks": langfuse_callbacks(),
                "metadata": {
                    "incident_id": stored_ticket.incident_id,
                    "service": stored_ticket.service,
                },
                "tags": ["incident-triage"],
            },
        )
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


@app.post("/tickets/{ticket_id}/approval")
def approve_remediation(ticket_id: str, decision: ApprovalDecision) -> dict[str, Any]:
    if ticket_id not in _tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")

    with observe_graph_run():
        result = triage_graph.invoke(
            Command(resume=decision.approved),
            config={
                "configurable": {"thread_id": ticket_id},
                "callbacks": langfuse_callbacks(),
                "metadata": {"incident_id": ticket_id},
                "tags": ["incident-remediation-approval"],
            },
        )
    return {
        "incident_id": ticket_id,
        "approval_status": result.get("approval_status"),
        "execution_result": result.get("execution_result"),
        "remediation_plan": result.get("remediation_plan"),
    }


def main() -> None:
    import uvicorn

    uvicorn.run("team1_hackathon1.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
