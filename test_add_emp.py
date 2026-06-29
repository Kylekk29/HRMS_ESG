import requests
r = requests.post("http://localhost:8000/api/employees", json={
    "employee_id": "TEST001",
    "full_name": "Test User",
    "department": "Engineering"
})
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
