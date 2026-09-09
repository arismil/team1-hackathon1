import logging
import json
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from team1_hackathon1.llm import model
from team1_hackathon1.observability import trace_node_state
from team1_hackathon1.state import IncidentState
from team1_hackathon1.tools import INVESTIGATION_TOOLS, REMEDIATION_TOOLS

logger = logging.getLogger(__name__)


def _content_text(content: Any) -> str:
    """Normalize provider-specific message content to plain text."""
    return content if isinstance(content, str) else str(content)


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

    def investigate(state: IncidentState) -> dict[str, Any]:
        """Orchestrate dedicated workers for each investigation data source."""
        response = model.invoke(
            f"""
            You are the investigation orchestrator. Decide which read-only
            investigation workers to run for this incident. Return ONLY valid JSON:
            an array of objects with exactly these fields:
            tool (one of search_logs, get_service_metrics, search_knowledge_base,
            get_incident_history) and args (an object).
            Always include logs, metrics, knowledge base, and incident history.
            Use the exact service name supplied below. Never request remediation.

            Incident:
            {state!r}
            """
        )

        evidence: list[dict[str, Any]] = []
        errors: list[str] = []
        workers = {candidate.name: candidate for candidate in INVESTIGATION_TOOLS}
        try:
            tasks = json.loads(_json_content(_content_text(response.content).strip()))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Investigation orchestrator returned invalid JSON: {response.content!r}"
            ) from exc

        if not isinstance(tasks, list):
            raise ValueError("Investigation orchestrator output must be a JSON array.")

        for task in tasks:
            if not isinstance(task, dict):
                errors.append(f"Invalid investigation task: {task!r}")
                continue
            name = task.get("tool")
            arguments = task.get("args", {})
            if not isinstance(name, str):
                errors.append(f"Investigation task has invalid tool name: {name!r}")
                continue
            tool = workers.get(name)
            if tool is None:
                errors.append(f"Unknown investigation tool requested: {name!r}")
                continue
            if not isinstance(arguments, dict):
                errors.append(f"{name} arguments must be an object: {arguments!r}")
                continue
            try:
                evidence.append(
                    {
                        "tool": name,
                        "result": tool.invoke(arguments),
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
            signing keys are also high risk and all require human approval.
            If retry_count is greater than zero, choose a high-risk action other than
            restart_service because the previous remediation failed.

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
        retry_count = state.get("retry_count", 0)
        if retry_count > 0:
            if action == "restart_service":
                raise ValueError(
                    "A retry after failed remediation must use a high-risk action."
                )
            risk_level = "high"
            plan["risk_level"] = risk_level

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
        failed = any(
            marker in result.lower()
            for marker in ("did not resolve", "unknown service", "not applicable", "error:")
        )
        return {
            "execution_result": result,
            "remediation_attempts": [f"{action}: {result}"],
            "retry_count": state.get("retry_count", 0) + 1,
            "errors": [f"{action} did not resolve the incident."] if failed else [],
        }

    def request_approval(state: IncidentState) -> dict[str, Any]:
        print(f"Requesting approval for remediation of {state['incident_id']}")
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

    def route_after_execution(state: IncidentState) -> str:
        execution_result = (state["execution_result"] or "").lower()
        failed = any(
            marker in execution_result
            for marker in ("did not resolve", "unknown service", "not applicable", "error:")
        )
        if failed and state.get("retry_count", 0) <= 1:
            return "plan_remediation"
        return END

    graph = StateGraph(IncidentState)
    graph.add_node(
        "classify_severity", trace_node_state("classify_severity", classify_severity)
    )
    graph.add_node(
        "categorize_ticket", trace_node_state("categorize_ticket", categorize_ticket)
    )
    graph.add_node("investigate", trace_node_state("investigate", investigate))
    graph.add_node("diagnose", trace_node_state("diagnose", diagnose))
    graph.add_node(
        "plan_remediation", trace_node_state("plan_remediation", plan_remediation)
    )
    graph.add_node(
        "execute_remediation", trace_node_state("execute_remediation", execute_remediation)
    )
    graph.add_node(
        "request_approval", trace_node_state("request_approval", request_approval)
    )

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
    graph.add_conditional_edges(
        "execute_remediation",
        route_after_execution,
        {"plan_remediation": "plan_remediation", END: END},
    )
    graph.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {"execute_remediation": "execute_remediation", END: END},
    )
    return graph.compile(checkpointer=InMemorySaver())
