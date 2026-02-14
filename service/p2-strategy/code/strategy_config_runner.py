#!/usr/bin/env python3

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from data_ingester_client import DataIngesterClient
from db_client import DBClient
from collections import deque
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_INGESTER_URL = os.environ.get('DATA_INGESTER_URL', 'http://localhost:8000')
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

TOP_100_NSE_STOCKS = [
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "ICICIBANK",
    "BHARTIARTL",
    "INFY",
    "SBIN",
    "ITC",
    "HINDUNILVR",
    "LT",
    "BAJFINANCE",
    "HCLTECH",
    "MARUTI",
    "AXISBANK",
    "SUNPHARMA",
    "KOTAKBANK",
    "TITAN",
    "ONGC",
    "TATAMOTORS",
    "ADANIENT",
    "NTPC",
    "ASIANPAINT",
    "POWERGRID",
    "M&M",
    "ULTRACEMCO",
    "TATASTEEL",
    "BAJAJFINSV",
    "COALINDIA",
    "HINDALCO",
    "WIPRO",
    "JSWSTEEL",
    "IOC",
    "ADANIPORTS",
    "NESTLEIND",
    "GRASIM",
    "TECHM",
    "BPCL",
    "DRREDDY",
    "DIVISLAB",
    "BRITANNIA",
    "CIPLA",
    "EICHERMOT",
    "APOLLOHOSP",
    "HEROMOTOCO",
    "TATACONSUM",
    "SBILIFE",
    "BAJAJ-AUTO",
    "HDFCLIFE",
    "INDUSINDBK",
    "GODREJCP",
    "DABUR",
    "ADANIGREEN",
    "VEDL",
    "PIDILITIND",
    "SIEMENS",
    "HAVELLS",
    "DLF",
    "BANKBARODA",
    "AMBUJACEM",
    "GAIL",
    "SHREECEM",
    "ICICIPRULI",
    "ICICIGI",
    "TRENT",
    "TORNTPHARM",
    "JINDALSTEL",
    "PFC",
    "RECLTD",
    "CHOLAFIN",
    "INDIGO",
    "BHEL",
    "ABB",
    "CANBK",
    "TATAPOWER",
    "HAL",
    "IRFC",
    "ADANIPOWER",
    "BEL",
    "MARICO",
    "PNB",
    "ZOMATO",
    "UNIONBANK",
    "IOB",
    "IDBI",
    "NHPC",
    "IRCTC",
    "POLYCAB",
    "PERSISTENT",
    "MAXHEALTH",
    "MPHASIS",
    "COLPAL",
    "NAUKRI",
    "BERGEPAINT",
    "AUROPHARMA",
    "LUPIN",
    "BOSCHLTD",
    "HDFCAMC",
    "MUTHOOTFIN",
    "SBICARD",
    "COFORGE",
]

def get_date_range():
    """Get default date range (last 3 months)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def sync_stock_data(ingester_client: DataIngesterClient, stocks: List[str], exchanges: List[str], granularity: str, start_date: str, end_date: str):
    """Sync stock data from broker"""
    logger.info(f"Syncing {len(stocks)} stocks from {exchanges} for {start_date} to {end_date}")
    
    result = ingester_client.sync_stocks(
        stocks=stocks,
        exchanges=exchanges,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date
    )
    
    if 'error' in result:
        logger.error(f"Sync failed: {result['error']}")
    else:
        logger.info(f"Sync completed: {result}")
    
    return result

def find_best_points(symbol_data: Dict[str, Dict[str, Dict[str, Any]]],
                      vertical_gap: float,
                      horizontal_gap: float,
                      continuous_days: int) -> List[Dict[str, Any]]:
    
    # Work on a copy to avoid modifying the original
    day_data = {k: v for k, v in symbol_data.items()}

    random_day = list(day_data.keys())[0]
    time_points = sorted(day_data[random_day].keys())

    incorrect_days = []
    for date, items in day_data.items():
        current_time_list = list(items.keys())
        if set(current_time_list) != set(time_points):
            incorrect_days.append(date)

    if incorrect_days:
        logger.warning(f"Inconsistent time points in days {incorrect_days}")

    for date in incorrect_days:
        del day_data[date]
    
    # Pre-compute sorted days list for efficiency
    sorted_days = sorted(day_data.keys())

    scores = []
    for x in range(len(time_points)):
        for y in range(len(time_points)):
            if y - x < horizontal_gap:
                continue
            exceeded = 0
            profit_days = 0
            total_count = 0

            window = deque(maxlen=continuous_days)
            window_sum = 0
            _average = 0
            _highest = 0
            _lowest = sys.maxsize
            _record = []
            for day_idx, day_key in enumerate(sorted_days):
                day_record = day_data[day_key]
                window.append({
                    'x_avg': day_record[time_points[x]]['open'],
                    'y_avg': day_record[time_points[y]]['open']
                })
                window_sum += (window[-1]['y_avg'] / window[-1]['x_avg'] - 1.0) * 100.0
                if window.maxlen == len(window):
                    if window_sum > vertical_gap:
                        exceeded += 1
                    if window_sum > 0:
                        profit_days += 1
                    _record.append(window_sum)
                    total_count += 1
                    _average += window_sum
                    _highest = max(_highest, window_sum)
                    _lowest = min(_lowest, window_sum)
                    removed = window.popleft()
                    window_sum -= (removed['y_avg'] / removed['x_avg'] - 1.0) * 100.0
            scores.append({
                'exceed_prob': exceeded / total_count,
                'profit_prob': profit_days / total_count,
                'exceeded': exceeded,
                'profit_days': profit_days,
                'average': _average / total_count,
                'total_count': total_count,
                'p5': sorted(_record)[int(0.05 * len(_record))],
                'p10': sorted(_record)[int(0.1 * len(_record))],
                'p20': sorted(_record)[int(0.2 * len(_record))],
                'p40': sorted(_record)[int(0.4 * len(_record))],
                'p50': sorted(_record)[int(0.5 * len(_record))],
                'x': time_points[x],
                'y': time_points[y],
                'highest': _highest,
                'lowest': _lowest
            })
    scores.sort(key=lambda x: x['exceed_prob'], reverse=True)
    return scores

def get_symbol_data(symbol: str, exchange: str, start_date: str, end_date: str, granularity: str, syncing_needed: bool = True):

    if syncing_needed:
        ingester_client = DataIngesterClient(base_url=DATA_INGESTER_URL, timeout=120)
        ingester_client.sync_stocks(
            stocks=[symbol],
            exchanges=[exchange],
            granularity=granularity,
            start_date=start_date,
            end_date=end_date
        )

    db_client = DBClient(DB_CONFIG)
    symbol_info = db_client.get_stock_data(
        stock=symbol,
        exchange=exchange,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        limit=None
        )
    day_data = {}       
    for data in symbol_info['data']['ohlc']:
        date, time = data['x'].split(' ')
        if date not in day_data:
            day_data[date] = {}
        day_data[date][time] = {
            'open': data['o'],
            'high': data['h'],
            'low': data['l'],
            'close': data['c']
        }
    return day_data

def decorate_points(points: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Add metadata to each point"""
    for point in points:
        point.update(metadata)
    return points

def process_stock_by_exchange(symbols: List[str],
                                exchange: str,
                                config: Dict[str, Any], 
                                strategy_id: str, 
                                db_client: DBClient, 
                                data_ingester_client: DataIngesterClient, 
                                threshold_prob: float, 
                                horizontal_gaps: List[float], 
                                continuous_days_list: List[int], 
                                start_date: str, 
                                end_date: str, 
                                granularity: str):
    master_data = []
    total_combinations = (len(symbols) * len(horizontal_gaps) * len(continuous_days_list))
    processed = 0
    rate_limiter = 0
    try:
        for symbol in symbols:
            syncing_needed = True
            logger.info(f"Processing symbol {symbol} on exchange {exchange}")
            symbol_data = get_symbol_data(symbol, exchange, start_date, end_date, granularity, syncing_needed)
            rate_limiter = (rate_limiter + 1) % 5
            if rate_limiter == 0:
                logger.info("Pausing for 5 seconds...")
                time.sleep(5)
            for c_days in continuous_days_list:
                logger.info(f"Processing {symbol} ({exchange}) with continuous_days={c_days}")
                candidate_points = []
                for h_gap in horizontal_gaps:
                    processed += 1
                    logger.info(f"[{processed}/{total_combinations}] Evaluating {symbol} ({exchange}) with h_gap={h_gap}, c_days={c_days}")
                    l_vgap = 0
                    r_vgap = 200
                    max_itr = 100
                    best_point = None
                    best_valid_point = None
                    
                    while r_vgap - l_vgap > 0.1 and max_itr > 0:
                        v_gap = (l_vgap + r_vgap) / 2
                        try:
                            points = find_best_points(
                                symbol_data=symbol_data,
                                vertical_gap=v_gap,
                                horizontal_gap=h_gap,
                                continuous_days=c_days)
                            if points:
                                best_point = points[0]
                                
                                for point in points:
                                    if point['exceed_prob'] >= threshold_prob:
                                        best_point = point if point['average'] > best_point['average'] else best_point
                                if best_point['exceed_prob'] >= threshold_prob:
                                    best_point = decorate_points([best_point], {
                                        'exchange': exchange,
                                        'symbol': symbol,
                                        'vertical_gap': v_gap,
                                        'horizontal_gap': h_gap,
                                        'continuous_days': c_days
                                    })[0]
                                    best_valid_point = best_point
                                    l_vgap = v_gap  # Try higher v_gap
                                else:
                                    r_vgap = v_gap  # Try lower v_gap
                            max_itr -= 1
                        except Exception as e:
                            logger.error(f"Error processing {symbol} ({exchange}): {e}")
                            max_itr -= 1
                            continue
                    if best_valid_point:
                        candidate_points.append(best_valid_point)
                candidate_points.sort(key=lambda x: x['vertical_gap'], reverse=True)
                if len(candidate_points) > 0:
                    master_data.extend(candidate_points[:1])
                if len(master_data) == 10:
                    logger.info(f"Processed {processed}/{total_combinations} combinations, pausing for 5 seconds...")
                    db_client.save_strategy_results(strategy_id, master_data)
                    master_data = []  # Clear master data after saving
                    logger.info(f"Saving {len(master_data)} results to database...")

        if master_data:
            logger.info(f"Saving remaining {len(master_data)} of {exchange} results to database...")
            db_client.save_strategy_results(strategy_id, master_data)

    except Exception as e:
        logger.error(f"Strategy execution error for {strategy_id}: {e}")
        raise
 

def process_strategy_scheduler_job(config: Dict[str, Any], strategy_id: str) -> str:
    """
    Process strategy scheduler job from the poller.
    
    Expected config format (matching frontend API):
    {
        "vertical_gaps": [0.5, 1, 2],
        "horizontal_gaps": [2],
        "continuous_days": [3, 5, 7, 10],
        "granularity": "3minute",
        "start_date": "2025-10-11",
        "end_date": "2026-01-10",
        "nse_stocks": ["RELIANCE", "TCS"],
        "bse_stocks": ["HDFCBANK"],
        "include_all_nse": false,
        "include_all_bse": false
    }
    
    Returns:
        str: The strategy_id (run_id) for the executed strategy
    """
    logger.info(f"Processing strategy scheduler job with config: {config}")
    
    data_ingester_client = DataIngesterClient(base_url=DATA_INGESTER_URL, timeout=120)
    db_client = DBClient(DB_CONFIG)

    # Extract configuration with defaults
    threshold_prob = config.get('threshold_prob', 0.8)
    horizontal_gaps = config.get('horizontal_gaps', [2])
    continuous_days_list = config.get('continuous_days', [3, 5, 7, 10])
    granularity = config.get('granularity', '3minute')
    start_date = config.get('start_date')
    end_date = config.get('end_date')
    
    # Handle "include all" flags - fetch all stocks from data ingester if enabled
    include_all_nse = config.get('include_all_nse', False)
    include_all_bse = config.get('include_all_bse', False)
    
    if include_all_nse:
        logger.info("Fetching all NSE stocks from data ingester...")
        # nse_symbols_response = data_ingester_client.get_symbols(exchange='NSE')
        # nse_stocks = nse_symbols_response['symbols']
        nse_stocks = TOP_100_NSE_STOCKS  # Use predefined top 100 list for NSE
        logger.info(f"Fetched {len(nse_stocks)} NSE stocks")
    else:
        nse_stocks = config.get('nse_stocks', [])
    
    if include_all_bse:
        logger.info("Fetching all BSE stocks from data ingester...")
        bse_symbols_response = data_ingester_client.get_symbols(exchange='BSE')
        bse_stocks = bse_symbols_response['symbols']
        logger.info(f"Fetched {len(bse_stocks)} BSE stocks")
    else:
        bse_stocks = config.get('bse_stocks', [])

    # Use default dates if not provided
    if not start_date or not end_date:
        start_date, end_date = get_date_range()

    process_stock_by_exchange(nse_stocks, 'NSE', config, strategy_id, db_client, data_ingester_client, threshold_prob, horizontal_gaps, continuous_days_list, start_date, end_date, granularity)
    process_stock_by_exchange(bse_stocks, 'BSE', config, strategy_id, db_client, data_ingester_client, threshold_prob, horizontal_gaps, continuous_days_list, start_date, end_date, granularity)

    return strategy_id

if __name__ == '__main__':
    # Example usage
    example_config = {
        "threshold_prob": 0.8,
        "horizontal_gaps": [2],
        "continuous_days": [3, 5, 7, 10],
        "granularity": "3minute",
        "start_date": "2025-10-11",
        "end_date": "2026-01-10",
        "nse_stocks": ["RELIANCE", "TCS"],
        "bse_stocks": [],
        "include_all_nse": False,
        "include_all_bse": False
    }
    strategy_id = f"strategy_{int(datetime.now().timestamp())}"
    process_strategy_scheduler_job(example_config, strategy_id)