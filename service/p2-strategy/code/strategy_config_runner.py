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


def find_best_points(day_data: Dict[str, List[Dict[str, Any]]],
                      vertical_gap: float,
                      horizontal_gap: float,
                      continuous_days: int) -> List[Dict[str, Any]]:

    random_day = list(day_data.keys())[0]
    time_points = list(day_data[random_day].keys())

    incorrect_days = []
    for date, items in day_data.items():
        current_time_list = list(items.keys())
        if set(current_time_list) != set(time_points):
            incorrect_days.append(date)

    if incorrect_days:
        logger.warning(f"Inconsistent time points in days {incorrect_days}")

    for date in incorrect_days:
        del day_data[date]

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
            for day in range(len(day_data)):
                window.append({
                    'x_avg': (day_data[list(day_data.keys())[day]][time_points[x]]['high'] + day_data[list(day_data.keys())[day]][time_points[x]]['open'] + day_data[list(day_data.keys())[day]][time_points[x]]['close']) / 3,
                    'y_avg': (day_data[list(day_data.keys())[day]][time_points[y]]['low'] + day_data[list(day_data.keys())[day]][time_points[y]]['open'] + day_data[list(day_data.keys())[day]][time_points[y]]['close']) / 3
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
    scores.sort(key=lambda x: (x['exceeded'], x['average']), reverse=True)
    return scores


def find_best_points_for_symbol(symbol: str,
                               exchange: str,
                               vertical_gap: float,
                               horizontal_gap: float,
                               continuous_days: int,
                               start_date: str,
                               end_date: str,
                               granularity: str,
                               syncing_needed: bool):
    logger.info("Starting Strategy Runner")
    logger.info(f"Finding best points for {symbol} on {exchange}")
    
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

    points = find_best_points(day_data, 
    vertical_gap=vertical_gap, 
    horizontal_gap=horizontal_gap, 
    continuous_days=continuous_days)
    return points

NSE_NIFTY_50 = {
    "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports and SEZ",
    "APOLLOHOSP": "Apollo Hospitals",
    "ASIANPAINT": "Asian Paints",
    "AXISBANK": "Axis Bank",
    "BAJAJ-AUTO": "Bajaj Auto",
    "BAJFINANCE": "Bajaj Finance",
    "BAJAJFINSV": "Bajaj Finserv",
    "BEL": "Bharat Electronics",
    "BHARTIARTL": "Bharti Airtel",
    "CIPLA": "Cipla",
    "COALINDIA": "Coal India",
    "DRREDDY": "Dr Reddy's Laboratories",
    "EICHERMOT": "Eicher Motors",
    "GRASIM": "Grasim Industries",
    "HCLTECH": "HCL Technologies",
    "HDFCBANK": "HDFC Bank",
    "HDFCLIFE": "HDFC Life Insurance",
    "HINDALCO": "Hindalco Industries",
    "HINDUNILVR": "Hindustan Unilever",
    "ICICIBANK": "ICICI Bank",
    "ITC": "ITC",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "LT": "Larsen & Toubro",
    "M&M": "Mahindra & Mahindra",
    "MARUTI": "Maruti Suzuki",
    "NESTLEIND": "Nestle India",
    "NTPC": "NTPC",
    "ONGC": "ONGC",
    "POWERGRID": "Power Grid Corporation",
    "RELIANCE": "Reliance Industries",
    "SBILIFE": "SBI Life Insurance",
    "SBIN": "State Bank of India",
    "SHRIRAMFIN": "Shriram Finance",
    "SUNPHARMA": "Sun Pharmaceutical",
    "TCS": "Tata Consultancy Services",
    "TATACONSUM": "Tata Consumer Products",
    "TATAMOTORS": "Tata Motors",
    "TATASTEEL": "Tata Steel",
    "TECHM": "Tech Mahindra",
    "TITAN": "Titan Company",
    "TRENT": "Trent",
    "ULTRACEMCO": "UltraTech Cement",
    "WIPRO": "Wipro"
}

BSE_TOP_50 = {
    "RELIANCE": "Reliance Industries",
    "HDFCBANK": "HDFC Bank",
    "BHARTIARTL": "Bharti Airtel",
    "TCS": "Tata Consultancy Services",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "INFY": "Infosys",
    "BAJFINANCE": "Bajaj Finance",
    "HINDUNILVR": "Hindustan Unilever",
    "LICI": "Life Insurance Corporation of India",
    "ITC": "ITC",
    "MARUTI": "Maruti Suzuki",
    "HCLTECH": "HCL Technologies",
    "SUNPHARMA": "Sun Pharmaceutical",
    "AXISBANK": "Axis Bank",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "ULTRACEMCO": "UltraTech Cement",
    "BAJAJFINSV": "Bajaj Finserv",
    "NTPC": "NTPC",
    "TITAN": "Titan Company",
    "POWERGRID": "Power Grid Corporation",
    "ONGC": "ONGC",
    "ASIANPAINT": "Asian Paints",
    "ADANIENT": "Adani Enterprises",
    "ADANIPORTS": "Adani Ports and SEZ",
    "COALINDIA": "Coal India",
    "M&M": "Mahindra & Mahindra",
    "LT": "Larsen & Toubro",
    "NESTLEIND": "Nestle India",
    "TECHM": "Tech Mahindra"
}

def decorate_points(points: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Add metadata to each point"""
    for point in points:
        point.update(metadata)
    return points

def main():
    vertical_gap = [0.5,1,2]
    horizontal_gap = [2]
    continuous_days = [3,5,7,10]
    start_date, end_date = get_date_range()
    granularity = '3minute'
    master_data = []
    for symbol in NSE_NIFTY_50.keys():
        exchange = 'NSE'
        syncing_needed = True
        for v_gap in vertical_gap:
            for h_gap in horizontal_gap:
                for c_days in continuous_days:
                    logger.info(f"Evaluating {symbol} with v_gap={v_gap}, h_gap={h_gap}, c_days={c_days}")
                    points = find_best_points_for_symbol(symbol, exchange, vertical_gap=v_gap, horizontal_gap=h_gap, continuous_days=c_days, start_date=start_date, end_date=end_date, granularity=granularity, syncing_needed=syncing_needed)
                    logger.info(f"Top points for {symbol}: {points[:3]}")
                    syncing_needed = False  # Only sync once per symbol
                    points = decorate_points(points, {'exchange': exchange, 'symbol': symbol, 'vertical_gap': v_gap, 'horizontal_gap': h_gap, 'continuous_days': c_days})
                    master_data.extend(points)
    master_data.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)


# def process_strategy_scheduler_job(config: Dict[str, Any], strategy_id: str) -> str:
#     """
#     Process strategy scheduler job from the poller.
    
#     Expected config format (matching frontend API):
#     {
#         "vertical_gaps": [0.5, 1, 2],
#         "horizontal_gaps": [2],
#         "continuous_days": [3, 5, 7, 10],
#         "granularity": "3minute",
#         "start_date": "2025-10-11",
#         "end_date": "2026-01-10",
#         "nse_stocks": ["RELIANCE", "TCS"],
#         "bse_stocks": ["HDFCBANK"],
#     }
    
#     Returns:
#         str: The strategy_id (run_id) for the executed strategy
#     """
#     logger.info(f"Processing strategy scheduler job with config: {config}")
    
#     # Extract configuration with defaults
#     vertical_gaps = config.get('vertical_gaps', [0.5, 1, 2])
#     horizontal_gaps = config.get('horizontal_gaps', [2])
#     continuous_days_list = config.get('continuous_days', [3, 5, 7, 10])
#     granularity = config.get('granularity', '3minute')
#     start_date = config.get('start_date')
#     end_date = config.get('end_date')
#     nse_stocks = config.get('nse_stocks', [])
#     bse_stocks = config.get('bse_stocks', [])
    
#     # Use default dates if not provided
#     if not start_date or not end_date:
#         start_date, end_date = get_date_range()
    
#     # Initialize DB client
#     db_client = DBClient(DB_CONFIG)
    
#     # Create strategy run record
#     run_config = {
#         'vertical_gaps': vertical_gaps,
#         'horizontal_gaps': horizontal_gaps,
#         'continuous_days': continuous_days_list,
#         'granularity': granularity,
#         'start_date': start_date,
#         'end_date': end_date,
#         'nse_stocks': nse_stocks,
#         'bse_stocks': bse_stocks
#     }
    
    
#     master_data = []
#     total_combinations = (len(nse_stocks) + len(bse_stocks)) * len(vertical_gaps) * len(horizontal_gaps) * len(continuous_days_list)
#     processed = 0
    
#     try:
#         # Process NSE stocks
#         for symbol in nse_stocks:
#             exchange = 'NSE'
#             syncing_needed = True
            
#             for v_gap in vertical_gaps:
#                 for h_gap in horizontal_gaps:
#                     for c_days in continuous_days_list:
#                         processed += 1
#                         logger.info(f"[{processed}/{total_combinations}] Evaluating {symbol} ({exchange}) with v_gap={v_gap}, h_gap={h_gap}, c_days={c_days}")
                        
#                         try:
#                             points = find_best_points_for_symbol(
#                                 symbol=symbol,
#                                 exchange=exchange,
#                                 vertical_gap=v_gap,
#                                 horizontal_gap=h_gap,
#                                 continuous_days=c_days,
#                                 start_date=start_date,
#                                 end_date=end_date,
#                                 granularity=granularity,
#                                 syncing_needed=syncing_needed
#                             )
                            
#                             if points:
#                                 # Only take top result for this config
#                                 best_point = points[0]
#                                 best_point = decorate_points([best_point], {
#                                     'exchange': exchange,
#                                     'symbol': symbol,
#                                     'vertical_gap': v_gap,
#                                     'horizontal_gap': h_gap,
#                                     'continuous_days': c_days
#                                 })[0]
#                                 master_data.append(best_point)
#                                 logger.info(f"Top point for {symbol}: exceed_prob={best_point['exceed_prob']:.4f}, avg={best_point['average']:.4f}")
                            
#                             syncing_needed = False  # Only sync once per symbol
                            
#                         except Exception as e:
#                             logger.error(f"Error processing {symbol} ({exchange}): {e}")
#                             continue
        
#         # Process BSE stocks
#         for symbol in bse_stocks:
#             exchange = 'BSE'
#             syncing_needed = True
            
#             for v_gap in vertical_gaps:
#                 for h_gap in horizontal_gaps:
#                     for c_days in continuous_days_list:
#                         processed += 1
#                         logger.info(f"[{processed}/{total_combinations}] Evaluating {symbol} ({exchange}) with v_gap={v_gap}, h_gap={h_gap}, c_days={c_days}")
                        
#                         try:
#                             points = find_best_points_for_symbol(
#                                 symbol=symbol,
#                                 exchange=exchange,
#                                 vertical_gap=v_gap,
#                                 horizontal_gap=h_gap,
#                                 continuous_days=c_days,
#                                 start_date=start_date,
#                                 end_date=end_date,
#                                 granularity=granularity,
#                                 syncing_needed=syncing_needed
#                             )
                            
#                             if points:
#                                 # Only take top result for this config
#                                 best_point = points[0]
#                                 best_point = decorate_points([best_point], {
#                                     'exchange': exchange,
#                                     'symbol': symbol,
#                                     'vertical_gap': v_gap,
#                                     'horizontal_gap': h_gap,
#                                     'continuous_days': c_days
#                                 })[0]
#                                 master_data.append(best_point)
#                                 logger.info(f"Top point for {symbol}: exceed_prob={best_point['exceed_prob']:.4f}, avg={best_point['average']:.4f}")
                            
#                             syncing_needed = False  # Only sync once per symbol
                            
#                         except Exception as e:
#                             logger.error(f"Error processing {symbol} ({exchange}): {e}")
#                             continue
        
#         # Sort results by exceed_prob and average
#         master_data.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
        
#         # Save results to database
#         if master_data:
#             logger.info(f"Saving {len(master_data)} results to database...")
#             db_client.save_strategy_results(strategy_id, master_data)
#             logger.info(f"Results saved successfully for strategy {strategy_id}")
#         else:
#             logger.warning(f"No results to save for strategy {strategy_id}")
        
#     except Exception as e:
#         logger.error(f"Strategy execution error for {strategy_id}: {e}")
#         raise
    
#     return strategy_id

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
    }
    
    Returns:
        str: The strategy_id (run_id) for the executed strategy
    """
    logger.info(f"Processing strategy scheduler job with config: {config}")
    
    data_ingester_client = DataIngesterClient(base_url=DATA_INGESTER_URL, timeout=120)

    # Extract configuration with defaults
    vertical_gaps = config.get('vertical_gaps', [0.5, 1, 2])
    horizontal_gaps = config.get('horizontal_gaps', [2])
    continuous_days_list = config.get('continuous_days', [3, 5, 7, 10])
    granularity = config.get('granularity', '3minute')
    start_date = config.get('start_date')
    end_date = config.get('end_date')
    nse_stocks = config.get('nse_stocks', data_ingester_client.get_symbols(exchange='NSE'))
    bse_stocks = config.get('bse_stocks', [])

    # Use default dates if not provided
    if not start_date or not end_date:
        start_date, end_date = get_date_range()
    
    # Initialize DB client
    db_client = DBClient(DB_CONFIG)
    
    # Create strategy run record
    run_config = {
        'vertical_gaps': vertical_gaps,
        'horizontal_gaps': horizontal_gaps,
        'continuous_days': continuous_days_list,
        'granularity': granularity,
        'start_date': start_date,
        'end_date': end_date,
        'nse_stocks': nse_stocks,
        'bse_stocks': bse_stocks
    }
    
    
    master_data = []
    total_combinations = (len(nse_stocks) + len(bse_stocks)) * len(horizontal_gaps) * len(continuous_days_list)
    processed = 0
    
    try:

        for symbol in nse_stocks:
            exchange = 'NSE'
            syncing_needed = True
            for c_days in continuous_days_list:
                candidate_points = []
                for h_gap in horizontal_gaps:
                    processed += 1
                    logger.info(f"[{processed}/{total_combinations}] Evaluating {symbol} ({exchange}) with h_gap={h_gap}, c_days={c_days}")

                    l_vgap = 0
                    r_vgap = 200
                    max_itr = 100
                    threshold_prob = 0.8
                    best_point = None  # Track the best point found during binary search
                    best_valid_point = None  # Track the best point that meets threshold
                    
                    while r_vgap - l_vgap > 0.1 and max_itr > 0:
                        v_gap = (l_vgap + r_vgap) / 2
                        try:
                            points = find_best_points_for_symbol(
                                symbol=symbol,
                                exchange=exchange,
                                vertical_gap=v_gap,
                                horizontal_gap=h_gap,
                                continuous_days=c_days,
                                start_date=start_date,
                                end_date=end_date,
                                granularity=granularity,
                                syncing_needed=syncing_needed
                            )
                            
                            if points:
                                # Only take top result for this config
                                current_point = points[0]
                                current_point = decorate_points([current_point], {
                                    'exchange': exchange,
                                    'symbol': symbol,
                                    'vertical_gap': v_gap,
                                    'horizontal_gap': h_gap,
                                    'continuous_days': c_days
                                })[0]
                                best_point = current_point  # Track latest point
                                if current_point['exceed_prob'] >= threshold_prob:
                                    best_valid_point = current_point  # Save valid point
                                    l_vgap = v_gap  # Try higher v_gap
                                else:
                                    r_vgap = v_gap  # Try lower v_gap
                            syncing_needed = False  # Only sync once per symbol
                            max_itr -= 1
                        except Exception as e:
                            logger.error(f"Error processing {symbol} ({exchange}): {e}")
                            max_itr -= 1
                            continue
                    if best_valid_point:
                        candidate_points.append(best_valid_point)    
                candidate_points.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
                if len(candidate_points) > 0:
                    master_data.extend(candidate_points[:1])

        for symbol in bse_stocks:
            exchange = 'BSE'
            syncing_needed = True
            for c_days in continuous_days_list:
                candidate_points = []
                for h_gap in horizontal_gaps:
                    processed += 1
                    logger.info(f"[{processed}/{total_combinations}] Evaluating {symbol} ({exchange}) with h_gap={h_gap}, c_days={c_days}")

                    l_vgap = 0
                    r_vgap = 200
                    max_itr = 100
                    threshold_prob = 0.8
                    best_point = None  # Track the best point found during binary search
                    best_valid_point = None  # Track the best point that meets threshold
                    
                    while r_vgap - l_vgap > 0.1 and max_itr > 0:
                        v_gap = (l_vgap + r_vgap) / 2
                        try:
                            points = find_best_points_for_symbol(
                                symbol=symbol,
                                exchange=exchange,
                                vertical_gap=v_gap,
                                horizontal_gap=h_gap,
                                continuous_days=c_days,
                                start_date=start_date,
                                end_date=end_date,
                                granularity=granularity,
                                syncing_needed=syncing_needed
                            )
                            
                            if points:
                                # Only take top result for this config
                                current_point = points[0]
                                current_point = decorate_points([current_point], {
                                    'exchange': exchange,
                                    'symbol': symbol,
                                    'vertical_gap': v_gap,
                                    'horizontal_gap': h_gap,
                                    'continuous_days': c_days
                                })[0]
                                best_point = current_point  # Track latest point
                                if current_point['exceed_prob'] >= threshold_prob:
                                    best_valid_point = current_point  # Save valid point
                                    l_vgap = v_gap  # Try higher v_gap
                                else:
                                    r_vgap = v_gap  # Try lower v_gap
                            syncing_needed = False  # Only sync once per symbol
                            max_itr -= 1
                        except Exception as e:
                            logger.error(f"Error processing {symbol} ({exchange}): {e}")
                            max_itr -= 1
                            continue
                    if best_valid_point:
                        candidate_points.append(best_valid_point)    
                candidate_points.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
                if len(candidate_points) > 0:
                    master_data.extend(candidate_points[:1])

        # Sort results by exceed_prob and average
        master_data.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
        
        # Save results to database
        if master_data:
            logger.info(f"Saving {len(master_data)} results to database...")
            db_client.save_strategy_results(strategy_id, master_data)
            logger.info(f"Results saved successfully for strategy {strategy_id}")
        else:
            logger.warning(f"No results to save for strategy {strategy_id}")
        
    except Exception as e:
        logger.error(f"Strategy execution error for {strategy_id}: {e}")
        raise
    
    return strategy_id


if __name__ == '__main__':
    main()