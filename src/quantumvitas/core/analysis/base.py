"""
Base classes for analysis objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SourceFileStat:
    """
    Stat of a source file for stale detection.
    
    Uses (size_bytes, mtime) only. No sha256 in v1.
    Paths are calc-relative (e.g., "raw/scf.out").
    """
    path: str                              # Calc-relative path
    size_bytes: int
    mtime: float                           # Unix timestamp
    
    @classmethod
    def from_path(cls, file_path: Path, calc_dir: Path) -> "SourceFileStat":
        """Create SourceFileStat from a file path."""
        stat = file_path.stat()
        # Make path calc-relative
        try:
            relative = file_path.relative_to(calc_dir)
        except ValueError:
            relative = file_path
        return cls(
            path=str(relative),
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceFileStat":
        return cls(
            path=data["path"],
            size_bytes=data["size_bytes"],
            mtime=data["mtime"],
        )


@dataclass
class AnalysisObjectMeta:
    """
    Unified metadata for all analysis objects.
    
    This is the SINGLE SOURCE OF TRUTH for analysis object metadata.
    Trajectory, DOS, Bands all use this same structure.
    """
    # Identity
    schema_version: str                    # e.g., "1.0"
    object_type: str                       # "trajectory" | "dos" | "bands" | "scf"
    
    # Timing
    created_at: str                        # ISO 8601
    
    # Source tracking (for stale detection)
    source_files: List[SourceFileStat] = field(default_factory=list)
    
    # Provenance (for UI explanation only, NOT for stale detection)
    run_ulid: Optional[str] = None
    calc_ulid: Optional[str] = None
    step_ulid: Optional[str] = None
    
    # Parser info
    parser_name: str = ""
    parser_version: str = ""
    
    @classmethod
    def create(
        cls,
        object_type: str,
        source_files: List[SourceFileStat],
        *,
        run_id: Optional[str] = None,
        calc_ulid: Optional[str] = None,
        step_ulid: Optional[str] = None,
        parser_name: str = "",
        parser_version: str = "1.0",
    ) -> "AnalysisObjectMeta":
        """Factory method to create metadata."""
        return cls(
            schema_version="1.0",
            object_type=object_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_files=source_files,
            run_ulid=run_id,
            calc_ulid=calc_ulid,
            step_ulid=step_ulid,
            parser_name=parser_name,
            parser_version=parser_version,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "object_type": self.object_type,
            "created_at": self.created_at,
            "source_files": [sf.to_dict() for sf in self.source_files],
            "run_ulid": self.run_ulid,
            "calc_ulid": self.calc_ulid,
            "step_ulid": self.step_ulid,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisObjectMeta":
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            object_type=data["object_type"],
            created_at=data["created_at"],
            source_files=[SourceFileStat.from_dict(sf) for sf in data.get("source_files", [])],
            run_ulid=data.get("run_ulid", data.get("run_id")),
            calc_ulid=data.get("calc_ulid"),
            step_ulid=data.get("step_ulid"),
            parser_name=data.get("parser_name", ""),
            parser_version=data.get("parser_version", ""),
        )

