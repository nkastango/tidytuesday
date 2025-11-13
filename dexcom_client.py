"""
Dexcom API Client for downloading CGM data.
Uses OAuth 2.0 for authentication.
"""
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handler for OAuth callback."""

    authorization_code = None

    def do_GET(self):
        """Handle the OAuth callback GET request."""
        query_components = parse_qs(urlparse(self.path).query)

        if 'code' in query_components:
            OAuthCallbackHandler.authorization_code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authentication failed!</h1></body></html>')

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class DexcomClient:
    """Client for interacting with the Dexcom API."""

    # API endpoints
    ENVIRONMENTS = {
        'sandbox': {
            'auth_url': 'https://sandbox-api.dexcom.com/v2/oauth2/login',
            'token_url': 'https://sandbox-api.dexcom.com/v2/oauth2/token',
            'api_url': 'https://sandbox-api.dexcom.com/v3'
        },
        'production': {
            'auth_url': 'https://api.dexcom.com/v2/oauth2/login',
            'token_url': 'https://api.dexcom.com/v2/oauth2/token',
            'api_url': 'https://api.dexcom.com/v3'
        }
    }

    def __init__(self, environment='sandbox'):
        """Initialize the Dexcom client."""
        self.client_id = os.getenv('DEXCOM_CLIENT_ID')
        self.client_secret = os.getenv('DEXCOM_CLIENT_SECRET')
        self.redirect_uri = os.getenv('DEXCOM_REDIRECT_URI', 'http://localhost:8080/callback')

        if not self.client_id or not self.client_secret:
            raise ValueError("DEXCOM_CLIENT_ID and DEXCOM_CLIENT_SECRET must be set in .env file")

        self.environment = environment
        self.endpoints = self.ENVIRONMENTS[environment]
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = None

    def authenticate(self):
        """
        Perform OAuth authentication flow.
        Opens browser for user to authorize the application.
        """
        # Step 1: Get authorization code
        auth_url = (
            f"{self.endpoints['auth_url']}"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&response_type=code"
            f"&scope=offline_access"
            f"&state=test_state"
        )

        print(f"\nOpening browser for authentication...")
        print(f"If browser doesn't open, visit: {auth_url}\n")
        webbrowser.open(auth_url)

        # Start local server to receive callback
        server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
        print("Waiting for authentication callback...")
        server.handle_request()

        authorization_code = OAuthCallbackHandler.authorization_code

        if not authorization_code:
            raise Exception("Failed to get authorization code")

        # Step 2: Exchange authorization code for access token
        token_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': authorization_code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }

        response = requests.post(self.endpoints['token_url'], data=token_data)
        response.raise_for_status()

        token_response = response.json()
        self.access_token = token_response['access_token']
        self.refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 7200)
        self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

        print("Authentication successful!")
        return True

    def _refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise Exception("No refresh token available. Please re-authenticate.")

        token_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }

        response = requests.post(self.endpoints['token_url'], data=token_data)
        response.raise_for_status()

        token_response = response.json()
        self.access_token = token_response['access_token']
        expires_in = token_response.get('expires_in', 7200)
        self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

        print("Access token refreshed")

    def _ensure_valid_token(self):
        """Ensure we have a valid access token."""
        if not self.access_token:
            raise Exception("Not authenticated. Call authenticate() first.")

        # Refresh if token expires in less than 5 minutes
        if self.token_expiry and datetime.now() >= (self.token_expiry - timedelta(minutes=5)):
            self._refresh_access_token()

    def _make_request(self, endpoint, params=None):
        """Make an authenticated API request."""
        self._ensure_valid_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.endpoints['api_url']}/{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def get_glucose_readings(self, start_date, end_date):
        """
        Get glucose readings (EGVs - Estimated Glucose Values) for a date range.

        Args:
            start_date: datetime object or ISO format string
            end_date: datetime object or ISO format string

        Returns:
            List of glucose readings
        """
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
        if isinstance(end_date, datetime):
            end_date = end_date.isoformat()

        params = {
            'startDate': start_date,
            'endDate': end_date
        }

        try:
            data = self._make_request('users/self/egvs', params)
            return data.get('records', [])
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching glucose readings: {e}")
            return []

    def get_statistics(self, start_date, end_date):
        """
        Get statistics for a date range.

        Args:
            start_date: datetime object or ISO format string
            end_date: datetime object or ISO format string

        Returns:
            Statistics data
        """
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
        if isinstance(end_date, datetime):
            end_date = end_date.isoformat()

        params = {
            'startDate': start_date,
            'endDate': end_date
        }

        try:
            data = self._make_request('users/self/statistics', params)
            return data
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching statistics: {e}")
            return {}

    def get_data_range(self):
        """
        Get the available data range for the user.

        Returns:
            Dict with start and end dates
        """
        try:
            data = self._make_request('users/self/dataRange')
            return data
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching data range: {e}")
            return {}


if __name__ == "__main__":
    # Example usage
    client = DexcomClient(environment=os.getenv('DEXCOM_ENVIRONMENT', 'sandbox'))

    try:
        client.authenticate()

        # Get available data range
        data_range = client.get_data_range()
        print(f"\nAvailable data range: {data_range}")

        # Get last 7 days of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        readings = client.get_glucose_readings(start_date, end_date)
        print(f"\nFetched {len(readings)} glucose readings")

        if readings:
            print(f"Sample reading: {readings[0]}")

    except Exception as e:
        print(f"Error: {e}")
