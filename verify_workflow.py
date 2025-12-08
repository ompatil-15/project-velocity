import requests
import time
import subprocess
import sys

# Sample Payload
PAYLOAD = {
    "api_key": "test_key",
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
}


def run_integration_test():
    print("Starting server...")
    server = subprocess.Popen(
        [sys.executable, "main.py"], stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    try:
        print("Waiting for server to be ready...")
        time.sleep(5)

        # 1. Start Onboarding
        print("\n--- Step 1: Start Onboarding (Expect NEED_REVIEW) ---")
        r = requests.post("http://localhost:8000/onboard/start", json=PAYLOAD)
        data = r.json()
        thread_id = data.get("thread_id")
        print(f"Status: {data.get('status')} | Thread ID: {thread_id}")

        # We expect it to finish the run and STOP at the interrupt (after consultant)
        # Because we await ainvoke, it returns the state AT the interrupt.
        # Check Consultant Plan
        res = data.get("result", {})
        print("Consultant Plan:", res.get("consultant_plan"))

        if not thread_id:
            print("Error: No thread ID returned.")
            return

        # 2. Check Status
        print("\n--- Step 2: Check Status ---")
        r = requests.get(f"http://localhost:8000/onboard/{thread_id}/status")
        status_data = r.json()
        print("Current Status:", status_data)

        # 3. Resume (Simulate Fix)
        # We don't actually change the URL in this test because example.com will always fail,
        # but we verify the RESUME mechanic works (it should re-run and fail again or proceed if we mocked it).
        # For this test, let's just see if it runs.
        print("\n--- Step 3: Resume Onboarding ---")
        resume_payload = {
            "updated_data": {"note": "I fixed it (simulated)"},
            "user_message": "Please check again.",
        }
        r = requests.post(
            f"http://localhost:8000/onboard/{thread_id}/resume", json=resume_payload
        )

        if r.status_code == 200:
            resume_data = r.json()
            print(f"Resume Response Status: {resume_data.get('status')}")
            print("It re-ran the check!")
        else:
            print(f"Resume Failed: {r.text}")

    finally:
        print("\nStopping server...")
        server.terminate()
        server.wait()


if __name__ == "__main__":
    run_integration_test()
