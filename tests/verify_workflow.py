import requests
import time
import subprocess
import sys

# Sample Payload
PAYLOAD = {
    "merchant_id": "550e8400-e29b-41d4-a716-446655440000",  # Optional - UUID generated if not provided
    "business_details": {
        "pan": "ABCDE1234F",
        "entity_type": "Private Limited",
        "category": "E-commerce",
        "gstin": "22AAAAA0000A1Z5",
        "monthly_volume": "100000",
        "website_url": "http://example.com",  # Fails compliance
    },
    "bank_details": {
        "account_number": "1234567890",
        "ifsc": "HDFC0001234",
        "account_holder_name": "Test Merchant",
    },
    "signatory_details": {
        "name": "John Doe",
        "email": "john@example.com",
        "aadhaar": "123412341234",
    },
    "documents_path": "/Users/om.patil/Code/project-velocity/tests/sample_kyc.pdf",
}


def poll_for_completion(thread_id: str, max_wait: int = 120, poll_interval: int = 2):
    """
    Poll the status endpoint until the job completes or times out.
    
    Args:
        thread_id: The thread ID to poll
        max_wait: Maximum time to wait in seconds
        poll_interval: Time between polls in seconds
    
    Returns:
        Final status data or None if timed out
    """
    start_time = time.time()
    terminal_statuses = ["COMPLETED", "NEEDS_REVIEW", "FAILED"]
    
    print(f"Polling for status (max {max_wait}s)...")
    
    while time.time() - start_time < max_wait:
        try:
            r = requests.get(f"http://localhost:8000/onboard/{thread_id}/status")
            if r.status_code == 200:
                status_data = r.json()
                current_status = status_data.get("status")
                current_stage = status_data.get("stage", "UNKNOWN")
                
                print(f"  Status: {current_status} | Stage: {current_stage}")
                
                if current_status in terminal_statuses:
                    return status_data
            else:
                print(f"  Poll failed: {r.status_code}")
        except Exception as e:
            print(f"  Poll error: {e}")
        
        time.sleep(poll_interval)
    
    print("Polling timed out!")
    return None


def run_integration_test():
    print("Starting server...")
    server = subprocess.Popen(
        [sys.executable, "main.py"], stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    try:
        print("Waiting for server to be ready...")
        time.sleep(5)

        # 1. Start Onboarding (Now async - returns immediately)
        print("\n--- Step 1: Start Onboarding (Async) ---")
        r = requests.post("http://localhost:8000/onboard", json=PAYLOAD)
        data = r.json()
        print(f"Response: {data}")
        
        thread_id = data.get("thread_id")
        print(f"Status: {data.get('status')} | Thread ID: {thread_id}")
        
        if data.get("status") != "ACCEPTED":
            print("Error: Expected ACCEPTED status")
            return
            
        if not thread_id:
            print("Error: No thread ID returned.")
            return

        # 2. Poll for Completion (Long Polling)
        print("\n--- Step 2: Poll for Completion ---")
        final_status = poll_for_completion(thread_id, max_wait=120, poll_interval=3)
        
        if final_status:
            print("\n--- Final Status ---")
            print(f"Status: {final_status.get('status')}")
            print(f"Stage: {final_status.get('stage')}")
            print(f"Risk Score: {final_status.get('risk_score', 'N/A')}")
            print(f"Consultant Plan: {final_status.get('consultant_plan', [])}")
            print(f"Verification Notes: {final_status.get('verification_notes', [])}")
            print(f"Compliance Issues: {final_status.get('compliance_issues', [])}")
        else:
            print("Failed to get final status")
            return

        # 3. Resume (if NEEDS_REVIEW)
        if final_status.get("status") == "NEEDS_REVIEW":
            print("\n--- Step 3: Resume Onboarding (Async) ---")
            resume_payload = {
                "updated_data": {"note": "I fixed it (simulated)"},
                "user_message": "Please check again.",
            }
            r = requests.post(
                f"http://localhost:8000/onboard/{thread_id}/resume", json=resume_payload
            )

            if r.status_code == 200:
                resume_data = r.json()
                print(f"Resume Response: {resume_data}")
                
                # Poll for the resumed job to complete
                print("\n--- Step 4: Poll After Resume ---")
                resumed_status = poll_for_completion(thread_id, max_wait=120, poll_interval=3)
                
                if resumed_status:
                    print(f"\nFinal Status After Resume: {resumed_status.get('status')}")
            else:
                print(f"Resume Failed: {r.text}")
        
        # 4. Debug - List all jobs
        print("\n--- Debug: List All Jobs ---")
        r = requests.get("http://localhost:8000/debug/jobs")
        if r.status_code == 200:
            jobs_data = r.json()
            print(f"Active Jobs: {len(jobs_data.get('jobs', []))}")
            for job in jobs_data.get("jobs", []):
                print(f"  - {job['thread_id'][:8]}... | {job['status']} | {job['stage']}")

    finally:
        print("\nStopping server...")
        server.terminate()
        server.wait()


if __name__ == "__main__":
    run_integration_test()
