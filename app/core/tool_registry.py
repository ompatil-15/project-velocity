"""
Tool Registry - Central registry for all tools available to nodes.

Tools are atomic operations that nodes can call. Each tool has:
- Clear input/output schema
- Mock implementation for testing
- Real implementation for production

This registry pattern allows:
1. Easy testing with mocks
2. LLM function calling integration
3. Centralized documentation
4. Runtime tool discovery
"""

from typing import Any, Callable, Dict, List, Optional, Awaitable, Union
from app.core.contracts import ToolDefinition, ToolResult
import time


# Type for tool implementations
ToolImplementation = Callable[..., Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]


class ToolRegistry:
    """
    Central registry for all tools.
    
    Usage:
        # Register a tool
        @tool_registry.register(
            name="verify_pan",
            description="Verify PAN number format and existence",
            input_schema={"pan": {"type": "string"}},
            output_schema={"valid": {"type": "boolean"}, "name": {"type": "string"}}
        )
        def verify_pan(pan: str) -> Dict[str, Any]:
            # implementation
            return {"valid": True, "name": "JOHN DOE"}
        
        # Call a tool
        result = tool_registry.call("verify_pan", {"pan": "ABCDE1234F"})
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._implementations: Dict[str, ToolImplementation] = {}
        self._mock_implementations: Dict[str, ToolImplementation] = {}
        self._use_mocks: bool = False
    
    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any] = None,
        output_schema: Dict[str, Any] = None,
        category: str = "general",
        is_async: bool = False,
        requires_network: bool = False,
        is_idempotent: bool = True,
        mock_output: Dict[str, Any] = None,
    ) -> Callable[[ToolImplementation], ToolImplementation]:
        """
        Decorator to register a tool.
        
        Example:
            @tool_registry.register(
                name="fetch_webpage",
                description="Fetch HTML content from a URL",
                input_schema={"url": {"type": "string", "format": "uri"}},
                requires_network=True
            )
            def fetch_webpage(url: str) -> Dict[str, Any]:
                ...
        """
        def decorator(func: ToolImplementation) -> ToolImplementation:
            definition = ToolDefinition(
                name=name,
                description=description,
                input_schema=input_schema or {},
                output_schema=output_schema or {},
                category=category,
                is_async=is_async,
                requires_network=requires_network,
                is_idempotent=is_idempotent,
                mock_output=mock_output,
            )
            self._tools[name] = definition
            self._implementations[name] = func
            return func
        return decorator
    
    def register_mock(self, name: str) -> Callable[[ToolImplementation], ToolImplementation]:
        """
        Decorator to register a mock implementation for a tool.
        
        Example:
            @tool_registry.register_mock("verify_pan")
            def mock_verify_pan(pan: str) -> Dict[str, Any]:
                return {"valid": True, "name": "MOCK NAME"}
        """
        def decorator(func: ToolImplementation) -> ToolImplementation:
            self._mock_implementations[name] = func
            return func
        return decorator
    
    def set_mock_mode(self, enabled: bool):
        """Enable or disable mock mode globally."""
        self._use_mocks = enabled
    
    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self._tools.get(name)
    
    def get_all_definitions(self) -> List[ToolDefinition]:
        """Get all registered tool definitions."""
        return list(self._tools.values())
    
    def get_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """Get all tools in a category."""
        return [t for t in self._tools.values() if t.category == category]
    
    def call(
        self,
        name: str,
        inputs: Dict[str, Any],
        use_mock: Optional[bool] = None
    ) -> ToolResult:
        """
        Call a tool by name.
        
        Args:
            name: Tool name
            inputs: Tool inputs as dict
            use_mock: Override global mock setting
        
        Returns:
            ToolResult with success/failure and data
        """
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not found in registry"
            )
        
        # Determine if we should use mock
        should_mock = use_mock if use_mock is not None else self._use_mocks
        
        start_time = time.time()
        
        try:
            if should_mock:
                # Use mock implementation or static mock output
                if name in self._mock_implementations:
                    data = self._mock_implementations[name](**inputs)
                elif self._tools[name].mock_output:
                    data = self._tools[name].mock_output
                else:
                    return ToolResult(
                        tool_name=name,
                        success=False,
                        error=f"No mock implementation for '{name}'"
                    )
                was_mocked = True
            else:
                # Use real implementation
                if name not in self._implementations:
                    return ToolResult(
                        tool_name=name,
                        success=False,
                        error=f"No implementation for '{name}'"
                    )
                data = self._implementations[name](**inputs)
                was_mocked = False
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ToolResult(
                tool_name=name,
                success=True,
                data=data,
                execution_time_ms=execution_time,
                was_mocked=was_mocked
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                was_mocked=should_mock
            )
    
    async def call_async(
        self,
        name: str,
        inputs: Dict[str, Any],
        use_mock: Optional[bool] = None
    ) -> ToolResult:
        """
        Call an async tool by name.
        """
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Tool '{name}' not found in registry"
            )
        
        should_mock = use_mock if use_mock is not None else self._use_mocks
        start_time = time.time()
        
        try:
            if should_mock:
                if name in self._mock_implementations:
                    result = self._mock_implementations[name](**inputs)
                    # Handle both sync and async mocks
                    if hasattr(result, '__await__'):
                        data = await result
                    else:
                        data = result
                elif self._tools[name].mock_output:
                    data = self._tools[name].mock_output
                else:
                    return ToolResult(
                        tool_name=name,
                        success=False,
                        error=f"No mock implementation for '{name}'"
                    )
                was_mocked = True
            else:
                if name not in self._implementations:
                    return ToolResult(
                        tool_name=name,
                        success=False,
                        error=f"No implementation for '{name}'"
                    )
                result = self._implementations[name](**inputs)
                if hasattr(result, '__await__'):
                    data = await result
                else:
                    data = result
                was_mocked = False
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return ToolResult(
                tool_name=name,
                success=True,
                data=data,
                execution_time_ms=execution_time,
                was_mocked=was_mocked
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name=name,
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                was_mocked=should_mock
            )
    
    def to_openai_functions(self) -> List[Dict[str, Any]]:
        """
        Export tools as OpenAI function definitions.
        
        Useful for LLM function calling.
        """
        functions = []
        for tool in self._tools.values():
            functions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": tool.input_schema,
                    "required": list(tool.input_schema.keys()),
                }
            })
        return functions
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
    
    def __len__(self) -> int:
        return len(self._tools)


# Global registry instance
tool_registry = ToolRegistry()

