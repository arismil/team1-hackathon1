from pydantic import BaseModel, Field, ValidationError, field_validator

SEVERITIES = {"low", "medium", "high", "critical", "unknown"}


class SupportTicket(BaseModel):
    # Validates types, applies Field constraints (gt=0), and custom validators
    incident_id: str
    service: str
    description: str
    severity: str = "medium"
    error: str

    @field_validator("severity")  # Custom validation for severity enum
    @classmethod
    def severity_must_be_known(cls, value: str) -> str:
        if value not in SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(SEVERITIES)}, got {value!r}"
            )
        return value
