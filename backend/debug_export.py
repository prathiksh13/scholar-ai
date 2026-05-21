import traceback
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
try:
    # Attempting the request without Auth first, as per instructions "only if the route rejects anonymous access"
    # The route is /formatflow/export/{id}?kind=pdf
    url = "/formatflow/export/0cbbd4f3-7135-448a-8c2e-ab4880c864e0?kind=pdf"
    print(f"Testing URL: {url}")
    response = client.get(url)
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response Body: {response.text[:500]}") # Print start of body
    except:
        print("Response Body is binary or cannot be printed")
    
    if response.status_code == 401 or response.status_code == 403:
         print("Access denied. A temporary Authorization header might be needed.")

except Exception:
    print("An exception occurred during the request:")
    traceback.print_exc()
