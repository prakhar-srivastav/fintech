import requests
from io import StringIO
import pandas as pd

api_key    = 'ljz7f8iqzy7ppkti'
api_secret = '4ja9g1nkpdybepocuu1v0kgv4mzu9ka9'

def get_symbols():
    url = "https://api.kite.trade/instruments"
    headers = {
    "X-Kite-Version": "3",
    "Authorization": f"token {api_key}:{api_secret}"  # Replace with your actual API key and access token
    }
    response = requests.get(url, headers=headers)
    import pdb; pdb.set_trace()
    df = pd.read_csv(StringIO(response.text), header=None, low_memory=False)
    df.to_csv('symbols.csv')
    return response

def get_symbols_historical_data(symbol):
    # https://api.kite.trade/instruments/historical/5633/minute?from=2017-12-15+09:15:00&to=2017-12-15+09:20:00"

    url = f"https://api.kite.trade/instruments/historical/{symbol}/minute"
    params = {
        "from": "2025-2-15 09:15:00",
        "to": "2025-4-15 09:20:00",
    }
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{api_secret}"
    }
    response = requests.get(url, headers=headers, params=params)
    return response

jio = '5633'
# response = get_symbols_historical_data(jio)
response = get_symbols_historical_data(jio)
import pdb; pdb.set_trace()