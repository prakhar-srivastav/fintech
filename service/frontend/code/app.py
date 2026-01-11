from flask import Flask, render_template, jsonify, request
import mysql.connector
import os
import logging
import sys
from datetime import datetime, timedelta

from data_ingester_client import DataIngesterClient
from db_client import DBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

DATA_INGESTER_URL = os.environ.get('DATA_INGESTER_URL', 'http://localhost:8000')

data_ingester_client = DataIngesterClient(base_url=DATA_INGESTER_URL)

db_client = DBClient(DB_CONFIG)


@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('index.html')

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get list of all stocks from an exchange"""
    try:
        exchange = request.args.get('exchange')
        if not exchange:
            return jsonify({'error': 'Exchange is required'}), 400
        stocks = data_ingester_client.get_symbols(exchange=exchange)
        return jsonify({'stocks': stocks['symbols'][:100]})
    except Exception as e:
        logger.error(f"Error fetching stocks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exchanges', methods=['GET'])
def get_exchanges():
    """Get list of available exchanges"""
    try:
        exchanges = data_ingester_client.get_exchanges()
        return jsonify(exchanges)
    except Exception as e:
        logger.error(f"Error fetching exchanges: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/granularities', methods=['GET'])
def get_granularities():
    """Get list of available granularities"""
    try:
        granularities = data_ingester_client.get_granularities()
        return jsonify(granularities)
    except Exception as e:
        logger.error(f"Error fetching granularities: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_stock_data():
    """
    1. First sync data from broker via data_ingester_client
    2. Then pull data from database via db_client
    """
    try:
        # Get request parameters
        stock = request.args.get('stock')
        exchange = request.args.get('exchange')
        granularity = request.args.get('granularity', '5minute')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Validate required parameters
        if not stock:
            return jsonify({'error': 'Stock symbol is required'}), 400
        if not exchange:
            return jsonify({'error': 'Exchange is required'}), 400
        
        # Set default date range if not provided (last 7 days)
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Step 1: Sync data from broker (unless skip_sync is true)
        sync_result = None
        logger.info(f"Syncing data for {stock} on {exchange} from {start_date} to {end_date}")
        try:
            sync_result = data_ingester_client.sync_stocks(
                stocks=[stock],
                exchanges=[exchange],
                granularity=granularity,
                start_date=start_date,
                end_date=end_date
            )
            logger.info(f"Sync result: {sync_result}")
        except Exception as sync_error:
            logger.warning(f"Sync failed, will try to fetch from DB anyway: {sync_error}")
            sync_result = {'error': str(sync_error)}
        
        # Step 2: Pull data from database
        logger.info(f"Fetching data from DB for {stock}")
        data = db_client.get_stock_data(
            stock=stock,
            exchange=exchange,
            granularity=granularity,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"Error fetching stock data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get summary statistics"""
    try:
        summary = db_client.get_summary()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8089, debug=True)
