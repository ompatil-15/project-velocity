"""
Input Parser Node - Validates initial merchant application data.

Validates:
- PAN format (AAAAA9999A)
- GSTIN format (99AAAAA9999A9Z9)
"""

from typing import Any, Dict, List
import re
from app.schema import AgentState, ActionItem, ActionCategory, ActionSeverity
from app.utils.simulation import sim
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_action_item(
    category: ActionCategory,
    severity: ActionSeverity,
    title: str,
    description: str,
    suggestion: str,
    field_to_update: str = None,
    current_value: str = None,
    required_format: str = None,
) -> Dict[str, Any]:
    """Create an ActionItem dictionary."""
    item = ActionItem(
        category=category,
        severity=severity,
        title=title,
        description=description,
        suggestion=suggestion,
        field_to_update=field_to_update,
        current_value=current_value,
        required_format=required_format,
    )
    return item.model_dump()


def input_parser_node(state: AgentState) -> Dict[str, Any]:
    """Validate initial application data including PAN and GSTIN formats."""
    logger.info("Input Parser node started")
    
    app_data = state.get("application_data", {})
    business_details = app_data.get("business_details", {})
    
    action_items: List[Dict[str, Any]] = []
    verification_notes = []
    
    pan = business_details.get("pan", "")
    gstin = business_details.get("gstin", "")
    
    if sim.should_skip("input"):
        logger.debug("Simulation: Skipping input validation")
        return {
            "is_auth_valid": True,
            "verification_notes": ["Input validation skipped (simulation)"],
            "action_items": [],
            "next_step": "doc_intelligence_node",
        }
    
    if sim.should_fail("input_invalid_pan"):
        logger.debug("Simulation: Invalid PAN failure")
        action_items.append(create_action_item(
            category=ActionCategory.DATA,
            severity=ActionSeverity.BLOCKING,
            title="Correct PAN number",
            description="The PAN number format is invalid (Simulated).",
            suggestion="PAN should be 10 characters: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).",
            field_to_update="business_details.pan",
            current_value=pan,
            required_format="AAAAA9999A (5 letters + 4 digits + 1 letter)",
        ))
        return {
            "is_auth_valid": False,
            "verification_notes": ["Invalid PAN format (simulation)"],
            "action_items": action_items,
            "error_message": "Invalid PAN format",
        }
    
    if sim.should_fail("input_invalid_gstin"):
        logger.debug("Simulation: Invalid GSTIN failure")
        action_items.append(create_action_item(
            category=ActionCategory.DATA,
            severity=ActionSeverity.BLOCKING,
            title="Correct GSTIN number",
            description="The GSTIN format is invalid (Simulated).",
            suggestion="GSTIN should be 15 characters with state code, PAN, and check digit.",
            field_to_update="business_details.gstin",
            current_value=gstin,
            required_format="99AAAAA9999A9Z9 (2 digit state code + PAN + 1 char + Z + check digit)",
        ))
        return {
            "is_auth_valid": False,
            "verification_notes": ["Invalid GSTIN format (simulation)"],
            "action_items": action_items,
            "error_message": "Invalid GSTIN format",
        }
    
    # PAN format validation: AAAAA9999A
    if pan and not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan.upper()):
        action_items.append(create_action_item(
            category=ActionCategory.DATA,
            severity=ActionSeverity.BLOCKING,
            title="Correct PAN number",
            description="The PAN number format is invalid.",
            suggestion="PAN should be 10 characters: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).",
            field_to_update="business_details.pan",
            current_value=pan,
            required_format="AAAAA9999A (5 letters + 4 digits + 1 letter)",
        ))
        verification_notes.append("PAN format validation: FAILED")
    else:
        verification_notes.append("PAN format validation: PASSED")
    
    # GSTIN format validation: 99AAAAA9999A9Z9
    if gstin and not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$', gstin.upper()):
        action_items.append(create_action_item(
            category=ActionCategory.DATA,
            severity=ActionSeverity.BLOCKING,
            title="Correct GSTIN number",
            description="The GSTIN format is invalid.",
            suggestion="GSTIN should be 15 characters with state code, PAN, and check digit.",
            field_to_update="business_details.gstin",
            current_value=gstin,
            required_format="99AAAAA9999A9Z9 (2 digit state code + PAN + entity code + Z + check digit)",
        ))
        verification_notes.append("GSTIN format validation: FAILED")
    else:
        verification_notes.append("GSTIN format validation: PASSED")
    
    if action_items:
        return {
            "is_auth_valid": False,
            "verification_notes": verification_notes,
            "action_items": action_items,
            "error_message": "Input validation failed",
        }
    
    entity_type = business_details.get('entity_type', 'Unknown')
    logger.debug("Processing application for entity type: %s", entity_type)
    
    return {
        "is_auth_valid": True,
        "verification_notes": verification_notes + ["Basic data validation passed"],
        "action_items": [],
        "next_step": "doc_intelligence_node",
    }
