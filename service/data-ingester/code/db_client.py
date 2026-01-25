import time
import os
import requests
import sqlite3
import mysql.connector
from datetime import datetime, timedelta, timezone

import logging
logger = logging.getLogger(__name__)

# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


def convert_to_mysql_datetime(date_str):
    """
    Convert datetime string to MySQL format in IST (Indian Standard Time).
    
    Handles:
    - 'Mon, 20 Jan 2025 03:45:00 GMT' -> converts from UTC to IST
    - '2025-01-20T03:45:00Z' -> converts from UTC to IST
    - '2025-01-20T09:15:00+05:30' -> already IST, just formats
    - '2025-01-20 09:15:00' -> assumes already IST
    """
    if date_str is None:
        return None
    
    try:
        # Try parsing 'Mon, 20 Jan 2025 03:45:00 GMT' format
        # Note: %Z doesn't reliably parse timezone, so we handle GMT explicitly
        if 'GMT' in str(date_str) or 'UTC' in str(date_str):
            # Remove timezone suffix and parse
            clean_str = str(date_str).replace(' GMT', '').replace(' UTC', '')
            parsed_date = datetime.strptime(clean_str, '%a, %d %b %Y %H:%M:%S')
            # Mark as UTC and convert to IST
            parsed_date = parsed_date.replace(tzinfo=UTC)
            ist_date = parsed_date.astimezone(IST)
            record_time = ist_date.strftime('%Y-%m-%d %H:%M:%S')
            return record_time
    except (ValueError, TypeError) as e:
        logger.debug(f"GMT parsing failed: {e}")
    
    try:
        # Try parsing ISO format with Z (UTC)
        if isinstance(date_str, str) and date_str.endswith('Z'):
            parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            ist_date = parsed_date.astimezone(IST)
            record_time = ist_date.strftime('%Y-%m-%d %H:%M:%S')
            return record_time
    except (ValueError, TypeError) as e:
        logger.debug(f"ISO Z parsing failed: {e}")
    
    try:
        # Try parsing ISO format with timezone info
        if isinstance(date_str, str) and ('+' in date_str or 'T' in date_str):
            parsed_date = datetime.fromisoformat(date_str)
            if parsed_date.tzinfo is not None:
                ist_date = parsed_date.astimezone(IST)
                record_time = ist_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # No timezone, assume already IST
                record_time = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            return record_time
    except (ValueError, TypeError) as e:
        logger.debug(f"ISO parsing failed: {e}")
    
    try:
        # Handle datetime objects directly
        if isinstance(date_str, datetime):
            if date_str.tzinfo is not None:
                ist_date = date_str.astimezone(IST)
                record_time = ist_date.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # No timezone, assume already IST
                record_time = date_str.strftime('%Y-%m-%d %H:%M:%S')
            return record_time
    except (ValueError, TypeError) as e:
        logger.debug(f"Datetime object parsing failed: {e}")
    
    # Use as-is if already in correct format
    logger.info(f"Using as-is: '{date_str}'")
    return date_str

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