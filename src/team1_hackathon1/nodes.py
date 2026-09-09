from typing import Literal, TypedDict
import logging
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from team1_hackathon1.llm import model
from team1_hackathon1.state import IncidentState

logger = logging.getLogger(__name__)


def build_triage_graph() -> StateGraph:
    def classify_severity(state: IncidentState) -> dict:
        """Classify ticket into a category for routing."""
        severity = (
            model.invoke(
                f"Classify this support ticket as exactly one word --low, medium, high, critical: {state!r}"
            )
            .content.strip()
            .lower()
        )
        severity = (
            severity if severity in ("low", "medium", "high", "critical") else "unknown"
        )
        print(f"Classified ticket as severity {severity}")
        return {"severity": severity}

    def categorize_ticket(state: IncidentState) -> dict:
        """Classify ticket into a category for routing."""
        classification = (
            model.invoke(
                f"""
                Classify this IT incident as exactly one of:
                database, authentication, payment, performance,
                application, infrastructure, unknown.
    
                Incident:
                {state!r}
    
                Return only the category.
                """
            )
            .content.strip()
            .lower()
        )
        print(f"Classified ticket as category {classification}")
        return {"category": classification}

    graph = StateGraph(IncidentState)

    graph.add_node("classify_severity", classify_severity)
    graph.add_node("categorize_ticket", categorize_ticket)

    graph.add_edge(START, "classify_severity")
    graph.add_edge("classify_severity", "categorize_ticket")
    graph.add_edge("categorize_ticket", END)

    return graph.compile()
