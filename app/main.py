from fastapi import FastAPI, HTTPException, BackgroundTasks
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

# Mount Evidence Directory for static access
os.makedirs("evidence", exist_ok=True)
app.mount("/evidence", StaticFiles(directory="evidence"), name="evidence")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Project Velocity Agent"}


async def run_onboarding_workflow(thread_id: str, initial_state: dict):
    """
    Background task that runs the onboarding workflow.
    Updates job status in SQLite as it progresses.
    """
    try:
        # Update status to processing
        await job_store.update_job(thread_id, status=JobStatus.PROCESSING)

        config = {"configurable": {"thread_id": thread_id}}

        # Run the workflow
        print(f"[Background] Starting workflow for thread {thread_id}")
        final_state = await agent_app.ainvoke(initial_state, config=config)

        # Check if workflow is interrupted (needs review)
        current_state = await agent_app.aget_state(config)
        
        if current_state.next:
            # Graph is interrupted - needs merchant intervention
            await job_store.update_job(
                thread_id,
                status=JobStatus.NEEDS_REVIEW,
                stage=final_state.get("stage", "UNKNOWN"),
                result=final_state,
            )
        elif final_state.get("error_message"):
            await job_store.update_job(
                thread_id,
                status=JobStatus.NEEDS_REVIEW,
                stage=final_state.get("stage", "UNKNOWN"),
                error_message=final_state.get("error_message"),
                result=final_state,
            )
        else:
            await job_store.update_job(
                thread_id,
                status=JobStatus.COMPLETED,
                stage="FINAL",
                result=final_state,
            )

        print(f"[Background] Workflow completed for thread {thread_id}")

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


@app.post("/onboard/{thread_id}/resume")
async def resume_onboarding(
    thread_id: str,
    payload: ResumePayload,
    background_tasks: BackgroundTasks,
):
    """
    Resumes the onboarding process after merchant intervention.
    Also runs asynchronously - returns immediately and runs in background.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await agent_app.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # 1. Update State with new data (if any)
        if payload.updated_data:
            current_app_data = current_state.values.get("application_data", {})
            if isinstance(current_app_data, dict):
                current_app_data.update(payload.updated_data)

            await agent_app.aupdate_state(
                config, {"application_data": current_app_data}
            )

        # Update job status to processing
        await job_store.update_job(thread_id, status=JobStatus.PROCESSING)

        # 2. Resume execution in background
        async def resume_workflow():
            try:
                final_state = await agent_app.ainvoke(None, config=config)
                
                # Check if still interrupted
                new_state = await agent_app.aget_state(config)
                
                if new_state.next:
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.NEEDS_REVIEW,
                        stage=final_state.get("stage", "UNKNOWN"),
                        result=final_state,
                    )
                elif final_state.get("error_message"):
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.NEEDS_REVIEW,
                        stage=final_state.get("stage", "UNKNOWN"),
                        error_message=final_state.get("error_message"),
                        result=final_state,
                    )
                else:
                    await job_store.update_job(
                        thread_id,
                        status=JobStatus.COMPLETED,
                        stage="FINAL",
                        result=final_state,
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
