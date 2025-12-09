"""
Graph V2 - New architecture with BaseNode and Tool Registry.

This is the new version of the workflow graph that uses:
- BaseNode classes with clear contracts
- Tool registry for all external operations
- Standardized inputs/outputs

To use this instead of the old graph:
1. Import build_graph from app.graph_v2 instead of app.graph
2. Or set GRAPH_VERSION=v2 in your environment

The nodes are backward compatible with LangGraph - they still
accept AgentState and return Dict[str, Any].
"""

from typing import Literal
from langgraph.graph import StateGraph, END
import os

from app.schema import AgentState

# Import tools to register them
from app.core import tools  # noqa: F401

# Import new node instances
from app.core.nodes import (
    InputParserNode,
    DocIntelligenceNode,
    BankVerifierNode,
    WebComplianceNode,
    ConsultantNode,
    FinalizerNode,
)


def build_graph():
    """
    Build the workflow graph using new architecture nodes.
    
    The graph structure is the same as v1, but nodes use:
    - Clear input/output contracts
    - Tool registry for external calls
    - Simulation support built-in
    """
    workflow = StateGraph(AgentState)
    
    # Create node instances
    input_parser = InputParserNode()
    doc_intelligence = DocIntelligenceNode()
    bank_verifier = BankVerifierNode()
    web_compliance = WebComplianceNode()
    consultant = ConsultantNode()
    finalizer = FinalizerNode()
    
    # Add Nodes (using __call__ method which bridges to process())
    workflow.add_node("input_parser_node", input_parser)
    workflow.add_node("doc_intelligence_node", doc_intelligence)
    workflow.add_node("bank_verifier_node", bank_verifier)
    workflow.add_node("web_compliance_node", web_compliance)
    workflow.add_node("consultant_fixer_node", consultant)
    workflow.add_node("finalizer_node", finalizer)
    
    # Define Conditional Logic (same as v1)
    def check_auth(
        state: AgentState,
    ) -> Literal["doc_intelligence_node", "consultant_fixer_node"]:
        if state.get("is_auth_valid"):
            return "doc_intelligence_node"
        return "consultant_fixer_node"
    
    def check_docs(
        state: AgentState,
    ) -> Literal["bank_verifier_node", "consultant_fixer_node"]:
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
    workflow.add_conditional_edges("doc_intelligence_node", check_docs)
    workflow.add_conditional_edges("bank_verifier_node", check_bank)
    workflow.add_conditional_edges("web_compliance_node", check_compliance)
    
    # Consultant routes back to input for retry
    workflow.add_edge("consultant_fixer_node", "input_parser_node")
    
    # Finalizer -> END
    workflow.add_edge("finalizer_node", END)
    
    return workflow


def get_node_configs():
    """
    Get configuration for all nodes.
    
    Useful for:
    - Documentation generation
    - Admin UI display
    - Debugging
    """
    return {
        "input_parser_node": InputParserNode.get_config().model_dump(),
        "doc_intelligence_node": DocIntelligenceNode.get_config().model_dump(),
        "bank_verifier_node": BankVerifierNode.get_config().model_dump(),
        "web_compliance_node": WebComplianceNode.get_config().model_dump(),
        "consultant_fixer_node": ConsultantNode.get_config().model_dump(),
        "finalizer_node": FinalizerNode.get_config().model_dump(),
    }


def get_available_tools():
    """
    Get all registered tools.
    
    Useful for:
    - Documentation
    - LLM function calling setup
    """
    from app.core.tool_registry import tool_registry
    
    return [tool.model_dump() for tool in tool_registry.get_all_definitions()]

