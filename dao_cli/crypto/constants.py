"""
Constants for the DAO crypto modules.
"""

# Environment variable to enforce FIPS compliance
DAO_FIPS_ONLY = "DAO_FIPS_ONLY"

# Environment variable to select crypto backend
DAO_CRYPTO_BACKEND = "DAO_CRYPTO_BACKEND"

# Backend types
BACKEND_SOFTWARE = "software"
BACKEND_PKCS11 = "pkcs11"

# Algorithm identifiers
ALG_ED25519 = "ed25519"
ALG_ECDSA = "ecdsa"

# PKCS11 specific constants
PKCS11_TOKEN_LABEL = "DAO_PKCS11_TOKEN_LABEL"
PKCS11_KEY_LABEL = "DAO_PKCS11_KEY_LABEL"
PKCS11_PIN = "DAO_PKCS11_PIN"
PKCS11_LIB_PATH = "DAO_PKCS11_LIB_PATH"

# Default paths
DEFAULT_KEY_DIR = "~/.dao_keys"
DEFAULT_ED25519_PRIV_PEM = "~/.dao_keys/ed25519/priv.pem"
DEFAULT_ED25519_PUB_PEM = "~/.dao_keys/ed25519/pub.pem"