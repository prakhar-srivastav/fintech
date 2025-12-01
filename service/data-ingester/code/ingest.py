import threading
import queue
import time
from flask import Flask, request, jsonify
import requests
import sqlite3
import psycopg2

app = Flask(__name__)

task_queue = queue.Queue()
lock = threading.Lock()

BROKER_MIDDLEWARE_URL = "BROKER_MIDDLEWARE_URL"
DB_URL = "DB_URL"

def fetch_from_broker(sync_type, items=None):
    endpoint = f"/exchange" if sync_type == "exchange" else "/stocks"
    url = f"http://{BROKER_MIDDLEWARE_URL}/data{endpoint}"
    params = {}
    if items:
        params['items'] = ','.join(items)
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def update_db(data):
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS broker_data (
            id SERIAL PRIMARY KEY,
            info TEXT
        )
    """)
    cursor.execute("INSERT INTO broker_data (info) VALUES (%s)", (str(data),))
    conn.commit()
    cursor.close()
    conn.close()

def worker():
    while True:
        sync_type, items = task_queue.get()
        with lock:
            try:
                data = fetch_from_broker(sync_type, items)
                update_db(data)
                print(f"DB updated successfully for {sync_type} {items if items else 'all'}.")
            except Exception as e:
                print(f"Error: {e}")
        task_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

@app.route('/ingest', methods=['POST'])
def ingest():
    req_data = request.json
    sync_type = req_data.get('sync_type')  # 'exchange' or 'stocks'
    items = req_data.get('items')  # list of exchanges or stocks
    if sync_type not in ['exchange', 'stocks']:
        return jsonify({"error": "sync_type must be 'exchange' or 'stocks'"}), 400
    task_queue.put((sync_type, items))
    return jsonify({"status": "queued", "sync_type": sync_type, "items": items}), 202

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
