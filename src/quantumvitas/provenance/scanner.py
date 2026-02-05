"""
Artifact scanner for provenance system.

Per Law P9 (Single Artifact Scanner):
> Artifact scanning MUST occur only at Runner level.
> No duplicate scanners in handlers or engines.

This is the ONLY file that implements artifact scanning.
Handlers and engine modules MUST NOT implement their own scanners.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from quantumvitas.provenance.policy import ArtifactPolicy, DEFAULT_POLICY

logger = logging.getLogger(__name__)


@dataclass
class ScannedFile:
    """Result of scanning a single file."""

    rel_path: str
    abs_path: Path
    size_bytes: int
    mtime: float
    tier: int
    should_capture: bool
    skip_reason: Optional[str] = None
    sha256: Optional[str] = None  # Computed lazily at CAS ingestion


class ArtifactScanner:
    """
    Single scanner for artifact capture. Used ONLY by Runner.

    Per Law P9: No duplicate scanners in handlers or engines.

    Usage:
        scanner = ArtifactScanner(calc_raw_dir, policy)
        scanner.capture_baseline()  # PRE-STEP
        # ... execute step ...
        changes = scanner.scan_changes()  # POST-STEP
    """

    def __init__(self, calc_raw_dir: Path, policy: Optional[ArtifactPolicy] = None):
        """
        Initialize scanner.

        Args:
            calc_raw_dir: Path to calc/raw/ directory
            policy: Artifact policy (uses DEFAULT_POLICY if None)
        """
        self.calc_raw_dir = calc_raw_dir
        self.policy = policy or DEFAULT_POLICY
        self._baseline: Dict[str, Tuple[float, int]] = {}  # path -> (mtime, size)

    def capture_baseline(self) -> None:
        """
        Capture baseline state before step execution.

        Called by Runner at PRE-STEP.
        Records mtime and size for all existing files.
        """
        self._baseline = {}

        if not self.calc_raw_dir.exists():
            return

        for path in self.calc_raw_dir.rglob("*"):
            if path.is_file():
                try:
                    rel_path = path.relative_to(self.calc_raw_dir).as_posix()
                    stat = path.stat()
                    self._baseline[rel_path] = (stat.st_mtime, stat.st_size)
                except (OSError, ValueError):
                    # Skip files we can't stat or that are outside calc_raw_dir
                    pass

        logger.debug(
            "Captured baseline: %d files in %s",
            len(self._baseline),
            self.calc_raw_dir,
        )

    def scan_changes(self) -> List[ScannedFile]:
        """
        Scan for changed/new files after step execution.

        Called by Runner at POST-STEP.

        Delta detection: Uses path + mtime + size comparison.
        Hashing is deferred to CAS ingestion for efficiency.

        Returns:
            List of ScannedFile objects for changed/new files
        """
        results = []

        if not self.calc_raw_dir.exists():
            return results

        for path in self.calc_raw_dir.rglob("*"):
            if path.is_dir():
                continue

            try:
                rel_path = path.relative_to(self.calc_raw_dir).as_posix()
                stat = path.stat()
            except (OSError, ValueError):
                continue

            # Delta detection: skip unchanged files
            if rel_path in self._baseline:
                old_mtime, old_size = self._baseline[rel_path]
                if stat.st_mtime == old_mtime and stat.st_size == old_size:
                    continue  # Unchanged

            # Check policy
            should_capture, tier, skip_reason = self.policy.should_capture(
                rel_path, stat.st_size
            )

            results.append(
                ScannedFile(
                    rel_path=rel_path,
                    abs_path=path,
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                    tier=tier,
                    should_capture=should_capture,
                    skip_reason=skip_reason,
                )
            )

        logger.debug(
            "Scan changes: %d changed files (%d captured) in %s",
            len(results),
            sum(1 for f in results if f.should_capture),
            self.calc_raw_dir,
        )

        return results

    def scan_all(self) -> List[ScannedFile]:
        """
        Scan all files (ignore baseline).

        Useful for full directory scan without delta detection.

        Returns:
            List of ScannedFile objects for all files
        """
        results = []

        if not self.calc_raw_dir.exists():
            return results

        for path in self.calc_raw_dir.rglob("*"):
            if path.is_dir():
                continue

            try:
                rel_path = path.relative_to(self.calc_raw_dir).as_posix()
                stat = path.stat()
            except (OSError, ValueError):
                continue

            should_capture, tier, skip_reason = self.policy.should_capture(
                rel_path, stat.st_size
            )

            results.append(
                ScannedFile(
                    rel_path=rel_path,
                    abs_path=path,
                    size_bytes=stat.st_size,
                    mtime=stat.st_mtime,
                    tier=tier,
                    should_capture=should_capture,
                    skip_reason=skip_reason,
                )
            )

        return results


def hash_file(path: Path) -> str:
    """
    Compute SHA-256 hash of a file.

    Args:
        path: Path to file

    Returns:
        SHA-256 hex digest
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def ingest_artifacts(
    project_root: Path,
    scanned_files: List[ScannedFile],
) -> Optional[str]:
    """
    Ingest artifacts into CAS and create collection manifest.

    Args:
        project_root: Project root directory
        scanned_files: List of scanned files to ingest

    Returns:
        SHA-256 of artifact collection manifest in CAS, or None if no files
    """
    from quantumvitas.provenance.cas import CAS
    from quantumvitas.provenance.recording import now_iso8601

    files_to_capture = [f for f in scanned_files if f.should_capture]
    if not files_to_capture:
        return None

    cas = CAS(project_root)
    artifacts = []

    for scanned in scanned_files:
        artifact_entry = {
            "relative_path": scanned.rel_path,
            "size_bytes": scanned.size_bytes,
            "mtime": scanned.mtime,
            "tier": scanned.tier,
            "captured": scanned.should_capture,
        }

        if scanned.should_capture:
            # Hash and store in CAS
            sha = hash_file(scanned.abs_path)
            scanned.sha256 = sha

            # Store content
            content = scanned.abs_path.read_bytes()
            cas.store(content, tier=scanned.tier)

            artifact_entry["sha256"] = sha
        else:
            artifact_entry["sha256"] = None
            artifact_entry["skip_reason"] = scanned.skip_reason

        artifacts.append(artifact_entry)

    # Create collection manifest
    collection = {
        "version": 1,
        "type": "artifact_collection",
        "created_at": now_iso8601(),
        "artifacts": artifacts,
        "scan_metadata": {
            "total_files_scanned": len(scanned_files),
            "total_size_bytes": sum(f.size_bytes for f in scanned_files),
            "captured_count": len(files_to_capture),
            "captured_size_bytes": sum(f.size_bytes for f in files_to_capture),
        },
    }

    # Store collection manifest in CAS
    return cas.store_json(collection, tier=2)
