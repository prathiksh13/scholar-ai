import traceback
from fastapi.testclient import TestClient
from app.main import app
from app.api.formatflow import router
import inspect

# Locate the export function
for route in router.routes:
    if "export" in route.path:
        print(f"Found route: {route.path} with functions {route.endpoint}")
        # Check for dependencies
        print(f"Dependencies: {route.dependencies}")

client = TestClient(app)
try:
    # Testing with an invalid UUID just to see if we can trigger a 500 or 404
    url = "/formatflow/export/00000000-0000-0000-0000-000000000000?kind=pdf"
    print(f"\nTesting Invalid UUID URL: {url}")
    response = client.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception:
    traceback.print_exc()
