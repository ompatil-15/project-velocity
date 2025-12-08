from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import aiosqlite

from app.schema import AgentState
from app.nodes.input_parser import input_parser_node
from app.nodes.verifiers import (
    doc_intelligence_node,
    bank_verifier_node,
    finalizer_node,
)
from app.nodes.consultant import consultant_fixer_node
from app.nodes.web_compliance import web_compliance_node


def build_graph():
    workflow = StateGraph(AgentState)

    # Add Nodes
    workflow.add_node("input_parser_node", input_parser_node)
    workflow.add_node("doc_intelligence_node", doc_intelligence_node)
    workflow.add_node("bank_verifier_node", bank_verifier_node)
    workflow.add_node("web_compliance_node", web_compliance_node)
    workflow.add_node("consultant_fixer_node", consultant_fixer_node)
    workflow.add_node("finalizer_node", finalizer_node)

    # Define Conditional Logic

    def check_auth(
        state: AgentState,
    ) -> Literal["doc_intelligence_node", "consultant_fixer_node"]:
        if state.get("is_auth_valid"):
            return "doc_intelligence_node"
        return "consultant_fixer_node"

    def check_docs(
        state: AgentState,
    ) -> Literal["bank_verifier_node", "consultant_fixer_node"]:
        # Assuming doc always passes for now, but good to have logic
        if state.get("is_doc_verified"):
            return "bank_verifier_node"
        return "consultant_fixer_node"

    def check_bank(
        state: AgentState,
    ) -> Literal["web_compliance_node", "consultant_fixer_node"]:
        if state.get("is_bank_verified"):
            return "web_compliance_node"
        return "consultant_fixer_node"

    def check_compliance(
        state: AgentState,
    ) -> Literal["finalizer_node", "consultant_fixer_node"]:
        if state.get("is_website_compliant"):
            return "finalizer_node"
        return "consultant_fixer_node"

    # Add Edges
    workflow.set_entry_point("input_parser_node")

    workflow.add_conditional_edges("input_parser_node", check_auth)

    # Doc intelligence -> Bank Verifier (Assuming pass)
    workflow.add_edge("doc_intelligence_node", "bank_verifier_node")

    # Bank Verifier -> Web Compliance or Consultant
    workflow.add_conditional_edges("bank_verifier_node", check_bank)

    # Web Compliance -> Finalizer or Consultant
    workflow.add_conditional_edges("web_compliance_node", check_compliance)

    # Consultant Logic for Retry
    # If consultant runs, it means there was an error.
    # After user interaction (resume), we want to loop back to the *beginning* or the specific check.
    # For simplicity, let's route Consultant back to 'input_parser_node' (re-validate everything).

    workflow.add_edge("consultant_fixer_node", "input_parser_node")

    # Finalizer -> END
    workflow.add_edge("finalizer_node", END)

    # For the global instance, we will not compile here with checkpointer.
    # Instead we return the workflow and let main.py handle the compilation with the async checkpointer.

    return workflow


# We no longer export a compiled 'graph' here.
# Main.py will use build_graph() and compile it with the checkpointer.
