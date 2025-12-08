from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

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
    api_key: Optional[str] = None  # Simulating auth
    business_details: BusinessDetails
    bank_details: BankDetails
    signatory_details: SignatoryDetails
    documents_path: Optional[str] = None  # Path to documents for OCR


class ResumePayload(BaseModel):
    updated_data: Optional[Dict[str, Any]] = None
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


class AgentState(IdentityState, WorkflowState, ValidationState, ConsultantState):
    """
    Unified state for the Graph, composed of specialized sub-states.
    Follows Interface Segregation by allowing modules to depend on
    sub-interfaces if needed (though TypedDict structure is flat).
    """

    pass
