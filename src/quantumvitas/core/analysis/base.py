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
    step_ulids: List[str] = field(default_factory=list)
    gen_steps: List[str] = field(default_factory=list)
    engine_name: str = ""
    warnings: List[str] = field(default_factory=list)
    manifest_snapshot: Optional[Dict[str, Any]] = None
    
    # Parser info
    parser_name: str = ""
    parser_version: str = ""
    
    @classmethod
    def create(
        cls,
        object_type: str,
        source_files: List[SourceFileStat],
        *,
        run_ulid: Optional[str] = None,
        calc_ulid: Optional[str] = None,
        step_ulids: Optional[List[str]] = None,
        gen_steps: Optional[List[str]] = None,
        engine_name: str = "",
        parser_name: str = "",
        parser_version: str = "1.0",
        warnings: Optional[List[str]] = None,
        manifest_snapshot: Optional[Dict[str, Any]] = None,
    ) -> "AnalysisObjectMeta":
        """Factory method to create metadata."""
        return cls(
            schema_version="1.0",
            object_type=object_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_files=source_files,
            run_ulid=run_ulid,
            calc_ulid=calc_ulid,
            step_ulids=step_ulids or [],
            gen_steps=gen_steps or [],
            engine_name=engine_name,
            parser_name=parser_name,
            parser_version=parser_version,
            warnings=warnings or [],
            manifest_snapshot=manifest_snapshot,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "object_type": self.object_type,
            "created_at": self.created_at,
            "source_files": [sf.to_dict() for sf in self.source_files],
            "run_ulid": self.run_ulid,
            "calc_ulid": self.calc_ulid,
            "step_ulids": self.step_ulids,
            "gen_steps": self.gen_steps,
            "engine_name": self.engine_name,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "warnings": self.warnings,
            "manifest_snapshot": self.manifest_snapshot,
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
            step_ulids=data.get("step_ulids") or ([data["step_ulid"]] if data.get("step_ulid") else []),
            gen_steps=data.get("gen_steps", []),
            engine_name=data.get("engine_name", ""),
            parser_name=data.get("parser_name", ""),
            parser_version=data.get("parser_version", ""),
            warnings=data.get("warnings", []),
            manifest_snapshot=data.get("manifest_snapshot"),
        )


def check_staleness(meta: AnalysisObjectMeta, *, calc_dir: Path | None = None) -> bool:
    """
    Return True when any tracked source file differs from stored size/mtime.

    Relative source file paths are resolved against ``calc_dir``.
    If ``calc_dir`` is omitted and a relative path is present, the source is
    treated as stale because it cannot be validated.
    """
    for source_file in meta.source_files:
        source_path = Path(source_file.path)
        if not source_path.is_absolute():
            if calc_dir is None:
                return True
            source_path = Path(calc_dir) / source_path

        try:
            stat = source_path.stat()
        except OSError:
            return True

        if stat.st_size != source_file.size_bytes:
            return True
        if abs(stat.st_mtime - source_file.mtime) > 1e-6:
            return True

    return False
