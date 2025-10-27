import requests
import json

response = requests.get("http://localhost:5000/api/requirements")
if response.status_code == 200:
    data = response.json()
    print(f"Total requirements: {data.get('count', len(data.get('data', [])))}")
    requirements = data.get('data', [])
    print(f"\nFirst 5 requirements:")
    for i, req in enumerate(requirements[:5], 1):
        print(f"\n{i}. {req.get('requirement_id')}")
        print(f"   Title: {req.get('title')}")
        print(f"   Priority: {req.get('priority')}")
        print(f"   Status: {req.get('status')}")
else:
    print(f"Error: {response.status_code}")

