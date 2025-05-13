# FIPS Compliance Guide for DAO CLI

This document explains how to set up the DAO CLI in a FIPS-compliant mode, using OpenSSL 3.x with the FIPS provider module.

## Overview

The DAO CLI can operate in FIPS (Federal Information Processing Standards) mode, which is required for government and security-sensitive deployments. In this mode:

1. All cryptographic operations use validated algorithms
2. The system ensures OpenSSL is running with its FIPS provider enabled
3. All signatures are performed either by the FIPS-validated OpenSSL library or by a hardware security module

## Requirements

To run the DAO CLI in FIPS mode, you need:

1. OpenSSL 3.x compiled with FIPS provider support
2. pyca/cryptography built against this OpenSSL installation
3. (Optional) A PKCS#11-compatible hardware security module

## Setting up OpenSSL with FIPS Provider

### Step 1: Build OpenSSL 3.x with FIPS module

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install build-essential checkinstall zlib1g-dev -y

# Download OpenSSL source
cd /usr/local/src/
wget https://www.openssl.org/source/openssl-3.2.0.tar.gz
tar -xvf openssl-3.2.0.tar.gz
cd openssl-3.2.0/

# Configure with FIPS support
./config enable-fips shared --prefix=/usr/local/ssl --openssldir=/usr/local/ssl

# Build and install
make
sudo make install
```

### Step 2: Configure OpenSSL for FIPS mode

Create or modify the OpenSSL configuration file at `/usr/local/ssl/openssl.cnf`:

```
# OpenSSL FIPS configuration
openssl_conf = openssl_init

[openssl_init]
providers = providers_sect

[providers_sect]
fips = fips_sect
base = base_sect

[base_sect]
activate = 1

[fips_sect]
activate = 1
```

### Step 3: Build cryptography against FIPS-enabled OpenSSL

```bash
# Set environment variables to point to the custom OpenSSL build
export CFLAGS="-I/usr/local/ssl/include"
export LDFLAGS="-L/usr/local/ssl/lib"
export LD_LIBRARY_PATH=/usr/local/ssl/lib:$LD_LIBRARY_PATH
export OPENSSL_CONF=/usr/local/ssl/openssl.cnf

# Install cryptography with FIPS-enabled OpenSSL
pip install --force-reinstall --no-binary cryptography cryptography
```

## Enabling FIPS Mode in DAO CLI

Set the environment variable `DAO_FIPS_ONLY=1` to enable strict FIPS mode:

```bash
export DAO_FIPS_ONLY=1
```

In this mode, the CLI will:
1. Check that OpenSSL is running in FIPS mode
2. Fail with an error message if FIPS mode is not enabled
3. Only use algorithms approved by FIPS 140-2/140-3

## Using with Hardware Security Modules

For hardware-based key storage, set the following environment variables:

```bash
# Select the PKCS#11 backend
export DAO_CRYPTO_BACKEND=pkcs11

# Configure your HSM
export DAO_PKCS11_LIB_PATH=/path/to/your/pkcs11/library.so
export DAO_PKCS11_TOKEN_LABEL=your-token-label
export DAO_PKCS11_KEY_LABEL=your-key-label
export DAO_PKCS11_PIN=your-pin
```

## Verifying FIPS Mode

To verify that OpenSSL is running in FIPS mode:

```bash
openssl version -f
# Should include "FIPS" in the output

# You can also check directly from Python
python -c "import ssl; print('FIPS mode:', ssl.OPENSSL_VERSION, 'FIPS' in ssl.OPENSSL_VERSION)"
```

## Troubleshooting

If you encounter issues with FIPS mode:

1. Ensure OpenSSL is properly compiled with FIPS provider support
2. Check that the OpenSSL configuration file is correctly set up
3. Verify that the pyca/cryptography library was built against the correct OpenSSL version
4. Make sure all environment variables are set correctly

## FIPS Certification References

The following NIST certificates cover the cryptographic modules used:

- OpenSSL 3.x FIPS Provider: NIST CMVP Certificate #XXXX
- YubiKey PKCS#11 implementations: NIST CMVP Certificate #YYYY
- Cloud HSM solutions: Various certifications depending on provider

Always check for the most recent certification status at the [NIST Cryptographic Module Validation Program](https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules) website.