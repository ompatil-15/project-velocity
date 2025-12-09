"""
Input Parser Node - Validates initial application data.

INPUT:
  - application_data.business_details.pan
  - application_data.business_details.gstin

OUTPUT:
  - is_auth_valid: bool
  - action_items: validation errors (if any)
  - next_step: "doc_intelligence_node" if valid

TOOLS:
  - validate_pan
  - validate_gstin
"""

from typing import Any, Dict
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity


class InputParserNode(BaseNode):
    """
    Validates the initial merchant application data.
    
    Checks:
    - PAN format
    - GSTIN format
    
    Future enhancements:
    - PAN-GSTIN cross-validation
    - Business name extraction from PAN
    - LLM-based entity type validation
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="input_parser_node",
            display_name="Input Parser",
            description="Validates initial application data (PAN, GSTIN formats)",
            stage="INPUT",
            available_tools=["validate_pan", "validate_gstin"],
            simulation_key="input",
            llm=LLMConfig(
                enabled=False,  # Can enable for entity type validation
                system_prompt="You are validating merchant business information."
            ),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Validate PAN and GSTIN from application data.
        """
        self._log("Validating input data...")
        
        business_details = input.application_data.get("business_details", {})
        pan = business_details.get("pan", "")
        gstin = business_details.get("gstin", "")
        
        action_items = []
        
        # --- Force Success Mode ---
        if self.should_skip_checks():
            self._add_note("SIMULATION: Input validation skipped (force_success)")
            return NodeOutput(
                state_updates={
                    "is_auth_valid": True,
                    "stage": "INPUT",
                },
                action_items=[],
                verification_notes=["Input validation passed (simulated)"],
                next_node="doc_intelligence_node",
            )
        
        # --- Simulate Failures ---
        if self.should_simulate_failure("invalid_pan"):
            self._add_note("SIMULATION: Invalid PAN failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.DATA,
                severity=ActionSeverity.BLOCKING,
                title="Correct PAN number",
                description="The PAN number format is invalid (Simulated).",
                suggestion="PAN should be 10 characters: 5 letters, 4 digits, 1 letter.",
                field_to_update="business_details.pan",
                current_value=pan,
                required_format="AAAAA9999A",
            ))
            return NodeOutput(
                state_updates={
                    "is_auth_valid": False,
                    "error_message": "Invalid PAN format (simulated)",
                    "stage": "INPUT",
                },
                action_items=action_items,
                verification_notes=["PAN validation failed (simulated)"],
            )
        
        if self.should_simulate_failure("invalid_gstin"):
            self._add_note("SIMULATION: Invalid GSTIN failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.DATA,
                severity=ActionSeverity.BLOCKING,
                title="Correct GSTIN number",
                description="The GSTIN format is invalid (Simulated).",
                suggestion="GSTIN should be 15 characters.",
                field_to_update="business_details.gstin",
                current_value=gstin,
                required_format="99AAAAA9999A9Z9",
            ))
            return NodeOutput(
                state_updates={
                    "is_auth_valid": False,
                    "error_message": "Invalid GSTIN format (simulated)",
                    "stage": "INPUT",
                },
                action_items=action_items,
                verification_notes=["GSTIN validation failed (simulated)"],
            )
        
        # --- Real Validation using Tools ---
        
        # Validate PAN
        if pan:
            pan_result = self.call_tool("validate_pan", {"pan": pan})
            if pan_result.success and pan_result.data:
                if pan_result.data.get("valid"):
                    self._add_note(f"PAN valid: {pan_result.data.get('parsed', {}).get('holder_type', 'N/A')}")
                else:
                    action_items.append(self.create_action_item(
                        category=ActionCategory.DATA,
                        severity=ActionSeverity.BLOCKING,
                        title="Correct PAN number",
                        description=pan_result.data.get("error", "Invalid PAN format"),
                        suggestion="PAN should be 10 characters: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).",
                        field_to_update="business_details.pan",
                        current_value=pan,
                        required_format="AAAAA9999A",
                    ))
        
        # Validate GSTIN
        if gstin:
            gstin_result = self.call_tool("validate_gstin", {"gstin": gstin})
            if gstin_result.success and gstin_result.data:
                if gstin_result.data.get("valid"):
                    self._add_note(f"GSTIN valid: state {gstin_result.data.get('parsed', {}).get('state_code', 'N/A')}")
                else:
                    action_items.append(self.create_action_item(
                        category=ActionCategory.DATA,
                        severity=ActionSeverity.BLOCKING,
                        title="Correct GSTIN number",
                        description=gstin_result.data.get("error", "Invalid GSTIN format"),
                        suggestion="GSTIN should be 15 characters with state code, PAN, and check digit.",
                        field_to_update="business_details.gstin",
                        current_value=gstin,
                        required_format="99AAAAA9999A9Z9",
                    ))
        
        # --- Determine Result ---
        if action_items:
            return NodeOutput(
                state_updates={
                    "is_auth_valid": False,
                    "error_message": "Input validation failed",
                    "stage": "INPUT",
                },
                action_items=action_items,
                verification_notes=["Input validation failed - see action items"],
            )
        
        # All validations passed
        entity_type = business_details.get("entity_type", "Unknown")
        self._add_note(f"Processing {entity_type} merchant")
        
        return NodeOutput(
            state_updates={
                "is_auth_valid": True,
                "stage": "INPUT",
            },
            action_items=[],
            verification_notes=["Basic data validation passed"],
            next_node="doc_intelligence_node",
        )


# Create callable for LangGraph
input_parser_node = InputParserNode()

