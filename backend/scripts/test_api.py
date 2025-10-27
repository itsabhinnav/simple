import requests
import json

print("Testing backend API...")
print("\n1. Testing health endpoint:")
response = requests.get("http://localhost:5000/health")
print(f"   Status: {response.status_code}")
print(f"   Response: {response.text}")

print("\n2. Testing requirements endpoint:")
response = requests.get("http://localhost:5000/api/requirements")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Success: {data.get('success')}")
    print(f"   Count: {data.get('count')}")
    print(f"   Data length: {len(data.get('data', []))}")
    print(f"   First requirement:")
    if data.get('data') and len(data['data']) > 0:
        print(f"      ID: {data['data'][0].get('id')}")
        print(f"      Requirement ID: {data['data'][0].get('requirement_id')}")
        print(f"      Title: {data['data'][0].get('title')}")
    print("\n   Full response (first item):")
    print(json.dumps(data.get('data', [])[0] if data.get('data') else {}, indent=2))
else:
    print(f"   Error: {response.text}")

