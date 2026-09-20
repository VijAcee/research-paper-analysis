import requests
import json

BASE_URL = "http://localhost:8000"

def test_compare_endpoint():
    print("Testing /api/compare with 5 paper IDs including local/missing ones...")
    payload = {
        "paper_ids": [
            "6aae4f3bf43ae51eaeed16c3",
            "6aae4f3bf43ae51eaeed16c4",
            "6aae4f3bf43ae51eaeed16c5",
            "6aae4f3bf43ae51eaeed16c6",
            "6aae4f3bf43ae51eaeed16c7"
        ],
        "papers": [
            {"id": "6aae4f3bf43ae51eaeed16c3", "title": "Economics of BitCoin Price Formation", "year": 2026, "authors": ["d'Artis Kancs"]},
            {"id": "6aae4f3bf43ae51eaeed16c4", "title": "Red Flag: Sexual Violence Risk Perception", "year": 2026, "authors": ["Megan Korovich"]},
            {"id": "6aae4f3bf43ae51eaeed16c5", "title": "Think globally, measure locally", "year": 2026, "authors": ["Think globally"]},
            {"id": "6aae4f3bf43ae51eaeed16c6", "title": "The Environmental Data Initiative", "year": 2026, "authors": ["RESEARCH ARTICLE"]},
            {"id": "6aae4f3bf43ae51eaeed16c7", "title": "The feasibility of the PAM intervention", "year": 2026, "authors": ["Aikaterini Kassavou"]}
        ]
    }
    
    res = requests.post(f"{BASE_URL}/api/compare", json=payload)
    print("Status Code:", res.status_code)
    if res.status_code == 200:
        data = res.json()
        print("Success! Title:", data.get("title"))
        print("Matrix rows count:", len(data.get("matrix", [])))
        print("Report length:", len(data.get("detailed_analysis", "")))
    else:
        print("Error Response:", res.text)

if __name__ == "__main__":
    test_compare_endpoint()
