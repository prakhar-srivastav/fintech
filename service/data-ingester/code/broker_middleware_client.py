import requests
import json
from datetime import datetime, timedelta

class BrokerMiddlewareClient:
    def __init__(self, base_url='http://localhost:8080'):
        self.base_url = base_url
    
    def check_status(self):
        """Check API status"""
        response = requests.get(f'{self.base_url}/api/status')
        return response.json()
    
    def fetch_data(self, stocks=None, start_date=None, end_date=None, 
                   exchanges=None, granularity='5minute'):
        """Fetch stock data"""
        params = {
            "stocks": stocks,
            "start_date": start_date,
            "end_date": end_date,
            "exchanges": exchanges,
            "granularity": granularity
        }
        response = requests.get(f'{self.base_url}/api/data', params=params)
        return response.json()
    
    def get_exchanges(self):
        """Get available exchanges"""
        response = requests.get(f'{self.base_url}/api/exchanges')
        return response.json()
    
    def get_granularities(self):
        """Get available granularities"""
        response = requests.get(f'{self.base_url}/api/granularities')
        return response.json()
    
    def get_symbols(self, exchange=None):
        """Get symbols for an exchange or all symbols"""
        if exchange:
            url = f'{self.base_url}/api/symbols/{exchange}'
        else:
            url = f'{self.base_url}/api/symbols'
        response = requests.get(url)
        return response.json()
