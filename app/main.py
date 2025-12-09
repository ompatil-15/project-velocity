from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.responses import FileResponse
from app.schema import MerchantApplication, ResumePayload, JobStatus
from app.graph import build_graph
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
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
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
            "example": {
                "documents_path": absolute_path
            }
        }
    }


@app.get("/upload/{filename}")
async def get_uploaded_file(filename: str):
    """Download a previously uploaded file."""
    file_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


async def run_onboarding_workflow(thread_id: str, initial_state: dict):
    """
    Background task that runs the onboarding workflow.
    Updates job status and action items in SQLite as it progresses.
    """
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
            await job_store.update_job(
                thread_id,
                status=JobStatus.COMPLETED,
                stage="FINAL",
                result=final_state,
                action_items=action_items,
            )

        print(f"[Background] Workflow completed for thread {thread_id} with {len(action_items)} action items")

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
    print(f"Starting onboarding for: {application.business_details.entity_type}")

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
        if job["status"] in [JobStatus.COMPLETED.value, JobStatus.NEEDS_REVIEW.value, JobStatus.FAILED.value]:
            result = job.get("result") or {}
            response["risk_score"] = result.get("risk_score", 0.0)
            response["verification_notes"] = result.get("verification_notes", [])
            response["consultant_plan"] = result.get("consultant_plan", [])
            response["compliance_issues"] = result.get("compliance_issues", [])
            
            # Include action item summary
            action_items = job.get("action_items", [])
            blocking = [i for i in action_items if i.get("severity") == "BLOCKING" and not i.get("resolved")]
            warnings = [i for i in action_items if i.get("severity") == "WARNING" and not i.get("resolved")]
            
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


@app.get("/onboard/{thread_id}/action-items")
async def get_action_items(
    thread_id: str,
    include_resolved: bool = Query(default=False, description="Include resolved action items"),
):
    """
    Get action items for a specific onboarding session.
    
    This is a dedicated endpoint following Single Responsibility Principle (SRP).
    
    Returns:
        - action_items: List of action items with full details
        - summary: Count of blocking/warning items
        - resume_hint: Example payload for the resume endpoint
    """
    # Get action items from job store
    action_items = await job_store.get_action_items(thread_id, include_resolved=include_resolved)
    
    if action_items is None:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Categorize items
    blocking = [i for i in action_items if i.get("severity") == "BLOCKING" and not i.get("resolved")]
    warnings = [i for i in action_items if i.get("severity") == "WARNING" and not i.get("resolved")]
    resolved = [i for i in action_items if i.get("resolved")]
    
    # Build response
    response = {
        "thread_id": thread_id,
        "action_items": action_items,
        "summary": {
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "resolved_count": len(resolved),
            "total_pending": len(blocking) + len(warnings),
        },
    }
    
    # Add resume hint if there are pending items
    if blocking or warnings:
        pending_ids = [i.get("id") for i in blocking + warnings if i.get("id")]
        response["resume_hint"] = {
            "description": "After resolving issues, call POST /onboard/{thread_id}/resume with:",
            "example_payload": {
                "resolved_items": pending_ids[:3] + (["..."] if len(pending_ids) > 3 else []),
                "updated_data": {
                    "documents_path": "/path/to/new/document.pdf",
                    "business_details": {
                        "website_url": "https://updated-website.com"
                    }
                },
                "user_message": "I have resolved the issues"
            }
        }
    
    return response


@app.post("/onboard/{thread_id}/resume")
async def resume_onboarding(
    thread_id: str,
    payload: ResumePayload,
    background_tasks: BackgroundTasks,
):
    """
    Resumes the onboarding process after merchant intervention.
    
    Accepts:
        - resolved_items: List of action item IDs that were resolved
        - updated_data: Updated application data (merged with existing)
        - user_message: Optional message from merchant
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await agent_app.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # 1. Mark resolved items
        if payload.resolved_items:
            await job_store.mark_items_resolved(thread_id, payload.resolved_items)
            print(f"Marked {len(payload.resolved_items)} items as resolved")

        # 2. Update State with new data (if any)
        if payload.updated_data:
            current_app_data = current_state.values.get("application_data", {})
            if isinstance(current_app_data, dict):
                # Deep merge for nested dicts like business_details
                for key, value in payload.updated_data.items():
                    if key in current_app_data and isinstance(current_app_data[key], dict) and isinstance(value, dict):
                        current_app_data[key].update(value)
                    else:
                        current_app_data[key] = value

            await agent_app.aupdate_state(
                config, {"application_data": current_app_data}
            )

        # Update job status to processing
        await job_store.update_job(thread_id, status=JobStatus.PROCESSING)

        # 3. Resume execution in background
        async def resume_workflow():
            try:
                final_state = await agent_app.ainvoke(None, config=config)
                
                # Get new action items
                new_action_items = final_state.get("action_items", [])
                
                # Merge with existing (keeping resolved status from DB)
                existing_items = await job_store.get_action_items(thread_id, include_resolved=True)
                
                # Only add truly new items (by ID)
                existing_ids = {i.get("id") for i in existing_items if i.get("id")}
                items_to_add = [i for i in new_action_items if i.get("id") not in existing_ids]
                
                if items_to_add:
                    await job_store.append_action_items(thread_id, items_to_add)
                
                # Check if still interrupted
                new_state = await agent_app.aget_state(config)
                
                # Get final action items count
                final_items = await job_store.get_action_items(thread_id, include_resolved=True)
                
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
            "resolved_items_count": len(payload.resolved_items) if payload.resolved_items else 0,
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


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
