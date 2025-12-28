from flask import Flask, request, jsonify, render_template_string
import os
import logging
import sys
from fetcher import KiteDataFetcher
from typing import List, Optional, Dict, Tuple

# Configure logging for Kubernetes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

# Configuration
API_KEY = os.environ.get('API_KEY')
USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
TOTP_KEY = os.getenv("TOTP_KEY")
API_SECRET = os.getenv("API_SECRET")

fetcher = KiteDataFetcher(
    api_key=API_KEY,
    user_name=USER_NAME,
    password=PASSWORD,
    totp_key=TOTP_KEY,
    api_secret=API_SECRET,
    data_folder='data',
    granularity='5minute'
)

@app.route('/')
def index():
    """Serve the HTML form"""
    try:
        logger.info("Serving index page")
        if os.environ.get("BROKER_MIDDLEWARE_TEST"):
            return render_template_string(open('../index.html').read())
        else:
            return render_template_string(open('index.html').read())
    except Exception as e:
        logger.error(f"Error serving index page: {e}")
        return "Error loading page", 500


@app.route('/api/status', methods=['GET'])
def status():
    """Check connection status"""
    try:
        logger.info("Checking connection status")
        result = fetcher.test_connection()
        if result['success']:
            return jsonify(result)
        else:
            logger.error(f"Connection error: {result['error']}")
            logger.info("Refreshing access token and retrying...")
            fetcher.refresh_access_token()
            result = fetcher.test_connection()
            if result['success']:
                return jsonify(result)
            else:
                logger.error(f"Connection error - 2nd attempt: {result['error']}")
                return jsonify({'error': result['error']}), 500
    except Exception as e:
        logger.error(f"Error during connection test: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/data', methods=['GET', 'POST'])
def fetch_data():
    """Fetch stock data"""
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            stocks = data.get('stocks')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            exchanges = data.get('exchanges')
            granularity = data.get('granularity')
            fetcher.granularity = granularity
            result = fetcher.fetch_stock_data_with_retries(
                stocks=stocks,
                start_date=start_date,
                end_date=end_date,
                exchanges=exchanges if exchanges else None
            )
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error during fetch: {e}")
            return jsonify({'error': str(e)}), 500

    elif request.method == 'GET':
        try:
            params = request.args
            stocks = params.getlist('stocks') or None
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            exchanges = params.getlist('exchanges') or None
            granularity = params.get('granularity', '5minute')
            fetcher.granularity = granularity
            result = fetcher.fetch_stock_data_with_retries(
                stocks=stocks,
                start_date=start_date,
                end_date=end_date,
                exchanges=exchanges if exchanges else None
            )
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error during fetch: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid HTTP method'}), 405


@app.route('/api/exchanges', methods=['GET'])
def get_exchanges():
    try:
        """Get available exchanges"""
        return jsonify({
            'exchanges': KiteDataFetcher.EXCHANGES
        })
    except Exception as e:
        logger.error(f"Error fetching exchanges: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/granularities', methods=['GET'])
def get_granularities():
    try:
        """Get available granularities"""
        return jsonify({
            'granularities': KiteDataFetcher.ALLOWED_GRANULARITIES
        })
    except Exception as e:
        logger.error(f"Error fetching granularities: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/symbols', defaults={'exchange': None}, methods=['GET'])
@app.route('/api/symbols/<exchange>', methods=['GET'])
def get_symbols(exchange):
    """Get available symbols"""
    try:
        """Get available symbols"""
        if exchange:
            instruments = fetcher.fetch_instrument_from_exchange(exchange)
        else:
            # Fetch all instruments from all exchanges
            instruments = fetcher.fetch_all_instruments()
        symbols = [inst['tradingsymbol'] for inst in instruments]
        tokens = [inst['instrument_token'] for inst in instruments]
        return jsonify({
            'symbols': symbols,
            'tokens': tokens
        })
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

