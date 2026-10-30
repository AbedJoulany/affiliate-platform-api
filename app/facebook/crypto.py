import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class FacebookTokenEncryptionError(ValueError):
    """Raised when the configured Facebook token encryption key is unusable."""


class FacebookTokenCipher:
    """AES-256-GCM envelope encryption for Page access tokens.

    The configured key is URL-safe base64 encoding of exactly 32 random bytes.
    The persisted value contains only a version, nonce, and ciphertext.
    """

    VERSION = "v1"

    def __init__(self, encoded_key: str | None) -> None:
        if not encoded_key or not encoded_key.strip():
            raise FacebookTokenEncryptionError("Facebook token encryption is not configured")
        try:
            encoded = encoded_key.strip()
            encoded += "=" * (-len(encoded) % 4)
            key = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
            raise FacebookTokenEncryptionError("Facebook token encryption key is invalid") from exc
        if len(key) != 32:
            raise FacebookTokenEncryptionError(
                "Facebook token encryption key must decode to 32 bytes"
            )
        self._aes = AESGCM(key)

    def encrypt(self, token: str) -> str:
        if not token or not token.strip():
            raise FacebookTokenEncryptionError("Facebook access token is empty")
        nonce = os.urandom(12)
        ciphertext = self._aes.encrypt(nonce, token.encode("utf-8"), self.VERSION.encode())
        nonce_encoded = base64.urlsafe_b64encode(nonce).decode("ascii")
        ciphertext_encoded = base64.urlsafe_b64encode(ciphertext).decode("ascii")
        return f"{self.VERSION}.{nonce_encoded}.{ciphertext_encoded}"

    def decrypt(self, envelope: str) -> str:
        try:
            version, nonce_encoded, ciphertext_encoded = envelope.split(".", 2)
            if version != self.VERSION:
                raise ValueError
            nonce = base64.urlsafe_b64decode(nonce_encoded.encode("ascii"))
            ciphertext = base64.urlsafe_b64decode(ciphertext_encoded.encode("ascii"))
            return self._aes.decrypt(nonce, ciphertext, version.encode()).decode("utf-8")
        except (ValueError, UnicodeDecodeError, binascii.Error, InvalidTag) as exc:
            raise FacebookTokenEncryptionError(
                "Stored Facebook access token cannot be decrypted"
            ) from exc
