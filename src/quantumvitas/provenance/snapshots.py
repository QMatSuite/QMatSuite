"""
Run snapshot creation and retrieval.

Snapshots capture the complete SSOT state before a run:
- calculation.yaml
- step_*.yaml files
- Structure references (with SHA)

Snapshots are Tier-0 CAS objects (never auto-deleted).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from quantumvitas.provenance.cas import CAS
from quantumvitas.provenance.errors import SnapshotNotFoundError

logger = logging.getLogger(__name__)


def now_iso8601() -> str:
    """Get current timestamp in ISO8601 format with microseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def create_run_snapshot(
    project_root: Path,
    calc_ulid: str,
    run_ulid: str,
    calc_dir: Optional[Path] = None,
) -> str:
    """
    Create a snapshot of SSOT state before a run.

    Collects calculation.yaml + step_*.yaml and stores in CAS as Tier-0.

    Args:
        project_root: Project root directory
        calc_ulid: Calculation ULID
        run_ulid: Run ULID
        calc_dir: Optional explicit calculation directory

    Returns:
        SHA-256 hash of snapshot in CAS
    """
    if calc_dir is None:
        calc_dir = project_root / "calculations" / calc_ulid

    snapshot = {
        "version": 1,
        "type": "run_snapshot",
        "run_ulid": run_ulid,
        "calc_ulid": calc_ulid,
        "timestamp": now_iso8601(),
        "files": {},
        "structure_refs": [],
    }

    # Collect calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    if calc_yaml.exists():
        snapshot["files"]["calculation.yaml"] = calc_yaml.read_text()

    # Collect step_*.yaml files
    for step_file in sorted(calc_dir.glob("step_*.yaml")):
        snapshot["files"][step_file.name] = step_file.read_text()

    # Store in CAS as Tier-0
    cas = CAS(project_root)
    sha = cas.store_json(snapshot, tier=0)

    logger.debug(
        "Created run snapshot %s for calc %s, run %s (%d files)",
        sha[:12],
        calc_ulid,
        run_ulid,
        len(snapshot["files"]),
    )

    return sha


def get_run_snapshot(project_root: Path, sha256: str) -> Dict[str, Any]:
    """
    Retrieve a run snapshot from CAS.

    Args:
        project_root: Project root directory
        sha256: SHA-256 hash of snapshot

    Returns:
        Snapshot dict

    Raises:
        SnapshotNotFoundError: If snapshot doesn't exist
    """
    cas = CAS(project_root)
    return cas.retrieve_json(sha256)


def list_snapshot_files(snapshot: Dict[str, Any]) -> List[str]:
    """
    List files in a snapshot.

    Args:
        snapshot: Snapshot dict

    Returns:
        List of file names
    """
    return list(snapshot.get("files", {}).keys())


def get_snapshot_file_content(snapshot: Dict[str, Any], filename: str) -> Optional[str]:
    """
    Get content of a file from snapshot.

    Args:
        snapshot: Snapshot dict
        filename: File name (e.g., "calculation.yaml", "step_scf.yaml")

    Returns:
        File content or None if not found
    """
    return snapshot.get("files", {}).get(filename)
