"""
Restore functionality for provenance system.

Allows restoring SSOT state from a run snapshot.
"""

from __future__ import annotations

import logging
import yaml
from pathlib import Path
from typing import Optional

from qmatsuite.provenance.cas import CAS
from qmatsuite.provenance.snapshots import get_run_snapshot
from qmatsuite.provenance.opctx import (
    OperationContext,
    OperationType,
    ActorType,
    ScopeType,
)
from qmatsuite.provenance.errors import SnapshotNotFoundError

logger = logging.getLogger(__name__)


def restore_from_snapshot(
    project_root: Path,
    snapshot_sha: str,
    opctx: Optional[OperationContext] = None,
    calc_dir: Optional[Path] = None,
) -> dict:
    """
    Restore SSOT files from a run snapshot.

    Writes files via save_yaml_doc() with RESTORE opctx for provenance tracking.

    Args:
        project_root: Project root directory
        snapshot_sha: SHA-256 hash of snapshot in CAS
        opctx: Optional OperationContext (created if not provided)
        calc_dir: Optional explicit calculation directory

    Returns:
        Dict with restore summary

    Raises:
        SnapshotNotFoundError: If snapshot doesn't exist
    """
    from qmatsuite.core.yamldoc import StepDoc, CalcDoc
    from qmatsuite.core.yaml_io import save_yaml_doc

    # Get snapshot
    snapshot = get_run_snapshot(project_root, snapshot_sha)

    calc_ulid = snapshot.get("calc_ulid")
    run_ulid = snapshot.get("run_ulid")

    if calc_dir is None:
        if calc_ulid:
            calc_dir = project_root / "calculations" / calc_ulid
        else:
            raise ValueError("calc_dir required when snapshot has no calc_ulid")

    # Create opctx if not provided
    if opctx is None:
        opctx = OperationContext(
            op=OperationType.RESTORE,
            actor=ActorType.HUMAN,
            scope=ScopeType.CALC,
            source="restore_from_snapshot",
            payload={
                "from_run_ulid": run_ulid,
                "snapshot_sha": snapshot_sha,
            },
        )

    # Restore files
    restored_files = []
    files = snapshot.get("files", {})

    for filename, content in files.items():
        file_path = calc_dir / filename
        data = yaml.safe_load(content)

        # Determine doc type
        if filename == "calculation.yaml":
            doc = CalcDoc(data)
        elif filename.startswith("step_"):
            doc = StepDoc(data)
        else:
            continue  # Skip unknown files

        save_yaml_doc(doc, file_path, opctx)
        restored_files.append(filename)
        logger.info("Restored %s from snapshot %s", filename, snapshot_sha[:12])

    return {
        "snapshot_sha": snapshot_sha,
        "run_ulid": run_ulid,
        "calc_ulid": calc_ulid,
        "restored_files": restored_files,
        "file_count": len(restored_files),
    }


def restore_from_run(
    project_root: Path,
    run_ulid: str,
    opctx: Optional[OperationContext] = None,
) -> dict:
    """
    Restore SSOT files from a run's snapshot.

    Convenience function that looks up the snapshot SHA from the runs table.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        opctx: Optional OperationContext

    Returns:
        Dict with restore summary

    Raises:
        SnapshotNotFoundError: If run or snapshot doesn't exist
    """
    from qmatsuite.provenance.db import open_provenance_db

    # Look up snapshot SHA
    conn = open_provenance_db(project_root)
    try:
        cursor = conn.execute(
            "SELECT snapshot_sha, calc_ulid FROM runs WHERE run_ulid = ?",
            (run_ulid,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if row is None:
        raise SnapshotNotFoundError(f"Run not found: {run_ulid}")

    snapshot_sha = row["snapshot_sha"]
    if snapshot_sha is None:
        raise SnapshotNotFoundError(f"Run {run_ulid} has no snapshot")

    # Create opctx with run_ulid reference
    if opctx is None:
        opctx = OperationContext(
            op=OperationType.RESTORE,
            actor=ActorType.HUMAN,
            scope=ScopeType.CALC,
            source="restore_from_run",
            payload={"from_run_ulid": run_ulid},
        )

    return restore_from_snapshot(project_root, snapshot_sha, opctx)
