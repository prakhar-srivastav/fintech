import requests
import hashlib

# Set your credentials
api_key = 'ljz7f8iqzy7ppkti'
api_secret = '4ja9g1nkpdybepocuu1v0kgv4mzu9ka9'
request_token = 'PPwZLXbl05SRfKy9KufKqIRpvOmmfbYa'

# Create checksum: SHA256(api_key + request_token + api_secret)
checksum_str = api_key + request_token + api_secret
checksum = hashlib.sha256(checksum_str.encode()).hexdigest()

# Prepare headers and payload
url = 'https://api.kite.trade/session/token'
headers = {
    'X-Kite-Version': '3'
}
data = {
    'api_key': api_key,
    'request_token': request_token,
    'checksum': checksum
}

# Make the POST request
response = requests.post(url, headers=headers, data=data)

# Print the response
print("Status Code:", response.status_code)
print("Response:", response.json())
