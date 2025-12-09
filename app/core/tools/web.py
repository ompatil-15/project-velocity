"""
Web Tools - Website compliance checks, SSL verification, page fetching.
"""

import re
from typing import Any, Dict, List, Optional
from app.core.tool_registry import tool_registry


@tool_registry.register(
    name="check_ssl",
    description="Check if a website has valid SSL/HTTPS",
    input_schema={
        "url": {"type": "string", "format": "uri", "description": "Website URL to check"}
    },
    output_schema={
        "has_ssl": {"type": "boolean"},
        "certificate_valid": {"type": "boolean"},
        "expiry_days": {"type": "integer", "nullable": True},
        "error": {"type": "string", "nullable": True}
    },
    category="web",
    requires_network=True,
    mock_output={
        "has_ssl": True,
        "certificate_valid": True,
        "expiry_days": 180,
        "error": None
    }
)
def check_ssl(url: str) -> Dict[str, Any]:
    """
    Check SSL certificate for a URL.
    """
    import ssl
    import socket
    from urllib.parse import urlparse
    from datetime import datetime
    
    try:
        parsed = urlparse(url)
        hostname = parsed.netloc or parsed.path.split('/')[0]
        hostname = hostname.split(':')[0]  # Remove port if present
        
        if not hostname:
            return {
                "has_ssl": False,
                "certificate_valid": False,
                "expiry_days": None,
                "error": "Invalid URL"
            }
        
        # Check if URL uses HTTPS
        if not url.startswith('https://'):
            # Try to connect anyway to see if SSL is available
            pass
        
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                # Parse expiry date
                expiry_str = cert.get('notAfter', '')
                if expiry_str:
                    expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (expiry_date - datetime.now()).days
                else:
                    days_until_expiry = None
                
                return {
                    "has_ssl": True,
                    "certificate_valid": True,
                    "expiry_days": days_until_expiry,
                    "error": None
                }
                
    except ssl.SSLError as e:
        return {
            "has_ssl": True,
            "certificate_valid": False,
            "expiry_days": None,
            "error": f"SSL error: {str(e)}"
        }
    except socket.timeout:
        return {
            "has_ssl": False,
            "certificate_valid": False,
            "expiry_days": None,
            "error": "Connection timeout"
        }
    except Exception as e:
        return {
            "has_ssl": False,
            "certificate_valid": False,
            "expiry_days": None,
            "error": str(e)
        }


@tool_registry.register(
    name="fetch_webpage",
    description="Fetch HTML content from a webpage",
    input_schema={
        "url": {"type": "string", "format": "uri", "description": "URL to fetch"},
        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
    },
    output_schema={
        "success": {"type": "boolean"},
        "html": {"type": "string"},
        "status_code": {"type": "integer"},
        "error": {"type": "string", "nullable": True}
    },
    category="web",
    requires_network=True,
    is_async=True,
    mock_output={
        "success": True,
        "html": "<html><head><title>Mock Store</title></head><body><h1>Welcome</h1><a href='/privacy'>Privacy Policy</a><a href='/terms'>Terms</a><a href='/refund'>Refund Policy</a><footer>Contact: test@example.com</footer></body></html>",
        "status_code": 200,
        "error": None
    }
)
async def fetch_webpage(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Fetch webpage content using async HTTP client.
    """
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            
            return {
                "success": response.status_code == 200,
                "html": response.text,
                "status_code": response.status_code,
                "error": None if response.status_code == 200 else f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "status_code": 0,
            "error": str(e)
        }


# Sync version for non-async contexts
@tool_registry.register(
    name="fetch_webpage_sync",
    description="Fetch HTML content from a webpage (synchronous)",
    input_schema={
        "url": {"type": "string", "format": "uri", "description": "URL to fetch"},
        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
    },
    output_schema={
        "success": {"type": "boolean"},
        "html": {"type": "string"},
        "status_code": {"type": "integer"},
        "error": {"type": "string", "nullable": True}
    },
    category="web",
    requires_network=True,
    mock_output={
        "success": True,
        "html": "<html><head><title>Mock Store</title></head><body><h1>Welcome</h1><a href='/privacy'>Privacy Policy</a><a href='/terms'>Terms</a><a href='/refund'>Refund Policy</a><footer>Contact: test@example.com</footer></body></html>",
        "status_code": 200,
        "error": None
    }
)
def fetch_webpage_sync(url: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Fetch webpage content using sync HTTP client.
    """
    try:
        import httpx
        
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            
            return {
                "success": response.status_code == 200,
                "html": response.text,
                "status_code": response.status_code,
                "error": None if response.status_code == 200 else f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "html": "",
            "status_code": 0,
            "error": str(e)
        }


@tool_registry.register(
    name="check_page_policies",
    description="Check if webpage has required policy pages (Privacy, Terms, Refund)",
    input_schema={
        "html": {"type": "string", "description": "HTML content to analyze"},
        "base_url": {"type": "string", "description": "Base URL for relative links"}
    },
    output_schema={
        "has_privacy_policy": {"type": "boolean"},
        "has_terms": {"type": "boolean"},
        "has_refund_policy": {"type": "boolean"},
        "has_contact_info": {"type": "boolean"},
        "found_links": {"type": "array", "items": {"type": "string"}}
    },
    category="web",
    mock_output={
        "has_privacy_policy": True,
        "has_terms": True,
        "has_refund_policy": True,
        "has_contact_info": True,
        "found_links": ["/privacy", "/terms", "/refund"]
    }
)
def check_page_policies(html: str, base_url: str = "") -> Dict[str, Any]:
    """
    Analyze HTML for required policy pages and contact info.
    """
    html_lower = html.lower()
    
    # Privacy policy patterns
    privacy_patterns = [
        r'privacy\s*policy',
        r'href=["\'][^"\']*privacy[^"\']*["\']',
        r'data\s*protection',
    ]
    has_privacy = any(re.search(p, html_lower) for p in privacy_patterns)
    
    # Terms patterns
    terms_patterns = [
        r'terms\s*(of\s*)?(service|use|conditions)',
        r'href=["\'][^"\']*terms[^"\']*["\']',
        r'user\s*agreement',
    ]
    has_terms = any(re.search(p, html_lower) for p in terms_patterns)
    
    # Refund patterns
    refund_patterns = [
        r'refund\s*policy',
        r'return\s*policy',
        r'cancellation\s*policy',
        r'href=["\'][^"\']*refund[^"\']*["\']',
        r'href=["\'][^"\']*return[^"\']*["\']',
    ]
    has_refund = any(re.search(p, html_lower) for p in refund_patterns)
    
    # Contact info patterns
    contact_patterns = [
        r'contact\s*us',
        r'[\w.+-]+@[\w-]+\.[\w.-]+',  # Email
        r'\+?\d{10,}',  # Phone
        r'mailto:',
    ]
    has_contact = any(re.search(p, html_lower) for p in contact_patterns)
    
    # Extract policy links
    link_pattern = r'href=["\']([^"\']*(?:privacy|terms|refund|return|contact)[^"\']*)["\']'
    found_links = list(set(re.findall(link_pattern, html_lower)))
    
    return {
        "has_privacy_policy": has_privacy,
        "has_terms": has_terms,
        "has_refund_policy": has_refund,
        "has_contact_info": has_contact,
        "found_links": found_links[:10]  # Limit to 10
    }


@tool_registry.register(
    name="take_screenshot",
    description="Take a screenshot of a webpage",
    input_schema={
        "url": {"type": "string", "format": "uri", "description": "URL to screenshot"},
        "output_path": {"type": "string", "description": "Path to save screenshot"}
    },
    output_schema={
        "success": {"type": "boolean"},
        "path": {"type": "string"},
        "error": {"type": "string", "nullable": True}
    },
    category="web",
    requires_network=True,
    is_async=True,
    mock_output={
        "success": True,
        "path": "/evidence/mock_screenshot.png",
        "error": None
    }
)
async def take_screenshot(url: str, output_path: str) -> Dict[str, Any]:
    """
    Take screenshot using Playwright.
    """
    try:
        from playwright.async_api import async_playwright
        import os
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=30000)
            await page.screenshot(path=output_path, full_page=True)
            await browser.close()
        
        return {
            "success": True,
            "path": output_path,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "path": "",
            "error": str(e)
        }

