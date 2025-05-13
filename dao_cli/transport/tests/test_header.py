"""
Unit tests for header encoding and decoding.
"""

import unittest
import struct
from dao_cli.transport.header import PacketHeader
from dao_cli.transport.constants import (
    VERSION, FLAG_SYN, FLAG_ACK, FLAG_FIN, FLAG_RST, FLAG_FRAG,
    HEADER_SIZE, FRAG_HEADER_SIZE
)


class TestPacketHeader(unittest.TestCase):
    """Tests for the PacketHeader class."""
    
    def test_basic_header_encode(self):
        """Test encoding a basic header without fragment information."""
        header = PacketHeader(
            version=VERSION,
            flags=FLAG_SYN,
            channel_id=42,
            seq_no=123,
            payload_length=100
        )
        
        encoded = header.encode()
        self.assertEqual(len(encoded), HEADER_SIZE)
        
        # Verify the encoded header matches our expected values
        version, flags, channel_id, seq_no, payload_length = struct.unpack(">BBHHH", encoded)
        self.assertEqual(version, VERSION)
        self.assertEqual(flags, FLAG_SYN)
        self.assertEqual(channel_id, 42)
        self.assertEqual(seq_no, 123)
        self.assertEqual(payload_length, 100)
    
    def test_basic_header_decode(self):
        """Test decoding a basic header without fragment information."""
        # Create a raw header
        raw_header = struct.pack(">BBHHH", VERSION, FLAG_ACK, 42, 123, 100)
        
        # Decode it
        header, bytes_consumed = PacketHeader.decode(raw_header)
        
        # Verify the decoded header
        self.assertEqual(header.version, VERSION)
        self.assertEqual(header.flags, FLAG_ACK)
        self.assertEqual(header.channel_id, 42)
        self.assertEqual(header.seq_no, 123)
        self.assertEqual(header.payload_length, 100)
        self.assertEqual(bytes_consumed, HEADER_SIZE)
        
        # Check flag properties
        self.assertFalse(header.is_syn)
        self.assertTrue(header.is_ack)
        self.assertFalse(header.is_fin)
        self.assertFalse(header.is_rst)
        self.assertFalse(header.is_frag)
    
    def test_fragment_header_encode(self):
        """Test encoding a header with fragment information."""
        header = PacketHeader(
            version=VERSION,
            flags=FLAG_SYN | FLAG_FRAG,
            channel_id=42,
            seq_no=123,
            payload_length=100,
            frag_id=0xCAFEBABE,
            frag_offset=1024
        )
        
        encoded = header.encode()
        self.assertEqual(len(encoded), HEADER_SIZE + FRAG_HEADER_SIZE)
        
        # Verify the encoded header matches our expected values
        version, flags, channel_id, seq_no, payload_length = struct.unpack(">BBHHH", encoded[:HEADER_SIZE])
        self.assertEqual(version, VERSION)
        self.assertEqual(flags, FLAG_SYN | FLAG_FRAG)
        self.assertEqual(channel_id, 42)
        self.assertEqual(seq_no, 123)
        self.assertEqual(payload_length, 100)
        
        frag_id, frag_offset = struct.unpack(">IH", encoded[HEADER_SIZE:])
        self.assertEqual(frag_id, 0xCAFEBABE)
        self.assertEqual(frag_offset, 1024)
    
    def test_fragment_header_decode(self):
        """Test decoding a header with fragment information."""
        # Create a raw header with fragment info
        raw_header = struct.pack(">BBHHH", VERSION, FLAG_ACK | FLAG_FRAG, 42, 123, 100)
        raw_header += struct.pack(">IH", 0xCAFEBABE, 1024)
        
        # Decode it
        header, bytes_consumed = PacketHeader.decode(raw_header)
        
        # Verify the decoded header
        self.assertEqual(header.version, VERSION)
        self.assertEqual(header.flags, FLAG_ACK | FLAG_FRAG)
        self.assertEqual(header.channel_id, 42)
        self.assertEqual(header.seq_no, 123)
        self.assertEqual(header.payload_length, 100)
        self.assertEqual(header.frag_id, 0xCAFEBABE)
        self.assertEqual(header.frag_offset, 1024)
        self.assertEqual(bytes_consumed, HEADER_SIZE + FRAG_HEADER_SIZE)
        
        # Check flag properties
        self.assertFalse(header.is_syn)
        self.assertTrue(header.is_ack)
        self.assertFalse(header.is_fin)
        self.assertFalse(header.is_rst)
        self.assertTrue(header.is_frag)
    
    def test_decode_error_on_short_data(self):
        """Test decoding fails when data is too short."""
        raw_header = struct.pack(">BBHHH", VERSION, FLAG_ACK, 42, 123, 100)
        short_data = raw_header[:-1]  # Truncate the last byte
        
        with self.assertRaises(ValueError):
            PacketHeader.decode(short_data)
    
    def test_decode_error_on_short_frag_data(self):
        """Test decoding fails when fragment data is too short."""
        raw_header = struct.pack(">BBHHH", VERSION, FLAG_ACK | FLAG_FRAG, 42, 123, 100)
        raw_header += struct.pack(">I", 0xCAFEBABE)  # Missing frag_offset
        
        with self.assertRaises(ValueError):
            PacketHeader.decode(raw_header)


if __name__ == "__main__":
    unittest.main()