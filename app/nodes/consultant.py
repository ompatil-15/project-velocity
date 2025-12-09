from typing import Any, Dict, List
from app.schema import AgentState, ActionItem, ActionCategory, ActionSeverity
from langchain_core.messages import HumanMessage
import os
import json

from dotenv import load_dotenv
from app.utils.llm_factory import get_llm

load_dotenv()

# Standard Environment Configuration
# development = Simulator (Mock)
# production = Real LLM (Provider defined by LLM_PROVIDER env var)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def enrich_action_items_with_llm(
    action_items: List[Dict[str, Any]], 
    state: AgentState
) -> List[Dict[str, Any]]:
    """
    Use LLM to enrich action item suggestions with merchant-specific context.
    Only runs in production mode.
    """
    if not action_items:
        return action_items
    
    try:
        llm = get_llm()
        
        # Build context from merchant data
        merchant_context = {
            "business_type": state["application_data"]["business_details"].get("entity_type", "Unknown"),
            "category": state["application_data"]["business_details"].get("category", "Unknown"),
            "website": state["application_data"]["business_details"].get("website_url", "Not provided"),
            "merchant_name": state["application_data"]["bank_details"].get("account_holder_name", "Merchant"),
        }
        
        # Prepare action items for LLM
        items_summary = "\n".join([
            f"- {item['title']}: {item['description']}"
            for item in action_items
        ])
        
        prompt = f"""You are a compliance consultant helping a merchant complete their onboarding.

MERCHANT CONTEXT:
- Business Type: {merchant_context['business_type']}
- Category: {merchant_context['category']}
- Website: {merchant_context['website']}
- Name: {merchant_context['merchant_name']}

CURRENT ACTION ITEMS:
{items_summary}

For each action item, provide a more personalized and specific suggestion based on the merchant's context.
Return ONLY a JSON array with the same number of items, each containing:
- "id": the original item ID (if available)
- "enhanced_suggestion": a more specific, personalized suggestion

Example output:
[
  {{"id": "abc123", "enhanced_suggestion": "Since you're in e-commerce, add a clear 30-day return policy with easy RMA process..."}}
]

Output ONLY valid JSON, no additional text."""

        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Parse LLM response
        try:
            # Find JSON in response
            content = response.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                enhancements = json.loads(content[start:end])
                
                # Merge enhancements back into action items
                enhancement_map = {e.get("id", ""): e.get("enhanced_suggestion", "") for e in enhancements}
                
                for i, item in enumerate(action_items):
                    item_id = item.get("id", "")
                    if item_id in enhancement_map and enhancement_map[item_id]:
                        # Append LLM suggestion to existing suggestion
                        item["suggestion"] = f"{item['suggestion']}\n\n**Personalized Recommendation:** {enhancement_map[item_id]}"
                    elif i < len(enhancements) and enhancements[i].get("enhanced_suggestion"):
                        # Fallback to index-based matching
                        item["suggestion"] = f"{item['suggestion']}\n\n**Personalized Recommendation:** {enhancements[i]['enhanced_suggestion']}"
        except json.JSONDecodeError:
            print(f"Could not parse LLM response as JSON: {response.content[:200]}")
            
    except Exception as e:
        print(f"LLM enrichment failed: {e}")
        # Return original items if enrichment fails
    
    return action_items


def consultant_fixer_node(state: AgentState) -> Dict[str, Any]:
    """
    The 'Consultant Mode' node.
    Consolidates action items from previous nodes and optionally enriches with LLM.
    """
    print("--- [Node] Consultant Fixer ---")

    error = state.get("error_message")
    issues = state.get("compliance_issues", [])
    
    # Collect existing action items from state (from previous nodes)
    existing_action_items = state.get("action_items", [])
    
    # Ensure it's a list
    if not isinstance(existing_action_items, list):
        existing_action_items = []
    
    # Make a copy to avoid mutating state
    action_items = [item.copy() if isinstance(item, dict) else item for item in existing_action_items]
    
    print(f"Consultant received {len(action_items)} action items")
    
    # Count blocking vs warning items
    blocking_count = sum(1 for item in action_items if item.get("severity") == "BLOCKING")
    warning_count = sum(1 for item in action_items if item.get("severity") == "WARNING")
    
    # Generate correction plan from action items
    correction_plan = []
    for item in action_items:
        if isinstance(item, dict):
            correction_plan.append(f"[{item.get('severity', 'INFO')}] {item.get('title', 'Unknown')}: {item.get('suggestion', '')[:100]}...")
    
    # Enrich with LLM in production mode
    if ENVIRONMENT == "production" and action_items:
        print("Enriching action items with LLM...")
        action_items = enrich_action_items_with_llm(action_items, state)
    
    # Sort action items: BLOCKING first, then WARNING
    action_items.sort(key=lambda x: (
        0 if x.get("severity") == "BLOCKING" else 1,
        x.get("created_at", "")
    ))
    
    # Build summary for verification notes
    summary = []
    if blocking_count > 0:
        summary.append(f"{blocking_count} blocking issue(s) require attention")
    if warning_count > 0:
        summary.append(f"{warning_count} warning(s) for review")
    if error:
        summary.append(f"Error: {error}")
    
    # Calculate risk score based on issues
    risk_score = min(1.0, 0.3 + (blocking_count * 0.2) + (warning_count * 0.1))
    
    return {
        "action_items": action_items,
        "consultant_plan": correction_plan,
        "verification_notes": summary if summary else ["Consultant review completed"],
        "status": "NEEDS_REVIEW",
        "risk_score": risk_score,
    }
