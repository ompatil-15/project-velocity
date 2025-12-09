"""
Domain verification utilities.

Provides functions for checking domain age and email configuration.
"""

import whois
import dns.resolver
from datetime import datetime
from urllib.parse import urlparse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL (e.g., http://example.com/foo -> example.com)."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return ""


def get_domain_age(domain: str) -> int:
    """
    Return the age of the domain in days.
    Returns -1 if lookup fails or data unavailable.
    """
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date

        if isinstance(creation_date, list):
            creation_date = creation_date[0]

        if not creation_date:
            return -1

        now = datetime.now()
        age = (now - creation_date).days
        return age
    except Exception as e:
        logger.warning("WHOIS lookup failed for %s: %s", domain, e)
        return -1


def has_mx_records(domain: str) -> bool:
    """Check if the domain has valid MX (Mail Exchange) records."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except Exception as e:
        logger.warning("MX record check failed for %s: %s", domain, e)
        return False
