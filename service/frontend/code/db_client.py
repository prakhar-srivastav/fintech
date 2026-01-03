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
