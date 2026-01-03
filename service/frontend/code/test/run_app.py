#!/usr/bin/env python3
"""
Simple script to run the frontend application locally.
"""

import os
import sys
import subprocess

def main():
    # Set up environment variables
    os.environ.setdefault('DB_HOST', 'localhost')
    os.environ.setdefault('DB_PORT', '3306')
    os.environ.setdefault('DB_NAME', 'fintech_db')
    os.environ.setdefault('DB_USER', 'root')
    os.environ.setdefault('DB_PASSWORD', 'TLxcNWA2Yb')
    
    # Get the app directory
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    print("="*60)
    print("Starting Frontend Dashboard")
    print("="*60)
    print(f"DB_HOST: {os.environ.get('DB_HOST')}")
    print(f"DB_PORT: {os.environ.get('DB_PORT')}")
    print(f"DB_NAME: {os.environ.get('DB_NAME')}")
    print(f"DB_USER: {os.environ.get('DB_USER')}")
    print("="*60)
    print("Dashboard URL: http://localhost:8080")
    print("="*60)
    print()
    
    # Run the app
    subprocess.run(
        [sys.executable, 'app.py'],
        cwd=app_dir,
        env=os.environ.copy()
    )

if __name__ == '__main__':
    main()
