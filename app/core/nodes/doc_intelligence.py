"""
Document Intelligence Node - Extracts and validates KYC documents.

INPUT:
  - application_data.documents_path

OUTPUT:
  - is_doc_verified: bool
  - action_items: document issues (if any)

TOOLS:
  - extract_document_text
  - validate_document_content
  - extract_pan_from_document
"""

from typing import Any, Dict
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity
import os


class DocIntelligenceNode(BaseNode):
    """
    Extracts text from KYC documents using OCR and validates content.
    
    Checks:
    - Document exists
    - OCR extraction successful
    - Required fields present (PAN, name, etc.)
    
    Future enhancements:
    - Face matching
    - Document tampering detection
    - LLM-based content validation
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="doc_intelligence_node",
            display_name="Document Intelligence",
            description="Extracts and validates KYC documents using OCR",
            stage="DOCS",
            available_tools=[
                "extract_document_text",
                "validate_document_content",
                "extract_pan_from_document",
            ],
            simulation_key="doc",
            llm=LLMConfig(
                enabled=False,  # Can enable for document content analysis
                system_prompt="You are analyzing KYC documents for a payment gateway."
            ),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Extract and validate document content.
        """
        self._log("Processing documents...")
        
        doc_path = input.application_data.get("documents_path")
        action_items = []
        
        # --- Force Success Mode ---
        if self.should_skip_checks():
            self._add_note("SIMULATION: Document checks skipped (force_success)")
            return NodeOutput(
                state_updates={
                    "is_doc_verified": True,
                    "stage": "DOCS",
                },
                action_items=[],
                verification_notes=["Document verification passed (simulated)"],
            )
        
        # --- Simulate Failures ---
        if self.should_simulate_failure("blurry"):
            self._add_note("SIMULATION: Document blurry failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload clearer KYC document",
                description="The document is blurry or has low resolution. OCR could not extract text reliably.",
                suggestion="Upload a high-resolution scan (300+ DPI). Ensure document is flat and well-lit.",
                field_to_update="documents_path",
                current_value=doc_path,
                required_format="PDF, PNG, or JPG. Minimum 300 DPI.",
            ))
            return NodeOutput(
                state_updates={
                    "is_doc_verified": False,
                    "error_message": "Document OCR failed: Image too blurry",
                    "stage": "DOCS",
                    "missing_artifacts": ["Clear KYC Document"],
                },
                action_items=action_items,
            )
        
        if self.should_simulate_failure("missing"):
            self._add_note("SIMULATION: Document missing failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload KYC document",
                description="No document was found at the specified path.",
                suggestion="Please upload your KYC document (PAN card or government ID).",
                field_to_update="documents_path",
                required_format="PDF, PNG, or JPG. Maximum 5MB.",
            ))
            return NodeOutput(
                state_updates={
                    "is_doc_verified": False,
                    "error_message": "Document not found",
                    "stage": "DOCS",
                    "missing_artifacts": ["KYC Document"],
                },
                action_items=action_items,
            )
        
        if self.should_simulate_failure("invalid"):
            self._add_note("SIMULATION: Document invalid failure triggered")
            action_items.append(self.create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload valid KYC document",
                description="The document is missing required fields.",
                suggestion="Ensure you upload a complete government-issued ID.",
                field_to_update="documents_path",
                required_format="Complete PAN card or Aadhaar with name and ID visible.",
            ))
            return NodeOutput(
                state_updates={
                    "is_doc_verified": False,
                    "error_message": "Document missing required fields",
                    "stage": "DOCS",
                    "missing_artifacts": ["Valid KYC Document"],
                },
                action_items=action_items,
            )
        
        # --- Real Processing ---
        
        # Check if document path provided
        if not doc_path:
            self._add_note("No document provided in state, skipping extraction")
            return NodeOutput(
                state_updates={
                    "is_doc_verified": True,  # Pass for demo
                    "stage": "DOCS",
                },
                verification_notes=["No document provided, skipping verification"],
            )
        
        # Check file exists
        if not os.path.exists(doc_path):
            action_items.append(self.create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload KYC document",
                description=f"Document file not found at: {doc_path}",
                suggestion="Please upload a valid KYC document.",
                field_to_update="documents_path",
                current_value=doc_path,
            ))
            return NodeOutput(
                state_updates={
                    "is_doc_verified": False,
                    "error_message": f"Document not found: {doc_path}",
                    "stage": "DOCS",
                    "missing_artifacts": ["Uploaded Document"],
                },
                action_items=action_items,
            )
        
        # Extract text using OCR tool
        extract_result = self.call_tool("extract_document_text", {
            "file_path": doc_path,
            "extract_tables": False,
        })
        
        if not extract_result.success or not extract_result.data:
            action_items.append(self.create_action_item(
                category=ActionCategory.DOCUMENT,
                severity=ActionSeverity.BLOCKING,
                title="Upload readable KYC document",
                description=f"Failed to process document: {extract_result.error or 'Unknown error'}",
                suggestion="The document may be corrupted. Please upload a new document.",
                field_to_update="documents_path",
                current_value=doc_path,
            ))
            return NodeOutput(
                state_updates={
                    "is_doc_verified": False,
                    "error_message": f"OCR failed: {extract_result.error}",
                    "stage": "DOCS",
                },
                action_items=action_items,
            )
        
        extracted_text = extract_result.data.get("text", "")
        confidence = extract_result.data.get("confidence", 0)
        
        self._add_note(f"Extracted {len(extracted_text)} chars, confidence: {confidence:.2f}")
        
        # Validate document content
        validate_result = self.call_tool("validate_document_content", {
            "text": extracted_text,
            "expected_fields": ["PAN", "Name", "Government"],
        })
        
        if validate_result.success and validate_result.data:
            if validate_result.data.get("valid") and confidence >= 0.5:
                found_fields = validate_result.data.get("found_fields", [])
                self._add_note(f"Document valid. Found: {found_fields}")
                
                return NodeOutput(
                    state_updates={
                        "is_doc_verified": True,
                        "stage": "DOCS",
                    },
                    verification_notes=[
                        f"Document verified. Keywords found: {found_fields}",
                        f"OCR confidence: {confidence:.2f}",
                    ],
                )
        
        # Document validation failed
        missing_fields = validate_result.data.get("missing_fields", []) if validate_result.data else []
        
        action_items.append(self.create_action_item(
            category=ActionCategory.DOCUMENT,
            severity=ActionSeverity.BLOCKING,
            title="Upload clearer KYC document",
            description="The document is unclear or missing required content.",
            suggestion="Upload a high-resolution scan with all text clearly visible.",
            field_to_update="documents_path",
            current_value=doc_path,
            required_format="PDF, PNG, or JPG. Min 300 DPI.",
        ))
        
        return NodeOutput(
            state_updates={
                "is_doc_verified": False,
                "error_message": "Document unclear or missing required fields",
                "stage": "DOCS",
                "missing_artifacts": missing_fields or ["Clear KYC Document"],
            },
            action_items=action_items,
            verification_notes=[
                f"Extracted length: {len(extracted_text)}",
                f"Missing fields: {missing_fields}",
            ],
        )


# Create callable for LangGraph
doc_intelligence_node = DocIntelligenceNode()

