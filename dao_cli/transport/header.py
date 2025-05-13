"""
Packet header encoding and decoding for microtransport protocol.

This module provides utilities for creating and parsing packet headers
according to the transport protocol specification.
"""

import dataclasses
import struct
from typing import Optional, Tuple, Any

from .constants import (
    VERSION, FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_FRAG, 
    HEADER_SIZE, FRAG_HEADER_SIZE
)


@dataclasses.dataclass
class PacketHeader:
    """
    Packet header for microtransport protocol.
    
    Attributes:
        version: Protocol version (default: 0x01)
        flags: Bitfield for SYN, ACK, FIN, RST, and FRAG flags
        channel_id: Channel identifier (16-bit)
        seq_no: Sequence number (16-bit)
        payload_length: Length of payload in bytes (16-bit)
        frag_id: Fragment identifier (32-bit) - only if FLAG_FRAG is set
        frag_offset: Fragment offset in bytes (16-bit) - only if FLAG_FRAG is set
        channel: Reference to the channel for retransmissions (not serialized)
    """
    version: int = VERSION
    flags: int = 0
    channel_id: int = 0
    seq_no: int = 0
    payload_length: int = 0
    frag_id: Optional[int] = None
    frag_offset: Optional[int] = None
    channel: Any = None  # Reference to the original channel for retransmissions
    
    @property
    def is_syn(self) -> bool:
        """Check if SYN flag is set."""
        return bool(self.flags & FLAG_SYN)
    
    @property
    def is_ack(self) -> bool:
        """Check if ACK flag is set."""
        return bool(self.flags & FLAG_ACK)
    
    @property
    def is_fin(self) -> bool:
        """Check if FIN flag is set."""
        return bool(self.flags & FLAG_FIN)
    
    @property
    def is_rst(self) -> bool:
        """Check if RST flag is set."""
        return bool(self.flags & FLAG_RST)
    
    @property
    def is_frag(self) -> bool:
        """Check if FRAG flag is set."""
        return bool(self.flags & FLAG_FRAG)
    
    def encode(self) -> bytes:
        """
        Encode the packet header to bytes.
        
        Returns:
            bytes: The encoded header
        """
        # Base header (8 bytes): version (1), flags (1), channel_id (2), seq_no (2), payload_length (2)
        header = struct.pack(">BBHHH", 
                           self.version, 
                           self.flags, 
                           self.channel_id, 
                           self.seq_no, 
                           self.payload_length)
        
        # Add fragment header if FLAG_FRAG is set
        if self.is_frag and self.frag_id is not None and self.frag_offset is not None:
            # Fragment header (6 bytes): frag_id (4), frag_offset (2)
            header += struct.pack(">IH", self.frag_id, self.frag_offset)
            
        return header
    
    @classmethod
    def decode(cls, data: bytes) -> Tuple['PacketHeader', int]:
        """
        Decode a packet header from bytes.
        
        Args:
            data: The raw bytes to decode
            
        Returns:
            Tuple[PacketHeader, int]: The decoded header and the number of bytes consumed
            
        Raises:
            ValueError: If the data is too short to contain a valid header
        """
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data too short for header: {len(data)} bytes")
        
        # Decode base header
        version, flags, channel_id, seq_no, payload_length = struct.unpack(">BBHHH", data[:HEADER_SIZE])
        
        header = cls(
            version=version,
            flags=flags,
            channel_id=channel_id,
            seq_no=seq_no,
            payload_length=payload_length
        )
        
        bytes_consumed = HEADER_SIZE
        
        # Decode fragment header if present
        if header.is_frag:
            if len(data) < HEADER_SIZE + FRAG_HEADER_SIZE:
                raise ValueError(f"Data too short for fragment header: {len(data)} bytes")
            
            frag_id, frag_offset = struct.unpack(">IH", data[HEADER_SIZE:HEADER_SIZE + FRAG_HEADER_SIZE])
            header.frag_id = frag_id
            header.frag_offset = frag_offset
            bytes_consumed += FRAG_HEADER_SIZE
            
        return header, bytes_consumed