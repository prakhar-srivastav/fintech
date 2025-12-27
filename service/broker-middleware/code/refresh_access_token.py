import requests
import re
import onetimepass as otp
from urllib.parse import urlparse, parse_qs
import time
from kiteconnect import KiteConnect
import os


API_KEY = os.getenv("API_KEY")
USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
TOTP_KEY = os.getenv("TOTP_KEY")
API_SECRET = os.getenv("API_SECRET")

def refresh_access_token() -> str:
    """Use provided credentials and return access token.
    Args:
    Returns:
        Access token for the provided credentials
    """

    kite = KiteConnect(api_key=API_KEY)

    session = requests.Session()
    response = session.get(kite.login_url())
    # User login POST request
    login_payload = {
        "user_id": USER_NAME,
        "password": PASSWORD,
    }
    login_response = session.post("https://kite.zerodha.com/api/login", login_payload)
    # TOTP POST request
    totp_payload = {
        "user_id": USER_NAME,
        "request_id": login_response.json()["data"]["request_id"],
        "twofa_value": otp.get_totp(TOTP_KEY),
        "twofa_type": "totp",
        "skip_session": True,
    }
    totp_response = session.post("https://kite.zerodha.com/api/twofa", totp_payload)
    # Extract request token from redirect URL
    try:
        response = session.get(kite.login_url())
        if "request_token=" in response.url:
            parsed_url = urlparse(response.url)
            request_token = parse_qs(parsed_url.query)["request_token"][0]
    except Exception as e:
        err_str = str(e)
        request_token = err_str.split("request_token=")[1].split(" ")[0]
        if "&" in request_token:
            request_token = request_token.split("&")[0]

    kite = KiteConnect(api_key=API_KEY)
    time.sleep(1)
    data = kite.generate_session(request_token, api_secret=API_SECRET)

    return data["access_token"]
