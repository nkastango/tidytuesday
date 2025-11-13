"""
Database encryption utilities for protecting sensitive health data at rest.
"""
import os
import pandas as pd
from cryptography.fernet import Fernet
from secure_storage import SecureStorage


class DataEncryption:
    """Handles encryption/decryption of sensitive database fields."""

    def __init__(self):
        """Initialize encryption with key from secure storage."""
        self.key = SecureStorage.get_database_key()
        if not self.key:
            # Generate new key if none exists
            self.key = SecureStorage.generate_database_key()
            SecureStorage.store_database_key(self.key)
        self.cipher = Fernet(self.key)

    def encrypt_value(self, value):
        """
        Encrypt a single value.

        Args:
            value: Value to encrypt (will be converted to string)

        Returns:
            Encrypted string
        """
        if value is None:
            return None

        # Convert to string and encrypt
        value_str = str(value)
        encrypted = self.cipher.encrypt(value_str.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_value(self, encrypted_value):
        """
        Decrypt a single value.

        Args:
            encrypted_value: Encrypted string

        Returns:
            Decrypted original value as string
        """
        if encrypted_value is None:
            return None

        try:
            decrypted = self.cipher.decrypt(encrypted_value.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt value: {e}")

    def encrypt_dataframe_column(self, df, column_name):
        """
        Encrypt a specific column in a DataFrame.

        Args:
            df: Pandas DataFrame
            column_name: Name of column to encrypt

        Returns:
            DataFrame with encrypted column
        """
        if column_name not in df.columns:
            return df

        df = df.copy()
        df[column_name] = df[column_name].apply(self.encrypt_value)
        return df

    def decrypt_dataframe_column(self, df, column_name):
        """
        Decrypt a specific column in a DataFrame.

        Args:
            df: Pandas DataFrame
            column_name: Name of column to decrypt

        Returns:
            DataFrame with decrypted column
        """
        if column_name not in df.columns:
            return df

        df = df.copy()
        df[column_name] = df[column_name].apply(self.decrypt_value)
        return df


def set_secure_file_permissions(file_path):
    """
    Set secure file permissions (owner read/write only).

    Args:
        file_path: Path to file to secure
    """
    if os.name != 'nt':  # Unix-like systems
        os.chmod(file_path, 0o600)  # rw-------
        print(f"Set secure permissions on {file_path}")
    else:
        # On Windows, try to set restrictive permissions
        try:
            import subprocess
            # Remove inheritance and grant full control only to current user
            subprocess.run([
                'icacls', file_path,
                '/inheritance:r',
                '/grant:r', f'{os.getenv("USERNAME")}:F'
            ], check=True, capture_output=True)
            print(f"Set secure permissions on {file_path}")
        except Exception as e:
            print(f"Warning: Could not set secure permissions on {file_path}: {e}")
