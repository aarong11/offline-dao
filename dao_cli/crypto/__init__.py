"""
DAO crypto module selector.

This module selects and initializes the appropriate crypto backend
based on environment variables and user preferences.
"""
import os
import subprocess
import sys
from typing import Optional

from .constants import (
    DAO_FIPS_ONLY,
    DAO_CRYPTO_BACKEND,
    BACKEND_SOFTWARE,
    BACKEND_PKCS11,
)
from .adapter_base import CryptoAdapter

# Global adapter instance
_adapter: Optional[CryptoAdapter] = None


def _check_fips_mode() -> bool:
    """
    Check if OpenSSL is running in FIPS mode.
    
    Returns:
        True if OpenSSL is in FIPS mode, False otherwise
    """
    try:
        result = subprocess.run(
            ['openssl', 'version', '-f'],
            capture_output=True,
            text=True,
            check=False
        )
        return 'FIPS' in result.stdout
    except Exception:
        return False


def _is_fips_required() -> bool:
    """
    Check if FIPS mode is required based on environment settings.
    
    Returns:
        True if FIPS mode is required, False otherwise
    """
    return os.environ.get(DAO_FIPS_ONLY, '0').lower() in ('1', 'true', 'yes')


def get_adapter() -> CryptoAdapter:
    """
    Get or create the crypto adapter based on environment settings.
    
    Returns:
        A configured CryptoAdapter instance
    
    Raises:
        RuntimeError: If FIPS is required but not available
        ImportError: If the selected backend cannot be imported
    """
    global _adapter
    if _adapter is not None:
        return _adapter
    
    # Check FIPS requirements
    fips_required = _is_fips_required()
    fips_available = _check_fips_mode()
    
    if fips_required and not fips_available:
        raise RuntimeError(
            "FIPS mode is required (DAO_FIPS_ONLY=1) but OpenSSL is not in FIPS mode. "
            "See FIPS.md for instructions on enabling FIPS mode."
        )
    
    # Determine which backend to use
    backend = os.environ.get(DAO_CRYPTO_BACKEND, BACKEND_SOFTWARE).lower()
    
    if backend == BACKEND_SOFTWARE:
        from .adapter_pycacrypto import PycaCryptoAdapter
        _adapter = PycaCryptoAdapter()
        print("Using software crypto backend (pyca/cryptography)")
    elif backend == BACKEND_PKCS11:
        from .adapter_pkcs11 import Pkcs11Adapter
        _adapter = Pkcs11Adapter()
        print(f"Using hardware crypto backend (PKCS#11) with mechanism {_adapter._mechanism.name}")
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose '{BACKEND_SOFTWARE}' or '{BACKEND_PKCS11}'")
    
    return _adapter


__all__ = ['get_adapter']