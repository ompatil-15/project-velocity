import asyncio
import os
import re
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.schema import AgentState, ActionItem, ActionCategory, ActionSeverity
from playwright.async_api import async_playwright
from app.utils.llm_factory import get_llm
from app.utils.adverse_media import check_reputation
from app.utils.domain_checks import get_domain_from_url, get_domain_age, has_mx_records
from langchain_core.messages import HumanMessage

# --- Configuration ---
EVIDENCE_DIR = "evidence"
PROHIBITED_KEYWORDS = [
    "gambling", "casino", "drugs", "weapons", "firearms",
    "adult", "porn", "bitcoin", "crypto",
]
FUNCTIONALITY_KEYWORDS = [
    "add to cart", "buy now", "checkout", "subscribe", "book now", "pricing",
]

# --- Policy Templates ---
POLICY_TEMPLATES = {
    "refund_policy": """## Refund & Return Policy

**Effective Date:** [Date]

### Return Window
- Products can be returned within 30 days of purchase
- Items must be unused and in original packaging

### Refund Process
1. Contact us at [email] with your order number
2. We'll provide return shipping instructions
3. Refund processed within 5-7 business days after receipt

### Non-Refundable Items
- Digital products after download
- Personalized/custom items
- Sale items (final sale)

### Contact
Email: support@[yourdomain].com
""",
    "privacy_policy": """## Privacy Policy

**Effective Date:** [Date]

### Information We Collect
- Personal information (name, email, address)
- Payment information (processed securely)
- Usage data (browsing behavior)

### How We Use Your Information
- Process orders and payments
- Send order updates and confirmations
- Improve our services

### Data Protection
- SSL encryption for all transactions
- No selling of personal data to third parties
- Data retained only as long as necessary

### Your Rights
- Access your personal data
- Request data deletion
- Opt-out of marketing emails

### Contact
Privacy inquiries: privacy@[yourdomain].com
""",
    "terms_of_service": """## Terms of Service

**Effective Date:** [Date]

### Acceptance of Terms
By using our website, you agree to these terms.

### Use of Service
- You must be 18+ to make purchases
- Account information must be accurate
- You're responsible for account security

### Orders & Payments
- Prices subject to change without notice
- We reserve the right to refuse orders
- Payment processed at time of order

### Intellectual Property
All content is owned by [Company Name].

### Limitation of Liability
We're not liable for indirect damages.

### Contact
Legal inquiries: legal@[yourdomain].com
""",
}


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


async def capture_screenshot(page, merchant_id: str, tag: str) -> str:
    """Captures a screenshot and saves it to the evidence directory."""
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{EVIDENCE_DIR}/{merchant_id}_{timestamp}_{tag}.png"
    try:
        await page.screenshot(path=filename, full_page=True)
        return filename
    except Exception as e:
        print(f"Failed to capture screenshot for {tag}: {e}")
        return ""


async def analyze_vision_risk(image_path: str) -> float:
    """Uses LLM Vision to analyze the screenshot for potential risks."""
    if not image_path or not os.path.exists(image_path):
        return 0.0

    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        llm = get_llm()
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "Analyze this website screenshot for a merchant onboarding compliance check. Look for: 1. Prohibited items (drugs, weapons, gambling). 2. Deceptive branding or low-quality 'scam' indicators. 3. Consistency with a legitimate business. Return a Risk Score from 0.0 (Safe) to 1.0 (High Risk) and a brief justification.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded_string}"},
                },
            ]
        )
        response = await llm.ainvoke([message])
        content = response.content.lower()

        match = re.search(r"risk score:\s*(\d+(\.\d+)?)", content)
        if match:
            return float(match.group(1))

        if "high risk" in content:
            return 0.8
        if "medium risk" in content:
            return 0.5
        return 0.1

    except Exception as e:
        print(f"Vision Analysis Failed: {e}")
        return 0.0


async def find_policy_links(page) -> Dict[str, str]:
    """Finds links to key policy pages on the current page."""
    links = {}
    anchors = await page.query_selector_all("a")
    for a in anchors:
        text = await a.text_content()
        href = await a.get_attribute("href")
        if not text or not href:
            continue

        text = text.lower()
        if "privacy" in text:
            links["privacy_policy"] = href
        elif "term" in text:
            links["terms_of_service"] = href
        elif "refund" in text or "return" in text:
            links["refund_policy"] = href
        elif "contact" in text:
            links["contact_us"] = href
        elif "about" in text:
            links["about_us"] = href

    return links


async def web_compliance_node(state: AgentState) -> Dict[str, Any]:
    """
    Rigorously checks the merchant's website for compliance.
    Returns structured action items for any issues found.
    """
    url = state["application_data"]["business_details"].get("website_url")
    merchant_id = state.get("merchant_id", "unknown")
    company_name = state["application_data"]["business_details"].get("entity_type", "Your Company")

    issues = []
    notes = []
    action_items: List[Dict[str, Any]] = []
    risk_score_increase = 0.0
    evidence_files = []

    print(f"--- Web Compliance Check: {url} ---")

    # Handle missing URL
    if not url:
        action_items.append(create_action_item(
            category=ActionCategory.WEBSITE,
            severity=ActionSeverity.BLOCKING,
            title="Provide website URL",
            description="No website URL was provided in the application.",
            suggestion="Please provide your business website URL for compliance verification.",
            field_to_update="business_details.website_url",
            required_format="Full URL including https:// (e.g., https://yourbusiness.com)",
        ))
        return {
            "is_website_compliant": False,
            "compliance_issues": ["Website URL not provided"],
            "verification_notes": ["Cannot perform compliance check without URL"],
            "action_items": action_items,
            "error_message": "Website URL missing",
        }

    # 1. SSL Check
    if not url.startswith("https://"):
        issues.append("Website is not using HTTPS (Insecure).")
        risk_score_increase += 1.0
        notes.append("SSL Check: FAILED")
        action_items.append(create_action_item(
            category=ActionCategory.WEBSITE,
            severity=ActionSeverity.BLOCKING,
            title="Enable HTTPS/SSL on your website",
            description="Your website is not using HTTPS, which means customer data is transmitted insecurely.",
            suggestion="Install an SSL certificate on your website. Most hosting providers offer free SSL via Let's Encrypt. Contact your hosting provider for assistance.",
            field_to_update="business_details.website_url",
            current_value=url,
            required_format="URL must start with https:// (not http://)",
        ))
    else:
        notes.append("SSL Check: PASSED")

    # 1b. Adverse Media Scan
    merchant_name = state["application_data"]["bank_details"].get(
        "account_holder_name", "Unknown Merchant"
    )
    adverse_media = check_reputation(merchant_name)
    if adverse_media:
        real_hits = [m for m in adverse_media if "Search failed" not in m]
        if real_hits:
            issues.append(f"Adverse Media Found: {len(real_hits)} suspicious items.")
            risk_score_increase += 0.5 * len(real_hits)
            action_items.append(create_action_item(
                category=ActionCategory.COMPLIANCE,
                severity=ActionSeverity.WARNING,
                title="Address adverse media findings",
                description=f"Found {len(real_hits)} potentially negative mentions related to your business.",
                suggestion="Review the findings and provide clarification or documentation if these are false positives or have been resolved.",
            ))
        notes.extend(adverse_media)

    # 1c. Domain Verification
    domain = get_domain_from_url(url)
    if domain:
        age = get_domain_age(domain)
        if age != -1:
            notes.append(f"Domain Age: {age} days")
            if age < 30:
                issues.append(f"High Risk: Domain is very new ({age} days old).")
                risk_score_increase += 0.5
                action_items.append(create_action_item(
                    category=ActionCategory.WEBSITE,
                    severity=ActionSeverity.WARNING,
                    title="Verify domain ownership",
                    description=f"Your domain is very new ({age} days old), which increases risk assessment.",
                    suggestion="Provide additional documentation to verify your business legitimacy, such as business registration, trade license, or other official documents.",
                ))
        else:
            notes.append("Domain Age: Could not verify")

        if not has_mx_records(domain):
            issues.append("High Risk: Domain has no email (MX) records.")
            risk_score_increase += 0.5
            action_items.append(create_action_item(
                category=ActionCategory.WEBSITE,
                severity=ActionSeverity.WARNING,
                title="Setup business email",
                description="Your domain has no email (MX) records configured.",
                suggestion="Configure email for your domain (e.g., support@yourdomain.com). This improves legitimacy and customer trust.",
            ))
        else:
            notes.append("MX Records: Valid")

    # Browser-based checks
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            homepage_content = (await page.content()).lower()

            # Capture Homepage Evidence
            hp_screenshot = await capture_screenshot(page, merchant_id, "homepage")
            if hp_screenshot:
                evidence_files.append(hp_screenshot)

            # Vision Analysis
            vision_risk = await analyze_vision_risk(hp_screenshot)
            if vision_risk > 0.5:
                issues.append(f"Vision Analysis flagged high risk ({vision_risk}).")
                risk_score_increase += vision_risk

            # Prohibited Content Scan
            found_prohibited = [w for w in PROHIBITED_KEYWORDS if w in homepage_content]
            if found_prohibited:
                issues.append(f"Prohibited content detected: {', '.join(found_prohibited)}")
                risk_score_increase += 0.5
                action_items.append(create_action_item(
                    category=ActionCategory.COMPLIANCE,
                    severity=ActionSeverity.BLOCKING,
                    title="Remove prohibited content",
                    description=f"Your website contains prohibited keywords: {', '.join(found_prohibited)}",
                    suggestion="Remove or modify content containing prohibited terms. If this is a false positive, provide clarification about your business nature.",
                ))

            # Contact Information Check
            emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", homepage_content)
            phones = re.findall(r"\+?\d[\d -]{8,12}\d", homepage_content)
            if not emails and not phones:
                issues.append("No contact information found on homepage.")
                action_items.append(create_action_item(
                    category=ActionCategory.WEBSITE,
                    severity=ActionSeverity.BLOCKING,
                    title="Add contact information to website",
                    description="No email address or phone number was found on your homepage.",
                    suggestion="Add a visible contact section with email and/or phone number. This is required for customer support and builds trust.",
                    required_format="Email (support@yourdomain.com) and/or phone number",
                ))

            # Policy Pages Check
            links = await find_policy_links(page)
            required_policies = {
                "privacy_policy": "Privacy Policy",
                "terms_of_service": "Terms of Service", 
                "refund_policy": "Refund/Return Policy",
            }

            for policy_key, policy_name in required_policies.items():
                if policy_key in links:
                    policy_url = links[policy_key]
                    if not policy_url.startswith("http"):
                        policy_url = url.rstrip("/") + "/" + policy_url.lstrip("/")

                    try:
                        await page.goto(policy_url, timeout=10000)
                        pol_screenshot = await capture_screenshot(page, merchant_id, policy_key)
                        if pol_screenshot:
                            evidence_files.append(pol_screenshot)
                        notes.append(f"Verified {policy_name} at {policy_url}")
                    except Exception as nav_e:
                        issues.append(f"{policy_name} link broken: {str(nav_e)}")
                        action_items.append(create_action_item(
                            category=ActionCategory.WEBSITE,
                            severity=ActionSeverity.BLOCKING,
                            title=f"Fix {policy_name} page",
                            description=f"The {policy_name} page exists but cannot be loaded.",
                            suggestion=f"Check that the {policy_name} page at {policy_url} is accessible and not broken.",
                        ))
                else:
                    issues.append(f"Missing {policy_name} page")
                    action_items.append(create_action_item(
                        category=ActionCategory.WEBSITE,
                        severity=ActionSeverity.BLOCKING,
                        title=f"Add {policy_name} page",
                        description=f"Your website is missing a {policy_name} page, which is required for compliance.",
                        suggestion=f"Create a {policy_name} page and add a link to it in your website footer. You can customize the template below for your business.",
                        sample_content=POLICY_TEMPLATES.get(policy_key, "").replace("[Company Name]", company_name),
                    ))

        except Exception as e:
            print(f"Playwright navigation error: {e}")
            issues.append(f"Website unreachable: {str(e)}")
            action_items.append(create_action_item(
                category=ActionCategory.WEBSITE,
                severity=ActionSeverity.BLOCKING,
                title="Ensure website is accessible",
                description=f"Could not access your website. Error: {str(e)}",
                suggestion="Verify your website is online and accessible. Check for server issues, DNS configuration, or firewall settings.",
                field_to_update="business_details.website_url",
                current_value=url,
            ))

        finally:
            await browser.close()

    # Result Aggregation
    current_risk = state.get("risk_score", 0.0)
    new_risk = min(1.0, current_risk + risk_score_increase)
    notes.extend([f"Evidence saved: {f}" for f in evidence_files])

    if issues:
        return {
            "is_website_compliant": False,
            "compliance_issues": issues,
            "verification_notes": notes,
            "risk_score": new_risk,
            "missing_artifacts": issues,
            "error_message": "Website compliance checks failed",
            "action_items": action_items,
        }

    return {
        "is_website_compliant": True,
        "verification_notes": notes + ["All website compliance checks passed"],
        "risk_score": new_risk,
        "action_items": [],
    }
