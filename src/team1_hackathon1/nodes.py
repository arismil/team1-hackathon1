from team1_hackathon1.llm import model
from team1_hackathon1.state import IncidentState
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph


def classify(state: IncidentState) -> dict:
    """Classify ticket into a category for routing."""
    severity = (
        model.invoke(
            f"Classify this support ticket as exactly one word --low, medium, high, critical: {state['ticket']!r}"
        )
        .content.strip()
        .lower()
    )
    severity = severity if severity in ("low", "medium", "high", "critical") else "unknown"
    return {"severity": severity}


