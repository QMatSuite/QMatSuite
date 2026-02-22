"""
Provenance pin functionality.

Pins allow users to save analysis results (plots, data) to history.
Data is stored in CAS; metadata is recorded in operations table.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from qmatsuite.provenance.cas import CAS
from qmatsuite.provenance.db import open_provenance_db
from qmatsuite.provenance.locks import provenance_lock
from qmatsuite.provenance.opctx import (
    OperationContext,
    OperationType,
    ActorType,
    ScopeType,
)
from qmatsuite.provenance.recording import record_operation_event, generate_ulid

logger = logging.getLogger(__name__)
RunUlidSource = Literal["exact", "inferred", "unknown"]


class PinError(Exception):
    """Error during pin operation."""
    pass


@dataclass
class PinResult:
    """Result of a pin operation."""
    success: bool
    pin_ulid: Optional[str] = None
    run_ulid: Optional[str] = None
    png_sha: Optional[str] = None
    json_sha: Optional[str] = None
    run_ulid_source: RunUlidSource = "exact"
    run_ulid_source_details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "pin_ulid": self.pin_ulid,
            "run_ulid": self.run_ulid,
            "png_sha": self.png_sha,
            "json_sha": self.json_sha,
            "run_ulid_source": self.run_ulid_source,
            "run_ulid_source_details": self.run_ulid_source_details,
            "error": self.error,
        }


def can_pin_to_run(
    project_root: Path,
    run_ulid: str,
    step_ulid: str,
) -> Dict[str, Any]:
    """
    Check if pinning is allowed for a run and step.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        step_ulid: Step ULID

    Returns:
        Dict with 'allowed' and 'reason' keys
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            # Check if run exists
            cursor = conn.execute(
                "SELECT status FROM runs WHERE run_ulid = ?",
                (run_ulid,),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "allowed": False,
                    "reason": f"Run not found: {run_ulid}",
                }

            # Check if step is in this run
            cursor = conn.execute(
                "SELECT status FROM run_steps WHERE run_ulid = ? AND step_ulid = ?",
                (run_ulid, step_ulid),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    "allowed": False,
                    "reason": f"Step {step_ulid} not found in run {run_ulid}",
                }

            return {"allowed": True, "reason": None}

        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to check pin eligibility: {e}")
        return {"allowed": False, "reason": str(e)}


def pin_analysis_to_history(
    project_root: Path,
    run_ulid: Optional[str],
    step_ulid: str,
    analysis_kind: str,
    png_data: Optional[bytes] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    run_ulid_source: RunUlidSource = "exact",
    run_ulid_source_details: Optional[Dict[str, Any]] = None,
) -> PinResult:
    """
    Pin analysis results to provenance.

    Args:
        project_root: Project root directory
        run_ulid: Optional run ULID
        step_ulid: Step ULID
        analysis_kind: Type of analysis (e.g., "bands", "dos")
        png_data: Optional PNG image data
        json_payload: Optional JSON data to store
        run_ulid_source: Provenance confidence for run linkage
            ("exact" | "inferred" | "unknown")
        run_ulid_source_details: Optional details describing inference/match path

    Returns:
        PinResult with success status and storage references

    Raises:
        PinError: If pinning fails
    """
    # Validate
    if run_ulid:
        can_pin = can_pin_to_run(project_root, run_ulid, step_ulid)
        if not can_pin["allowed"]:
            raise PinError(can_pin["reason"])
    elif run_ulid_source != "unknown":
        raise PinError("run_ulid is required unless run_ulid_source is 'unknown'")

    if not png_data and not json_payload:
        raise PinError("At least png_data or json_payload required")
    if run_ulid_source not in {"exact", "inferred", "unknown"}:
        raise PinError(f"Invalid run_ulid_source: {run_ulid_source}")

    try:
        cas = CAS(project_root)
        pin_ulid = generate_ulid()

        # Store PNG in CAS
        png_sha = None
        if png_data:
            png_sha = cas.store(png_data, tier=1)

        # Store JSON in CAS
        json_sha = None
        if json_payload:
            json_sha = cas.store_json(json_payload, tier=1)

        # Record pin metadata
        pin_metadata = {
            "pin_ulid": pin_ulid,
            "run_ulid": run_ulid,
            "run_ulid_source": run_ulid_source,
            "run_ulid_source_details": run_ulid_source_details,
            "step_ulid": step_ulid,
            "analysis_kind": analysis_kind,
            "png_sha": png_sha,
            "json_sha": json_sha,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }

        # Store pin index in CAS
        pin_index_sha = cas.store_json(pin_metadata, tier=1)

        # Record operation event
        opctx = OperationContext(
            op=OperationType.PIN_CREATE,
            actor=ActorType.HUMAN,
            scope=ScopeType.STEP,
            source="pin_analysis_to_history",
            payload={
                "run_ulid": run_ulid,
                "step_ulid": step_ulid,
                "analysis_kind": analysis_kind,
                "pin_ulid": pin_ulid,
                "run_ulid_source": run_ulid_source,
                "run_ulid_source_details": run_ulid_source_details,
                "pin_index_sha": pin_index_sha,
            },
        )

        try:
            record_operation_event(
                project_root,
                opctx,
                target_ulid=step_ulid,
            )
        except Exception as e:
            # Law P7: Provenance failures are non-fatal
            logger.warning(f"Failed to record pin operation: {e}")

        logger.debug(
            "Pinned %s analysis for run=%s step=%s (pin=%s)",
            analysis_kind,
            run_ulid,
            step_ulid,
            pin_ulid,
        )

        return PinResult(
            success=True,
            pin_ulid=pin_ulid,
            run_ulid=run_ulid,
            png_sha=png_sha,
            json_sha=json_sha,
            run_ulid_source=run_ulid_source,
            run_ulid_source_details=run_ulid_source_details,
        )

    except Exception as e:
        logger.error(f"Failed to pin analysis: {e}")
        raise PinError(str(e)) from e


def get_pin_data(
    project_root: Path,
    run_ulid: str,
    step_ulid: str,
    analysis_kind: str,
) -> Dict[str, Any]:
    """
    Get pinned data for a step analysis.

    Searches for the most recent pin matching the criteria.

    Args:
        project_root: Project root directory
        run_ulid: Run ULID
        step_ulid: Step ULID
        analysis_kind: Type of analysis

    Returns:
        Dict with png_data (bytes), json_data (dict), error (str if failed)
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            # First check if the run exists
            cursor = conn.execute(
                "SELECT run_ulid FROM runs WHERE run_ulid = ?",
                (run_ulid,),
            )
            if cursor.fetchone() is None:
                return {"error": f"Run not found: {run_ulid}", "png_data": None, "json_data": None}

            # Find the most recent PIN_CREATE operation for this step/analysis
            cursor = conn.execute(
                """
                SELECT payload FROM operations
                WHERE op_type = 'pin_create'
                AND target_ulid = ?
                ORDER BY timestamp DESC
                """,
                (step_ulid,),
            )

            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[0]) if row[0] else {}
                except json.JSONDecodeError:
                    continue

                if (
                    payload.get("run_ulid") == run_ulid
                    and payload.get("analysis_kind") == analysis_kind
                ):
                    # Found matching pin
                    cas = CAS(project_root)
                    result: Dict[str, Any] = {
                        "pin_ulid": payload.get("pin_ulid"),
                        "png_data": None,
                        "json_data": None,
                        "run_ulid_source": payload.get("run_ulid_source", "unknown"),
                        "error": None,
                    }

                    # Retrieve from CAS via pin_index
                    pin_index_sha = payload.get("pin_index_sha")
                    if pin_index_sha:
                        try:
                            pin_metadata = cas.retrieve_json(pin_index_sha)
                            png_sha = pin_metadata.get("png_sha")
                            json_sha = pin_metadata.get("json_sha")
                            result["run_ulid_source"] = pin_metadata.get(
                                "run_ulid_source",
                                result["run_ulid_source"],
                            )

                            if png_sha:
                                result["png_data"] = cas.retrieve(png_sha)
                            if json_sha:
                                result["json_data"] = cas.retrieve_json(json_sha)

                        except Exception as e:
                            logger.warning(f"Failed to retrieve pin data from CAS: {e}")
                            result["error"] = str(e)

                    return result

            # No matching pin found
            return {"error": "Pin not found", "png_data": None, "json_data": None}

        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to get pin data: {e}")
        return {"error": str(e), "png_data": None, "json_data": None}


def list_pins_for_step(
    project_root: Path,
    step_ulid: str,
) -> list[Dict[str, Any]]:
    """
    List all pins for a specific step.

    Args:
        project_root: Project root directory
        step_ulid: Step ULID

    Returns:
        List of pin metadata dicts
    """
    try:
        conn = open_provenance_db(project_root)
        try:
            cursor = conn.execute(
                """
                SELECT payload, timestamp FROM operations
                WHERE op_type = 'pin_create'
                AND target_ulid = ?
                ORDER BY timestamp DESC
                """,
                (step_ulid,),
            )

            pins = []
            for row in cursor.fetchall():
                try:
                    payload = json.loads(row[0]) if row[0] else {}
                    payload["timestamp"] = row[1]
                    pins.append(payload)
                except json.JSONDecodeError:
                    continue

            return pins

        finally:
            conn.close()

    except Exception as e:
        logger.warning(f"Failed to list pins: {e}")
        return []
