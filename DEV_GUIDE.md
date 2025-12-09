# Project Velocity - Developer Guide

## Table of Contents
1. [Starting the Server](#1-starting-the-server)
2. [API Usage](#2-api-usage-onboarding-flow)
3. [Architecture Overview](#3-architecture-overview)
4. [Node System](#4-node-system)
5. [Tool Registry](#5-tool-registry)
6. [Creating New Nodes](#6-creating-new-nodes)
7. [Adding New Tools](#7-adding-new-tools)
8. [Simulation & Testing](#8-simulation--testing)
9. [Database Inspection](#9-database-inspection)

---

## 1. Starting the Server

```bash
# Option A: Direct Python Execution
./venv/bin/python3 -m app.main

# Option B: Uvicorn (Development Mode)
./venv/bin/uvicorn app.main:app --reload
```
*Port runs on `8000` by default.*

---

## 2. API Usage (Onboarding Flow)

### Step 1: Start Onboarding
```bash
curl -X POST http://localhost:8000/onboard \
-H "Content-Type: application/json" \
-d '{
    "merchant_id": "MERCH123",
    "business_details": {
        "pan": "ABCDE1234F",
        "entity_type": "Private Limited",
        "category": "E-commerce",
        "gstin": "22AAAAA0000A1Z5",
        "monthly_volume": "100000",
        "website_url": "https://example.com"
    },
    "bank_details": {
        "account_number": "1234567890",
        "ifsc": "HDFC0001234",
        "account_holder_name": "Test Merchant"
    },
    "signatory_details": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "aadhaar": "999999999999"
    }
}'
```
**Response:** Returns a `thread_id` (UUID).

### Step 2: Check Status
```bash
curl http://localhost:8000/onboard/<THREAD_ID>/status
```

### Step 3: Resume (if NEEDS_REVIEW)
```bash
curl -X POST http://localhost:8000/onboard/<THREAD_ID>/resume \
-H "Content-Type: application/json" \
-d '{
        "business_details": {
        "website_url": "https://new-site.com"
        }
}'
```

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI (main.py)                        │
│  /onboard, /status, /resume, /action-items, /debug/*            │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow (graph.py)                │
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │  Input   │───▶│   Doc    │───▶│   Bank   │───▶│   Web    │ │
│   │  Parser  │    │  Intel   │    │ Verifier │    │Compliance│ │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘ │
│        │               │               │               │        │
│        │               │               │               │        │
│        ▼               ▼               ▼               ▼        │
│   ┌────────────────────────────────────────────────────────┐   │
│   │               Consultant (on failure)                   │   │
│   └─────────────────────────┬──────────────────────────────┘   │
│                             │                                   │
│                             ▼                                   │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │                    Finalizer (on success)                 │ │
│   └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Contracts** | `app/core/contracts.py` | Input/Output schemas for nodes |
| **BaseNode** | `app/core/base_node.py` | Abstract base class for nodes |
| **Tool Registry** | `app/core/tool_registry.py` | Central registry for all tools |
| **Tools** | `app/core/tools/` | Tool implementations |
| **Nodes (v2)** | `app/core/nodes/` | New architecture nodes |
| **Nodes (v1)** | `app/nodes/` | Legacy nodes (still functional) |

---

## 4. Node System

### Node Contract

Every node follows this contract:

```
INPUT (NodeInput):
├── application_data: Dict      # Merchant application
├── merchant_id: str            # Unique ID
├── stage: str                  # Current workflow stage
├── is_auth_valid: bool         # Previous validation flags
├── is_doc_verified: bool
├── is_bank_verified: bool
├── is_website_compliant: bool
├── existing_action_items: List # From previous nodes
└── existing_notes: List

OUTPUT (NodeOutput):
├── state_updates: Dict         # Fields to update in state
├── action_items: List          # Issues found
├── verification_notes: List    # Audit trail
├── next_node: str (optional)   # Routing hint
└── tool_results: List          # Tool execution log
```

### Node Configuration

Each node has a config (`NodeConfig`):

```python
NodeConfig(
    node_name="input_parser_node",      # Unique identifier
    display_name="Input Parser",         # Human-readable name
    description="...",                   # What the node does
    stage="INPUT",                       # Workflow stage
    available_tools=["validate_pan"],    # Tools this node can use
    simulation_key="input",              # For simulation flags
    llm=LLMConfig(enabled=False),        # LLM settings
)
```

### Available Nodes

| Node | Stage | Tools | Purpose |
|------|-------|-------|---------|
| `InputParserNode` | INPUT | validate_pan, validate_gstin | Validate merchant data |
| `DocIntelligenceNode` | DOCS | extract_document_text, validate_document_content | OCR & document validation |
| `BankVerifierNode` | BANK | validate_ifsc, penny_drop_verify | Bank account verification |
| `WebComplianceNode` | COMPLIANCE | check_ssl, fetch_webpage_sync, check_page_policies | Website compliance |
| `ConsultantNode` | FINAL | (LLM) | Consolidate issues, generate recommendations |
| `FinalizerNode` | FINAL | - | Complete onboarding |

---

## 5. Tool Registry

### Concept

Tools are atomic operations that nodes can call. The registry provides:
- Centralized tool management
- Mock/real implementation switching
- Schema definitions for LLM function calling

### Tool Categories

| Category | Tools | Purpose |
|----------|-------|---------|
| **validation** | validate_pan, validate_gstin, validate_ifsc, validate_aadhaar | Format validation |
| **document** | extract_document_text, validate_document_content, extract_pan_from_document | OCR & extraction |
| **bank** | penny_drop_verify, lookup_ifsc, validate_account_number | Bank verification |
| **web** | check_ssl, fetch_webpage_sync, check_page_policies, take_screenshot | Website checks |

### Using Tools in Nodes

```python
class MyNode(BaseNode):
    def process(self, input: NodeInput) -> NodeOutput:
        # Call a tool
        result = self.call_tool("validate_pan", {"pan": "ABCDE1234F"})
        
        if result.success:
            data = result.data  # Tool output
        else:
            error = result.error  # Error message
```

---

## 6. Creating New Nodes

### Step 1: Create Node Class

```python
# app/core/nodes/my_node.py

from app.core.base_node import BaseNode
from app.core.contracts import NodeInput, NodeOutput, NodeConfig, LLMConfig
from app.schema import ActionCategory, ActionSeverity


class MyNode(BaseNode):
    """
    Docstring explaining what this node does.
    
    INPUT:
      - application_data.my_field
    
    OUTPUT:
      - is_my_check_passed: bool
    
    TOOLS:
      - my_tool
    """
    
    @classmethod
    def get_config(cls) -> NodeConfig:
        return NodeConfig(
            node_name="my_node",
            display_name="My Node",
            description="Does something important",
            stage="CUSTOM",
            available_tools=["my_tool"],
            simulation_key="my",
            llm=LLMConfig(enabled=False),
        )
    
    def process(self, input: NodeInput) -> NodeOutput:
        self._log("Processing...")
        
        # Force success mode
        if self.should_skip_checks():
            return NodeOutput(
                state_updates={"is_my_check_passed": True},
                verification_notes=["Check passed (simulated)"],
            )
        
        # Simulate failures
        if self.should_simulate_failure("some_error"):
            return NodeOutput(
                state_updates={"is_my_check_passed": False},
                action_items=[self.create_action_item(...)],
            )
        
        # Real logic
        result = self.call_tool("my_tool", {"param": "value"})
        
        if result.success:
            return NodeOutput(
                state_updates={"is_my_check_passed": True},
                verification_notes=["Check passed"],
            )
        else:
            return NodeOutput(
                state_updates={"is_my_check_passed": False},
                action_items=[...],
            )


# Create callable for LangGraph
my_node = MyNode()
```

### Step 2: Add to Graph

```python
# In graph_v2.py

from app.core.nodes.my_node import MyNode

workflow.add_node("my_node", MyNode())
workflow.add_conditional_edges("previous_node", check_my)
```

### Step 3: Add Simulation Flags

```bash
# .env
SIMULATE_MY_SOME_ERROR_FAILURE=false
SIMULATE_FORCE_SUCCESS_MY=false
```

---

## 7. Adding New Tools

### Step 1: Create Tool Function

```python
# app/core/tools/my_tools.py

from app.core.tool_registry import tool_registry


@tool_registry.register(
    name="my_tool",
    description="Does something useful",
    input_schema={
        "param": {"type": "string", "description": "Input parameter"}
    },
    output_schema={
        "result": {"type": "boolean"},
        "data": {"type": "object"}
    },
    category="custom",
    requires_network=False,
    mock_output={"result": True, "data": {"mock": True}}
)
def my_tool(param: str) -> dict:
    """
    Real implementation of the tool.
    """
    # Your logic here
    return {"result": True, "data": {"processed": param}}


# Optional: Register mock implementation
@tool_registry.register_mock("my_tool")
def mock_my_tool(param: str) -> dict:
    return {"result": True, "data": {"mock": True, "param": param}}
```

### Step 2: Import in __init__.py

```python
# app/core/tools/__init__.py

from app.core.tools.my_tools import *
```

### Step 3: Add to Node's available_tools

```python
NodeConfig(
    available_tools=["my_tool", ...],
)
```

---

## 8. Simulation & Testing

### Environment Flags

```bash
# Force all checks to pass (mock success)
SIMULATE_FORCE_SUCCESS_ALL=true

# Force specific checks to pass
SIMULATE_FORCE_SUCCESS_INPUT=true
SIMULATE_FORCE_SUCCESS_DOC=true
SIMULATE_FORCE_SUCCESS_BANK=true
SIMULATE_FORCE_SUCCESS_WEB=true

# Simulate specific failures
SIMULATE_INPUT_INVALID_PAN_FAILURE=true
SIMULATE_DOC_BLURRY_FAILURE=true
SIMULATE_BANK_NAME_MISMATCH_FAILURE=true
SIMULATE_WEB_NO_SSL_FAILURE=true
```

### Runtime Configuration

```bash
# Get current simulation state
curl http://localhost:8000/debug/simulate

# Update flags at runtime (no restart needed)
curl -X POST http://localhost:8000/debug/simulate \
-H "Content-Type: application/json" \
-d '{"force_success_all": true}'

# Reset to defaults
curl -X DELETE http://localhost:8000/debug/simulate
```

### Tool Mock Mode

```python
from app.core.tool_registry import tool_registry

# Enable mock mode globally
tool_registry.set_mock_mode(True)

# Or per-call
result = tool_registry.call("my_tool", {"param": "value"}, use_mock=True)
```

---

## 9. Database Inspection

### SQLite Files

| File | Purpose |
|------|---------|
| `db/checkpoints.sqlite` | LangGraph state checkpoints |
| `db/jobs.sqlite` | Job metadata (status, timestamps) |

### Quick Inspection

```bash
# View recent jobs
sqlite3 db/jobs.sqlite "SELECT thread_id, status, stage FROM jobs ORDER BY created_at DESC LIMIT 10;"

# View checkpoints
sqlite3 db/checkpoints.sqlite "SELECT thread_id FROM checkpoints GROUP BY thread_id;"
```

### Programmatic Access

```python
from app.utils.job_store import job_store

# Get job info
job = await job_store.get_job("thread-id-here")
print(job)
```

---

## Quick Reference

### Useful Commands

```bash
# Start server
make run

# Run tests
make test

# Generate graph visualization
python tests/visualize_graph.py

# Check lint
make lint
```

### Key Files

```
app/
├── main.py              # FastAPI endpoints
├── graph.py             # LangGraph workflow (v1)
├── graph_v2.py          # LangGraph workflow (v2 - new architecture)
├── schema.py            # Data models
├── core/
│   ├── contracts.py     # Node input/output contracts
│   ├── base_node.py     # BaseNode class
│   ├── tool_registry.py # Tool registry
│   ├── tools/           # Tool implementations
│   └── nodes/           # Node implementations (v2)
├── nodes/               # Node implementations (v1)
└── utils/               # Utilities (LLM, simulation, etc.)
```
