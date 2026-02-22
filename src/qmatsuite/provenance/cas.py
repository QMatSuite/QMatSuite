"""
Content-Addressed Store (CAS) for provenance system.

Per Law P5 (CAS Integrity):
- Objects are immutable and content-addressed by SHA-256
- Object path is derived from hash: .cas/objects/<first2>/<rest>
- Once written, a CAS object is never modified
- Duplicate writes (same hash) are no-ops

Storage Tiers:
- Tier-0: Run snapshots (YAML, structures) - never auto-delete
- Tier-0.5: Reproducibility assets (pseudos, potentials) - never auto-delete
- Tier-1: Derived outputs (reports, images, journal bodies) - long-lived
- Tier-2: Raw artifacts from calc/raw (excluding blacklist) - configurable
- Tier-3: Large optional outputs (wavefunction, CHGCAR) - rolling window
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Union

from qmatsuite.provenance.errors import CASIntegrityError, SnapshotNotFoundError

logger = logging.getLogger(__name__)


class CAS:
    """
    Content-Addressed Store for provenance objects.

    Thread-safe for concurrent writes (atomic temp+rename pattern).
    """

    def __init__(self, project_root: Path):
        """
        Initialize CAS.

        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self.root = project_root / ".provenance" / ".cas"

    def _ensure_dirs(self) -> None:
        """Ensure CAS directories exist."""
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        (self.root / "tmp").mkdir(parents=True, exist_ok=True)

    def _object_path(self, sha256: str) -> Path:
        """
        Get path to CAS object.

        Args:
            sha256: SHA-256 hash (64 hex chars)

        Returns:
            Path to object file
        """
        return self.root / "objects" / sha256[:2] / sha256[2:]

    def store(self, content: bytes, tier: int) -> str:
        """
        Store content in CAS.

        Atomic write via temp file + rename.
        Duplicate writes are no-ops (content-addressed).

        Args:
            content: Raw bytes to store
            tier: Storage tier (0, 1, 2, or 3)

        Returns:
            SHA-256 hash of content
        """
        self._ensure_dirs()

        sha = hashlib.sha256(content).hexdigest()
        obj_path = self._object_path(sha)

        # Dedup: already exists
        if obj_path.exists():
            return sha

        # Atomic write via temp file
        tmp_path = self.root / "tmp" / f"{sha}.tmp"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            tmp_path.write_bytes(content)
            obj_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.rename(obj_path)
        except Exception as e:
            # Clean up temp file on failure
            tmp_path.unlink(missing_ok=True)
            raise CASIntegrityError(f"Failed to store CAS object: {e}") from e

        # Record in database
        try:
            from qmatsuite.provenance.db import open_provenance_db

            conn = open_provenance_db(self.project_root)
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO cas_objects (sha256, tier, size_bytes)
                    VALUES (?, ?, ?)
                    """,
                    (sha, tier, len(content)),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            # Log but don't fail - CAS file is written
            logger.warning(f"Failed to record CAS object in database: {e}")

        return sha

    def store_json(self, data: dict, tier: int) -> str:
        """
        Store JSON-serializable data in CAS.

        Args:
            data: Dict to serialize and store
            tier: Storage tier

        Returns:
            SHA-256 hash
        """
        content = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        return self.store(content, tier)

    def retrieve(self, sha256: str) -> bytes:
        """
        Retrieve content from CAS.

        Args:
            sha256: SHA-256 hash

        Returns:
            Raw bytes

        Raises:
            SnapshotNotFoundError: If object doesn't exist
            CASIntegrityError: If content hash doesn't match
        """
        obj_path = self._object_path(sha256)

        if not obj_path.exists():
            raise SnapshotNotFoundError(f"CAS object not found: {sha256}")

        content = obj_path.read_bytes()

        # Verify integrity
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != sha256:
            raise CASIntegrityError(
                f"CAS integrity check failed: expected {sha256}, got {actual_hash}"
            )

        return content

    def retrieve_json(self, sha256: str) -> dict:
        """
        Retrieve and parse JSON from CAS.

        Args:
            sha256: SHA-256 hash

        Returns:
            Parsed dict
        """
        content = self.retrieve(sha256)
        return json.loads(content.decode("utf-8"))

    def exists(self, sha256: str) -> bool:
        """
        Check if object exists in CAS.

        Args:
            sha256: SHA-256 hash

        Returns:
            True if object exists
        """
        return self._object_path(sha256).exists()


# =============================================================================
# Convenience functions
# =============================================================================


def cas_store(project_root: Path, content: bytes, tier: int) -> str:
    """Store content in CAS. Convenience function."""
    return CAS(project_root).store(content, tier)


def cas_store_json(project_root: Path, data: dict, tier: int) -> str:
    """Store JSON in CAS. Convenience function."""
    return CAS(project_root).store_json(data, tier)


def cas_retrieve(project_root: Path, sha256: str) -> bytes:
    """Retrieve content from CAS. Convenience function."""
    return CAS(project_root).retrieve(sha256)


def cas_retrieve_json(project_root: Path, sha256: str) -> dict:
    """Retrieve JSON from CAS. Convenience function."""
    return CAS(project_root).retrieve_json(sha256)


def cas_exists(project_root: Path, sha256: str) -> bool:
    """Check if object exists in CAS. Convenience function."""
    return CAS(project_root).exists(sha256)
