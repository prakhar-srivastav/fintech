import os
import logging
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import time
logger = logging.getLogger(__name__)

class DataIngesterClient:
    
    def __init__(self, 
                base_url: str,
                timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

    def _make_request(self,
                    method: str,
                    endpoint: str, 
                    data: Optional[Dict] = None, 
                    params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            else:
                return {'error': f'Unsupported method: {method}'}
            
            logger.info(f"Response status code: {response.status_code}")
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Request to {url} timed out")
            return {'error': 'Request timed out', 'status': 'timeout'}
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to data ingester at {url}")
            return {'error': 'Connection failed', 'status': 'connection_error'}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from data ingester: {e}")
            return {'error': str(e), 'status': 'http_error'}
        except Exception as e:
            logger.error(f"Error calling data ingester: {e}")
            return {'error': str(e), 'status': 'error'}
    
    def get_exchanges(self) -> Dict[str, Any]:
        """
        Get list of available exchanges.
        """
        logger.info("Fetching available exchanges")
        return self._make_request('GET', '/exchanges')
    
    def get_symbols(self, exchange: Optional[str] = None) -> Dict[str, Any]:
        """
        Get list of available symbols/stocks.
        """
        logger.info(f"Fetching symbols for exchange: {exchange or 'all'}")
        params = {}
        if exchange:
            params['exchange'] = exchange
        return self._make_request('GET', '/symbols', params=params)
    
    def get_granularities(self) -> Dict[str, Any]:
        """
        Get list of available granularities.
        """
        logger.info("Fetching available granularities")
        return self._make_request('GET', '/granularities')

    def sync_stocks(self,
        stocks: List[str],
        exchanges: List[str],
        granularity: str = '5minute',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        retry: int = 3
    ) -> Dict[str, Any]:
        """
        Trigger sync for specified stocks.
        """
        data = {
            "payload": {
                "stocks": stocks,
                "exchanges": exchanges,
                "granularity": granularity,
                "start_date": start_date,
                "end_date": end_date
            }
        }
        logger.info(f"Triggering sync for stocks: {stocks} on exchanges: {exchanges}")
        for attempt in range(1, retry + 1):
            _request = self._make_request('POST', '/sync', data=data)
            if 'error' in _request:
                logger.error(f"Sync failed: {_request['error']}")
                if attempt < retry:
                    logger.info(f"Retrying sync... ({retry - attempt} attempts left)")
                    time.sleep(2)
                    continue
            return _request

_ingester_client = None

def get_ingester_client() -> DataIngesterClient:
    """Get singleton data ingester client instance"""
    global _ingester_client
    if _ingester_client is None:
        _ingester_client = DataIngesterClient()
    return _ingester_client
    
