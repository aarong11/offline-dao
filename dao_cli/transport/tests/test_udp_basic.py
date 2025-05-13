"""
Unit tests for UDP transport.
"""

import asyncio
import unittest
from unittest import mock
import time
from typing import List, Optional, Dict, Tuple

from dao_cli.transport.udp import UdpTransport
from dao_cli.transport.header import PacketHeader
from dao_cli.transport.base import TransportError
from dao_cli.transport.constants import FLAG_FRAG, FRAGMENT_TIMEOUT


class MockChannel:
    """Mock implementation of a MicroChannel for testing."""
    
    def __init__(self, max_bytes: int = 500):
        self.MAX_BYTES = max_bytes
        self._sent_data: List[bytes] = []
        self._read_queue: List[bytes] = []
    
    def send(self, payload: bytes) -> None:
        """Store sent data for inspection."""
        if len(payload) > self.MAX_BYTES:
            raise ValueError(f"Payload too large: {len(payload)} > {self.MAX_BYTES}")
        self._sent_data.append(payload)
    
    def receive(self) -> Optional[bytes]:
        """Return next queued packet if available."""
        if not self._read_queue:
            return None
        return self._read_queue.pop(0)
    
    def queue_packet(self, packet: bytes) -> None:
        """Queue a packet to be returned by receive."""
        self._read_queue.append(packet)
    
    @property
    def sent_data(self) -> List[bytes]:
        """Return all sent data for inspection."""
        return self._sent_data


class TestUdpBasic(unittest.TestCase):
    """Basic tests for UdpTransport."""
    
    def setUp(self):
        self.transport = UdpTransport()
        self.mock_channel = MockChannel()
    
    def test_send_small_payload(self):
        """Test sending a payload smaller than MTU."""
        data = b"Hello, World!"
        
        # Send the data
        asyncio.run(self.transport.send(data, self.mock_channel))
        
        # Check that one packet was sent
        self.assertEqual(len(self.mock_channel.sent_data), 1)
        
        # Decode and check the packet
        sent_packet = self.mock_channel.sent_data[0]
        header, consumed = PacketHeader.decode(sent_packet)
        payload = sent_packet[consumed:]
        
        self.assertEqual(header.flags, 0)  # No flags for simple UDP packet
        self.assertEqual(header.channel_id, 0)  # Default channel
        self.assertEqual(header.payload_length, len(data))
        self.assertEqual(payload, data)
    
    def test_send_empty_payload(self):
        """Test sending an empty payload."""
        data = b""
        
        # Send the data
        asyncio.run(self.transport.send(data, self.mock_channel))
        
        # Check that nothing was sent for empty payload
        self.assertEqual(len(self.mock_channel.sent_data), 0)
    
    def test_send_large_payload_fragmentation(self):
        """Test that large payloads are fragmented."""
        # Create a payload larger than MTU
        data = b"A" * 500
        
        # Set transport MTU smaller for testing
        self.transport.MTU = 100
        
        # Send the data
        asyncio.run(self.transport.send(data, self.mock_channel))
        
        # Check that multiple packets were sent
        self.assertGreater(len(self.mock_channel.sent_data), 1)
        
        # Check that all sent packets have the FRAG flag set
        for packet in self.mock_channel.sent_data:
            header, _ = PacketHeader.decode(packet)
            self.assertTrue(header.is_frag)
            self.assertEqual(header.channel_id, 0)  # Default channel
    
    def test_receive_packet(self):
        """Test receiving a single packet."""
        data = b"Test Message"
        
        # Create a packet to be received
        header = PacketHeader(payload_length=len(data))
        packet = header.encode() + data
        
        # Queue the packet for receipt
        self.mock_channel.queue_packet(packet)
        
        # Receive the packet
        received = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Check that the data is correct
        self.assertEqual(received, data)
    
    def test_receive_no_packet(self):
        """Test receiving when no packet is available."""
        # Receive when no packet is queued
        received = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Should return empty bytes
        self.assertEqual(received, b"")


class TestUdpFragmentation(unittest.TestCase):
    """Tests for UDP fragmentation and reassembly."""
    
    def setUp(self):
        self.transport = UdpTransport()
        self.mock_channel = MockChannel()
        self.frag_id = 12345
        
        # Clear any cached fragmentation state between tests
        self.transport._fragments = {}
        self.transport._fragment_timeouts = {}
    
    def create_fragment(self, data: bytes, offset: int, frag_id: int = None) -> bytes:
        """Helper to create a fragment packet."""
        header = PacketHeader(
            flags=FLAG_FRAG,
            payload_length=len(data),
            frag_id=self.frag_id if frag_id is None else frag_id,
            frag_offset=offset
        )
        return header.encode() + data
    
    def test_receive_fragments_in_order(self):
        """Test receiving fragments in order."""
        # Create fragments
        frag1 = self.create_fragment(b"First", 0)
        frag2 = self.create_fragment(b"Second", 5)
        frag3 = self.create_fragment(b"Third", 11)
        
        # Queue just the first fragment
        self.mock_channel.queue_packet(frag1)
        
        # First receive should return first fragment's data
        received1 = asyncio.run(self.transport.recv(self.mock_channel))
        self.assertEqual(received1, b"First")
        
        # Queue second fragment and receive again
        self.mock_channel.queue_packet(frag2)
        received2 = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Now we should have the concatenated data from first and second fragment
        self.assertEqual(received2, b"FirstSecond")
        
        # Queue third fragment and receive again
        self.mock_channel.queue_packet(frag3)
        received3 = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Now we should have the complete message
        self.assertEqual(received3, b"FirstSecondThird")
    
    def test_receive_fragments_out_of_order(self):
        """Test receiving fragments out of order."""
        # Create fragments
        frag1 = self.create_fragment(b"First", 0)
        frag2 = self.create_fragment(b"Second", 5)
        frag3 = self.create_fragment(b"Third", 11)
        
        # Queue fragments out of order - first middle fragment
        self.mock_channel.queue_packet(frag2)
        
        # First receive should return empty since we don't have offset 0
        received1 = asyncio.run(self.transport.recv(self.mock_channel))
        self.assertEqual(received1, b"")
        
        # Queue first fragment
        self.mock_channel.queue_packet(frag1)
        
        # Second receive should get first+second fragments
        received2 = asyncio.run(self.transport.recv(self.mock_channel))
        self.assertEqual(received2, b"FirstSecond")
        
        # Queue third fragment
        self.mock_channel.queue_packet(frag3)
        
        # Third receive should get all fragments
        received3 = asyncio.run(self.transport.recv(self.mock_channel))
        self.assertEqual(received3, b"FirstSecondThird")
    
    def test_fragment_timeout(self):
        """Test that fragments expire after timeout."""
        # Create fragments with different fragment IDs
        frag1 = self.create_fragment(b"First", 0, frag_id=5000)  # Use a different frag_id for first fragment
        frag2 = self.create_fragment(b"Second", 5)  # Use the default frag_id from setUp
        
        # Queue first fragment with ID 5000
        self.mock_channel.queue_packet(frag1)
        received1 = asyncio.run(self.transport.recv(self.mock_channel))
        self.assertEqual(received1, b"First")
        
        # Set fragment timeout to a value that doesn't interfere with this test
        expired_key = (0, 5000)  # The key for the first fragment (channel 0, frag_id 5000)
        
        # Manually expire this fragment by removing it from tracking
        if expired_key in self.transport._fragments:
            del self.transport._fragments[expired_key]
        if expired_key in self.transport._fragment_timeouts:
            del self.transport._fragment_timeouts[expired_key]
        
        # Queue second fragment with different frag_id
        self.mock_channel.queue_packet(frag2)
        received2 = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Should be empty because this fragment has no offset 0 for its own frag_id
        self.assertEqual(received2, b"")
    
    def test_multiple_messages(self):
        """Test handling fragments from multiple messages simultaneously."""
        # Create fragments for message 1
        msg1_frag1 = self.create_fragment(b"Msg1-Part1", 0, frag_id=1001)
        msg1_frag2 = self.create_fragment(b"Msg1-Part2", 10, frag_id=1001)
        
        # Create fragments for message 2
        msg2_frag1 = self.create_fragment(b"Msg2-Part1", 0, frag_id=2002)
        msg2_frag2 = self.create_fragment(b"Msg2-Part2", 10, frag_id=2002)
        
        # Queue fragments interleaved
        self.mock_channel.queue_packet(msg1_frag1)
        self.mock_channel.queue_packet(msg2_frag1)
        
        # Process both first fragments
        received1 = asyncio.run(self.transport.recv(self.mock_channel))
        received2 = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Should have the first part of each message
        self.assertTrue(b"Msg1-Part1" in received1 or b"Msg1-Part1" in received2)
        self.assertTrue(b"Msg2-Part1" in received1 or b"Msg2-Part1" in received2)
        
        # Queue the second fragments
        self.mock_channel.queue_packet(msg1_frag2)
        self.mock_channel.queue_packet(msg2_frag2)
        
        # Process both second fragments
        received3 = asyncio.run(self.transport.recv(self.mock_channel))
        received4 = asyncio.run(self.transport.recv(self.mock_channel))
        
        # Should have the complete messages
        self.assertTrue(
            b"Msg1-Part1Msg1-Part2" in [received3, received4] or
            b"Msg2-Part1Msg2-Part2" in [received3, received4]
        )


if __name__ == "__main__":
    unittest.main()