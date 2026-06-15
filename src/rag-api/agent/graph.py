# =============================================================================
# ENTERPRISE AGENTIC RAG — LANGGRAPH GRAPH DEFINITION
# =============================================================================

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

from .state import RAGState
from .nodes import AgentNodes
from ..core.config import Settings


def create_agent_graph(settings: Settings, checkpointer=None):
    """Create the Agentic RAG LangGraph"""

    nodes = AgentNodes(settings)

    # Build graph
    workflow = StateGraph(RAGState)

    # Add nodes
    workflow.add_node("plan", nodes.plan)
    workflow.add_node("guardrails_input", nodes.guardrails_check)
    workflow.add_node("retrieve", nodes.retrieve)
    workflow.add_node("rerank", nodes.rerank)
    workflow.add_node("generate", nodes.generate)
    workflow.add_node("reflect", nodes.reflect)
    workflow.add_node("guardrails_output", nodes.guardrails_check)

    # Define edges
    workflow.set_entry_point("plan")

    # Plan → Input Guardrails
    workflow.add_edge("plan", "guardrails_input")

    # Input Guardrails → Retrieve (if passed) or END (if failed)
    def check_input_guardrails(state: RAGState) -> Literal["retrieve", "end_failed"]:
        if state.get("guardrails_passed", True):
            return "retrieve"
        return "end_failed"

    workflow.add_conditional_edges(
        "guardrails_input",
        check_input_guardrails,
        {"retrieve": "retrieve", "end_failed": END}
    )

    # Retrieve → Rerank
    workflow.add_edge("retrieve", "rerank")

    # Rerank → Generate
    workflow.add_edge("rerank", "generate")

    # Generate → Output Guardrails
    workflow.add_edge("generate", "guardrails_output")

    # Output Guardrails → Reflect or End
    def check_output_guardrails(state: RAGState) -> Literal["reflect", "end_blocked"]:
        if state.get("guardrails_passed", True):
            return "reflect"
        # Modify answer with safe response
        state["answer"] = "I cannot provide an answer due to safety guidelines."
        state["citations"] = []
        return "end_blocked"

    workflow.add_conditional_edges(
        "guardrails_output",
        check_output_guardrails,
        {"reflect": "reflect", "end_blocked": END}
    )

    # Reflect → Retrieve (if needs more) or End
    def should_continue(state: RAGState) -> Literal["retrieve", "end"]:
        if state.get("needs_more_info", False) and state["iterations"] < state["max_iterations"]:
            return "retrieve"
        return "end"

    workflow.add_conditional_edges(
        "reflect",
        should_continue,
        {"retrieve": "retrieve", "end": END}
    )

    # Compile with checkpointer
    if checkpointer is None:
        # Use SQLite for local, Postgres for production
        if settings.DATABASE_URL:
            checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
        else:
            checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["guardrails_output"],  # Allow human review
    )

    return app


def create_simple_rag_graph(settings: Settings, checkpointer=None):
    """Simple RAG without agentic loop (for starter tier)"""

    nodes = AgentNodes(settings)

    workflow = StateGraph(RAGState)

    workflow.add_node("guardrails_input", nodes.guardrails_check)
    workflow.add_node("retrieve", nodes.retrieve)
    workflow.add_node("rerank", nodes.rerank)
    workflow.add_node("generate", nodes.generate)
    workflow.add_node("guardrails_output", nodes.guardrails_check)

    workflow.set_entry_point("guardrails_input")

    workflow.add_conditional_edges(
        "guardrails_input",
        lambda s: "retrieve" if s.get("guardrails_passed", True) else END,
        {"retrieve": "retrieve"}
    )

    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", "guardrails_output")

    workflow.add_conditional_edges(
        "guardrails_output",
        lambda s: END,
        {}
    )

    if checkpointer is None:
        if settings.DATABASE_URL:
            checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
        else:
            checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

    return workflow.compile(checkpointer=checkpointer)


# Export for API
__all__ = ["create_agent_graph", "create_simple_rag_graph"]