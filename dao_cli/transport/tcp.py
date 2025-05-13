"""
TCP-like transport implementation.

This module provides a reliable, connection-oriented transport
for low-bandwidth channels. It implements connection setup, teardown,
guaranteed delivery through acknowledgments, and automatic retransmissions.
"""

import asyncio
import logging
import struct
import time
import uuid
from typing import Dict, Optional, Set, Tuple

try:
    from ..channels.backchannel_encode import MicroChannel
except ImportError:
    # Use mock for testing
    from .tests.mock_channel import MicroChannel

from .base import Transport, ConnectionError, TransportError
from .constants import (
    VERSION, FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_FRAG,
    FLAG_SYN_ACK, FLAG_FIN_ACK, MTU, INITIAL_TIMEOUT,
    BACKOFF_FACTOR, MAX_RETRIES, MAX_SEQ_NUM
)
from .header import PacketHeader


class RetransmitHandler:
    """Handles packet retransmission logic and timeout calculations."""
    
    def __init__(self, timeout: float = INITIAL_TIMEOUT, max_retries: int = MAX_RETRIES):
        """Initialize the retransmission handler.
        
        Args:
            timeout: Initial timeout in seconds
            max_retries: Maximum number of retransmission attempts
        """
        self.initial_timeout = timeout
        self.current_timeout = timeout
        self.max_retries = max_retries
        self.retries = 0
        self.last_send_time = 0.0
    
    def reset(self) -> None:
        """Reset the handler to initial state."""
        self.current_timeout = self.initial_timeout
        self.retries = 0
        self.last_send_time = 0.0
    
    def record_send(self) -> None:
        """Record that a packet was sent."""
        self.last_send_time = time.monotonic()
    
    def should_retransmit(self) -> bool:
        """Check if the packet should be retransmitted."""
        elapsed = time.monotonic() - self.last_send_time
        return elapsed > self.current_timeout and self.retries < self.max_retries
    
    def retransmit(self) -> None:
        """Mark a retransmission attempt."""
        self.retries += 1
        self.current_timeout *= BACKOFF_FACTOR
        self.last_send_time = time.monotonic()
    
    @property
    def has_failed(self) -> bool:
        """Check if retransmission has failed (exceeded max retries)."""
        return self.retries >= self.max_retries


class TcpTransport(Transport):
    """
    TCP-like reliable transport implementation.
    
    Provides reliable, ordered data transmission over micro-channels using:
    - Three-way handshake for connection setup
    - Stop-and-wait flow control with acknowledgments
    - Automatic retransmission of unacknowledged packets
    - Connection teardown
    """
    
    def __init__(self):
        """Initialize the TCP transport."""
        super().__init__()
        
        # Sequence number tracking
        self._next_seq: Dict[int, int] = {}  # channel_id -> next seq number to use
        
        # Acknowledgment tracking
        self._expected_acks: Dict[Tuple[int, int], asyncio.Event] = {}  # (channel_id, seq) -> ack event
        self._received_acks: Dict[int, int] = {}  # channel_id -> highest ack received
        
        # Pending retransmissions
        self._pending_packets: Dict[Tuple[int, int], Tuple[bytes, RetransmitHandler, MicroChannel]] = {}  # (channel, seq) -> (packet, handler, channel)
        
        # Connection state
        self._connections: Set[int] = set()  # Set of channels with established connections
        
        # Defer creating asyncio event objects until an event loop exists
        self._stop_ticker = None
        self._ticker_task = None
    
    async def _start_ticker(self):
        """Start the background task for managing retransmissions."""
        # Create the Event in an asyncio context
        if self._stop_ticker is None:
            self._stop_ticker = asyncio.Event()
            
        if self._ticker_task is None:
            self._ticker_task = asyncio.create_task(self._ticker())
    
    async def _ticker(self):
        """Background task that checks for packets that need retransmission."""
        while not self._stop_ticker.is_set():
            try:
                await asyncio.sleep(0.1)  # Check 10 times per second
                
                # Check each pending packet
                for (channel_id, seq), (packet, handler, chan) in list(self._pending_packets.items()):
                    try:
                        # Check if we've exceeded max retries
                        if handler.has_failed:
                            self.logger.warning(
                                f"Failed to receive ACK for packet on channel {channel_id}, "
                                f"seq {seq} after {handler.retries} retries"
                            )
                            # Fail the pending ACK wait and remove the packet
                            if (channel_id, seq) in self._expected_acks:
                                self._expected_acks[channel_id, seq].set()
                            del self._pending_packets[channel_id, seq]
                            continue
                        
                        # Check if it's time to retransmit
                        if handler.should_retransmit():
                            self.logger.debug(
                                f"Retransmitting packet on channel {channel_id}, "
                                f"seq {seq}, attempt {handler.retries + 1}/{handler.max_retries}"
                            )
                            # Send the packet again
                            chan.send(packet)
                            handler.retransmit()
                    except Exception as e:
                        self.logger.error(f"Error in retransmission ticker: {e}")
                        continue
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in retransmission ticker: {e}")
    
    async def send(
        self,
        data: bytes,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> None:
        """
        Send data using reliable TCP-like delivery.
        
        - Establishes a connection if not already established
        - Handles fragmentation for large messages
        - Ensures delivery through acknowledgments and retransmissions
        
        Args:
            data: The data to send
            chan: The channel to send through
            channel_id: Channel identifier (default: 0)
            
        Raises:
            ConnectionError: If connection establishment fails
            TransportError: If data transmission fails
        """
        if not self._ticker_task:
            await self._start_ticker()
            
        # Ensure we have an established connection
        if channel_id not in self._connections:
            await self._establish_connection(chan, channel_id)
        
        # If data is empty, nothing to send
        if not data:
            self.logger.debug("No data to send")
            return
        
        # Determine if we need fragmentation
        if len(data) <= self.MTU:
            # Small enough for a single packet
            await self._send_with_ack(data, chan, channel_id)
        else:
            # Fragment and send each piece
            await self._send_fragmented(data, chan, channel_id)
    
    async def _establish_connection(self, chan: MicroChannel, channel_id: int) -> None:
        """Establish a TCP-like connection using three-way handshake."""
        # Initialize sequence numbers if not already done
        if channel_id not in self._next_seq:
            self._next_seq[channel_id] = 0
        
        # Sequence number for SYN packet
        seq = self._next_seq[channel_id]
        
        # Create SYN packet
        syn_header = PacketHeader(
            version=VERSION,
            flags=FLAG_SYN,
            channel_id=channel_id,
            seq_no=seq,
            payload_length=0,
            channel=chan  # Store the channel reference
        )
        syn_packet = syn_header.encode()
        
        # Create handler for SYN retransmission
        handler = RetransmitHandler()
        self._pending_packets[channel_id, seq] = (syn_packet, handler, chan)
        
        # Set up acknowledgment tracking
        ack_event = asyncio.Event()
        self._expected_acks[channel_id, seq] = ack_event
        
        try:
            # Send SYN packet
            self.logger.debug(f"Sending SYN packet to channel {channel_id}, seq {seq}")
            chan.send(syn_packet)
            handler.record_send()
            
            # Wait for SYN-ACK
            self.logger.debug(f"Waiting for SYN-ACK on channel {channel_id}")
            await asyncio.wait_for(ack_event.wait(), timeout=INITIAL_TIMEOUT * 2)
            
            # Clean up after receiving ACK
            del self._expected_acks[channel_id, seq]
            del self._pending_packets[channel_id, seq]
            
            # Connection is established
            self._connections.add(channel_id)
            
            # Increment sequence number
            self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
            self.logger.info(f"Connection established on channel {channel_id}")
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for SYN-ACK on channel {channel_id}")
            # Clean up
            if (channel_id, seq) in self._expected_acks:
                del self._expected_acks[channel_id, seq]
            if (channel_id, seq) in self._pending_packets:
                del self._pending_packets[channel_id, seq]
            raise ConnectionError(f"Failed to establish connection on channel {channel_id}")
    
    async def _send_with_ack(self, data: bytes, chan: MicroChannel, channel_id: int) -> None:
        """Send data with reliable acknowledgment."""
        # Get next sequence number
        seq = self._next_seq[channel_id]
        
        # Create packet header
        header = PacketHeader(
            version=VERSION,
            flags=0,  # Regular data packet
            channel_id=channel_id,
            seq_no=seq,
            payload_length=len(data),
            channel=chan  # Store the channel reference
        )
        packet = header.encode() + data
        
        # Create handler for retransmission
        handler = RetransmitHandler()
        self._pending_packets[channel_id, seq] = (packet, handler, chan)
        
        # Set up acknowledgment tracking
        ack_event = asyncio.Event()
        self._expected_acks[channel_id, seq] = ack_event
        
        try:
            # Send the packet
            self.logger.debug(f"Sending data packet to channel {channel_id}, seq {seq}, size {len(data)}")
            chan.send(packet)
            handler.record_send()
            
            # Wait for ACK
            self.logger.debug(f"Waiting for ACK on channel {channel_id}, seq {seq}")
            await asyncio.wait_for(ack_event.wait(), timeout=INITIAL_TIMEOUT * 4)
            
            # Clean up after receiving ACK
            del self._expected_acks[channel_id, seq]
            del self._pending_packets[channel_id, seq]
            
            # Increment sequence number
            self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for ACK on channel {channel_id}, seq {seq}")
            # Clean up
            if (channel_id, seq) in self._expected_acks:
                del self._expected_acks[channel_id, seq]
            if (channel_id, seq) in self._pending_packets:
                del self._pending_packets[channel_id, seq]
            raise TransportError(f"Failed to get acknowledgment for data on channel {channel_id}")
    
    async def _send_fragmented(self, data: bytes, chan: MicroChannel, channel_id: int) -> None:
        """Send fragmented data with reliable acknowledgment."""
        # Generate a unique fragment ID
        frag_id = uuid.uuid4().int & 0xFFFFFFFF
        
        # Calculate max payload per fragment (accounting for fragment header)
        max_payload = self.MTU - 6  # Subtract 6 bytes for frag_id and offset
        
        # Split the data into fragments and send each one
        offset = 0
        while offset < len(data):
            # Get the current fragment
            fragment = data[offset:offset + max_payload]
            
            # Get next sequence number
            seq = self._next_seq[channel_id]
            
            # Create fragment header
            header = PacketHeader(
                version=VERSION,
                flags=FLAG_FRAG,
                channel_id=channel_id,
                seq_no=seq,
                payload_length=len(fragment),
                frag_id=frag_id,
                frag_offset=offset,
                channel=chan  # Store the channel reference
            )
            packet = header.encode() + fragment
            
            # Create handler for retransmission
            handler = RetransmitHandler()
            self._pending_packets[channel_id, seq] = (packet, handler, chan)
            
            # Set up acknowledgment tracking
            ack_event = asyncio.Event()
            self._expected_acks[channel_id, seq] = ack_event
            
            try:
                # Send the fragment
                self.logger.debug(
                    f"Sending fragment {offset}/{len(data)} to channel {channel_id}, "
                    f"seq {seq}, size {len(fragment)}"
                )
                chan.send(packet)
                handler.record_send()
                
                # Wait for ACK
                self.logger.debug(f"Waiting for ACK on channel {channel_id}, seq {seq}")
                await asyncio.wait_for(ack_event.wait(), timeout=INITIAL_TIMEOUT * 4)
                
                # Clean up after receiving ACK
                del self._expected_acks[channel_id, seq]
                del self._pending_packets[channel_id, seq]
                
                # Increment sequence number
                self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
                
                # Move to next fragment
                offset += len(fragment)
                
            except asyncio.TimeoutError:
                self.logger.error(f"Timeout waiting for ACK on channel {channel_id}, seq {seq}")
                # Clean up
                if (channel_id, seq) in self._expected_acks:
                    del self._expected_acks[channel_id, seq]
                if (channel_id, seq) in self._pending_packets:
                    del self._pending_packets[channel_id, seq]
                raise TransportError(f"Failed to get acknowledgment for fragment on channel {channel_id}")
    
    async def _close_connection(self, chan: MicroChannel, channel_id: int) -> None:
        """Close a TCP-like connection using FIN/ACK exchange."""
        # Check if connection exists
        if channel_id not in self._connections:
            self.logger.warning(f"Attempted to close non-existent connection on channel {channel_id}")
            return
        
        # Get next sequence number
        seq = self._next_seq[channel_id]
        
        # Create FIN packet
        fin_header = PacketHeader(
            version=VERSION,
            flags=FLAG_FIN,
            channel_id=channel_id,
            seq_no=seq,
            payload_length=0,
            channel=chan  # Store the channel reference
        )
        fin_packet = fin_header.encode()
        
        # Create handler for FIN retransmission
        handler = RetransmitHandler()
        self._pending_packets[channel_id, seq] = (fin_packet, handler, chan)
        
        # Set up acknowledgment tracking
        ack_event = asyncio.Event()
        self._expected_acks[channel_id, seq] = ack_event
        
        try:
            # Send FIN packet
            self.logger.debug(f"Sending FIN packet to channel {channel_id}, seq {seq}")
            chan.send(fin_packet)
            handler.record_send()
            
            # Wait for FIN-ACK
            self.logger.debug(f"Waiting for FIN-ACK on channel {channel_id}")
            await asyncio.wait_for(ack_event.wait(), timeout=INITIAL_TIMEOUT * 2)
            
            # Clean up after receiving ACK
            del self._expected_acks[channel_id, seq]
            del self._pending_packets[channel_id, seq]
            
            # Connection is closed
            self._connections.remove(channel_id)
            
            # Increment sequence number
            self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
            self.logger.info(f"Connection closed on channel {channel_id}")
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for FIN-ACK on channel {channel_id}")
            # Clean up
            if (channel_id, seq) in self._expected_acks:
                del self._expected_acks[channel_id, seq]
            if (channel_id, seq) in self._pending_packets:
                del self._pending_packets[channel_id, seq]
            raise ConnectionError(f"Failed to close connection on channel {channel_id}")
    
    async def recv(
        self,
        chan: MicroChannel,
        channel_id: int = 0,
    ) -> bytes:
        """
        Receive data using reliable TCP-like reception.
        
        - Handles connection establishment/acceptance
        - Acknowledges received packets
        - Reassembles fragmented messages
        
        Args:
            chan: The channel to receive from
            channel_id: Channel identifier (default: 0)
            
        Returns:
            bytes: The received data
            
        Raises:
            TransportError: If there's an error receiving or processing the packet
        """
        if not self._ticker_task:
            await self._start_ticker()
            
        # Initialize sequence tracking if not done already
        if channel_id not in self._received_acks:
            self._received_acks[channel_id] = -1
            
        # Read from the channel
        raw_packet = chan.receive()
        if raw_packet is None:
            return b""
        
        try:
            # Decode header
            header, bytes_consumed = PacketHeader.decode(raw_packet)
            
            # For connection management
            if header.is_syn:
                return await self._handle_syn(header, chan, channel_id)
            elif header.is_fin:
                return await self._handle_fin(header, chan, channel_id)
            elif header.is_rst:
                return await self._handle_rst(header, chan, channel_id)
            
            # For regular data packets
            if header.is_ack:
                await self._handle_ack(header, channel_id)
                
            # Extract payload
            payload = raw_packet[bytes_consumed:]
            
            # Send acknowledgment for the received packet
            await self._send_ack(header.seq_no, chan, channel_id)
            
            # Update highest received ack
            self._received_acks[channel_id] = header.seq_no
            
            # If no payload, just return empty
            if not payload:
                return b""
            
            # Check if this is a fragment
            if header.is_frag:
                # Handle fragments similar to UDP but with reliability
                return await self._handle_fragment(header, payload)
            else:
                # Regular data packet
                return payload
            
        except Exception as e:
            self.logger.error(f"Error receiving TCP packet: {e}")
            raise TransportError(f"Failed to receive TCP packet: {e}") from e
    
    async def _handle_syn(
        self,
        header: PacketHeader,
        chan: MicroChannel,
        channel_id: int,
    ) -> bytes:
        """Handle a SYN packet (connection request)."""
        self.logger.debug(f"Received SYN packet on channel {channel_id}, seq {header.seq_no}")
        
        # Send SYN-ACK
        syn_ack_header = PacketHeader(
            version=VERSION,
            flags=FLAG_SYN_ACK,
            channel_id=channel_id,
            seq_no=0,  # First sequence from our side
            payload_length=0,
            channel=chan  # Store the channel reference
        )
        syn_ack_packet = syn_ack_header.encode()
        
        # Initialize sequence tracking if not done yet
        if channel_id not in self._next_seq:
            self._next_seq[channel_id] = 0
            
        # Update received ack
        self._received_acks[channel_id] = header.seq_no
            
        # Send SYN-ACK
        self.logger.debug(f"Sending SYN-ACK to channel {channel_id}")
        chan.send(syn_ack_packet)
        
        # Connection is now established
        self._connections.add(channel_id)
        
        # We don't have any data to return yet
        return b""
    
    async def _handle_fin(
        self,
        header: PacketHeader,
        chan: MicroChannel,
        channel_id: int,
    ) -> bytes:
        """Handle a FIN packet (connection close)."""
        self.logger.debug(f"Received FIN packet on channel {channel_id}, seq {header.seq_no}")
        
        # Send FIN-ACK
        fin_ack_header = PacketHeader(
            version=VERSION,
            flags=FLAG_FIN_ACK,
            channel_id=channel_id,
            seq_no=self._next_seq.get(channel_id, 0),
            payload_length=0,
            channel=chan  # Store the channel reference
        )
        fin_ack_packet = fin_ack_header.encode()
        
        # Update received ack
        self._received_acks[channel_id] = header.seq_no
            
        # Send FIN-ACK
        self.logger.debug(f"Sending FIN-ACK to channel {channel_id}")
        chan.send(fin_ack_packet)
        
        # Remove connection
        if channel_id in self._connections:
            self._connections.remove(channel_id)
        
        # We don't have any data to return
        return b""
    
    async def _handle_rst(
        self,
        header: PacketHeader,
        chan: MicroChannel,
        channel_id: int,
    ) -> bytes:
        """Handle an RST packet (connection reset)."""
        self.logger.debug(f"Received RST packet on channel {channel_id}, seq {header.seq_no}")
        
        # Reset connection state
        if channel_id in self._connections:
            self._connections.remove(channel_id)
        if channel_id in self._next_seq:
            self._next_seq[channel_id] = 0
        if channel_id in self._received_acks:
            self._received_acks[channel_id] = -1
            
        # Clean up any pending packets for this channel
        for key in list(self._expected_acks.keys()):
            if key[0] == channel_id:
                self._expected_acks[key].set()  # Signal to unblock any waiters
                del self._expected_acks[key]
        
        for key in list(self._pending_packets.keys()):
            if key[0] == channel_id:
                del self._pending_packets[key]
                
        # We don't have any data to return
        return b""
    
    async def _handle_ack(self, header: PacketHeader, channel_id: int) -> None:
        """Process an acknowledgment packet."""
        seq = header.seq_no
        ack_key = (channel_id, seq)
        
        # Check if we're waiting for this ACK
        if ack_key in self._expected_acks:
            self.logger.debug(f"Received ACK for seq {seq} on channel {channel_id}")
            # Signal that the ACK was received
            self._expected_acks[ack_key].set()
        else:
            self.logger.debug(f"Received unexpected ACK for seq {seq} on channel {channel_id}")
    
    async def _send_ack(self, seq: int, chan: MicroChannel, channel_id: int) -> None:
        """Send an acknowledgment for a received packet."""
        ack_header = PacketHeader(
            version=VERSION,
            flags=FLAG_ACK,
            channel_id=channel_id,
            seq_no=seq,  # ACK the sequence we received
            payload_length=0,
            channel=chan  # Store the channel reference
        )
        ack_packet = ack_header.encode()
        
        # Send ACK (no retransmission for ACKs)
        self.logger.debug(f"Sending ACK for seq {seq} on channel {channel_id}")
        chan.send(ack_packet)
    
    async def _handle_fragment(self, header: PacketHeader, payload: bytes) -> bytes:
        """Handle a received fragment."""
        # Basic implementation - just return the fragment payload
        # In a more robust implementation, we would track and reassemble
        return payload
        
    async def __aenter__(self):
        """Start the background tasks when used as a context manager."""
        await self._start_ticker()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context manager."""
        if self._ticker_task:
            self._stop_ticker.set()
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass
        return False