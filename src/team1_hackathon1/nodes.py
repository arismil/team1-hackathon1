import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from team1_hackathon1.llm import model
from team1_hackathon1.state import IncidentState
from team1_hackathon1.tools import INVESTIGATION_TOOLS

logger = logging.getLogger(__name__)


def _content_text(content: Any) -> str:
    """Normalize provider-specific message content to plain text."""
    return content if isinstance(content, str) else str(content)


def _tool_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    arguments = tool_call.get("args", {})
    if not isinstance(arguments, dict):
        raise ValueError(f"Tool call arguments must be an object: {arguments!r}")
    return arguments


def build_triage_graph() -> Any:
    def classify_severity(state: IncidentState) -> dict[str, str]:
        severity = (
            _content_text(
                model.invoke(
                    "Classify this support ticket as exactly one word --low, medium, "
                    f"high, critical: {state!r}"
                ).content
            )
            .strip()
            .lower()
        )
        return {
            "severity": severity
            if severity in ("low", "medium", "high", "critical")
            else "unknown"
        }

    def categorize_ticket(state: IncidentState) -> dict[str, str]:
        classification = (
            _content_text(
                model.invoke(
                    """
                Classify this IT incident as exactly one of:
                database, authentication, payment, performance,
                application, infrastructure, unknown.

                Incident:
                {state}

                Return only the category.
                """.format(state=state)
                ).content
            )
            .strip()
            .lower()
        )
        return {"classification": classification}

    investigation_model = model.bind_tools(INVESTIGATION_TOOLS)

    def investigate(state: IncidentState) -> dict[str, Any]:
        """Gather evidence by allowing the LLM to call read-only mock systems."""
        response = investigation_model.invoke(
            f"""
            Investigate this IT incident using the available read-only tools.
            You must call the tools for logs, metrics, knowledge-base guidance,
            and incident history for the affected service before concluding.
            Use the exact service name supplied below. Do not execute remediation.

            Incident:
            {state!r}
            """
        )

        evidence: list[dict[str, Any]] = []
        errors: list[str] = []
        for tool_call in getattr(response, "tool_calls", []):
            name = tool_call.get("name")
            tool = next(
                (
                    candidate
                    for candidate in INVESTIGATION_TOOLS
                    if candidate.name == name
                ),
                None,
            )
            if tool is None:
                errors.append(f"Unknown investigation tool requested: {name!r}")
                continue
            try:
                evidence.append(
                    {
                        "tool": name,
                        "result": tool.invoke(_tool_arguments(tool_call)),
                    }
                )
            except (TypeError, ValueError, KeyError) as exc:
                errors.append(f"{name} failed: {exc}")
        print(f"Investigation evidence: {evidence}")
        return {"messages": [response], "evidence": evidence, "errors": errors}

    graph = StateGraph(IncidentState)
    graph.add_node("classify_severity", classify_severity)
    graph.add_node("categorize_ticket", categorize_ticket)
    graph.add_node("investigate", investigate)
    graph.add_edge(START, "classify_severity")
    graph.add_edge("classify_severity", "categorize_ticket")
    graph.add_edge("categorize_ticket", "investigate")
    graph.add_edge("investigate", END)
    return graph.compile()
