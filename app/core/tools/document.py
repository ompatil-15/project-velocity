"""
Document Tools - OCR, text extraction, and document validation.
"""

import os
from typing import Any, Dict, List
from app.core.tool_registry import tool_registry


@tool_registry.register(
    name="extract_document_text",
    description="Extract text content from a document using OCR",
    input_schema={
        "file_path": {"type": "string", "description": "Path to the document file"},
        "extract_tables": {"type": "boolean", "description": "Whether to extract tables", "default": False}
    },
    output_schema={
        "success": {"type": "boolean"},
        "text": {"type": "string"},
        "confidence": {"type": "number"},
        "pages": {"type": "integer"},
        "error": {"type": "string", "nullable": True}
    },
    category="document",
    requires_network=False,
    mock_output={
        "success": True,
        "text": "INCOME TAX DEPARTMENT\nGOVERNMENT OF INDIA\nPermanent Account Number Card\nABCDE1234F\nName: MOCK MERCHANT\nFather's Name: MOCK FATHER\nDate of Birth: 01/01/1990",
        "confidence": 0.95,
        "pages": 1,
        "error": None
    }
)
def extract_document_text(file_path: str, extract_tables: bool = False) -> Dict[str, Any]:
    """
    Extract text from document using Docling (IBM).
    
    Supports: PDF, PNG, JPG, TIFF
    """
    if not file_path:
        return {
            "success": False,
            "text": "",
            "confidence": 0,
            "pages": 0,
            "error": "File path is required"
        }
    
    if not os.path.exists(file_path):
        return {
            "success": False,
            "text": "",
            "confidence": 0,
            "pages": 0,
            "error": f"File not found: {file_path}"
        }
    
    try:
        from langchain_docling import DoclingLoader
        
        loader = DoclingLoader(file_path=file_path)
        docs = loader.load()
        
        full_text = "\n".join([d.page_content for d in docs])
        
        # Estimate confidence based on text length and keywords
        keywords = ["PAN", "Aadhaar", "Government", "Income Tax", "UIDAI"]
        found_keywords = sum(1 for k in keywords if k.lower() in full_text.lower())
        confidence = min(0.95, 0.5 + (found_keywords * 0.1) + (min(len(full_text), 500) / 1000))
        
        return {
            "success": True,
            "text": full_text,
            "confidence": round(confidence, 2),
            "pages": len(docs),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "text": "",
            "confidence": 0,
            "pages": 0,
            "error": str(e)
        }


@tool_registry.register(
    name="validate_document_content",
    description="Validate extracted document content against expected fields",
    input_schema={
        "text": {"type": "string", "description": "Extracted text from document"},
        "expected_fields": {"type": "array", "items": {"type": "string"}, "description": "List of field names to look for"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "found_fields": {"type": "array", "items": {"type": "string"}},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"}
    },
    category="document",
    mock_output={
        "valid": True,
        "found_fields": ["PAN", "Name", "Date of Birth"],
        "missing_fields": [],
        "confidence": 0.9
    }
)
def validate_document_content(text: str, expected_fields: List[str] = None) -> Dict[str, Any]:
    """
    Check if document contains expected content.
    """
    if expected_fields is None:
        expected_fields = ["PAN", "Name", "Government"]
    
    text_lower = text.lower()
    
    found = []
    missing = []
    
    for field in expected_fields:
        if field.lower() in text_lower:
            found.append(field)
        else:
            missing.append(field)
    
    valid = len(missing) == 0 or len(found) >= len(expected_fields) * 0.5
    confidence = len(found) / max(len(expected_fields), 1)
    
    return {
        "valid": valid,
        "found_fields": found,
        "missing_fields": missing,
        "confidence": round(confidence, 2)
    }


@tool_registry.register(
    name="extract_pan_from_document",
    description="Extract PAN number from document text",
    input_schema={
        "text": {"type": "string", "description": "Document text to search"}
    },
    output_schema={
        "found": {"type": "boolean"},
        "pan": {"type": "string", "nullable": True},
        "name": {"type": "string", "nullable": True}
    },
    category="document",
    mock_output={"found": True, "pan": "ABCDE1234F", "name": "MOCK MERCHANT"}
)
def extract_pan_from_document(text: str) -> Dict[str, Any]:
    """
    Extract PAN number from document text using regex.
    """
    import re
    
    # PAN pattern
    pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'
    matches = re.findall(pan_pattern, text.upper())
    
    if matches:
        # Try to extract name (usually near PAN)
        name = None
        name_patterns = [
            r'Name[:\s]+([A-Z][A-Z\s]+)',
            r'([A-Z][A-Z\s]{5,30})\s*\n.*PAN',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text.upper())
            if name_match:
                name = name_match.group(1).strip()
                break
        
        return {
            "found": True,
            "pan": matches[0],
            "name": name
        }
    
    return {"found": False, "pan": None, "name": None}

