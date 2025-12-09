"""
Simulation configuration for controlled testing.

In development mode, these configs allow simulating specific failure scenarios
to test all UI states without triggering real failures.

Usage:
    from app.utils.simulation import sim
    
    if sim.should_fail("doc_blurry"):
        # Return simulated failure
    
    if sim.is_dev_mode():
        # Development-specific behavior

Runtime toggle (no restart needed):
    POST /debug/simulate {"doc_blurry": true, "web_no_ssl": true}
    GET  /debug/simulate  → view current flags
    DELETE /debug/simulate → reset all
"""

import os
from typing import Dict, List, Optional


# Runtime overrides (in-memory, no restart needed)
_runtime_flags: Dict[str, bool] = {}


class SimulationConfig:
    """Centralized simulation configuration."""
    
    # All available scenarios
    ALL_SCENARIOS = [
        # Force success (skip real checks)
        "force_success_all",      # Skip ALL checks, return success
        "force_success_doc",      # Skip document checks
        "force_success_bank",     # Skip bank checks  
        "force_success_web",      # Skip web compliance checks
        "force_success_input",    # Skip input validation
        # Force failures
        "doc_blurry", "doc_missing", "doc_invalid",
        "bank_name_mismatch", "bank_invalid_ifsc", "bank_account_closed",
        "web_no_ssl", "web_no_refund_policy", "web_no_privacy_policy",
        "web_no_terms", "web_prohibited_content", "web_domain_new",
        "web_adverse_media", "web_unreachable",
        "input_invalid_pan", "input_invalid_gstin",
    ]
    
    # Map scenario to env var
    ENV_MAP = {
        # Force success (skip checks)
        "force_success_all": "SIMULATE_FORCE_SUCCESS_ALL",
        "force_success_doc": "SIMULATE_FORCE_SUCCESS_DOC",
        "force_success_bank": "SIMULATE_FORCE_SUCCESS_BANK",
        "force_success_web": "SIMULATE_FORCE_SUCCESS_WEB",
        "force_success_input": "SIMULATE_FORCE_SUCCESS_INPUT",
        # Force failures
        "doc_blurry": "SIMULATE_DOC_BLURRY",
        "doc_missing": "SIMULATE_DOC_MISSING",
        "doc_invalid": "SIMULATE_DOC_INVALID",
        "bank_name_mismatch": "SIMULATE_BANK_NAME_MISMATCH",
        "bank_invalid_ifsc": "SIMULATE_BANK_INVALID_IFSC",
        "bank_account_closed": "SIMULATE_BANK_ACCOUNT_CLOSED",
        "web_no_ssl": "SIMULATE_WEB_NO_SSL",
        "web_no_refund_policy": "SIMULATE_WEB_NO_REFUND_POLICY",
        "web_no_privacy_policy": "SIMULATE_WEB_NO_PRIVACY_POLICY",
        "web_no_terms": "SIMULATE_WEB_NO_TERMS",
        "web_prohibited_content": "SIMULATE_WEB_PROHIBITED_CONTENT",
        "web_domain_new": "SIMULATE_WEB_DOMAIN_NEW",
        "web_adverse_media": "SIMULATE_WEB_ADVERSE_MEDIA",
        "web_unreachable": "SIMULATE_WEB_UNREACHABLE",
        "input_invalid_pan": "SIMULATE_INPUT_INVALID_PAN",
        "input_invalid_gstin": "SIMULATE_INPUT_INVALID_GSTIN",
    }
    
    # --- Environment ---
    
    def is_dev_mode(self) -> bool:
        """Check if running in development mode."""
        return os.getenv("ENVIRONMENT", "development").lower() in ("development", "dev", "local")
    
    def is_prod_mode(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
    
    # --- Runtime Flag Management ---
    
    def set_flag(self, scenario: str, enabled: bool) -> bool:
        """Set a simulation flag at runtime (no restart needed)."""
        if scenario not in self.ALL_SCENARIOS:
            return False
        _runtime_flags[scenario] = enabled
        return True
    
    def set_flags(self, flags: Dict[str, bool]) -> Dict[str, bool]:
        """Set multiple flags at once. Returns what was set."""
        result = {}
        for scenario, enabled in flags.items():
            if scenario in self.ALL_SCENARIOS:
                _runtime_flags[scenario] = enabled
                result[scenario] = enabled
        return result
    
    def reset_flags(self) -> None:
        """Clear all runtime flags (revert to env vars)."""
        _runtime_flags.clear()
    
    def get_all_flags(self) -> Dict[str, bool]:
        """Get current state of all flags (runtime + env)."""
        result = {}
        for scenario in self.ALL_SCENARIOS:
            result[scenario] = self.should_fail(scenario)
        return result
    
    # --- Flag Checking ---
    
    def _get_env_flag(self, key: str, default: str = "false") -> bool:
        """Get a simulation flag from environment."""
        return os.getenv(key, default).lower() == "true"
    
    def _check_flag(self, scenario: str) -> bool:
        """Check if a flag is enabled (runtime or env)."""
        if not self.is_dev_mode():
            return False
        if scenario in _runtime_flags:
            return _runtime_flags[scenario]
        env_var = self.ENV_MAP.get(scenario)
        if not env_var:
            return False
        return self._get_env_flag(env_var)
    
    def should_skip(self, node: str) -> bool:
        """
        Check if real checks should be skipped (force success).
        
        In dev mode, DEFAULT is to skip real checks (mock success) unless:
        - SIMULATE_REAL_CHECKS=true (run actual checks)
        - A specific failure is being simulated
        
        Args:
            node: "doc" | "bank" | "web" | "input"
        
        Returns:
            True if checks should be skipped and success returned.
        """
        if not self.is_dev_mode():
            return False  # Production always runs real checks
        
        # Explicit force success
        if self._check_flag("force_success_all"):
            return True
        if self._check_flag(f"force_success_{node}"):
            return True
        
        # Check if real checks are explicitly enabled
        if self._get_env_flag("SIMULATE_REAL_CHECKS"):
            return False  # Run real checks
        
        # Check if any failure is being simulated for this node
        node_failures = {
            "doc": ["doc_blurry", "doc_missing", "doc_invalid"],
            "bank": ["bank_name_mismatch", "bank_invalid_ifsc", "bank_account_closed"],
            "web": ["web_unreachable", "web_no_ssl", "web_no_refund_policy", 
                    "web_no_privacy_policy", "web_no_terms", "web_prohibited_content",
                    "web_domain_new", "web_adverse_media"],
            "input": ["input_invalid_pan", "input_invalid_gstin"],
        }
        
        # If any failure is simulated for this node, don't skip (let failure trigger)
        for failure in node_failures.get(node, []):
            if self._check_flag(failure):
                return False
        
        # DEFAULT in dev mode: skip real checks (mock success)
        return True
    
    def should_fail(self, scenario: str) -> bool:
        """
        Check if a specific failure scenario should be simulated.
        
        Priority: runtime flag > environment variable
        Only works in development mode.
        
        Scenarios:
            Document Node:
                - doc_blurry: Document OCR fails (blurry/unclear)
                - doc_missing: Document file not found
                - doc_invalid: Document missing required fields
            
            Bank Node:
                - bank_name_mismatch: Account holder name doesn't match
                - bank_invalid_ifsc: Invalid IFSC code
                - bank_account_closed: Account is closed/inactive
            
            Web Compliance Node:
                - web_no_ssl: Website doesn't have HTTPS
                - web_no_refund_policy: Missing refund policy
                - web_no_privacy_policy: Missing privacy policy
                - web_no_terms: Missing terms of service
                - web_prohibited_content: Prohibited keywords found
                - web_domain_new: Domain too new (< 30 days)
                - web_adverse_media: Negative news found
                - web_unreachable: Website is down/unreachable
            
            Input Node:
                - input_invalid_pan: Invalid PAN format
                - input_invalid_gstin: Invalid GSTIN format
        """
        # Only simulate in dev mode
        if not self.is_dev_mode():
            return False
        
        # Check runtime override first (no restart needed)
        if scenario in _runtime_flags:
            return _runtime_flags[scenario]
        
        # Fall back to environment variable
        env_var = self.ENV_MAP.get(scenario)
        if not env_var:
            return False
        
        return self._get_env_flag(env_var)
    
    def get_active_simulations(self) -> List[str]:
        """Get list of all currently active simulation flags."""
        return [s for s in self.ALL_SCENARIOS if self.should_fail(s)]
    
    # --- Legacy support ---
    
    def should_fail_doc(self) -> bool:
        """Legacy: Check SIMULATE_DOC_FAILURE flag."""
        return self._get_env_flag("SIMULATE_DOC_FAILURE") or self.should_fail("doc_blurry")


# Singleton instance
sim = SimulationConfig()

