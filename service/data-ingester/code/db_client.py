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

    """
    Insert broker data into the database
    data_rows: List of dictionaries with keys:
        - stocks
        - exchange
        - granularity
        - record_time
        - open
        - close
        - low
        - high
        - volume
        - broker_name

    example data_row:
    {
        'stocks': 'RELIANCE',
        'exchange': 'NSE',
        'granularity': '5minute',
        'record_time': '2025-01-20 03:45:00',
        'open': 2500.0,
        'close': 2520.0,
        'low': 2490.0,
        'high': 2530.0,
        'volume': 150000,
        'broker_name': 'zerodha'
    }
    """
    def insert_broker_data(self, data_rows):
        insert_query = """
        REPLACE INTO broker_data (stock, exchange, granularity, record_time, open, close, low, high, volume, broker_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        formatted_rows = []
        for row in data_rows:
            record_time = convert_to_mysql_datetime(row.get('record_time'))
            formatted_rows.append((
                row.get('stock'),
                row.get('exchange'),
                row.get('granularity'),
                record_time,
                row.get('open'),
                row.get('close'),
                row.get('low'),
                row.get('high'),
                row.get('volume'),
                row.get('broker_name'),
            ))
        self.cursor.executemany(insert_query, formatted_rows)
        self.connection.commit()

    def close(self):
        self.cursor.close()
        self.connection.close()