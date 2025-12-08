from duckduckgo_search import DDGS
from typing import List, Optional


def check_reputation(merchant_name: str) -> List[str]:
    """
    Checks for adverse media (scams, fraud, bad reviews) using DuckDuckGo.
    Returns a list of suspicious result titles/links.
    """
    suspicious_findings = []

    # We combine queries to save time, or run multiple.
    # Let's run a targeted query.
    query = f'"{merchant_name}" scam OR fraud OR "bad reviews" OR complaint'

    print(f"Running Adverse Media Scan for: {merchant_name}")

    try:
        with DDGS() as ddgs:
            # Get top 5 results
            results = list(ddgs.text(query, max_results=5))

            for r in results:
                title = r.get("title", "").lower()
                body = r.get("body", "").lower()
                href = r.get("href", "")

                # Check for red flags in the search results
                red_flags = [
                    "scam",
                    "fraud",
                    "beware",
                    "fake",
                    "stolen",
                    "complaint",
                    "rip off",
                ]
                if any(flag in title or flag in body for flag in red_flags):
                    suspicious_findings.append(
                        f"Suspicious Result: {r.get('title')} ({href})"
                    )

    except Exception as e:
        print(f"Adverse Media Scan failed: {e}")
        # Fail open (don't block onboarding if search fails, but log it)
        suspicious_findings.append(
            f"Adverse Media Scan Warning: Search failed ({str(e)})"
        )

    return suspicious_findings
