"""
Abstract base class for cryptographic adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, TypeAlias

# Type alias for base64-encoded strings
B64: TypeAlias = str


class CryptoAdapter(ABC):
    """
    Abstract base class for cryptographic operations.
    Each implementation must provide methods for signing, verification,
    and public key retrieval, without exposing the private key.
    """

    @abstractmethod
    def sign(self, payload: Dict[str, Any]) -> B64:
        """
        Sign a JSON payload and return the base64-encoded signature.

        Args:
            payload: A dictionary that will be canonicalized before signing

        Returns:
            Base64-encoded signature
        """
        pass

    @abstractmethod
    def verify(self, payload: Dict[str, Any], signature: B64, pubkey: B64) -> bool:
        """
        Verify a signature against a JSON payload using a public key.

        Args:
            payload: The dictionary that was signed
            signature: Base64-encoded signature
            pubkey: Base64-encoded public key

        Returns:
            True if the signature is valid, False otherwise
        """
        pass

    @abstractmethod
    def public_key_b64(self) -> B64:
        """
        Get the current public key in base64 format.

        Returns:
            Base64-encoded public key
        """
        pass