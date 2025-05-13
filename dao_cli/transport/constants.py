"""
Constants for microtransport protocol.

Defines header flags, sizes, and timeouts for the transport layer.
"""

# Protocol version
VERSION = 0x01

# Packet header flags
FLAG_SYN = 0x01  # Connection setup
FLAG_ACK = 0x02  # Acknowledgement
FLAG_FIN = 0x04  # Connection teardown
FLAG_RST = 0x08  # Connection reset
FLAG_FRAG = 0x10  # Fragmented payload

# Flag combinations
FLAG_SYN_ACK = FLAG_SYN | FLAG_ACK
FLAG_FIN_ACK = FLAG_FIN | FLAG_ACK

# Header sizes
HEADER_SIZE = 8  # Fixed 8-byte header
FRAG_HEADER_SIZE = 6  # Additional 6-byte fragmentation header (4-byte ID + 2-byte offset)

# Size limits
MTU = 248  # Default maximum payload size per packet

# Timeouts (in seconds)
INITIAL_TIMEOUT = 5.0  # Initial wait for ACK
BACKOFF_FACTOR = 2.0  # Exponential backoff multiplier
MAX_RETRIES = 5  # Maximum retransmission attempts
FRAGMENT_TIMEOUT = 30.0  # Time to wait for complete fragments before dropping

# Window size for flow control (currently just stop-and-wait)
WINDOW_SIZE = 1  # Stop-and-wait protocol

# Seq/ACK number limits
MAX_SEQ_NUM = 65535  # 16-bit sequence number space