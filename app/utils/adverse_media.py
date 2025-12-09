"""
Adverse media scanning utility.

Checks for negative news, scams, and fraud reports associated with merchants.
"""

from duckduckgo_search import DDGS
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)


def check_reputation(merchant_name: str) -> List[str]:
    """
    Check for adverse media (scams, fraud, bad reviews) using DuckDuckGo.
    Returns a list of suspicious result titles/links.
    """
    suspicious_findings = []
    query = f'"{merchant_name}" scam OR fraud OR "bad reviews" OR complaint'

    logger.debug("Running adverse media scan for: %s", merchant_name)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

            for r in results:
                title = r.get("title", "").lower()
                body = r.get("body", "").lower()
                href = r.get("href", "")

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
        logger.warning("Adverse media scan failed: %s", e)
        suspicious_findings.append(
            f"Adverse Media Scan Warning: Search failed ({str(e)})"
        )

    return suspicious_findings
