"""
Provenance query API.

Provides functions for querying the provenance database
to support the service.history.* RPC endpoints.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from quantumvitas.provenance.db import open_provenance_db
from quantumvitas.provenance.cas import CAS

logger = logging.getLogger(__name__)

# Directory name for provenance data
PROVENANCE_DIR_NAME = ".provenance"


def query_operations(
    project_root: Path,
    calc_ulid: Optional[str] = None,
    limit: int = 100,
    reverse: bool = True,
) -> List[Dict[str, Any]]:
    """
    Query operation events from the provenance database.

    Args:
        project_root: Project root directory
        calc_ulid: Optional filter by calculation ULID
        limit: Maximum results (default 100)
        reverse: If True, return newest first

    Returns:
        List of operation dicts
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            if calc_ulid:
                query = """
                    SELECT ulid, op_type, timestamp, actor, scope,
                           target_ulid, calc_ulid, source, facade_endpoint,
                           request_id, payload
                    FROM operations
                    WHERE calc_ulid = ?
                    ORDER BY ulid {}
                    LIMIT ?
                """.format("DESC" if reverse else "ASC")
                cursor = conn.execute(query, (calc_ulid, limit))
            else:
                query = """
                    SELECT ulid, op_type, timestamp, actor, scope,
                           target_ulid, calc_ulid, source, facade_endpoint,
                           request_id, payload
                    FROM operations
                    ORDER BY ulid {}
                    LIMIT ?
                """.format("DESC" if reverse else "ASC")
                cursor = conn.execute(query, (limit,))

            results = []
            for row in cursor.fetchall():
                payload = {}
                if row[10]:
                    try:
                        payload = json.loads(row[10])
                    except json.JSONDecodeError:
                        pass

                results.append({
                    "ulid": row[0],
                    "op_type": row[1],
                    "timestamp": row[2],
                    "actor": row[3],
                    "scope": row[4],
                    "target_ulid": row[5],
                    "calc_ulid": row[6],
                    "source": row[7],
                    "facade_endpoint": row[8],
                    "request_id": row[9],
                    "payload": payload,
                })

            return results
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to query operations: {e}")
        return []


def query_runs(
    project_root: Path,
    calc_ulid: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Query runs from the provenance database.

    Args:
        project_root: Project root directory
        calc_ulid: Optional filter by calculation ULID
        limit: Maximum results (default 50)

    Returns:
        List of run dicts
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            if calc_ulid:
                query = """
                    SELECT run_ulid, calc_ulid, project_ulid, started_at,
                           finished_at, status, snapshot_sha, engine, error_message
                    FROM runs
                    WHERE calc_ulid = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (calc_ulid, limit))
            else:
                query = """
                    SELECT run_ulid, calc_ulid, project_ulid, started_at,
                           finished_at, status, snapshot_sha, engine, error_message
                    FROM runs
                    ORDER BY started_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (limit,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    "run_ulid": row[0],
                    "calc_ulid": row[1],
                    "project_ulid": row[2],
                    "started_at": row[3],
                    "finished_at": row[4],
                    "status": row[5],
                    "snapshot_sha": row[6],
                    "engine": row[7],
                    "error_message": row[8],
                })

            return results
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to query runs: {e}")
        return []


def get_run_details(
    project_root: Path,
    run_ulid: str,
) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific run.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID

    Returns:
        Run details dict or None if not found
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            # Get run record
            cursor = conn.execute(
                """
                SELECT run_ulid, calc_ulid, project_ulid, started_at,
                       finished_at, status, snapshot_sha, engine, error_message
                FROM runs
                WHERE run_ulid = ?
                """,
                (run_ulid,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            run_info = {
                "run_ulid": row[0],
                "calc_ulid": row[1],
                "project_ulid": row[2],
                "started_at": row[3],
                "finished_at": row[4],
                "status": row[5],
                "snapshot_sha": row[6],
                "engine": row[7],
                "error_message": row[8],
            }

            # Get run steps
            cursor = conn.execute(
                """
                SELECT step_ulid, step_index, status, started_at, finished_at,
                       snapshot_sha, artifact_collection_sha, digest_sha
                FROM run_steps
                WHERE run_ulid = ?
                ORDER BY step_index
                """,
                (run_ulid,),
            )

            steps = []
            for step_row in cursor.fetchall():
                steps.append({
                    "step_ulid": step_row[0],
                    "step_index": step_row[1],
                    "status": step_row[2],
                    "started_at": step_row[3],
                    "finished_at": step_row[4],
                    "snapshot_sha": step_row[5],
                    "artifact_collection_sha": step_row[6],
                    "digest_sha": step_row[7],
                })

            run_info["steps"] = steps
            run_info["step_ulids"] = [s["step_ulid"] for s in steps]

            # Get snapshot if available
            if run_info["snapshot_sha"]:
                try:
                    cas = CAS(project_root)
                    snapshot = cas.retrieve_json(run_info["snapshot_sha"])
                    run_info["snapshot"] = snapshot
                except Exception:
                    pass

            return run_info
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to get run details: {e}")
        return None


def get_latest_run_ulid(
    project_root: Path,
    calc_ulid: Optional[str] = None,
) -> Optional[str]:
    """
    Get the ULID of the most recent run.

    Args:
        project_root: Project root directory
        calc_ulid: Optional filter by calculation ULID

    Returns:
        Run ULID or None if no runs found
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            if calc_ulid:
                cursor = conn.execute(
                    """
                    SELECT run_ulid FROM runs
                    WHERE calc_ulid = ?
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (calc_ulid,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT run_ulid FROM runs
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                )

            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to get latest run: {e}")
        return None


def get_run_step_ulids(project_root: Path, run_ulid: str) -> List[str]:
    """
    Get the step ULIDs for a specific run.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID

    Returns:
        List of step ULIDs in execution order
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            cursor = conn.execute(
                """
                SELECT step_ulid FROM run_steps
                WHERE run_ulid = ?
                ORDER BY step_index
                """,
                (run_ulid,),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to get run step ULIDs: {e}")
        return []


def build_timeline_entry(
    op: Dict[str, Any],
    project_root: Path,
) -> Dict[str, Any]:
    """
    Build a timeline entry from an operation record.

    Maps operation types to frontend-compatible timeline entries.

    Args:
        op: Operation dict from query_operations()
        project_root: Project root directory

    Returns:
        Timeline entry dict
    """
    entry: Dict[str, Any] = {
        "ulid": op["ulid"],
        "timestamp": op["timestamp"],
        "event_type": op["op_type"],
        "calc_ulid": op["calc_ulid"],
        "step_ulid": op.get("target_ulid"),
        "op_type": op["op_type"],
        "kind": "operation",
    }

    payload = op.get("payload", {})

    # Map operation types to frontend event types (lowercase enum values)
    if op["op_type"] in ("step_add", "step_update", "preset_apply", "calc_create"):
        entry["event_type"] = "edit"
        entry["scope"] = op.get("scope", "")
        entry["summary"] = payload.get("summary", "")
        entry["actor"] = op.get("actor", "")

    elif op["op_type"] == "pin_create":
        entry["event_type"] = "pin_created"
        entry["kind"] = "pin"
        entry["run_ulid"] = payload.get("run_ulid", "")
        entry["analysis_kind"] = payload.get("analysis_kind", "")

    else:
        # Catch-all for other operation types (structure_import,
        # species_map_update, calc_update, etc.)
        entry["event_type"] = "operation"
        entry["scope"] = op.get("scope", "")
        entry["summary"] = payload.get("summary", "")
        entry["actor"] = op.get("actor", "")

    return entry
