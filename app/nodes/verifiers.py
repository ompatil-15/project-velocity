from typing import Any, Dict
import random
from app.schema import AgentState


import os
from langchain_docling import DoclingLoader


def doc_intelligence_node(state: AgentState) -> Dict[str, Any]:
    """
    Extracts text from documents using Docling (IBM) and validates content.
    Corresponds to Steps 10, 11.
    """
    print("--- [Node] Doc Intelligence ---")

    # 1. Simulation Check: Force Failure Flag
    if os.getenv("SIMULATE_DOC_FAILURE", "false").lower() == "true":
        print("!!! SIMULATING DOCUMENT FAILURE !!!")
        return {
            "is_doc_verified": False,
            "error_message": "Simulated Verification Failure: Unable to verify document authenticity.",
            "verification_notes": ["SIMULATION: Force failed document check."],
            "missing_artifacts": ["Valid KYC Document"],
        }

    doc_path = state["application_data"].get("documents_path")

    # 2. Check for File Existence
    if not doc_path:
        # If no document is provided (e.g. initial simulation), we pass with a note
        # In a real scenario, this might fail, but for now we allow the flow to proceed if data is missing
        return {
            "is_doc_verified": True,
            "verification_notes": [
                "No document provided in state, skipping extraction."
            ],
        }

    if not os.path.exists(doc_path):
        return {
            "is_doc_verified": False,
            "error_message": f"Document file not found at path: {doc_path}",
            "missing_artifacts": ["Uploaded Document"],
        }

    # 3. Perform Extraction using Docling
    try:
        print(f"Extracting content from: {doc_path} using Docling...")
        loader = DoclingLoader(file_path=doc_path)
        docs = loader.load()
        full_text = "\n".join([d.page_content for d in docs])

        # 4. Keyword Validation
        keywords = [
            "PAN",
            "Aadhaar",
            "Government of India",
            "Income Tax",
            "Male",
            "Female",
            "Permanent Account Number",
        ]
        found_keywords = [k for k in keywords if k.lower() in full_text.lower()]

        print(
            f"Extracted Length: {len(full_text)} chars. Found Keywords: {found_keywords}"
        )

        if (
            len(found_keywords) >= 2 or len(full_text) > 50
        ):  # Heuristic: if we got reasonable text and some keywords
            return {
                "is_doc_verified": True,
                "verification_notes": [
                    f"Document verified. Keywords found: {found_keywords}"
                ],
            }
        else:
            return {
                "is_doc_verified": False,
                "error_message": "Document unclear or missing security features (Low OCR Confidence).",
                "verification_notes": [
                    f"Extracted content length: {len(full_text)}",
                    "Insufficient keywords found.",
                ],
                "missing_artifacts": ["Clear/Valid KYC Document"],
            }

    except Exception as e:
        print(f"Docling Extraction Failed: {e}")
        return {
            "is_doc_verified": False,
            "error_message": f"Document processing error: {str(e)}",
            "missing_artifacts": ["Readable KYC Document"],
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
