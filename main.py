from fastapi import FastAPI, HTTPException
from schema import MerchantApplication, ResumePayload
from agent_graph import graph
import uvicorn
import uuid

app = FastAPI(title="Project Velocity Agent", version="1.0")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Project Velocity Agent"}


@app.post("/onboard/start")
async def start_onboarding(application: MerchantApplication):
    """
    Triggers the autonomous onboarding agent.
    """
    print(f"Starting onboarding for: {application.business_details.entity_type}")

    # Initialize Agent State
    initial_state = {
        "application_data": application.model_dump(),
        "merchant_id": application.business_details.pan,
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

    try:
        # Enable Concurrency via Thread ID
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # Invoke the LangGraph agent with config
        final_state = await graph.ainvoke(initial_state, config=config)

        # Determine final status
        status = "COMPLETED"
        if final_state.get("error_message"):
            status = "NEEDS_REVIEW"

        return {
            "status": status,
            "thread_id": thread_id,
            "merchant_id": application.business_details.pan,  # simple ID
            "result": final_state,
        }

    except Exception as e:
        print(f"Agent execution failed: {e}")
        # Return 200 with error status so frontend handles it gracefully
        return {"status": "FAILED", "error": str(e)}


@app.get("/onboard/{thread_id}/status")
async def get_status(thread_id: str):
    """
    Get the current status of the onboarding session.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await graph.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        state_data = current_state.values

        # Determine status
        status = state_data.get("status", "IN_PROGRESS")
        # If the graph is interrupted (next node is present but stopped), it's waiting
        if current_state.next:
            # We are interrupted. Since we interrupt AFTER consultant, this is likely NEEDS_REVIEW.
            status = "NEEDS_REVIEW"
        elif not current_state.next and status != "COMPLETED":
            # If no next and not completed, maybe finished?
            pass

        return {
            "status": status,
            "stage": state_data.get("stage", "UNKNOWN"),
            "risk_score": state_data.get("risk_score", 0.0),
            "messages": [m.content for m in state_data.get("messages", [])],
            "consultant_plan": state_data.get("consultant_plan", []),
            "verification_notes": state_data.get("verification_notes", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/onboard/{thread_id}/resume")
async def resume_onboarding(thread_id: str, payload: ResumePayload):
    """
    Resumes the onboarding process after merchant intervention.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = await graph.aget_state(config)

        if not current_state:
            raise HTTPException(status_code=404, detail="Session not found")

        # 1. Update State with new data (if any)
        if payload.updated_data:
            # Deep merge logic simplifed for demo
            # We assume we are updating 'application_data'
            # In a real app we'd need careful partial updates.
            # Using update_state to patch
            await graph.aupdate_state(
                config, {"application_data": payload.updated_data}
            )  # This appends to history

        # 2. Resume execution
        # We simply invoke with None to continue from interrupt
        # Because we looped Consultant -> Input Parser, simply resuming moves to Input Parser

        final_state = await graph.ainvoke(None, config=config)

        return {"status": "RESUMED", "result": final_state}

    except Exception as e:
        print(f"Resume failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
