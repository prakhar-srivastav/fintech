import threading
import queue
import time
from datetime import datetime
import os
from flask import Flask, request, jsonify
import requests
import sqlite3
import mysql.connector
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from broker_middleware_client import BrokerMiddlewareClient

app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour, 10 per minute"]
)

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

"""
TODO: create a db_client.py file to handle all db related operations
1. insert_data -> the actual query execution to be handled there with date parsing etc
2. db_config handling
3. add test for exchange, status, symbols fetching from broker middleware
4. add other cases where exchange/symbols are not given etc
5. make it deployable with proper config management
"""

BROKER_MIDDLEWARE_URL = os.environ.get("BROKER_MIDDLEWARE_URL", "http://localhost:8080")

broker_client = BrokerMiddlewareClient(base_url=BROKER_MIDDLEWARE_URL)

def fetch_from_broker_middleware(start_date, end_date, stocks, exchange, granularity):
    return broker_client.fetch_data(
        stocks=stocks,
        start_date=start_date,
        end_date=end_date,
        exchanges=exchange,
        granularity=granularity
    )

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

def update_db(data):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    items = data['items']
    for stocks in items.keys():
        stocks_data = items[stocks]
        rows = stocks_data['rows']
        exchange = stocks_data['exchange']
        granularity = stocks_data['granularity']
        for row in rows:

            when_added = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Parse the date from various formats and convert to MySQL datetime format
            raw_date = row.get('date')
            parsed_date = convert_to_mysql_datetime(raw_date)
            record_time = parsed_date
            _open = row.get('open')
            _close = row.get('close')
            _low = row.get('low')
            _high = row.get('high')
            _volume = row.get('volume')

            cursor.execute(
                """
                INSERT INTO broker_data 
                (when_added, record_time, stocks, exchange, open, close, low, high, volume, broker_name, granularity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    when_added,
                    record_time,
                    stocks,
                    exchange,
                    _open,
                    _close,
                    _low,
                    _high,
                    _volume,
                    "zerodha",
                    granularity
                )
            )
    conn.commit()
    cursor.close()
    conn.close()

def process_data(payload):
    start_date = payload['start_date']
    end_date = payload['end_date']
    stocks = payload['stocks']
    exchange = payload['exchanges']
    granularity = payload['granularity']
    data = fetch_from_broker_middleware(start_date=start_date, end_date=end_date, stocks=stocks, exchange=exchange, granularity=granularity)
    if data:
        update_db(data)
    return data

@app.route('/sync', methods=['POST'])
@limiter.limit("5 per minute")
def sync():
    try:
        req_data = request.json
        print(f"Received sync request: {req_data}")
        payload = req_data.get('payload')
        process_data(payload)
        return jsonify({"status": "true", "items": payload[0]}), 202
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"status": "false", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)