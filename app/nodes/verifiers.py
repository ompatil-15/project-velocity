from typing import Any, Dict
import random
from app.schema import AgentState


def doc_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """
    Simulates OCR and extraction of documents.
    Corresponds to Steps 10, 11.
    """
    print("--- [Node] Doc Intelligence ---")
    # Simulate processing time or logic

    # Check if documents exist in simulated path
    # For simulation, we assume success unless specified otherwise

    return {
        "is_doc_verified": True,
        "verification_notes": ["PAN card extracted successfully", "Aadhaar verified"],
        # "next_step": "bank_verifier_node" # The graph edges will verify this, but we can hint
    }


def bank_verifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Performs Penny Drop and name match.
    Corresponds to Steps 6, 7.
    """
    print("--- [Node] Bank Verifier ---")
    bank_details = state["application_data"].get("bank_details", {})
    holder_name = bank_details.get("account_holder_name", "")

    # Failure testing: if name is "FAIL_ME", we simulate failure
    if holder_name == "FAIL_ME":
        return {
            "is_bank_verified": False,
            "error_message": "Penny drop failed: Name mismatch.",
            "next_step": "consultant_fixer_node",
        }

    return {
        "is_bank_verified": True,
        "verification_notes": ["Penny drop successful", "Name match 100%"],
    }


def finalizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generates agreement and finishes onboarding.
    Corresponds to Steps 13, 14.
    """
    print("--- [Node] Finalizer ---")

    return {
        "verification_notes": ["Agreement generated", "Settlement enabled"],
        "next_step": "END",
    }
