"""
OperationContext and related enums for provenance tracking.

Per Law P2 (OperationContext Required): Any write to Present World SSOT YAML
MUST carry an explicit OperationContext. This provides:
- Clear audit trail of who did what
- Structured payload for operation-specific data
- Correlation IDs for multi-operation requests
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any


class OperationType(str, Enum):
    """
    Exhaustive list of operation types.

    Per Law P8: Only SSOT-writing actions are provenance events.
    UI-only operations (like preset SELECT) are NOT recorded.
    """

    # Project-level
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"

    # Calculation-level
    CALC_CREATE = "calc_create"
    CALC_UPDATE = "calc_update"
    CALC_DELETE = "calc_delete"
    CALC_COPY = "calc_copy"
    CALC_FORK = "calc_fork"

    # Step-level
    STEP_ADD = "step_add"
    STEP_UPDATE = "step_update"
    STEP_REMOVE = "step_remove"
    STEP_REORDER = "step_reorder"

    # Preset operations (APPLY only; SELECT is UI-only, not recorded)
    PRESET_APPLY = "preset_apply"
    PRESET_CLEAR = "preset_clear"

    # Structure operations
    STRUCTURE_CREATE = "structure_create"
    STRUCTURE_UPDATE = "structure_update"
    STRUCTURE_IMPORT = "structure_import"
    RELAX_PROMOTE = "relax_promote"  # Relaxed structure promoted to resource

    # Species/Pseudo
    SPECIES_MAP_UPDATE = "species_map_update"
    PSEUDO_ASSIGN = "pseudo_assign"

    # Rollback/Restore
    RESTORE = "restore"  # Restore from snapshot
    ROLLBACK = "rollback"  # Rollback to previous state

    # Pins
    PIN_CREATE = "pin_create"  # Pin analysis to history
    PIN_DELETE = "pin_delete"  # Remove pinned analysis

    # Misc
    SEED = "seed"  # Initial state capture
    CORRECTION = "correction"  # Manual correction event
    CUSTOM = "custom"  # Extension point


class ActorType(str, Enum):
    """Who initiated the operation."""
    HUMAN = "human"  # User-initiated via UI/CLI
    AGENT = "agent"  # AI agent initiated
    SYSTEM = "system"  # System-initiated (auto-saves, migrations, etc.)


class ScopeType(str, Enum):
    """Scope of the operation."""
    PROJECT = "project"
    CALC = "calc"
    STEP = "step"
    STRUCTURE = "structure"
    RESOURCE = "resource"  # Pseudo, potential, etc.


@dataclass(frozen=True, slots=True)
class OperationContext:
    """
    Mandatory context for all SSOT writes. Immutable and serializable.

    Per Law P2: save_yaml_doc() MUST require an opctx parameter.
    Calling save_yaml_doc() without opctx MUST raise OperationContextRequiredError.

    Attributes:
        op: What kind of operation (OperationType enum)
        actor: Who initiated (ActorType enum)
        scope: Project/calc/step/structure scope (ScopeType enum)
        source: Kernel public method name (e.g., "Calculation.add_step")
        payload: Operation-specific data (JSON-serializable dict)
        timestamp: ISO8601 timestamp; recorder sets if None
        facade_endpoint: Optional higher-level API endpoint
        request_id: Optional correlation ID for multi-op requests
    """

    op: OperationType
    actor: ActorType
    scope: ScopeType
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None
    facade_endpoint: Optional[str] = None
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for SQLite JSON column."""
        return {
            "op": self.op.value,
            "actor": self.actor.value,
            "scope": self.scope.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "facade_endpoint": self.facade_endpoint,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationContext":
        """Deserialize from SQLite JSON column."""
        return cls(
            op=OperationType(data["op"]),
            actor=ActorType(data["actor"]),
            scope=ScopeType(data["scope"]),
            source=data["source"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
            facade_endpoint=data.get("facade_endpoint"),
            request_id=data.get("request_id"),
        )

    def with_timestamp(self) -> "OperationContext":
        """Return a copy with current timestamp if not already set."""
        if self.timestamp is not None:
            return self
        ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        return OperationContext(
            op=self.op,
            actor=self.actor,
            scope=self.scope,
            source=self.source,
            payload=self.payload,
            timestamp=ts,
            facade_endpoint=self.facade_endpoint,
            request_id=self.request_id,
        )


# =============================================================================
# Convenience factory functions
# =============================================================================


def opctx_for_step_add(
    step_type_spec: str,
    actor: ActorType = ActorType.SYSTEM,
    source: str = "Step.add",
) -> OperationContext:
    """Create OperationContext for adding a step."""
    return OperationContext(
        op=OperationType.STEP_ADD,
        actor=actor,
        scope=ScopeType.STEP,
        source=source,
        payload={"step_type_spec": step_type_spec},
    )


def opctx_for_step_update(
    step_ulid: str,
    actor: ActorType = ActorType.SYSTEM,
    source: str = "Step.update",
) -> OperationContext:
    """Create OperationContext for updating a step."""
    return OperationContext(
        op=OperationType.STEP_UPDATE,
        actor=actor,
        scope=ScopeType.STEP,
        source=source,
        payload={"step_ulid": step_ulid},
    )


def opctx_for_preset_apply(
    preset_name: str,
    actor: ActorType = ActorType.HUMAN,
    source: str = "Step.apply_preset",
) -> OperationContext:
    """Create OperationContext for applying a preset."""
    return OperationContext(
        op=OperationType.PRESET_APPLY,
        actor=actor,
        scope=ScopeType.STEP,
        source=source,
        payload={"preset_name": preset_name},
    )


def opctx_for_calc_create(
    name: str,
    actor: ActorType = ActorType.SYSTEM,
    source: str = "Calculation.create",
) -> OperationContext:
    """Create OperationContext for creating a calculation."""
    return OperationContext(
        op=OperationType.CALC_CREATE,
        actor=actor,
        scope=ScopeType.CALC,
        source=source,
        payload={"name": name},
    )


def opctx_for_restore(
    from_run_ulid: str,
    actor: ActorType = ActorType.HUMAN,
    source: str = "Calculation.restore",
) -> OperationContext:
    """Create OperationContext for restoring from a snapshot."""
    return OperationContext(
        op=OperationType.RESTORE,
        actor=actor,
        scope=ScopeType.CALC,
        source=source,
        payload={"from_run_ulid": from_run_ulid},
    )


def opctx_system_internal(
    source: str,
    scope: ScopeType = ScopeType.PROJECT,
) -> OperationContext:
    """
    Create OperationContext for system-internal operations.

    Use this for operations that don't fit other categories,
    such as migrations, seeds, or internal bookkeeping.
    """
    return OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=scope,
        source=source,
        payload={"internal": True},
    )
