from __future__ import annotations

import logging
from cryptography.fernet import Fernet
from app.config import get_settings

logger = logging.getLogger(__name__)

class CryptoEngine:
    """Centralized encryption engine for sensitive data at rest."""
    
    def __init__(self, key: str | None = None):
        settings = get_settings()
        self.fernet = Fernet(key or settings.fernet_key)

    def encrypt(self, value: str) -> str:
        """Encrypts a string and returns a UTF-8 string."""
        if not value:
            return ""
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        """Decrypts a string and returns the original text."""
        if not value:
            return None
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            return None

_engine: CryptoEngine | None = None

def get_crypto_engine() -> CryptoEngine:
    global _engine
    if _engine is None:
        _engine = CryptoEngine()
    return _engine
