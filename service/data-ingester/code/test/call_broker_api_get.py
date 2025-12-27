import requests
import json

url = 'http://localhost:8080/api/data'
params = {
    'stocks': ['RELIANCE', 'TCS'],
    'start_date': '2025-01-19',
    'end_date': '2025-12-22',
    'exchanges': ['NSE', 'BSE'],
    'granularity': '5minute'
}

response = requests.get(url, params=params)
print(json.dumps(response.json(), indent=2))