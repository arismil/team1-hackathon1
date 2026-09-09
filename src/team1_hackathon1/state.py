import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, Field


Severity = Literal["low", "medium", "high", "critical"]
RiskLevel = Literal["low", "medium", "high"]
ApprovalStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
]
FinalStatus = Literal[
    "resolved",
    "failed",
    "escalated",
]


class Plan(BaseModel):
    steps: list[str] = Field(
        description="2-4 ordered, concrete steps needed to solve the ticket"
    )


class Replan(BaseModel):
    done: bool = Field(
        description="True if the ticket is resolved; False if more steps are needed"
    )
    remaining_steps: list[str] = Field(
        description="Updated remaining steps if not done; [] if done"
    )


class IncidentState(TypedDict):
    incident_id: str
    service: str
    description: str
    error: str | None

    classification: str | None
    severity: Severity | None

    evidence: Annotated[list[dict], operator.add]
    messages: Annotated[list[Any], operator.add]

    root_cause: str | None

    remediation_plan: str | None
    risk_level: RiskLevel | None

    approval_status: ApprovalStatus | None

    execution_result: str | None
    verification_result: str | None

    remediation_attempts: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]

    retry_count: int

    final_status: FinalStatus | None
    final_report: str | None
