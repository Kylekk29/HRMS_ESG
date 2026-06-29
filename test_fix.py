import requests
r = requests.get("http://localhost:8000/")
print(f"Page: {len(r.text)}B")
print(f"addEmpBtn: {'addEmpBtn' in r.text}")
print(f"Chart local: {'chart.min.js' in r.text}")
print(f"marked local: {'marked.min.js' in r.text}")
print(f"init wrapped: {'try {' in r.text}")

r2 = requests.get("http://localhost:8000/static/chart.min.js")
print(f"Chart.js served: {len(r2.text)}B, status={r2.status_code}")

r3 = requests.get("http://localhost:8000/static/marked.min.js")
print(f"marked served: {len(r3.text)}B, status={r3.status_code}")
