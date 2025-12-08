from typing import TypedDict, Annotated, List, Dict, Any, Optional
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


# --- Graph State (AgentState) ---


class AgentState(TypedDict):
    # original application data
    application_data: Dict[str, Any]

    # Validation flags
    is_auth_valid: bool
    is_bank_verified: bool
    is_doc_verified: bool
    is_website_compliant: bool

    # Details from verification
    verification_notes: List[str]
    compliance_issues: List[str]  # Add this field as it was used in nodes
    compliance_report: Dict[str, Any]

    # Internal agent control
    messages: Annotated[List[BaseMessage], add_messages]
    error_message: Optional[str]
    next_step: Optional[str]
    retry_count: int
