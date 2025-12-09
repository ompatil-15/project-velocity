from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from enum import Enum
from datetime import datetime
import uuid


# --- Job Status Tracking ---

class JobStatus(str, Enum):
    """Status of an onboarding job."""
    QUEUED = "QUEUED"           # Job received, waiting to start
    PROCESSING = "PROCESSING"    # Workflow is running
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Waiting for merchant intervention
    COMPLETED = "COMPLETED"      # Successfully completed
    FAILED = "FAILED"            # Failed with error


class ActionCategory(str, Enum):
    """Category of action item."""
    DOCUMENT = "DOCUMENT"
    BANK = "BANK"
    COMPLIANCE = "COMPLIANCE"
    WEBSITE = "WEBSITE"
    DATA = "DATA"


class ActionSeverity(str, Enum):
    """Severity of action item."""
    BLOCKING = "BLOCKING"  # Must be resolved to proceed
    WARNING = "WARNING"    # Recommended but not required


class ActionItem(BaseModel):
    """
    Immutable action item for merchant to resolve.
    Once created, can only be marked as resolved.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: ActionCategory
    severity: ActionSeverity
    title: str                              # Short title: "Upload clearer KYC document"
    description: str                        # What went wrong
    suggestion: str                         # How to fix it
    field_to_update: Optional[str] = None   # Hint: which field might need update
    current_value: Optional[str] = None     # Current value that failed
    required_format: Optional[str] = None   # Expected format/constraints
    sample_content: Optional[str] = None    # For policies: draft template text
    created_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


# Pydantic Data Models (for validation)


class BusinessDetails(BaseModel):
    pan: str
    entity_type: str
    category: str
    gstin: str
    monthly_volume: str
    website_url: Optional[str] = None


class BankDetails(BaseModel):
    account_number: str
    ifsc: str
    account_holder_name: str


class SignatoryDetails(BaseModel):
    name: str
    email: str
    aadhaar: str


class MerchantApplication(BaseModel):
    merchant_id: Optional[str] = None  # UUID - generated if not provided
    business_details: BusinessDetails
    bank_details: BankDetails
    signatory_details: SignatoryDetails
    documents_path: Optional[str] = None  # Path to documents for OCR


class PartialBusinessDetails(BaseModel):
    """Partial business details for updates."""
    pan: Optional[str] = None
    entity_type: Optional[str] = None
    category: Optional[str] = None
    gstin: Optional[str] = None
    monthly_volume: Optional[str] = None
    website_url: Optional[str] = None


class PartialBankDetails(BaseModel):
    """Partial bank details for updates."""
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    account_holder_name: Optional[str] = None


class PartialSignatoryDetails(BaseModel):
    """Partial signatory details for updates."""
    name: Optional[str] = None
    email: Optional[str] = None
    aadhaar: Optional[str] = None


class ResumePayload(BaseModel):
    """
    Simple payload for resuming onboarding.
    
    Just send any updated fields in the same structure as MerchantApplication.
    Fields not provided are kept from existing state.
    
    Example - just re-verify (no data change):
        {}
    
    Example - update document:
        {"documents_path": "/uploads/new_doc.pdf"}
    
    Example - update website URL:
        {"business_details": {"website_url": "https://new-site.com"}}
    """
    # Partial application data - same structure as MerchantApplication
    business_details: Optional[PartialBusinessDetails] = None
    bank_details: Optional[PartialBankDetails] = None
    signatory_details: Optional[PartialSignatoryDetails] = None
    documents_path: Optional[str] = None
    
    # Optional context
    user_message: Optional[str] = None


# --- Graph State (AgentState) ---


class IdentityState(TypedDict):
    """Holds core identity and application data."""

    application_data: Dict[str, Any]
    merchant_id: Optional[str]


class WorkflowState(TypedDict):
    """Tracks the execution flow and status of the agent."""

    stage: Literal["INPUT", "DOCS", "BANK", "COMPLIANCE", "FINAL"]
    status: Literal["IN_PROGRESS", "NEEDS_REVIEW", "COMPLETED", "REJECTED"]
    next_step: Optional[str]
    retry_count: int
    error_message: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]


class ValidationState(TypedDict):
    """Flags for core validation logic gates."""

    is_auth_valid: bool
    is_bank_verified: bool
    is_doc_verified: bool
    is_website_compliant: bool


class ConsultantState(TypedDict):
    """Data related to risk assessment and consultant feedback."""

    risk_score: float  # 0.0 to 1.0 (1.0 = High Risk)
    verification_notes: List[str]
    compliance_issues: List[str]
    missing_artifacts: List[str]
    consultant_plan: List[str]
    action_items: List[Dict[str, Any]]  # List of ActionItem dicts (immutable, append-only)


class AgentState(IdentityState, WorkflowState, ValidationState, ConsultantState):
    """
    Unified state for the Graph, composed of specialized sub-states.
    Follows Interface Segregation by allowing modules to depend on
    sub-interfaces if needed (though TypedDict structure is flat).
    """

    pass
