import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path to import strategy_engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy_engine import StrategyEngine, Mode, StockType

class TestStrategyEngine(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.engine = StrategyEngine(Mode.MARKET_SIMULATION)
        
        # Create sample stock data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        np.random.seed(42)  # For reproducible tests
        
        # Generate sample OHLC data
        self.sample_data = {}
        stock_symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']
        
        for symbol in stock_symbols:
            base_price = np.random.uniform(100, 1000)
            price_changes = np.random.normal(0, 0.02, len(dates))
            prices = [base_price]
            
            for change in price_changes[1:]:
                new_price = prices[-1] * (1 + change)
                prices.append(max(new_price, 1))  # Ensure positive prices
            
            # Create OHLC data
            df = pd.DataFrame(index=dates)
            df['close'] = prices
            df['open'] = df['close'].shift(1).fillna(df['close'].iloc[0])
            df['high'] = df[['open', 'close']].max(axis=1) * (1 + np.random.uniform(0, 0.01, len(df)))
            df['low'] = df[['open', 'close']].min(axis=1) * (1 - np.random.uniform(0, 0.01, len(df)))
            df['volume'] = np.random.randint(10000, 100000, len(df))
            
            self.sample_data[symbol] = df
    
    def test_initialization(self):
        """Test StrategyEngine initialization"""
        self.assertEqual(self.engine.mode, Mode.MARKET_SIMULATION)
        self.assertEqual(self.engine.strategy_params['y_days'], 30)
        self.assertEqual(self.engine.strategy_params['stop_loss_percent'], 5.0)
        self.assertEqual(len(self.engine.selected_stocks), 0)
    
    def test_stock_selection(self):
        """Test stock selection functionality"""
        stock_types = [StockType.CLASSIC, StockType.CRYPTO, StockType.MUTUAL]
        selected = self.engine.select_stocks(stock_types, stocks_per_group=3)
        
        # Check if all stock types are selected
        self.assertIn('technology', selected)
        self.assertIn('banking', selected)
        self.assertIn('crypto', selected)
        self.assertIn('mutual_funds', selected)
        
        # Check if stocks per group limit is respected
        for group, stocks in selected.items():
            self.assertLessEqual(len(stocks), 3)
        
        # Check if selected_stocks is populated
        self.assertGreater(len(self.engine.selected_stocks), 0)
    
    def test_find_trading_ranges(self):
        """Test trading range identification"""
        stock_symbol = 'RELIANCE'
        ranges = self.engine.find_trading_ranges(self.sample_data[stock_symbol], stock_symbol)
        
        # Should return z_segments ranges
        self.assertEqual(len(ranges), self.engine.strategy_params['z_segments'])
        
        # Each range should have required fields
        for range_data in ranges:
            self.assertIn('highest', range_data)
            self.assertIn('lowest', range_data)
            self.assertIn('avg_price', range_data)
            self.assertIn('type', range_data)
    
    def test_validate_range_conditions(self):
        """Test range validation logic"""
        lower_range = {'highest': 100, 'lowest': 90, 'avg_price': 95}
        higher_range = {'highest': 120, 'lowest': 110, 'avg_price': 115}
        
        # Valid condition: highest of lower < lowest of higher
        self.assertTrue(self.engine.validate_range_conditions(lower_range, higher_range))
        
        # Invalid condition
        invalid_higher = {'highest': 105, 'lowest': 95, 'avg_price': 100}
        self.assertFalse(self.engine.validate_range_conditions(lower_range, invalid_higher))
    
    def test_calculate_signals(self):
        """Test signal generation"""
        stock_symbol = 'TCS'
        signals = self.engine.calculate_signals(self.sample_data[stock_symbol], stock_symbol)
        
        self.assertEqual(signals['stock'], stock_symbol)
        self.assertIn('ranges', signals)
        self.assertIn('buy_signals', signals)
        self.assertIn('sell_signals', signals)
        self.assertIsInstance(signals['buy_signals'], list)
    
    def test_market_simulation(self):
        """Test market simulation functionality"""
        # Select some stocks first
        self.engine.select_stocks([StockType.CLASSIC], stocks_per_group=2)
        
        # Run simulation
        results = self.engine.run_market_simulation(
            self.sample_data, 
            "2023-01-01", 
            "2023-12-31"
        )
        
        self.assertEqual(results['mode'], 'market_simulation')
        self.assertIn('total_trades', results)
        self.assertIn('success_rate', results)
        self.assertIn('detailed_results', results)
        self.assertIsInstance(results['detailed_results'], list)
    
    def test_simulate_trade(self):
        """Test individual trade simulation"""
        stock_symbol = 'HDFCBANK'
        stock_data = self.sample_data[stock_symbol]
        
        # Create a mock buy signal
        buy_signal = {
            'price': 100.0,
            'timestamp': stock_data.index[50],  # Use middle of dataset
            'target_price': 115.0,
            'confidence': 75.0
        }
        
        signals = {
            'stock': stock_symbol,
            'stop_loss_price': 95.0,
            'early_exit_price': 115.0
        }
        
        trade_result = self.engine.simulate_trade(stock_data, buy_signal, signals)
        
        self.assertEqual(trade_result['stock'], stock_symbol)
        self.assertEqual(trade_result['entry_price'], 100.0)
        self.assertIn('exit_price', trade_result)
        self.assertIn('profit_loss', trade_result)
        self.assertIn('exit_reason', trade_result)
    
    def test_real_money_mode_setup(self):
        """Test real money mode initialization"""
        real_engine = StrategyEngine(Mode.REAL_MONEY)
        self.assertEqual(real_engine.mode, Mode.REAL_MONEY)
        
        # Test that market simulation mode engine raises error for real money operations
        with self.assertRaises(ValueError):
            self.engine.run_real_money_mode({})
    
    def test_optimization(self):
        """Test strategy optimization"""
        # Select stocks first
        self.engine.select_stocks([StockType.CLASSIC], stocks_per_group=1)
        
        # Run optimization with limited data for speed
        optimization_results = self.engine.optimize_strategy(self.sample_data)
        
        self.assertIn('optimized_params', optimization_results)
        self.assertIn('best_success_rate', optimization_results)
        self.assertIn('optimization_complete', optimization_results)
        self.assertTrue(optimization_results['optimization_complete'])

class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflow"""
    
    def test_complete_workflow(self):
        """Test complete strategy workflow"""
        # Initialize engine
        engine = StrategyEngine(Mode.MARKET_SIMULATION)
        
        # Select stocks
        selected = engine.select_stocks([StockType.CLASSIC], stocks_per_group=2)
        self.assertGreater(len(selected), 0)
        
        # Create sample data
        dates = pd.date_range(start='2023-01-01', end='2023-06-30', freq='D')
        sample_data = {}
        
        for stock in engine.selected_stocks[:2]:  # Limit to 2 stocks for speed
            base_price = 500
            prices = [base_price + i * 0.5 + np.random.normal(0, 5) for i in range(len(dates))]
            
            df = pd.DataFrame(index=dates)
            df['close'] = prices
            df['open'] = df['close'].shift(1).fillna(df['close'].iloc[0])
            df['high'] = df[['open', 'close']].max(axis=1) * 1.01
            df['low'] = df[['open', 'close']].min(axis=1) * 0.99
            df['volume'] = 50000
            
            sample_data[stock] = df
        
        # Run simulation
        results = engine.run_market_simulation(sample_data, "2023-01-01", "2023-06-30")
        
        # Verify results structure
        self.assertIn('mode', results)
        self.assertIn('total_trades', results)
        self.assertIn('success_rate', results)

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)

