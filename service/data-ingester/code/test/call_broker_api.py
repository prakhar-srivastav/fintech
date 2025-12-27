
import requests
import json

BROKER_MIDDLEWARE_URL = "http://localhost:8080"
url = f'{BROKER_MIDDLEWARE_URL}/api/data'
payload = {
    "stocks": ["RELIANCE"],
    "start_date": "2025-01-19",
    "end_date": "2025-12-22",
    "exchanges": ["NSE"],
    "granularity": "5minute"
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))