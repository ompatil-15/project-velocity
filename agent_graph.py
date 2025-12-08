from typing import Literal
from langgraph.graph import StateGraph, END

from schema import AgentState
from nodes.input_parser import input_parser_node
from nodes.verifiers import doc_intelligence_node, bank_verifier_node, finalizer_node
from nodes.consultant import consultant_fixer_node
from nodes.web_compliance import web_compliance_node


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

    # Finalizer -> END
    workflow.add_edge("finalizer_node", END)

    # Consultant -> END (Manual Review)
    workflow.add_edge("consultant_fixer_node", END)

    return workflow.compile()


# Global graph instance
graph = build_graph()
