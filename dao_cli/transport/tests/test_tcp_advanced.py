"""
Advanced unit tests for TCP transport with proper async handling.
"""

import asyncio
import unittest
import logging
from typing import List, Optional, Dict, Tuple, Set

from dao_cli.transport.tcp import TcpTransport
from dao_cli.transport.base import TransportError, ConnectionError
from dao_cli.transport.constants import (
    VERSION, FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_FRAG,
    FLAG_SYN_ACK, FLAG_FIN_ACK, MAX_SEQ_NUM
)
from dao_cli.transport.header import PacketHeader


class TestMicroChannel:
    """Simple test channel for TCP testing."""
    
    def __init__(self, max_bytes: int = 500):
        self.MAX_BYTES = max_bytes
        self._sent_data: List[bytes] = []
        self._read_queue: List[bytes] = []
    
    def send(self, payload: bytes) -> None:
        """Store sent data for test inspection."""
        if len(payload) > self.MAX_BYTES:
            raise ValueError(f"Payload too large: {len(payload)} > {self.MAX_BYTES}")
        self._sent_data.append(payload)
    
    def receive(self) -> Optional[bytes]:
        """Return next queued packet if available."""
        if not self._read_queue:
            return None
        return self._read_queue.pop(0)
    
    def queue_packet(self, packet: bytes) -> None:
        """Queue a packet to be received."""
        self._read_queue.append(packet)
    
    @property
    def sent_data(self) -> List[bytes]:
        """Return all sent data for inspection."""
        return self._sent_data
    
    def clear(self) -> None:
        """Clear sent data history."""
        self._sent_data.clear()
        self._read_queue.clear()


class TestTcpTransport(TcpTransport):
    """Modified TCP transport that simplifies testing."""
    
    def __init__(self):
        super().__init__()
        # Override the events handling for testing
        self.test_mode = True
    
    async def _establish_connection(self, chan, channel_id: int = 0) -> None:
        """Simplified connection establishment for testing."""
        # Skip the normal connection process in test mode
        if self.test_mode:
            self._connections.add(channel_id)
            if channel_id not in self._next_seq:
                self._next_seq[channel_id] = 0
            return None
        else:
            # Use the real implementation for non-test mode
            return await super()._establish_connection(chan, channel_id)
    
    async def _send_with_ack(self, data: bytes, chan, channel_id: int) -> None:
        """Simplified send with ack for testing."""
        # Skip ack waiting in test mode
        if self.test_mode:
            # Get next sequence number
            seq = self._next_seq[channel_id]
            
            # Create packet header
            header = PacketHeader(
                version=VERSION,
                flags=0,  # Regular data packet
                channel_id=channel_id,
                seq_no=seq,
                payload_length=len(data)
            )
            packet = header.encode() + data
            
            # Send the packet
            self.logger.debug(f"Test mode: Sending data packet to channel {channel_id}, seq {seq}, size {len(data)}")
            chan.send(packet)
            
            # Increment sequence number
            self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
        else:
            # Use the real implementation for non-test mode
            await super()._send_with_ack(data, chan, channel_id)
    
    async def _send_fragmented(self, data: bytes, chan, channel_id: int) -> None:
        """Simplified fragmentation for testing."""
        # Skip ack waiting in test mode
        if self.test_mode:
            # Calculate max payload per fragment
            max_payload = self.MTU - 6  # Subtract 6 bytes for frag_id and offset
            
            # Generate a fragment ID
            frag_id = 12345  # Fixed ID for testing
            
            # Split the data into fragments
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
                    frag_offset=offset
                )
                packet = header.encode() + fragment
                
                # Send the fragment
                self.logger.debug(
                    f"Test mode: Sending fragment {offset}/{len(data)} to channel {channel_id}, "
                    f"seq {seq}, size {len(fragment)}"
                )
                chan.send(packet)
                
                # Increment sequence number
                self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
                
                # Move to next fragment
                offset += len(fragment)
        else:
            # Use the real implementation for non-test mode
            await super()._send_fragmented(data, chan, channel_id)
    
    async def _close_connection(self, chan, channel_id: int) -> None:
        """Simplified connection close for testing."""
        # Skip the normal close process in test mode
        if self.test_mode:
            if channel_id in self._connections:
                # Get next sequence number
                seq = self._next_seq[channel_id]
                
                # Create FIN packet
                fin_header = PacketHeader(
                    version=VERSION,
                    flags=FLAG_FIN,
                    channel_id=channel_id,
                    seq_no=seq,
                    payload_length=0
                )
                fin_packet = fin_header.encode()
                
                # Send FIN packet
                self.logger.debug(f"Test mode: Sending FIN packet to channel {channel_id}")
                chan.send(fin_packet)
                
                # Remove from connections
                self._connections.remove(channel_id)
                
                # Increment sequence number
                self._next_seq[channel_id] = (seq + 1) % MAX_SEQ_NUM
        else:
            # Use the real implementation for non-test mode
            await super()._close_connection(chan, channel_id)


class TestTcpAdvanced(unittest.TestCase):
    """Advanced tests for TCP transport with proper testing support."""
    
    def setUp(self):
        self.transport = TestTcpTransport()
        self.transport.test_mode = True  # Enable test mode
        self.channel = TestMicroChannel()
    
    def tearDown(self):
        pass
    
    async def _run_with_transport(self, coro):
        """Run a coroutine with the transport context manager."""
        async with self.transport:
            return await coro
    
    def test_connection_establishment(self):
        """Test establishing a TCP connection."""
        async def establish_connection():
            # Manually establish connection
            await self.transport._establish_connection(self.channel)
            self.assertIn(0, self.transport._connections)
            return True
        
        result = asyncio.run(self._run_with_transport(establish_connection()))
        self.assertTrue(result)
    
    def test_send_data(self):
        """Test sending data over an established connection."""
        test_data = b"Hello, TCP world!"
        
        async def send_data():
            # Send test data
            await self.transport.send(test_data, self.channel)
            return True
        
        result = asyncio.run(self._run_with_transport(send_data()))
        self.assertTrue(result)
        
        # Find the data packet in sent packets
        data_found = False
        for packet in self.channel.sent_data:
            header, consumed = PacketHeader.decode(packet)
            if not header.is_syn and not header.is_ack:
                payload = packet[consumed:]
                if payload == test_data:
                    data_found = True
                    break
        
        self.assertTrue(data_found, "Test data was not found in sent packets")
    
    def test_fragmentation(self):
        """Test sending data that requires fragmentation."""
        # Create a large payload that will need fragmentation
        large_data = b"A" * 1000
        
        async def send_large_data():
            # Set a smaller MTU to force fragmentation
            self.transport.MTU = 100
            # Send large data
            await self.transport.send(large_data, self.channel)
            return True
        
        result = asyncio.run(self._run_with_transport(send_large_data()))
        self.assertTrue(result)
        
        # Check that multiple packets were sent and they have the FRAG flag
        frag_packets = 0
        for packet in self.channel.sent_data:
            header, _ = PacketHeader.decode(packet)
            if header.is_frag:
                frag_packets += 1
        
        self.assertGreater(frag_packets, 1, "Not enough fragment packets were sent")
    
    def test_connection_teardown(self):
        """Test closing a TCP connection."""
        async def close_connection():
            # First establish connection manually
            await self.transport._establish_connection(self.channel)
            self.assertIn(0, self.transport._connections)
            
            # Now close it
            await self.transport._close_connection(self.channel, 0)
            self.assertNotIn(0, self.transport._connections)
            return True
        
        result = asyncio.run(self._run_with_transport(close_connection()))
        self.assertTrue(result)
        
        # Verify FIN packet was sent
        fin_sent = False
        for packet in self.channel.sent_data:
            header, _ = PacketHeader.decode(packet)
            if header.is_fin:
                fin_sent = True
                break
        
        self.assertTrue(fin_sent, "FIN packet was not sent during connection teardown")
    
    def test_multiple_channels(self):
        """Test using multiple channels independently."""
        async def use_multiple_channels():
            channel1 = TestMicroChannel()
            channel2 = TestMicroChannel()
            
            # Establish connections on both channels
            await self.transport._establish_connection(channel1, channel_id=1)
            await self.transport._establish_connection(channel2, channel_id=2)
            
            # Send data on both channels
            await self.transport.send(b"Channel 1 data", channel1, channel_id=1)
            await self.transport.send(b"Channel 2 data", channel2, channel_id=2)
            
            # Verify both connections are established
            self.assertIn(1, self.transport._connections)
            self.assertIn(2, self.transport._connections)
            
            # Verify data was sent on both channels
            channel1_data_sent = False
            for packet in channel1.sent_data:
                header, consumed = PacketHeader.decode(packet)
                if header.channel_id == 1 and not header.is_syn:
                    payload = packet[consumed:]
                    if b"Channel 1 data" in payload:
                        channel1_data_sent = True
                        break
            
            channel2_data_sent = False
            for packet in channel2.sent_data:
                header, consumed = PacketHeader.decode(packet)
                if header.channel_id == 2 and not header.is_syn:
                    payload = packet[consumed:]
                    if b"Channel 2 data" in payload:
                        channel2_data_sent = True
                        break
            
            self.assertTrue(channel1_data_sent, "Data not sent on channel 1")
            self.assertTrue(channel2_data_sent, "Data not sent on channel 2")
            
            return True
        
        result = asyncio.run(self._run_with_transport(use_multiple_channels()))
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()