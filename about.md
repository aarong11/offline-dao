# DAO Offline-First Toolkit Documentation

## Overview

This project is a decentralized autonomous organization (DAO) toolkit designed for resilient operation in environments with limited, unstable, or surveilled connectivity. It enables collaborators to coordinate tasks, share project updates, and communicate through unconventional channels when traditional internet might be unavailable or compromised.

## Key Features

### 1. Alternative Communication Channels

The system leverages numerous non-traditional transmission mediums ("side-channels"):

- **Blockchain Mempool**: Using zero-fee transactions with OP_RETURN fields (docs/mempool.txt)
- **Consumer Device Metadata**: AirTag renames, Wi-Fi SSID beacons, BLE device names
- **Experimental Channels**: Over 25 unconventional methods including thermal patterns, ultrasonic audio, and smart device signals (docs/experimental_channels2.txt)

### 2. Offline-First Project Coordination

- **Project Delta Bundle**: Cryptographically signed update files for asynchronous sharing between participants
- **Human-Oriented Epoch Markers**: Coordination using natural events ("full moon", "first frost") instead of timestamps
- **Task/Project Management**: Complete system for creating, claiming, and completing tasks
- **Resource Matching**: Connects tasks with contributors who have the right skills and resources

### 3. Security and Privacy Features

- **Pseudonymous Identities**: Contributors operate under anon-IDs with optional verified linking
- **FIPS Compliance**: Supports federal security standards with validated cryptography (FIPS.md)
- **Device Management**: Secure association of physical devices with contributor identities
- **Hardware Security Module Support**: Optional integration with PKCS#11 HSMs

### 4. Transport Layer Abstraction (MC-TCP/UDP)

- **Uniform API**: Same interface regardless of underlying channel (AirTag, Wi-Fi, BLE, etc.)
- **Reliable Transport**: MC-TCP with acknowledgments, retransmissions for critical data
- **Datagram Service**: MC-UDP for simpler one-shot transmissions
- **Common Packet Format**: 8-byte header with version, flags, channel ID, and sequence number

## System Architecture

```
Application Layer
    │
    ▼
DAO Serializer & Crypto
    │
    ▼
Transport Layer (MC-TCP/MC-UDP)
    │
    ▼
Channel Adapters
    │
    ▼
Transmission Mediums (physical carriers)
```

## Data Model

The system uses JSON schemas for all data structures:

- **Projects**: Top-level containers with tasks and funding (schemas/project.schema.json)
- **Tasks**: Unit of work with dependencies, resources, and status (schemas/task.schema.json)
- **Contributors**: Pseudonymous profiles with skills and reputation (schemas/contributor.schema.json)
- **Experiments**: Research protocols for testing new channels (schemas/experiment.schema.json)
- **Transmission Mediums**: Capabilities of communication carriers (schemas/transmission_medium.schema.json)

## Command-Line Interface

The main dao.py CLI provides functionality for:

- Creating and managing projects
- Adding and claiming tasks
- Tracking contributions and simulating payouts
- Generating and importing cryptographically signed project deltas
- Managing contributor identities and device access
- Visualizing task dependencies

## Integration Examples

### Exporting Project Updates Over Covert Channels

```bash
# Generate a signed delta file
dao.py
# Select option 18
# Enter project ID when prompted

# Send delta via alternative channel
dao export-delta --project-id <ID> --channel airtag
```

### Setting Up a Bitcoin Mempool Channel

As described in mempool.txt:

```bash
# Listen for incoming DAO packets in Bitcoin mempool
dao listen --channel mempool-bitcoin --transport udp
```

## Use Cases

1. **Disaster Response**: Coordinate when traditional infrastructure is down
2. **Field Research**: Sync data between remote locations with limited connectivity
3. **Privacy-Sensitive Collaboration**: Work together without revealing personal details
4. **Censorship-Resistant Coordination**: Communicate through side-channels when main channels are blocked
5. **Secure Government Operations**: FIPS-compliant tooling for sensitive government applications

## Technical Requirements

- Python 3.x
- OpenSSL 3.x (for FIPS compliance)
- Optional hardware security module with PKCS#11 support

The system is designed to operate on standard consumer hardware while enabling resilient, secure, and privacy-preserving collaboration through diverse communication channels.