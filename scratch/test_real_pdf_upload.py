import requests

url = "http://localhost:8000/api/papers/upload/text"
payload = {
    "title": "Medical Science: Foreign Language Learners Study",
    "text": "Abstract: Foreign language learners frequently utilize mobile devices to support their learning activities outside the classroom. We conducted semi-structured interviews with foreign language learners to evaluate their experiences and behaviors. Participants reported using mobile devices for vocabulary acquisition and listening exercises, but effectiveness varied depending on individual goals."
}

try:
    response = requests.post(url, json=payload, timeout=30)
    print("STATUS CODE:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print("UPLOAD & ANALYSIS SUCCESSFUL!")
        print("Paper Title:", data.get("title"))
        print("Paper ID:", data.get("id"))
    else:
        print("ERROR RESPONSE:", response.text)
except Exception as e:
    print("UPLOAD FAILED WITH EXCEPTION:", str(e))
