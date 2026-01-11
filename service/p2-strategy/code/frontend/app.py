#!/usr/bin/env python3
"""
P2 Strategy Frontend
Flask application for running and visualizing P2 strategy results.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from flask import Flask, render_template, jsonify, request
import json

# Add parent path to import strategy modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_strategy import (
    find_best_points_for_symbol,
    get_date_range,
    NSE_NIFTY_50,
    BSE_TOP_50,
    decorate_points
)
from db_client import DBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

# Initialize DB client
db_client = DBClient(DB_CONFIG)

# Default configurations
DEFAULT_CONFIG = {
    'vertical_gaps': [0.5, 1, 2],
    'horizontal_gaps': [1, 2],
    'continuous_days': [3, 5, 7, 10, 15, 20],
    'granularity': '3minute',
    'nse_stocks': list(NSE_NIFTY_50.keys()),
    'bse_stocks': list(BSE_TOP_50.keys())
}


@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get default configuration"""
    start_date, end_date = get_date_range()
    config = {
        **DEFAULT_CONFIG,
        'start_date': start_date,
        'end_date': end_date,
        'available_nse_stocks': NSE_NIFTY_50,
        'available_bse_stocks': BSE_TOP_50
    }
    return jsonify(config)


@app.route('/api/granularities', methods=['GET'])
def get_granularities():
    """Get available granularities"""
    granularities = ['1minute', '3minute', '5minute', '10minute', '15minute', '30minute', '60minute', 'day']
    return jsonify({'granularities': granularities})


@app.route('/api/run-strategy', methods=['POST'])
def run_strategy():
    """
    Run the P2 strategy with provided configuration.
    
    Expected payload:
    {
        "vertical_gaps": [0.5, 1, 2],
        "horizontal_gaps": [2],
        "continuous_days": [3, 5, 7, 10],
        "granularity": "3minute",
        "start_date": "2025-10-11",
        "end_date": "2026-01-10",
        "nse_stocks": ["RELIANCE", "TCS"],
        "bse_stocks": ["HDFCBANK"],
        "sync_data": true
    }
    """
    try:
        data = request.json
        
        # Extract configuration
        vertical_gaps = data.get('vertical_gaps', DEFAULT_CONFIG['vertical_gaps'])
        horizontal_gaps = data.get('horizontal_gaps', DEFAULT_CONFIG['horizontal_gaps'])
        continuous_days_list = data.get('continuous_days', DEFAULT_CONFIG['continuous_days'])
        granularity = data.get('granularity', DEFAULT_CONFIG['granularity'])
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        nse_stocks = data.get('nse_stocks', [])
        bse_stocks = data.get('bse_stocks', [])
        sync_data = data.get('sync_data', True)
        
        # Use default dates if not provided
        if not start_date or not end_date:
            start_date, end_date = get_date_range()
        
        logger.info(f"Running strategy with config: v_gaps={vertical_gaps}, h_gaps={horizontal_gaps}, "
                    f"c_days={continuous_days_list}, granularity={granularity}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"NSE stocks: {nse_stocks}, BSE stocks: {bse_stocks}")
        
        master_data = []
        total_combinations = (len(nse_stocks) + len(bse_stocks)) * len(vertical_gaps) * len(horizontal_gaps) * len(continuous_days_list)
        processed = 0
        
        # Process NSE stocks
        for symbol in nse_stocks:
            exchange = 'NSE'
            syncing_needed = sync_data
            
            for v_gap in vertical_gaps:
                for h_gap in horizontal_gaps:
                    for c_days in continuous_days_list:
                        try:
                            logger.info(f"Evaluating {symbol} ({exchange}) with v_gap={v_gap}, h_gap={h_gap}, c_days={c_days}")
                            
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
                            
                            syncing_needed = False  # Only sync once per symbol
                            
                            # Decorate and add top points
                            points = decorate_points(points, {
                                'exchange': exchange,
                                'symbol': symbol,
                                'vertical_gap': v_gap,
                                'horizontal_gap': h_gap,
                                'continuous_days': c_days
                            })
                            points.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
                            master_data.extend(points[:4])  # Keep top 4 per combination
                            processed += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing {symbol}: {e}")
                            processed += 1
                            continue
        
        # Process BSE stocks
        for symbol in bse_stocks:
            exchange = 'BSE'
            syncing_needed = sync_data
            
            for v_gap in vertical_gaps:
                for h_gap in horizontal_gaps:
                    for c_days in continuous_days_list:
                        try:
                            logger.info(f"Evaluating {symbol} ({exchange}) with v_gap={v_gap}, h_gap={h_gap}, c_days={c_days}")
                            
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
                            
                            syncing_needed = False
                            
                            points = decorate_points(points, {
                                'exchange': exchange,
                                'symbol': symbol,
                                'vertical_gap': v_gap,
                                'horizontal_gap': h_gap,
                                'continuous_days': c_days
                            })
                            points.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)
                            master_data.extend(points[:4])  # Keep top 4 per combination
                            processed += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing {symbol}: {e}")
                            processed += 1
                            continue
        
        # Sort by exceed probability
        master_data.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)

        # Generate unique strategy ID and save to database
        strategy_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            db_client.insert_strategy_results(master_data, strategy_id)
            logger.info(f"Saved {len(master_data)} results to database with strategy_id={strategy_id}")
        except Exception as db_error:
            logger.error(f"Failed to save results to database: {db_error}")
            # Continue anyway - results are still available in response

        # Generate summary statistics
        summary = generate_summary(strategy_id)
        
        return jsonify({
            'status': 'success',
            'strategy_id': strategy_id,
            'total_results': len(master_data),
            'top_results': master_data,  # Return top 50
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"Strategy execution error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


def generate_summary(strategy_id: str) -> Dict[str, Any]:
    """Generate summary statistics from results"""
    # Get all results (use large per_page to get all in one call)
    result = db_client.get_strategy_results(strategy_id, page=1, per_page=1000)
    data = result['results']
    
    by_symbol = {}
    for item in data:
        symbol = item['stock']
        if symbol not in by_symbol:
            by_symbol[symbol] = []
        by_symbol[symbol].append(item)
    
    # Find best performing symbols - group by symbol with max exceed as primary
    symbol_scores = []
    
    for symbol, symbol_data in by_symbol.items():
        # Sort configs by exceed_prob descending
        symbol_data.sort(key=lambda x: (x.get('exceed_prob', 0), x.get('average', 0)), reverse=True)

        # Get the best config
        best_config = symbol_data[0]
        max_exceed = best_config.get('exceed_prob', 0)
        
        # Get top 10 configs for this symbol (percentiles already in data)
        configs_with_percentiles = symbol_data
        
        symbol_scores.append({
            'symbol': symbol,
            'exchange': best_config.get('exchange', ''),
            'exceed_prob': round(max_exceed, 4),
            'average': best_config.get('average'),
            'x': best_config.get('x'),
            'y': best_config.get('y'),
            'vertical_gap': best_config.get('vertical_gap'),
            'horizontal_gap': best_config.get('horizontal_gap'),
            'continuous_days': best_config.get('continuous_days'),
            'p5': best_config.get('p5'),
            'p10': best_config.get('p10'),
            'p20': best_config.get('p20'),
            'p40': best_config.get('p40'),
            'p50': best_config.get('p50'),
            'total_configs': len(symbol_data),
            'configs': configs_with_percentiles  # All configs for this symbol
        })
    
    # Sort by max exceed_prob
    symbol_scores.sort(key=lambda x: (x['exceed_prob'], x['average']), reverse=True)

    return {
        'symbol_scores': symbol_scores,
        'total_symbols': len(by_symbol)
    }


# ============================================================================
# DATABASE-BACKED ENDPOINTS FOR PREVIOUS RUNS
# ============================================================================

@app.route('/api/runs', methods=['GET'])
def get_strategy_runs():
    """
    Get list of previous strategy runs with pagination.
    
    Query params:
        - limit: Number of runs per page (default: 20)
        - offset: Number of runs to skip (default: 0)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        result = db_client.get_strategy_runs(limit=limit, offset=offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching strategy runs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>', methods=['GET'])
def get_run_details(strategy_id):
    """
    Get details and results for a specific strategy run with pagination.
    
    Query params:
        - page: Page number (default: 1)
        - per_page: Results per page (default: 50)
        - stock: Filter by stock symbol (optional)
        - exchange: Filter by exchange (optional)
        - sort_by: Field to sort by (default: exceed_prob)
        - sort_order: 'asc' or 'desc' (default: desc)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        stock = request.args.get('stock')
        exchange = request.args.get('exchange')
        sort_by = request.args.get('sort_by', 'exceed_prob')
        sort_order = request.args.get('sort_order', 'desc')
        
        results = db_client.get_strategy_results(
            strategy_id=strategy_id,
            page=page,
            per_page=per_page,
            stock=stock,
            exchange=exchange,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error fetching run details: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>/summary', methods=['GET'])
def get_run_summary(strategy_id):
    """
    Get summary statistics for a specific strategy run.
    """
    try:
        summary = db_client.get_strategy_summary(strategy_id)
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error fetching run summary: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>/best-per-stock', methods=['GET'])
def get_best_per_stock(strategy_id):
    """
    Get the best result for each stock/exchange pair.
    Returns at most one entry per unique stock+exchange combination.
    
    Query params:
        - top_n: Number of best results per stock/exchange (default: 1)
    """
    try:
        top_n = request.args.get('top_n', 1, type=int)
        results = db_client.get_best_per_stock_exchange(strategy_id, top_n=top_n)
        return jsonify({
            'results': results,
            'total': len(results)
        })
    except Exception as e:
        logger.error(f"Error fetching best per stock: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>/stock/<stock>', methods=['GET'])
def get_stock_configs(strategy_id, stock):
    """
    Get top 4 configurations for a specific stock.
    
    Query params:
        - exchange: Filter by exchange (optional)
        - top_n: Number of top configs to return (default: 4)
    """
    try:
        exchange = request.args.get('exchange')
        top_n = request.args.get('top_n', 4, type=int)
        
        results = db_client.get_top_configs_per_stock(
            strategy_id=strategy_id,
            stock=stock,
            exchange=exchange,
            top_n=top_n
        )
        
        return jsonify({
            'stock': stock,
            'exchange': exchange,
            'configs': results,
            'total': len(results)
        })
    except Exception as e:
        logger.error(f"Error fetching stock configs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>/stocks', methods=['GET'])
def get_run_stocks(strategy_id):
    """
    Get list of unique stocks from a strategy run.
    """
    try:
        stocks = db_client.get_unique_stocks(strategy_id)
        return jsonify({'stocks': stocks})
    except Exception as e:
        logger.error(f"Error fetching stocks: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)
