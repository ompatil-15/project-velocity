"""
Consultant Node - Consolidates issues and generates recommendations.

This node:
- Collects action items from previous nodes
- Optionally enriches suggestions with LLM
- Calculates risk score
- Generates correction plan
"""

from typing import Any, Dict, List
from app.schema import AgentState, ActionItem, ActionCategory, ActionSeverity
from app.utils.logger import get_logger
from app.utils.llm_factory import get_llm
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
import os
import json

load_dotenv()

logger = get_logger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()


def enrich_action_items_with_llm(
    action_items: List[Dict[str, Any]], 
    state: AgentState
) -> List[Dict[str, Any]]:
    """
    Enrich action item suggestions with merchant-specific context using LLM.
    Only runs in production mode.
    """
    if not action_items:
        return action_items
    
    try:
        llm = get_llm()
        
        merchant_context = {
            "business_type": state["application_data"]["business_details"].get("entity_type", "Unknown"),
            "category": state["application_data"]["business_details"].get("category", "Unknown"),
            "website": state["application_data"]["business_details"].get("website_url", "Not provided"),
            "merchant_name": state["application_data"]["bank_details"].get("account_holder_name", "Merchant"),
        }
        
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
        
        try:
            content = response.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end > start:
                enhancements = json.loads(content[start:end])
                enhancement_map = {e.get("id", ""): e.get("enhanced_suggestion", "") for e in enhancements}
                
                for i, item in enumerate(action_items):
                    item_id = item.get("id", "")
                    if item_id in enhancement_map and enhancement_map[item_id]:
                        item["suggestion"] = f"{item['suggestion']}\n\n**Personalized Recommendation:** {enhancement_map[item_id]}"
                    elif i < len(enhancements) and enhancements[i].get("enhanced_suggestion"):
                        item["suggestion"] = f"{item['suggestion']}\n\n**Personalized Recommendation:** {enhancements[i]['enhanced_suggestion']}"
                
                logger.debug("LLM enrichment applied to %d items", len(action_items))
        except json.JSONDecodeError:
            logger.warning("Could not parse LLM response as JSON")
            
    except Exception as e:
        logger.error("LLM enrichment failed: %s", e)
    
    return action_items


def consultant_fixer_node(state: AgentState) -> Dict[str, Any]:
    """Consolidate action items and generate merchant recommendations."""
    logger.info("Consultant node started")

    error = state.get("error_message")
    existing_action_items = state.get("action_items", [])
    
    if not isinstance(existing_action_items, list):
        existing_action_items = []
    
    action_items = [item.copy() if isinstance(item, dict) else item for item in existing_action_items]
    
    logger.debug("Received %d action items for review", len(action_items))
    
    blocking_count = sum(1 for item in action_items if item.get("severity") == "BLOCKING")
    warning_count = sum(1 for item in action_items if item.get("severity") == "WARNING")
    
    correction_plan = []
    for item in action_items:
        if isinstance(item, dict):
            correction_plan.append(
                f"[{item.get('severity', 'INFO')}] {item.get('title', 'Unknown')}: {item.get('suggestion', '')[:100]}..."
            )
    
    if ENVIRONMENT == "production" and action_items:
        logger.debug("Enriching action items with LLM")
        action_items = enrich_action_items_with_llm(action_items, state)
    
    action_items.sort(key=lambda x: (
        0 if x.get("severity") == "BLOCKING" else 1,
        x.get("created_at", "")
    ))
    
    summary = []
    if blocking_count > 0:
        summary.append(f"{blocking_count} blocking issue(s) require attention")
    if warning_count > 0:
        summary.append(f"{warning_count} warning(s) for review")
    if error:
        summary.append(f"Error: {error}")
    
    risk_score = min(1.0, 0.3 + (blocking_count * 0.2) + (warning_count * 0.1))
    
    return {
        "action_items": action_items,
        "consultant_plan": correction_plan,
        "verification_notes": summary if summary else ["Consultant review completed"],
        "status": "NEEDS_REVIEW",
        "risk_score": risk_score,
    }
