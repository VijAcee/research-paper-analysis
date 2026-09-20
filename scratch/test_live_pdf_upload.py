import os
import sys
import requests

backend_dir = r"c:\Users\welcome\Documents\vijita\projects\Research-Paper Analysis\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Create a small sample PDF text content for testing
sample_pdf_path = os.path.join(os.path.dirname(__file__), "sample_test_paper.pdf")

# Generate simple PDF bytes if not exists
if not os.path.exists(sample_pdf_path):
    with open(sample_pdf_path, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 210 >>\nstream\nBT /F1 12 Tf 50 700 Td (Efficacy of Metformin in Reducing HbA1c Levels in Patients with Type 2 Diabetes.) Tj 0 -20 Td (We conducted a 24-week double-blind randomized trial with N=150 patients.) Tj 0 -20 Td (1000mg metformin daily reduced HbA1c by 1.4% p < 0.001 compared to placebo.) Tj ET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000505 00000 n \ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n574\n%%EOF")

# Obtain auth token for testing
auth_url = "http://localhost:8000/api/auth/register"
token = ""
try:
    reg_res = requests.post(auth_url, json={"email": "test_user_upload@test.com", "password": "password123", "full_name": "Test User"})
    if reg_res.status_code == 200:
        token = reg_res.json().get("access_token")
    else:
        login_res = requests.post("http://localhost:8000/api/auth/login", json={"email": "test_user_upload@test.com", "password": "password123"})
        if login_res.status_code == 200:
            token = login_res.json().get("access_token")
except Exception as e:
    print("Auth error:", e)

# Test upload to live FastAPI server
url = "http://localhost:8000/api/papers/upload"
headers = {"Authorization": f"Bearer {token}"} if token else {}
with open(sample_pdf_path, "rb") as pdf_file:
    files = {"file": ("sample_test_paper.pdf", pdf_file, "application/pdf")}
    res = requests.post(url, files=files, headers=headers)

print("Status Code:", res.status_code)
if res.status_code == 200:
    data = res.json()
    print("Paper ID:", data.get("id"))
    print("Title Extracted:", data.get("title"))
    analysis = data.get("analysis", {})
    print("What Paper Is About:", analysis.get("what_is_paper_about"))
    print("Research Problem:", analysis.get("research_problem"))
    print("What Researchers Discovered:", analysis.get("what_researchers_discovered"))
else:
    print("Error:", res.text)
