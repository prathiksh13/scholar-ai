import traceback
import sys
import os

# Set environment
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth import get_current_user

    # Mocking the user to bypass authentication
    async def mock_get_current_user():
        return {"id": "test_user"}

    app.dependency_overrides[get_current_user] = mock_get_current_user

    client = TestClient(app, raise_server_exceptions=False)
    
    document_id = "0cbbd4f3-7135-448a-8c2e-ab4880c864e0"
    url = f"/formatflow/export/{document_id}?kind=pdf"
    print(f"Testing URL: {url}")
    
    response = client.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response Content-Type: {response.headers.get('content-type')}")
    
    if response.status_code == 500:
        print("--- 500 Internal Server Error Body ---")
        print(response.text)
        print("--------------------------------------")
    elif response.status_code == 200:
        print("Success! (First 50 bytes):", response.content[:50])
    else:
        print(f"Response Detail: {response.text}")

except Exception:
    print("--- Traceback started ---")
    traceback.print_exc()
    print("--- Traceback ended ---")
