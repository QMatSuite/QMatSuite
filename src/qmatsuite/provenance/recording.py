"""
Provenance event recording.

This module provides functions for recording operation events
to the provenance database.

Per Law P2: All YAML writes carry OperationContext.
Per Law P6: Recording happens AFTER edit.lock is released.
Per Law P7: Recording failures are logged but don't fail YAML writes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from qmatsuite.provenance.errors import ProvenanceError
from qmatsuite.provenance.opctx import OperationContext
from qmatsuite.provenance.locks import provenance_lock
from qmatsuite.provenance.db import open_provenance_db

logger = logging.getLogger(__name__)


def generate_ulid() -> str:
    """
    Generate a new ULID.

    Uses the ulid package if available, otherwise falls back to UUID.
    """
    try:
        import ulid
        return str(ulid.new())
    except ImportError:
        import uuid
        return str(uuid.uuid4()).replace("-", "").upper()[:26]


def now_iso8601() -> str:
    """Get current timestamp in ISO8601 format with microseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def compute_diff_summary(before: Optional[dict], after: dict) -> Dict[str, Any]:
    """
    Compute a summary of changes between before and after states.

    This is a lightweight diff that captures:
    - List of changed paths (JSONPointer-like)
    - Human-readable summary

    Args:
        before: State before change (None for new documents)
        after: State after change

    Returns:
        Dict with 'changed_paths' and 'summary' keys
    """
    if before is None:
        return {
            "changed_paths": [],
            "summary": "Created new document",
        }

    changed_paths = []
    _find_changed_paths(before, after, "", changed_paths)

    n_changes = len(changed_paths)
    if n_changes == 0:
        summary = "No changes detected"
    elif n_changes == 1:
        summary = f"Changed {changed_paths[0]}"
    elif n_changes <= 5:
        summary = f"Changed {n_changes} fields: {', '.join(changed_paths[:3])}" + ("..." if n_changes > 3 else "")
    else:
        summary = f"Changed {n_changes} fields"

    return {
        "changed_paths": changed_paths[:20],  # Limit to prevent huge payloads
        "summary": summary,
    }


def _find_changed_paths(before: Any, after: Any, path: str, result: List[str], max_depth: int = 10) -> None:
    """
    Recursively find changed paths between two dicts.

    Args:
        before: Before value
        after: After value
        path: Current path prefix
        result: List to append changed paths to
        max_depth: Maximum recursion depth
    """
    if max_depth <= 0:
        return

    if type(before) != type(after):
        result.append(path or "/")
        return

    if isinstance(before, dict) and isinstance(after, dict):
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            child_path = f"{path}/{key}" if path else f"/{key}"
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val != after_val:
                if isinstance(before_val, dict) and isinstance(after_val, dict):
                    _find_changed_paths(before_val, after_val, child_path, result, max_depth - 1)
                else:
                    result.append(child_path)
    elif before != after:
        result.append(path or "/")


def record_operation_event(
    project_root: Path,
    opctx: OperationContext,
    diff_summary: Optional[Dict[str, Any]] = None,
    target_ulid: Optional[str] = None,
    calc_ulid: Optional[str] = None,
) -> str:
    """
    Record an operation event to the provenance database.

    Per Law P6: This must be called AFTER edit.lock is released.
    Per Law P7: Failures are logged but don't propagate.

    Args:
        project_root: Project root directory
        opctx: OperationContext for this operation
        diff_summary: Optional diff summary from compute_diff_summary()
        target_ulid: Optional ULID of the affected entity
        calc_ulid: Optional calculation ULID

    Returns:
        ULID of the recorded operation

    Raises:
        ProvenanceError: If recording fails (per Law P7, callers should catch this)
    """
    operation_ulid = generate_ulid()
    timestamp = opctx.timestamp or now_iso8601()

    # Build payload
    payload = dict(opctx.payload) if opctx.payload else {}
    if diff_summary:
        payload.update(diff_summary)

    try:
        with provenance_lock(project_root):
            conn = open_provenance_db(project_root)
            try:
                conn.execute(
                    """
                    INSERT INTO operations (
                        ulid, op_type, timestamp, actor, scope,
                        target_ulid, calc_ulid, source, facade_endpoint,
                        request_id, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation_ulid,
                        opctx.op.value,
                        timestamp,
                        opctx.actor.value,
                        opctx.scope.value,
                        target_ulid,
                        calc_ulid,
                        opctx.source,
                        opctx.facade_endpoint,
                        opctx.request_id,
                        json.dumps(payload),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        logger.debug(
            "Recorded operation %s: %s (%s)",
            operation_ulid,
            opctx.op.value,
            opctx.source,
        )
        return operation_ulid

    except Exception as e:
        raise ProvenanceError(f"Failed to record operation: {e}") from e


def record_seed_event(project_root: Path) -> str:
    """
    Record a seed event for a newly initialized project.

    This is called when provenance is first enabled for a project.

    Args:
        project_root: Project root directory

    Returns:
        ULID of the seed operation
    """
    from qmatsuite.provenance.opctx import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    opctx = OperationContext(
        op=OperationType.SEED,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="ensure_provenance_initialized",
        payload={"migration": True},
    )

    return record_operation_event(project_root, opctx)


# =============================================================================
# Run Recording Functions
# =============================================================================


def record_run_start(
    project_root: Path,
    run_ulid: str,
    calc_ulid: str,
    snapshot_sha: Optional[str] = None,
    engine: Optional[str] = None,
    project_ulid: Optional[str] = None,
) -> None:
    """
    Record the start of a calculation run.

    Per Law P7: Failures are logged but don't propagate.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        calc_ulid: Calculation ULID
        snapshot_sha: Optional SHA-256 of pre-run snapshot in CAS
        engine: Optional engine family (qe, vasp, etc.)
        project_ulid: Optional project ULID
    """
    try:
        with provenance_lock(project_root):
            conn = open_provenance_db(project_root)
            try:
                conn.execute(
                    """
                    INSERT INTO runs (
                        run_ulid, calc_ulid, project_ulid, started_at,
                        status, snapshot_sha, engine
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_ulid,
                        calc_ulid,
                        project_ulid,
                        now_iso8601(),
                        "running",
                        snapshot_sha,
                        engine,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        logger.debug("Recorded run start: %s (calc: %s)", run_ulid, calc_ulid)

    except Exception as e:
        logger.warning(f"Failed to record run start (non-fatal): {e}")


def record_run_complete(
    project_root: Path,
    run_ulid: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Record the completion of a calculation run.

    Per Law P7: Failures are logged but don't propagate.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        status: Final status ('success', 'failed', 'aborted')
        error_message: Optional error message if failed/aborted
    """
    try:
        with provenance_lock(project_root):
            conn = open_provenance_db(project_root)
            try:
                conn.execute(
                    """
                    UPDATE runs
                    SET finished_at = ?, status = ?, error_message = ?
                    WHERE run_ulid = ?
                    """,
                    (
                        now_iso8601(),
                        status,
                        error_message,
                        run_ulid,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        logger.debug("Recorded run complete: %s (status: %s)", run_ulid, status)

    except Exception as e:
        logger.warning(f"Failed to record run complete (non-fatal): {e}")


def record_run_step(
    project_root: Path,
    run_ulid: str,
    step_ulid: str,
    step_index: int,
    status: str = "pending",
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    snapshot_sha: Optional[str] = None,
    artifact_collection_sha: Optional[str] = None,
    digest_sha: Optional[str] = None,
) -> None:
    """
    Record a step execution in the run_steps table.

    Per Law P7: Failures are logged but don't propagate.
    This creates a normalized row per step (not a JSON blob).

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        step_ulid: Step ULID
        step_index: Position in execution order (0-based)
        status: Step status ('pending', 'running', 'success', 'failed', 'skipped')
        started_at: Optional ISO8601 start time
        finished_at: Optional ISO8601 finish time
        snapshot_sha: Optional SHA of step YAML snapshot
        artifact_collection_sha: Optional SHA of artifact collection manifest
        digest_sha: Optional SHA of step digest
    """
    try:
        with provenance_lock(project_root):
            conn = open_provenance_db(project_root)
            try:
                # Upsert: insert or update on conflict
                conn.execute(
                    """
                    INSERT INTO run_steps (
                        run_ulid, step_ulid, step_index, status,
                        started_at, finished_at, snapshot_sha,
                        artifact_collection_sha, digest_sha
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_ulid, step_ulid) DO UPDATE SET
                        status = excluded.status,
                        started_at = COALESCE(excluded.started_at, run_steps.started_at),
                        finished_at = COALESCE(excluded.finished_at, run_steps.finished_at),
                        snapshot_sha = COALESCE(excluded.snapshot_sha, run_steps.snapshot_sha),
                        artifact_collection_sha = COALESCE(excluded.artifact_collection_sha, run_steps.artifact_collection_sha),
                        digest_sha = COALESCE(excluded.digest_sha, run_steps.digest_sha)
                    """,
                    (
                        run_ulid,
                        step_ulid,
                        step_index,
                        status,
                        started_at,
                        finished_at,
                        snapshot_sha,
                        artifact_collection_sha,
                        digest_sha,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        logger.debug(
            "Recorded run step: %s/%s (index: %d, status: %s)",
            run_ulid,
            step_ulid,
            step_index,
            status,
        )

    except Exception as e:
        logger.warning(f"Failed to record run step (non-fatal): {e}")


def update_run_step_status(
    project_root: Path,
    run_ulid: str,
    step_ulid: str,
    status: str,
    finished_at: Optional[str] = None,
    artifact_collection_sha: Optional[str] = None,
) -> None:
    """
    Update the status of a run step.

    Per Law P7: Failures are logged but don't propagate.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        step_ulid: Step ULID
        status: New status
        finished_at: Optional finish time
        artifact_collection_sha: Optional artifact collection SHA
    """
    try:
        with provenance_lock(project_root):
            conn = open_provenance_db(project_root)
            try:
                conn.execute(
                    """
                    UPDATE run_steps
                    SET status = ?,
                        finished_at = COALESCE(?, finished_at),
                        artifact_collection_sha = COALESCE(?, artifact_collection_sha)
                    WHERE run_ulid = ? AND step_ulid = ?
                    """,
                    (
                        status,
                        finished_at,
                        artifact_collection_sha,
                        run_ulid,
                        step_ulid,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    except Exception as e:
        logger.warning(f"Failed to update run step status (non-fatal): {e}")
