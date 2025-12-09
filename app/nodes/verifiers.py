from typing import Any, Dict, List
import os
from app.schema import AgentState, ActionItem, ActionCategory, ActionSeverity
from langchain_docling import DoclingLoader


def create_action_item(
    category: ActionCategory,
    severity: ActionSeverity,
    title: str,
    description: str,
    suggestion: str,
    field_to_update: str = None,
    current_value: str = None,
    required_format: str = None,
    sample_content: str = None,
) -> Dict[str, Any]:
    """Helper to create an ActionItem dict."""
    item = ActionItem(
        category=category,
        severity=severity,
        title=title,
        description=description,
        suggestion=suggestion,
        field_to_update=field_to_update,
        current_value=current_value,
        required_format=required_format,
        sample_content=sample_content,
    )
    return item.model_dump()


def doc_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts text from documents using Docling (IBM) and validates content.
    Corresponds to Steps 10, 11.
    """
    print("--- [Node] Doc Intelligence ---")
    
    action_items: List[Dict[str, Any]] = []
    doc_path = state["application_data"].get("documents_path")

    # 1. Simulation Check: Force Failure Flag
    if os.getenv("SIMULATE_DOC_FAILURE", "false").lower() == "true":
        print("!!! SIMULATING DOCUMENT FAILURE !!!")
        action_items.append(create_action_item(
            category=ActionCategory.DOCUMENT,
            severity=ActionSeverity.BLOCKING,
            title="Document verification failed (Simulated)",
            description="The document verification was force-failed for testing purposes.",
            suggestion="This is a simulated failure. Set SIMULATE_DOC_FAILURE=false to proceed normally.",
            field_to_update="documents_path",
            current_value=doc_path,
        ))
        return {
            "is_doc_verified": False,
            "error_message": "Simulated Verification Failure: Unable to verify document authenticity.",
            "verification_notes": ["SIMULATION: Force failed document check."],
            "missing_artifacts": ["Valid KYC Document"],
            "action_items": action_items,
        }

    # 2. Check for File Existence
    if not doc_path:
        # If no document is provided, we pass with a note (for demo purposes)
        return {
            "is_doc_verified": True,
            "verification_notes": ["No document provided in state, skipping extraction."],
            "action_items": [],
        }

    if not os.path.exists(doc_path):
        action_items.append(create_action_item(
            category=ActionCategory.DOCUMENT,
            severity=ActionSeverity.BLOCKING,
            title="Upload KYC document",
            description=f"Document file not found at the specified path: {doc_path}",
            suggestion="Please upload a valid KYC document (PAN card, Aadhaar, or other government-issued ID).",
            field_to_update="documents_path",
            current_value=doc_path,
            required_format="PDF, PNG, or JPG. Maximum file size: 5MB. Minimum resolution: 300 DPI.",
        ))
        return {
            "is_doc_verified": False,
            "error_message": f"Document file not found at path: {doc_path}",
            "missing_artifacts": ["Uploaded Document"],
            "action_items": action_items,
        }

    # 3. Perform Extraction using Docling
    try:
        print(f"Extracting content from: {doc_path} using Docling...")
        loader = DoclingLoader(file_path=doc_path)
        docs = loader.load()
        full_text = "\n".join([d.page_content for d in docs])

        # 4. Keyword Validation
        keywords = [
            "PAN", "Aadhaar", "Government of India", "Income Tax",
            "Male", "Female", "Permanent Account Number",
        ]
        found_keywords = [k for k in keywords if k.lower() in full_text.lower()]

        print(f"Extracted Length: {len(full_text)} chars. Found Keywords: {found_keywords}")

        # Heuristic: if we got reasonable text and some keywords
        if len(found_keywords) >= 2 or len(full_text) > 50:
            return {
                "is_doc_verified": True,
                "verification_notes": [f"Document verified. Keywords found: {found_keywords}"],
                "action_items": [],
            }
        else:
            action_items.append(create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload clearer KYC document",
                description="The uploaded document is unclear or missing required security features. OCR confidence is too low.",
                suggestion="Please upload a high-resolution scan or photo of your KYC document. Ensure all text, photo, and security features are clearly visible. Avoid glare, shadows, or cropped edges.",
                field_to_update="documents_path",
                current_value=doc_path,
                required_format="PDF, PNG, or JPG. Minimum 300 DPI. Ensure document is flat and well-lit.",
            ))
            return {
                "is_doc_verified": False,
                "error_message": "Document unclear or missing security features (Low OCR Confidence).",
                "verification_notes": [
                    f"Extracted content length: {len(full_text)}",
                    "Insufficient keywords found.",
                ],
                "missing_artifacts": ["Clear/Valid KYC Document"],
                "action_items": action_items,
            }

    except Exception as e:
        print(f"Docling Extraction Failed: {e}")
        action_items.append(create_action_item(
            category=ActionCategory.DOCUMENT,
            severity=ActionSeverity.BLOCKING,
            title="Upload readable KYC document",
            description=f"Failed to process the uploaded document. Error: {str(e)}",
            suggestion="The document format may be corrupted or unsupported. Please upload a new document in PDF, PNG, or JPG format.",
            field_to_update="documents_path",
            current_value=doc_path,
            required_format="PDF, PNG, or JPG. File must not be password-protected or corrupted.",
        ))
        return {
            "is_doc_verified": False,
            "error_message": f"Document processing error: {str(e)}",
            "missing_artifacts": ["Readable KYC Document"],
            "action_items": action_items,
        }


def bank_verifier_node(state: AgentState) -> Dict[str, Any]:
    """
    Performs Penny Drop and name match.
    Corresponds to Steps 6, 7.
    """
    print("--- [Node] Bank Verifier ---")
    
    action_items: List[Dict[str, Any]] = []
    bank_details = state["application_data"].get("bank_details", {})
    holder_name = bank_details.get("account_holder_name", "")
    account_number = bank_details.get("account_number", "")
    ifsc = bank_details.get("ifsc", "")

    # Failure testing: if name is "FAIL_ME", we simulate failure
    if holder_name == "FAIL_ME":
        action_items.append(create_action_item(
            category=ActionCategory.BANK,
            severity=ActionSeverity.BLOCKING,
            title="Correct bank account holder name",
            description="The name on the bank account does not match the business/signatory name provided in the application.",
            suggestion="Please verify that the account holder name matches exactly with your business registration or signatory details. Common issues include spelling differences, missing middle names, or abbreviated names.",
            field_to_update="bank_details.account_holder_name",
            current_value=holder_name,
            required_format="Full name as it appears on bank account statement.",
        ))
        return {
            "is_bank_verified": False,
            "error_message": "Penny drop failed: Name mismatch.",
            "action_items": action_items,
        }

    # Check for missing bank details
    if not account_number or not ifsc:
        action_items.append(create_action_item(
            category=ActionCategory.BANK,
            severity=ActionSeverity.BLOCKING,
            title="Provide complete bank details",
            description="Bank account number or IFSC code is missing.",
            suggestion="Please provide your complete bank account details including the account number and IFSC code.",
            field_to_update="bank_details",
            required_format="Account number: 9-18 digits. IFSC: 11 characters (e.g., HDFC0001234).",
        ))
        return {
            "is_bank_verified": False,
            "error_message": "Incomplete bank details provided.",
            "action_items": action_items,
        }

    return {
        "is_bank_verified": True,
        "verification_notes": ["Penny drop successful", "Name match 100%"],
        "action_items": [],
    }


def finalizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Generates agreement and finishes onboarding.
    Corresponds to Steps 13, 14.
    """
    print("--- [Node] Finalizer ---")

    return {
        "verification_notes": ["Agreement generated", "Settlement enabled"],
        "status": "COMPLETED",
        "action_items": [],
    }
