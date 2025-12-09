"""
Core contracts for the node architecture.

This module defines the standard interfaces that all nodes must follow.
Clear inputs and outputs enable:
1. Easy testing and mocking
2. LLM/Tool calling in the middle
3. Type safety and validation
4. Documentation auto-generation
"""

from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


# =============================================================================
# Tool Contracts
# =============================================================================

class ToolDefinition(BaseModel):
    """
    Definition of a tool that can be called by nodes.
    
    Tools are the atomic operations that nodes can perform:
    - External API calls (bank verification, PAN validation)
    - Document processing (OCR, extraction)
    - Web operations (fetch page, check SSL)
    - LLM operations (generate, classify, extract)
    """
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="What the tool does")
    
    # Input/Output schemas (JSON Schema format for LLM compatibility)
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool input"
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict, 
        description="JSON Schema for tool output"
    )
    
    # Metadata
    category: str = Field(default="general", description="Tool category")
    is_async: bool = Field(default=False, description="Whether tool is async")
    requires_network: bool = Field(default=False, description="Needs network access")
    is_idempotent: bool = Field(default=True, description="Safe to retry")
    
    # Simulation support
    mock_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Mock output for simulation mode"
    )


class ToolResult(BaseModel):
    """
    Result from a tool execution.
    
    Standardized result format enables:
    - Consistent error handling
    - LLM interpretation of results
    - Audit logging
    """
    tool_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    was_mocked: bool = False


# =============================================================================
# Node Configuration
# =============================================================================

class LLMConfig(BaseModel):
    """Configuration for LLM usage within a node."""
    enabled: bool = False
    provider: str = "gemini"  # gemini, openai, etc.
    model: Optional[str] = None  # Specific model override
    temperature: float = 0.0
    max_tokens: int = 1024
    
    # Prompt templates (can be overridden)
    system_prompt: Optional[str] = None
    

class NodeConfig(BaseModel):
    """
    Configuration for a node.
    
    Each node can be configured with:
    - Which tools it can use
    - LLM settings
    - Simulation behavior
    - Retry policies
    """
    node_name: str = Field(..., description="Unique node identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(default="", description="What this node does")
    
    # Stage in the workflow
    stage: str = Field(default="UNKNOWN", description="INPUT|DOCS|BANK|COMPLIANCE|FINAL")
    
    # Tools this node can use
    available_tools: List[str] = Field(
        default_factory=list,
        description="Tool names this node can call"
    )
    
    # LLM configuration
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    # Simulation
    simulation_key: str = Field(
        default="",
        description="Key for simulation flags (e.g., 'doc', 'bank')"
    )
    
    # Retry behavior
    max_retries: int = 3
    retry_delay_seconds: float = 1.0


# =============================================================================
# Node Input/Output Contracts
# =============================================================================

class NodeInput(BaseModel):
    """
    Standardized input for all nodes.
    
    Each node receives:
    - The current state (read-only view)
    - Node-specific configuration
    - Optional context from previous nodes
    """
    # Core data
    application_data: Dict[str, Any] = Field(
        ..., description="The merchant application data"
    )
    merchant_id: Optional[str] = Field(
        None, description="Merchant identifier"
    )
    
    # Workflow context
    stage: str = Field(default="INPUT")
    previous_node: Optional[str] = None
    retry_count: int = 0
    
    # Validation flags from previous nodes
    is_auth_valid: bool = False
    is_doc_verified: bool = False
    is_bank_verified: bool = False
    is_website_compliant: bool = False
    
    # Previous findings (for consultant node)
    existing_action_items: List[Dict[str, Any]] = Field(default_factory=list)
    existing_notes: List[str] = Field(default_factory=list)
    
    class Config:
        extra = "allow"  # Allow extra fields from AgentState


class NodeOutput(BaseModel):
    """
    Standardized output from all nodes.
    
    Every node must return:
    - State updates (what changed)
    - Action items (if any issues found)
    - Verification notes (audit trail)
    - Next step hint (optional routing)
    """
    # What state fields to update
    state_updates: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dict of state fields to update"
    )
    
    # Issues found (if any)
    action_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="New action items from this node"
    )
    
    # Audit trail
    verification_notes: List[str] = Field(
        default_factory=list,
        description="Notes about what was checked"
    )
    
    # Routing hint
    next_node: Optional[str] = Field(
        None,
        description="Suggested next node (for conditional routing)"
    )
    
    # Tool execution log
    tool_results: List[ToolResult] = Field(
        default_factory=list,
        description="Results from tools called"
    )
    
    def to_state_dict(self) -> Dict[str, Any]:
        """
        Convert output to dict for LangGraph state update.
        
        Merges state_updates with standard fields.
        """
        result = dict(self.state_updates)
        
        if self.action_items:
            result["action_items"] = self.action_items
            
        if self.verification_notes:
            result["verification_notes"] = self.verification_notes
            
        if self.next_node:
            result["next_step"] = self.next_node
            
        return result


# =============================================================================
# Type helpers for node functions
# =============================================================================

# Type for node function signature
NodeFunction = Callable[[NodeInput, NodeConfig], NodeOutput]

