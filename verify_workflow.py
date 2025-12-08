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
        "website_url": "http://example.com",  # Safe test URL
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
    # Start the server in a separate process
    server = subprocess.Popen(
        [sys.executable, "main.py"], stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    try:
        # Wait for server to start
        print("Waiting for server to be ready...")
        time.sleep(5)

        # Test Health Check
        try:
            r = requests.get("http://localhost:8000/")
            print(f"Health Check: {r.status_code} {r.json()}")
            assert r.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            raise

        # Test Onboarding Flow
        print("Triggering Onboarding Flow...")
        r = requests.post("http://localhost:8000/onboard/start", json=PAYLOAD)

        if r.status_code == 200:
            data = r.json()
            print(f"Success! Status: {data['status']}")
            print("Final State Keys:", data["result"].keys())

            # Verify graph completion
            res = data["result"]
            if "verification_notes" in res:
                print("Verification Notes:", res["verification_notes"])

            # Example.com likely fails compliance check for refund policy etc.
            # So we expect "NEEDS_REVIEW" or compliance issues.
            if data["status"] == "NEEDS_REVIEW":
                print(
                    "Correctly identified partial compliance (Example.com has no refund policy)."
                )
            elif data["status"] == "COMPLETED":
                print("Completed flow.")

        else:
            print(f"Request failed: {r.status_code} {r.text}")

    finally:
        print("Stopping server...")
        server.terminate()
        server.wait()


if __name__ == "__main__":
    run_integration_test()
