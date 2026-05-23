import requests
import json

print("Checking API requirements endpoint...")
response = requests.get("http://localhost:5000/api/requirements")

print(f"Status Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"\nResponse:")
print(json.dumps(response.json(), indent=2))









