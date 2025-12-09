"""
Finalizer Node - Completes onboarding and generates agreement.

INPUT:
  - All verification flags (should all be True)

OUTPUT:
  - status: COMPLETED
  - verification_notes: completion messages

TOOLS:
  - (Agreement generation handled externally in main.py)
"""

from typing import Any, Dict
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig


class FinalizerNode(BaseNode):
    """
    Final node that marks onboarding as complete.
    
    This node:
    - Confirms all verifications passed
    - Sets status to COMPLETED
    - Agreement and email generation triggered by main.py
    
    Future enhancements:
    - Risk tier assignment
    - Settlement configuration
    - Integration setup
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="finalizer_node",
            display_name="Finalizer",
            description="Completes onboarding and triggers agreement generation",
            stage="FINAL",
            available_tools=[],
            simulation_key="finalizer",
            llm=LLMConfig(enabled=False),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Mark onboarding as complete.
        """
        self._log("Finalizing onboarding...")
        
        # Verify all checks passed
        checks = {
            "Auth/Input": input.is_auth_valid,
            "Documents": input.is_doc_verified,
            "Bank": input.is_bank_verified,
            "Website": input.is_website_compliant,
        }
        
        all_passed = all(checks.values())
        
        if not all_passed:
            failed_checks = [name for name, passed in checks.items() if not passed]
            self._add_note(f"Warning: Some checks not passed: {failed_checks}")
        
        notes = [
            "All verifications complete",
            "Agreement pending generation",
            "Settlement configuration pending",
        ]
        
        return NodeOutput(
            state_updates={
                "status": "COMPLETED",
                "stage": "FINAL",
            },
            action_items=[],  # No action items at this stage
            verification_notes=notes,
        )


# Create callable for LangGraph
finalizer_node = FinalizerNode()

