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
from strategy_execution_runner import process_strategy_execution_job

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


def strategy_scheduler_poller():
    """
    Main poller loop that checks for pending strategy scheduler excution jobs
    and processes them.
    """
    logger.info("Starting strategy scheduler poller...")
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
    
    while True:
        try:
            # Fetch running strategy executions first
            running_result = db_client.get_strategy_execution_runs(status='running')
            running_jobs = running_result.get('runs', [])
            if running_jobs:
                logger.info(f"Found {len(running_jobs)} running strategy executions. Skipping new executions.")
                time.sleep(POLL_INTERVAL)
                continue
            
            # Fetch pending strategy scheduler jobs
            result = db_client.get_strategy_execution_runs(status='queued')
            pending_jobs = result.get('runs', [])
            logger.info(f"Found {len(pending_jobs)} pending strategy executions.")
            
            pending_job = pending_jobs[0] if pending_jobs else None
            if pending_job:
                execution_id = pending_job['id']
                logger.info(f"Processing strategy execution ID: {execution_id}")
                try:
                    db_client.change_strategy_execution_run_status(execution_id, 'running')
                    process_strategy_execution_job(execution_id)
                    logger.info(f"Completed strategy execution for execution ID: {execution_id}")
                except Exception as e:
                    logger.error(f"Error processing job {execution_id}: {e}")
                    db_client.change_strategy_execution_run_status(execution_id, 'failed')

        except Exception as e:
            logger.error(f"Error in strategy scheduler poller: {e}")

        # Sleep for a defined interval before checking again
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    strategy_scheduler_poller()