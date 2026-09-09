import logging
import json
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from team1_hackathon1.llm import model
from team1_hackathon1.state import IncidentState
from team1_hackathon1.tools import INVESTIGATION_TOOLS, REMEDIATION_TOOLS

logger = logging.getLogger(__name__)


def _content_text(content: Any) -> str:
    """Normalize provider-specific message content to plain text."""
    return content if isinstance(content, str) else str(content)


def _tool_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    arguments = tool_call.get("args", {})
    if not isinstance(arguments, dict):
        raise ValueError(f"Tool call arguments must be an object: {arguments!r}")
    return arguments


def _json_content(raw: str) -> str:
    """Remove an optional Markdown code fence around model-generated JSON."""
    if raw.startswith("```") and raw.endswith("```"):
        lines = raw.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return raw


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
        return {"messages": [response], "evidence": evidence, "errors": errors}

    def diagnose(state: IncidentState) -> dict[str, Any]:
        """Synthesize the ticket and all investigation results into a diagnosis."""
        response = model.invoke(
            f"""
            Diagnose this IT incident using all the gathered state below.
            Determine the most likely root cause, cite the relevant evidence, and
            distinguish confirmed facts from uncertainty. Do not recommend or
            execute remediation yet. Return a concise but complete diagnosis.

            Ticket and classifications:
            incident_id: {state["incident_id"]}
            service: {state["service"]}
            description: {state["description"]}
            reported_error: {state["error"]}
            classification: {state["classification"]}
            severity: {state["severity"]}

            Investigation evidence:
            {state["evidence"]}

            Investigation errors:
            {state["errors"]}
            """
        )
        diagnosis = _content_text(response.content).strip()
        if not diagnosis:
            raise ValueError("Diagnosis model returned empty content.")
        return {"root_cause": diagnosis, "messages": [response]}

    def plan_remediation(state: IncidentState) -> dict[str, Any]:
        """Ask the LLM to choose and risk-rate one simulated remediation."""
        response = model.invoke(
            f"""
            Plan one remediation for this diagnosed IT incident using only these
            actions: restart_service, scale_database, rotate_signing_key.
            Return ONLY valid JSON with exactly these fields:
            action (string), risk_level (low or high), steps (array of strings),
            rationale (string).
            Restarting a service is low risk. Scaling database capacity and rotating
            signing keys are high risk and require human approval.

            Incident state:
            {state!r}
            """
        )
        raw_plan = _json_content(_content_text(response.content).strip())
        try:
            plan = json.loads(raw_plan)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Remediation plan was not valid JSON: {raw_plan!r}"
            ) from exc

        if not isinstance(plan, dict):
            raise ValueError("Remediation plan must be a JSON object.")
        action = plan.get("action")
        risk_level = plan.get("risk_level")
        steps = plan.get("steps")
        if action not in REMEDIATION_TOOLS:
            raise ValueError(f"Unsupported remediation action: {action!r}")
        if risk_level not in ("low", "high"):
            raise ValueError(f"Unsupported remediation risk level: {risk_level!r}")
        if not isinstance(steps, list) or not all(
            isinstance(step, str) for step in steps
        ):
            raise ValueError("Remediation plan steps must be a list of strings.")

        return {
            "remediation_plan": json.dumps(plan),
            "risk_level": risk_level,
            "approval_status": "not_required" if risk_level == "low" else "pending",
            "messages": [response],
        }

    def execute_remediation(state: IncidentState) -> dict[str, Any]:
        plan = json.loads(state["remediation_plan"] or "{}")
        action = plan["action"]
        result = REMEDIATION_TOOLS[action].invoke({"service": state["service"]})
        print(f"Executed remediation {action} for {state['service']}: {result}")
        return {
            "execution_result": result,
            "remediation_attempts": [f"{action}: {result}"],
        }

    def request_approval(state: IncidentState) -> dict[str, Any]:
        decision = interrupt(
            {
                "message": "High-risk remediation requires human approval.",
                "incident_id": state["incident_id"],
                "service": state["service"],
                "risk_level": state["risk_level"],
                "remediation_plan": state["remediation_plan"],
                "question": "Approve this remediation?",
            }
        )
        approved = decision is True or (
            isinstance(decision, str)
            and decision.strip().lower() in {"yes", "y", "approve", "approved", "true"}
        )
        return {"approval_status": "approved" if approved else "rejected"}

    def route_by_risk(state: IncidentState) -> str:
        return (
            "execute_remediation"
            if state["risk_level"] == "low"
            else "request_approval"
        )

    def route_after_approval(state: IncidentState) -> str:
        return "execute_remediation" if state["approval_status"] == "approved" else END

    graph = StateGraph(IncidentState)
    graph.add_node("classify_severity", classify_severity)
    graph.add_node("categorize_ticket", categorize_ticket)
    graph.add_node("investigate", investigate)
    graph.add_node("diagnose", diagnose)
    graph.add_node("plan_remediation", plan_remediation)
    graph.add_node("execute_remediation", execute_remediation)
    graph.add_node("request_approval", request_approval)

    graph.add_edge(START, "classify_severity")
    graph.add_edge("classify_severity", "categorize_ticket")
    graph.add_edge("categorize_ticket", "investigate")
    graph.add_edge("investigate", "diagnose")
    graph.add_edge("diagnose", "plan_remediation")
    graph.add_conditional_edges(
        "plan_remediation",
        route_by_risk,
        {
            "execute_remediation": "execute_remediation",
            "request_approval": "request_approval",
        },
    )
    graph.add_edge("execute_remediation", END)
    graph.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {"execute_remediation": "execute_remediation", END: END},
    )
    return graph.compile(checkpointer=InMemorySaver())
