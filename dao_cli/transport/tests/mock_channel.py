"""
Mock channel implementation for testing the transport layer.

This provides a minimal implementation of MicroChannel for testing 
without requiring the cryptography dependencies.
"""

from abc import ABC, abstractmethod
from typing import Optional, List


class MicroChannel:
    """Mock implementation of MicroChannel for testing."""
    
    def __init__(self):
        """Initialize the mock channel."""
        self._buffer: List[bytes] = []
        self._read_index = 0
    
    def send(self, payload: bytes) -> None:
        """Send a payload through the channel."""
        self._buffer.append(payload)
    
    def receive(self) -> Optional[bytes]:
        """Receive a payload from the channel if available."""
        if self._read_index >= len(self._buffer):
            return None
        
        data = self._buffer[self._read_index]
        self._read_index += 1
        return data