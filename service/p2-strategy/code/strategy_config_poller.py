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

# Import strategy runner function
from strategy_config_runner import process_strategy_scheduler_job
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


def strategy_scheduler_poller():
    """
    Main poller loop that checks for pending strategy scheduler jobs
    and processes them.
    """
    logger.info("Starting strategy scheduler poller...")
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
    
    while True:
        try:
            # Fetch pending strategy scheduler jobs
            result = db_client.get_strategy_runs(status='queued')
            pending_jobs = result.get('runs', [])
            logger.info(f"Found {len(pending_jobs)} pending strategy runs.")
            
            for strategy in pending_jobs:
                strategy_id = strategy['id']
                config = strategy['config']
                logger.info(f"Processing strategy run ID: {strategy_id}")
                logger.info(f"Config: {config}")

                try:
                    # Process the strategy run
                    db_client.update_strategy_run_status(strategy_id, 'running')
                    process_strategy_scheduler_job(config, strategy_id)
                    
                    # Mark the job as completed
                    db_client.update_strategy_run_status(strategy_id, 'completed')
                    logger.info(f"Completed strategy run ID: {strategy_id}")

                except Exception as job_error:
                    logger.error(f"Error processing job {strategy_id}: {job_error}")
                    db_client.update_strategy_run_status(strategy_id, 'failed')

        except Exception as e:
            logger.error(f"Error in strategy scheduler poller: {e}")

        # Sleep for a defined interval before checking again
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    strategy_scheduler_poller()