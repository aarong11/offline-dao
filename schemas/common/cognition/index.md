# Cognitive Schema System

This document provides an overview of the cognitive schema system designed for tracking human psychological states, emotional states, and memories in a cryptographically verifiable way within the DAO.

## Schema Architecture

The cognitive schema system follows a modular, inheritance-based architecture:

```
common/
├── signature.schema.json              # Reusable signature component
└── cognition/
    ├── base_cognitive_state.schema.json  # Base schema for all cognitive states
    └── memory_context.schema.json        # Reusable memory context component

human_contributor.schema.json          # Enhanced human schema with state references
psychological_state.schema.json        # Psychological state tracking
emotional_state.schema.json            # Emotional state tracking
memory.schema.json                     # Memory records with cryptographic chaining
```

## Schema Relationships

- `human_contributor.schema.json` → References the most recent psychological and emotional states
- `psychological_state.schema.json` → Inherits from `base_cognitive_state.schema.json`, links to emotional states
- `emotional_state.schema.json` → Inherits from `base_cognitive_state.schema.json`, links to psychological states
- `memory.schema.json` → Uses `memory_context.schema.json` for contextual information, links to emotional and psychological states

## Cryptographic Verification Chain

Each schema implements a chain of cryptographic references:

1. Human record points to the most recent state records
2. State records maintain a chain through `previous_state_cid` fields
3. Memory records maintain their own chain through `previous_memory_cid`
4. All records are cryptographically signed using the common signature schema

## AI-Assisted Context Recovery Support

The memory schema includes specific fields to support AI-assisted context recovery:

- Comprehensive contextual data (emotional, psychological, temporal, spatial, perceptual, social)
- Semantic cues and retrieval triggers
- Vector embedding support for similarity search
- Confidence rating and factors affecting confidence
- Verification mechanisms

## Implementation Considerations

When implementing these schemas:

1. Treat the `human_id` as a pseudonymous identifier, not tied to legal identity
2. Store vector embeddings separately from the main record when possible
3. Consider implementing a pruning/summarization mechanism for extended memory chains
4. Keep all ratings subjective to the individual's own baseline
5. Use epoch markers for human-readable time references in addition to machine timestamps