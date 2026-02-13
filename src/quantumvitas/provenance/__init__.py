"""
Provenance / Versioned History System.

This module provides:
- OperationContext for tracking YAML write operations
- SQLite timeline for operation events and runs
- Content-Addressed Store (CAS) for snapshots and artifacts
- Graceful degradation (provenance failures don't fail YAML writes)

Reference: docs/laws/L1/PROVENANCE_VERSIONED_HISTORY_SPEC.md v1.1

Key Laws:
- P1: History World must not participate in runtime logic
- P2: All YAML writes require OperationContext
- P3: Skip/rerun decisions must not consult provenance
- P6: Sequential locking (edit.lock -> release -> provenance.lock)
- P7: Provenance failures must not fail YAML writes
- P9: Single artifact scanner at Runner level only
"""

from quantumvitas.provenance.opctx import (
    OperationContext,
    OperationType,
    ActorType,
    ScopeType,
    opctx_for_step_add,
    opctx_for_step_update,
    opctx_for_preset_apply,
    opctx_for_calc_create,
    opctx_for_restore,
    opctx_system_internal,
)
from quantumvitas.provenance.errors import (
    ProvenanceError,
    OperationContextRequiredError,
    CASIntegrityError,
    SnapshotNotFoundError,
    LockReentrancyError,
)
from quantumvitas.provenance.recording import (
    record_operation_event,
    compute_diff_summary,
    record_run_start,
    record_run_complete,
    record_run_step,
    update_run_step_status,
)
from quantumvitas.provenance.cas import (
    CAS,
    cas_store,
    cas_store_json,
    cas_retrieve,
    cas_retrieve_json,
    cas_exists,
)
from quantumvitas.provenance.snapshots import (
    create_run_snapshot,
    get_run_snapshot,
)
from quantumvitas.provenance.restore import (
    restore_from_snapshot,
    restore_from_run,
)
from quantumvitas.provenance.policy import (
    ArtifactPolicy,
    DEFAULT_POLICY,
    QE_POLICY,
    VASP_POLICY,
    ORCA_POLICY,
    GAUSSIAN_POLICY,
    XTB_POLICY,
    LAMMPS_POLICY,
)
from quantumvitas.provenance.scanner import (
    ArtifactScanner,
    ScannedFile,
    ingest_artifacts,
)
from quantumvitas.provenance.db import (
    open_provenance_db,
    ensure_provenance_initialized,
    ProvenanceDB,
)
from quantumvitas.provenance.locks import (
    provenance_lock,
)
from quantumvitas.provenance.query import (
    query_operations,
    query_runs,
    get_run_details,
    get_latest_run_ulid,
    get_run_step_ulids,
    build_timeline_entry,
    PROVENANCE_DIR_NAME,
)
from quantumvitas.provenance.pins import (
    PinError,
    PinResult,
    can_pin_to_run,
    pin_analysis_to_history,
    get_pin_data,
    list_pins_for_step,
)

__all__ = [
    # Core context
    "OperationContext",
    "OperationType",
    "ActorType",
    "ScopeType",
    # Context factories
    "opctx_for_step_add",
    "opctx_for_step_update",
    "opctx_for_preset_apply",
    "opctx_for_calc_create",
    "opctx_for_restore",
    "opctx_system_internal",
    # Errors
    "ProvenanceError",
    "OperationContextRequiredError",
    "CASIntegrityError",
    "SnapshotNotFoundError",
    "LockReentrancyError",
    # Recording
    "record_operation_event",
    "compute_diff_summary",
    "record_run_start",
    "record_run_complete",
    "record_run_step",
    "update_run_step_status",
    # CAS
    "CAS",
    "cas_store",
    "cas_store_json",
    "cas_retrieve",
    "cas_retrieve_json",
    "cas_exists",
    # Snapshots
    "create_run_snapshot",
    "get_run_snapshot",
    # Restore
    "restore_from_snapshot",
    "restore_from_run",
    # Artifact Policy
    "ArtifactPolicy",
    "DEFAULT_POLICY",
    "QE_POLICY",
    "VASP_POLICY",
    "ORCA_POLICY",
    "GAUSSIAN_POLICY",
    "XTB_POLICY",
    "LAMMPS_POLICY",
    # Scanner
    "ArtifactScanner",
    "ScannedFile",
    "ingest_artifacts",
    # Database
    "open_provenance_db",
    "ensure_provenance_initialized",
    "ProvenanceDB",
    # Locks
    "provenance_lock",
    # Query API
    "query_operations",
    "query_runs",
    "get_run_details",
    "get_latest_run_ulid",
    "get_run_step_ulids",
    "build_timeline_entry",
    "PROVENANCE_DIR_NAME",
    # Pins
    "PinError",
    "PinResult",
    "can_pin_to_run",
    "pin_analysis_to_history",
    "get_pin_data",
    "list_pins_for_step",
]
