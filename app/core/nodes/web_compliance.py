"""
Web Compliance Node - Checks website for required policies and compliance.

INPUT:
  - application_data.business_details.website_url

OUTPUT:
  - is_website_compliant: bool
  - compliance_issues: list of issues found
  - action_items: compliance issues (if any)

TOOLS:
  - check_ssl
  - fetch_webpage_sync
  - check_page_policies
  - take_screenshot
"""

from typing import Any, Dict
from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity


class WebComplianceNode(BaseNode):
    """
    Checks merchant website for compliance requirements.
    
    Checks:
    - SSL/HTTPS enabled
    - Privacy Policy page
    - Terms of Service page
    - Refund/Return Policy page
    - Contact information
    
    Future enhancements:
    - Screenshot evidence capture
    - Content quality analysis (LLM)
    - Adverse media check
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="web_compliance_node",
            display_name="Web Compliance",
            description="Checks website for SSL, policies, and contact info",
            stage="COMPLIANCE",
            available_tools=[
                "check_ssl",
                "fetch_webpage_sync",
                "check_page_policies",
                "take_screenshot",
            ],
            simulation_key="web",
            llm=LLMConfig(
                enabled=False,  # Can enable for content quality analysis
                system_prompt="You are analyzing a merchant website for payment gateway compliance."
            ),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Check website compliance.
        """
        self._log("Checking website compliance...")
        
        business_details = input.application_data.get("business_details", {})
        website_url = business_details.get("website_url", "")
        
        action_items = []
        compliance_issues = []
        
        # --- Force Success Mode ---
        if self.should_skip_checks():
            self._add_note("SIMULATION: Web compliance checks skipped (force_success)")
            return NodeOutput(
                state_updates={
                    "is_website_compliant": True,
                    "compliance_issues": [],
                    "stage": "COMPLIANCE",
                },
                action_items=[],
                verification_notes=["Website compliance passed (simulated)"],
            )
        
        # --- Simulate Failures ---
        if self.should_simulate_failure("no_ssl"):
            self._add_note("SIMULATION: No SSL failure triggered")
            compliance_issues.append("Website is not using HTTPS (Insecure)")
            action_items.append(self._create_ssl_action_item(website_url))
        
        if self.should_simulate_failure("no_privacy"):
            self._add_note("SIMULATION: No privacy policy failure triggered")
            compliance_issues.append("Missing Privacy Policy page")
            action_items.append(self._create_privacy_action_item())
        
        if self.should_simulate_failure("no_terms"):
            self._add_note("SIMULATION: No terms failure triggered")
            compliance_issues.append("Missing Terms of Service page")
            action_items.append(self._create_terms_action_item())
        
        if self.should_simulate_failure("no_refund"):
            self._add_note("SIMULATION: No refund policy failure triggered")
            compliance_issues.append("Missing Refund/Return Policy page")
            action_items.append(self._create_refund_action_item())
        
        if self.should_simulate_failure("no_contact"):
            self._add_note("SIMULATION: No contact info failure triggered")
            compliance_issues.append("No contact information found")
            action_items.append(self._create_contact_action_item())
        
        # Return early if simulated failures
        if action_items:
            return NodeOutput(
                state_updates={
                    "is_website_compliant": False,
                    "compliance_issues": compliance_issues,
                    "error_message": "Website compliance checks failed",
                    "stage": "COMPLIANCE",
                },
                action_items=action_items,
            )
        
        # --- Real Checks ---
        
        # No website provided
        if not website_url:
            self._add_note("No website URL provided, skipping compliance checks")
            return NodeOutput(
                state_updates={
                    "is_website_compliant": True,  # Pass for merchants without websites
                    "stage": "COMPLIANCE",
                },
                verification_notes=["No website provided, skipping checks"],
            )
        
        # Normalize URL
        if not website_url.startswith(('http://', 'https://')):
            website_url = f"https://{website_url}"
        
        # Check SSL
        ssl_result = self.call_tool("check_ssl", {"url": website_url})
        if ssl_result.success and ssl_result.data:
            if not ssl_result.data.get("has_ssl"):
                compliance_issues.append("Website is not using HTTPS (Insecure)")
                action_items.append(self._create_ssl_action_item(website_url))
            elif not ssl_result.data.get("certificate_valid"):
                compliance_issues.append("SSL certificate is invalid or expired")
                action_items.append(self.create_action_item(
                    category=ActionCategory.WEBSITE,
                    severity=ActionSeverity.BLOCKING,
                    title="Fix SSL certificate",
                    description="Your SSL certificate is invalid or expired.",
                    suggestion="Contact your hosting provider to renew or fix your SSL certificate.",
                ))
            else:
                expiry_days = ssl_result.data.get("expiry_days")
                if expiry_days and expiry_days < 30:
                    compliance_issues.append(f"SSL certificate expires in {expiry_days} days")
                    action_items.append(self.create_action_item(
                        category=ActionCategory.WEBSITE,
                        severity=ActionSeverity.WARNING,
                        title="Renew SSL certificate soon",
                        description=f"Your SSL certificate expires in {expiry_days} days.",
                        suggestion="Renew your SSL certificate to avoid disruption.",
                    ))
                else:
                    self._add_note(f"SSL valid, expires in {expiry_days} days")
        
        # Fetch webpage and check policies
        fetch_result = self.call_tool("fetch_webpage_sync", {
            "url": website_url,
            "timeout": 30,
        })
        
        if fetch_result.success and fetch_result.data:
            html = fetch_result.data.get("html", "")
            
            # Check for required policies
            policy_result = self.call_tool("check_page_policies", {
                "html": html,
                "base_url": website_url,
            })
            
            if policy_result.success and policy_result.data:
                policies = policy_result.data
                
                if not policies.get("has_privacy_policy"):
                    compliance_issues.append("Missing Privacy Policy page")
                    action_items.append(self._create_privacy_action_item())
                else:
                    self._add_note("Privacy Policy found")
                
                if not policies.get("has_terms"):
                    compliance_issues.append("Missing Terms of Service page")
                    action_items.append(self._create_terms_action_item())
                else:
                    self._add_note("Terms of Service found")
                
                if not policies.get("has_refund_policy"):
                    compliance_issues.append("Missing Refund/Return Policy page")
                    action_items.append(self._create_refund_action_item())
                else:
                    self._add_note("Refund Policy found")
                
                if not policies.get("has_contact_info"):
                    compliance_issues.append("No contact information found")
                    action_items.append(self._create_contact_action_item())
                else:
                    self._add_note("Contact info found")
        else:
            compliance_issues.append(f"Could not fetch website: {fetch_result.error}")
            action_items.append(self.create_action_item(
                category=ActionCategory.WEBSITE,
                severity=ActionSeverity.WARNING,
                title="Ensure website is accessible",
                description=f"Could not access your website: {fetch_result.error}",
                suggestion="Make sure your website is online and publicly accessible.",
                field_to_update="business_details.website_url",
                current_value=website_url,
            ))
        
        # Determine final compliance
        blocking_count = sum(1 for item in action_items if item.get("severity") == "BLOCKING")
        is_compliant = blocking_count == 0
        
        return NodeOutput(
            state_updates={
                "is_website_compliant": is_compliant,
                "compliance_issues": compliance_issues,
                "stage": "COMPLIANCE",
                "error_message": "Website compliance checks failed" if not is_compliant else None,
            },
            action_items=action_items,
            verification_notes=[
                f"Website: {website_url}",
                f"Issues found: {len(compliance_issues)}",
                f"Blocking issues: {blocking_count}",
            ],
        )
    
    # --- Action Item Helpers ---
    
    def _create_ssl_action_item(self, url: str):
        return self.create_action_item(
            category=ActionCategory.WEBSITE,
            severity=ActionSeverity.BLOCKING,
            title="Enable HTTPS/SSL on your website",
            description="Your website is not using HTTPS, which is required for secure payment processing.",
            suggestion="Install an SSL certificate. Most hosting providers offer free SSL via Let's Encrypt.",
            field_to_update="business_details.website_url",
            current_value=url,
        )
    
    def _create_privacy_action_item(self):
        return self.create_action_item(
            category=ActionCategory.COMPLIANCE,
            severity=ActionSeverity.BLOCKING,
            title="Add Privacy Policy page",
            description="A Privacy Policy is legally required for collecting customer data.",
            suggestion="Create a Privacy Policy page and link it in your website footer.",
            sample_content="Your Privacy Policy should explain what data you collect, how you use it, and how customers can request deletion.",
        )
    
    def _create_terms_action_item(self):
        return self.create_action_item(
            category=ActionCategory.COMPLIANCE,
            severity=ActionSeverity.BLOCKING,
            title="Add Terms of Service page",
            description="Terms of Service define the rules for using your website and services.",
            suggestion="Create a Terms of Service page and link it in your website footer.",
            sample_content="Your Terms should cover user responsibilities, payment terms, and dispute resolution.",
        )
    
    def _create_refund_action_item(self):
        return self.create_action_item(
            category=ActionCategory.COMPLIANCE,
            severity=ActionSeverity.BLOCKING,
            title="Add Refund/Return Policy page",
            description="A clear refund policy is required for accepting online payments.",
            suggestion="Create a Refund Policy page explaining your return and refund process.",
            sample_content="Your policy should explain how to request refunds, timeline, and any conditions.",
        )
    
    def _create_contact_action_item(self):
        return self.create_action_item(
            category=ActionCategory.COMPLIANCE,
            severity=ActionSeverity.BLOCKING,
            title="Add contact information to website",
            description="Contact information is required for customer support.",
            suggestion="Add a visible contact section with email and/or phone number.",
        )


# Create callable for LangGraph
web_compliance_node = WebComplianceNode()

