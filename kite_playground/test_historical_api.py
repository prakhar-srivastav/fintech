import requests
import pandas as pd
api_key    = 'ljz7f8iqzy7ppkti'
api_secret = '4ja9g1nkpdybepocuu1v0kgv4mzu9ka9'
request_token = 'JfjWjYTSptBfgJq3P2wvvyvKtZdgTd6j'
access_token = 'yN1o0qoSdRMB9VP1kIdp0Cthiw17tt3v'
df = pd.read_csv('symbols.csv')

count = 0
total = 0
datas = []
for i, row in df.iterrows():
    in_tk = row['instrument_token']
    url = "https://api.kite.trade/instruments/historical/4644609/minute"
    params = {
        "from": "2025-04-15 09:15:00",
        "to": "2025-06-13 09:20:00"
    }
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()['data']
    datas.append(len(data))
    print(response.status_code)
import pdb; pdb.set_trace()
    