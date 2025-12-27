import threading
import queue
import time
import os
from flask import Flask, request, jsonify
import requests
import sqlite3
import mysql.connector

app = Flask(__name__)

'''

prakharsrivastava@Prakhars-MacBook-Pro-2 fintech % curl -X POST http://localhost:8080/api/data \
-H "Content-Type: application/json" \
-d '{
    "stocks": ["RELIANCE"],
    "start_date": "2025-01-19",
    "end_date": "2025-12-22",
    "exchanges": ["NSE","BSE"],
    "granularity": "5minute"
}'

'''

BROKER_MIDDLEWARE_URL = os.environ.get("BROKER_MIDDLEWARE_URL", "http://localhost:51038")
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

def fetch_from_broker(start_date, end_date, symbols, exchange, granularity):
    url = f"http://{BROKER_MIDDLEWARE_URL}/data"
    params = {
        'start_date': start_date,
        'end_date': end_date,
        'symbols': symbols,
        'exchange': exchange,
        'granularity': granularity
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def update_db(data):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    for row in data:
        symbol = row.get('symbol')
        exchange = row.get('exchange')
        date = row.get('when_added')
        granularity = row.get('granularity')
        cursor.execute(
            "SELECT 1 FROM broker_data WHERE symbol=%s AND exchange=%s AND when_added=%s AND granularity=%s",
            (symbol, exchange, date, granularity)
        )
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(
                """
                INSERT INTO broker_data 
                (when_added, symbol, exchange, open, close, low, high, volume, broker_name, granularity)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row.get('when_added'),
                    symbol,
                    exchange,
                    row.get('open'),
                    row.get('close'),
                    row.get('low'),
                    row.get('high'),
                    row.get('volume'),
                    row.get('broker_name'),
                    granularity
                )
            )
    conn.commit()
    cursor.close()
    conn.close()

def validate_if_data_exists(start_date, end_date, symbols, exchange, granularity):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    query = """
    SELECT COUNT(*) FROM broker_data
    WHERE symbol = %s AND exchange = %s AND when_added >= %s AND when_added <= %s AND granularity = %s
    """
    cursor.execute(query, (symbols, exchange, start_date, end_date, granularity))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    print(f"Data existence check: {count} records found for {symbols} from {start_date} to {end_date}")
    return count > 0 

def process_data(items):
    for item in items:
        start_date = item.get('start_date', '2024-01-01')
        end_date = item.get('end_date', 'today')
        symbols = item.get('symbols', None)
        exchange = item.get('exchanges', None)
        granularity = item.get('granularity', '5minute')
        is_present = validate_if_data_exists(start_date, end_date, symbols, exchange, granularity)
        if is_present:
            print(f"Data already present for {symbols} from {start_date} to {end_date}. Skipping fetch.")
            continue
        else:
            data = fetch_from_broker(start_date=start_date, end_date=end_date, symbols=symbols, exchange=exchange, granularity=granularity)
            if data:
                update_db(data)

# TODO: limit the rate of requests to this endpoint
@app.route('/sync', methods=['POST'])
def sync():
    try:
        req_data = request.json
        print(f"Received sync request: {req_data}")
        items = req_data.get('items')
        process_data(items)
        return jsonify({"status": "true", "items": items[0]}), 202
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"status": "false", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

"""
- curl -X POST http://localhost:8000/sync -H "Content-Type: application/json" -d '{
    "items": [
        {
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
            "symbols": "AAPL",
            "exchanges": "NASDAQ",
            "granularity": "5minute"
        }
    ]
}'
"""