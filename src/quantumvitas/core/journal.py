"""
Journal: Append-only change tracking for YAML documents.

This module provides traceability for all YAML mutations:
- Records before/after snapshots at save boundary
- ULID-based identification of changes and targets
- Append-only JSONL storage for simplicity and reliability

Design decisions:
- Storage: JSONL (append-only, human-readable, easy to debug)
- Hook point: yaml_io.save_yaml_doc() only
- No undo/redo yet - recording and listing only
- Deep copies prevent reference leakage into journal

Per docs/journal_design.md:
- Journal records all YAML mutations (project/calc/step)
- Business logic does NOT compute diffs
- Journal hooks only at Doc boundary
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Literal, Any
import copy

import ulid


DocType = Literal["step", "calc", "project", "unknown"]

# Default journal file location (in user's data directory)
_DEFAULT_JOURNAL_DIR = Path.home() / ".quantumvitas" / "journal"


def _deep_copy(value: Any) -> Any:
    """Deep copy a value, handling common types efficiently."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return copy.deepcopy(value)


@dataclass
class JournalEntry:
    """
    A single journal entry recording a YAML document change.
    
    Attributes:
        id: ULID for this entry (unique identifier)
        target_ulid: ULID of the target document (from meta.id)
        doc_type: Type of document ("step", "calc", "project")
        timestamp: When the change occurred (UTC)
        before: Deep copy snapshot before change
        after: Deep copy snapshot after change
        summary: Human-readable short description
        path: Optional file path (for debugging)
    """
    id: str
    target_ulid: str
    doc_type: DocType
    timestamp: str  # ISO 8601 format
    before: dict
    after: dict
    summary: str
    path: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        target_ulid: str,
        doc_type: DocType,
        before: dict,
        after: dict,
        summary: str,
        path: Optional[Path] = None,
    ) -> "JournalEntry":
        """
        Create a new journal entry.
        
        Deep copies before/after to prevent reference leakage.
        """
        return cls(
            id=str(ulid.new()),
            target_ulid=target_ulid,
            doc_type=doc_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            before=_deep_copy(before),
            after=_deep_copy(after),
            summary=summary,
            path=str(path) if path else None,
        )
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "JournalEntry":
        """Create from dict (JSON deserialization)."""
        return cls(**data)


class Journal:
    """
    Append-only journal for tracking YAML document changes.
    
    Storage format: JSONL (one JSON object per line)
    Location: ~/.quantumvitas/journal/journal.jsonl
    
    Thread-safety: Append-only writes are generally safe,
    but concurrent reads during writes may see partial lines.
    For production, consider file locking or SQLite.
    """
    
    def __init__(self, journal_dir: Optional[Path] = None, enabled: bool = True):
        """
        Initialize journal.
        
        Args:
            journal_dir: Directory for journal files (default: ~/.quantumvitas/journal)
            enabled: If False, no entries are recorded (useful for tests)
        """
        self._journal_dir = Path(journal_dir) if journal_dir else _DEFAULT_JOURNAL_DIR
        self._enabled = enabled
        self._journal_file: Optional[Path] = None
    
    @property
    def journal_file(self) -> Path:
        """Path to the journal file."""
        if self._journal_file is None:
            self._journal_dir.mkdir(parents=True, exist_ok=True)
            self._journal_file = self._journal_dir / "journal.jsonl"
        return self._journal_file
    
    @property
    def enabled(self) -> bool:
        """Whether journaling is enabled."""
        return self._enabled
    
    def enable(self) -> None:
        """Enable journaling."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable journaling."""
        self._enabled = False
    
    def record_change(self, entry: JournalEntry) -> None:
        """
        Record a change to the journal.
        
        Appends a single JSON line to the journal file.
        No-op if journal is disabled.
        
        Args:
            entry: The journal entry to record
        """
        if not self._enabled:
            return
        
        line = json.dumps(entry.to_dict(), separators=(",", ":")) + "\n"
        
        # Append-only write
        with open(self.journal_file, "a", encoding="utf-8") as f:
            f.write(line)
    
    def list_entries(
        self,
        target_ulid: Optional[str] = None,
        doc_type: Optional[DocType] = None,
        limit: Optional[int] = None,
    ) -> list[JournalEntry]:
        """
        List journal entries.
        
        Args:
            target_ulid: Filter by target document ULID
            doc_type: Filter by document type
            limit: Maximum number of entries to return (most recent first)
            
        Returns:
            List of matching journal entries, most recent first
        """
        if not self.journal_file.exists():
            return []
        
        entries: list[JournalEntry] = []
        
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    entry = JournalEntry.from_dict(data)
                    
                    # Apply filters
                    if target_ulid and entry.target_ulid != target_ulid:
                        continue
                    if doc_type and entry.doc_type != doc_type:
                        continue
                    
                    entries.append(entry)
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Skip malformed lines
                    continue
        
        # Most recent first
        entries.reverse()
        
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """
        Get a specific journal entry by ID.
        
        Args:
            entry_id: ULID of the entry
            
        Returns:
            JournalEntry if found, None otherwise
        """
        if not self.journal_file.exists():
            return None
        
        with open(self.journal_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    if data.get("id") == entry_id:
                        return JournalEntry.from_dict(data)
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
        
        return None
    
    def clear(self) -> None:
        """
        Clear all journal entries.
        
        WARNING: This is destructive. Only use for testing.
        """
        if self.journal_file.exists():
            self.journal_file.unlink()
        self._journal_file = None


# =============================================================================
# Global Journal Instance
# =============================================================================

# Global journal instance (can be replaced for testing)
_journal: Optional[Journal] = None


def get_journal() -> Journal:
    """Get the global journal instance."""
    global _journal
    if _journal is None:
        _journal = Journal()
    return _journal


def set_journal(journal: Journal) -> None:
    """Set the global journal instance (for testing)."""
    global _journal
    _journal = journal


def reset_journal() -> None:
    """Reset to default journal (for testing cleanup)."""
    global _journal
    _journal = None


# =============================================================================
# Helper Functions
# =============================================================================


def infer_doc_type(data: dict) -> DocType:
    """
    Infer document type from data structure.
    
    Uses heuristics based on known document fields.
    """
    if not isinstance(data, dict):
        return "unknown"
    
    # Check meta.kind if available
    meta = data.get("meta", {})
    if isinstance(meta, dict):
        kind = meta.get("kind", "")
        if kind == "step":
            return "step"
        if kind == "calculation":
            return "calc"
        if kind == "project":
            return "project"
    
    # Heuristics based on keys
    if "step_type" in data or "parameters" in data:
        return "step"
    if "calculations" in data or "project" in data:
        return "project"
    if "steps" in data or "parent_calculation_id" in data:
        return "calc"
    
    return "unknown"


def extract_target_ulid(data: dict) -> str:
    """
    Extract target ULID from document data.
    
    Looks for meta.id, falls back to generating a new ULID.
    """
    meta = data.get("meta", {})
    if isinstance(meta, dict):
        id_val = meta.get("id")
        if id_val and isinstance(id_val, str):
            return id_val
    
    # Fallback: generate a new ID (shouldn't happen normally)
    return str(ulid.new())


def generate_summary(doc_type: DocType, before: dict, after: dict) -> str:
    """
    Generate a human-readable summary of changes.
    
    Simple heuristic: count added/removed/modified keys at top level.
    """
    before_keys = set(before.keys()) if isinstance(before, dict) else set()
    after_keys = set(after.keys()) if isinstance(after, dict) else set()
    
    added = after_keys - before_keys
    removed = before_keys - after_keys
    
    # Check for modifications in shared keys
    common = before_keys & after_keys
    modified = sum(1 for k in common if before.get(k) != after.get(k))
    
    parts = []
    if added:
        parts.append(f"+{len(added)}")
    if removed:
        parts.append(f"-{len(removed)}")
    if modified:
        parts.append(f"~{modified}")
    
    if not parts:
        return f"Saved {doc_type}"
    
    return f"Saved {doc_type} ({', '.join(parts)} keys)"

