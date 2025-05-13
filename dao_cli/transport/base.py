"""
Abstract base class for transport protocols.

This module defines the Transport abstract base class that provides
the common interface for both TCP-like and UDP-like transports.
"""

import abc
import logging
from typing import Optional

try:
    # Try importing the real MicroChannel first
    from ..channels.backchannel_encode import MicroChannel
except ImportError:
    # Fall back to the mock for testing
    from .tests.mock_channel import MicroChannel

logger = logging.getLogger(__name__)


class TransportError(Exception):
    """Base exception class for transport-related errors."""
    pass


class ConnectionError(TransportError):
    """Exception raised for connection errors."""
    pass


class FragmentationError(TransportError):
    """Exception raised for fragmentation errors."""
    pass


class Transport(abc.ABC):
    """
    Channel-agnostic transport (TCP-like or UDP-like).
    
    This abstract base class defines the interface for transport implementations
    to provide reliable or unreliable data transmission over low-bandwidth
    channels.
    """

    # Default maximum payload size per packet
    MTU: int = 248

    def __init__(self) -> None:
        """Initialize the transport."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @abc.abstractmethod
    async def send(
        self,
        data: bytes,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> None:
        """
        Send data through the given channel.
        
        Args:
            data: The data to send
            chan: The channel to send the data through
            channel_id: Channel identifier (default: 0)
            
        Raises:
            TransportError: If the data couldn't be sent
        """
        pass

    @abc.abstractmethod
    async def recv(
        self,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> bytes:
        """
        Receive data from the given channel.
        
        Args:
            chan: The channel to receive data from
            channel_id: Channel identifier (default: 0)
            
        Returns:
            bytes: The received data
            
        Raises:
            TransportError: If the data couldn't be received
        """
        pass