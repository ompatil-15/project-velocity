"""
Bank Tools - Penny drop, account verification, IFSC lookup.
"""

from typing import Any, Dict
from app.core.tool_registry import tool_registry


@tool_registry.register(
    name="penny_drop_verify",
    description="Perform penny drop verification on bank account",
    input_schema={
        "account_number": {"type": "string", "description": "Bank account number"},
        "ifsc": {"type": "string", "description": "IFSC code"},
        "expected_name": {"type": "string", "description": "Expected account holder name"}
    },
    output_schema={
        "success": {"type": "boolean"},
        "verified": {"type": "boolean"},
        "account_holder_name": {"type": "string"},
        "name_match_score": {"type": "number"},
        "bank_name": {"type": "string"},
        "error": {"type": "string", "nullable": True}
    },
    category="bank",
    requires_network=True,
    is_idempotent=False,
    mock_output={
        "success": True,
        "verified": True,
        "account_holder_name": "MOCK MERCHANT",
        "name_match_score": 1.0,
        "bank_name": "HDFC Bank",
        "error": None
    }
)
def penny_drop_verify(
    account_number: str,
    ifsc: str,
    expected_name: str
) -> Dict[str, Any]:
    """
    Perform penny drop verification.
    
    In production, this would call an actual bank API like:
    - Cashfree Bank Verification
    - Razorpay Fund Account Validation
    - PayU Bank Account Verification
    
    For now, this is a placeholder that returns mock success.
    """
    # TODO: Integrate with actual penny drop API
    
    # For demo, simulate verification
    if not account_number or not ifsc:
        return {
            "success": False,
            "verified": False,
            "account_holder_name": "",
            "name_match_score": 0,
            "bank_name": "",
            "error": "Account number and IFSC are required"
        }
    
    # Simulate name matching
    # In production, compare expected_name with bank's response
    name_match = 1.0 if expected_name else 0.8
    
    # Get bank name from IFSC (first 4 chars)
    bank_codes = {
        "HDFC": "HDFC Bank",
        "ICIC": "ICICI Bank",
        "SBIN": "State Bank of India",
        "AXIS": "Axis Bank",
        "KKBK": "Kotak Mahindra Bank",
        "PUNB": "Punjab National Bank",
        "BARB": "Bank of Baroda",
        "UBIN": "Union Bank of India",
    }
    bank_code = ifsc[:4].upper()
    bank_name = bank_codes.get(bank_code, f"Bank ({bank_code})")
    
    return {
        "success": True,
        "verified": True,
        "account_holder_name": expected_name.upper() if expected_name else "VERIFIED",
        "name_match_score": name_match,
        "bank_name": bank_name,
        "error": None
    }


@tool_registry.register(
    name="lookup_ifsc",
    description="Look up bank and branch details from IFSC code",
    input_schema={
        "ifsc": {"type": "string", "description": "IFSC code to look up"}
    },
    output_schema={
        "found": {"type": "boolean"},
        "bank_name": {"type": "string"},
        "branch_name": {"type": "string"},
        "address": {"type": "string"},
        "city": {"type": "string"},
        "state": {"type": "string"}
    },
    category="bank",
    requires_network=True,
    mock_output={
        "found": True,
        "bank_name": "HDFC Bank",
        "branch_name": "Mumbai Main Branch",
        "address": "123 Main Street, Fort",
        "city": "Mumbai",
        "state": "Maharashtra"
    }
)
def lookup_ifsc(ifsc: str) -> Dict[str, Any]:
    """
    Look up bank details from IFSC code.
    
    In production, this would call an API like:
    - RazorpayX IFSC API
    - Custom IFSC database
    """
    # TODO: Integrate with IFSC lookup API
    
    if not ifsc or len(ifsc) != 11:
        return {
            "found": False,
            "bank_name": "",
            "branch_name": "",
            "address": "",
            "city": "",
            "state": ""
        }
    
    # Mock response based on bank code
    bank_codes = {
        "HDFC": ("HDFC Bank", "Mumbai"),
        "ICIC": ("ICICI Bank", "Mumbai"),
        "SBIN": ("State Bank of India", "Delhi"),
        "AXIS": ("Axis Bank", "Bangalore"),
    }
    
    bank_code = ifsc[:4].upper()
    bank_info = bank_codes.get(bank_code, ("Unknown Bank", "Unknown City"))
    
    return {
        "found": True,
        "bank_name": bank_info[0],
        "branch_name": f"{bank_info[1]} Branch",
        "address": f"123 Main Road, {bank_info[1]}",
        "city": bank_info[1],
        "state": "Maharashtra" if bank_info[1] == "Mumbai" else "Karnataka"
    }


@tool_registry.register(
    name="validate_account_number",
    description="Validate bank account number format",
    input_schema={
        "account_number": {"type": "string", "description": "Account number to validate"}
    },
    output_schema={
        "valid": {"type": "boolean"},
        "length": {"type": "integer"},
        "error": {"type": "string", "nullable": True}
    },
    category="bank",
    mock_output={"valid": True, "length": 14, "error": None}
)
def validate_account_number(account_number: str) -> Dict[str, Any]:
    """
    Validate bank account number format.
    
    Indian bank account numbers are typically 9-18 digits.
    """
    if not account_number:
        return {"valid": False, "length": 0, "error": "Account number is required"}
    
    # Remove spaces
    account_number = account_number.replace(" ", "").replace("-", "")
    
    # Check if all digits
    if not account_number.isdigit():
        return {
            "valid": False,
            "length": len(account_number),
            "error": "Account number must contain only digits"
        }
    
    # Check length (9-18 digits for Indian banks)
    if len(account_number) < 9 or len(account_number) > 18:
        return {
            "valid": False,
            "length": len(account_number),
            "error": "Account number must be between 9 and 18 digits"
        }
    
    return {"valid": True, "length": len(account_number), "error": None}

