"""
Transport layer for microchannel communications.

This module provides TCP-like and UDP-like transport protocols
for reliable and best-effort data transmission over low-bandwidth channels.
"""

# Import public API
from .base import Transport, TransportError, ConnectionError, FragmentationError
from .header import PacketHeader
from .constants import (
    VERSION, FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_FRAG,
    FLAG_SYN_ACK, FLAG_FIN_ACK, HEADER_SIZE, FRAG_HEADER_SIZE,
    MTU, INITIAL_TIMEOUT, BACKOFF_FACTOR, MAX_RETRIES
)
from .tcp import TcpTransport
from .udp import UdpTransport

__all__ = [
    'Transport',
    'TransportError',
    'ConnectionError',
    'FragmentationError',
    'PacketHeader',
    'TcpTransport',
    'UdpTransport',
]