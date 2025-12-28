import os
import subprocess
import signal
import time
import requests
import sys
import json
from flask import render_template_string

# Test configuration - Update these values for your environment
with open('values.json') as f:
    TEST_ENV = json.load(f)

APP_HOST = 'http://localhost:8080'
APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'app.py')

class AppTestRunner:
    def __init__(self):
        self.process = None
        self.original_env = {}
    
    def set_env(self):
        """Set environment variables for the app"""
        print("Setting environment variables...")
        for key, value in TEST_ENV.items():
            # Store original value if exists
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
            print(f"{key}=***")
    
    def unset_env(self):
        """Restore original environment variables"""
        print("Unsetting environment variables...")
        for key in TEST_ENV.keys():
            if self.original_env.get(key) is not None:
                os.environ[key] = self.original_env[key]
            elif key in os.environ:
                del os.environ[key]
            print(f"  {key} restored")
    
    def start_app(self):
        """Start the Flask app as a subprocess"""
        print(f"Starting app: {APP_PATH}")
        self.process = subprocess.Popen(
            [sys.executable, APP_PATH],
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group for clean kill
        )
        # Wait for app to start
        time.sleep(3)
        print(f"App started with PID: {self.process.pid}")
    
    def stop_app(self):
        """Stop the Flask app"""
        if self.process:
            print(f"Stopping app (PID: {self.process.pid})...")
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except Exception as e:
                print(f"Force killing app: {e}")
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            print("App stopped")
    
    def __enter__(self):
        self.set_env()
        self.start_app()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_app()
        self.unset_env()
        return False


def test_status_endpoint():
    """Test /api/status endpoint"""
    print("\n--- Testing /api/status ---")
    try:
        response = requests.get(f'{APP_HOST}/api/status')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_exchanges_endpoint():
    """Test /api/exchanges endpoint"""
    print("\n--- Testing /api/exchanges ---")
    try:
        response = requests.get(f'{APP_HOST}/api/exchanges')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_granularities_endpoint():
    """Test /api/granularities endpoint"""
    print("\n--- Testing /api/granularities ---")
    try:
        response = requests.get(f'{APP_HOST}/api/granularities')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_data_endpoint_get():
    """Test /api/data GET endpoint"""
    print("\n--- Testing /api/data (GET) ---")
    try:
        params = {
            'stocks': ['RELIANCE'],
            'start_date': '2025-01-01',
            'end_date': '2025-01-10',
            'exchanges': ['NSE'],
            'granularity': '5minute'
        }
        response = requests.get(f'{APP_HOST}/api/data', params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def test_data_endpoint_post():
    """Test /api/data POST endpoint"""
    print("\n--- Testing /api/data (POST) ---")
    try:
        payload = {
            'stocks': ['RELIANCE'],
            'start_date': '2025-01-01',
            'end_date': '2025-01-10',
            'exchanges': ['NSE'],
            'granularity': '5minute'
        }
        response = requests.post(
            f'{APP_HOST}/api/data',
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    results = {
        'status': test_status_endpoint(),
        'exchanges': test_exchanges_endpoint(),
        'granularities': test_granularities_endpoint(),
        'data_get': test_data_endpoint_get(),
        'data_post': test_data_endpoint_post(),
    }
    
    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    return all(results.values())


if __name__ == '__main__':
    print("=" * 50)
    print("BROKER MIDDLEWARE APP TESTS")
    print("=" * 50)
    
    with AppTestRunner() as runner:
        success = run_all_tests()
    
    print("\n" + "=" * 50)
    print("Test run complete. Environment cleaned up.")
    print("=" * 50)
    
    sys.exit(0 if success else 1)
