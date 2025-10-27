import requests

# Test with and without authentication
print("Testing API with different configurations...\n")

headers = {
    'Content-Type': 'application/json'
}

response = requests.get("http://localhost:5000/api/requirements", headers=headers)
print(f"GET /api/requirements:")
print(f"  Status: {response.status_code}")
print(f"  Content-Type: {response.headers.get('Content-Type')}")
try:
    data = response.json()
    print(f"  Response: {data}")
except:
    print(f"  Response text: {response.text}")

if data.get('data'):
    print(f"\nFirst requirement keys: {list(data['data'][0].keys())}")

