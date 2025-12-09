"""
Bank Verifier Node - Performs penny drop and account validation.

INPUT:
  - application_data.bank_details.account_number
  - application_data.bank_details.ifsc
  - application_data.bank_details.account_holder_name

OUTPUT:
  - is_bank_verified: bool
  - action_items: bank issues (if any)

TOOLS:
  - validate_ifsc
  - validate_account_number
  - penny_drop_verify
  - lookup_ifsc
"""

from typing import Any, Dict
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity


class BankVerifierNode(BaseNode):
    """
    Verifies bank account details using penny drop.
    
    Checks:
    - IFSC format
    - Account number format
    - Penny drop verification
    - Name matching
    
    Future enhancements:
    - Bank statement analysis
    - UPI verification
    - Multi-account support
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="bank_verifier_node",
            display_name="Bank Verifier",
            description="Verifies bank account via penny drop and name matching",
            stage="BANK",
            available_tools=[
                "validate_ifsc",
                "validate_account_number",
                "penny_drop_verify",
                "lookup_ifsc",
            ],
            simulation_key="bank",
            llm=LLMConfig(
                enabled=False,
                system_prompt="You are verifying merchant bank details."
            ),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Verify bank account details.
        """
        self._log("Verifying bank details...")
        
        bank_details = input.application_data.get("bank_details", {})
        account_number = bank_details.get("account_number", "")
        ifsc = bank_details.get("ifsc", "")
        holder_name = bank_details.get("account_holder_name", "")
        
        action_items = []
        
        # --- Force Success Mode ---
        if self.should_skip_checks():
            self._add_note("SIMULATION: Bank checks skipped (force_success)")
            return NodeOutput(
                state_updates={
                    "is_bank_verified": True,
                    "stage": "BANK",
                },
                action_items=[],
                verification_notes=["Bank verification passed (simulated)"],
            )
        
        # --- Simulate Failures ---
        if self.should_simulate_failure("name_mismatch") or holder_name == "FAIL_ME":
            self._add_note("SIMULATION: Bank name mismatch failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.BANK,
                severity=ActionSeverity.BLOCKING,
                title="Correct bank account holder name",
                description="The name on the bank account does not match the business name.",
                suggestion="Ensure the account holder name matches exactly with your business registration.",
                field_to_update="bank_details.account_holder_name",
                current_value=holder_name,
                required_format="Full name as it appears on bank account.",
            ))
            return NodeOutput(
                state_updates={
                    "is_bank_verified": False,
                    "error_message": "Penny drop failed: Name mismatch",
                    "stage": "BANK",
                },
                action_items=action_items,
            )
        
        if self.should_simulate_failure("invalid_ifsc"):
            self._add_note("SIMULATION: Invalid IFSC failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.BANK,
                severity=ActionSeverity.BLOCKING,
                title="Correct IFSC code",
                description="The IFSC code is invalid or does not match any bank branch.",
                suggestion="Verify the IFSC from your cheque book or bank statement.",
                field_to_update="bank_details.ifsc",
                current_value=ifsc,
                required_format="11 characters: AAAA0BBBBBB (e.g., HDFC0001234)",
            ))
            return NodeOutput(
                state_updates={
                    "is_bank_verified": False,
                    "error_message": "Invalid IFSC code",
                    "stage": "BANK",
                },
                action_items=action_items,
            )
        
        if self.should_simulate_failure("account_closed"):
            self._add_note("SIMULATION: Account closed failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.BANK,
                severity=ActionSeverity.BLOCKING,
                title="Provide active bank account",
                description="The bank account appears to be closed or inactive.",
                suggestion="Please provide details of an active bank account.",
                field_to_update="bank_details.account_number",
                current_value=account_number,
                required_format="Active savings or current account.",
            ))
            return NodeOutput(
                state_updates={
                    "is_bank_verified": False,
                    "error_message": "Bank account is closed/inactive",
                    "stage": "BANK",
                },
                action_items=action_items,
            )
        
        # --- Real Validation ---
        
        # Check for missing details
        if not account_number or not ifsc:
            action_items.append(self.create_action_item(
                category=ActionCategory.BANK,
                severity=ActionSeverity.BLOCKING,
                title="Provide complete bank details",
                description="Bank account number or IFSC code is missing.",
                suggestion="Please provide complete bank account details.",
                field_to_update="bank_details",
                required_format="Account: 9-18 digits. IFSC: 11 chars.",
            ))
            return NodeOutput(
                state_updates={
                    "is_bank_verified": False,
                    "error_message": "Incomplete bank details",
                    "stage": "BANK",
                },
                action_items=action_items,
            )
        
        # Validate IFSC format
        ifsc_result = self.call_tool("validate_ifsc", {"ifsc": ifsc})
        if ifsc_result.success and ifsc_result.data:
            if not ifsc_result.data.get("valid"):
                action_items.append(self.create_action_item(
                    category=ActionCategory.BANK,
                    severity=ActionSeverity.BLOCKING,
                    title="Correct IFSC code",
                    description=ifsc_result.data.get("error", "Invalid IFSC format"),
                    suggestion="IFSC should be 11 characters: 4 letters + 0 + 6 alphanumeric.",
                    field_to_update="bank_details.ifsc",
                    current_value=ifsc,
                    required_format="AAAA0BBBBBB",
                ))
        
        # Validate account number format
        acct_result = self.call_tool("validate_account_number", {"account_number": account_number})
        if acct_result.success and acct_result.data:
            if not acct_result.data.get("valid"):
                action_items.append(self.create_action_item(
                    category=ActionCategory.BANK,
                    severity=ActionSeverity.BLOCKING,
                    title="Correct account number",
                    description=acct_result.data.get("error", "Invalid account number"),
                    suggestion="Account number should be 9-18 digits.",
                    field_to_update="bank_details.account_number",
                    current_value=account_number,
                ))
        
        # If format validation failed, return early
        if action_items:
            return NodeOutput(
                state_updates={
                    "is_bank_verified": False,
                    "error_message": "Bank details validation failed",
                    "stage": "BANK",
                },
                action_items=action_items,
            )
        
        # Perform penny drop verification
        penny_result = self.call_tool("penny_drop_verify", {
            "account_number": account_number,
            "ifsc": ifsc,
            "expected_name": holder_name,
        })
        
        if penny_result.success and penny_result.data:
            if penny_result.data.get("verified"):
                bank_name = penny_result.data.get("bank_name", "Unknown Bank")
                match_score = penny_result.data.get("name_match_score", 0)
                
                self._add_note(f"Penny drop successful. Bank: {bank_name}, Match: {match_score:.0%}")
                
                return NodeOutput(
                    state_updates={
                        "is_bank_verified": True,
                        "stage": "BANK",
                    },
                    verification_notes=[
                        "Penny drop successful",
                        f"Bank: {bank_name}",
                        f"Name match: {match_score:.0%}",
                    ],
                )
            else:
                action_items.append(self.create_action_item(
                    category=ActionCategory.BANK,
                    severity=ActionSeverity.BLOCKING,
                    title="Verify bank account details",
                    description=penny_result.data.get("error", "Penny drop verification failed"),
                    suggestion="Please verify and re-enter your bank details.",
                    field_to_update="bank_details",
                ))
        
        return NodeOutput(
            state_updates={
                "is_bank_verified": False,
                "error_message": "Bank verification failed",
                "stage": "BANK",
            },
            action_items=action_items,
        )


# Create callable for LangGraph
bank_verifier_node = BankVerifierNode()

