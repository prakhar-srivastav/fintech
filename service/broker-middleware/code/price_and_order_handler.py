from kiteconnect import KiteConnect
from typing import Dict, Optional, List
import logging
import time

logger = logging.getLogger(__name__)


class PriceService:
    """Service to fetch live prices from Kite"""
    
    def __init__(self, kite: KiteConnect):
        self.kite = kite
        self._instruments_cache: Dict[str, Dict] = {}
    
    def _get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[int]:
        """Get instrument token for a symbol"""
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._instruments_cache:
            return self._instruments_cache[cache_key].get('instrument_token')
        
        try:
            instruments = self.kite.instruments(exchange)
            for instrument in instruments:
                key = f"{instrument['exchange']}:{instrument['tradingsymbol']}"
                self._instruments_cache[key] = instrument
            
            return self._instruments_cache.get(cache_key, {}).get('instrument_token')
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            return None
    
    def fetch_price(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Fetch live price for a symbol"""
        try:
            instrument_token = self._get_instrument_token(symbol, exchange)
            if not instrument_token:
                return {
                    'success': False,
                    'error': f"Instrument not found: {exchange}:{symbol}"
                }
            
            # Get live quote
            quote_key = f"{exchange}:{symbol}"
            quote = self.kite.quote([quote_key])
            
            if quote_key in quote:
                data = quote[quote_key]
                return {
                    'success': True,
                    'symbol': symbol,
                    'exchange': exchange,
                    'last_price': data.get('last_price'),
                    'open': data.get('ohlc', {}).get('open'),
                    'high': data.get('ohlc', {}).get('high'),
                    'low': data.get('ohlc', {}).get('low'),
                    'close': data.get('ohlc', {}).get('close'),
                    'volume': data.get('volume'),
                    'bid_price': data.get('depth', {}).get('buy', [{}])[0].get('price'),
                    'ask_price': data.get('depth', {}).get('sell', [{}])[0].get('price'),
                    'timestamp': data.get('timestamp')
                }
            else:
                return {
                    'success': False,
                    'error': f"No quote data for {quote_key}"
                }
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def fetch_ltp(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Fetch only Last Traded Price (faster)"""
        try:
            quote_key = f"{exchange}:{symbol}"
            ltp_data = self.kite.ltp([quote_key])
            
            if quote_key in ltp_data:
                return {
                    'success': True,
                    'symbol': symbol,
                    'exchange': exchange,
                    'last_price': ltp_data[quote_key].get('last_price'),
                    'instrument_token': ltp_data[quote_key].get('instrument_token')
                }
            else:
                return {
                    'success': False,
                    'error': f"No LTP data for {quote_key}"
                }
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def fetch_multiple_prices(self, symbols: List[str], exchange: str = "NSE") -> Dict:
        """Fetch live prices for multiple symbols"""
        try:
            quote_keys = [f"{exchange}:{symbol}" for symbol in symbols]
            quotes = self.kite.quote(quote_keys)
            
            results = {}
            for symbol in symbols:
                quote_key = f"{exchange}:{symbol}"
                if quote_key in quotes:
                    data = quotes[quote_key]
                    results[symbol] = {
                        'success': True,
                        'last_price': data.get('last_price'),
                        'volume': data.get('volume'),
                        'change': data.get('change')
                    }
                else:
                    results[symbol] = {
                        'success': False,
                        'error': 'Not found'
                    }
            
            return {'success': True, 'prices': results}
        except Exception as e:
            logger.error(f"Error fetching multiple prices: {e}")
            return {'success': False, 'error': str(e)}


class OrderService:
    """Service to place buy/sell orders via Kite"""
    
    # Order status constants
    STATUS_COMPLETE = "COMPLETE"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"
    
    # Terminal statuses (order won't change after these)
    TERMINAL_STATUSES = ["COMPLETE", "REJECTED", "CANCELLED"]
    
    # Polling config
    MAX_WAIT_SECONDS = 30
    POLL_INTERVAL_SECONDS = 0.5
    
    def __init__(self, kite: KiteConnect, price_service: PriceService):
        self.kite = kite
        self.price_service = price_service
    
    def place_buy_order(
        self,
        symbol: str,
        money_quantity: float,
        exchange: str = "NSE",
    ) -> Dict:
        """
        Place a BUY order using money amount.
        Calculates number of shares based on current price.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE", "INFY")
            money_quantity: Amount of money to invest
            exchange: Exchange (NSE/BSE)
        
        Returns:
            Dict with order_id, shares_bought, price_per_share, total_amount
        """
        return self._place_order(
            transaction_type="BUY",
            symbol=symbol,
            money_quantity=money_quantity,
            exchange=exchange,
        )
    
    def place_sell_order(
        self,
        symbol: str,
        share_quantity: int,
        exchange: str = "NSE",
    ) -> Dict:
        """
        Place a SELL order using share quantity.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE", "INFY")
            share_quantity: Number of shares to sell
            exchange: Exchange (NSE/BSE)
        
        Returns:
            Dict with order_id, shares_sold, price_per_share, total_amount
        """
        return self._place_order(
            transaction_type="SELL",
            symbol=symbol,
            share_quantity=share_quantity,
            exchange=exchange,
        )
    
    def _wait_for_order_completion(self, order_id: str) -> Dict:
        """
        Wait for an order to reach a terminal status (COMPLETE, REJECTED, CANCELLED).
        Polls the order status until completion or timeout.
        
        Returns:
            Dict with final order details including status, filled_quantity, average_price
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.MAX_WAIT_SECONDS:
                return {
                    'success': False,
                    'error': f"Order {order_id} timed out after {self.MAX_WAIT_SECONDS}s",
                    'order_id': order_id,
                    'status': 'TIMEOUT'
                }
            
            try:
                orders = self.kite.orders()
                for order in orders:
                    if order['order_id'] == order_id:
                        status = order.get('status')
                        
                        if status in self.TERMINAL_STATUSES:
                            return {
                                'success': status == self.STATUS_COMPLETE,
                                'order_id': order_id,
                                'status': status,
                                'filled_quantity': order.get('filled_quantity', 0),
                                'pending_quantity': order.get('pending_quantity', 0),
                                'average_price': order.get('average_price'),
                                'transaction_type': order.get('transaction_type'),
                                'tradingsymbol': order.get('tradingsymbol'),
                                'exchange': order.get('exchange'),
                                'status_message': order.get('status_message', ''),
                                'order_timestamp': str(order.get('order_timestamp', '')),
                                'exchange_timestamp': str(order.get('exchange_timestamp', ''))
                            }
                        
                        # Order still pending, continue polling
                        logger.debug(f"Order {order_id} status: {status}, waiting...")
                        break
                
            except Exception as e:
                logger.error(f"Error polling order status: {e}")
            
            time.sleep(self.POLL_INTERVAL_SECONDS)
    
    def _place_order(
        self,
        transaction_type: str,
        symbol: str,
        exchange: str,
        share_quantity: Optional[int] = None,
        money_quantity: Optional[float] = None,
    ) -> Dict:
        """Internal method to place an order"""
        try:
            # Get current price
            price_data = self.price_service.fetch_ltp(symbol, exchange)
            if not price_data['success']:
                return {
                    'success': False,
                    'error': f"Could not fetch price: {price_data.get('error')}"
                }
            
            current_price = price_data['last_price']
            
            if transaction_type == "BUY":
                # Calculate shares from money
                if money_quantity is None or money_quantity <= 0:
                    return {
                        'success': False,
                        'error': "money_quantity must be provided and > 0 for BUY orders"
                    }
                
                # Calculate shares (fractional)
                fractional_shares = money_quantity / current_price
                
                # Kite/Zerodha only supports whole shares - round down
                shares_to_buy = int(fractional_shares)
                if shares_to_buy <= 0:
                    return {
                        'success': False,
                        'error': f"Insufficient funds to buy any shares of {symbol} at ₹{current_price} per share"
                    }
                actual_amount = shares_to_buy * current_price
                order_id = self.kite.place_order(
                    variety="regular",
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                    quantity=shares_to_buy,
                    order_type=self.kite.ORDER_TYPE_MARKET,
                    product=self.kite.PRODUCT_CNC
                )
                
                logger.info(f"BUY order placed: {shares_to_buy} shares of {symbol}, Order ID: {order_id}. Waiting for execution...")
                
                # Wait for order to complete
                order_result = self._wait_for_order_completion(order_id)
                
                if not order_result['success']:
                    return {
                        'success': False,
                        'order_id': order_id,
                        'error': f"Order {order_result['status']}: {order_result.get('status_message', '')}",
                        'status': order_result['status']
                    }
                
                # Order completed successfully - use actual execution price
                executed_price = order_result['average_price'] or current_price
                executed_quantity = order_result['filled_quantity']
                actual_amount = executed_quantity * executed_price
                
                logger.info(f"BUY order COMPLETE: {executed_quantity} shares of {symbol} @ ₹{executed_price} = ₹{actual_amount}")
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'status': 'COMPLETE',
                    'transaction_type': 'BUY',
                    'symbol': symbol,
                    'exchange': exchange,
                    'shares_bought': executed_quantity,
                    'price_per_share': executed_price,
                    'total_amount': actual_amount,
                    'money_provided': money_quantity,
                    'money_remaining': money_quantity - actual_amount,
                    'order_timestamp': order_result.get('order_timestamp'),
                    'exchange_timestamp': order_result.get('exchange_timestamp')
                }
                
            elif transaction_type == "SELL":
                # Use share quantity directly
                if share_quantity is None or share_quantity <= 0:
                    return {
                        'success': False,
                        'error': "share_quantity must be provided and > 0 for SELL orders"
                    }
                
                expected_amount = share_quantity * current_price
                
                order_id = self.kite.place_order(
                    variety="regular",
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=self.kite.TRANSACTION_TYPE_SELL,
                    quantity=share_quantity,
                    order_type=self.kite.ORDER_TYPE_MARKET,
                    product=self.kite.PRODUCT_CNC
                )
                
                logger.info(f"SELL order placed: {share_quantity} shares of {symbol}, Order ID: {order_id}. Waiting for execution...")
                
                # Wait for order to complete
                order_result = self._wait_for_order_completion(order_id)
                
                if not order_result['success']:
                    return {
                        'success': False,
                        'order_id': order_id,
                        'error': f"Order {order_result['status']}: {order_result.get('status_message', '')}",
                        'status': order_result['status']
                    }
                
                # Order completed successfully - use actual execution price
                executed_price = order_result['average_price'] or current_price
                executed_quantity = order_result['filled_quantity']
                actual_amount = executed_quantity * executed_price
                
                logger.info(f"SELL order COMPLETE: {executed_quantity} shares of {symbol} @ ₹{executed_price} = ₹{actual_amount}")
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'status': 'COMPLETE',
                    'transaction_type': 'SELL',
                    'symbol': symbol,
                    'exchange': exchange,
                    'shares_sold': executed_quantity,
                    'price_per_share': executed_price,
                    'total_amount': actual_amount,
                    'order_timestamp': order_result.get('order_timestamp'),
                    'exchange_timestamp': order_result.get('exchange_timestamp')
                }
            
            else:
                return {
                    'success': False,
                    'error': f"Invalid transaction_type: {transaction_type}"
                }

        except Exception as e:
            logger.error(f"Error placing {transaction_type} order for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get the status of an order"""
        try:
            orders = self.kite.orders()
            for order in orders:
                if order['order_id'] == order_id:
                    return {
                        'success': True,
                        'order_id': order_id,
                        'status': order['status'],
                        'filled_quantity': order.get('filled_quantity', 0),
                        'pending_quantity': order.get('pending_quantity', 0),
                        'average_price': order.get('average_price'),
                        'transaction_type': order.get('transaction_type'),
                        'tradingsymbol': order.get('tradingsymbol')
                    }
            
            return {
                'success': False,
                'error': f"Order {order_id} not found"
            }
        except Exception as e:
            logger.error(f"Error getting order status for {order_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_order(self, order_id: str, variety: str = "regular") -> Dict:
        """Cancel a pending order"""
        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            logger.info(f"Order cancelled: {order_id}")
            return {
                'success': True,
                'order_id': order_id,
                'message': 'Order cancelled successfully'
            }
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class GTTService:
    """
    Service to manage GTT (Good Till Triggered) orders via Kite.
    Supports both single trigger and OCO (One Cancels Other) triggers.
    
    GTT Types:
    - single: One trigger price, executes when price crosses the trigger
    - two-leg (OCO): Two triggers (target + stop-loss), whichever triggers first executes
    """
    
    # GTT status constants
    STATUS_ACTIVE = "active"
    STATUS_TRIGGERED = "triggered"
    STATUS_DISABLED = "disabled"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELLED = "cancelled"
    STATUS_REJECTED = "rejected"
    
    def __init__(self, kite: KiteConnect, price_service: PriceService):
        self.kite = kite
        self.price_service = price_service
    
    def place_single_gtt(
        self,
        symbol: str,
        trigger_price: float,
        quantity: int,
        transaction_type: str = "SELL",  # BUY or SELL
        limit_price: Optional[float] = None,
        exchange: str = "NSE"
    ) -> Dict:
        """
        Place a single trigger GTT order.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
            trigger_price: Price at which the order should trigger
            quantity: Number of shares
            transaction_type: BUY or SELL
            limit_price: Order price (if None, uses trigger_price)
            exchange: Exchange (NSE/BSE)
        
        Returns:
            Dict with trigger_id and details
        """
        try:
            # Get current price (LTP) - required for GTT
            price_data = self.price_service.fetch_ltp(symbol, exchange)
            if not price_data['success']:
                return {
                    'success': False,
                    'error': f"Could not fetch price: {price_data.get('error')}"
                }
            
            last_price = price_data['last_price']
            
            # If no limit_price specified, use trigger_price
            if limit_price is None:
                limit_price = trigger_price
            
            # Validate trigger direction
            if transaction_type == "SELL":
                # For sell, trigger should generally be below current price (stop-loss)
                # or above current price (target) - both are valid
                pass
            elif transaction_type == "BUY":
                # For buy, trigger can be above or below current price
                pass
            
            # Place GTT order
            trigger_id = self.kite.place_gtt(
                trigger_type=self.kite.GTT_TYPE_SINGLE,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=[trigger_price],
                last_price=last_price,
                orders=[{
                    "exchange": exchange,
                    "tradingsymbol": symbol,
                    "transaction_type": transaction_type,
                    "quantity": quantity,
                    "order_type": self.kite.ORDER_TYPE_LIMIT,
                    "product": self.kite.PRODUCT_CNC,
                    "price": limit_price
                }]
            )
            
            logger.info(f"Single GTT placed: {symbol} {transaction_type} {quantity} @ trigger ₹{trigger_price}, ID: {trigger_id}")
            
            return {
                'success': True,
                'trigger_id': trigger_id,
                'gtt_type': 'single',
                'symbol': symbol,
                'exchange': exchange,
                'transaction_type': transaction_type,
                'quantity': quantity,
                'trigger_price': trigger_price,
                'limit_price': limit_price,
                'last_price': last_price,
                'message': f"GTT order placed. Will execute when {symbol} reaches ₹{trigger_price}"
            }
            
        except Exception as e:
            logger.error(f"Error placing single GTT for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_oco_gtt(
        self,
        symbol: str,
        quantity: int,
        target_trigger_price: float,
        target_limit_price: Optional[float] = None,
        stoploss_trigger_price: float = None,
        stoploss_limit_price: Optional[float] = None,
        exchange: str = "NSE"
    ) -> Dict:
        """
        Place an OCO (One Cancels Other) GTT order for position management.
        
        This is typically used AFTER buying shares:
        - Set a target price (sell when price goes UP)
        - Set a stop-loss price (sell when price goes DOWN)
        Whichever triggers first executes, and the other is cancelled.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE")
            quantity: Number of shares to sell
            target_trigger_price: Price to sell at for profit (upper trigger)
            target_limit_price: Limit price for target order (optional)
            stoploss_trigger_price: Price to sell at to limit loss (lower trigger)
            stoploss_limit_price: Limit price for stop-loss order (optional)
            exchange: Exchange (NSE/BSE)
        
        Returns:
            Dict with trigger_id and OCO details
        """
        try:
            # Validate inputs
            if not stoploss_trigger_price:
                return {
                    'success': False,
                    'error': "stoploss_trigger_price is required for OCO orders"
                }
            
            # Get current price (LTP) - required for GTT
            price_data = self.price_service.fetch_ltp(symbol, exchange)
            if not price_data['success']:
                return {
                    'success': False,
                    'error': f"Could not fetch price: {price_data.get('error')}"
                }
            
            last_price = price_data['last_price']
            
            # Validate trigger prices relative to current price
            if target_trigger_price <= last_price:
                return {
                    'success': False,
                    'error': f"Target price (₹{target_trigger_price}) must be above current price (₹{last_price})"
                }
            
            if stoploss_trigger_price >= last_price:
                return {
                    'success': False,
                    'error': f"Stop-loss price (₹{stoploss_trigger_price}) must be below current price (₹{last_price})"
                }
            
            if stoploss_trigger_price >= target_trigger_price:
                return {
                    'success': False,
                    'error': f"Stop-loss price (₹{stoploss_trigger_price}) must be below target price (₹{target_trigger_price})"
                }
            
            # Set limit prices if not provided
            # For target: limit slightly below trigger (safer execution)
            if target_limit_price is None:
                target_limit_price = target_trigger_price * 0.995  # 0.5% below trigger
            
            # For stop-loss: limit slightly below trigger (market might gap down)
            if stoploss_limit_price is None:
                stoploss_limit_price = stoploss_trigger_price * 0.99  # 1% below trigger
            
            # Place OCO GTT - trigger_values is [stoploss, target] in ascending order
            trigger_id = self.kite.place_gtt(
                trigger_type=self.kite.GTT_TYPE_OCO,
                tradingsymbol=symbol,
                exchange=exchange,
                trigger_values=[stoploss_trigger_price, target_trigger_price],  # Must be ascending
                last_price=last_price,
                orders=[
                    # Stop-loss order (first trigger - lower price)
                    {
                        "exchange": exchange,
                        "tradingsymbol": symbol,
                        "transaction_type": "SELL",
                        "quantity": quantity,
                        "order_type": self.kite.ORDER_TYPE_LIMIT,
                        "product": self.kite.PRODUCT_CNC,
                        "price": stoploss_limit_price
                    },
                    # Target order (second trigger - higher price)
                    {
                        "exchange": exchange,
                        "tradingsymbol": symbol,
                        "transaction_type": "SELL",
                        "quantity": quantity,
                        "order_type": self.kite.ORDER_TYPE_LIMIT,
                        "product": self.kite.PRODUCT_CNC,
                        "price": target_limit_price
                    }
                ]
            )
            
            # Calculate potential profit/loss
            potential_profit = (target_trigger_price - last_price) * quantity
            potential_loss = (last_price - stoploss_trigger_price) * quantity
            
            logger.info(f"OCO GTT placed: {symbol} x{quantity}, Target: ₹{target_trigger_price}, SL: ₹{stoploss_trigger_price}, ID: {trigger_id}")
            
            return {
                'success': True,
                'trigger_id': trigger_id,
                'gtt_type': 'oco',
                'symbol': symbol,
                'exchange': exchange,
                'quantity': quantity,
                'current_price': last_price,
                'target': {
                    'trigger_price': target_trigger_price,
                    'limit_price': round(target_limit_price, 2),
                    'potential_profit': round(potential_profit, 2),
                    'profit_percent': round((target_trigger_price - last_price) / last_price * 100, 2)
                },
                'stoploss': {
                    'trigger_price': stoploss_trigger_price,
                    'limit_price': round(stoploss_limit_price, 2),
                    'potential_loss': round(potential_loss, 2),
                    'loss_percent': round((last_price - stoploss_trigger_price) / last_price * 100, 2)
                },
                'message': f"OCO GTT placed. Sell {quantity} of {symbol} when price hits target (₹{target_trigger_price}) OR stop-loss (₹{stoploss_trigger_price})"
            }
            
        except Exception as e:
            logger.error(f"Error placing OCO GTT for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_gtt_orders(self) -> Dict:
        """Get all active GTT orders"""
        try:
            gtts = self.kite.get_gtts()
            
            return {
                'success': True,
                'gtts': [{
                    'id': gtt['id'],
                    'symbol': gtt['condition']['tradingsymbol'],
                    'exchange': gtt['condition']['exchange'],
                    'trigger_type': gtt['type'],
                    'status': gtt['status'],
                    'trigger_values': gtt['condition']['trigger_values'],
                    'last_price': gtt['condition']['last_price'],
                    'created_at': str(gtt.get('created_at', '')),
                    'updated_at': str(gtt.get('updated_at', '')),
                    'orders': gtt.get('orders', [])
                } for gtt in gtts],
                'count': len(gtts)
            }
        except Exception as e:
            logger.error(f"Error fetching GTT orders: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_gtt_order(self, trigger_id: int) -> Dict:
        """Get details of a specific GTT order"""
        try:
            gtt = self.kite.get_gtt(trigger_id)
            
            return {
                'success': True,
                'id': gtt['id'],
                'symbol': gtt['condition']['tradingsymbol'],
                'exchange': gtt['condition']['exchange'],
                'trigger_type': gtt['type'],
                'status': gtt['status'],
                'trigger_values': gtt['condition']['trigger_values'],
                'last_price': gtt['condition']['last_price'],
                'created_at': str(gtt.get('created_at', '')),
                'updated_at': str(gtt.get('updated_at', '')),
                'orders': gtt.get('orders', []),
                'meta': gtt.get('meta', {})
            }
        except Exception as e:
            logger.error(f"Error fetching GTT order {trigger_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_gtt(self, trigger_id: int) -> Dict:
        """Cancel a GTT order"""
        try:
            self.kite.delete_gtt(trigger_id)
            logger.info(f"GTT cancelled: {trigger_id}")
            
            return {
                'success': True,
                'trigger_id': trigger_id,
                'message': 'GTT order cancelled successfully'
            }
        except Exception as e:
            logger.error(f"Error cancelling GTT {trigger_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class PriceAndOrderHandler:
    """
    Combined handler for price fetching and order management.
    Provides a unified interface for trading operations.
    """
    
    def __init__(self, kite: KiteConnect):
        """
        Initialize with a KiteConnect instance.
        
        Args:
            kite: Authenticated KiteConnect instance
        """
        self.kite = kite
        self.price_service = PriceService(kite)
        self.order_service = OrderService(kite, self.price_service)
        self.gtt_service = GTTService(kite, self.price_service)
    
    # ==================== Price Methods ====================
    
    def get_live_price(self, symbol: str, exchange: str = "NSE") -> Dict:
        return self.price_service.fetch_price(symbol, exchange)
    
    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Dict:
        return self.price_service.fetch_ltp(symbol, exchange)
    
    def get_multiple_prices(self, symbols: List[str], exchange: str = "NSE") -> Dict:
        return self.price_service.fetch_multiple_prices(symbols, exchange)
    
    # ==================== Order Methods ====================

    def buy(
        self,
        symbol: str,
        money_quantity: float,
        exchange: str = "NSE",
    ) -> Dict:
        return self.order_service.place_buy_order(
            symbol=symbol,
            money_quantity=money_quantity,
            exchange=exchange,
        )
    
    def sell(
        self,
        symbol: str,
        share_quantity: int,
        exchange: str = "NSE",
    ) -> Dict:
        return self.order_service.place_sell_order(
            symbol=symbol,
            share_quantity=share_quantity,
            exchange=exchange
        )
    
    def get_order_status(self, order_id: str) -> Dict:
        return self.order_service.get_order_status(order_id)
    
    def cancel_order(self, order_id: str) -> Dict:
        return self.order_service.cancel_order(order_id)
    
    # ==================== GTT Methods ====================

    def create_single_gtt(
        self,
        symbol: str,
        trigger_price: float,
        quantity: int,
        transaction_type: str = "SELL",
        limit_price: Optional[float] = None,
        exchange: str = "NSE"
    ) -> Dict:
        return self.gtt_service.place_single_gtt(
            symbol=symbol,
            trigger_price=trigger_price,
            quantity=quantity,
            transaction_type=transaction_type,
            limit_price=limit_price,
            exchange=exchange
        )
    
    def create_oco_gtt(
        self,
        symbol: str,
        quantity: int,
        target_trigger_price: float,
        target_limit_price: Optional[float] = None,
        stoploss_trigger_price: float = None,
        stoploss_limit_price: Optional[float] = None,
        exchange: str = "NSE"
    ) -> Dict:
        return self.gtt_service.place_oco_gtt(
            symbol=symbol,
            quantity=quantity,
            target_trigger_price=target_trigger_price,
            target_limit_price=target_limit_price,
            stoploss_trigger_price=stoploss_trigger_price,
            stoploss_limit_price=stoploss_limit_price,
            exchange=exchange
        )
    
    def get_gtt_orders(self) -> Dict:
        return self.gtt_service.get_gtt_orders()
    
    def get_gtt_order(self, trigger_id: int) -> Dict:
        return self.gtt_service.get_gtt_order(trigger_id)
    
    def cancel_gtt(self, trigger_id: int) -> Dict:
        return self.gtt_service.cancel_gtt(trigger_id)
