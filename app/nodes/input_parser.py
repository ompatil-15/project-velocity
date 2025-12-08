from typing import Any, Dict
from app.schema import AgentState, MerchantApplication


def input_parser_node(state: AgentState) -> Dict[str, Any]:
    """
    Validates the initial application data.
    Corresponds to Steps 1, 2, 4, 5, 9.
    """
    print("--- [Node] Input Parser ---")
    app_data = state.get("application_data", {})

    # In a real app, we'd do deeper validation here.
    # Since FastAPI handles Pydantic validation on entry, we assume structure is good.
    # We simulate "Authentication" (Step 2) here.

    api_key = app_data.get("api_key")
    if not api_key:
        return {
            "is_auth_valid": False,
            "error_message": "Missing API Key. Authentication failed.",
            "next_step": "consultant_fixer_node",  # Route to consultant to fix
        }

    print(
        f"Processing application for: {app_data.get('business_details', {}).get('entity_type')}"
    )

    return {
        "is_auth_valid": True,
        "verification_notes": [
            "Authentication successful",
            "Basic data validation passed",
        ],
        "next_step": "doc_intelligence_node",  # Next logical step
    }
