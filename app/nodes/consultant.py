from typing import Any, Dict
from app.schema import AgentState
from langchain_core.messages import SystemMessage, HumanMessage
import os
from app.templates import get_template

from dotenv import load_dotenv
from app.utils.llm_factory import get_llm

load_dotenv()

# Standard Environment Configuration
# development = Simulator (Mock)
# production = Real LLM (Provider defined by LLM_PROVIDER env var)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def consultant_fixer_node(state: AgentState) -> Dict[str, Any]:
    """
    The 'Consultant Mode' node.
    Analyzes errors (bank failure, compliance issues) and suggests fixes.
    """
    print("--- [Node] Consultant Fixer ---")

    error = state.get("error_message")
    issues = state.get("compliance_issues", [])

    correction_plan = []

    # Logic to populate structured plan
    # Logic to populate structured plan
    if ENVIRONMENT == "production":
        try:
            # Factory determines provider/model/key from environment variables
            llm = get_llm()

            prompt = (
                f"You are a compliance consultant for a merchant onboarding system.\n"
                f"The merchant has encountered errors: {error}\n"
                f"Compliance Issues: {issues}\n"
                f"Provide a concise, actionable plan (3-4 bullet points) for the merchant to fix these issues.\n"
                f"Do not include introductory text, just the plan items."
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            # Simple parsing: split by newlines and clean up
            lines = [
                line.strip().lstrip("-* ")
                for line in response.content.split("\n")
                if line.strip()
            ]
            correction_plan.extend(lines)
        except Exception as e:
            correction_plan.append(f"LLM Error ({type(e).__name__}): {str(e)}")
            correction_plan.append("Switching to Simulator fallback.")

    # FALLBACK / SIMULATOR MODE
    if not correction_plan:  # Use simulator if LLM failed or mode is SIMULATOR
        if error:
            print(f"Consultant detected critical error: {error}")
            correction_plan.append(f"Action: Send email to user regarding {error}")

        if issues:
            print(f"Consultant detected compliance issues: {issues}")
            for issue in issues:
                # Simple keyword match to suggest template
                # Extract basic terms
                company = state["application_data"]["business_details"]["entity_type"]
                domain = "example.com"  # Simplification

                suggestion = f"Suggestion: Update website to include {issue}"
                correction_plan.append(suggestion)

                # Generate the artifact content
                if "Refund" in issue or "Privacy" in issue:
                    template = get_template(issue, company, domain)
                    correction_plan.append(f"DRAFT CONTENT for {issue}:\n{template}")

    # Update state with richer data
    return {
        "consultant_plan": correction_plan,
        "verification_notes": [
            f"Consultant Intervention: {p}" for p in correction_plan
        ],
        "status": "NEEDS_REVIEW",
        "risk_score": 0.8 if issues else 0.5,  # High risk if issues found
    }
