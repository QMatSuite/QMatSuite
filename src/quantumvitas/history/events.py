"""
History event types for project history.

Events are append-only and immutable. Each event has:
- id: ULID for the event
- timestamp: ISO 8601 timestamp
- event_type: discriminator for event kind
- project_id: optional project ULID
- calc_id: optional calculation ULID  
- step_id: optional step ULID
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import ulid


class EventType(str, Enum):
    """Event type discriminator."""
    BASELINE = "baseline"
    EDIT = "edit"
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    PIN_CREATED = "pin_created"


class EditOperation(str, Enum):
    """Semantic edit operation types."""
    SET = "set"          # Set a value at a path
    DELETE = "delete"    # Delete a value at a path
    CREATE = "create"    # Create a new resource (step, structure, etc.)
    REPLACE = "replace"  # Replace entire resource (large import)


@dataclass
class HistoryEvent:
    """
    Base class for all history events.
    
    All events are immutable once created.
    """
    id: str  # ULID for this event
    timestamp: str  # ISO 8601 format
    event_type: str
    project_id: Optional[str] = None
    calc_id: Optional[str] = None
    step_id: Optional[str] = None
    
    @classmethod
    def generate_id(cls) -> str:
        """Generate a new ULID for an event."""
        return str(ulid.new())
    
    @classmethod
    def now_timestamp(cls) -> str:
        """Get current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json_line(self) -> str:
        """Convert to JSON line for JSONL storage."""
        return json.dumps(self.to_dict(), separators=(",", ":"))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEvent":
        """
        Create event from dictionary.
        
        Dispatches to appropriate subclass based on event_type.
        """
        event_type = data.get("event_type")
        
        if event_type == EventType.BASELINE.value:
            return BaselineEvent.from_dict(data)
        elif event_type == EventType.EDIT.value:
            return EditEvent.from_dict(data)
        elif event_type == EventType.RUN_STARTED.value:
            return RunStartedEvent.from_dict(data)
        elif event_type == EventType.RUN_FINISHED.value:
            return RunFinishedEvent.from_dict(data)
        elif event_type == EventType.PIN_CREATED.value:
            return PinCreatedEvent.from_dict(data)
        else:
            # Generic event for forward compatibility
            return cls(**data)


@dataclass
class BaselineEvent(HistoryEvent):
    """
    Baseline event marking project history initialization.
    
    Stored once when history is first created for a project.
    Contains enough info to identify the initial state.
    """
    event_type: str = field(default=EventType.BASELINE.value)
    snapshot_path: Optional[str] = None  # Optional path to baseline snapshot
    structure_ulids: List[str] = field(default_factory=list)
    calculation_ulids: List[str] = field(default_factory=list)
    
    @classmethod
    def create(
        cls,
        project_ulid: str,
        structure_ulids: Optional[List[str]] = None,
        calculation_ulids: Optional[List[str]] = None,
        snapshot_path: Optional[str] = None,
    ) -> "BaselineEvent":
        """Create a new baseline event."""
        return cls(
            id=cls.generate_id(),
            timestamp=cls.now_timestamp(),
            project_ulid=project_ulid,
            structure_ulids=structure_ulids or [],
            calculation_ulids=calculation_ulids or [],
            snapshot_path=snapshot_path,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data.get("event_type", EventType.BASELINE.value),
            project_ulid=data.get("project_ulid", data.get("project_id")),
            calc_ulid=data.get("calc_ulid", data.get("calc_id")),
            step_ulid=data.get("step_ulid", data.get("step_id")),
            snapshot_path=data.get("snapshot_path"),
            structure_ulids=data.get("structure_ulids", data.get("structure_ids", [])),
            calculation_ulids=data.get("calculation_ulids", data.get("calculation_ids", [])),
        )


@dataclass
class EditChange:
    """
    A single edit change within an EditEvent.
    
    Represents one atomic operation (set/delete) on a path.
    """
    op: str  # EditOperation value
    path: str  # JSONPointer-like path (e.g., "/parameters/SYSTEM/ecutwfc")
    old_value: Optional[Any] = None  # Previous value (None for creates)
    new_value: Optional[Any] = None  # New value (None for deletes)
    value_hash: Optional[str] = None  # Hash for large values (instead of storing them)


@dataclass
class EditEvent(HistoryEvent):
    """
    Edit event recording semantic changes to project YAML/JSON.
    
    Contains structured diffs, not text diffs.
    """
    event_type: str = field(default=EventType.EDIT.value)
    doc_type: Optional[str] = None  # "step", "calc", "project", "structure"
    doc_path: Optional[str] = None  # Relative path to document
    changes: List[Dict[str, Any]] = field(default_factory=list)  # List of EditChange dicts
    actor: Optional[str] = None  # "gui", "cli", "daemon", "system"
    summary: Optional[str] = None  # Human-readable summary
    
    @classmethod
    def create(
        cls,
        project_id: Optional[str],
        calc_id: Optional[str],
        step_id: Optional[str],
        doc_type: str,
        doc_path: str,
        changes: List[EditChange],
        actor: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> "EditEvent":
        """Create a new edit event."""
        return cls(
            id=cls.generate_id(),
            timestamp=cls.now_timestamp(),
            project_id=project_id,
            calc_id=calc_id,
            step_id=step_id,
            doc_type=doc_type,
            doc_path=doc_path,
            changes=[asdict(c) if hasattr(c, "__dataclass_fields__") else c for c in changes],
            actor=actor,
            summary=summary,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data.get("event_type", EventType.EDIT.value),
            project_id=data.get("project_id"),
            calc_id=data.get("calc_id"),
            step_id=data.get("step_id"),
            doc_type=data.get("doc_type"),
            doc_path=data.get("doc_path"),
            changes=data.get("changes", []),
            actor=data.get("actor"),
            summary=data.get("summary"),
        )


@dataclass
class RunStartedEvent(HistoryEvent):
    """
    Event recording the start of an engine run.
    
    Created at the beginning of CalculationRunner.run().
    """
    event_type: str = field(default=EventType.RUN_STARTED.value)
    run_id: str = ""  # ULID for this run
    calc_name: Optional[str] = None
    step_ids: List[str] = field(default_factory=list)  # Steps to be executed
    step_types: List[str] = field(default_factory=list)  # Step types for display
    engine: Optional[str] = None
    structure_id: Optional[str] = None
    snapshot_path: Optional[str] = None  # Path to run snapshot
    
    @classmethod
    def create(
        cls,
        project_id: str,
        calc_id: str,
        run_id: str,
        calc_name: Optional[str] = None,
        step_ids: Optional[List[str]] = None,
        step_types: Optional[List[str]] = None,
        engine: Optional[str] = None,
        structure_id: Optional[str] = None,
        snapshot_path: Optional[str] = None,
    ) -> "RunStartedEvent":
        """Create a new run started event."""
        return cls(
            id=cls.generate_id(),
            timestamp=cls.now_timestamp(),
            project_id=project_id,
            calc_id=calc_id,
            run_id=run_id,
            calc_name=calc_name,
            step_ids=step_ids or [],
            step_types=step_types or [],
            engine=engine,
            structure_id=structure_id,
            snapshot_path=snapshot_path,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunStartedEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data.get("event_type", EventType.RUN_STARTED.value),
            project_id=data.get("project_id"),
            calc_id=data.get("calc_id"),
            step_id=data.get("step_id"),
            run_id=data.get("run_id", ""),
            calc_name=data.get("calc_name"),
            step_ids=data.get("step_ids", []),
            step_types=data.get("step_types", []),
            engine=data.get("engine"),
            structure_id=data.get("structure_id"),
            snapshot_path=data.get("snapshot_path"),
        )


@dataclass
class RunFinishedEvent(HistoryEvent):
    """
    Event recording the completion of an engine run.
    
    Created at the end of CalculationRunner.run(), after digests are computed.
    """
    event_type: str = field(default=EventType.RUN_FINISHED.value)
    run_id: str = ""  # Links to run revision
    status: str = ""  # "success", "failed", "cancelled"
    duration_seconds: Optional[float] = None
    step_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_summary: Optional[str] = None  # Brief error description if failed
    
    @classmethod
    def create(
        cls,
        project_id: str,
        calc_id: str,
        run_id: str,
        status: str,
        duration_seconds: Optional[float] = None,
        step_count: int = 0,
        success_count: int = 0,
        failure_count: int = 0,
        error_summary: Optional[str] = None,
    ) -> "RunFinishedEvent":
        """Create a new run finished event."""
        return cls(
            id=cls.generate_id(),
            timestamp=cls.now_timestamp(),
            project_id=project_id,
            calc_id=calc_id,
            run_id=run_id,
            status=status,
            duration_seconds=duration_seconds,
            step_count=step_count,
            success_count=success_count,
            failure_count=failure_count,
            error_summary=error_summary,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunFinishedEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data.get("event_type", EventType.RUN_FINISHED.value),
            project_id=data.get("project_id"),
            calc_id=data.get("calc_id"),
            step_id=data.get("step_id"),
            run_id=data.get("run_id", ""),
            status=data.get("status", ""),
            duration_seconds=data.get("duration_seconds"),
            step_count=data.get("step_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            error_summary=data.get("error_summary"),
        )


@dataclass
class PinCreatedEvent(HistoryEvent):
    """
    Event recording a pin-to-history action.
    
    Created when user pins analysis results to history.
    """
    event_type: str = field(default=EventType.PIN_CREATED.value)
    run_id: str = ""  # Run this pin belongs to
    analysis_kind: str = ""  # "bands", "dos", "scf_convergence", etc.
    pin_path: Optional[str] = None  # Path to pinned files
    
    @classmethod
    def create(
        cls,
        project_id: str,
        calc_id: str,
        step_id: str,
        run_id: str,
        analysis_kind: str,
        pin_path: Optional[str] = None,
    ) -> "PinCreatedEvent":
        """Create a new pin created event."""
        return cls(
            id=cls.generate_id(),
            timestamp=cls.now_timestamp(),
            project_id=project_id,
            calc_id=calc_id,
            step_id=step_id,
            run_id=run_id,
            analysis_kind=analysis_kind,
            pin_path=pin_path,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PinCreatedEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            event_type=data.get("event_type", EventType.PIN_CREATED.value),
            project_id=data.get("project_id"),
            calc_id=data.get("calc_id"),
            step_id=data.get("step_id"),
            run_id=data.get("run_id", ""),
            analysis_kind=data.get("analysis_kind", ""),
            pin_path=data.get("pin_path"),
        )


def compute_semantic_diff(
    before: Dict[str, Any],
    after: Dict[str, Any],
    base_path: str = "",
) -> List[EditChange]:
    """
    Compute semantic diff between two dictionaries.
    
    Returns list of EditChange objects describing the changes.
    Uses JSONPointer-like paths.
    
    Args:
        before: Previous state dictionary
        after: New state dictionary
        base_path: Base path prefix for nested calls
        
    Returns:
        List of EditChange objects
    """
    changes: List[EditChange] = []
    
    all_keys = set(before.keys()) | set(after.keys())
    
    for key in all_keys:
        path = f"{base_path}/{key}"
        old_val = before.get(key)
        new_val = after.get(key)
        
        if key not in before:
            # New key added
            changes.append(EditChange(
                op=EditOperation.SET.value,
                path=path,
                old_value=None,
                new_value=_maybe_hash_value(new_val),
            ))
        elif key not in after:
            # Key deleted
            changes.append(EditChange(
                op=EditOperation.DELETE.value,
                path=path,
                old_value=_maybe_hash_value(old_val),
                new_value=None,
            ))
        elif old_val != new_val:
            # Value changed
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                # Recurse into nested dicts
                nested_changes = compute_semantic_diff(old_val, new_val, path)
                changes.extend(nested_changes)
            else:
                changes.append(EditChange(
                    op=EditOperation.SET.value,
                    path=path,
                    old_value=_maybe_hash_value(old_val),
                    new_value=_maybe_hash_value(new_val),
                ))
    
    return changes


def _maybe_hash_value(value: Any, max_size: int = 500) -> Any:
    """
    For large values, return a hash instead of the full value.
    
    Preserves small scalars, lists, and dicts for readability.
    """
    if value is None:
        return None
    
    if isinstance(value, (bool, int, float)):
        return value
    
    if isinstance(value, str):
        if len(value) > max_size:
            import hashlib
            h = hashlib.sha256(value.encode()).hexdigest()[:16]
            return {"__hash__": h, "__len__": len(value)}
        return value
    
    if isinstance(value, (list, dict)):
        serialized = json.dumps(value, sort_keys=True, default=str)
        if len(serialized) > max_size:
            import hashlib
            h = hashlib.sha256(serialized.encode()).hexdigest()[:16]
            return {"__hash__": h, "__len__": len(serialized)}
        return value
    
    # For other types, convert to string
    str_val = str(value)
    if len(str_val) > max_size:
        import hashlib
        h = hashlib.sha256(str_val.encode()).hexdigest()[:16]
        return {"__hash__": h, "__type__": type(value).__name__}
    return str_val

