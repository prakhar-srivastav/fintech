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

    def get_pending_strategy_scheduler_jobs(self):
        """
        Get pending strategy scheduler jobs.
        
        Returns:
            List of pending jobs with id and config
        """
        query = """
        SELECT id, config FROM strategy_scheduler_jobs
        WHERE status = 'scheduled'
        ORDER BY created_at ASC
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            jobs = cursor.fetchall()
            cursor.close()
            
            # Parse config JSON
            for job in jobs:
                if job.get('config'):
                    try:
                        job['config'] = json.loads(job['config'])
                    except:
                        pass
            
            return jobs

    def mark_strategy_scheduler_job_completed(self, job_id):
        """
        Mark a strategy scheduler job as completed.
        
        Args:
            job_id: The job ID to mark as completed
        """
        query = """
        UPDATE strategy_scheduler_jobs
        SET status = 'completed', completed_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (job_id,))
            conn.commit()
            cursor.close()

    def mark_strategy_scheduler_job_failed(self, job_id, error_message=None):
        """
        Mark a strategy scheduler job as failed.
        
        Args:
            job_id: The job ID to mark as failed
            error_message: Optional error message
        """
        query = """
        UPDATE strategy_scheduler_jobs
        SET status = 'failed', error_message = %s, completed_at = NOW()
        WHERE id = %s
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (error_message, job_id))
            conn.commit()
            cursor.close()