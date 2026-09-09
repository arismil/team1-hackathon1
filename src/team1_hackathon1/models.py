from pydantic import BaseModel, Field, ValidationError, field_validator

PRIORITIES = {"low", "medium", "high", "critical"}


class SupportTicket(BaseModel):
    # Validates types, applies Field constraints (gt=0), and custom validators
    ticket_id: str
    issue: str
    priority: str = "medium"
    sla_minutes: int = Field(default=60, gt=0, description="Minutes until SLA breach")
    tags: list[str] = Field(default_factory=list)
    assignee: str | None = None

    @field_validator("priority")  # Custom validation for priority enum
    @classmethod
    def priority_must_be_known(cls, value: str) -> str:
        if value not in PRIORITIES:
            raise ValueError(
                f"priority must be one of {sorted(PRIORITIES)}, got {value!r}"
            )
        return value
