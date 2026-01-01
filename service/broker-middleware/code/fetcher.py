from kiteconnect import KiteConnect
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from typing import List, Optional, Dict, Tuple
import sys
import requests
import re
import onetimepass as otp
from urllib.parse import urlparse, parse_qs
import logging

# Configure logging for Kubernetes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)


class KiteDataFetcher:
    
    EXCHANGES = ['NSE', 'BSE', 'NFO', 'CDS', 'BCD', 'MCX']
    ALLOWED_GRANULARITIES = ['minute', '3minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day', 'week']
    RATE_LIMIT_DELAY = 0.35
    MAX_DAYS_INTRADAY = 60

    def __init__(
        self, 
        api_key: str, 
        user_name: str,
        password: str,
        totp_key: str,
        api_secret: str,
        data_folder: str = 'data',
        granularity: str = '5minute',
    ):
        self.api_key = api_key
        self.user_name = user_name
        self.password = password
        self.totp_key = totp_key
        self.api_secret = api_secret
        self.data_folder = data_folder
        self.granularity = granularity
        self.exchanges = self.EXCHANGES
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.generate_access_token())
        
        self._instruments_cache: List[Dict] = []
    
    def test_connection(
        self) -> Dict:
        """Test connection to Kite API"""
        try:
            profile = self.kite.profile()
            return {
                'success': True,
                'user_name': profile['user_name'],
                'email': profile['email']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def generate_access_token(
        self) -> str:
        """Generate access token using login credentials and TOTP"""
        session = requests.Session()
        response = session.get(self.kite.login_url())
        # User login POST request
        login_payload = {
            "user_id": self.user_name,
            "password": self.password,
        }
        login_response = session.post("https://kite.zerodha.com/api/login", login_payload)
        # TOTP POST request
        totp_payload = {
            "user_id": self.user_name,
            "request_id": login_response.json()["data"]["request_id"],
            "twofa_value": otp.get_totp(self.totp_key),
            "twofa_type": "totp",
            "skip_session": True,
        }
        totp_response = session.post("https://kite.zerodha.com/api/twofa", totp_payload)
        # Extract request token from redirect URL
        try:
            response = session.get(self.kite.login_url())
            if "request_token=" in response.url:
                parsed_url = urlparse(response.url)
                request_token = parse_qs(parsed_url.query)["request_token"][0]
        except Exception as e:
            err_str = str(e)
            request_token = err_str.split("request_token=")[1].split(" ")[0]
            if "&" in request_token:
                request_token = request_token.split("&")[0]
        kite = KiteConnect(api_key=self.api_key)
        time.sleep(1)
        data = kite.generate_session(request_token, api_secret=self.api_secret)

        return data["access_token"]

    def fetch_instrument_from_exchange(
        self, 
        exchange: str
    ) -> List[Dict]:
        """Fetch instruments from a specific exchange"""
        try:
            instruments = self.kite.instruments(exchange)
            return instruments
        except Exception as e:
            print(f"Error fetching {exchange}: {e}")
            return []

    def fetch_all_instruments(self) -> List[Dict]:
        """Fetch all available instruments"""
        if self._instruments_cache:
            return self._instruments_cache
        
        all_instruments = []
        for exchange in self.exchanges:
            instruments = self.fetch_instrument_from_exchange(exchange)
            all_instruments.extend(instruments)
        
        self._instruments_cache = all_instruments
        return all_instruments
    
    def fetch_historical_data(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = '5minute'
    ) -> List[Dict]:
        """Fetch historical data with automatic chunking"""
        try:
            date_diff = (to_date - from_date).days
            
            if date_diff <= self.MAX_DAYS_INTRADAY:
                data = self.kite.historical_data(
                    instrument_token=instrument_token,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval
                )
                time.sleep(self.RATE_LIMIT_DELAY)
                return data
            else:
                all_data = []
                current_start = from_date
                
                while current_start < to_date:
                    current_end = min(
                        current_start + timedelta(days=self.MAX_DAYS_INTRADAY), 
                        to_date
                    )
                    
                    chunk_data = self.kite.historical_data(
                        instrument_token=instrument_token,
                        from_date=current_start,
                        to_date=current_end,
                        interval=interval
                    )
                    
                    if chunk_data:
                        all_data.extend(chunk_data)
                    
                    time.sleep(self.RATE_LIMIT_DELAY)
                    current_start = current_end + timedelta(days=1)
                
                return all_data
                
        except Exception as e:
            return []
    
    def save_to_csv(
        self, 
        symbol: str, 
        data: List[Dict], 
        exchange: str
    ) -> bool:
        """Save stock data to CSV file"""
        if not data:
            return False
        
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
        
        df = pd.DataFrame(data)
        filename = f"{self.data_folder}/{symbol}_{exchange}_{int(time.time())}.csv"
        df.to_csv(filename, index=False)
        return True
    
    def fetch_stock_data(
        self,
        stocks: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Main method to fetch stock data"""
        
        to_date = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
        from_date = datetime.strptime(start_date, '%Y-%m-%d') if start_date else datetime(2025, 1, 1)
        target_exchanges = exchanges or self.exchanges
        exchange_data = {} 
        for ex in target_exchanges:
            exchange_data[ex] = self.fetch_instrument_from_exchange(ex)
        stats = self._fetch_stocks(
            stocks, 
            exchange_data, 
            from_date, 
            to_date
        )
        return stats
    
    def fetch_stock_data_with_retries(
        self,
        stocks: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exchanges: Optional[List[str]] = None,
        max_retries: int = 2
    ) -> Dict[str, int]:
        """Fetch stock data with retries on failure"""
        attempt = 0
        while attempt < max_retries:
            try:
                result = self.fetch_stock_data(
                    stocks=stocks,
                    start_date=start_date,
                    end_date=end_date,
                    exchanges=exchanges
                )
                return result
            except Exception as e:
                logger.error(f"Error fetching stock data (attempt {attempt + 1}): {e}")
            finally:
                attempt += 1
                time.sleep(2 ** attempt)
                if attempt < max_retries:
                    logger.info("Refreshing access token and retrying...")
                    self.kite.set_access_token(self.generate_access_token())

        return {'error': 'Max retries reached'}
    
    def _fetch_stocks(
        self,
        stock_list: List[str],
        exchange_data: Dict[str, List[Tuple[int, str]]],
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, int]:
        """Fetch data for all stocks in the list"""
        successful = 0
        failed = 0
        not_found = 0
        data_map = {}
        stock_map = {}
        stock_set = set()

        for exchange, instruments in exchange_data.items():
            for inst in instruments:
                symbol = inst['tradingsymbol']
                token = inst['instrument_token']
                if symbol not in stock_map:
                    stock_map[symbol] = []
                stock_map[symbol].append((token, exchange))
                stock_set.add(symbol)

        if not stock_list:
            stock_list = list(stock_set)

        data_map = []
        for symbol in stock_list:
            found_any = False
            for token, exchange in stock_map.get(symbol, []):
                current_data = self.fetch_historical_data(token, from_date, to_date, self.granularity)
                if current_data:
                    found_any = True
                    data_map.append({
                        'rows': current_data,
                        'exchange': exchange,
                        'granularity': self.granularity,
                    })
                    self.save_to_csv(symbol, current_data, exchange) 
                if found_any:
                    successful += 1
                else:
                    failed += 1

        return {
            'successful': successful,
            'failed': failed,
            'not_found': not_found,
            'total': len(stock_list),
            'items': data_map,
        }