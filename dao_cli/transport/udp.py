"""
UDP-like transport implementation.

This module provides a best-effort, connectionless datagram transport
for low-bandwidth channels. It supports packet fragmentation and reassembly
but does not guarantee delivery or ordering.
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

try:
    from ..channels.backchannel_encode import MicroChannel
except ImportError:
    # Use mock for testing
    from .tests.mock_channel import MicroChannel

from .base import Transport, FragmentationError, TransportError
from .constants import (
    VERSION, FLAG_FRAG, MTU, FRAGMENT_TIMEOUT
)
from .header import PacketHeader


class UdpTransport(Transport):
    """
    UDP-like datagram transport implementation.

    Provides best-effort, connectionless datagram delivery over micro-channels.
    Supports fragmentation and reassembly for payloads larger than the MTU.
    Does not provide delivery guarantees or ordering.
    """

    def __init__(self) -> None:
        """Initialize the UDP transport."""
        super().__init__()
        
        # Store fragments waiting for reassembly
        self._fragments: Dict[Tuple[int, int], Dict[int, bytes]] = {}
        self._fragment_timeouts: Dict[Tuple[int, int], float] = {}
    
    async def send(
        self,
        data: bytes,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> None:
        """
        Send data using UDP-like best-effort delivery.

        For payloads larger than MTU, fragments the data and sends multiple packets.
        Does not wait for acknowledgment.
        
        Args:
            data: The data to send
            chan: The channel to send through
            channel_id: Channel identifier (default: 0)
            
        Raises:
            TransportError: If there's an error encoding or writing the packet
        """
        if not data:
            self.logger.debug("No data to send")
            return
        
        # Determine if we need fragmentation
        if len(data) <= self.MTU:
            # Small enough for a single packet
            await self._send_single_packet(data, chan, channel_id)
        else:
            # Need to fragment
            await self._send_fragmented_packets(data, chan, channel_id)
    
    async def _send_single_packet(
        self,
        data: bytes,
        chan: MicroChannel,
        channel_id: int,
    ) -> None:
        """Send a single UDP packet."""
        header = PacketHeader(
            version=VERSION,
            flags=0,  # No flags for UDP
            channel_id=channel_id,
            seq_no=0,  # Not used in UDP mode
            payload_length=len(data)
        )
        
        try:
            # Encode and send
            packet = header.encode() + data
            chan.send(packet)
            self.logger.debug(f"Sent {len(data)} bytes as single UDP packet to channel {channel_id}")
        except Exception as e:
            self.logger.error(f"Error sending UDP packet: {e}")
            raise TransportError(f"Failed to send UDP packet: {e}") from e
    
    async def _send_fragmented_packets(
        self,
        data: bytes,
        chan: MicroChannel,
        channel_id: int,
    ) -> None:
        """Send fragmented UDP packets for large payloads."""
        # Generate a unique fragment ID for this message
        frag_id = uuid.uuid4().int & 0xFFFFFFFF
        
        # Calculate max payload per fragment (accounting for fragment header)
        max_payload = self.MTU - 6  # Subtract 6 bytes for frag_id and offset
        
        # Split the data into fragments
        offset = 0
        while offset < len(data):
            # Get the current fragment
            fragment = data[offset:offset + max_payload]
            
            # Create header with FRAG flag
            header = PacketHeader(
                version=VERSION,
                flags=FLAG_FRAG,
                channel_id=channel_id,
                seq_no=0,  # Not used in UDP mode
                payload_length=len(fragment),
                frag_id=frag_id,
                frag_offset=offset
            )
            
            try:
                # Encode and send
                packet = header.encode() + fragment
                chan.send(packet)
                self.logger.debug(
                    f"Sent fragment {offset}/{len(data)} of message {frag_id} "
                    f"({len(fragment)} bytes) to channel {channel_id}"
                )
            except Exception as e:
                self.logger.error(f"Error sending UDP fragment: {e}")
                raise TransportError(f"Failed to send UDP fragment: {e}") from e
            
            # Move to next fragment
            offset += len(fragment)
    
    async def recv(
        self,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> bytes:
        """
        Receive data using UDP-like best-effort reception.

        For fragmented packets, attempts to reassemble the complete message.
        May return partial data if not all fragments arrive.
        
        Args:
            chan: The channel to receive from
            channel_id: Channel identifier (default: 0)
            
        Returns:
            bytes: The received data
            
        Raises:
            TransportError: If there's an error receiving or processing the packet
        """
        # Clean up expired fragments
        self._cleanup_expired_fragments()
        
        # Read from the channel
        raw_packet = chan.receive()
        if raw_packet is None:
            return b""
        
        try:
            # Decode header
            header, bytes_consumed = PacketHeader.decode(raw_packet)
            
            # Extract payload
            payload = raw_packet[bytes_consumed:]
            
            # Check if this is a fragment
            if header.is_frag:
                return await self._handle_fragment(header, payload, channel_id)
            else:
                # Simple packet, just return the payload
                self.logger.debug(f"Received {len(payload)} bytes from channel {channel_id}")
                return payload
        except Exception as e:
            self.logger.error(f"Error receiving UDP packet: {e}")
            raise TransportError(f"Failed to receive UDP packet: {e}") from e
    
    async def _handle_fragment(
        self,
        header: PacketHeader,
        payload: bytes,
        channel_id: int,
    ) -> bytes:
        """Handle a received fragment and reassemble if possible."""
        # Ensure frag_id and offset are not None (should be guaranteed by header.is_frag)
        if header.frag_id is None or header.frag_offset is None:
            self.logger.error("Fragment header missing frag_id or offset")
            raise FragmentationError("Fragment header missing frag_id or offset")
        
        # Create a unique key for this fragmented message
        msg_key = (channel_id, header.frag_id)
        
        # Initialize tracking structures if this is a new fragmented message
        if msg_key not in self._fragments:
            self._fragments[msg_key] = {}
            self._fragment_timeouts[msg_key] = time.monotonic() + FRAGMENT_TIMEOUT
            self.logger.debug(f"Starting new fragmented message {header.frag_id} on channel {channel_id}")
        
        # Store this fragment
        self._fragments[msg_key][header.frag_offset] = payload
        
        self.logger.debug(
            f"Received fragment {header.frag_offset}, size {len(payload)} "
            f"for message {header.frag_id} on channel {channel_id}, "
            f"now have {len(self._fragments[msg_key])} fragments"
        )
        
        # Try to reassemble the message
        result = self._try_reassemble(msg_key)
        return result
    
    def _try_reassemble(self, msg_key: Tuple[int, int]) -> bytes:
        """
        Try to reassemble a fragmented message from its fragments.
        
        Args:
            msg_key: (channel_id, frag_id) tuple identifying the message
            
        Returns:
            bytes: The reassembled data if successful, or empty bytes if incomplete
        """
        # Need to have the first fragment (offset 0)
        if 0 not in self._fragments[msg_key]:
            return b""
        
        # Start from the first fragment
        offsets = sorted(self._fragments[msg_key].keys())
        
        # Create a result buffer to hold all the data
        result = bytearray()
        
        # Iterate through fragments in order by offset
        current_offset = 0
        for offset in offsets:
            # If there's a gap in offsets, we can only return up to the gap
            if offset > current_offset:
                break
                
            # Append this fragment
            fragment = self._fragments[msg_key][offset]
            result.extend(fragment)
            current_offset = offset + len(fragment)
        
        # If we have at least some fragments, return what we've got
        if result:
            return bytes(result)
        
        return b""
    
    def _cleanup_expired_fragments(self) -> None:
        """Remove fragment tracking for messages that have timed out."""
        now = time.monotonic()
        expired_keys = []
        
        for key, expire_time in list(self._fragment_timeouts.items()):
            if expire_time <= now:
                expired_keys.append(key)
                self.logger.debug(f"Fragment {key[1]} on channel {key[0]} expired")
                
                # Remove the fragments immediately
                if key in self._fragments:
                    del self._fragments[key]
                if key in self._fragment_timeouts:
                    del self._fragment_timeouts[key]