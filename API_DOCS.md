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

## Endpoints

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
  "action_items_count": 2
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
      "category": "DOCUMENT | BANK | WEBSITE | COMPLIANCE",
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
async function uploadDocument(file: File): Promise<string> {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await fetch('/api/upload', { method: 'POST', body: formData });
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

```json
// Just re-verify (no data change)
{}

// Update document
{"documents_path": "/uploads/new_doc.pdf"}

// Update website
{"business_details": {"website_url": "https://fixed-site.com"}}

// Update bank details
{"bank_details": {"account_holder_name": "Corrected Name"}}

// Multiple updates
{
  "documents_path": "/uploads/new.pdf",
  "business_details": {"website_url": "https://new.com"},
  "user_message": "Fixed all issues"
}
```

**Response:** `202 Accepted`
```json
{
  "status": "ACCEPTED",
  "thread_id": "uuid",
  "data_updated": true,
  "fields_updated": ["documents_path", "business_details"]
}
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
```

---

## Polling Pattern

```typescript
async function pollStatus(threadId: string): Promise<StatusResponse> {
  const maxAttempts = 60;
  const interval = 2000; // 2 seconds
  
  for (let i = 0; i < maxAttempts; i++) {
    const res = await fetch(`/onboard/${threadId}/status`);
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
- `500` - Server error

Error response format:
```json
{
  "detail": "Error message"
}
```

---

## Simulation Mode (Development)

Simulate specific failure scenarios for UI testing. **No server restart needed!**

**Requirement:** `ENVIRONMENT=development`

### Runtime Toggle (Recommended)

```bash
# View current flags
GET /debug/simulate

# Enable failures (no restart!)
POST /debug/simulate
{"doc_blurry": true, "web_no_refund_policy": true}

# Disable a flag
POST /debug/simulate
{"doc_blurry": false}

# Reset all to env vars
DELETE /debug/simulate
```

### Available Scenarios

| Scenario | Description |
|----------|-------------|
| **Document** | |
| `doc_blurry` | OCR fails - blurry document |
| `doc_missing` | Document file not found |
| `doc_invalid` | Document missing required fields |
| **Bank** | |
| `bank_name_mismatch` | Account holder name doesn't match |
| `bank_invalid_ifsc` | Invalid IFSC code |
| `bank_account_closed` | Account closed/inactive |
| **Website** | |
| `web_unreachable` | Website down |
| `web_no_ssl` | No HTTPS |
| `web_no_refund_policy` | Missing refund policy |
| `web_no_privacy_policy` | Missing privacy policy |
| `web_no_terms` | Missing terms of service |
| `web_prohibited_content` | Prohibited content found |
| `web_domain_new` | Domain < 30 days old |
| `web_adverse_media` | Negative news found |
| **Input** | |
| `input_invalid_pan` | Invalid PAN format |
| `input_invalid_gstin` | Invalid GSTIN format |

### Environment Variables (Alternative)

Set in `.env` file (requires restart):

```bash
SIMULATE_DOC_BLURRY=true
SIMULATE_WEB_NO_REFUND_POLICY=true
```

---

## Debug Endpoints

```
GET /debug/threads  → List all thread IDs
GET /debug/jobs     → List all jobs with status
```
