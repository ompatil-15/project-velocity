from typing import Any, Dict
import asyncio
import os
from datetime import datetime
from app.schema import AgentState
from playwright.async_api import async_playwright


async def web_compliance_node(state: AgentState) -> Dict[str, Any]:
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
    filename = None  # Initialize filename for scope

    try:
        async with async_playwright() as p:
            # We use a headless browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            print(f"Navigating to {url}...")
            # For hackathon safety/speed, and to avoid errors with invalid user inputs,
            # we might wrap this carefully.
            # Also, since we are in a 'Code' environment, local network access or restricted internet might apply.
            # We'll try-except.
            try:
                await page.goto(url, timeout=10000)
                content = (await page.content()).lower()

                # --- Capture Evidence ---
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # Using merchant_id for filename.
                merchant_id = state.get(
                    "merchant_id", "unknown_merchant"
                )  # Use .get with default for robustness
                filename = f"evidence/{merchant_id}_{timestamp}_homepage.png"

                # Ensure directory exists (defensive)
                os.makedirs("evidence", exist_ok=True)

                await page.screenshot(path=filename)
                print(f"Evidence captured: {filename}")

                issues = (
                    []
                )  # Renamed from missing_policies in the instruction, will use this for return
                for keyword in REQUIRED_KEYWORDS:
                    if keyword not in content:
                        issues.append(
                            f"Missing '{keyword}'"
                        )  # Store as formatted string
                        missing_policies.append(
                            keyword
                        )  # Keep original for backward compatibility if needed

            except Exception as e:
                print(f"Playwright navigation error: {e}")
                return {
                    "is_website_compliant": False,
                    "error_message": f"Website unreachable: {str(e)}",
                    "next_step": "consultant_fixer_node",
                }
            finally:
                await browser.close()

    except Exception as e:
        # Fallback if playwright fails entirely (e.g. system deps missing)
        return {
            "is_website_compliant": False,
            "error_message": f"Compliance check system infrastructure error: {e}",
            "next_step": "consultant_fixer_node",
        }

    if issues:  # Check the 'issues' list
        return {
            "is_website_compliant": False,
            "compliance_issues": issues,
            "verification_notes": [
                f"Website visited: {url}",
                f"Evidence saved: {filename}" if filename else "No evidence captured",
            ],
            "error_message": "Website compliance policies missing",
            "missing_artifacts": issues,  # Treating issues as missing artifacts
            "next_step": "consultant_fixer_node",
        }

    return {
        "is_website_compliant": True,
        "verification_notes": [
            f"Website compliance checks passed",
            f"Website visited: {url}",
            f"Evidence saved: {filename}" if filename else "No evidence captured",
        ],
    }
