import threading
import queue
import time
from flask import Flask, request, jsonify
import requests
import sqlite3  # Replace with your SQL DB connector

app = Flask(__name__)

# Simple in-memory queue and lock
task_queue = queue.Queue()
lock = threading.Lock()

BROKER_URL = "http://broker-middleware:5000/data"  # Update endpoint as needed
DB_PATH = "./data.db"  # Update path and connector for your SQL DB

def fetch_from_broker():
    response = requests.get(BROKER_URL)
    response.raise_for_status()
    return response.json()

def update_db(data):
    # Example for SQLite, replace with your DB logic
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS broker_data (id INTEGER PRIMARY KEY, info TEXT)")
    cursor.execute("INSERT INTO broker_data (info) VALUES (?)", (str(data),))
    conn.commit()
    conn.close()

def worker():
    while True:
        req_data = task_queue.get()
        with lock:
            try:
                data = fetch_from_broker()
                update_db(data)
                print("DB updated successfully.")
            except Exception as e:
                print(f"Error: {e}")
        task_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

@app.route('/ingest', methods=['POST'])
def ingest():
    req_data = request.json
    task_queue.put(req_data)
    return jsonify({"status": "queued"}), 202

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
