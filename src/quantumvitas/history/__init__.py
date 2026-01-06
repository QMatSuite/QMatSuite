"""
Project History: Append-only archive of project evolution.

This module provides:
- ProjectHistory: Main class for history storage and retrieval
- Run revisions with digests
- Semantic edit events
- Pin-to-history functionality

Design invariants (DO NOT VIOLATE):
1. History is append-only and immutable. Once recorded, never rewrite.
2. Every engine invocation creates a run with a unique ULID.
3. Digests are computed automatically at end of each run (success or failure).
4. Pins are restricted to steps included in the MOST RECENT run.
5. History is project-scoped (under project_root/.history/).
"""

from quantumvitas.history.storage import (
    ProjectHistory,
    ensure_history_dir,
    get_latest_run_id,
)

from quantumvitas.history.events import (
    HistoryEvent,
    EditEvent,
    EditOperation,
    RunStartedEvent,
    RunFinishedEvent,
    PinCreatedEvent,
    BaselineEvent,
)

from quantumvitas.history.run_revision import (
    RunRevision,
    RunStatus,
    StepDigest,
    create_run_revision,
    load_run_revision,
)

from quantumvitas.history.digests import (
    compute_step_digest,
    compute_run_digest,
    DigestValue,
)

from quantumvitas.history.pins import (
    pin_analysis_to_history,
    PinResult,
    PinError,
)

__all__ = [
    # Storage
    "ProjectHistory",
    "ensure_history_dir",
    "get_latest_run_id",
    # Events
    "HistoryEvent",
    "EditEvent",
    "EditOperation",
    "RunStartedEvent",
    "RunFinishedEvent",
    "PinCreatedEvent",
    "BaselineEvent",
    # Run revisions
    "RunRevision",
    "RunStatus",
    "StepDigest",
    "create_run_revision",
    "load_run_revision",
    # Digests
    "compute_step_digest",
    "compute_run_digest",
    "DigestValue",
    # Pins
    "pin_analysis_to_history",
    "PinResult",
    "PinError",
]

