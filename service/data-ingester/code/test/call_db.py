import time
import os
import requests
import sqlite3
import mysql.connector



DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'TLxcNWA2Yb'),
    'database': os.environ.get('DB_NAME', 'fintech_db'),
    'port': int(os.environ.get('DB_PORT', '3306'))
}

query = """ show tables; """

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()
cursor.execute(query)
results = cursor.fetchall()

print(results)

cursor.close()
conn.close()