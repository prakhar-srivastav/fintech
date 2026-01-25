"""
Strategy Task Handler
- Polls for pending tasks
- Executes buy/sell orders via broker-middleware
- Updates task status and creates follow-up tasks
"""

import os
import time
import logging
import requests
from datetime import datetime, timedelta
from db_client import DBClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BROKER_MIDDLEWARE_URL = os.getenv('BROKER_MIDDLEWARE_URL', 'http://localhost:5000')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '10'))  # seconds
BUFFER = int(os.getenv('BUFFER', '170'))  # seconds buffer for polling

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

class TaskHandler:
    def __init__(self, db_client: DBClient):
        self.db = db_client
    
    def get_pending_tasks(self, time_left, time_right, day_of_execution):
        """Get all pending tasks that are ready to execute"""
        query = """
        SELECT * FROM strategy_execution_tasks 
        WHERE status = 'pending' AND timestamp_of_execution BETWEEN %s AND %s
        AND day_of_execution = %s
        ORDER BY created_at ASC
        LIMIT 10
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (time_left, time_right, day_of_execution))
            tasks = cursor.fetchall()
            cursor.close()
            return tasks

    def execute_buy(self, task):
        
        #TODO: use broker-middleware-client
        response = requests.post(
            f"{BROKER_MIDDLEWARE_URL}/api/order/buy",
            json={
                'symbol': task['stock'],
                'exchange': task['exchange'],
                'money': float(task['current_money']),
                'stimulate_mode': task['stimulate_mode']  # Note: broker uses 'stimulate_mode'
            },
            timeout=60
        )
        return response.json()
    
    def execute_sell(self, task):
        
        response = requests.post(
            f"{BROKER_MIDDLEWARE_URL}/api/order/sell",
            json={
                'symbol': task['stock'],
                'exchange': task['exchange'],
                'quantity': int(task['current_shares']),
                'stimulate_mode': task['stimulate_mode']  # Note: broker uses 'stimulate_mode'
            },
            timeout=60
        )
        return response.json()
     
    def update_task_completed(self, task_id, result):
        """Update task as completed with order results"""
        query = """
        UPDATE strategy_execution_tasks
        SET status = 'completed',
            price_during_order = %s,
            executed_at = NOW()
        WHERE id = %s
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (result.get('price_per_share'), task_id))
            conn.commit()
            cursor.close()
    
    def update_task_failed(self, task_id, error):
        """Update task as failed"""
        query = """
        UPDATE strategy_execution_tasks
        SET status = 'failed',
            error_message = %s,
            executed_at = NOW()
        WHERE id = %s
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (error, task_id))
            conn.commit()
            cursor.close()
    
    def create_follow_up_task(self, task, result):
        """Create the next task based on order type"""
        if task['order_type'] == 'buy':
            new_task = {
                'execution_detail_id': task['execution_detail_id'],
                'timestamp_of_execution': task['y'],
                'day_of_execution': task['day_of_execution'],
                'current_money': 0,
                'current_shares': result['shares_bought'],
                'order_type': 'sell',
                'stimulate_mode': task['stimulate_mode'],
                'x': task['x'],
                'y': task['y'],
                'stock': task['stock'],
                'exchange': task['exchange'],
                'days_remaining': task['days_remaining'],
                'previous_task_id': task['id']
            }
            return self.db.store_strategy_execution_task(new_task)
        
        elif task['order_type'] == 'sell':
            # After sell → check if more days remaining
            if task['days_remaining'] > 1:
                # Create next buy task
                # Calculate next day_of_execution (it's a date string like '2026-01-26')
                current_date = datetime.strptime(str(task['day_of_execution']), '%Y-%m-%d')
                next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
                
                new_task = {
                    'execution_detail_id': task['execution_detail_id'],
                    'timestamp_of_execution': None,
                    'day_of_execution': next_date,
                    'current_money': result['total_amount'],  # SELL returns total_amount, not money_provided
                    'current_shares': 0,
                    'order_type': 'buy',
                    'stimulate_mode': task['stimulate_mode'],
                    'x': task['x'],
                    'y': task['y'],
                    'stock': task['stock'],
                    'exchange': task['exchange'],
                    'days_remaining': task['days_remaining'] - 1,
                    'previous_task_id': task['id']
                }
                return self.db.store_strategy_execution_task(new_task)
            else:
                # No more days → mark detail as completed
                self._complete_execution_detail(task['execution_detail_id'])
                return None
        
        return None
    
    def _complete_execution_detail(self, detail_id):
        """Mark execution detail as completed and check if all details done"""
        # Update detail status
        query = """
        UPDATE strategy_execution_details
        SET status = 'completed'
        WHERE id = %s
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (detail_id,))
            conn.commit()
            
            # Check if all details for this execution are completed
            cursor.execute("""
                SELECT execution_id FROM strategy_execution_details WHERE id = %s
            """, (detail_id,))
            row = cursor.fetchone()
            if row:
                execution_id = row[0]
                
                # Check pending details
                cursor.execute("""
                    SELECT COUNT(*) FROM strategy_execution_details 
                    WHERE execution_id = %s AND status != 'completed'
                """, (execution_id,))
                pending = cursor.fetchone()[0]
                
                if pending == 0:
                    # All done → complete the execution
                    cursor.execute("""
                        UPDATE strategy_executions
                        SET status = 'completed', completed_at = NOW()
                        WHERE id = %s
                    """, (execution_id,))
                    conn.commit()
                    logger.info(f"Execution {execution_id} completed!")
            
            cursor.close()
    
    def update_strategy_execution_task_output(self, task_id, result):
        """Update the task output with order results"""
        query = """
        INSERT INTO strategy_execution_tasks_output (
            task_id, order_id, shares_bought, price_per_share,
            total_amount, money_provided, money_remaining, order_timestamp, exchange_timestamp
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                task_id,
                result.get('order_id'),
                result.get('shares_bought'),
                result.get('price_per_share'),
                result.get('total_amount'),
                result.get('money_provided'),
                result.get('money_remaining'),
                result.get('order_timestamp'),
                result.get('exchange_timestamp')
            ))
            conn.commit()
            cursor.close()

    def process_task(self, task):
        """Process a single task"""
        task_id = task['id']
        order_type = task['order_type']
        
        logger.info(f"Processing task {task_id}: {order_type} {task['stock']}")
        
        try:
            # Execute order
            if order_type == 'buy':
                result = self.execute_buy(task)
            elif order_type == 'sell':
                result = self.execute_sell(task)
            else:
                raise ValueError(f"Unknown order type: {order_type}")
                        
            if result.get('success'):
                self.update_strategy_execution_task_output(task_id, result)
                logger.info(f"Task {task_id} success: {result}")
                self.update_task_completed(task_id, result)
                self.create_follow_up_task(task, result)
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"Task {task_id} failed: {error}")
                self.update_task_failed(task_id, error)
        
        except Exception as e:
            logger.error(f"Task {task_id} exception: {e}")
            self.update_task_failed(task_id, str(e))
    
    def run(self):
        """Main polling loop"""
        logger.info("Task handler started")
        
        while True:
            try:
                # Calculate seconds since midnight today
                now = datetime.now()
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                start_time = int((now - midnight).total_seconds())

                time_left = start_time - BUFFER
                time_right = start_time + POLL_INTERVAL
                logger.info(f"Polling for tasks between {time_left} and {time_right} on day {now.strftime('%Y-%m-%d')}")
                tasks = self.get_pending_tasks(time_left, time_right, now.strftime('%Y-%m-%d'))

                if tasks:
                    logger.info(f"Found {len(tasks)} pending tasks")
                    for task in tasks:
                        self.process_task(task)
                else:
                    logger.debug("No pending tasks")
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
            
            time.sleep(POLL_INTERVAL)


def main():
    db_client = DBClient(DB_CONFIG)
    handler = TaskHandler(db_client)
    handler.run()


if __name__ == '__main__':
    main()

