from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from state import IncidentState

from nodes import (
    triage_node,
    investigation_orchestrator_node,

    logs_node,
    metrics_node,
    knowledge_base_node,
    history_node,

    diagnosis_node,
    remediation_node,
    execute_node,
    verify_node,
    replan_node,
    close_node,
)


""" human approval node!"""

def human_approval_node(state: IncidentState):
    """
    Σταματά τον LangGraph όταν η remediation είναι high-risk.

    Ο graph παραμένει paused μέχρι να πάρει:
        Command(resume=True)
    ή
        Command(resume=False)
    """

    approval = interrupt(
        {
            "message": "High-risk remediation requires human approval.",
            "incident_id": state.get("incident_id"),
            "service": state.get("service"),
            "risk_level": state.get("risk_level"),
            "remediation_plan": state.get("remediation_plan"),
            "question": "Do you approve this remediation?"
        }
    )

    if isinstance(approval, bool):
        approved = approval

    elif isinstance(approval, str):
        approved = approval.strip().lower() in {
            "yes",
            "y",
            "approve",
            "approved",
            "true"
        }

    else:
        approved = False

    return {
        "approved": approved
    }


""" CONDITIONAL ROUTING FUNCTIONS """

def route_by_risk(state: IncidentState) -> str:
    """
    LOW risk:
        remediation -> execute

    MEDIUM / HIGH risk:
        remediation -> human_approval
    """

    risk_level = state.get(
        "risk_level",
        "high"
    ).lower()

    if risk_level == "low":
        return "execute"

    return "human_approval"


def route_after_approval(state: IncidentState) -> str:
    """
    Human approved:
        -> execute

    Human rejected:
        -> replan
    """

    if state.get("approved") is True:
        return "execute"

    return "replan"


def route_after_verification(state: IncidentState) -> str:
    """
    Αν το remediation πέτυχε:
        -> close

    Αν απέτυχε:
        -> replan
    """

    if state.get("resolved") is True:
        return "close"

    return "replan"


""" BUILD LANGGRAPH """

def build_graph():

    graph = StateGraph(IncidentState)

    graph.add_node(
        "triage",
        triage_node
    )

    graph.add_node(
        "investigation_orchestrator",
        investigation_orchestrator_node
    )

    graph.add_node(
        "logs",
        logs_node
    )

    graph.add_node(
        "metrics",
        metrics_node
    )

    graph.add_node(
        "knowledge_base",
        knowledge_base_node
    )

    graph.add_node(
        "history",
        history_node
    )

    """ diagnosis!"""

    graph.add_node(
        "diagnosis",
        diagnosis_node
    )

    graph.add_node(
        "remediation",
        remediation_node
    )

    graph.add_node(
        "human_approval",
        human_approval_node
    )

    graph.add_node(
        "execute",
        execute_node
    )

    graph.add_node(
        "verify",
        verify_node
    )

    graph.add_node(
        "replan",
        replan_node
    )

    graph.add_node(
        "close",
        close_node
    )


    """prosthetw  edges!"""

    graph.add_edge(
        START,
        "triage"
    )

    """TRIAGE ,INVESTIGATION_ORCHESTRATOR"""

    graph.add_edge(
        "triage",
        "investigation_orchestrator"
    )

    """PARALLEL INVESTIGATION"""
    """Ο orchestrator ξεκινάει τους 4 investigation workers."""

    graph.add_edge(
        "investigation_orchestrator",
        "logs"
    )

    graph.add_edge(
        "investigation_orchestrator",
        "metrics"
    )

    graph.add_edge(
        "investigation_orchestrator",
        "knowledge_base"
    )

    graph.add_edge(
        "investigation_orchestrator",
        "history"
    )

    """TO DIAGNOSIS PERIMENEI NA GINOUN 
    logs
     metrics
    knowledge_base
    history"""

    graph.add_edge(
        [
            "logs",
            "metrics",
            "knowledge_base",
            "history"
        ],
        "diagnosis"
    )

    """diagnosis --> remedation"""

    graph.add_edge(
        "diagnosis",
        "remediation"
    )

    """conditional routing base on risk!"""

    graph.add_conditional_edges(
        "remediation",
        route_by_risk,
        {
            "execute": "execute",
            "human_approval": "human_approval"
        }
    )

    """human approval!"""

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute": "execute",
            "replan": "replan"
        }
    )

    """execution --> verification """

    graph.add_edge(
        "execute",
        "verify"
    )

    """verification"""

    graph.add_conditional_edges(
        "verify",
        route_after_verification,
        {
            "close": "close",
            "replan": "replan"
        }
    )

    """replan!"""

    graph.add_edge(
        "replan",
        "remediation"
    )

    """close --> end!"""

    graph.add_edge(
        "close",
        END
    )

    """chekpointer"""

    checkpointer = InMemorySaver()

    app = graph.compile(
        checkpointer=checkpointer
    )

    return app


"""CREATE COMPILED APP """

app = build_graph()