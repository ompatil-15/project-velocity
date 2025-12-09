"""
Validation Tools - PAN, GSTIN, and other format validations.
"""

import re
from typing import Any, Dict
from app.core.tool_registry import tool_registry


@tool_registry.register(
    name="validate_pan",
    description="Validate PAN (Permanent Account Number) format",
    input_schema={
        "pan": {"type": "string", "description": "PAN number to validate"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "error": {"type": "string", "nullable": True},
        "parsed": {"type": "object", "nullable": True}
    },
    category="validation",
    mock_output={"valid": True, "error": None, "parsed": {"type": "P", "holder_type": "Individual"}}
)
def validate_pan(pan: str) -> Dict[str, Any]:
    """
    Validate PAN format: AAAAA9999A
    - First 5: Letters (AAA = Area Code, 4th = Holder Type, 5th = Name Initial)
    - Next 4: Digits (Sequential Number)
    - Last 1: Letter (Check character)
    """
    if not pan:
        return {"valid": False, "error": "PAN is required", "parsed": None}
    
    pan = pan.upper().strip()
    
    # Format check
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
    if not re.match(pattern, pan):
        return {
            "valid": False, 
            "error": "Invalid format. PAN must be 10 characters: 5 letters + 4 digits + 1 letter",
            "parsed": None
        }
    
    # 4th character indicates holder type
    holder_types = {
        'A': 'Association of Persons (AOP)',
        'B': 'Body of Individuals (BOI)',
        'C': 'Company',
        'F': 'Firm',
        'G': 'Government',
        'H': 'Hindu Undivided Family (HUF)',
        'L': 'Local Authority',
        'J': 'Artificial Juridical Person',
        'P': 'Individual',
        'T': 'Trust (AOP)',
        'K': 'Krishi',
    }
    
    fourth_char = pan[3]
    holder_type = holder_types.get(fourth_char, 'Unknown')
    
    return {
        "valid": True,
        "error": None,
        "parsed": {
            "type": fourth_char,
            "holder_type": holder_type,
            "name_initial": pan[4],
        }
    }


@tool_registry.register(
    name="validate_gstin",
    description="Validate GSTIN (Goods and Services Tax Identification Number) format",
    input_schema={
        "gstin": {"type": "string", "description": "GSTIN to validate"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "error": {"type": "string", "nullable": True},
        "parsed": {"type": "object", "nullable": True}
    },
    category="validation",
    mock_output={"valid": True, "error": None, "parsed": {"state_code": "27", "pan": "ABCDE1234F"}}
)
def validate_gstin(gstin: str) -> Dict[str, Any]:
    """
    Validate GSTIN format: 99AAAAA9999A9Z9
    - First 2: State code (01-37)
    - Next 10: PAN of entity
    - 13th: Entity number within state
    - 14th: 'Z' by default
    - 15th: Check digit
    """
    if not gstin:
        return {"valid": False, "error": "GSTIN is required", "parsed": None}
    
    gstin = gstin.upper().strip()
    
    # Format check
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$'
    if not re.match(pattern, gstin):
        return {
            "valid": False,
            "error": "Invalid format. GSTIN must be 15 characters: 2 digits + 10 char PAN + entity code + Z + check digit",
            "parsed": None
        }
    
    state_code = gstin[:2]
    pan = gstin[2:12]
    entity_code = gstin[12]
    
    # State code validation (01-37 are valid)
    if not (1 <= int(state_code) <= 37):
        return {
            "valid": False,
            "error": f"Invalid state code: {state_code}. Must be between 01 and 37",
            "parsed": None
        }
    
    return {
        "valid": True,
        "error": None,
        "parsed": {
            "state_code": state_code,
            "pan": pan,
            "entity_code": entity_code,
        }
    }


@tool_registry.register(
    name="validate_ifsc",
    description="Validate IFSC (Indian Financial System Code) format",
    input_schema={
        "ifsc": {"type": "string", "description": "IFSC code to validate"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "error": {"type": "string", "nullable": True},
        "parsed": {"type": "object", "nullable": True}
    },
    category="validation",
    mock_output={"valid": True, "error": None, "parsed": {"bank_code": "HDFC", "branch_code": "001234"}}
)
def validate_ifsc(ifsc: str) -> Dict[str, Any]:
    """
    Validate IFSC format: AAAA0BBBBBB
    - First 4: Bank code (letters)
    - 5th: Always 0 (reserved)
    - Last 6: Branch code (alphanumeric)
    """
    if not ifsc:
        return {"valid": False, "error": "IFSC is required", "parsed": None}
    
    ifsc = ifsc.upper().strip()
    
    # Format check
    pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    if not re.match(pattern, ifsc):
        return {
            "valid": False,
            "error": "Invalid format. IFSC must be 11 characters: 4 letters + 0 + 6 alphanumeric",
            "parsed": None
        }
    
    return {
        "valid": True,
        "error": None,
        "parsed": {
            "bank_code": ifsc[:4],
            "branch_code": ifsc[5:],
        }
    }


@tool_registry.register(
    name="validate_aadhaar",
    description="Validate Aadhaar number format (basic check)",
    input_schema={
        "aadhaar": {"type": "string", "description": "Aadhaar number to validate"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "error": {"type": "string", "nullable": True}
    },
    category="validation",
    mock_output={"valid": True, "error": None}
)
def validate_aadhaar(aadhaar: str) -> Dict[str, Any]:
    """
    Validate Aadhaar format: 12 digits, cannot start with 0 or 1.
    Note: This is format validation only, not Verhoeff checksum.
    """
    if not aadhaar:
        return {"valid": False, "error": "Aadhaar is required"}
    
    # Remove spaces and hyphens
    aadhaar = re.sub(r'[\s-]', '', aadhaar)
    
    # Must be 12 digits
    if not re.match(r'^[2-9][0-9]{11}$', aadhaar):
        return {
            "valid": False,
            "error": "Invalid format. Aadhaar must be 12 digits and cannot start with 0 or 1"
        }
    
    return {"valid": True, "error": None}

