"""
Implementation of CryptoAdapter using pyca/cryptography for Ed25519 signatures.
"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey
)
from cryptography.hazmat.primitives import serialization
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import os
import base64
import json
import pathlib
import getpass
from typing import Dict, Any, Optional

from .adapter_base import CryptoAdapter, B64
from .constants import DEFAULT_ED25519_PRIV_PEM, DEFAULT_ED25519_PUB_PEM


class PycaCryptoAdapter(CryptoAdapter):
    """
    Ed25519 implementation using pyca/cryptography.
    
    This adapter handles key generation, loading, and Ed25519 signatures
    using the pyca/cryptography library.
    
    Keys are stored in PEM format, with private keys encrypted using
    scrypt and AES-256-GCM via Fernet.
    """
    
    def __init__(self, key_path: Optional[str] = None):
        """
        Initialize with an optional key path.
        
        Args:
            key_path: Path to the private key file. If None, defaults to ~/.dao_keys/ed25519/priv.pem
        """
        if key_path is None:
            key_path = DEFAULT_ED25519_PRIV_PEM
            
        key_path = pathlib.Path(os.path.expanduser(key_path))
        self._load_or_create(key_path)
    
    def _load_or_create(self, key_path: pathlib.Path) -> None:
        """
        Load an existing key or create a new one if it doesn't exist.
        
        Args:
            key_path: Path to the key file
        """
        if key_path.exists():
            # Load existing key
            password = getpass.getpass("Key passphrase: ").encode()
            
            try:
                self._priv = serialization.load_pem_private_key(
                    key_path.read_bytes(),
                    password
                )
            except Exception as e:
                raise ValueError(f"Failed to load private key: {e}")
        else:
            # Create new key
            key_path.parent.mkdir(parents=True, exist_ok=True)
            self._priv = Ed25519PrivateKey.generate()
            
            # Get passphrase for encryption
            while True:
                password = getpass.getpass("New key passphrase: ").encode()
                confirm = getpass.getpass("Confirm passphrase: ").encode()
                if password == confirm:
                    break
                print("Passphrases don't match. Try again.")
            
            # Save private key in encrypted PEM format
            encrypted_pem = self._priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(password)
            )
            
            key_path.write_bytes(encrypted_pem)
            
            # Also save public key for convenience
            pub_path = pathlib.Path(os.path.expanduser(DEFAULT_ED25519_PUB_PEM))
            pub_path.parent.mkdir(parents=True, exist_ok=True)
            
            pub_pem = self._priv.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            pub_path.write_bytes(pub_pem)
            print(f"Key pair generated. Public key saved to {pub_path}")
            
        # Extract public key from private key
        self._pub = self._priv.public_key()
    
    def sign(self, payload: Dict[str, Any]) -> B64:
        """
        Sign a JSON payload using Ed25519.
        
        Args:
            payload: The dictionary to sign
            
        Returns:
            Base64-encoded signature
        """
        # Canonicalize the JSON payload
        message = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
        
        # Sign the message
        signature = self._priv.sign(message)
        
        # Return base64 encoded signature
        return base64.b64encode(signature).decode()
    
    def verify(self, payload: Dict[str, Any], signature: B64, pubkey: B64) -> bool:
        """
        Verify a signature using Ed25519.
        
        Args:
            payload: The dictionary that was signed
            signature: Base64-encoded signature
            pubkey: Base64-encoded public key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Canonicalize the JSON payload
            message = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
            
            # Decode the signature and public key from base64
            sig_bytes = base64.b64decode(signature)
            pub_bytes = base64.b64decode(pubkey)
            
            # Create a public key object
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            
            # Verify the signature
            public_key.verify(sig_bytes, message)
            
            return True
        except Exception:
            return False
    
    def public_key_b64(self) -> B64:
        """
        Get the base64-encoded public key in raw format.
        
        Returns:
            Base64-encoded public key
        """
        raw_pub = self._pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        return base64.b64encode(raw_pub).decode()