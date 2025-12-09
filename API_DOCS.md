# Project Velocity API Documentation

> For frontend integration. Base URL: `http://localhost:8000`

---

## Quick Start Flow

```
1. POST /onboard        → Start onboarding, get thread_id
2. GET  /status         → Poll until COMPLETED or NEEDS_REVIEW
3. GET  /action-items   → If NEEDS_REVIEW, show issues to merchant
4. POST /upload         → If document needed, upload file
5. POST /resume         → Submit fixes, go back to step 2
```

---

## Core Endpoints

### 1. Start Onboarding

```
POST /onboard
```

**Request:**
```json
{
  "merchant_id": "optional-uuid",
  "business_details": {
    "pan": "ABCDE1234F",
    "entity_type": "Private Limited",
    "category": "E-commerce",
    "gstin": "29ABCDE1234F1Z5",
    "monthly_volume": "10-50 Lakhs",
    "website_url": "https://example.com"
  },
  "bank_details": {
    "account_number": "1234567890",
    "ifsc": "HDFC0001234",
    "account_holder_name": "Example Pvt Ltd"
  },
  "signatory_details": {
    "name": "John Doe",
    "email": "john@example.com",
    "aadhaar": "123456789012"
  },
  "documents_path": "/uploads/kyc.pdf"
}
```

**Response:** `202 Accepted`
```json
{
  "status": "ACCEPTED",
  "thread_id": "uuid-string",
  "merchant_id": "uuid-string"
}
```

---

### 2. Check Status

```
GET /onboard/{thread_id}/status
```

**Response:**
```json
{
  "status": "PROCESSING | NEEDS_REVIEW | COMPLETED | FAILED",
  "stage": "INPUT | DOCS | BANK | COMPLIANCE | FINAL",
  "risk_score": 0.3,
  "error_message": null,
  "action_items_summary": {
    "blocking_count": 2,
    "warning_count": 1,
    "total_pending": 3
  }
}
```

**Status Values:**
| Status | Meaning | Next Action |
|--------|---------|-------------|
| `PROCESSING` | Workflow running | Keep polling |
| `NEEDS_REVIEW` | Merchant action needed | Show action items |
| `COMPLETED` | Success | Done |
| `FAILED` | Error | Show error |

---

### 3. Get Action Items

```
GET /onboard/{thread_id}/action-items?include_resolved=false
```

**Response:**
```json
{
  "thread_id": "uuid",
  "action_items": [
    {
      "id": "abc123",
      "category": "DOCUMENT | BANK | WEBSITE | COMPLIANCE | DATA",
      "severity": "BLOCKING | WARNING",
      "title": "Upload clearer KYC document",
      "description": "Document is blurry",
      "suggestion": "Upload high-resolution scan",
      "field_to_update": "documents_path",
      "current_value": "/uploads/old.pdf",
      "required_format": "PDF, PNG, JPG. Min 300 DPI",
      "sample_content": null,
      "resolved": false
    }
  ],
  "summary": {
    "blocking_count": 1,
    "warning_count": 0,
    "total_pending": 1
  },
  "resume_hint": {
    "fields_with_issues": ["documents_path", "business_details.website_url"],
    "examples": {
      "just_reverify": {},
      "update_document": {"documents_path": "/uploads/new.pdf"},
      "update_website": {"business_details": {"website_url": "https://new.com"}}
    }
  }
}
```

---

### 4. Upload Document

```
POST /upload
Content-Type: multipart/form-data
```

**Request:**
```
file: <binary>
merchant_id: optional-string
```

**Response:**
```json
{
  "status": "success",
  "file_path": "/uploads/abc123_document.pdf",
  "filename": "document.pdf"
}
```

**Frontend Example (Next.js):**
```typescript
async function uploadDocument(file: File, merchantId?: string): Promise<string> {
  const formData = new FormData();
  formData.append('file', file);
  if (merchantId) formData.append('merchant_id', merchantId);
  
  const res = await fetch('http://localhost:8000/upload', { 
    method: 'POST', 
    body: formData 
  });
  const data = await res.json();
  return data.file_path;
}
```

---

### 5. Resume Onboarding

```
POST /onboard/{thread_id}/resume
```

**Request:** Partial application data (same structure as onboard, all fields optional)

**Response:** `202 Accepted`
```json
{
  "status": "ACCEPTED",
  "thread_id": "uuid",
  "data_updated": true,
  "fields_updated": ["documents_path", "business_details"]
}
```

#### Resume Examples (curl)

**Re-verify only (no data change):**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{}'
```

**Update document:**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{"documents_path": "/uploads/new_doc.pdf"}'
```

**Update website URL:**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{"business_details": {"website_url": "https://fixed-site.com"}}'
```

**Fix PAN number:**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{"business_details": {"pan": "ABCDE1234F"}}'
```

**Fix bank details:**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{"bank_details": {"account_holder_name": "CORRECT NAME PVT LTD", "ifsc": "HDFC0001234"}}'
```

**Multiple updates:**
```bash
curl -X POST http://localhost:8000/onboard/{thread_id}/resume \
-H "Content-Type: application/json" \
-d '{
  "business_details": {"pan": "ABCDE1234F", "website_url": "https://example.com"},
  "bank_details": {"account_holder_name": "EXAMPLE PVT LTD"},
  "user_message": "Fixed all issues"
}'
```

---

### 6. Get Full State (Debug/Demo)

```
GET /onboard/{thread_id}/state
```

Returns the complete internal state. Useful for:
- Debugging data updates after resume
- Demo purposes to show all merchant data
- Verifying verification flags

**Response:**
```json
{
  "application_data": {
    "business_details": {
      "pan": "ABCDE1234F",
      "entity_type": "Private Limited",
      "category": "E-commerce",
      "gstin": "27ABCDE1234F1Z5",
      "monthly_volume": "100000",
      "website_url": "https://example.com"
    },
    "bank_details": {
      "account_number": "1234567890",
      "ifsc": "HDFC0001234",
      "account_holder_name": "EXAMPLE PVT LTD"
    },
    "signatory_details": {
      "name": "Jane Doe",
      "email": "jane@example.com",
      "aadhaar": "999999999999"
    },
    "documents_path": "/uploads/doc_20251209.pdf"
  },
  "merchant_id": "550e8400-e29b-41d4-a716-446655440004",
  
  "verification_flags": {
    "is_auth_valid": true,
    "is_doc_verified": true,
    "is_bank_verified": true,
    "is_website_compliant": false
  },
  
  "workflow": {
    "status": "NEEDS_REVIEW",
    "stage": "COMPLIANCE",
    "next_step": null,
    "error_message": "Website compliance checks failed",
    "retry_count": 0
  },
  
  "assessment": {
    "risk_score": 0.7,
    "compliance_issues": ["Missing Privacy Policy page"],
    "missing_artifacts": []
  },
  
  "action_items": [...],
  "verification_notes": [...],
  "consultant_plan": [...],
  
  "_meta": {
    "next_nodes": ["input_parser_node"],
    "is_interrupted": true
  }
}
```

---

### 7. Download Agreement

```
GET /agreements/{merchant_id}
```

Download the merchant agreement PDF generated on successful onboarding.

**Response:** PDF file download

```bash
curl -O http://localhost:8000/agreements/550e8400-e29b-41d4-a716-446655440004
```

---

## TypeScript Types

```typescript
// Onboard Request
interface MerchantApplication {
  merchant_id?: string;
  business_details: {
    pan: string;
    entity_type: string;
    category: string;
    gstin: string;
    monthly_volume: string;
    website_url?: string;
  };
  bank_details: {
    account_number: string;
    ifsc: string;
    account_holder_name: string;
  };
  signatory_details: {
    name: string;
    email: string;
    aadhaar: string;
  };
  documents_path?: string;
}

// Resume Request (all fields optional)
interface ResumePayload {
  business_details?: Partial<MerchantApplication['business_details']>;
  bank_details?: Partial<MerchantApplication['bank_details']>;
  signatory_details?: Partial<MerchantApplication['signatory_details']>;
  documents_path?: string;
  user_message?: string;
}

// Action Item
interface ActionItem {
  id: string;
  category: 'DOCUMENT' | 'BANK' | 'WEBSITE' | 'COMPLIANCE' | 'DATA';
  severity: 'BLOCKING' | 'WARNING';
  title: string;
  description: string;
  suggestion: string;
  field_to_update?: string;
  current_value?: string;
  required_format?: string;
  sample_content?: string;
  resolved: boolean;
}

// Status Response
type JobStatus = 'QUEUED' | 'PROCESSING' | 'NEEDS_REVIEW' | 'COMPLETED' | 'FAILED';

// Full State Response
interface FullState {
  application_data: MerchantApplication;
  merchant_id: string;
  verification_flags: {
    is_auth_valid: boolean;
    is_doc_verified: boolean;
    is_bank_verified: boolean;
    is_website_compliant: boolean;
  };
  workflow: {
    status: JobStatus;
    stage: string;
    next_step?: string;
    error_message?: string;
    retry_count: number;
  };
  assessment: {
    risk_score: number;
    compliance_issues: string[];
    missing_artifacts: string[];
  };
  action_items: ActionItem[];
  verification_notes: string[];
  consultant_plan: string[];
}
```

---

## Polling Pattern

```typescript
async function pollStatus(threadId: string): Promise<StatusResponse> {
  const maxAttempts = 60;
  const interval = 2000; // 2 seconds
  
  for (let i = 0; i < maxAttempts; i++) {
    const res = await fetch(`http://localhost:8000/onboard/${threadId}/status`);
    const data = await res.json();
    
    if (data.status !== 'PROCESSING' && data.status !== 'QUEUED') {
      return data;
    }
    
    await new Promise(r => setTimeout(r, interval));
  }
  
  throw new Error('Timeout waiting for onboarding');
}
```

---

## Error Handling

All endpoints return standard HTTP codes:
- `200` - Success
- `202` - Accepted (async processing started)
- `404` - Thread/session not found
- `400` - Bad request (validation error)
- `500` - Server error

Error response format:
```json
{
  "detail": "Error message"
}
```

---

## On Successful Onboarding

When status becomes `COMPLETED`:

1. **Agreement PDF** is generated at `/agreements/{merchant_id}`
2. **Welcome Email** is sent to signatory email with:
   - Account details summary
   - Next steps instructions
   - Agreement PDF attachment

---

## Debug & Demo Endpoints

These endpoints are for development, testing, and demo purposes.

### Endpoint Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/onboard/{thread_id}/state` | GET | View full internal state |
| `/debug/threads` | GET | List all thread IDs |
| `/debug/jobs` | GET | List all jobs with status |
| `/debug/simulate` | GET | View simulation flags |
| `/debug/simulate` | POST | Set simulation flags |
| `/debug/simulate` | DELETE | Reset simulation flags |
| `/debug/test-email` | POST | Send test welcome email |
| `/debug/test-pdf` | POST | Generate test agreement PDF |

### View Full State

Useful for demos to show current merchant data and verification progress:

```bash
curl http://localhost:8000/onboard/{thread_id}/state
```

### List All Sessions

```bash
# List all thread IDs
curl http://localhost:8000/debug/threads

# List all jobs with details
curl http://localhost:8000/debug/jobs
```

### Test Email & PDF

```bash
# Send test welcome email
curl -X POST "http://localhost:8000/debug/test-email?to_email=your@email.com"

# Generate test agreement PDF
curl -X POST http://localhost:8000/debug/test-pdf
```

---

## Simulation Mode (Development)

Simulate specific failure scenarios for UI testing. **No server restart needed!**

**Requirement:** `ENVIRONMENT=development`

### View Current Simulation State

```bash
curl http://localhost:8000/debug/simulate
```

**Response:**
```json
{
  "environment": "development",
  "real_checks_enabled": false,
  "behavior": {
    "input": "mock_success",
    "doc": "mock_success",
    "bank": "mock_success",
    "web": "mock_success"
  },
  "active_failures": [],
  "all_flags": {...},
  "hint": "Set force_success_all=false and simulate_real_checks=true to run real checks"
}
```

### Enable/Disable Failures

```bash
# Enable document blurry failure
curl -X POST http://localhost:8000/debug/simulate \
-H "Content-Type: application/json" \
-d '{"doc_blurry": true}'

# Enable multiple failures
curl -X POST http://localhost:8000/debug/simulate \
-H "Content-Type: application/json" \
-d '{"doc_blurry": true, "web_no_ssl": true, "bank_name_mismatch": true}'

# Disable all failures (mock success for everything)
curl -X POST http://localhost:8000/debug/simulate \
-H "Content-Type: application/json" \
-d '{"force_success_all": true}'

# Reset to environment defaults
curl -X DELETE http://localhost:8000/debug/simulate
```

### Available Simulation Scenarios

| Flag | Description |
|------|-------------|
| **Force Success** | |
| `force_success_all` | Skip all real checks, mock success |
| `force_success_input` | Skip input validation |
| `force_success_doc` | Skip document checks |
| `force_success_bank` | Skip bank verification |
| `force_success_web` | Skip website compliance |
| **Document Failures** | |
| `doc_blurry` | OCR fails - blurry document |
| `doc_missing` | Document file not found |
| `doc_invalid` | Document missing required fields |
| **Bank Failures** | |
| `bank_name_mismatch` | Account holder name doesn't match |
| `bank_invalid_ifsc` | Invalid IFSC code |
| `bank_account_closed` | Account closed/inactive |
| **Website Failures** | |
| `web_no_ssl` | No HTTPS |
| `web_no_privacy` | Missing privacy policy |
| `web_no_terms` | Missing terms of service |
| `web_no_refund` | Missing refund policy |
| `web_no_contact` | Missing contact info |
| **Input Failures** | |
| `input_invalid_pan` | Invalid PAN format |
| `input_invalid_gstin` | Invalid GSTIN format |

### Environment Variables (Alternative)

Set in `.env` file (requires restart):

```bash
# Development mode
ENVIRONMENT=development

# Force success (skip real checks)
SIMULATE_FORCE_SUCCESS_ALL=true

# Or simulate specific failures
SIMULATE_DOC_BLURRY_FAILURE=true
SIMULATE_WEB_NO_SSL_FAILURE=true
```

---

## Complete Integration Example

```typescript
// 1. Start onboarding
const startRes = await fetch('http://localhost:8000/onboard', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(merchantData)
});
const { thread_id } = await startRes.json();

// 2. Poll for status
let status = await pollStatus(thread_id);

// 3. Handle NEEDS_REVIEW
if (status.status === 'NEEDS_REVIEW') {
  // Get action items
  const itemsRes = await fetch(`http://localhost:8000/onboard/${thread_id}/action-items`);
  const { action_items } = await itemsRes.json();
  
  // Show to user, collect fixes...
  
  // If document upload needed
  const filePath = await uploadDocument(newFile, merchantId);
  
  // Resume with fixes
  await fetch(`http://localhost:8000/onboard/${thread_id}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      documents_path: filePath,
      business_details: { website_url: 'https://fixed.com' }
    })
  });
  
  // Poll again
  status = await pollStatus(thread_id);
}

// 4. Handle COMPLETED
if (status.status === 'COMPLETED') {
  // Agreement PDF available at /agreements/{merchant_id}
  // Welcome email sent to signatory
  console.log('Onboarding complete!');
}
```
