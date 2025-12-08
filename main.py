from fastapi import FastAPI, HTTPException
from schema import MerchantApplication
from agent_graph import graph
import uvicorn

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
        # Invoke the LangGraph agent
        final_state = await graph.ainvoke(initial_state)

        # Determine final status
        status = "COMPLETED"
        if final_state.get("error_message"):
            status = "NEEDS_REVIEW"

        return {
            "status": status,
            "merchant_id": application.business_details.pan,  # simple ID
            "result": final_state,
        }

    except Exception as e:
        print(f"Agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
