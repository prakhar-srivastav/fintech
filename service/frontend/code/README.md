# Frontend Dashboard

A Flask-based web dashboard for visualizing stock data from the MySQL database.

## Features

- **Summary Cards**: Display total records, stocks, exchanges, and data range
- **Interactive Filters**: Filter by stock symbol, exchange, granularity, and date range
- **Price Charts**: Line chart showing Close, High, and Low prices
- **Volume Charts**: Bar chart showing trading volume
- **Price Change Indicator**: Shows percentage change over the selected period

## Prerequisites

- Python 3.9+
- MySQL database with `broker_data` table
- Required Python packages (see `requirements.txt`)

## Local Development

### 1. Set up virtual environment

```bash
cd /Users/prakharsrivastava/fintech/service/frontend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=fintech_db
export DB_USER=root
export DB_PASSWORD=your_password
```

### 3. Run the application

```bash
python app.py
```

The dashboard will be available at http://localhost:8080

## Docker Deployment

### Build the image

```bash
docker build -t frontend:latest .
```

### Run the container

```bash
docker run -d \
  -p 8080:8080 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=3306 \
  -e DB_NAME=fintech_db \
  -e DB_USER=root \
  -e DB_PASSWORD=your_password \
  --name frontend \
  frontend:latest
```

## Kubernetes Deployment

### Install with Helm

```bash
helm install frontend ./helm \
  --set db.host=mysql \
  --set db.password=your_password
```

### Port forward for local access

```bash
kubectl port-forward svc/frontend-frontend 8080:8080
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard page |
| `/api/stocks` | GET | List of available stock symbols |
| `/api/exchanges` | GET | List of available exchanges |
| `/api/granularities` | GET | List of available granularities |
| `/api/data` | GET | Stock data for charting |
| `/api/summary` | GET | Summary statistics |

### Example: Get stock data

```bash
curl "http://localhost:8080/api/data?stock=RELIANCE&exchange=NSE&granularity=5minute"
```

## Project Structure

```
frontend/
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── dockerfile          # Docker image definition
├── README.md           # This file
├── templates/
│   └── index.html      # Dashboard HTML template
└── helm/
    ├── Chart.yaml      # Helm chart metadata
    ├── values.yaml     # Default configuration values
    └── templates/
        ├── deployment.yaml
        ├── service.yaml
        └── secret.yaml
```

## Troubleshooting

### Database connection issues

1. Verify MySQL is running and accessible
2. Check environment variables are set correctly
3. Ensure the `broker_data` table exists with the correct schema

### No data displayed

1. Verify there is data in the `broker_data` table
2. Check browser console for API errors
3. Review Flask logs for database query errors

### Charts not rendering

1. Ensure Chart.js CDN is accessible
2. Check browser console for JavaScript errors
