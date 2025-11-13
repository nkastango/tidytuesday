"""
Secure credential and token storage using system keyring.
"""
import keyring
import json
from datetime import datetime


class SecureStorage:
    """Secure storage for sensitive credentials and tokens."""

    SERVICE_NAME = "dexcom-cgm-manager"

    @staticmethod
    def store_tokens(access_token, refresh_token=None, expires_at=None):
        """
        Store OAuth tokens securely in system keyring.

        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_at: Token expiration datetime (optional)
        """
        token_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at.isoformat() if expires_at else None
        }
        keyring.set_password(
            SecureStorage.SERVICE_NAME,
            'oauth_tokens',
            json.dumps(token_data)
        )

    @staticmethod
    def get_tokens():
        """
        Retrieve OAuth tokens from system keyring.

        Returns:
            Dict with access_token, refresh_token, and expires_at
        """
        token_json = keyring.get_password(
            SecureStorage.SERVICE_NAME,
            'oauth_tokens'
        )
        if not token_json:
            return None

        token_data = json.loads(token_json)
        if token_data.get('expires_at'):
            token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])

        return token_data

    @staticmethod
    def clear_tokens():
        """Delete stored tokens from keyring."""
        try:
            keyring.delete_password(SecureStorage.SERVICE_NAME, 'oauth_tokens')
        except keyring.errors.PasswordDeleteError:
            pass  # Already deleted

    @staticmethod
    def store_database_key(key):
        """
        Store database encryption key securely.

        Args:
            key: Encryption key bytes
        """
        import base64
        keyring.set_password(
            SecureStorage.SERVICE_NAME,
            'database_key',
            base64.b64encode(key).decode('utf-8')
        )

    @staticmethod
    def get_database_key():
        """
        Retrieve database encryption key.

        Returns:
            Encryption key bytes or None
        """
        import base64
        key_str = keyring.get_password(
            SecureStorage.SERVICE_NAME,
            'database_key'
        )
        if not key_str:
            return None
        return base64.b64decode(key_str.encode('utf-8'))

    @staticmethod
    def generate_database_key():
        """
        Generate a new database encryption key.

        Returns:
            32-byte encryption key
        """
        from cryptography.fernet import Fernet
        return Fernet.generate_key()
