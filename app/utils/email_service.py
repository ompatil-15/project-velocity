"""
Email service using Resend.

Handles sending welcome emails with attachments.
"""

import os
import uuid
import resend
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from app.utils.simulation import sim


# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"

# Jinja2 environment for template rendering
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


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


def render_email_template(
    template_name: str,
    context: Dict[str, Any],
) -> str:
    """Render an email template with the given context."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)


def prepare_welcome_email_context(
    merchant_data: Dict[str, Any],
    merchant_id: str,
) -> Dict[str, Any]:
    """Prepare context for welcome email template."""
    business = merchant_data.get("business_details", {})
    bank = merchant_data.get("bank_details", {})
    signatory = merchant_data.get("signatory_details", {})

    return {
        "merchant_id": merchant_id,
        "business_name": business.get("entity_type", "Your Business"),
        "business_category": business.get("category", "General"),
        "pan": business.get("pan", "N/A"),
        "gstin": business.get("gstin", "N/A"),
        "signatory_name": signatory.get("name", "Valued Customer"),
        "signatory_email": signatory.get("email", ""),
        "account_holder_name": bank.get("account_holder_name", "N/A"),
        "account_number_masked": mask_account_number(bank.get("account_number", "")),
        "ifsc": bank.get("ifsc", "N/A"),
    }


async def send_welcome_email(
    to_email: str,
    merchant_data: Dict[str, Any],
    merchant_id: str,
    agreement_pdf_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send welcome email to merchant on successful onboarding.

    Args:
        to_email: Recipient email address
        merchant_data: Merchant application data
        merchant_id: Unique merchant identifier
        agreement_pdf_path: Path to the agreement PDF to attach

    Returns:
        Result dict with status and details
    """
    # Check simulation mode
    if sim.is_dev_mode() and not os.getenv("RESEND_API_KEY"):
        print(f"[Email] DEV MODE: Would send welcome email to {to_email}")
        return {
            "status": "simulated",
            "message": f"Email would be sent to {to_email} (no API key configured)",
            "to": to_email,
            "merchant_id": merchant_id,
        }

    # Initialize Resend
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return {
            "status": "skipped",
            "message": "RESEND_API_KEY not configured",
        }

    resend.api_key = api_key

    # Prepare email context
    context = prepare_welcome_email_context(merchant_data, merchant_id)

    # Render templates
    html_content = render_email_template("welcome.html", context)
    text_content = render_email_template("welcome.txt", context)

    # Prepare attachments
    attachments = []
    if agreement_pdf_path and os.path.exists(agreement_pdf_path):
        with open(agreement_pdf_path, "rb") as f:
            pdf_content = f.read()
        attachments.append(
            {
                "filename": f"Merchant_Agreement_{merchant_id}.pdf",
                "content": list(pdf_content),
            }
        )

    # Send email
    try:
        from_email = os.getenv("EMAIL_FROM")

        params = {
            "from": from_email,
            "to": [to_email],
            "subject": f"Welcome to {os.getenv('COMPANY_NAME', 'Our Service')} - Your Merchant Account is Active [{merchant_id}]",
            "html": html_content,
            "text": text_content,
        }

        if attachments:
            params["attachments"] = attachments

        email_response = resend.Emails.send(params)

        return {
            "status": "sent",
            "message": f"Welcome email sent to {to_email}",
            "email_id": email_response.get("id"),
            "to": to_email,
            "merchant_id": merchant_id,
            "has_attachment": bool(attachments),
        }

    except Exception as e:
        print(f"[Email] Failed to send email: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "to": to_email,
            "merchant_id": merchant_id,
        }


async def send_test_email(to_email: str) -> Dict[str, Any]:
    """Send a test email to verify configuration."""
    test_data = {
        "business_details": {
            "entity_type": "Test Business Pvt. Ltd.",
            "category": "E-commerce",
            "pan": "ABCDE1234F",
            "gstin": "29ABCDE1234F1Z5",
        },
        "bank_details": {
            "account_holder_name": "Test Business Pvt. Ltd.",
            "account_number": "1234567890123456",
            "ifsc": "HDFC0001234",
        },
        "signatory_details": {
            "name": "Test User",
            "email": to_email,
        },
    }

    return await send_welcome_email(
        to_email=to_email,
        merchant_data=test_data,
        merchant_id=str(uuid.uuid4()),
    )
