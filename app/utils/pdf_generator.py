"""
PDF generator for merchant agreements.

Uses WeasyPrint to convert HTML templates to professional PDF documents.
"""

import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from app.utils.simulation import sim


# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "agreement"

# Output directory for generated PDFs
AGREEMENTS_DIR = Path(__file__).parent.parent.parent / "agreements"

# Jinja2 environment for template rendering
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def ensure_agreements_dir():
    """Ensure the agreements directory exists."""
    AGREEMENTS_DIR.mkdir(parents=True, exist_ok=True)


def mask_account_number(account_number: str) -> str:
    """Mask account number showing only last 4 digits."""
    if len(account_number) <= 4:
        return account_number
    return "X" * (len(account_number) - 4) + account_number[-4:]


def mask_aadhaar(aadhaar: str) -> str:
    """Mask Aadhaar showing only last 4 digits."""
    if len(aadhaar) <= 4:
        return aadhaar
    return "XXXX-XXXX-" + aadhaar[-4:]


def generate_agreement_number(merchant_id: str) -> str:
    """Generate a unique agreement number."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"MSA-{timestamp}-{merchant_id[:8].upper()}"


def prepare_agreement_context(
    merchant_data: Dict[str, Any],
    merchant_id: str,
) -> Dict[str, Any]:
    """Prepare context for agreement template."""
    business = merchant_data.get("business_details", {})
    bank = merchant_data.get("bank_details", {})
    signatory = merchant_data.get("signatory_details", {})
    
    now = datetime.now()
    
    return {
        # Agreement info
        "agreement_number": generate_agreement_number(merchant_id),
        "effective_date": now.strftime("%B %d, %Y"),
        "generation_timestamp": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "merchant_id": merchant_id,
        
        # Business details
        "business_name": business.get("entity_type", "Merchant Business"),
        "entity_type": business.get("entity_type", "Private Limited"),
        "business_category": business.get("category", "General"),
        "pan": business.get("pan", "N/A"),
        "gstin": business.get("gstin", "N/A"),
        "monthly_volume": business.get("monthly_volume", "Not specified"),
        "website_url": business.get("website_url", "N/A"),
        
        # Signatory details
        "signatory_name": signatory.get("name", "Authorized Signatory"),
        "signatory_email": signatory.get("email", "N/A"),
        "aadhaar_masked": mask_aadhaar(signatory.get("aadhaar", "")),
        
        # Bank details
        "account_holder_name": bank.get("account_holder_name", "N/A"),
        "account_number_masked": mask_account_number(bank.get("account_number", "")),
        "ifsc": bank.get("ifsc", "N/A"),
    }


def render_agreement_html(context: Dict[str, Any]) -> str:
    """Render the agreement HTML template."""
    template = jinja_env.get_template("merchant_agreement.html")
    return template.render(**context)


async def generate_agreement_pdf(
    merchant_data: Dict[str, Any],
    merchant_id: str,
    output_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a professional PDF agreement for the merchant.
    
    Args:
        merchant_data: Merchant application data
        merchant_id: Unique merchant identifier
        output_filename: Optional custom filename (without extension)
    
    Returns:
        Result dict with status and file path
    """
    ensure_agreements_dir()
    
    # Generate filename
    if not output_filename:
        output_filename = f"agreement_{merchant_id}"
    
    output_path = AGREEMENTS_DIR / f"{output_filename}.pdf"
    
    # Check simulation mode
    if sim.is_dev_mode() and sim.should_skip("doc"):
        print(f"[PDF] DEV MODE: Would generate agreement at {output_path}")
        # Still generate the PDF in dev mode for testing
    
    # Prepare context
    context = prepare_agreement_context(merchant_data, merchant_id)
    
    # Render HTML
    html_content = render_agreement_html(context)
    
    # Generate PDF
    try:
        from weasyprint import HTML, CSS
        
        # Create PDF from HTML
        html = HTML(string=html_content)
        html.write_pdf(str(output_path))
        
        print(f"[PDF] Generated agreement: {output_path}")
        
        return {
            "status": "generated",
            "file_path": str(output_path),
            "filename": f"{output_filename}.pdf",
            "agreement_number": context["agreement_number"],
            "merchant_id": merchant_id,
            "effective_date": context["effective_date"],
        }
        
    except ImportError as e:
        print(f"[PDF] WeasyPrint not available: {e}")
        # Fallback: save HTML instead
        html_path = AGREEMENTS_DIR / f"{output_filename}.html"
        with open(html_path, "w") as f:
            f.write(html_content)
        
        return {
            "status": "fallback_html",
            "message": "WeasyPrint not installed. Generated HTML instead.",
            "file_path": str(html_path),
            "filename": f"{output_filename}.html",
            "agreement_number": context["agreement_number"],
            "merchant_id": merchant_id,
        }
        
    except Exception as e:
        print(f"[PDF] Failed to generate PDF: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "merchant_id": merchant_id,
        }


async def get_agreement_path(merchant_id: str) -> Optional[str]:
    """Get the path to a merchant's agreement PDF if it exists."""
    pdf_path = AGREEMENTS_DIR / f"agreement_{merchant_id}.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    
    # Check for HTML fallback
    html_path = AGREEMENTS_DIR / f"agreement_{merchant_id}.html"
    if html_path.exists():
        return str(html_path)
    
    return None


async def generate_test_agreement() -> Dict[str, Any]:
    """Generate a test agreement to verify the system."""
    test_data = {
        "business_details": {
            "entity_type": "Test Business Pvt. Ltd.",
            "category": "E-commerce",
            "pan": "ABCDE1234F",
            "gstin": "29ABCDE1234F1Z5",
            "monthly_volume": "10-50 Lakhs",
            "website_url": "https://testbusiness.com",
        },
        "bank_details": {
            "account_holder_name": "Test Business Pvt. Ltd.",
            "account_number": "1234567890123456",
            "ifsc": "HDFC0001234",
        },
        "signatory_details": {
            "name": "John Doe",
            "email": "john@testbusiness.com",
            "aadhaar": "123456789012",
        },
    }
    
    test_merchant_id = str(uuid.uuid4())
    
    return await generate_agreement_pdf(
        merchant_data=test_data,
        merchant_id=test_merchant_id,
    )

