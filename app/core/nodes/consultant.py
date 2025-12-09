"""
Consultant Node - Consolidates issues and generates recommendations.

INPUT:
  - existing_action_items: list of action items from previous nodes
  - All verification flags

OUTPUT:
  - action_items: enriched/consolidated action items
  - consultant_plan: summary of recommendations
  - risk_score: calculated risk score
  - status: NEEDS_REVIEW

TOOLS:
  - (None currently, but can add LLM-based enrichment)
"""

from typing import Any, Dict, List
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity
import json


class ConsultantNode(BaseNode):
    """
    Consolidates action items and generates merchant recommendations.
    
    This node:
    - Collects all action items from previous nodes
    - Sorts by severity (BLOCKING first)
    - Optionally enriches with LLM for personalized suggestions
    - Calculates risk score
    - Generates a summary plan
    
    Future enhancements:
    - LLM-based suggestion personalization
    - Industry-specific recommendations
    - Risk model integration
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="consultant_fixer_node",
            display_name="Consultant",
            description="Consolidates issues and generates personalized recommendations",
            stage="FINAL",
            available_tools=[],  # Can add LLM enrichment tool
            simulation_key="consultant",
            llm=LLMConfig(
                enabled=True,  # Enable for personalized suggestions
                system_prompt="""You are a compliance consultant helping a merchant complete their payment gateway onboarding.
                
Your role is to:
1. Provide clear, actionable suggestions
2. Personalize recommendations based on the merchant's business type
3. Prioritize the most critical issues first
4. Be encouraging but professional"""
            ),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Consolidate and enrich action items.
        """
        self._log("Consolidating issues and generating recommendations...")
        
        # Collect existing action items
        action_items = list(input.existing_action_items or [])
        
        self._add_note(f"Received {len(action_items)} action items")
        
        # Count by severity
        blocking_count = sum(1 for item in action_items if item.get("severity") == "BLOCKING")
        warning_count = sum(1 for item in action_items if item.get("severity") == "WARNING")
        
        # Sort: BLOCKING first, then WARNING, then by created_at
        action_items.sort(key=lambda x: (
            0 if x.get("severity") == "BLOCKING" else 1,
            x.get("created_at", "")
        ))
        
        # Generate correction plan summary
        correction_plan = []
        for item in action_items:
            severity = item.get("severity", "INFO")
            title = item.get("title", "Unknown")
            suggestion = item.get("suggestion", "")[:100]
            correction_plan.append(f"[{severity}] {title}: {suggestion}...")
        
        # Optionally enrich with LLM
        if self.config.llm.enabled and action_items:
            action_items = self._enrich_with_llm(action_items, input)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(blocking_count, warning_count)
        
        # Build summary notes
        summary = []
        if blocking_count > 0:
            summary.append(f"{blocking_count} blocking issue(s) require attention")
        if warning_count > 0:
            summary.append(f"{warning_count} warning(s) for review")
        
        error = input.existing_notes[-1] if input.existing_notes else None
        if error and "error" in error.lower():
            summary.append(error)
        
        return NodeOutput(
            state_updates={
                "status": "NEEDS_REVIEW",
                "risk_score": risk_score,
                "consultant_plan": correction_plan,
            },
            action_items=action_items,
            verification_notes=summary if summary else ["Consultant review completed"],
        )
    
    def _calculate_risk_score(self, blocking: int, warnings: int) -> float:
        """
        Calculate risk score from 0.0 (low risk) to 1.0 (high risk).
        """
        base_score = 0.3
        score = base_score + (blocking * 0.2) + (warnings * 0.1)
        return min(1.0, round(score, 2))
    
    def _enrich_with_llm(
        self, 
        action_items: List[Dict[str, Any]], 
        input: NodeInput
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to add personalized suggestions to action items.
        """
        try:
            # Build merchant context
            business_details = input.application_data.get("business_details", {})
            context = {
                "business_type": business_details.get("entity_type", "Unknown"),
                "category": business_details.get("category", "Unknown"),
                "website": business_details.get("website_url", "Not provided"),
            }
            
            # Build items summary
            items_summary = "\n".join([
                f"- {item['title']}: {item['description']}"
                for item in action_items
            ])
            
            prompt = f"""Merchant Context:
- Business Type: {context['business_type']}
- Category: {context['category']}
- Website: {context['website']}

Current Issues:
{items_summary}

For each issue, provide a brief personalized suggestion based on the merchant's business type.
Return ONLY a JSON array with objects containing:
- "id": the item ID (if available)
- "enhanced_suggestion": personalized recommendation (1-2 sentences)

Output ONLY valid JSON."""

            response = self.call_llm(prompt)
            
            if response:
                # Parse response and merge
                try:
                    start = response.find('[')
                    end = response.rfind(']') + 1
                    if start != -1 and end > start:
                        enhancements = json.loads(response[start:end])
                        
                        enhancement_map = {
                            e.get("id", ""): e.get("enhanced_suggestion", "") 
                            for e in enhancements
                        }
                        
                        for i, item in enumerate(action_items):
                            item_id = item.get("id", "")
                            enhanced = enhancement_map.get(item_id, "")
                            
                            if not enhanced and i < len(enhancements):
                                enhanced = enhancements[i].get("enhanced_suggestion", "")
                            
                            if enhanced:
                                item["suggestion"] = f"{item['suggestion']}\n\n**Personalized:** {enhanced}"
                        
                        self._add_note("LLM enrichment applied")
                except json.JSONDecodeError:
                    self._add_note("Could not parse LLM response")
                    
        except Exception as e:
            self._add_note(f"LLM enrichment failed: {e}")
        
        return action_items


# Create callable for LangGraph
consultant_fixer_node = ConsultantNode()

