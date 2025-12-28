import requests

url = "http://localhost:8000/sync"
headers = {"Content-Type": "application/json"}
data = {
    "payload": {
        "stocks": ["RELIANCE"],
        "start_date": "2025-12-19",
        "end_date": "2025-12-22",
        "exchanges": ["BSE"],
        "granularity": "10minute"
    }
}

response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.text)