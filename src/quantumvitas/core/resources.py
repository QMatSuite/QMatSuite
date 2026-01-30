"""
Shared resource metadata helpers used by projects, calculations, steps, and structures.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import threading
import time
from pathlib import Path
from typing import Literal, Optional, Sequence

import ulid

# Find resources directory relative to this file's location
# resources/ is at the root of the repo, not in src/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent.parent  # src/quantumvitas/core -> root
RESOURCES_DIR = _PACKAGE_ROOT / "resources"


def get_resources_dir() -> Path:
    """
    Get the path to the resources directory.
    
    Returns:
        Path to resources/ directory at repo root
    """
    return RESOURCES_DIR

ResourceKind = Literal["project", "calculation", "step", "structure"]

_SLUG_INVALID_RE = re.compile(r"[^a-z0-9_]+")
_DEFAULT_NAMES: dict[ResourceKind, str] = {
    "project": "Project",
    "calculation": "Calculation",
    "step": "Step",
    "structure": "Structure",
}


# ==============================================================================
# ULID Generation with Monotonic Counter
# ==============================================================================
# 
# ulid-py has a known issue: it generates random bits independently for each
# call, which can cause collisions when multiple ULIDs are generated within
# the same millisecond. This is observed in Ubuntu CI environments.
#
# Fix: Implement a custom ULID generator with monotonically incrementing
# random portion within the same millisecond to guarantee uniqueness.
#
# ULID format: 10 chars timestamp (48-bit ms) + 16 chars randomness (80-bit)
# Crockford's Base32 encoding
# ==============================================================================

# Crockford's Base32 alphabet (excludes I, L, O, U to avoid confusion)
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class _MonotonicUlidGenerator:
    """
    Thread-safe ULID generator with monotonic counter to prevent collisions.
    
    The standard ulid-py library generates random bits for each ULID independently.
    When generating multiple ULIDs within the same millisecond (common in fast loops
    or CI environments), there's a small but non-zero probability of collision.
    
    This generator implements the ULID spec with a monotonically incrementing
    random portion within the same millisecond, guaranteeing strict uniqueness.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._last_timestamp_ms: int = 0
        # 80-bit random value (0 to 2^80 - 1)
        self._random_value: int = int.from_bytes(os.urandom(10), 'big')
    
    def generate(self) -> str:
        """
        Generate a new ULID string, guaranteed unique within this process.
        
        Within the same millisecond, the random portion is incremented
        monotonically to ensure strict ordering and uniqueness.
        
        Returns:
            26-character ULID string (uppercase)
        """
        with self._lock:
            # Get current timestamp in milliseconds
            current_ms = int(time.time() * 1000)
            
            if current_ms <= self._last_timestamp_ms:
                # Same or earlier millisecond (clock drift): increment random
                self._random_value += 1
                # Check for overflow (very unlikely with 80-bit space)
                if self._random_value >= (1 << 80):
                    # Wait for next millisecond
                    while int(time.time() * 1000) <= self._last_timestamp_ms:
                        time.sleep(0.0001)
                    current_ms = int(time.time() * 1000)
                    self._random_value = int.from_bytes(os.urandom(10), 'big')
                else:
                    # Use the incremented value with the previous timestamp
                    # to maintain monotonicity
                    current_ms = self._last_timestamp_ms
            else:
                # New millisecond: generate fresh random value
                self._random_value = int.from_bytes(os.urandom(10), 'big')
            
            self._last_timestamp_ms = current_ms
            
            # Encode timestamp (48-bit = 6 bytes -> 10 base32 chars)
            timestamp_chars = self._encode_base32(current_ms, 10)
            
            # Encode randomness (80-bit = 10 bytes -> 16 base32 chars)
            random_chars = self._encode_base32(self._random_value, 16)
            
            return timestamp_chars + random_chars
    
    @staticmethod
    def _encode_base32(value: int, length: int) -> str:
        """Encode integer to Crockford's Base32 with fixed length."""
        result = []
        for _ in range(length):
            result.append(_CROCKFORD_BASE32[value & 0x1F])
            value >>= 5
        return ''.join(reversed(result))


# Global monotonic generator instance
_monotonic_generator = _MonotonicUlidGenerator()


def generate_resource_id() -> str:
    """
    Create a new ULID string, guaranteed unique within this process.
    
    Uses a monotonic counter to prevent collisions when generating
    multiple ULIDs within the same millisecond (common in CI environments).
    
    The generated ULID is compatible with the ULID specification and
    can be parsed by the ulid-py library.
    
    Returns:
        26-character ULID string (uppercase)
    """
    return _monotonic_generator.generate()


def slugify(value: str, fallback: str = "resource") -> str:
    """
    Convert a human-readable name into a filesystem-friendly slug.
    """
    normalized = value.strip().lower()
    normalized = _SLUG_INVALID_RE.sub("-", normalized)
    normalized = normalized.strip("-")
    return normalized or fallback


def ensure_relative_path(path: Path | str, *, base: Optional[Path] = None) -> str:
    """
    Return a POSIX-style path that is relative to ``base`` (defaults to project root).
    """
    path_obj = Path(path)
    if path_obj.is_absolute():
        if base is None:
            raise ValueError("Absolute paths require a base to relativize against.")
        base_resolved = base.resolve()
        path_obj_resolved = path_obj.resolve()
        # Handle symlink issues by comparing resolved paths
        try:
            path_obj = path_obj_resolved.relative_to(base_resolved)
        except ValueError:
            # If relative_to fails, try with string comparison
            # This can happen with symlinks or different path representations
            base_str = str(base_resolved)
            path_str = str(path_obj_resolved)
            if path_str.startswith(base_str):
                rel_str = path_str[len(base_str):].lstrip('/')
                path_obj = Path(rel_str)
            else:
                raise
    return path_obj.as_posix()


@dataclass(slots=True)
class ResourceMeta:
    """
    Metadata shared across all top-level QuantumVITAS resources.

    ``path`` is stored relative to the project root (POSIX form) to keep configs
    portable.
    """

    id: str
    name: str
    slug: str
    path: str
    kind: ResourceKind

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "path": self.path,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(
        cls,
        data: Optional[dict],
        *,
        kind: ResourceKind,
        default_name: str,
        default_path: str,
    ) -> "ResourceMeta":
        data = data or {}
        # Check for ulid first (new format), then id (legacy)
        resource_id = data.get("ulid") or data.get("id") or generate_resource_id()
        name = data.get("name") or default_name
        slug = data.get("slug") or slugify(name)
        path = data.get("path") or default_path
        stored_kind = data.get("kind") or kind
        return cls(
            id=str(resource_id),
            name=name,
            slug=slug,
            path=path,
            kind=stored_kind,
        )

    def resolved_path(self, project_root: Path) -> Path:
        return (project_root / self.path).resolve()

    def with_updates(
        self,
        *,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        path: Optional[str] = None,
    ) -> "ResourceMeta":
        new_name = name or self.name
        return ResourceMeta(
            id=self.id,
            name=new_name,
            slug=slug or (slugify(new_name) if name else self.slug),
            path=path or self.path,
            kind=self.kind,
        )


def meta_from_name(kind: ResourceKind, *, name: str, path: str) -> ResourceMeta:
    """
    Helper for creating metadata when scaffolding new resources.
    """
    return ResourceMeta(
        id=generate_resource_id(),
        name=name,
        slug=slugify(name),
        path=path,
        kind=kind,
    )


def generate_unique_name_and_slug(
    *,
    kind: ResourceKind,
    preferred_name: Optional[str],
    existing_slugs: Sequence[str],
) -> tuple[str, str]:
    """
    Produce a unique (name, slug) pair for the given resource kind.
    """

    base_name = preferred_name.strip() if preferred_name else _DEFAULT_NAMES[kind]
    attempt = base_name
    suffix = 2
    existing_set = {slug.lower() for slug in existing_slugs if slug}

    while True:
        slug_candidate = slugify(attempt)
        if slug_candidate.lower() not in existing_set:
            return attempt, slug_candidate
        attempt = f"{base_name} {suffix}"
        suffix += 1

