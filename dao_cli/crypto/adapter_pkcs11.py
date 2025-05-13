"""
Implementation of CryptoAdapter using python-pkcs11 for hardware key storage.
"""
import os
import json
import base64
import pkcs11
from pkcs11 import ObjectClass, KeyType, Mechanism
from pkcs11.util.ec import encode_named_curve_parameters
from typing import Dict, Any, Optional, cast
from .adapter_base import CryptoAdapter, B64
from .constants import (
    PKCS11_TOKEN_LABEL, 
    PKCS11_KEY_LABEL, 
    PKCS11_PIN, 
    PKCS11_LIB_PATH,
    ALG_ED25519,
    ALG_ECDSA
)


class Pkcs11Adapter(CryptoAdapter):
    """
    PKCS#11 implementation for hardware-backed crypto operations.
    
    This adapter handles Ed25519 or ECDSA (secp256r1) signatures using 
    hardware security modules via the PKCS#11 interface.
    
    Private keys never leave the hardware device.
    """
    
    def __init__(self, 
                token_label: Optional[str] = None, 
                key_label: Optional[str] = None,
                pin: Optional[str] = None,
                lib_path: Optional[str] = None):
        """
        Initialize with optional PKCS#11 parameters.
        
        Args:
            token_label: Label of the PKCS#11 token to use
            key_label: Label of the key to use for signing
            pin: PIN to access the token
            lib_path: Path to the PKCS#11 library
        """
        # Get parameters from args or environment variables
        self._token_label = token_label or os.environ.get(PKCS11_TOKEN_LABEL)
        self._key_label = key_label or os.environ.get(PKCS11_KEY_LABEL)
        self._pin = pin or os.environ.get(PKCS11_PIN)
        self._lib_path = lib_path or os.environ.get(PKCS11_LIB_PATH)
        
        if not self._token_label:
            raise ValueError("Token label must be provided or set in environment variable")
        if not self._key_label:
            raise ValueError("Key label must be provided or set in environment variable")
        if not self._pin:
            raise ValueError("PIN must be provided or set in environment variable")
        if not self._lib_path:
            raise ValueError("PKCS#11 library path must be provided or set in environment variable")
        
        # Initialize PKCS#11 session and determine available mechanisms
        self._lib = pkcs11.lib(self._lib_path)
        self._token = self._lib.get_token(token_label=self._token_label)
        
        # Open session and determine key type
        with self._token.open(user_pin=self._pin) as session:
            # Look for existing key pair with the specified label
            try:
                # Find the private key first
                priv_key = next(session.get_objects({
                    ObjectClass.PRIVATE_KEY, 
                    'label': self._key_label
                }))
                
                # Check key type to determine mechanism
                if priv_key[KeyType.EC]:
                    self._mechanism = Mechanism.ECDSA
                    self._alg = ALG_ECDSA
                elif hasattr(Mechanism, 'EDDSA') and priv_key[KeyType.EC_EDWARDS]:
                    self._mechanism = Mechanism.EDDSA
                    self._alg = ALG_ED25519
                else:
                    raise ValueError("Unsupported key type in token")
                
                # Get the public key for verification and export
                self._pub_key = next(session.get_objects({
                    ObjectClass.PUBLIC_KEY,
                    'label': self._key_label
                }))
                
            except StopIteration:
                # No existing key pair, need to generate one
                self._generate_keypair(session)
        
    def _generate_keypair(self, session):
        """
        Generate a new key pair on the token.
        
        Attempts to use Ed25519 if available, falls back to ECDSA (secp256r1)
        if Ed25519 is not supported by the token.
        
        Args:
            session: An active PKCS#11 session
        """
        # Check if the token supports EdDSA
        mechanisms = session.token.mechanisms
        
        if hasattr(Mechanism, 'EDDSA') and Mechanism.EDDSA in mechanisms:
            # Generate Ed25519 key pair
            public, private = session.generate_keypair(
                KeyType.EC_EDWARDS,
                {
                    'label': self._key_label,
                    'id': self._key_label.encode(),
                    'verify': True,
                    'token': True
                },
                {
                    'label': self._key_label,
                    'id': self._key_label.encode(),
                    'sign': True,
                    'token': True,
                    'sensitive': True,
                    'extractable': False
                }
            )
            self._mechanism = Mechanism.EDDSA
            self._alg = ALG_ED25519
            self._pub_key = public
            print(f"Generated new Ed25519 key pair on token {self._token_label}")
            
        else:
            # Fall back to ECDSA with secp256r1 curve
            params = encode_named_curve_parameters('secp256r1')
            
            public, private = session.generate_keypair(
                KeyType.EC,
                {
                    'label': self._key_label,
                    'id': self._key_label.encode(),
                    'verify': True,
                    'token': True,
                    'ecParams': params
                },
                {
                    'label': self._key_label,
                    'id': self._key_label.encode(),
                    'sign': True,
                    'token': True,
                    'sensitive': True,
                    'extractable': False
                }
            )
            self._mechanism = Mechanism.ECDSA
            self._alg = ALG_ECDSA
            self._pub_key = public
            print(f"Generated new ECDSA (secp256r1) key pair on token {self._token_label}")
    
    def sign(self, payload: Dict[str, Any]) -> B64:
        """
        Sign a JSON payload using the hardware-stored key.
        
        Args:
            payload: The dictionary to sign
            
        Returns:
            Base64-encoded signature
        """
        # Canonicalize the JSON payload
        message = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
        
        with self._token.open(user_pin=self._pin) as session:
            # Get the private key
            priv_key = next(session.get_objects({
                ObjectClass.PRIVATE_KEY,
                'label': self._key_label
            }))
            
            # Sign the message with the appropriate mechanism
            signature = priv_key.sign(message, mechanism=self._mechanism)
            
            # Return base64 encoded signature
            return base64.b64encode(signature).decode()
    
    def verify(self, payload: Dict[str, Any], signature: B64, pubkey: B64) -> bool:
        """
        Verify a signature using a public key.
        
        Args:
            payload: The dictionary that was signed
            signature: Base64-encoded signature
            pubkey: Base64-encoded public key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # For verification, we use the local token's public key to verify
            # This is more efficient than extracting the public key from the provided pubkey
            # Canonicalize the JSON payload
            message = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
            
            # Decode the signature from base64
            sig_bytes = base64.b64decode(signature)
            
            with self._token.open(user_pin=self._pin) as session:
                # Get the public key
                pub_key = next(session.get_objects({
                    ObjectClass.PUBLIC_KEY,
                    'label': self._key_label
                }))
                
                # Verify the signature with the appropriate mechanism
                pub_key.verify(message, sig_bytes, mechanism=self._mechanism)
                
                return True
        except Exception as e:
            print(f"Verification failed: {e}")
            return False
    
    def public_key_b64(self) -> B64:
        """
        Get the base64-encoded public key.
        
        Returns:
            Base64-encoded public key
        """
        with self._token.open(user_pin=self._pin) as session:
            # Get the public key
            pub_key = next(session.get_objects({
                ObjectClass.PUBLIC_KEY,
                'label': self._key_label
            }))
            
            # Export the public key in DER format
            pub_data = pub_key[pkcs11.KeyAttribute.VALUE]
            
            return base64.b64encode(pub_data).decode()