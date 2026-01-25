#!/usr/bin/env python3
"""
Strategy Config Poller
Polls the database for scheduled strategy jobs and processes them.
"""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

from db_client import DBClient

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

# Polling interval in seconds
POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '60'))


def create_initial_task(strategy_result):
    task = {
        'execution_detail_id': strategy_result['execution_detail_id'],
        'timestamp_of_execution': strategy_result['x'],
        'day_of_execution': 0,
        'current_money': int(strategy_result['total_money'] * strategy_result['weight_percent'] / 100),
        'current_shares': 0,
        'price_during_order': None,
        'order_type': 'buy',
        'simulate_mode': strategy_result['simulate_mode'],
        'x': strategy_result['x'],
        'y': strategy_result['y'],
        'stock': strategy_result['stock'],
        'exchange': strategy_result['exchange'],
        'days_remaining': strategy_result.get('continuous_days', 0),
        'previous_task_id': -1,
        'status': 'queued',
        'executed_at': None,
        'error_message': None,
    }
    task_id = db_client.store_strategy_execution_task(task)
    return task_id

def process_strategy_execution_job(execution_id):
    logger.info(f"Processing strategy execution job: {execution_id}")

    execution_details = db_client.get_strategy_execution_data_by_id(execution_id)
    if not execution_details:
        logger.error(f"No execution details found for ID: {execution_id}")
        return

    strategy_id = execution_details['strategy_id']
    simulate_mode = execution_details['simulate_mode']
    total_money = execution_details['total_money'] if execution_details['total_money'] else 0
    
    strategy_result_details = db_client.get_strategy_execution_details(execution_id)
    
    strategy_results = []

    for current in strategy_result_details:
        execution_detail_id = current['id']
        strategy_result_id = current['strategy_result_id']
        logger.info(f"Processing strategy result ID: {strategy_result_id} for execution ID: {execution_id}")
        try:
            # current already contains joined data from strategy_results
            strategy_results.append({
                'execution_detail_id': execution_detail_id,
                'strategy_result_id': strategy_result_id,
                'weight_percent': current['weight_percent'],
                'simulate_mode': simulate_mode,
                'total_money': total_money,
                'stock': current['stock'],
                'exchange': current['exchange'],
                'x': current['x'],
                'y': current['y'],
                'continuous_days': current['continuous_days'],
                'exceed_prob': current['exceed_prob'],
                'average': current['average'],
            })
            logger.info(f"Completed strategy result ID: {strategy_result_id} for execution ID: {execution_id}")
        except Exception as e:
            logger.error(f"Error executing strategy result ID: {strategy_result_id} for execution ID: {execution_id}: {e}")
    
    tasks = []
    try:
        for strategy_result in strategy_results:
            task_id = create_initial_task(strategy_result)
            tasks.append(task_id)
            logger.info(f"Created initial task for strategy result ID: {strategy_result['strategy_result_id']} for execution ID: {execution_id}")
    except Exception as e:
        logger.error(f"Error processing trades for strategy result ID: {strategy_result['strategy_result_id']} for execution ID: {execution_id}: {e}")
    logger.info(f"All tasks created for execution ID: {execution_id}: {tasks}")
    return tasks

if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error("Usage: python strategy_execution_runner.py <execution_id>")
        sys.exit(1)
    
    execution_id = int(sys.argv[1])
    process_strategy_execution_job(execution_id)

