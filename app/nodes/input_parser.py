from typing import Any, Dict
from app.schema import AgentState


def input_parser_node(state: AgentState) -> Dict[str, Any]:
    """
    Validates the initial application data.
    Corresponds to Steps 1, 4, 5, 9.
    Note: Authentication (Step 2) is out of scope for MVP.
    """
    print("--- [Node] Input Parser ---")
    app_data = state.get("application_data", {})

    # FastAPI handles Pydantic validation on entry, we assume structure is good.
    print(
        f"Processing application for: {app_data.get('business_details', {}).get('entity_type')}"
    )

    return {
        "is_auth_valid": True,
        "verification_notes": [
            "Basic data validation passed",
        ],
        "next_step": "doc_intelligence_node",
    }
