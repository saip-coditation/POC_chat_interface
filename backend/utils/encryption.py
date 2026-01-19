"""
API Key Encryption Utilities

Uses Fernet symmetric encryption for secure API key storage.
"""

import base64
import logging
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def get_fernet():
    """Get Fernet instance with the configured encryption key."""
    key = settings.ENCRYPTION_KEY
    if not key:
        # Generate a key for development (not recommended for production)
        logger.warning("No ENCRYPTION_KEY set. Using a temporary key. Set ENCRYPTION_KEY in production!")
        key = Fernet.generate_key().decode()
    
    # Ensure key is bytes
    if isinstance(key, str):
        key = key.encode()
    
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage.
    
    Args:
        api_key: The plain text API key
        
    Returns:
        Base64 encoded encrypted string
    """
    if not api_key:
        return ''
    
    try:
        fernet = get_fernet()
        encrypted = fernet.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise ValueError("Failed to encrypt API key")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an encrypted API key.
    
    Args:
        encrypted_key: Base64 encoded encrypted string
        
    Returns:
        Plain text API key
    """
    if not encrypted_key:
        return ''
    
    try:
        fernet = get_fernet()
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except InvalidToken:
        logger.error("Invalid encryption token - key may be corrupted or wrong encryption key")
        raise ValueError("Failed to decrypt API key - invalid token")
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise ValueError("Failed to decrypt API key")


def mask_api_key(api_key: str) -> str:
    """
    Mask an API key for display (show last 4 characters).
    
    Args:
        api_key: The API key to mask
        
    Returns:
        Masked string like "••••••••abcd"
    """
    if not api_key or len(api_key) < 4:
        return "••••••••"
    
    return "••••••••" + api_key[-4:]
