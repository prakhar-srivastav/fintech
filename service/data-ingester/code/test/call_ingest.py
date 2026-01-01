import requests

url = "http://localhost:8000/sync"
headers = {"Content-Type": "application/json"}
data = {
    "payload": {
        "stocks": ["RELIANCE", "ZERODHA"],
        "start_date": "2025-12-19",
        "end_date": "2025-12-22",
        "exchanges": ["NSE", "BSE"],
        "granularity": "10minute"
    }
}

response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.text)