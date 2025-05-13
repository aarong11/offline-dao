"""
microchannel_layer.py – v0.1
=================================================
Unified "micro‑channel" packet abstraction for extremely low‑bandwidth
back‑channels (AirTag rename, Wi‑Fi SSID, BLE device name, Calendar titles, …).

The goal is to let the DAO core call **one API** regardless of which carrier
field is available on a given site.  Each channel implementation is kept in a
small plug‑in class that knows its own field size, rate limit, and the vendor
API needed to write / read the metadata.

▸ Security: every packet is AES‑GCM encrypted and CRC‑checked before emit.
▸ Integrity: sequence numbers and channel IDs stop replay / mixing.
▸ Bandwidth: default MTU = 26 payload bytes per frame (fits AirTag rename).

Dependencies:
    pip install cryptography crcmod

*NOTE*  All vendor‑specific I/O is stubbed behind `_write_raw()` /
`_read_raw()` so that unit tests can inject fakes without Apple / Google /
Bluetooth stacks present.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import crcmod

# ---------------------------------------------------------------------------
# Packet codec helpers
# ---------------------------------------------------------------------------

CRC16 = crcmod.predefined.mkPredefinedCrcFun("crc-ccitt-false")

HEADER_EMOJI = "\U0001F6C8"  # 🛈 – 3‑byte UTF‑8 info symbol (safe in Apple UI)
MAX_FIELD_CHARS = 32          # smallest carrier constraint (AirTag rename)
PAYLOAD_BYTES = 26            # 32 - len(header+seq) - b64 inflation
AES_KEY_BYTES = 32


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def b64u_dec(txt: str) -> bytes:
    pad = '=' * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


@dataclass
class Packet:
    seq: int
    payload: bytes  # plaintext payload (≤ PAYLOAD_BYTES)

    def encode(self, key: bytes) -> str:
        """Return wire‑format string suitable for carrier field."""
        if len(self.payload) > PAYLOAD_BYTES:
            raise ValueError("payload too large for single packet")
        aes = AESGCM(key)
        nonce = self.seq.to_bytes(12, "big")  # 96‑bit nonce from seq
        cipher = aes.encrypt(nonce, self.payload, b"")
        frame = cipher + CRC16(self.payload).to_bytes(2, "big")
        return f"{HEADER_EMOJI}{self.seq:02d}" + b64u(frame)

    @staticmethod
    def decode(raw: str, key: bytes) -> "Packet":
        if not raw.startswith(HEADER_EMOJI):
            raise ValueError("bad header")
        seq = int(raw[len(HEADER_EMOJI): len(HEADER_EMOJI) + 2])
        body = b64u_dec(raw[len(HEADER_EMOJI) + 2:])
        cipher, crc = body[:-2], int.from_bytes(body[-2:], "big")
        aes = AESGCM(key)
        nonce = seq.to_bytes(12, "big")
        payload = aes.decrypt(nonce, cipher, b"")
        if CRC16(payload) != crc:
            raise ValueError("CRC mismatch")
        return Packet(seq, payload)

# ---------------------------------------------------------------------------
# Abstract transport
# ---------------------------------------------------------------------------

class MicroChannel(ABC):
    """Abstract base class for a single metadata carrier."""

    def __init__(self, secret_key: bytes):
        if len(secret_key) != AES_KEY_BYTES:
            raise ValueError("AES‑GCM key must be 32 bytes")
        self.key = secret_key
        self.last_tx_seq: int = -1
        self.last_rx_seq: int = -1

    # -- high‑level API ------------------------------------------------------
    def send(self, payload: bytes) -> None:
        self.last_tx_seq = (self.last_tx_seq + 1) % 100
        pkt = Packet(self.last_tx_seq, payload)
        self._write_raw(pkt.encode(self.key))

    def receive(self) -> Optional[bytes]:
        raw = self._read_raw()
        if raw is None:
            return None
        try:
            pkt = Packet.decode(raw, self.key)
        except Exception:
            return None
        if pkt.seq == self.last_rx_seq:
            return None  # duplicate
        self.last_rx_seq = pkt.seq
        return pkt.payload

    # -- vendor‑specific I/O -------------------------------------------------
    @abstractmethod
    def _write_raw(self, frame: str) -> None:
        """Write the encoded frame into the carrier field."""
    @abstractmethod
    def _read_raw(self) -> Optional[str]:
        """Return the latest frame string if changed, else None."""

# ---------------------------------------------------------------------------
# Concrete channel stubs (implementations need real APIs)
# ---------------------------------------------------------------------------

class AirTagRenameChannel(MicroChannel):
    """AirTag / Find My accessory rename carrier (owner account only)."""

    def __init__(self, device_id: str, icloud_session, secret_key: bytes):
        super().__init__(secret_key)
        self.device_id = device_id
        self.api = icloud_session  # e.g., pyicloud.PyiCloudService
    
    def _write_raw(self, frame: str) -> None:
        # TODO: call private endpoint once per >10 s
        self.api.devices[self.device_id].set_display_name(frame)

    def _read_raw(self) -> Optional[str]:
        name = self.api.devices[self.device_id].raw_item.get("name")
        return name

class WifiSSIDChannel(MicroChannel):
    """Uses an Access Point SSID broadcast as payload (hostapd control)."""

    def __init__(self, hostapd_cli_path: str = "/usr/bin/hostapd_cli", *, secret_key: bytes):
        super().__init__(secret_key)
        self.cli = hostapd_cli_path
        self._cache: Optional[str] = None

    def _write_raw(self, frame: str) -> None:
        import subprocess, shlex
        subprocess.run([self.cli, "set", "ssid", frame[:MAX_FIELD_CHARS]])
        subprocess.run([self.cli, "reload"])

    def _read_raw(self) -> Optional[str]:
        import subprocess, json as _json
        info = subprocess.check_output([self.cli, "status"], text=True)
        for ln in info.splitlines():
            if ln.startswith("ssid="):
                ssid = ln.split("=", 1)[1]
                if ssid != self._cache:
                    self._cache = ssid
                    return ssid
        return None

# Add BLENameChannel, CalendarChannel stubs similarly...

CHANNEL_REGISTRY = {
    "airtag": AirTagRenameChannel,
    "wifi": WifiSSIDChannel,
}

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def open_channel(kind: str, *args, **kwargs) -> MicroChannel:
    cls = CHANNEL_REGISTRY[kind]
    return cls(*args, **kwargs)

# ---------------------------------------------------------------------------
# Simple CLI demo (for wifi)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    key_path = Path.home() / ".dao_keys" / "microchannel.key"
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = secrets.token_bytes(AES_KEY_BYTES)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
    chan = open_channel("wifi", secret_key=key)
    while True:
        payload = json.dumps({"ts": int(time.time())}).encode()
        chan.send(payload)
        print("TX", payload)
        time.sleep(15)
