"""
Strategy Task Watcher
- Monitors running executions for zombie tasks
- Marks stale/failed executions as failed

Criteria 
1. strategy_executions.status -> running 
    1. strategy_execution_details -> running
        1. if task in queued/running for more than buffer then mark everything fail
        2. other cases like failure seen should be alerted so that manual intervention can be done
    2. strategy_execution_details -> queued (ignore) -> task other than queued then fail
    3. strategy_execution_details -> completed/failed -> task other than completed/failed then fail

2. strategy_execution.status -> queued => everything to be queued else fail everything
3. strategy_execution.status -> completed/failed => everything to be completed/failed else default to failed

TODO: send alert for failures
"""

import os
import time
import logging
from datetime import datetime, timedelta
from db_client import DBClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '1800'))  # 30 minutes
BUFFER = int(os.getenv('BUFFER', '600'))  # 10 minutes grace period

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

class TaskWatcher:
    def __init__(self, db_client: DBClient):
        self.db = db_client
    
    def recursively_mark_execution_failed(self, execution, reason):
        """
        Fail the execution, execution details, tasks and task outputs related to the execution
        """ 
        execution_id = execution['id']
        # Update execution status
        self.db.change_strategy_execution_run_status(execution_id, 'failed')
        
        # Get and update execution details
        execution_details = self.db.get_strategy_execution_details(execution_id)
        for execution_detail in execution_details:
            self.db.change_strategy_execution_detail_status(execution_detail['id'], 'failed')
            
            # Get and update tasks for this detail
            queued_tasks = self.db.get_strategy_execution_tasks_by_detail(execution_detail['id'], status='queued')
            running_tasks = self.db.get_strategy_execution_tasks_by_detail(execution_detail['id'], status='running')
            for task in queued_tasks:
                self.db.change_strategy_execution_task_status(task['id'], 'failed', reason)
            for task in running_tasks:
                self.db.change_strategy_execution_task_status(task['id'], 'failed', reason)

        logger.info(f"Marked execution {execution_id} and all related details/tasks as failed due to: {reason}")
    
    def is_execution_zombie(self, execution):
        execution_id = execution['id']
        execution_details = self.db.get_strategy_execution_details(execution_id)
        if not execution_details:
            return True, "No execution details found"
        
        for execution_detail in execution_details:
            
            if execution_detail['status'] == 'running':
            
                tasks = self.db.get_strategy_execution_tasks_by_detail(execution_detail['id'], status='queued')
                tasks.extend(self.db.get_strategy_execution_tasks_by_detail(execution_detail['id'], status='running'))
                for task in tasks:
                    timestamp_of_execution = task['timestamp_of_execution']  # seconds since midnight
                    day_of_execution = task['day_of_execution']  # date string like '2026-01-26'
                    
                    """
                    If the task is queued and the scheduled execution time has passed by more than BUFFER seconds, 
                    we consider it a zombie. This means the task should have been executed by now, but it's still 
                    queued, indicating a potential issue.
                    """
                    # Parse the day and add seconds since midnight
                    day_date = datetime.strptime(str(day_of_execution), "%Y-%m-%d")
                    scheduled_time = day_date + timedelta(seconds=int(timestamp_of_execution))
                    
                    if datetime.now() > scheduled_time + timedelta(seconds=BUFFER):
                        return True, f"Task {task['id']} is queued and scheduled time has passed by more than {BUFFER} seconds"
        
        return False, None

    def handle_1(self):
        # 1.1.1 - Check for zombie tasks in running executions
        result = self.db.get_strategy_execution_runs('running')
        executions = result.get('runs', [])
        logger.info(f"Found {len(executions)} running executions")
        for execution in executions:
            logger.info(f"Checking execution ID: {execution['id']}")
            zombie_detected, reason = self.is_execution_zombie(execution)
            if zombie_detected:
                logger.warning(f"Zombie execution detected: {execution['id']}, Reason: {reason}")
                self.recursively_mark_execution_failed(execution, reason)
              
        # 1.1.2 will be handled by alerts and allowing manual intervention.

        # 1.2 - execution_details in 'queued' but tasks not in 'queued'
        query = """
        SELECT se.id as execution_id,
        sed.id as execution_detail_id,
        setask.id as task_id,
        se.status as execution_status, 
        sed.status as execution_detail_status,
        setask.status as task_status
        FROM strategy_executions as se
        JOIN strategy_execution_details as sed on sed.execution_id = se.id
        JOIN strategy_execution_tasks as setask on setask.execution_detail_id = sed.id
        WHERE sed.status = 'queued' AND setask.status != 'queued' AND se.status = 'running'
        """
        result = self.db.execute_query(query)
        logger.info(f"Found {len(result)} rows with details in queued but tasks not in queued")
        execution_ids_handled = set()
        for row in result:
            execution_id = row['execution_id']
            if execution_id not in execution_ids_handled:
                execution_ids_handled.add(execution_id)
                self.recursively_mark_execution_failed({'id': execution_id}, "Case 1.2: Detail queued but task not queued")

        # 1.3 - execution_details in 'completed/failed' but tasks not in 'completed/failed'
        query = """
        SELECT se.id as execution_id,
        sed.id as execution_detail_id,
        setask.id as task_id,
        se.status as execution_status, 
        sed.status as execution_detail_status,
        setask.status as task_status
        FROM strategy_executions as se
        JOIN strategy_execution_details as sed on sed.execution_id = se.id
        JOIN strategy_execution_tasks as setask on setask.execution_detail_id = sed.id
        WHERE sed.status IN ('completed', 'failed') AND setask.status NOT IN ('completed', 'failed') AND se.status = 'running'
        """
        result = self.db.execute_query(query)
        logger.info(f"Found {len(result)} rows with details completed/failed but tasks not")
        execution_ids_handled = set()
        for row in result:
            execution_id = row['execution_id']
            if execution_id not in execution_ids_handled:
                execution_ids_handled.add(execution_id)
                self.recursively_mark_execution_failed({'id': execution_id}, "Case 1.3: Detail completed/failed but task not")

    def handle_2(self):
        """Execution is 'queued' but details/tasks are not all 'queued' -> fail everything"""
        query = """
        SELECT se.id as execution_id,
        sed.id as execution_detail_id,
        setask.id as task_id,
        se.status as execution_status, 
        sed.status as execution_detail_status,
        setask.status as task_status
        FROM strategy_executions as se
        JOIN strategy_execution_details as sed on sed.execution_id = se.id
        JOIN strategy_execution_tasks as setask on setask.execution_detail_id = sed.id
        WHERE se.status = 'queued' AND (setask.status != 'queued' OR sed.status != 'queued')
        """
        result = self.db.execute_query(query)
        logger.info(f"Found {len(result)} rows with execution queued but details/tasks not queued")
        execution_ids_handled = set()
        for row in result:
            execution_id = row['execution_id']
            if execution_id not in execution_ids_handled:
                execution_ids_handled.add(execution_id)
                self.recursively_mark_execution_failed({'id': execution_id}, "Case 2: Execution queued but details/tasks not queued")

    def handle_3(self):
        """Execution is 'completed/failed' but details/tasks are not -> fail everything"""
        query = """
        SELECT se.id as execution_id,
        sed.id as execution_detail_id,
        setask.id as task_id,
        se.status as execution_status, 
        sed.status as execution_detail_status,
        setask.status as task_status
        FROM strategy_executions as se
        JOIN strategy_execution_details as sed on sed.execution_id = se.id
        JOIN strategy_execution_tasks as setask on setask.execution_detail_id = sed.id
        WHERE se.status IN ('completed', 'failed') AND (setask.status NOT IN ('completed', 'failed') OR sed.status NOT IN ('completed', 'failed'))
        """
        result = self.db.execute_query(query)
        logger.info(f"Found {len(result)} rows with execution completed/failed but details/tasks not")
        execution_ids_handled = set()
        for row in result:
            execution_id = row['execution_id']
            if execution_id not in execution_ids_handled:
                execution_ids_handled.add(execution_id)
                self.recursively_mark_execution_failed({'id': execution_id}, "Case 3: Execution completed/failed but details/tasks not")
    
    def run(self):
        """Main polling loop"""
        logger.info("Task Watcher started")
        
        while True:
            try:
                logger.info("Running task watcher checks...")
                logger.info(f"Current time: {datetime.now()}")
                t1 = time.time()
                logger.info("Starting handle_1 checks...")
                self.handle_1()
                t2 = time.time()
                logger.info("Starting handle_2 checks...")
                self.handle_2()
                t3 = time.time()
                logger.info("Starting handle_3 checks...")
                self.handle_3()
                t4 = time.time()
                logger.info(f"Task watcher checks completed in {t4 - t1} seconds.")
                logger.info(f"handle_1 took {t2 - t1} seconds")
                logger.info(f"handle_2 took {t3 - t2} seconds")
                logger.info(f"handle_3 took {t4 - t3} seconds")
                logger.info(f"Sleeping for {POLL_INTERVAL} seconds...")
                time.sleep(POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
            
            time.sleep(POLL_INTERVAL)

def main():
    db_client = DBClient(DB_CONFIG)
    watcher = TaskWatcher(db_client)
    watcher.run()

if __name__ == '__main__':
    main()

