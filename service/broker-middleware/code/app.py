from flask import Flask, request, jsonify, render_template_string
import os
import logging
import sys
from fetcher import KiteDataFetcher
from price_and_order_handler import PriceAndOrderHandler
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

# Initialize PriceAndOrderHandler with the same Kite instance
order_handler = PriceAndOrderHandler(fetcher.kite)

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
            logger.info(f"Fetched data for stocks: {stocks}")
            logger.info(f"Data fetch result: {result}")
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


# ==================== Price API ====================

@app.route('/api/price/<symbol>', methods=['GET'])
def get_price(symbol):
    """
    Get live price for a symbol.
    
    Query params:
        exchange: NSE (default) or BSE
    
    Example: GET /api/price/RELIANCE?exchange=NSE
    """
    try:
        exchange = request.args.get('exchange', 'NSE')
        logger.info(f"Fetching price for {exchange}:{symbol}")
        
        result = order_handler.get_live_price(symbol, exchange)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/price/ltp/<symbol>', methods=['GET'])
def get_ltp(symbol):
    """
    Get Last Traded Price (LTP) only - faster than full quote.
    
    Query params:
        exchange: NSE (default) or BSE
    
    Example: GET /api/price/ltp/RELIANCE?exchange=NSE
    """
    try:
        exchange = request.args.get('exchange', 'NSE')
        logger.info(f"Fetching LTP for {exchange}:{symbol}")
        
        result = order_handler.get_ltp(symbol, exchange)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error fetching LTP for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/price/multiple', methods=['POST'])
def get_multiple_prices():
    """
    Get live prices for multiple symbols.
    
    Request body:
        {
            "symbols": ["RELIANCE", "INFY", "TCS"],
            "exchange": "NSE"  // optional, default NSE
        }
    """
    try:
        data = request.get_json(force=True)
        symbols = data.get('symbols', [])
        exchange = data.get('exchange', 'NSE')
        
        if not symbols:
            return jsonify({'success': False, 'error': 'symbols list is required'}), 400
        
        logger.info(f"Fetching prices for {len(symbols)} symbols on {exchange}")
        
        result = order_handler.get_multiple_prices(symbols, exchange)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching multiple prices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Order API ====================

@app.route('/api/order/buy', methods=['POST'])
def place_buy_order():
    """
    Place a BUY order using money amount.
    Calculates shares based on current price and waits for order execution.
    
    Request body:
        {
            "symbol": "RELIANCE",
            "money": 50000,           // Amount to invest in INR
            "exchange": "NSE"         // optional, default NSE
        }
    
    Response:
        {
            "success": true,
            "order_id": "123456789",
            "status": "COMPLETE",
            "shares_bought": 20,
            "price_per_share": 2498.50,
            "total_amount": 49970.0,
            "money_provided": 50000,
            "money_remaining": 30.0
        }
    """
    try:
        data = request.get_json(force=True)
        symbol = data.get('symbol')
        money = data.get('money')
        exchange = data.get('exchange', 'NSE')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'symbol is required'}), 400
        if not money or money <= 0:
            return jsonify({'success': False, 'error': 'money must be a positive number'}), 400
        
        logger.info(f"Placing BUY order: {symbol} on {exchange} with ₹{money}")
        
        result = order_handler.buy(
            symbol=symbol,
            money_quantity=float(money),
            exchange=exchange
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error placing buy order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/order/sell', methods=['POST'])
def place_sell_order():
    """
    Place a SELL order using share quantity.
    Waits for order execution before returning.
    
    Request body:
        {
            "symbol": "RELIANCE",
            "quantity": 10,           // Number of shares to sell
            "exchange": "NSE"         // optional, default NSE
        }
    
    Response:
        {
            "success": true,
            "order_id": "123456790",
            "status": "COMPLETE",
            "shares_sold": 10,
            "price_per_share": 2501.25,
            "total_amount": 25012.50
        }
    """
    try:
        data = request.get_json(force=True)
        symbol = data.get('symbol')
        quantity = data.get('quantity')
        exchange = data.get('exchange', 'NSE')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'symbol is required'}), 400
        if not quantity or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be a positive number'}), 400
        
        logger.info(f"Placing SELL order: {quantity} shares of {symbol} on {exchange}")
        
        result = order_handler.sell(
            symbol=symbol,
            share_quantity=float(quantity),
            exchange=exchange
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error placing sell order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/order/status/<order_id>', methods=['GET'])
def get_order_status(order_id):
    """
    Get the status of an order.
    
    Example: GET /api/order/status/123456789
    """
    try:
        logger.info(f"Fetching order status for {order_id}")
        
        result = order_handler.get_order_status(order_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error fetching order status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/order/cancel/<order_id>', methods=['POST', 'DELETE'])
def cancel_order(order_id):
    """
    Cancel a pending order.
    
    Example: POST /api/order/cancel/123456789
    """
    try:
        logger.info(f"Cancelling order {order_id}")
        
        result = order_handler.cancel_order(order_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== GTT (Good Till Triggered) Order API ====================

@app.route('/api/gtt/single', methods=['POST'])
def place_single_gtt():
    """
    Place a single trigger GTT order.
    
    Request body:
        {
            "symbol": "RELIANCE",
            "trigger_price": 2400,       // Price at which order triggers
            "quantity": 10,               // Number of shares
            "transaction_type": "SELL",   // BUY or SELL (default: SELL)
            "limit_price": 2395,          // Optional: execution price (default: trigger_price)
            "exchange": "NSE"             // Optional, default NSE
        }
    
    Example use cases:
        - Stop-loss: SELL when price drops to trigger
        - Target: SELL when price rises to trigger
        - Buy on breakout: BUY when price rises above resistance
    """
    try:
        data = request.get_json(force=True)
        symbol = data.get('symbol')
        trigger_price = data.get('trigger_price')
        quantity = data.get('quantity')
        transaction_type = data.get('transaction_type', 'SELL')
        limit_price = data.get('limit_price')
        exchange = data.get('exchange', 'NSE')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'symbol is required'}), 400
        if not trigger_price or trigger_price <= 0:
            return jsonify({'success': False, 'error': 'trigger_price must be a positive number'}), 400
        if not quantity or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be a positive number'}), 400
        
        logger.info(f"Placing single GTT: {transaction_type} {quantity} {symbol} @ trigger ₹{trigger_price}")
        
        result = order_handler.create_single_gtt(
            symbol=symbol,
            trigger_price=float(trigger_price),
            quantity=int(quantity),
            transaction_type=transaction_type,
            limit_price=float(limit_price) if limit_price else None,
            exchange=exchange
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error placing single GTT: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gtt/oco', methods=['POST'])
def place_oco_gtt():
    """
    Place an OCO (One Cancels Other) GTT order for position management.
    
    This is typically used AFTER buying shares to set both:
    - Target price (sell for profit)
    - Stop-loss price (sell to limit loss)
    
    Whichever price is hit first, that order executes and the other is cancelled.
    
    Request body:
        {
            "symbol": "RELIANCE",
            "quantity": 10,                    // Shares to sell
            "target_trigger_price": 2700,      // Sell at this price for profit
            "target_limit_price": 2695,        // Optional: limit price for target
            "stoploss_trigger_price": 2400,    // Sell at this price to limit loss
            "stoploss_limit_price": 2380,      // Optional: limit price for stop-loss
            "exchange": "NSE"                  // Optional, default NSE
        }
    
    Example:
        - Buy RELIANCE at ₹2500
        - Place OCO GTT:
          - Target: ₹2700 (₹200 profit/share)
          - Stop-loss: ₹2400 (₹100 loss/share)
        - If price goes to ₹2700 first → target executes, stop-loss cancelled
        - If price drops to ₹2400 first → stop-loss executes, target cancelled
    
    Response includes potential profit/loss calculations.
    """
    try:
        data = request.get_json(force=True)
        symbol = data.get('symbol')
        quantity = data.get('quantity')
        target_trigger_price = data.get('target_trigger_price')
        target_limit_price = data.get('target_limit_price')
        stoploss_trigger_price = data.get('stoploss_trigger_price')
        stoploss_limit_price = data.get('stoploss_limit_price')
        exchange = data.get('exchange', 'NSE')
        
        if not symbol:
            return jsonify({'success': False, 'error': 'symbol is required'}), 400
        if not quantity or quantity <= 0:
            return jsonify({'success': False, 'error': 'quantity must be a positive number'}), 400
        if not target_trigger_price or target_trigger_price <= 0:
            return jsonify({'success': False, 'error': 'target_trigger_price must be a positive number'}), 400
        if not stoploss_trigger_price or stoploss_trigger_price <= 0:
            return jsonify({'success': False, 'error': 'stoploss_trigger_price must be a positive number'}), 400
        
        logger.info(f"Placing OCO GTT: {symbol} x{quantity}, Target: ₹{target_trigger_price}, SL: ₹{stoploss_trigger_price}")
        
        result = order_handler.create_oco_gtt(
            symbol=symbol,
            quantity=int(quantity),
            target_trigger_price=float(target_trigger_price),
            target_limit_price=float(target_limit_price) if target_limit_price else None,
            stoploss_trigger_price=float(stoploss_trigger_price),
            stoploss_limit_price=float(stoploss_limit_price) if stoploss_limit_price else None,
            exchange=exchange
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error placing OCO GTT: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gtt', methods=['GET'])
def get_gtt_orders():
    """
    Get all GTT orders (active, triggered, etc.)
    
    Example: GET /api/gtt
    """
    try:
        logger.info("Fetching all GTT orders")
        
        result = order_handler.get_gtt_orders()
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error fetching GTT orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gtt/<int:trigger_id>', methods=['GET'])
def get_gtt_order(trigger_id):
    """
    Get details of a specific GTT order.
    
    Example: GET /api/gtt/123456
    """
    try:
        logger.info(f"Fetching GTT order {trigger_id}")
        
        result = order_handler.get_gtt_order(trigger_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error fetching GTT order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/gtt/<int:trigger_id>', methods=['DELETE'])
def cancel_gtt_order(trigger_id):
    """
    Cancel a GTT order.
    
    Example: DELETE /api/gtt/123456
    """
    try:
        logger.info(f"Cancelling GTT order {trigger_id}")
        
        result = order_handler.cancel_gtt(trigger_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error cancelling GTT order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

