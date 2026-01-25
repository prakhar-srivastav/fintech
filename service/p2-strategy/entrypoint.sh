#!/bin/bash
set -e

echo "Starting P2 Strategy Service: $SERVICE"

case "$SERVICE" in
    "frontend")
        echo "Running Frontend (app.py) on port 8082..."
        exec python frontend/app.py
        ;;
    "config-poller")
        echo "Running Config Poller (strategy_config_poller.py)..."
        exec python strategy_config_poller.py
        ;;
    "execution-poller")
        echo "Running Execution Poller (strategy_execution_poller.py)..."
        exec python strategy_execution_poller.py
        ;;
    *)
        echo "Unknown service: $SERVICE"
        echo "Valid options: frontend, config-poller, execution-poller"
        exit 1
        ;;
esac
