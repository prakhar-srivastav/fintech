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

from db_client import DBClient
from strategy_config_runner import process_strategy_scheduler_job


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


NSE_NIFTY_50 = [ "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "KOTAKBANK", "LT", "AXISBANK",]
BSE_TOP_50 = [ "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "KOTAKBANK", "LT", "AXISBANK",]

# Default configurations
DEFAULT_CONFIG = db_client.get_default_strategy_config()

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('index.html')

def get_date_range(days: int = 90):
    """Get date range for specified number of days"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


@app.route('/api/config', methods=['GET'])
def get_config():
    start_date, end_date = get_date_range()
    """Get default configuration"""
    config = {
        **DEFAULT_CONFIG,
        'available_nse_stocks': NSE_NIFTY_50,
        'available_bse_stocks': BSE_TOP_50,
        'start_date': start_date,
        'end_date': end_date,
    }
    return jsonify(config)


@app.route('/api/granularities', methods=['GET'])
def get_granularities():
    """Get available granularities"""
    granularities = db_client.get_granularities()
    return jsonify({'granularities': granularities})


@app.route('/api/schedule-strategy', methods=['POST'])
def schedule_strategy():
    """
    Schedule the P2 strategy with provided configuration.
    
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

        strategy_run_id = db_client.create_strategy_run(data)

        return jsonify({
            'status': 'success',
            'strategy_run_id': strategy_run_id,
        }), 200
        
    except Exception as e:
        logger.error(f"Strategy execution error: {e}")
        return jsonify({'status': 'failure',
                     'error': str(e)}), 500


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
        # Sort configs by vertical_gap descending
        symbol_data.sort(key=lambda x: (x.get('vertical_gap', 0), x.get('exceed_prob', 0)), reverse=True)

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

    # Sort by max vertical_gap
    symbol_scores.sort(key=lambda x: (x['vertical_gap'], x['exceed_prob']), reverse=True)

    return {
        'symbol_scores': symbol_scores,
        'total_symbols': len(by_symbol)
    }


# ============================================================================
# PREVIOUS RUNS
# ============================================================================

@app.route('/api/runs', methods=['GET'])
def get_strategy_runs():
    """
    Get list of previous strategy runs with pagination.
    For completed runs, includes summary info.
    
    Query params:
        - limit: Number of runs per page (default: 20)
        - offset: Number of runs to skip (default: 0)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        result = db_client.get_strategy_runs(limit=limit, offset=offset)
        
        for run in result.get('runs', []):
            if run.get('status') in ['completed', 'running']:
                try:
                    # Get quick summary stats
                    summary = generate_summary(run['id'])
                    run['summary'] = {
                        'total_symbols': summary.get('total_symbols', 0),
                        'top_symbol': summary['symbol_scores'][0]['symbol'] if summary.get('symbol_scores') else None,
                        'top_exceed_prob': summary['symbol_scores'][0]['exceed_prob'] if summary.get('symbol_scores') else None,
                        'top_exchange': summary['symbol_scores'][0]['exchange'] if summary.get('symbol_scores') else None,
                    }
                except Exception as e:
                    logger.warning(f"Could not generate summary for run {run['id']}: {e}")
                    run['summary'] = None
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching strategy runs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<strategy_id>/summary', methods=['GET'])
def get_run_summary(strategy_id):
    """
    Get summary statistics for a specific strategy run.
    Returns the same format as generate_summary for consistency.
    """
    try:
        summary = generate_summary(strategy_id)
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error fetching run summary: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# EXECUTION OF RUNS INSTANCE
# ============================================================================

@app.route('/api/runs/<strategy_id>/execute', methods=['POST'])
def execute_strategy_run(strategy_id):
    """
    Execute a specific strategy run instance by its ID.
    
    Expected payload:
    {
        "stimulate_mode": true/false,
        "total_money": 100000 (required if stimulate_mode is false),
        "selected_configs": [
            {"id": 123, "weight_percent": 25.5},
            {"id": 456, "weight_percent": 74.5}
        ]
    }
    """
    try:
        data = request.json
        stimulate_mode = data.get('stimulate_mode', True)
        total_money = data.get('total_money', None)
        selected_configs = data.get('selected_configs', [])
        
        # Validate: if not stimulate mode, total_money is required
        if not stimulate_mode and not total_money:
            return jsonify({
                'status': 'failure',
                'error': 'Total money is required when not in stimulate mode'
            }), 400
        
        # Validate: weight percentages should sum to ~100%
        if selected_configs:
            total_weight = sum(c.get('weight_percent', 0) for c in selected_configs)
            if abs(total_weight - 100) > 0.01:
                return jsonify({
                    'status': 'failure',
                    'error': f'Weight percentages must sum to 100% (current: {total_weight:.2f}%)'
                }), 400
        
        result = db_client.create_strategy_execution(
            strategy_id, 
            stimulate_mode=stimulate_mode,
            total_money=total_money,
            selected_configs=selected_configs
        )
        return jsonify({
            'status': 'success',
            'details': result
        }), 200
    except Exception as e:
        logger.error(f"Error executing strategy run {strategy_id}: {e}")
        return jsonify({'status': 'failure',
                     'error': str(e)}), 500


# ============================================================================
# EXECUTIONS TAB - View all executions and their details
# ============================================================================

@app.route('/api/executions', methods=['GET'])
def get_executions():
    """
    Get all strategy executions with pagination.
    
    Query params:
        - limit: Number of executions per page (default: 50)
        - offset: Number of executions to skip (default: 0)
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        result = db_client.get_all_strategy_executions(limit=limit, offset=offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching executions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/executions/<int:execution_id>', methods=['GET'])
def get_execution_details(execution_id):
    """
    Get full details of a specific execution including:
    - Execution info (status, total_money, stimulate_mode, etc.)
    - Strategy config from strategy_runs
    - All stock details with tasks and outputs
    - Daywise profit calculations
    """
    try:
        result = db_client.get_execution_full_details(execution_id)
        if not result:
            return jsonify({'error': 'Execution not found'}), 404
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching execution {execution_id}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)
