#!/usr/bin/env python3
"""
Test script for the frontend application.
Run this to verify all endpoints are working correctly.
"""

import os
import sys
import subprocess
import time
import requests
import signal

# Configuration
APP_PORT = 8080
BASE_URL = f"http://localhost:{APP_PORT}"

def setup_environment():
    """Set up environment variables for testing"""
    os.environ.setdefault('DB_HOST', 'localhost')
    os.environ.setdefault('DB_PORT', '3306')
    os.environ.setdefault('DB_NAME', 'fintech_db')
    os.environ.setdefault('DB_USER', 'root')
    os.environ.setdefault('DB_PASSWORD', 'TLxcNWA2Yb')

def start_app():
    """Start the Flask application"""
    print("Starting Flask application...")
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    process = subprocess.Popen(
        [sys.executable, 'app.py'],
        cwd=app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy()
    )
    # Wait for app to start
    time.sleep(3)
    return process

def stop_app(process):
    """Stop the Flask application"""
    print("Stopping Flask application...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

def test_endpoint(name, url, expected_keys=None, method='GET'):
    """Test an API endpoint"""
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"Method: {method}")
    
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            if expected_keys:
                data = response.json()
                for key in expected_keys:
                    if key not in data:
                        print(f"❌ FAIL: Missing key '{key}' in response")
                        return False
            print(f"✅ PASS")
            return True
        else:
            print(f"❌ FAIL: Unexpected status code")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ FAIL: Connection refused")
        return False
    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False

def run_tests():
    """Run all endpoint tests"""
    results = []
    
    # Test main page
    results.append(test_endpoint(
        "Main Dashboard",
        f"{BASE_URL}/"
    ))
    
    # Test API endpoints
    results.append(test_endpoint(
        "Get Stocks",
        f"{BASE_URL}/api/stocks",
        expected_keys=['stocks']
    ))
    
    results.append(test_endpoint(
        "Get Exchanges",
        f"{BASE_URL}/api/exchanges",
        expected_keys=['exchanges']
    ))
    
    results.append(test_endpoint(
        "Get Granularities",
        f"{BASE_URL}/api/granularities",
        expected_keys=['granularities']
    ))
    
    results.append(test_endpoint(
        "Get Summary",
        f"{BASE_URL}/api/summary",
        expected_keys=['total_records', 'total_stocks', 'total_exchanges']
    ))
    
    # Test data endpoint (without stock param - should return error)
    results.append(test_endpoint(
        "Get Data (no params - expect error)",
        f"{BASE_URL}/api/data"
    ) == False)  # We expect this to fail
    
    return results

def main():
    """Main test runner"""
    print("="*60)
    print("Frontend Application Test Suite")
    print("="*60)
    
    setup_environment()
    
    # Start the app
    process = start_app()
    
    try:
        # Run tests
        results = run_tests()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        if passed == total:
            print("\n✅ All tests passed!")
            return 0
        else:
            print(f"\n❌ {total - passed} test(s) failed")
            return 1
            
    finally:
        stop_app(process)

if __name__ == '__main__':
    sys.exit(main())
