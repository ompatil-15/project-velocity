from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import FileResponse
from app.schema import MerchantApplication, ResumePayload, JobStatus
from app.graph import build_graph
from typing import List
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from fastapi.staticfiles import StaticFiles
from app.utils import job_store
import uvicorn
import uuid
from contextlib import asynccontextmanager
import aiosqlite
import os
from typing import Optional
from datetime import datetime

# Uploads directory for documents
UPLOADS_DIR = "uploads"

# Global variable to hold the compiled graph
agent_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize job table
    await job_store.init_job_table()
    print("Job tracking table initialized.")

    # Load the Checkpointer
    async with AsyncSqliteSaver.from_conn_string(
        "db/checkpoints.sqlite"
    ) as checkpointer:
        # Build and Compile the Graph
        global agent_app
        workflow = build_graph()
        agent_app = workflow.compile(
            checkpointer=checkpointer, interrupt_after=["consultant_fixer_node"]
        )
        print("Agent Graph compiled with Async Persistence.")
        yield
        # Connection closes automatically on exit


app = FastAPI(title="Project Velocity Agent", version="1.0", lifespan=lifespan)

# Create necessary directories
os.makedirs("evidence", exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Mount static directories
app.mount("/evidence", StaticFiles(directory="evidence"), name="evidence")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Project Velocity Agent"}


# --- Document Upload ---

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    merchant_id: Optional[str] = None,
):
    """
    Upload a document (KYC, ID proof, etc.) for onboarding.

    Returns the file_path to use in the /onboard request.

    Accepts: PDF, PNG, JPG/JPEG (max 10MB)
    """
    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    merchant_prefix = merchant_id[:8] if merchant_id else "unknown"
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{merchant_prefix}_{timestamp}_{unique_id}{ext}"

    # Save file
    file_path = os.path.join(UPLOADS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Return absolute path for use in documents_path
    absolute_path = os.path.abspath(file_path)

    return {
        "status": "uploaded",
        "filename": filename,
        "file_path": absolute_path,
        "size_bytes": len(content),
        "content_type": file.content_type,
        "usage_hint": {
            "description": "Use file_path in your /onboard request:",
            "example": {"documents_path": absolute_path},
        },
    }


@app.get("/upload/{filename}")
async def get_uploaded_file(filename: str):
    """Download a previously uploaded file."""
    file_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# --- Agreement Download ---


@app.get("/agreements/{merchant_id}")
async def get_agreement(merchant_id: str):
    """
    Download the merchant agreement PDF.

    The agreement is generated upon successful onboarding completion.
    """
    from app.utils.pdf_generator import get_agreement_path

    agreement_path = await get_agreement_path(merchant_id)

    if not agreement_path:
        raise HTTPException(
            status_code=404,
            detail=f"Agreement not found for merchant {merchant_id}. It may not be generated yet.",
        )

    filename = f"Merchant_Agreement_{merchant_id}.pdf"
    if agreement_path.endswith(".html"):
        filename = f"Merchant_Agreement_{merchant_id}.html"

    return FileResponse(
        agreement_path,
        filename=filename,
        media_type=(
            "application/pdf" if agreement_path.endswith(".pdf") else "text/html"
        ),
    )


async def run_onboarding_workflow(thread_id: str, initial_state: dict):
    """
    Background task that runs the onboarding workflow.
    Updates job status and action items in SQLite as it progresses.
    On success, generates agreement PDF and sends welcome email.
    """
    from app.utils.pdf_generator import generate_agreement_pdf
    from app.utils.email_service import send_welcome_email

    try:
        # Update status to processing
        await job_store.update_job(thread_id, status=JobStatus.PROCESSING)

        config = {"configurable": {"thread_id": thread_id}}

        # Run the workflow
        print(f"[Background] Starting workflow for thread {thread_id}")
        final_state = await agent_app.ainvoke(initial_state, config=config)

        # Extract action items from final state
        action_items = final_state.get("action_items", [])

        # Check if workflow is interrupted (needs review)
        current_state = await agent_app.aget_state(config)

        if current_state.next:
            # Graph is interrupted - needs merchant intervention
            await job_store.update_job(
                thread_id,
                status=JobStatus.NEEDS_REVIEW,
                stage=final_state.get("stage", "UNKNOWN"),
                result=final_state,
                action_items=action_items,
            )
        elif final_state.get("error_message"):
            await job_store.update_job(
                thread_id,
                status=JobStatus.NEEDS_REVIEW,
                stage=final_state.get("stage", "UNKNOWN"),
                error_message=final_state.get("error_message"),
                result=final_state,
                action_items=action_items,
            )
        else:
            # SUCCESS: Generate agreement PDF and send welcome email
            print(f"[Background] SUCCESS - Generating agreement and sending email")
            merchant_id = final_state.get("merchant_id", thread_id)
            merchant_data = final_state.get("application_data", {})

            print(f"[Background] Merchant ID: {merchant_id}")
            print(
                f"[Background] Merchant Data Keys: {merchant_data.keys() if merchant_data else 'None'}"
            )

            # Generate agreement PDF
            pdf_result = await generate_agreement_pdf(
                merchant_data=merchant_data,
                merchant_id=merchant_id,
            )
            print(f"[Background] Agreement PDF: {pdf_result}")

            # Send welcome email
            signatory_email = merchant_data.get("signatory_details", {}).get("email")
            print(f"[Background] Signatory email from data: {signatory_email}")
            # Use test email in dev mode if not provided
            if not signatory_email:
                signatory_email = os.getenv("TEST_EMAIL")
                print(f"[Background] Using fallback email: {signatory_email}")

            email_result = await send_welcome_email(
                to_email=signatory_email,
                merchant_data=merchant_data,
                merchant_id=merchant_id,
                agreement_pdf_path=pdf_result.get("file_path"),
            )
            print(f"[Background] Welcome email result: {email_result}")

            # Update job with completion info
            await job_store.update_job(
                thread_id,
                status=JobStatus.COMPLETED,
                stage="FINAL",
                result={
                    **final_state,
                    "agreement": pdf_result,
                    "email": email_result,
                },
                action_items=action_items,
            )

        print(
            f"[Background] Workflow completed for thread {thread_id} with {len(action_items)} action items"
        )

    except Exception as e:
        print(f"[Background] Workflow failed for thread {thread_id}: {e}")
        await job_store.update_job(
            thread_id,
            status=JobStatus.FAILED,
            error_message=str(e),
        )


@app.post("/onboard")
async def start_onboarding(
    application: MerchantApplication,
    background_tasks: BackgroundTasks,
):
    """
    Triggers the autonomous onboarding agent.
    Returns immediately with a thread_id for status polling.
    The actual workflow runs in the background.
    """
    print(f"Starting onboarding for merchant: {application.merchant_id}")
    # Generate thread ID
    thread_id = str(uuid.uuid4())

    # Use provided merchant_id or generate UUID
    merchant_id = application.merchant_id or str(uuid.uuid4())

    # Initialize Agent State
    initial_state = {
        "application_data": application.model_dump(),
        "merchant_id": merchant_id,
        # Status
        "stage": "INPUT",
        "status": "IN_PROGRESS",
        # Default flags
        "is_auth_valid": False,
        "is_bank_verified": False,
        "is_doc_verified": False,
        "is_website_compliant": False,
        # Feedback
        "risk_score": 0.0,
        "verification_notes": [],
        "compliance_issues": [],
        "missing_artifacts": [],
        "consultant_plan": [],
        "action_items": [],  # Initialize empty action items
        # Internal
        "messages": [],
        "error_message": None,
        "retry_count": 0,
    }

    # Create job entry in SQLite
    await job_store.create_job(thread_id, merchant_id)

    # Add workflow to background tasks
    background_tasks.add_task(run_onboarding_workflow, thread_id, initial_state)

    # Return immediately with 200
    return {
        "status": "ACCEPTED",
        "message": "Onboarding request accepted. Use /onboard/{thread_id}/status to poll for updates.",
        "thread_id": thread_id,
        "merchant_id": merchant_id,
    }


@app.get("/onboard/{thread_id}/status")
async def get_status(thread_id: str):
    """
    Get the current status of the onboarding session.
    Use this endpoint for long polling to check job progress.

    Returns:
        - status: QUEUED | PROCESSING | NEEDS_REVIEW | COMPLETED | FAILED
        - stage: Current workflow stage
        - Additional details based on status
    """
    # Check SQLite job store
    job = await job_store.get_job(thread_id)

    if job:
        response = {
            "status": job["status"],
            "stage": job["stage"],
            "merchant_id": job["merchant_id"],
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }

        if job.get("error_message"):
            response["error_message"] = job["error_message"]

        # If completed or needs review, include more details from result
        if job["status"] in [
            JobStatus.COMPLETED.value,
            JobStatus.NEEDS_REVIEW.value,
            JobStatus.FAILED.value,
        ]:
            result = job.get("result") or {}
            response["risk_score"] = result.get("risk_score", 0.0)
            response["verification_notes"] = result.get("verification_notes", [])
            response["consultant_plan"] = result.get("consultant_plan", [])
            response["compliance_issues"] = result.get("compliance_issues", [])

            # Include action item summary
            action_items = job.get("action_items", [])
            blocking = [
                i
                for i in action_items
                if i.get("severity") == "BLOCKING" and not i.get("resolved")
            ]
            warnings = [
                i
                for i in action_items
                if i.get("severity") == "WARNING" and not i.get("resolved")
            ]

            response["action_items_summary"] = {
                "blocking_count": len(blocking),
                "warning_count": len(warnings),
                "total_pending": len(blocking) + len(warnings),
            }

        return response

    # Fallback: Try to get from LangGraph state (for old sessions before persistence)
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await agent_app.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        state_data = current_state.values

        # Determine status
        status = state_data.get("status", "IN_PROGRESS")
        if current_state.next:
            status = "NEEDS_REVIEW"

        return {
            "status": status,
            "stage": state_data.get("stage", "UNKNOWN"),
            "risk_score": state_data.get("risk_score", 0.0),
            "consultant_plan": state_data.get("consultant_plan", []),
            "verification_notes": state_data.get("verification_notes", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")


@app.get("/onboard/{thread_id}/state")
async def get_full_state(thread_id: str):
    """
    Get the full state of the onboarding session including all application data.
    
    Useful for:
    - Debugging data updates after resume
    - Viewing current merchant application data
    - Inspecting verification flags
    
    Returns:
        - application_data: Full merchant application (business, bank, signatory details)
        - verification_flags: is_auth_valid, is_doc_verified, is_bank_verified, is_website_compliant
        - workflow_state: status, stage, error messages
        - action_items: All action items with full details
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await agent_app.aget_state(config)
        
        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail="Session not found")
        
        state = current_state.values
        
        # Build comprehensive response
        response = {
            # Application data
            "application_data": state.get("application_data", {}),
            "merchant_id": state.get("merchant_id"),
            
            # Verification flags
            "verification_flags": {
                "is_auth_valid": state.get("is_auth_valid", False),
                "is_doc_verified": state.get("is_doc_verified", False),
                "is_bank_verified": state.get("is_bank_verified", False),
                "is_website_compliant": state.get("is_website_compliant", False),
            },
            
            # Workflow state
            "workflow": {
                "status": state.get("status", "IN_PROGRESS"),
                "stage": state.get("stage", "UNKNOWN"),
                "next_step": state.get("next_step"),
                "error_message": state.get("error_message"),
                "retry_count": state.get("retry_count", 0),
            },
            
            # Risk and compliance
            "assessment": {
                "risk_score": state.get("risk_score", 0.0),
                "compliance_issues": state.get("compliance_issues", []),
                "missing_artifacts": state.get("missing_artifacts", []),
            },
            
            # Action items
            "action_items": state.get("action_items", []),
            
            # Notes and plan
            "verification_notes": state.get("verification_notes", []),
            "consultant_plan": state.get("consultant_plan", []),
            
            # Graph metadata
            "_meta": {
                "next_nodes": list(current_state.next) if current_state.next else [],
                "is_interrupted": bool(current_state.next),
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")


@app.get("/onboard/{thread_id}/action-items")
async def get_action_items(
    thread_id: str,
    include_resolved: bool = Query(
        default=False, description="Include resolved action items"
    ),
):
    """
    Get action items for a specific onboarding session.

    Returns:
        - action_items: List of action items with full details
        - summary: Count of blocking/warning items
        - resume_hint: Example payload for the resume endpoint
    """
    # Get action items from job store
    action_items = await job_store.get_action_items(
        thread_id, include_resolved=include_resolved
    )

    if action_items is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Categorize items by severity
    blocking = [
        i
        for i in action_items
        if i.get("severity") == "BLOCKING" and not i.get("resolved")
    ]
    warnings = [
        i
        for i in action_items
        if i.get("severity") == "WARNING" and not i.get("resolved")
    ]
    resolved = [i for i in action_items if i.get("resolved")]

    pending = blocking + warnings

    # Build response
    response = {
        "thread_id": thread_id,
        "action_items": action_items,
        "summary": {
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "resolved_count": len(resolved),
            "total_pending": len(pending),
        },
    }

    # Add resume hints - simple: just send partial data in same structure as MerchantApplication
    if pending:
        fields_to_update = list(
            set(i.get("field_to_update") for i in pending if i.get("field_to_update"))
        )

        response["resume_hint"] = {
            "description": "Send any updated fields in the same structure as MerchantApplication. Empty payload to just re-verify.",
            "fields_with_issues": fields_to_update,
            "examples": {
                "just_reverify": {},
                "update_document": {"documents_path": "/uploads/new_doc.pdf"},
                "update_website": {
                    "business_details": {"website_url": "https://new-site.com"}
                },
                "update_bank": {
                    "bank_details": {"account_holder_name": "Corrected Name"}
                },
            },
        }

    return response


def deep_merge(base: dict, updates: dict) -> dict:
    """Deep merge updates into base dict."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif value is not None:  # Only update if value is not None
            result[key] = value
    return result


@app.post("/onboard/{thread_id}/resume")
async def resume_onboarding(
    thread_id: str,
    payload: ResumePayload,
    background_tasks: BackgroundTasks,
):
    """
    Resumes the onboarding process after merchant intervention.

    Simple approach:
    - Send partial application data in same structure as MerchantApplication
    - Fields not provided are kept from existing state
    - Empty payload = just re-verify (merchant fixed externally)

    Examples:
        - Just re-verify: {}
        - Update document: {"documents_path": "/uploads/new_doc.pdf"}
        - Update website: {"business_details": {"website_url": "https://new-site.com"}}
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await agent_app.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get current application data
        current_app_data = current_state.values.get("application_data", {})

        # Build updates from payload
        updates = {}
        if payload.documents_path:
            updates["documents_path"] = payload.documents_path
        if payload.business_details:
            updates["business_details"] = payload.business_details.model_dump(
                exclude_none=True
            )
        if payload.bank_details:
            updates["bank_details"] = payload.bank_details.model_dump(exclude_none=True)
        if payload.signatory_details:
            updates["signatory_details"] = payload.signatory_details.model_dump(
                exclude_none=True
            )

        # Deep merge updates into current data
        if updates:
            merged_data = deep_merge(current_app_data, updates)
            await agent_app.aupdate_state(config, {"application_data": merged_data})
            print(f"Updated application data: {list(updates.keys())}")

        # Update job status to processing
        await job_store.update_job(thread_id, status=JobStatus.PROCESSING)

        # Resume execution in background
        async def resume_workflow():
            try:
                final_state = await agent_app.ainvoke(None, config=config)

                # Get new action items
                new_action_items = final_state.get("action_items", [])

                # Merge with existing (keeping resolved status from DB)
                existing_items = (
                    await job_store.get_action_items(thread_id, include_resolved=True)
                    or []
                )

                # Only add truly new items (by ID)
                existing_ids = {i.get("id") for i in existing_items if i.get("id")}
                items_to_add = [
                    i for i in new_action_items if i.get("id") not in existing_ids
                ]

                if items_to_add:
                    await job_store.append_action_items(thread_id, items_to_add)

                # Check if still interrupted
                new_state = await agent_app.aget_state(config)

                # Get final action items
                final_items = (
                    await job_store.get_action_items(thread_id, include_resolved=True)
                    or []
                )

                if new_state.next:
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.NEEDS_REVIEW,
                        stage=final_state.get("stage", "UNKNOWN"),
                        result=final_state,
                        action_items=final_items,
                    )
                elif final_state.get("error_message"):
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.NEEDS_REVIEW,
                        stage=final_state.get("stage", "UNKNOWN"),
                        error_message=final_state.get("error_message"),
                        result=final_state,
                        action_items=final_items,
                    )
                else:
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.COMPLETED,
                        stage="FINAL",
                        result=final_state,
                        action_items=final_items,
                    )

                print(f"[Background] Resume completed for {thread_id}")

            except Exception as e:
                print(f"[Background] Resume failed for {thread_id}: {e}")
                await job_store.update_job(
                    thread_id,
                    status=JobStatus.FAILED,
                    error_message=str(e),
                )

        background_tasks.add_task(resume_workflow)

        return {
            "status": "ACCEPTED",
            "message": "Resume request accepted. Use /onboard/{thread_id}/status to poll for updates.",
            "thread_id": thread_id,
            "data_updated": bool(updates),
            "fields_updated": list(updates.keys()) if updates else [],
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Debug Endpoints ---


@app.get("/debug/threads")
async def list_threads():
    """List all active threads in the checkpoints table."""
    try:
        async with aiosqlite.connect("db/checkpoints.sqlite") as db:
            cursor = await db.execute("SELECT DISTINCT thread_id FROM checkpoints")
            rows = await cursor.fetchall()
            return {"threads": [row[0] for row in rows]}
    except Exception as e:
        return {"error": str(e), "threads": []}


@app.get("/debug/jobs")
async def list_jobs():
    """List all jobs from SQLite."""
    jobs = await job_store.list_jobs()
    return {"jobs": jobs}


# --- Simulation Control (No Restart Needed) ---

from app.utils.simulation import sim


@app.get("/debug/simulate")
async def get_simulations():
    """
    Get current simulation flags and behavior.
    Shows which failures are being simulated and what each node will do.
    """
    if not sim.is_dev_mode():
        raise HTTPException(
            status_code=403, detail="Simulations only available in development mode"
        )

    import os

    real_checks_enabled = os.getenv("SIMULATE_REAL_CHECKS", "false").lower() == "true"

    return {
        "environment": "development",
        "real_checks_enabled": real_checks_enabled,
        "behavior": {
            "doc": (
                "MOCK_SUCCESS"
                if sim.should_skip("doc")
                else (
                    "SIMULATE_FAILURE"
                    if any(
                        sim.should_fail(f)
                        for f in ["doc_blurry", "doc_missing", "doc_invalid"]
                    )
                    else "REAL_CHECK"
                )
            ),
            "bank": (
                "MOCK_SUCCESS"
                if sim.should_skip("bank")
                else (
                    "SIMULATE_FAILURE"
                    if any(
                        sim.should_fail(f)
                        for f in [
                            "bank_name_mismatch",
                            "bank_invalid_ifsc",
                            "bank_account_closed",
                        ]
                    )
                    else "REAL_CHECK"
                )
            ),
            "web": (
                "MOCK_SUCCESS"
                if sim.should_skip("web")
                else (
                    "SIMULATE_FAILURE"
                    if any(
                        sim.should_fail(f)
                        for f in [
                            "web_unreachable",
                            "web_no_ssl",
                            "web_no_refund_policy",
                            "web_no_privacy_policy",
                            "web_no_terms",
                            "web_prohibited_content",
                            "web_domain_new",
                            "web_adverse_media",
                        ]
                    )
                    else "REAL_CHECK"
                )
            ),
            "input": (
                "MOCK_SUCCESS"
                if sim.should_skip("input")
                else (
                    "SIMULATE_FAILURE"
                    if any(
                        sim.should_fail(f)
                        for f in ["input_invalid_pan", "input_invalid_gstin"]
                    )
                    else "REAL_CHECK"
                )
            ),
        },
        "active_failures": sim.get_active_simulations(),
        "all_flags": sim.get_all_flags(),
        "available_scenarios": sim.ALL_SCENARIOS,
        "hint": {
            "mock_success": "Default in dev mode - all checks pass",
            "simulate_failure": "Set specific flags to test error UI",
            "real_check": "Set SIMULATE_REAL_CHECKS=true to run actual checks",
        },
    }


@app.post("/debug/simulate")
async def set_simulations(flags: dict):
    """
    Set simulation flags at runtime (no restart needed).

    Example:
        POST /debug/simulate
        {"doc_blurry": true, "web_no_refund_policy": true}

    To disable a flag:
        {"doc_blurry": false}
    """
    if not sim.is_dev_mode():
        raise HTTPException(
            status_code=403, detail="Simulations only available in development mode"
        )

    # Validate flags
    invalid = [k for k in flags.keys() if k not in sim.ALL_SCENARIOS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenarios: {invalid}. Available: {sim.ALL_SCENARIOS}",
        )

    # Set flags
    updated = sim.set_flags(flags)

    return {
        "updated": updated,
        "active": sim.get_active_simulations(),
    }


@app.delete("/debug/simulate")
async def reset_simulations():
    """
    Reset all runtime simulation flags.
    Reverts to environment variable settings.
    """
    if not sim.is_dev_mode():
        raise HTTPException(
            status_code=403, detail="Simulations only available in development mode"
        )

    sim.reset_flags()

    return {
        "message": "All runtime flags reset. Now using environment variables.",
        "active": sim.get_active_simulations(),
    }


# --- Test Endpoints for Email and PDF ---


@app.post("/debug/test-email")
async def test_email(to_email: str = Query()):
    """
    Send a test welcome email to verify email configuration.
    """
    from app.utils.email_service import send_test_email

    result = await send_test_email(to_email)
    return result


@app.post("/debug/test-pdf")
async def test_pdf():
    """
    Generate a test agreement PDF to verify PDF generation.
    """
    from app.utils.pdf_generator import generate_test_agreement

    result = await generate_test_agreement()
    return result


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
