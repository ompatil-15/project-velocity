# Project Velocity - Developer Guide

## 1. Starting the Server

The server is a FastAPI application. Ensure your virtual environment is active or use the venv python directly.

```bash
# Option A: Direct Python Execution
./venv/bin/python3 -m app.main

# Option B: Uvicorn (Development Mode)
./venv/bin/uvicorn app.main:app --reload
```
*Port runs on `8000` by default.*

## 2. API Usage (Onboarding Flow)

### Step 1: Start Onboarding
Submit the merchant application form.
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
        "website_url": "http://example.com"
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
**Response:** Returns a `thread_id`. Save this!

### Step 2: Check Status
Poll the status of the thread.
```bash
# Replace <THREAD_ID> with the UUID from Step 1
curl http://localhost:8000/onboard/<THREAD_ID>/status
```

### Step 3: Resume (Interactive Mode)
If the status is `NEEDS_REVIEW`, the payload will contain `consultant_plan` and `compliance_issues`. Fix the data and resume.
```bash
curl -X POST http://localhost:8000/onboard/<THREAD_ID>/resume \
-H "Content-Type: application/json" \
-d '{
    "updated_data": {
        "business_details": {
            "entity_type": "Public Limited"
        }
    },
    "user_message": "Updated entity type as requested."
}'
```

## 3. Database Inspection
The agent uses **SQLite** for persistence. The database file is `checkpoints.sqlite` in the root directory.

### Quick Inspection
To see the raw checkpoints:
```bash
sqlite3 checkpoints.sqlite "SELECT thread_id, checkpoint FROM checkpoints ORDER BY thread_id, thread_ts DESC LIMIT 5;"
```

### Decode State
The state blob is binary. To debug state programmatically:
```python
import sqlite3
import pickle # Note: LangGraph uses specialized serdes, but raw inspection is limited.

# Best way to inspect is via the API or python shell:
from schema import AgentState
from agent_graph import agent_app
# Use verify_workflow.py as a reference implementation.
```
