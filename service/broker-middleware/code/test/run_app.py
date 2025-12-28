import os
import subprocess
import signal
import sys
import json

# Test configuration - Update these values for your environment
with open('values.json') as f:
    TEST_ENV = json.load(f)

APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'app.py')

def set_env():
    """Set environment variables for the app"""
    print("Setting environment variables...")
    for key, value in TEST_ENV.items():
        os.environ[key] = value
        print(f"{key}=***")

def unset_env():
    """Unset environment variables"""
    print("\nUnsetting environment variables...")
    for key in TEST_ENV.keys():
        if key in os.environ:
            del os.environ[key]
        print(f"{key} removed")

def run_app():
    """Run the Flask app and show output"""
    print(f"\nStarting app: {APP_PATH}")
    print("=" * 50)
    print("APP OUTPUT (Press Ctrl+C to stop)")
    print("=" * 50 + "\n")
    
    process = subprocess.Popen(
        [sys.executable, APP_PATH],
        env=os.environ.copy(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    
    try:
        # Wait for the process to complete (or be interrupted)
        process.wait()
    except KeyboardInterrupt:
        print("\n\nReceived Ctrl+C, shutting down...")
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
    
    return process.returncode

if __name__ == '__main__':
    print("=" * 50)
    print("BROKER MIDDLEWARE APP RUNNER")
    print("=" * 50)
    
    set_env()
    
    try:
        exit_code = run_app()
    finally:
        unset_env()
        print("\nApp stopped. Environment cleaned up.")
    
    sys.exit(exit_code or 0)
