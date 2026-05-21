import traceback
from fastapi.testclient import TestClient
from app.main import app
from app.auth import get_current_user

# Mocking the user to bypass authentication
async def mock_get_current_user():
    return {"id": "test_user"}

app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)
try:
    # Testing the document ID that supposedly causes issues
    document_id = "0cbbd4f3-7135-448a-8c2e-ab4880c864e0"
    url = f"/formatflow/export/{document_id}?kind=pdf"
    print(f"Testing URL: {url}")
    response = client.get(url)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 500:
        print("Response Body (JSON):", response.json() if response.headers.get("content-type") == "application/json" else response.text)
    elif response.status_code == 200:
        print("Success! (Partial Body):", response.text[:200])
    else:
        print(f"Response: {response.status_code} - {response.text}")

except Exception:
    print("An exception occurred during the request:")
    traceback.print_exc()
finally:
    app.dependency_overrides.clear()
