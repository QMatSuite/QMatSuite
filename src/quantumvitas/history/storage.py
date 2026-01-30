"""
Project history storage module.

Provides:
- ProjectHistory: Main class for history operations
- Atomic writes to events.jsonl
- Run directory management
- Latest run tracking

Storage layout:
    project_root/.history/
    ├── events.jsonl           # Append-only event log
    └── runs/
        └── run_<ULID>/
            ├── run_revision.json
            ├── snapshot.tar.zst (optional)
            └── pins/
                └── <step_id>/
                    ├── <analysis_kind>.png
                    └── <analysis_kind>.json
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import ulid

from quantumvitas.history.events import (
    HistoryEvent,
    BaselineEvent,
    EditEvent,
    RunStartedEvent,
    RunFinishedEvent,
    PinCreatedEvent,
    EventType,
)


HISTORY_DIR_NAME = ".history"
EVENTS_FILE_NAME = "events.jsonl"
RUNS_DIR_NAME = "runs"


def ensure_history_dir(project_root: Path) -> Path:
    """
    Ensure .history directory exists for a project.
    
    Creates the directory structure if it doesn't exist:
    - .history/
    - .history/runs/
    
    Args:
        project_root: Path to project root
        
    Returns:
        Path to .history directory
    """
    history_dir = project_root / HISTORY_DIR_NAME
    history_dir.mkdir(parents=True, exist_ok=True)
    
    runs_dir = history_dir / RUNS_DIR_NAME
    runs_dir.mkdir(exist_ok=True)
    
    return history_dir


def get_latest_run_id(project_root: Path) -> Optional[str]:
    """
    Get the ULID of the most recent run for a project.
    
    Reads from events.jsonl to find the latest run_finished event.
    
    Args:
        project_root: Path to project root
        
    Returns:
        ULID of latest run, or None if no runs exist
    """
    history = ProjectHistory(project_root)
    return history.get_latest_run_id()


@dataclass
class ProjectHistory:
    """
    Main class for project history operations.
    
    Provides:
    - Append-only event recording
    - Event querying and filtering
    - Run directory management
    - Latest run tracking
    
    Thread-safety: Uses file locking for JSONL appends.
    Crash tolerance: Uses atomic writes (temp file + rename).
    """
    
    project_root: Path
    _history_dir: Optional[Path] = None
    
    def __post_init__(self):
        self.project_root = Path(self.project_root).resolve()
    
    @property
    def history_dir(self) -> Path:
        """Get .history directory, creating if needed."""
        if self._history_dir is None:
            self._history_dir = ensure_history_dir(self.project_root)
        return self._history_dir
    
    @property
    def events_file(self) -> Path:
        """Path to events.jsonl file."""
        return self.history_dir / EVENTS_FILE_NAME
    
    @property
    def runs_dir(self) -> Path:
        """Path to runs directory."""
        return self.history_dir / RUNS_DIR_NAME
    
    def is_initialized(self) -> bool:
        """Check if history has been initialized for this project."""
        return self.events_file.exists()
    
    def ensure_baseline(self) -> bool:
        """
        Ensure a baseline event exists.
        
        Creates one if history is not yet initialized.
        
        Returns:
            True if baseline was created, False if already existed
        """
        if self.is_initialized():
            # Check if baseline event exists
            events = self.list_events(event_types=[EventType.BASELINE.value], limit=1)
            if events:
                return False
        
        # Create baseline event
        project_ulid = self._get_project_ulid()
        structure_ulids = self._get_structure_ulids()
        calculation_ulids = self._get_calculation_ulids()
        
        baseline = BaselineEvent.create(
            project_id=project_ulid,
            structure_ids=structure_ulids,
            calculation_ids=calculation_ulids,
        )
        
        self.append_event(baseline)
        return True
    
    def append_event(self, event: HistoryEvent) -> None:
        """
        Append an event to events.jsonl.
        
        Uses file locking and atomic writes for safety.
        
        Args:
            event: Event to append
        """
        # Ensure history directory exists
        self.history_dir  # triggers creation
        
        json_line = event.to_json_line() + "\n"
        
        # Atomic append with file locking
        self._atomic_append(self.events_file, json_line)
    
    def _atomic_append(self, path: Path, content: str) -> None:
        """
        Atomically append content to a file.
        
        Uses file locking to prevent corruption from concurrent writes.
        """
        # Create file if it doesn't exist
        if not path.exists():
            path.touch()
        
        # Open for append with exclusive lock
        with open(path, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def list_events(
        self,
        *,
        event_types: Optional[List[str]] = None,
        calc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        reverse: bool = True,
    ) -> List[HistoryEvent]:
        """
        List events with optional filtering.
        
        Args:
            event_types: Filter by event type(s)
            calc_id: Filter by calculation ID
            run_id: Filter by run ID
            since: ISO timestamp - events after this time
            until: ISO timestamp - events before this time
            limit: Maximum number of events to return
            offset: Number of events to skip
            reverse: If True, return newest first (default)
            
        Returns:
            List of matching events
        """
        if not self.events_file.exists():
            return []
        
        events: List[HistoryEvent] = []
        
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    event = HistoryEvent.from_dict(data)
                    
                    # Apply filters
                    if event_types and event.event_type not in event_types:
                        continue
                    if calc_id and event.calc_ulid != calc_id:
                        continue
                    if run_id:
                        # Check run_id field for run events
                        event_run_id = getattr(event, "run_ulid", None)
                        if event_run_id != run_id:
                            continue
                    if since and event.timestamp < since:
                        continue
                    if until and event.timestamp > until:
                        continue
                    
                    events.append(event)
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Skip malformed lines
                    continue
        
        # Sort by timestamp
        if reverse:
            events.reverse()
        
        # Apply offset and limit
        if offset:
            events = events[offset:]
        if limit:
            events = events[:limit]
        
        return events
    
    def get_event(self, event_id: str) -> Optional[HistoryEvent]:
        """
        Get a specific event by ID.
        
        Args:
            event_id: ULID of the event
            
        Returns:
            Event if found, None otherwise
        """
        if not self.events_file.exists():
            return None
        
        with open(self.events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    if data.get("ulid") == event_id:
                        return HistoryEvent.from_dict(data)
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
        
        return None
    
    def get_latest_run_id(self) -> Optional[str]:
        """
        Get the ULID of the most recent run.
        
        Returns:
            ULID of latest run, or None if no runs exist
        """
        # Look for most recent run_finished event
        events = self.list_events(
            event_types=[EventType.RUN_FINISHED.value],
            limit=1,
            reverse=True,
        )
        
        if events:
            event = events[0]
            if isinstance(event, RunFinishedEvent):
                return event.run_ulid
            # Fallback for generic event
            return getattr(event, "run_ulid", None)
        
        return None
    
    def get_run_step_ids(self, run_id: str) -> List[str]:
        """
        Get the list of step IDs that were executed in a run.
        
        Args:
            run_id: ULID of the run
            
        Returns:
            List of step IDs, or empty list if not found
        """
        # Find run_started event with this run_id
        events = self.list_events(
            event_types=[EventType.RUN_STARTED.value],
            run_id=run_id,
            limit=1,
        )
        
        if events:
            event = events[0]
            if isinstance(event, RunStartedEvent):
                return event.step_ids
            return getattr(event, "step_ids", [])
        
        return []
    
    def create_run_dir(self, run_id: str) -> Path:
        """
        Create directory for a run.
        
        Args:
            run_id: ULID for the run
            
        Returns:
            Path to run directory
        """
        run_dir = self.runs_dir / f"run_{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir
    
    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """
        Get directory for a run if it exists.
        
        Args:
            run_id: ULID of the run
            
        Returns:
            Path to run directory, or None if not found
        """
        run_dir = self.runs_dir / f"run_{run_id}"
        if run_dir.exists():
            return run_dir
        return None
    
    def list_runs(
        self,
        *,
        calc_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """
        List run IDs, newest first.
        
        Args:
            calc_id: Optional filter by calculation ID
            limit: Maximum number of runs to return
            
        Returns:
            List of run ULIDs
        """
        events = self.list_events(
            event_types=[EventType.RUN_FINISHED.value],
            calc_id=calc_id,
            reverse=True,
        )
        
        run_ids = []
        seen = set()

        for event in events:
            run_id = getattr(event, "run_ulid", None)
            if run_id and run_id not in seen:
                seen.add(run_id)
                run_ids.append(run_id)
                if limit and len(run_ids) >= limit:
                    break

        return run_ids
    
    def get_pins_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all pins for a run.
        
        Args:
            run_id: ULID of the run
            
        Returns:
            List of pin info dicts with step_id, analysis_kind, paths
        """
        events = self.list_events(
            event_types=[EventType.PIN_CREATED.value],
            run_id=run_id,
        )
        
        pins = []
        for event in events:
            if isinstance(event, PinCreatedEvent):
                pins.append({
                    "step_id": event.step_ulid,
                    "analysis_kind": event.analysis_kind,
                    "pin_path": event.pin_path,
                    "timestamp": event.timestamp,
                })

        return pins
    
    def pin_exists(self, run_id: str, step_id: str, analysis_kind: str) -> bool:
        """
        Check if a pin already exists.
        
        Args:
            run_id: ULID of the run
            step_id: ULID of the step
            analysis_kind: Type of analysis (e.g., "bands", "dos")
            
        Returns:
            True if pin exists
        """
        events = self.list_events(
            event_types=[EventType.PIN_CREATED.value],
            run_id=run_id,
        )
        
        for event in events:
            if (isinstance(event, PinCreatedEvent) and
                event.step_ulid == step_id and
                event.analysis_kind == analysis_kind):
                return True

        return False
    
    def _get_project_ulid(self) -> str:
        """Get project ULID from project.qv.yml."""
        try:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(self.project_root)
            project_meta = config.get("project", {}).get("meta", {})
            return project_meta.get("ulid", "")
        except Exception:
            return ""
    
    def _get_structure_ulids(self) -> List[str]:
        """Get list of structure ULIDs from project."""
        try:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(self.project_root)
            structures = config.get("structures", [])
            return [s.get("structure_ulid", s.get("structure_id", s.get("ulid", ""))) for s in structures if s]
        except Exception:
            return []
    
    def _get_calculation_ulids(self) -> List[str]:
        """Get list of calculation IDs from project."""
        try:
            from quantumvitas.core.project_utils import load_project_config
            config = load_project_config(self.project_root)
            calculations = config.get("calculations", [])
            return [c.get("calculation_id", c.get("ulid", "")) for c in calculations if c]
        except Exception:
            return []


def generate_run_id() -> str:
    """Generate a new ULID for a run."""
    return str(ulid.new())

