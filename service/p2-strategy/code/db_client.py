"""
Database client for the frontend application.
Provides methods to query stock data from MySQL database.
"""

import os
import logging
import json
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def convert_to_mysql_datetime(date_str):
    try:
        # Try parsing 'Mon, 20 Jan 2025 03:45:00 GMT' format
        parsed_date = datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %Z')
        record_time = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            # Try parsing ISO format '2025-01-20T03:45:00'
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            record_time = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            # Use as-is if already in correct format or None
            record_time = date_str
    return record_time


class DBClient:

    def __init__(self, db_config):
        self.db_config = db_config
        self.connection = mysql.connector.connect(**db_config)
        self.cursor = self.connection.cursor()

    def close(self):
        self.cursor.close()
        self.connection.close()

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Creates a new connection and closes it when done.
        """
        conn = None
        try:
            conn = mysql.connector.connect(**self.db_config)
            yield conn
        finally:
            if conn:
                conn.close()

    def execute_query(self, query, params=None):
        """
        Execute a raw SQL query and return results as list of dicts.
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters for the query
        
        Returns:
            List of dictionaries with query results
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            return results
    
    def get_default_strategy_config(self):
        """Get default strategy configuration from database"""
        query = """
        SELECT parameter, value FROM default_strategy_config
        """
        config = {}
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    param, value = row
                    if param in ['vertical_gaps', 'horizontal_gaps', 'continuous_days']:
                        # Handle float values for vertical_gaps
                        if param == 'vertical_gaps':
                            config[param] = [float(x) for x in value.split(',')]
                        else:
                            config[param] = [int(x) for x in value.split(',')]
                    else:
                        config[param] = value
                cursor.close()
        except Exception as e:
            logger.warning(f"Could not load default config from DB: {e}, using hardcoded defaults")
            # Return hardcoded defaults if table doesn't exist
            config = {
                'vertical_gaps': [0.5, 1, 2],
                'horizontal_gaps': [2],
                'continuous_days': [3, 5, 7, 10],
                'granularity': '3minute'
            }
        return config
        
    def get_granularities(self):
        """Get available granularities from broker data"""
        query = """
        SELECT DISTINCT granularity FROM broker_data
        """
        granularities = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                granularities.append(row[0])
            cursor.close()
        return granularities

    def get_stock_data(self, stock, exchange=None, granularity=None, 
                       start_date=None, end_date=None, limit=1000):
        """
        Get stock data for charting.
        
        Args:
            stock: Stock symbol (required)
            exchange: Exchange filter (optional)
            granularity: Granularity filter (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            limit: Maximum rows to return (default: 1000)
        
        Returns:
            Dict with chart-ready data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT record_time, open, high, low, close, volume
                FROM broker_data
                WHERE stock = %s
            """
            params = [stock]
            
            if exchange:
                query += " AND exchange = %s"
                params.append(exchange)
            
            if granularity:
                query += " AND granularity = %s"
                params.append(granularity)
            
            if start_date:
                query += " AND record_time >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND record_time <= %s"
                params.append(end_date)
            
            query += " ORDER BY record_time ASC"
            
            if limit:
                query += f" LIMIT {int(limit)}"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Format data for charts
            data = {
                'labels': [],
                'open': [],
                'high': [],
                'low': [],
                'close': [],
                'volume': [],
                'ohlc': []
            }
            
            for row in rows:
                timestamp = row['record_time'].strftime('%Y-%m-%d %H:%M') \
                    if isinstance(row['record_time'], datetime) else str(row['record_time'])
                data['labels'].append(timestamp)
                data['open'].append(float(row['open']) if row['open'] else None)
                data['high'].append(float(row['high']) if row['high'] else None)
                data['low'].append(float(row['low']) if row['low'] else None)
                data['close'].append(float(row['close']) if row['close'] else None)
                data['volume'].append(int(row['volume']) if row['volume'] else 0)
                data['ohlc'].append({
                    'x': timestamp,
                    'o': float(row['open']) if row['open'] else None,
                    'h': float(row['high']) if row['high'] else None,
                    'l': float(row['low']) if row['low'] else None,
                    'c': float(row['close']) if row['close'] else None
                })
            
            return {
                'stock': stock,
                'exchange': exchange,
                'granularity': granularity,
                'count': len(rows),
                'data': data
            }

    def create_strategy_scheduler_job(self, config):
        """Create a new strategy scheduler job"""
        query = """
        INSERT INTO strategy_scheduler_jobs (config, status, created_at)
        VALUES (%s, %s, %s)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (json.dumps(config), 'scheduled', datetime.now()))
            conn.commit()
            job_id = cursor.lastrowid
            cursor.close()
            return job_id

    def create_strategy_run(self, config, status='queued'):
        """
        Create a new strategy run record.
        
        Args:
            config: Configuration dict used for this run
            status: Initial status (default: 'queued')
        
        Returns:
            int: The auto-generated strategy run ID
        """
        query = """
        INSERT INTO strategy_runs (config, status, when_added)
        VALUES (%s, %s, NOW())
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (json.dumps(config), status))
            conn.commit()
            strategy_id = cursor.lastrowid
            cursor.close()
            return strategy_id

    def update_strategy_run_status(self, strategy_id, status):
        """
        Update the status of a strategy run.
        
        Args:
            strategy_id: The strategy run ID
            status: New status ('running', 'completed', 'failed')
        """
        query = """
        UPDATE strategy_runs 
        SET status = %s, updated_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, strategy_id))
            conn.commit()
            cursor.close()

    def save_strategy_results(self, strategy_id, results):
        """
        Save strategy results to the database.
        
        Args:
            strategy_id: The strategy run ID
            results: List of result dictionaries
        """
        insert_query = """
        INSERT INTO strategy_results (
            stock, exchange, x, y, exceed_prob, profit_days, average, 
            total_count, highest, p5, p10, p20, p40, p50, 
            vertical_gap, horizontal_gap, continuous_days, strategy_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        formatted_rows = []
        for row in results:
            formatted_rows.append((
                row.get('symbol'),
                row.get('exchange'),
                row.get('x'),
                row.get('y'),
                row.get('exceed_prob'),
                row.get('profit_days'),
                row.get('average'),
                row.get('total_count'),
                row.get('highest'),
                row.get('p5'),
                row.get('p10'),
                row.get('p20'),
                row.get('p40'),
                row.get('p50'),
                row.get('vertical_gap'),
                row.get('horizontal_gap'),
                row.get('continuous_days'),
                strategy_id
            ))
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(insert_query, formatted_rows)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    def get_strategy_runs(self, status=None, limit=20, offset=0):
        """
        Get list of all strategy runs with pagination.
        
        Args:
            status: Filter by status (optional)
            limit: Maximum number of runs to return (default: 20)
            offset: Number of runs to skip (default: 0)
        
        Returns:
            Dict with runs list and total count
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as total FROM strategy_runs")
            total = cursor.fetchone()['total']
            
            # Get paginated runs
            query = """
                SELECT id, when_added, status, config,
                    (SELECT COUNT(*) FROM strategy_results WHERE strategy_id = sr.id) as result_count
                FROM strategy_runs sr
            """
            params = []
            if status:
                query += " WHERE status = %s"
                params.append(status)
            query += " ORDER BY when_added DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cursor.execute(query, params)

            runs = cursor.fetchall()
            cursor.close()
            
            # Format datetime fields
            for run in runs:
                if run.get('when_added'):
                    run['when_added'] = run['when_added'].strftime('%Y-%m-%d %H:%M:%S')
                if run.get('config'):
                    try:
                        run['config'] = json.loads(run['config'])
                    except:
                        pass
            
            return {
                'runs': runs,
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total
            }

    def get_strategy_results(self, strategy_id, page=1, per_page=50, 
                             stock=None, exchange=None, sort_by='exceed_prob', sort_order='desc'):
        """
        Get paginated strategy results for a specific run.
        
        Args:
            strategy_id: The strategy run ID
            page: Page number (1-indexed)
            per_page: Results per page
            stock: Filter by stock symbol (optional)
            exchange: Filter by exchange (optional)
            sort_by: Field to sort by (default: exceed_prob)
            sort_order: Sort order - 'asc' or 'desc' (default: desc)
        
        Returns:
            Dict with results, pagination info
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            offset = (page - 1) * per_page
            
            # Build WHERE clause
            where_clauses = ["strategy_id = %s"]
            params = [strategy_id]
            
            if stock:
                where_clauses.append("stock = %s")
                params.append(stock)
            
            if exchange:
                where_clauses.append("exchange = %s")
                params.append(exchange)
            
            where_sql = " AND ".join(where_clauses)
            
            # Validate sort_by to prevent SQL injection
            valid_sort_fields = ['exceed_prob', 'average', 'stock', 'exchange', 'vertical_gap', 'horizontal_gap', 'continuous_days']
            if sort_by not in valid_sort_fields:
                sort_by = 'exceed_prob'
            sort_order_sql = 'DESC' if sort_order.lower() == 'desc' else 'ASC'
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM strategy_results WHERE {where_sql}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            # Get paginated results
            query = f"""
                SELECT id, stock, exchange, x, y, exceed_prob, profit_days, average, 
                       total_count, highest, p5, p10, p20, p40, p50, 
                       vertical_gap, horizontal_gap, continuous_days
                FROM strategy_results 
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order_sql}
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [per_page, offset])
            results = cursor.fetchall()
            cursor.close()
            
            # Process results
            for row in results:
                # Convert Decimal to float for JSON serialization
                for key in ['exceed_prob', 'average', 'highest', 'p5', 'p10', 'p20', 'p40', 'p50']:
                    if row.get(key) is not None:
                        row[key] = float(row[key])
            
            total_pages = (total + per_page - 1) // per_page
            
            return {
                'results': results,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages
                }
            }
    
    def create_strategy_execution(self, strategy_id, stimulate_mode=True, total_money=None, selected_configs=None):
        """
        Create a new strategy execution record.
        
        Args:
            strategy_id: The strategy run ID
            stimulate_mode: Whether to run in simulation mode (default: True)
            total_money: Total money to invest (required if not stimulate_mode)
            selected_configs: List of dicts with 'id' and 'weight_percent' keys
        
        Returns:
            Dict with execution details
        """
        query = """
        INSERT INTO strategy_executions (strategy_id, status, stimulate_mode, total_money, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """
        query_2 = """
        INSERT INTO strategy_execution_details (execution_id, strategy_result_id, weight_percent)
        VALUES (%s, %s, %s)
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (strategy_id, 'queued', stimulate_mode, total_money, datetime.now()))
            execution_id = cursor.lastrowid
            if selected_configs:
                detail_rows = [(execution_id, cfg['id'], cfg.get('weight_percent', 0)) for cfg in selected_configs]
                cursor.executemany(query_2, detail_rows)
            conn.commit()
            cursor.close()
            return {
                'execution_id': execution_id,
                'strategy_id': strategy_id,
                'stimulate_mode': stimulate_mode,
                'total_money': total_money,
                'status': 'queued',
                'configs_count': len(selected_configs) if selected_configs else 0,
                'created_at': datetime.now().isoformat()
            }

    def get_strategy_execution_data_by_id(self, execution_id):
        """
        Get strategy execution data by ID.
        
        Args:
            execution_id: The execution ID
        
        Returns:
            Dict with execution data or None if not found
        """
        query = """
        SELECT id, strategy_id, status, stimulate_mode, total_money, 
               created_at, started_at, completed_at, error_message
        FROM strategy_executions 
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (execution_id,))
            result = cursor.fetchone()
            cursor.close()
            return result

    def get_strategy_execution_details(self, execution_id):
        """
        Get strategy execution details (selected configs with weights).
        
        Args:
            execution_id: The execution ID
        
        Returns:
            List of dicts with execution detail records
        """
        query = """
        SELECT sed.id, sed.execution_id, sed.strategy_result_id, sed.weight_percent, sed.status,
               sr.stock, sr.exchange, sr.x, sr.y, sr.exceed_prob, sr.average,
               sr.vertical_gap, sr.horizontal_gap, sr.continuous_days
        FROM strategy_execution_details sed
        JOIN strategy_results sr ON sed.strategy_result_id = sr.id
        WHERE sed.execution_id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (execution_id,))
            results = cursor.fetchall()
            cursor.close()
            
            # Convert Decimal to float for JSON serialization
            for row in results:
                for key in ['weight_percent', 'exceed_prob', 'average', 'vertical_gap', 'horizontal_gap']:
                    if row.get(key) is not None:
                        row[key] = float(row[key])
            
            return results

    def get_strategy_result_by_id(self, strategy_result_id):
        """
        Get a single strategy result by ID.
        
        Args:
            strategy_result_id: The strategy result ID
        
        Returns:
            Dict with strategy result data or None if not found
        """
        query = """
        SELECT id, strategy_id, stock, exchange, x, y, exceed_prob, profit_days, 
               average, total_count, highest, p5, p10, p20, p40, p50,
               vertical_gap, horizontal_gap, continuous_days
        FROM strategy_results 
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, (strategy_result_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                # Convert Decimal to float for JSON serialization
                for key in ['exceed_prob', 'average', 'highest', 'p5', 'p10', 'p20', 'p40', 'p50', 
                           'vertical_gap', 'horizontal_gap']:
                    if result.get(key) is not None:
                        result[key] = float(result[key])
            
            return result

    def store_strategy_execution_task(self, task):
        """
        Store a strategy execution task.
        
        Args:
            task: Dict with task details containing:
                - execution_detail_id: ID of the execution detail
                - timestamp_of_execution: When to execute
                - day_of_execution: Day number in the execution sequence
                - current_money: Current money allocated
                - current_shares: Current number of shares held
                - price_during_order: Price at which order was placed (nullable)
                - order_type: 'buy' or 'sell'
                - stimulate_mode: Whether in simulation mode
                - x: X point from strategy
                - y: Y point from strategy
                - stock: Stock symbol
                - exchange: Exchange name
                - days_remaining: Days remaining in execution
                - previous_task_id: ID of the previous task (-1 if first)
        
        Returns:
            int: The auto-generated task ID
        """
        query = """
        INSERT INTO strategy_execution_tasks (
            execution_detail_id, timestamp_of_execution, day_of_execution,
            current_money, current_shares, price_during_order, order_type,
            stimulate_mode, x, y, stock, exchange, days_remaining, 
            previous_task_id, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                task.get('execution_detail_id'),
                task.get('timestamp_of_execution'),
                task.get('day_of_execution', 0),
                task.get('current_money'),
                task.get('current_shares', 0),
                task.get('price_during_order'),
                task.get('order_type', 'buy'),
                task.get('stimulate_mode', True),
                task.get('x'),
                task.get('y'),
                task.get('stock'),
                task.get('exchange'),
                task.get('days_remaining', 0),
                task.get('previous_task_id', -1),
                'queued',
                datetime.now()
            ))
            conn.commit()
            task_id = cursor.lastrowid
            cursor.close()
            return task_id

    def change_strategy_execution_run_status(self, execution_id, status):
        """
        Change the status of a strategy execution run.
        
        Args:
            execution_id: The execution ID
            status: New status ('queued', 'running', 'completed', 'failed')
        """
        query = """
        UPDATE strategy_executions
        SET status = %s
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, execution_id))
            conn.commit()
            cursor.close()

    def get_strategy_execution_runs(self, status=None):
        """
        Get strategy execution runs filtered by status.
        
        Args:
            status: Filter by status (optional)
        
        Returns:
            Dict with 'runs' list of execution run records
        """
        query = """
        SELECT id, strategy_id, status, stimulate_mode, total_money, created_at
        FROM strategy_executions
        """
        params = []
        if status:
            query += " WHERE status = %s"
            params.append(status)
        
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            return {'runs': results}

    def change_strategy_execution_detail_status(self, detail_id, status):
        """
        Update the status of a strategy execution detail.
        
        Args:
            detail_id: The execution detail ID
            status: New status ('pending', 'running', 'completed', 'failed')
        """
        query = """
        UPDATE strategy_execution_details
        SET status = %s
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, detail_id))
            conn.commit()
            cursor.close()

    def get_strategy_execution_tasks_by_detail(self, execution_detail_id, status=None):
        """
        Get strategy execution tasks for a specific execution detail.
        
        Args:
            execution_detail_id: The execution detail ID
            status: Filter by status (optional)
        
        Returns:
            List of task records
        """
        query = """
        SELECT id, execution_detail_id, timestamp_of_execution, day_of_execution,
               current_money, current_shares, price_during_order, order_type,
               stimulate_mode, x, y, stock, exchange, days_remaining,
               previous_task_id, status, created_at, executed_at, error_message
        FROM strategy_execution_tasks
        WHERE execution_detail_id = %s
        """
        params = [execution_detail_id]
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            return results

    def change_strategy_execution_task_status(self, task_id, status, error_message=''):
        """
        Update the status of a strategy execution task.
        
        Args:
            task_id: The task ID
            status: New status ('queued', 'running', 'completed', 'failed')
            error_message: Optional error message if status is 'failed'
        """
        query = """
        UPDATE strategy_execution_tasks
        SET status = %s, error_message = %s, executed_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status, error_message, task_id))
            conn.commit()
            cursor.close()

    def get_all_strategy_executions(self, limit=50, offset=0):
        """
        Get all strategy executions with strategy run config details and profit summary.
        
        Returns:
            Dict with executions list and pagination info
        """
        query = """
        SELECT 
            se.id, se.strategy_id, se.status, se.stimulate_mode, se.total_money,
            se.created_at, se.started_at, se.completed_at, se.error_message,
            sr.config as strategy_config,
            (SELECT COUNT(*) FROM strategy_execution_details WHERE execution_id = se.id) as details_count
        FROM strategy_executions se
        JOIN strategy_runs sr ON se.strategy_id = sr.id
        ORDER BY se.created_at DESC
        LIMIT %s OFFSET %s
        """
        
        count_query = "SELECT COUNT(*) as total FROM strategy_executions"
        
        # Query to calculate total profit for an execution
        profit_query = """
        SELECT 
            COALESCE(SUM(
                CASE 
                    WHEN sell_task.total_amount IS NOT NULL AND buy_task.total_amount IS NOT NULL 
                    THEN sell_task.total_amount - buy_task.total_amount 
                    ELSE 0 
                END
            ), 0) as total_profit
        FROM strategy_execution_details sed
        JOIN strategy_execution_tasks buy_t ON buy_t.execution_detail_id = sed.id AND buy_t.order_type = 'buy' AND buy_t.status = 'completed'
        JOIN strategy_execution_tasks sell_t ON sell_t.execution_detail_id = sed.id AND sell_t.order_type = 'sell' AND sell_t.status = 'completed' AND sell_t.day_of_execution = buy_t.day_of_execution
        LEFT JOIN strategy_execution_tasks_output buy_task ON buy_task.task_id = buy_t.id
        LEFT JOIN strategy_execution_tasks_output sell_task ON sell_task.task_id = sell_t.id
        WHERE sed.execution_id = %s
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get total count
            cursor.execute(count_query)
            total = cursor.fetchone()['total']
            
            # Get paginated results
            cursor.execute(query, (limit, offset))
            results = cursor.fetchall()
            
            # Process results and calculate profit for each
            for row in results:
                if row.get('total_money'):
                    row['total_money'] = float(row['total_money'])
                if row.get('created_at'):
                    row['created_at'] = row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['created_at'], 'strftime') else str(row['created_at'])
                if row.get('started_at'):
                    row['started_at'] = row['started_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['started_at'], 'strftime') else str(row['started_at'])
                if row.get('completed_at'):
                    row['completed_at'] = row['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row['completed_at'], 'strftime') else str(row['completed_at'])
                if row.get('strategy_config'):
                    try:
                        row['strategy_config'] = json.loads(row['strategy_config'])
                    except:
                        pass
                
                # Calculate total profit for this execution
                try:
                    cursor.execute(profit_query, (row['id'],))
                    profit_result = cursor.fetchone()
                    row['total_profit'] = float(profit_result['total_profit']) if profit_result and profit_result['total_profit'] else 0
                except Exception as e:
                    logger.warning(f"Could not calculate profit for execution {row['id']}: {e}")
                    row['total_profit'] = 0
            
            cursor.close()
            
            return {
                'executions': results,
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total
            }

    def get_execution_full_details(self, execution_id):
        """
        Get full details of a strategy execution including all stock details,
        tasks, and outputs for the Executions tab.
        
        Args:
            execution_id: The execution ID
        
        Returns:
            Dict with execution data, stock details, and daywise profit info
        """
        # Get execution basic info
        exec_query = """
        SELECT 
            se.id, se.strategy_id, se.status, se.stimulate_mode, se.total_money,
            se.created_at, se.started_at, se.completed_at, se.error_message,
            sr.config as strategy_config
        FROM strategy_executions se
        JOIN strategy_runs sr ON se.strategy_id = sr.id
        WHERE se.id = %s
        """
        
        # Get execution details with strategy results info
        details_query = """
        SELECT 
            sed.id as detail_id, sed.execution_id, sed.strategy_result_id, 
            sed.weight_percent, sed.status as detail_status,
            sr.stock, sr.exchange, sr.x, sr.y, sr.exceed_prob, sr.average,
            sr.p5, sr.p10, sr.p20, sr.p40, sr.p50,
            sr.vertical_gap, sr.horizontal_gap, sr.continuous_days, sr.profit_days
        FROM strategy_execution_details sed
        JOIN strategy_results sr ON sed.strategy_result_id = sr.id
        WHERE sed.execution_id = %s
        """
        
        # Get tasks with outputs for this execution
        tasks_query = """
        SELECT 
            t.id as task_id, t.execution_detail_id, t.timestamp_of_execution,
            t.day_of_execution, t.current_money, t.current_shares,
            t.price_during_order, t.order_type, t.stimulate_mode,
            t.x, t.y, t.stock, t.exchange, t.days_remaining,
            t.status as task_status, t.created_at as task_created_at,
            t.executed_at, t.error_message as task_error,
            o.id as output_id, o.order_id, o.shares_bought, o.price_per_share,
            o.total_amount, o.money_provided, o.money_remaining,
            o.order_timestamp, o.exchange_timestamp
        FROM strategy_execution_tasks t
        LEFT JOIN strategy_execution_tasks_output o ON t.id = o.task_id
        WHERE t.execution_detail_id IN (
            SELECT id FROM strategy_execution_details WHERE execution_id = %s
        )
        ORDER BY t.execution_detail_id, t.day_of_execution, t.order_type
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get execution info
            cursor.execute(exec_query, (execution_id,))
            execution = cursor.fetchone()
            if not execution:
                cursor.close()
                return None
            
            # Process execution
            if execution.get('total_money'):
                execution['total_money'] = float(execution['total_money'])
            if execution.get('created_at'):
                execution['created_at'] = execution['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(execution['created_at'], 'strftime') else str(execution['created_at'])
            if execution.get('started_at'):
                execution['started_at'] = execution['started_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(execution['started_at'], 'strftime') else str(execution['started_at'])
            if execution.get('completed_at'):
                execution['completed_at'] = execution['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(execution['completed_at'], 'strftime') else str(execution['completed_at'])
            if execution.get('strategy_config'):
                try:
                    execution['strategy_config'] = json.loads(execution['strategy_config'])
                except:
                    pass
            
            # Get execution details
            cursor.execute(details_query, (execution_id,))
            details = cursor.fetchall()
            
            # Convert Decimals to floats
            for detail in details:
                for key in ['weight_percent', 'exceed_prob', 'average', 'p5', 'p10', 'p20', 'p40', 'p50', 'vertical_gap', 'horizontal_gap']:
                    if detail.get(key) is not None:
                        detail[key] = float(detail[key])
            
            # Get tasks with outputs
            cursor.execute(tasks_query, (execution_id,))
            tasks = cursor.fetchall()
            
            # Process tasks
            for task in tasks:
                for key in ['current_money', 'price_during_order', 'total_amount', 'money_provided', 'money_remaining', 'price_per_share']:
                    if task.get(key) is not None:
                        task[key] = float(task[key])
                if task.get('executed_at'):
                    task['executed_at'] = task['executed_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(task['executed_at'], 'strftime') else str(task['executed_at'])
                if task.get('order_timestamp'):
                    task['order_timestamp'] = task['order_timestamp'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(task['order_timestamp'], 'strftime') else str(task['order_timestamp'])
            
            cursor.close()
            
            # Organize tasks by detail_id
            tasks_by_detail = {}
            for task in tasks:
                detail_id = task['execution_detail_id']
                if detail_id not in tasks_by_detail:
                    tasks_by_detail[detail_id] = []
                tasks_by_detail[detail_id].append(task)
            
            # Add tasks to details and calculate profits
            total_profit = 0
            daywise_profit = {}
            
            for detail in details:
                detail_id = detail['detail_id']
                detail['tasks'] = tasks_by_detail.get(detail_id, [])
                
                # Calculate money allocated per day
                if execution.get('total_money') and detail.get('weight_percent'):
                    detail['money_allocated'] = execution['total_money'] * detail['weight_percent'] / 100
                else:
                    detail['money_allocated'] = 0
                
                # Calculate estimated profits
                if detail['money_allocated'] > 0:
                    detail['estimated_profit_average'] = detail['money_allocated'] * (detail.get('average', 0) or 0) / 100
                    detail['estimated_profit_vgap'] = detail['money_allocated'] * (detail.get('vertical_gap', 0) or 0) / 100
                    detail['estimated_profit_p5'] = detail['money_allocated'] * (detail.get('p5', 0) or 0) / 100
                    detail['estimated_profit_p10'] = detail['money_allocated'] * (detail.get('p10', 0) or 0) / 100
                    detail['estimated_profit_p20'] = detail['money_allocated'] * (detail.get('p20', 0) or 0) / 100
                    detail['estimated_profit_p40'] = detail['money_allocated'] * (detail.get('p40', 0) or 0) / 100
                    detail['estimated_profit_p50'] = detail['money_allocated'] * (detail.get('p50', 0) or 0) / 100
                else:
                    detail['estimated_profit_average'] = 0
                    detail['estimated_profit_vgap'] = 0
                    detail['estimated_profit_p5'] = 0
                    detail['estimated_profit_p10'] = 0
                    detail['estimated_profit_p20'] = 0
                    detail['estimated_profit_p40'] = 0
                    detail['estimated_profit_p50'] = 0
                
                # Calculate actual profit from completed tasks
                detail['actual_profit'] = 0
                detail['days_completed'] = 0
                detail['total_days'] = detail.get('continuous_days', 0) or 0
                detail['daywise'] = []
                
                # Group tasks by day
                days = {}
                for task in detail['tasks']:
                    day = task.get('day_of_execution', 'unknown')
                    if day not in days:
                        days[day] = {'buy': None, 'sell': None}
                    if task['order_type'] == 'buy':
                        days[day]['buy'] = task
                    else:
                        days[day]['sell'] = task
                
                # Calculate per-day profit
                for day, day_tasks in sorted(days.items()):
                    day_info = {
                        'day': day,
                        'buy': day_tasks['buy'],
                        'sell': day_tasks['sell'],
                        'profit': None,
                        'status': 'pending'
                    }
                    
                    buy_task = day_tasks['buy']
                    sell_task = day_tasks['sell']
                    
                    if buy_task and sell_task:
                        if buy_task.get('task_status') == 'completed' and sell_task.get('task_status') == 'completed':
                            buy_amount = buy_task.get('total_amount') or 0
                            sell_amount = sell_task.get('total_amount') or 0
                            day_profit = sell_amount - buy_amount
                            day_info['profit'] = day_profit
                            day_info['status'] = 'completed'
                            detail['actual_profit'] += day_profit
                            detail['days_completed'] += 1
                            
                            # Add to overall daywise profit
                            if day not in daywise_profit:
                                daywise_profit[day] = 0
                            daywise_profit[day] += day_profit
                        elif buy_task.get('task_status') == 'failed' or sell_task.get('task_status') == 'failed':
                            day_info['status'] = 'failed'
                        elif buy_task.get('task_status') == 'completed':
                            day_info['status'] = 'in_progress'
                    elif buy_task:
                        if buy_task.get('task_status') == 'completed':
                            day_info['status'] = 'in_progress'
                        elif buy_task.get('task_status') == 'failed':
                            day_info['status'] = 'failed'
                    
                    detail['daywise'].append(day_info)
                
                total_profit += detail['actual_profit']
            
            execution['details'] = details
            execution['total_profit'] = total_profit
            execution['daywise_profit'] = daywise_profit
            
            return execution