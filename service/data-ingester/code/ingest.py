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
from db_client import DBClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour, 10 per minute"]
)


BROKER_MIDDLEWARE_URL = os.environ.get("BROKER_MIDDLEWARE_URL", "http://localhost:8080")

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}


broker_client = BrokerMiddlewareClient(base_url=BROKER_MIDDLEWARE_URL)
db_client = DBClient(DB_CONFIG)


def transform_data_for_ingestion(data):
    items = data['items']
    broker_data_rows = []
    for item in items:
        stock = item['symbol']
        rows = item['rows']
        exchange = item['exchange']
        granularity = item['granularity']
        for row in rows:
            broker_data_rows.append({
                'stock': stock,
                'exchange': exchange,
                'granularity': granularity,
                'record_time': row.get('date'),
                'open': row.get('open'),
                'close': row.get('close'),
                'low': row.get('low'),
                'high': row.get('high'),
                'volume': row.get('volume'),
                'broker_name': 'zerodha',
            })
    return broker_data_rows


def process_data(payload):

    if 'exchanges' not in payload or not payload['exchanges']:
        logging.info("No exchanges provided in payload, fetching all exchanges.")
        exchanges = broker_client.get_exchanges()['exchanges']
    else:
        exchanges = payload['exchanges']

    if 'stocks' not in payload or not payload['stocks']:
        logging.info("No stocks provided in payload, fetching all stocks.")
        stocks = []
        for exchange in exchanges:
            stocks.extend(broker_client.get_symbols(exchange)['symbols'])
        logging.info(f"Fetched stocks: {stocks}")
    else:
        stocks = payload['stocks']

    start_date = payload['start_date']
    end_date = payload['end_date']
    granularity = payload['granularity']

    data = broker_client.fetch_data(
        stocks=stocks,
        start_date=start_date,
        end_date=end_date,
        exchanges=exchanges,
        granularity=granularity
    )
    logger.info(f"Fetched data: {data}")
    if data:
        broker_data_rows = transform_data_for_ingestion(data)
        db_client.insert_broker_data(broker_data_rows)


    return data


@app.route('/sync', methods=['POST'])
@limiter.limit("7 per minute")
def sync():
    try:
        req_data = request.json
        logging.info(f"Received sync request: {req_data}")
        payload = req_data.get('payload')
        process_data(payload)
        return jsonify({"status": "true"}), 202
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"status": "false", "error": str(e)}), 500


@app.route('/exchanges', methods=['GET'])
def get_exchanges():
    try:
        exchanges = broker_client.get_exchanges()
        return jsonify(exchanges), 200
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"status": "false", "error": str(e)}), 500


@app.route('/symbols', methods=['GET'])
def get_symbols():
    try:
        exchange = request.args.get('exchange')
        symbols = broker_client.get_symbols(exchange=exchange)
        return jsonify(symbols), 200
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"status": "false", "error": str(e)}), 500


@app.route('/granularities', methods=['GET'])
def get_granularities():
    try:
        granularities = broker_client.get_granularities()
        return jsonify(granularities), 200
    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"status": "false", "error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "data-ingester is running"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)