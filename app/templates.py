# Predefined Knowledge Base for the Consultant

REFUND_POLICY_TEMPLATE = """
**Refund Policy**

At {company_name}, we strive to ensure your satisfaction. 
- **Eligibility:** Refunds are processed for requests made within 7 days of purchase.
- **Processing Time:** Approved refunds will be credited to the original payment method within 5-7 business days.
- **Contact:** For issues, please email support@{domain}.
"""

PRIVACY_POLICY_TEMPLATE = """
**Privacy Policy**

{company_name} is committed to protecting your data.
- **Data Collection:** We collect basic user information for order processing.
- **Sharing:** We do not sell your personal data to third parties.
- **Security:** We use industry-standard encryption to protect your information.
"""


def get_template(policy_name: str, company_name: str, domain: str) -> str:
    if "refund" in policy_name.lower():
        return REFUND_POLICY_TEMPLATE.format(company_name=company_name, domain=domain)
    if "privacy" in policy_name.lower():
        return PRIVACY_POLICY_TEMPLATE.format(company_name=company_name, domain=domain)
    return "Template not found."
