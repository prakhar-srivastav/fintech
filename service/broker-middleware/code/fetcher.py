from kiteconnect import KiteConnect
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from typing import List, Optional, Dict, Tuple
import sys

class KiteDataFetcher:
    """A class to fetch stock data from Kite Connect API"""
    
    EXCHANGES = ['NSE', 'BSE', 'NFO', 'CDS', 'BCD', 'MCX']
    MAX_DAYS_INTRADAY = 60
    RATE_LIMIT_DELAY = 0.35
    
    def __init__(
        self, 
        api_key: str, 
        access_token: str,
        data_folder: str = 'data',
        granularity: str = '5minute',
        exchanges: Optional[List[str]] = None
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.data_folder = data_folder
        self.granularity = granularity
        self.exchanges = exchanges or self.EXCHANGES
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        self._instruments_cache: List[Dict] = []
    
    def test_connection(self) -> Dict:
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
    
    def get_instrument_token(
        self, 
        symbol: str, 
        instruments: List[Dict], 
        exchange: Optional[str] = None
    ) -> Tuple[Optional[int], Optional[str]]:
        """Get instrument token for a symbol"""
        if exchange:
            for inst in instruments:
                if inst['tradingsymbol'] == symbol and inst['exchange'] == exchange:
                    return inst['instrument_token'], inst['exchange']
        
        for preferred_exchange in ['NSE', 'BSE']:
            for inst in instruments:
                if inst['tradingsymbol'] == symbol and inst['exchange'] == preferred_exchange:
                    return inst['instrument_token'], inst['exchange']
        
        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token'], inst['exchange']
        
        return None, None
    
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
        all_instruments = self.fetch_all_instruments()
        
        if not all_instruments:
            return {'error': 'Failed to fetch instruments'}
        
        if not stocks:
            stock_map = self._build_stock_map(all_instruments, target_exchanges)
            stock_list = list(stock_map.keys())
        else:
            stock_list = stocks
            stock_map = None
        
        stats = self._fetch_stocks(
            stock_list, 
            stock_map, 
            all_instruments, 
            from_date, 
            to_date
        )
        
        return stats
    
    def _build_stock_map(
        self, 
        instruments: List[Dict], 
        exchanges: List[str]
    ) -> Dict[str, List[Tuple[int, str]]]:
        """Build a map of symbols to (token, exchange) tuples"""
        stock_map = {}
        for inst in instruments:
            if inst['exchange'] in exchanges:
                symbol = inst['tradingsymbol']
                token = inst['instrument_token']
                exchange = inst['exchange']
                
                if symbol not in stock_map:
                    stock_map[symbol] = []
                stock_map[symbol].append((token, exchange))
        
        return stock_map
    
    def _fetch_stocks(
        self,
        stock_list: List[str],
        stock_map: Optional[Dict],
        all_instruments: List[Dict],
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, int]:
        """Fetch data for all stocks in the list"""
        successful = 0
        failed = 0
        not_found = 0
        data_map = {}
        for symbol in stock_list:
            if stock_map and symbol in stock_map:
                found_any = False
                for token, exchange in stock_map[symbol]:
                    data = self.fetch_historical_data(token, from_date, to_date, self.granularity)
                    if data:
                        if self.save_to_csv(symbol, data, exchange):
                            found_any = True
                            data_map[symbol] = {
                            'data': data,
                            'exchange': exchange,
                            'granularity': self.granularity,
                            }

                if found_any:
                    successful += 1
                else:
                    failed += 1
            else:
                token, found_exchange = self.get_instrument_token(symbol, all_instruments)
                
                if not token:
                    not_found += 1
                    continue
                
                data = self.fetch_historical_data(token, from_date, to_date, self.granularity)
                
                if data:
                    if self.save_to_csv(symbol, data, found_exchange):
                        data_map[symbol] = {
                            'data': data,
                            'exchange': found_exchange,
                            'granularity': self.granularity,
                        }
                        successful += 1
                    else:
                        failed += 1
                else:
                    failed += 1
        
        
        return {
            'successful': successful,
            'failed': failed,
            'not_found': not_found,
            'total': len(stock_list),
            'data': data_map,
        }


def main():
    """Main entry point with CLI interface"""
    
    # Configuration
    API_KEY = os.environ.get('API_KEY')
    ACCESS_TOKEN = os.environ.get('ACCESS_TOKEN')
    
    # Create fetcher instance
    fetcher = KiteDataFetcher(
        api_key=API_KEY,
        access_token=ACCESS_TOKEN,
        data_folder='data',
        granularity='5minute'
    )
    
    # Test connection
    result = fetcher.test_connection()
    if result['success'] == False:
        print("Connection Failed")
        sys.exit(0)
    else:
        print("Connection Succesful")

    # Menu
    print("\n" + "=" * 70)
    print("CONFIGURATION OPTIONS:")
    print("=" * 70)
    print("1. Fetch specific stocks with date range")
    print("2. Fetch specific stocks (default dates: 2025-01-01 to today)")
    print("3. Fetch ALL stocks from ALL exchanges (⚠️  VERY LARGE!)")
    print("4. Fetch all stocks from specific exchange(s)")
    print("=" * 70)
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        stocks_input = input("\nEnter stock symbols (comma-separated): ").strip()
        start = input("Enter start date (YYYY-MM-DD) or Enter for default: ").strip()
        end = input("Enter end date (YYYY-MM-DD) or Enter for today: ").strip()
        
        stock_list = [s.strip().upper() for s in stocks_input.split(',')] if stocks_input else None
        
        fetcher.fetch_stock_data(
            stocks=stock_list,
            start_date=start or None,
            end_date=end or None
        )
    
    elif choice == "2":
        stocks_input = input("\nEnter stock symbols (comma-separated): ").strip()
        stock_list = [s.strip().upper() for s in stocks_input.split(',')] if stocks_input else None
        
        if stock_list:
            fetcher.fetch_stock_data(stocks=stock_list)
        else:
            print("❌ No stocks entered!")
    
    elif choice == "3":
        print("\n⚠️  WARNING: This will fetch ALL stocks from ALL exchanges")
        confirm = input("\nType 'YES' (all caps) to continue: ")
        
        if confirm == 'YES':
            fetcher.fetch_stock_data()
        else:
            print("❌ Cancelled.")
    
    elif choice == "4":
        print(f"\nAvailable exchanges: {', '.join(KiteDataFetcher.EXCHANGES)}")
        exchanges_input = input("Enter exchanges (comma-separated): ").strip()
        selected = [e.strip().upper() for e in exchanges_input.split(',')] if exchanges_input else None
        
        if selected:
            confirm = input(f"\nFetch from {', '.join(selected)}? Type 'yes': ")
            if confirm.lower() == 'yes':
                fetcher.fetch_stock_data(exchanges=selected)
        else:
            print("❌ No exchanges selected!")
    
    else:
        print("❌ Invalid choice!")
    
    print("\n✅ Done!\n")


if __name__ == "__main__":
    main()