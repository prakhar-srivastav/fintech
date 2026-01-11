"""
Database client for the frontend application.
Provides methods to query stock data from MySQL database.
"""

import os
import logging
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

import time
import os
import requests
import sqlite3
import mysql.connector
from datetime import datetime

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
    
    def get_summary(self):
        """Get summary statistics about the data"""
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT stock) as total_stocks,
                    COUNT(DISTINCT exchange) as total_exchanges,
                    MIN(record_time) as earliest_record,
                    MAX(record_time) as latest_record
                FROM broker_data
            """)
            summary = cursor.fetchone()
            cursor.close()
            
            # Format dates
            if summary['earliest_record']:
                summary['earliest_record'] = summary['earliest_record'].strftime('%Y-%m-%d %H:%M:%S')
            if summary['latest_record']:
                summary['latest_record'] = summary['latest_record'].strftime('%Y-%m-%d %H:%M:%S')
            
            return summary
    
    def get_latest_prices(self, stocks=None, limit=10):
        """
        Get latest prices for stocks.
        
        Args:
            stocks: List of stock symbols. If None, gets all stocks.
            limit: Number of stocks to return if stocks is None.
        
        Returns:
            List of latest price data per stock
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            if stocks:
                placeholders = ','.join(['%s'] * len(stocks))
                query = f"""
                    SELECT b1.*
                    FROM broker_data b1
                    INNER JOIN (
                        SELECT stock, MAX(record_time) as max_time
                        FROM broker_data
                        WHERE stock IN ({placeholders})
                        GROUP BY stock
                    ) b2 ON b1.stock = b2.stock AND b1.record_time = b2.max_time
                    ORDER BY b1.stock
                """
                cursor.execute(query, stocks)
            else:
                query = f"""
                    SELECT b1.*
                    FROM broker_data b1
                    INNER JOIN (
                        SELECT stock, MAX(record_time) as max_time
                        FROM broker_data
                        GROUP BY stock
                    ) b2 ON b1.stock = b2.stock AND b1.record_time = b2.max_time
                    ORDER BY b1.stock
                    LIMIT {int(limit)}
                """
                cursor.execute(query)
            
            result = cursor.fetchall()
            cursor.close()
            
            # Format datetime fields
            for row in result:
                if row.get('record_time'):
                    row['record_time'] = row['record_time'].strftime('%Y-%m-%d %H:%M:%S')
                if row.get('when_added'):
                    row['when_added'] = row['when_added'].strftime('%Y-%m-%d %H:%M:%S')
            
            return result

    def insert_strategy_results(self, results, strategy_id):
        """
        Insert strategy results into the database.
        
        Args:
            results: List of dictionaries with strategy results.
            strategy_id: Unique identifier for this strategy run.
        """

        insert_strategy_runs_query = """
        REPLACE INTO strategy_runs (id, when_added)
        VALUES (%s, NOW())
        """
        
        insert_query = """
        REPLACE INTO strategy_results (stock, exchange, x, y, exceed_prob, profit_days, average, total_count, highest, p5, p10, p20, p40, p50, vertical_gap, horizontal_gap, continuous_days, strategy_id)
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
                cursor.execute(insert_strategy_runs_query, (strategy_id,))
                cursor.executemany(insert_query, formatted_rows)
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()

    def get_strategy_runs(self, limit=20, offset=0):
        """
        Get list of all strategy runs with pagination.
        
        Args:
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
            cursor.execute("""
                SELECT id, when_added,
                    (SELECT COUNT(*) FROM strategy_results WHERE strategy_id = sr.id) as result_count
                FROM strategy_runs sr
                ORDER BY when_added DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            
            runs = cursor.fetchall()
            cursor.close()
            
            # Format datetime fields
            for run in runs:
                if run.get('when_added'):
                    run['when_added'] = run['when_added'].strftime('%Y-%m-%d %H:%M:%S')
            
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
            Dict with results, pagination info, and summary
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

    def get_best_per_stock_exchange(self, strategy_id, top_n=1):
        """
        Get the best result(s) for each stock/exchange pair from a strategy run.
        Returns at most top_n entries per unique stock+exchange combination,
        sorted by exceed_prob descending.
        
        Args:
            strategy_id: The strategy run ID
            top_n: Number of top results per stock/exchange pair (default: 1)
        
        Returns:
            List of best results grouped by stock/exchange
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Use ROW_NUMBER() window function to get top N per group
            query = """
                SELECT * FROM (
                    SELECT 
                        id, stock, exchange, x, y, exceed_prob, profit_days, average,
                        total_count, highest, p5, p10, p20, p40, p50, 
                        vertical_gap, horizontal_gap, continuous_days,
                        ROW_NUMBER() OVER (
                            PARTITION BY stock, exchange 
                            ORDER BY exceed_prob DESC
                        ) as rn
                    FROM strategy_results
                    WHERE strategy_id = %s
                ) ranked
                WHERE rn <= %s
                ORDER BY exceed_prob DESC
            """
            cursor.execute(query, (strategy_id, top_n))
            results = cursor.fetchall()
            cursor.close()
            
            # Process results
            for row in results:
                row.pop('rn', None)  # Remove ranking column
                for key in ['exceed_prob', 'average', 'highest', 'p5', 'p10', 'p20', 'p40', 'p50']:
                    if row.get(key) is not None:
                        row[key] = float(row[key])
            
            return results

    def get_top_configs_per_stock(self, strategy_id, stock, exchange=None, top_n=4):
        """
        Get the top N configurations for a specific stock.
        
        Args:
            strategy_id: The strategy run ID
            stock: Stock symbol
            exchange: Exchange (optional)
            top_n: Number of top configurations to return (default: 4)
        
        Returns:
            List of top N configurations for the stock
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT id, stock, exchange, x, y, exceed_prob, profit_days, average,
                       total_count, highest, p5, p10, p20, p40, p50, 
                       vertical_gap, horizontal_gap, continuous_days
                FROM strategy_results
                WHERE strategy_id = %s AND stock = %s
            """
            params = [strategy_id, stock]
            
            if exchange:
                query += " AND exchange = %s"
                params.append(exchange)
            
            query += " ORDER BY exceed_prob DESC LIMIT %s"
            params.append(top_n)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            # Process results
            for row in results:
                for key in ['exceed_prob', 'average', 'highest', 'p5', 'p10', 'p20', 'p40', 'p50']:
                    if row.get(key) is not None:
                        row[key] = float(row[key])
            
            return results

    def get_strategy_summary(self, strategy_id):
        """
        Get summary statistics for a strategy run.
        
        Args:
            strategy_id: The strategy run ID
        
        Returns:
            Dict with summary statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Basic counts
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_results,
                    COUNT(DISTINCT stock) as unique_stocks,
                    COUNT(DISTINCT exchange) as unique_exchanges,
                    MAX(exceed_prob) as max_exceed_prob,
                    AVG(exceed_prob) as avg_exceed_prob,
                    MAX(average) as max_average
                FROM strategy_results
                WHERE strategy_id = %s
            """, (strategy_id,))
            summary = cursor.fetchone()
            
            # Top symbols by max exceed_prob
            cursor.execute("""
                SELECT stock as symbol, exchange,
                       MAX(exceed_prob) as max_exceed_prob,
                       AVG(exceed_prob) as avg_exceed_prob,
                       COUNT(*) as count
                FROM strategy_results
                WHERE strategy_id = %s
                GROUP BY stock, exchange
                ORDER BY max_exceed_prob DESC
                LIMIT 10
            """, (strategy_id,))
            top_symbols = cursor.fetchall()
            
            # Stats by vertical_gap
            cursor.execute("""
                SELECT vertical_gap, AVG(exceed_prob) as avg_exceed_prob
                FROM strategy_results
                WHERE strategy_id = %s
                GROUP BY vertical_gap
                ORDER BY vertical_gap
            """, (strategy_id,))
            by_vertical_gap = {str(row['vertical_gap']): float(row['avg_exceed_prob']) for row in cursor.fetchall()}
            
            # Stats by horizontal_gap
            cursor.execute("""
                SELECT horizontal_gap, AVG(exceed_prob) as avg_exceed_prob
                FROM strategy_results
                WHERE strategy_id = %s
                GROUP BY horizontal_gap
                ORDER BY horizontal_gap
            """, (strategy_id,))
            by_horizontal_gap = {str(row['horizontal_gap']): float(row['avg_exceed_prob']) for row in cursor.fetchall()}
            
            # Stats by continuous_days
            cursor.execute("""
                SELECT continuous_days, AVG(exceed_prob) as avg_exceed_prob
                FROM strategy_results
                WHERE strategy_id = %s
                GROUP BY continuous_days
                ORDER BY continuous_days
            """, (strategy_id,))
            by_continuous_days = {str(row['continuous_days']): float(row['avg_exceed_prob']) for row in cursor.fetchall()}
            
            # Best overall result
            cursor.execute("""
                SELECT stock as symbol, exchange, x, y, exceed_prob, average, 
                       vertical_gap, horizontal_gap, continuous_days
                FROM strategy_results
                WHERE strategy_id = %s
                ORDER BY exceed_prob DESC
                LIMIT 1
            """, (strategy_id,))
            best_overall = cursor.fetchone()
            
            cursor.close()
            
            # Convert Decimal to float
            for key in ['max_exceed_prob', 'avg_exceed_prob', 'max_average']:
                if summary.get(key) is not None:
                    summary[key] = float(summary[key])
            
            for sym in top_symbols:
                for key in ['max_exceed_prob', 'avg_exceed_prob']:
                    if sym.get(key) is not None:
                        sym[key] = float(sym[key])
            
            if best_overall:
                for key in ['exceed_prob', 'average']:
                    if best_overall.get(key) is not None:
                        best_overall[key] = float(best_overall[key])
            
            return {
                'total_results': summary['total_results'],
                'unique_symbols': summary['unique_stocks'],
                'unique_exchanges': summary['unique_exchanges'],
                'max_exceed_prob': summary['max_exceed_prob'],
                'avg_exceed_prob': summary['avg_exceed_prob'],
                'top_symbols': top_symbols,
                'by_vertical_gap': by_vertical_gap,
                'by_horizontal_gap': by_horizontal_gap,
                'by_continuous_days': by_continuous_days,
                'best_overall': best_overall
            }

    def get_unique_stocks(self, strategy_id):
        """
        Get list of unique stocks from a strategy run.
        
        Args:
            strategy_id: The strategy run ID
        
        Returns:
            List of unique stock symbols with their exchanges
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT DISTINCT stock, exchange
                FROM strategy_results
                WHERE strategy_id = %s
                ORDER BY stock, exchange
            """, (strategy_id,))
            stocks = cursor.fetchall()
            cursor.close()
            return stocks