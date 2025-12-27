# Broker Middleware API Documentation

## Overview
The Broker Middleware is a Flask-based REST API that provides access to historical stock data from the Kite Connect API. It supports fetching data for multiple stocks across different exchanges with configurable granularity.

**Base URL:** `http://localhost:8080` // can change but we will assume this for example purpose only

---

## Endpoints

### 1. Health Check / Status
**Endpoint:** `GET /api/status`

**Description:** Check the connection status and authentication with Kite Connect API.

**Request:**
```bash
curl http://localhost:8080/api/status
```

**Python Example:**
```python
import requests

response = requests.get('http://localhost:8080/api/status')
print(response.json())
```

**Success Response (200):**
```json
{
    "success": true,
    "user_name": "John Doe",
    "email": "john@example.com",
    "broker": "Zerodha"
}
```

**Error Response (500):**
```json
{
    "success": false,
    "error": "Invalid access token or connection failed"
}
```

---

### 2. Fetch Stock Data
**Endpoint:** `POST /api/data`

**Description:** Fetch historical stock data for specified stocks, date range, and granularity.

**Request Headers:**
```
Content-Type: application/json
```

**Request Body Parameters:**
| Parameter | Type | Required | Description | Default |
|-----------|------|----------|-------------|---------|
| `stocks` | Array of strings | No | List of stock symbols (e.g., ["RELIANCE", "TCS"]) | null (fetch all) |
| `start_date` | String (YYYY-MM-DD) | No | Start date for historical data | 2025-01-01 |
| `end_date` | String (YYYY-MM-DD) | No | End date for historical data | Today |
| `exchanges` | Array of strings | No | List of exchanges (NSE, BSE, NFO, CDS, BCD, MCX) | All exchanges |
| `granularity` | String | No | Data granularity (minute, 3minute, 5minute, 15minute, 30minute, 60minute, day) | 5minute |

**Request:**
```bash
curl -X POST http://localhost:8080/api/data \
-H "Content-Type: application/json" \
-d '{
    "stocks": ["RELIANCE", "TCS"],
    "start_date": "2025-01-19",
    "end_date": "2025-12-22",
    "exchanges": ["NSE", "BSE"],
    "granularity": "5minute"
}'
```

**Python Example:**
```python
import requests
import json

url = 'http://localhost:8080/api/data'
payload = {
    "stocks": ["RELIANCE", "TCS"],
    "start_date": "2025-01-19",
    "end_date": "2025-12-22",
    "exchanges": ["NSE", "BSE"],
    "granularity": "5minute"
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))
```

**Success Response (200):**
```json
{
    "successful": 2,
    "failed": 0,
    "not_found": 0,
    "total": 2,
    "message": "Data fetched successfully",
    "stocks_fetched": ["RELIANCE", "TCS"]
}
```

**Error Response (500):**
```json
{
    "error": "Invalid date format or connection error"
}
```

---

### 3. Get Available Exchanges
**Endpoint:** `GET /api/exchanges`

**Description:** Get a list of all available exchanges.

**Request:**
```bash
curl http://localhost:8080/api/exchanges
```

**Python Example:**
```python
import requests

response = requests.get('http://localhost:8080/api/exchanges')
print(response.json())
```

**Response (200):**
```json
{
    "exchanges": [
        "NSE",
        "BSE",
        "NFO",
        "CDS",
        "BCD",
        "MCX"
    ]
}
```

---

### 4. Get Symbols by Exchange
**Endpoint:** `GET /api/symbols/<exchange>`

**Description:** Get all available trading symbols for a specific exchange.

**Path Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `exchange` | String | Yes | Exchange code (NSE, BSE, NFO, etc.) |

**Request:**
```bash
curl http://localhost:8080/api/symbols/NSE
```

**Python Example:**
```python
import requests

exchange = "NSE"
response = requests.get(f'http://localhost:8080/api/symbols/{exchange}')
print(response.json())
```

**Response (200):**
```json
{
    "symbols": [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
        "WIPRO",
        "MARUTI",
        "BAJAJFINSV"
    ],
    "tokens": [
        738561,
        2953217,
        1295193,
        1333057,
        1850625,
        1259094,
        1299500,
        500096
    ]
}
```

---

### 5. Get All Symbols
**Endpoint:** `GET /api/symbols`

**Description:** Get all available trading symbols across all exchanges.

**Request:**
```bash
curl http://localhost:8080/api/symbols
```

**Python Example:**
```python
import requests

response = requests.get('http://localhost:8080/api/symbols')
data = response.json()
print(f"Total symbols available: {len(data['symbols'])}")
print(f"First 10 symbols: {data['symbols'][:10]}")
```

**Response (200):**
```json
{
    "symbols": [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
        "WIPRO",
        "MARUTI",
        ...
    ],
    "tokens": [
        738561,
        2953217,
        1295193,
        ...
    ]
}
```

---

## Error Handling

### Common Error Responses

**Invalid JSON (400):**
```json
{
    "error": "Invalid JSON format"
}
```

**Missing Required Fields (400):**
```json
{
    "error": "Missing required field: stocks"
}
```

**Invalid Date Format (400):**
```json
{
    "error": "Invalid date format. Use YYYY-MM-DD"
}
```

**Authentication Error (401):**
```json
{
    "error": "Invalid or expired access token"
}
```

**Server Error (500):**
```json
{
    "error": "Internal server error: {error_details}"
}
```

---

## Complete Python Client Example

```python
import requests
import json
from datetime import datetime, timedelta

class BrokerMiddlewareClient:
    def __init__(self, base_url='http://localhost:8080'):
        self.base_url = base_url
    
    def check_status(self):
        """Check API status"""
        response = requests.get(f'{self.base_url}/api/status')
        return response.json()
    
    def fetch_data(self, stocks=None, start_date=None, end_date=None, 
                   exchanges=None, granularity='5minute'):
        """Fetch stock data"""
        payload = {
            "stocks": stocks,
            "start_date": start_date,
            "end_date": end_date,
            "exchanges": exchanges,
            "granularity": granularity
        }
        response = requests.post(f'{self.base_url}/api/data', json=payload)
        return response.json()
    
    def get_exchanges(self):
        """Get available exchanges"""
        response = requests.get(f'{self.base_url}/api/exchanges')
        return response.json()
    
    def get_symbols(self, exchange=None):
        """Get symbols for an exchange or all symbols"""
        if exchange:
            url = f'{self.base_url}/api/symbols/{exchange}'
        else:
            url = f'{self.base_url}/api/symbols'
        response = requests.get(url)
        return response.json()

# Usage Example
if __name__ == '__main__':
    client = BrokerMiddlewareClient()
    
    # Check status
    print("=== Status ===")
    status = client.check_status()
    print(json.dumps(status, indent=2))
    
    # Get exchanges
    print("\n=== Available Exchanges ===")
    exchanges = client.get_exchanges()
    print(json.dumps(exchanges, indent=2))
    
    # Get NSE symbols
    print("\n=== NSE Symbols ===")
    symbols = client.get_symbols('NSE')
    print(f"Total NSE symbols: {len(symbols['symbols'])}")
    print(f"First 5 symbols: {symbols['symbols'][:5]}")
    
    # Fetch data
    print("\n=== Fetch Stock Data ===")
    result = client.fetch_data(
        stocks=['RELIANCE', 'TCS'],
        start_date='2025-01-19',
        end_date='2025-12-22',
        exchanges=['NSE'],
        granularity='5minute'
    )
    print(json.dumps(result, indent=2))
```