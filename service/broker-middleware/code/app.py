from flask import Flask, request, jsonify, render_template_string
from kiteconnect import KiteConnect
import pandas as pd
from datetime import datetime, timedelta
import os
import time
from typing import List, Optional, Dict, Tuple
import threading
from fetcher import KiteDataFetcher
from refresh_access_token import refresh_access_token

# Flask App
app = Flask(__name__)

# Configuration
API_KEY = os.environ.get('API_KEY')

# Global fetcher instance
fetcher = KiteDataFetcher(
    api_key=API_KEY,
    access_token=refresh_access_token(),
    data_folder='data',
    granularity='5minute'
)

# Store job status
job_status = {}

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Kite Stock Data Fetcher</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        h1 { 
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }
        .status {
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
        }
        .status.success { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: 600;
        }
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea {
            resize: vertical;
            min-height: 100px;
            font-family: monospace;
        }
        .hint {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .response {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }
        .loading {
            text-align: center;
            display: none;
            margin-top: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Kite Stock Data Fetcher</h1>
        <p class="subtitle">Fetch historical stock data from Kite Connect API</p>
        
        <div id="status" class="status success" style="display:none;"></div>
        
        <form id="fetchForm">
            <div class="form-group">
                <label>Stock Symbols</label>
                <textarea name="stocks" placeholder="RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK&#10;(Leave empty to fetch all stocks)"></textarea>
                <div class="hint">Enter comma-separated stock symbols. Leave empty to fetch all stocks.</div>
            </div>
            
            <div class="form-group">
                <label>Start Date</label>
                <input type="date" name="start_date" value="2025-01-01">
                <div class="hint">Leave empty for default: 2025-01-01</div>
            </div>
            
            <div class="form-group">
                <label>End Date</label>
                <input type="date" name="end_date">
                <div class="hint">Leave empty for today</div>
            </div>
            
            <div class="form-group">
                <label>Exchanges</label>
                <select name="exchanges" multiple size="6">
                    <option value="NSE" selected>NSE (National Stock Exchange)</option>
                    <option value="BSE" selected>BSE (Bombay Stock Exchange)</option>
                    <option value="NFO">NFO (NSE F&O)</option>
                    <option value="CDS">CDS (Currency Derivatives)</option>
                    <option value="BCD">BCD (BSE Currency)</option>
                    <option value="MCX">MCX (Multi Commodity)</option>
                </select>
                <div class="hint">Hold Ctrl/Cmd to select multiple exchanges</div>
            </div>
            
            <div class="form-group">
                <label>Granularity</label>
                <select name="granularity">
                    <option value="minute">1 Minute</option>
                    <option value="3minute">3 Minutes</option>
                    <option value="5minute" selected>5 Minutes</option>
                    <option value="15minute">15 Minutes</option>
                    <option value="30minute">30 Minutes</option>
                    <option value="60minute">60 Minutes</option>
                    <option value="day">Day</option>
                </select>
            </div>
            
            <button type="submit" id="submitBtn">🚀 Fetch Data</button>
        </form>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px;">Fetching data... This may take a while.</p>
        </div>
        
        <div id="response" class="response" style="display:none;"></div>
    </div>
    
    <script>
        const form = document.getElementById('fetchForm');
        const submitBtn = document.getElementById('submitBtn');
        const loading = document.getElementById('loading');
        const response = document.getElementById('response');
        const status = document.getElementById('status');
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            submitBtn.disabled = true;
            loading.style.display = 'block';
            response.style.display = 'none';
            status.style.display = 'none';
            
            const formData = new FormData(form);
            const data = {
                stocks: formData.get('stocks').trim() ? 
                    formData.get('stocks').split(',').map(s => s.trim().toUpperCase()) : null,
                start_date: formData.get('start_date') || null,
                end_date: formData.get('end_date') || null,
                exchanges: formData.getAll('exchanges'),
                granularity: formData.get('granularity')
            };
            
            try {
                const res = await fetch('/api/data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await res.json();
                
                if (result.error) {
                    status.className = 'status error';
                    status.textContent = '❌ Error: ' + result.error;
                    status.style.display = 'block';
                } else {
                    response.innerHTML = `
                        <h3>✅ Fetch Complete!</h3>
                        <p><strong>Successful:</strong> ${result.successful}</p>
                        <p><strong>Failed:</strong> ${result.failed}</p>
                        <p><strong>Not Found:</strong> ${result.not_found}</p>
                        <p><strong>Total:</strong> ${result.total}</p>
                        <p><strong>Data saved in:</strong> data/ folder</p>
                    `;
                    response.style.display = 'block';
                }
            } catch (error) {
                status.className = 'status error';
                status.textContent = '❌ Error: ' + error.message;
                status.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                loading.style.display = 'none';
            }
        });
        
        // Check connection on load
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    status.className = 'status success';
                    status.textContent = `✓ Connected as ${data.user_name} (${data.email})`;
                    status.style.display = 'block';
                } else {
                    status.className = 'status error';
                    status.textContent = '❌ Connection failed: ' + data.error;
                    status.style.display = 'block';
                    submitBtn.disabled = true;
                }
            });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the HTML form"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status', methods=['GET'])
def status():
    """Check connection status"""
    result = fetcher.test_connection()
    if not result['success']:
        print(f"Connection error: {result['error']}")
        print("Refreshing access token and retrying...")
        # Refresh access token and retry
        fetcher.access_token = refresh_access_token()
    result = fetcher.test_connection()
    return jsonify(result)

@app.route('/api/data', methods=['POST'])
def fetch_data():
    """Fetch stock data"""
    try:
        data = request.get_json()
        stocks = data.get('stocks')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        exchanges = data.get('exchanges')
        granularity = data.get('granularity', '5minute')
        # Update fetcher granularity
        fetcher.granularity = granularity
        
        # Fetch data (this will block until complete)
        try:
            result = fetcher.fetch_stock_data(
                stocks=stocks,
                start_date=start_date,
                end_date=end_date,
                exchanges=exchanges if exchanges else None
            )
        except Exception as e:
            print(f"Error during fetch: {e}")
            print("Refreshing access token and retrying...")
            # Refresh access token and retry
            fetcher.access_token = refresh_access_token()
            result = fetcher.fetch_stock_data(
                stocks=stocks,
                start_date=start_date,
                end_date=end_date,
                exchanges=exchanges if exchanges else None
            )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/exchanges', methods=['GET'])
def get_exchanges():
    """Get available exchanges"""
    return jsonify({
        'exchanges': KiteDataFetcher.EXCHANGES
    })

@app.route('/api/symbols', defaults={'exchange': None}, methods=['GET'])
@app.route('/api/symbols/<exchange>', methods=['GET'])
def get_symbols(exchange):
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)