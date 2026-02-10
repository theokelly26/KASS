"""RSA-PSS authentication for Kalshi WebSocket and REST API connections."""

from __future__ import annotations

import base64
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import structlog

logger = structlog.get_logger(__name__)


class KalshiWSAuth:
    """Handles RSA-PSS authentication for Kalshi WebSocket and REST connections."""

    def __init__(self, key_id: str, private_key_path: str | Path) -> None:
        self._key_id = key_id
        self._private_key = self._load_private_key(Path(private_key_path))
        logger.info("kalshi_auth_initialized", key_id=key_id)

    @staticmethod
    def _load_private_key(path: Path) -> rsa.RSAPrivateKey:
        """Load RSA private key from PEM file."""
        key_data = path.read_bytes()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise TypeError("Private key must be RSA")
        return private_key

    def _sign(self, message: str) -> str:
        """Sign a message with RSA-PSS and return base64-encoded signature."""
        signature = self._private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=hashes.SHA256().digest_size,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def create_headers(self) -> dict[str, str]:
        """Generate authentication headers for WebSocket handshake.

        The signed message is: timestamp_ms + "GET" + "/trade-api/ws/v2"
        """
        timestamp_ms = str(int(time.time() * 1000))
        message = timestamp_ms + "GET" + "/trade-api/ws/v2"
        signature = self._sign(message)

        return {
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        }

    def sign_rest_request(self, method: str, path: str) -> dict[str, str]:
        """Generate auth headers for REST API requests.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /trade-api/v2/markets)
        """
        timestamp_ms = str(int(time.time() * 1000))
        message = timestamp_ms + method.upper() + path
        signature = self._sign(message)

        return {
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        }
