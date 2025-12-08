import asyncio
import os
import re
import base64
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.schema import AgentState
from playwright.async_api import async_playwright
from app.utils.llm_factory import get_llm
from app.utils.adverse_media import check_reputation
from app.utils.domain_checks import get_domain_from_url, get_domain_age, has_mx_records
from langchain_core.messages import HumanMessage

# --- Configuration ---
EVIDENCE_DIR = "evidence"
PROHIBITED_KEYWORDS = [
    "gambling",
    "casino",
    "drugs",
    "weapons",
    "firearms",
    "adult",
    "porn",
    "bitcoin",
    "crypto",
]
FUNCTIONALITY_KEYWORDS = [
    "add to cart",
    "buy now",
    "checkout",
    "subscribe",
    "book now",
    "pricing",
]


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
        # Read image and encode to base64
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        llm = (
            get_llm()
        )  # Factory will return a model (Vision support assumed for advanced models like Gemini/GPT-4o)

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
        # Note: If the configured model doesn't support images, this might fail. We wrap in try/except.
        response = await llm.ainvoke([message])
        content = response.content.lower()

        # Simple heuristic parsing of the score (robustness could be improved)
        # Assuming the LLM returns something like "Risk Score: 0.2"
        import re

        match = re.search(r"risk score:\s*(\d+(\.\d+)?)", content)
        if match:
            return float(match.group(1))

        if "high risk" in content:
            return 0.8
        if "medium risk" in content:
            return 0.5
        return 0.1  # Default low risk if nothing flagged

    except Exception as e:
        print(f"Vision Analysis Failed: {e}")
        return 0.0


async def find_policy_links(page) -> Dict[str, str]:
    """Finds links to key policy pages on the current page."""
    links = {}
    # Simple keyword search in hrefs and text
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
    """
    url = state["application_data"]["business_details"]["website_url"]
    merchant_id = state.get("merchant_id", "unknown")

    issues = []
    notes = []
    risk_score_increase = 0.0
    evidence_files = []

    print(f"--- Web Compliance Check: {url} ---")

    # 1. SSL Check
    if not url.startswith("https://"):
        issues.append("Website is not using HTTPS (Insecure).")
        risk_score_increase += 1.0  # Immediate high risk
        notes.append("SSL Check: FAILED")
    else:
        notes.append("SSL Check: PASSED")

    # 1b. Adverse Media Scan (Open Source)
    # Use the company name from business details
    company_name = state["application_data"]["business_details"].get(
        "entity_type", "Merchant"
    )  # actually name?
    # Current schema: 'business_details': {'pan': ..., 'entity_type': ...}
    # Wait, looking at sample data in verify_workflow.py:
    # "signatory_details": {'name': 'John Doe'...}
    # "bank_details": {'account_holder_name': 'Test Merchant'} <-- Using this as proxy for now
    merchant_name = state["application_data"]["bank_details"].get(
        "account_holder_name", "Unknown Merchant"
    )

    adverse_media = check_reputation(merchant_name)
    if adverse_media:
        # Filter out "Search failed" warnings from high risk score impact, just add to notes/issues
        real_hits = [m for m in adverse_media if "Search failed" not in m]
        if real_hits:
            issues.append(f"Adverse Media Found: {len(real_hits)} suspicious items.")
            risk_score_increase += 0.5 * len(real_hits)  # High impact

        notes.extend(adverse_media)

    # 1c. Domain & Infrastructure Verification
    domain = get_domain_from_url(url)
    if domain:
        # Check Domain Age
        age = get_domain_age(domain)
        if age != -1:
            notes.append(f"Domain Age: {age} days")
            if age < 30:  # New domain < 1 month
                issues.append(f"High Risk: Domain is very new ({age} days old).")
                risk_score_increase += 0.5
        else:
            notes.append("Domain Age: Could not verify")

        # Check MX Records
        has_mx = has_mx_records(domain)
        if not has_mx:
            issues.append("High Risk: Domain has no email (MX) records.")
            risk_score_increase += 0.5
        else:
            notes.append("MX Records: Valid")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Create context to set user agent (avoid bot detection) and ignore HTTPS errors for testing if needed
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # 2. Homepage Analysis
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")
            homepage_content = (await page.content()).lower()

            # Capture Homepage Evidence
            hp_screenshot = await capture_screenshot(page, merchant_id, "homepage")
            if hp_screenshot:
                evidence_files.append(hp_screenshot)

            # 2a. Vision Analysis (on Homepage)
            # Only run if we have a screenshot and we are in production mode (to save costs/API calls in dev)
            # For hackathon, we assume we want to show it off, so we'll try it if credentials exist.
            vision_risk = await analyze_vision_risk(hp_screenshot)
            if vision_risk > 0.5:
                issues.append(
                    f"Vision Analysis flagged high risk ({vision_risk}). Potential deceptive branding."
                )
                risk_score_increase += vision_risk

            # 3. Prohibited Content Scan
            found_prohibited = [
                word for word in PROHIBITED_KEYWORDS if word in homepage_content
            ]
            if found_prohibited:
                issues.append(
                    f"Prohibited content detected: {', '.join(found_prohibited)}"
                )
                risk_score_increase += 0.5

            # 4. Functionality Check (Add to Cart)
            is_functional = any(
                keyword in homepage_content for keyword in FUNCTIONALITY_KEYWORDS
            )
            if not is_functional:
                # Try to see if there is a 'Shop' or 'Store' link to check there?
                # For now, just flag it as a warning
                issues.append(
                    "No active 'Add to Cart' or 'Checkout' functionality detected on homepage."
                )
                # We don't fail hard, just note it.

            # 5. Contact Extraction (Regex)
            # Simple regex for emails
            emails = re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", homepage_content
            )
            phones = re.findall(
                r"\+?\d[\d -]{8,12}\d", homepage_content
            )  # Very basic phone regex
            if not emails and not phones:
                issues.append("No contact information (Email/Phone) found on homepage.")

            # 6. Deep Navigation (Find Policies)
            links = await find_policy_links(page)
            required_policies = ["privacy_policy", "terms_of_service", "refund_policy"]

            for policy in required_policies:
                if policy in links:
                    policy_url = links[policy]
                    # Handle relative URLs
                    if not policy_url.startswith("http"):
                        policy_url = url.rstrip("/") + "/" + policy_url.lstrip("/")

                    try:
                        print(f"Navigating to {policy}: {policy_url}")
                        await page.goto(policy_url, timeout=10000)

                        # Capture Policy Evidence
                        pol_screenshot = await capture_screenshot(
                            page, merchant_id, policy
                        )
                        if pol_screenshot:
                            evidence_files.append(pol_screenshot)

                        # Extract Text (We could store this in state for the LLM to review later)
                        # policy_text = await page.inner_text("body")
                        notes.append(f"Verified {policy} at {policy_url}")

                    except Exception as nav_e:
                        print(f"Could not load {policy}: {nav_e}")
                        issues.append(
                            f"Found {policy} link but could not load page: {str(nav_e)}"
                        )
                else:
                    issues.append(f"Missing Link for {policy}")

        except Exception as e:
            print(f"Playwright navigation error: {e}")
            issues.append(f"Website unreachable or timeout: {str(e)}")

        finally:
            await browser.close()

    # --- Result Aggregation ---

    # Calculate Impact on Risk Score
    current_risk = state.get("risk_score", 0.0)
    new_risk = min(1.0, current_risk + risk_score_increase)

    # Verification Notes
    notes.extend([f"Evidence saved: {f}" for f in evidence_files])

    if issues:
        return {
            "is_website_compliant": False,
            "compliance_issues": issues,
            "verification_notes": notes,
            "risk_score": new_risk,
            "missing_artifacts": issues,
            "error_message": "Website compliance checks failed",
            # We route to consultant to fix/explain these issues
        }

    return {
        "is_website_compliant": True,
        "verification_notes": notes + ["All website compliance checks passed"],
        "risk_score": new_risk,
        # Decrease risk if everything is perfect? For now stay neutral.
    }
