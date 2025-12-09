"""
Base Node - Abstract base class for all workflow nodes.

Each node in the workflow should:
1. Have clear input requirements
2. Produce standardized output
3. Be able to call tools (external APIs, LLM, etc.)
4. Support simulation/mocking for testing

This base class provides:
- Tool calling infrastructure
- LLM calling infrastructure  
- Action item creation helpers
- Simulation mode support
- Logging and audit trail
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from app.core.contracts import (
    NodeInput, 
    NodeOutput, 
    NodeConfig, 
    ToolResult,
    LLMConfig,
)
from app.core.tool_registry import tool_registry
from app.schema import ActionItem, ActionCategory, ActionSeverity, AgentState
from app.utils.simulation import sim
import os


class BaseNode(ABC):
    """
    Abstract base class for workflow nodes.
    
    Subclass this to create a new node:
    
        class MyVerifierNode(BaseNode):
            @classmethod
            def get_config(cls) -> NodeConfig:
                return NodeConfig(
                    node_name="my_verifier",
                    display_name="My Verifier",
                    stage="DOCS",
                    available_tools=["extract_text", "verify_pan"],
                    simulation_key="doc"
                )
            
            def process(self, input: NodeInput) -> NodeOutput:
                # Your logic here
                result = self.call_tool("verify_pan", {"pan": input.application_data["pan"]})
                ...
    """
    
    def __init__(self, config: Optional[NodeConfig] = None):
        """Initialize node with optional config override."""
        self._config = config or self.get_config()
        self._tool_results: List[ToolResult] = []
        self._verification_notes: List[str] = []
    
    @classmethod
    @abstractmethod
    def get_config(cls) -> NodeConfig:
        """
        Return the default configuration for this node.
        
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    def process(self, input: NodeInput) -> NodeOutput:
        """
        Main processing logic for the node.
        
        Must be implemented by subclasses.
        
        Args:
            input: Standardized node input
            
        Returns:
            Standardized node output
        """
        pass
    
    @property
    def config(self) -> NodeConfig:
        """Get node configuration."""
        return self._config
    
    @property
    def name(self) -> str:
        """Get node name."""
        return self._config.node_name
    
    # =========================================================================
    # Tool Calling
    # =========================================================================
    
    def call_tool(
        self, 
        tool_name: str, 
        inputs: Dict[str, Any],
        use_mock: Optional[bool] = None
    ) -> ToolResult:
        """
        Call a tool from the registry.
        
        Args:
            tool_name: Name of the tool to call
            inputs: Tool inputs
            use_mock: Override simulation setting
            
        Returns:
            ToolResult with success/failure and data
        """
        # Check if tool is allowed for this node
        if tool_name not in self._config.available_tools:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not in available_tools for {self.name}"
            )
            self._tool_results.append(result)
            return result
        
        # Determine mock mode
        if use_mock is None:
            use_mock = sim.should_skip(self._config.simulation_key)
        
        result = tool_registry.call(tool_name, inputs, use_mock=use_mock)
        self._tool_results.append(result)
        
        return result
    
    async def call_tool_async(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        use_mock: Optional[bool] = None
    ) -> ToolResult:
        """Call an async tool."""
        if tool_name not in self._config.available_tools:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not in available_tools for {self.name}"
            )
            self._tool_results.append(result)
            return result
        
        if use_mock is None:
            use_mock = sim.should_skip(self._config.simulation_key)
        
        result = await tool_registry.call_async(tool_name, inputs, use_mock=use_mock)
        self._tool_results.append(result)
        
        return result
    
    # =========================================================================
    # LLM Calling
    # =========================================================================
    
    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Call the configured LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Override system prompt
            **kwargs: Additional LLM parameters
            
        Returns:
            LLM response text or None if disabled/failed
        """
        if not self._config.llm.enabled:
            self._add_note("LLM call skipped (disabled in config)")
            return None
        
        try:
            from app.utils.llm_factory import get_llm
            from langchain_core.messages import HumanMessage, SystemMessage
            
            llm = get_llm()
            messages = []
            
            # Add system prompt if provided
            sys_prompt = system_prompt or self._config.llm.system_prompt
            if sys_prompt:
                messages.append(SystemMessage(content=sys_prompt))
            
            messages.append(HumanMessage(content=prompt))
            
            response = llm.invoke(messages)
            self._add_note(f"LLM call successful ({len(response.content)} chars)")
            
            return response.content
            
        except Exception as e:
            self._add_note(f"LLM call failed: {str(e)}")
            return None
    
    # =========================================================================
    # Action Item Helpers
    # =========================================================================
    
    def create_action_item(
        self,
        category: ActionCategory,
        severity: ActionSeverity,
        title: str,
        description: str,
        suggestion: str,
        field_to_update: Optional[str] = None,
        current_value: Optional[str] = None,
        required_format: Optional[str] = None,
        sample_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a standardized action item.
        
        Returns dict representation for state updates.
        """
        item = ActionItem(
            category=category,
            severity=severity,
            title=title,
            description=description,
            suggestion=suggestion,
            field_to_update=field_to_update,
            current_value=current_value,
            required_format=required_format,
            sample_content=sample_content,
        )
        return item.model_dump()
    
    # =========================================================================
    # Simulation Helpers
    # =========================================================================
    
    def should_skip_checks(self) -> bool:
        """Check if this node should skip real checks (force success)."""
        return sim.should_skip(self._config.simulation_key)
    
    def should_simulate_failure(self, failure_type: str) -> bool:
        """Check if a specific failure should be simulated."""
        return sim.should_fail(f"{self._config.simulation_key}_{failure_type}")
    
    # =========================================================================
    # Note/Logging Helpers
    # =========================================================================
    
    def _add_note(self, note: str):
        """Add a verification note."""
        self._verification_notes.append(note)
    
    def _log(self, message: str):
        """Log a message (with node name prefix)."""
        from app.utils.logger import get_logger
        logger = get_logger(f"node.{self._config.node_name}")
        logger.info(message)
    
    # =========================================================================
    # State Conversion
    # =========================================================================
    
    @classmethod
    def from_state(cls, state: AgentState) -> NodeInput:
        """
        Convert AgentState to NodeInput.
        
        Helper for existing LangGraph integration.
        """
        return NodeInput(
            application_data=state.get("application_data", {}),
            merchant_id=state.get("merchant_id"),
            stage=state.get("stage", "INPUT"),
            is_auth_valid=state.get("is_auth_valid", False),
            is_doc_verified=state.get("is_doc_verified", False),
            is_bank_verified=state.get("is_bank_verified", False),
            is_website_compliant=state.get("is_website_compliant", False),
            existing_action_items=state.get("action_items", []),
            existing_notes=state.get("verification_notes", []),
        )
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        Make node callable for LangGraph.
        
        This bridges the new architecture with existing LangGraph setup.
        """
        # Reset per-invocation state
        self._tool_results = []
        self._verification_notes = []
        
        # Convert state to input
        input_data = self.from_state(state)
        
        self._log("Processing...")
        
        # Run the node logic
        output = self.process(input_data)
        
        # Add tool results and notes to output
        output.tool_results = self._tool_results
        output.verification_notes = self._verification_notes + output.verification_notes
        
        self._log(f"Complete. Actions: {len(output.action_items)}, Notes: {len(output.verification_notes)}")
        
        # Convert to state dict for LangGraph
        return output.to_state_dict()


def create_node_function(node_class: Type[BaseNode]):
    """
    Create a LangGraph-compatible function from a BaseNode class.
    
    Usage:
        input_parser_node = create_node_function(InputParserNode)
    """
    instance = node_class()
    return instance.__call__

