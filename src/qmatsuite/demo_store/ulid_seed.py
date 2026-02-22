"""
Deterministic ULID generation for demo snapshots.

Produces stable, reproducible ULIDs from a demo_slug and component name,
ensuring that re-generation from unchanged corpus produces byte-identical output.

Algorithm: sha256(salt:demo_slug:component) -> first 26 chars mapped to Crockford Base32.
"""

from __future__ import annotations

import hashlib

# Crockford Base32 alphabet (used by ULID)
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Fixed salt for deterministic generation
_SALT = "qmatsuite-demo-store-v1"


def deterministic_ulid(demo_slug: str, component: str) -> str:
    """
    Generate a deterministic ULID-like identifier from demo_slug and component.

    Args:
        demo_slug: The demo's stable identifier (e.g., "vasp_si_scf")
        component: Component within the demo (e.g., "project", "structure:si",
                   "calculation:si-scf", "step:si-scf:scf")

    Returns:
        26-character string in Crockford Base32 format (ULID-compatible)
    """
    seed = f"{_SALT}:{demo_slug}:{component}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()

    # Map first 16 bytes (128 bits) to 26 Crockford Base32 characters
    # ULID = 10 chars timestamp + 16 chars randomness = 26 chars total
    # We use a fixed timestamp prefix (01K...) to look like a valid ULID
    # and fill the rest from the hash
    value = int.from_bytes(digest[:16], "big")

    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5

    # Reverse to get MSB-first order
    result = "".join(reversed(chars))

    # Force a plausible ULID timestamp prefix (01K range)
    # This ensures it sorts after real ULIDs from ~2020 era
    return "01K" + result[3:]
