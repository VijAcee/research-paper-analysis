import requests

url = "http://localhost:8000/api/papers/upload"
pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 120 >>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(Environmental Science: Foreign language learners and mobile device engagement in ecological studies.) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000216 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n386\n%%EOF\n"

files = {'file': ('2. Environmental Science.pdf', pdf_content, 'application/pdf')}

try:
    response = requests.post(url, files=files, timeout=30)
    print("STATUS CODE:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print("UPLOAD SUCCESSFUL!")
        print("Paper Title:", data.get("title"))
        print("Paper ID:", data.get("id"))
    else:
        print("ERROR RESPONSE:", response.text)
except Exception as e:
    print("UPLOAD FAILED WITH EXCEPTION:", str(e))
