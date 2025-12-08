from typing import Any, Dict
from schema import AgentState
from playwright.sync_api import sync_playwright


def web_compliance_node(state: AgentState) -> Dict[str, Any]:
    """
    Checks the merchant's website for compliance policies using Playwright.
    Corresponds to Step 8.
    """
    print("--- [Node] Web Compliance ---")
    url = state["application_data"].get("business_details", {}).get("website_url")

    if not url:
        return {
            "is_website_compliant": False,
            "error_message": "No website URL provided for compliance check.",
            "next_step": "consultant_fixer_node",
        }

    REQUIRED_KEYWORDS = ["privacy policy", "terms of service", "refund policy"]
    missing_policies = []

    try:
        with sync_playwright() as p:
            # We use a headless browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"Navigating to {url}...")
            # For hackathon safety/speed, and to avoid errors with invalid user inputs,
            # we might wrap this carefully.
            # Also, since we are in a 'Code' environment, local network access or restricted internet might apply.
            # We'll try-except.
            try:
                page.goto(url, timeout=10000)
                content = page.content().lower()

                for keyword in REQUIRED_KEYWORDS:
                    if keyword not in content:
                        missing_policies.append(keyword)

            except Exception as e:
                print(f"Playwright navigation error: {e}")
                return {
                    "is_website_compliant": False,
                    "error_message": f"Website unreachable: {str(e)}",
                    "next_step": "consultant_fixer_node",
                }
            finally:
                browser.close()

    except Exception as e:
        # Fallback if playwright fails entirely (e.g. system deps missing)
        return {
            "is_website_compliant": False,
            "error_message": f"Compliance check system infrastructure error: {e}",
            "next_step": "consultant_fixer_node",
        }

    if missing_policies:
        return {
            "is_website_compliant": False,
            "compliance_issues": [f"Missing {p}" for p in missing_policies],
            "error_message": "Website compliance policies missing",
            "next_step": "consultant_fixer_node",
        }

    return {
        "is_website_compliant": True,
        "verification_notes": ["Website compliance checks passed"],
    }
