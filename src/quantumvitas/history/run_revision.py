"""
Run revision management.

A run revision captures the state of a calculation at the time of execution,
along with results and digests.

Storage layout:
    .history/runs/run_<ULID>/
    ├── run_revision.json    # Metadata + digests
    ├── snapshot.tar.zst     # Optional: structure + YAML snapshot
    └── pins/                # User-pinned analysis results
"""

from __future__ import annotations

import json
import logging
import os
import tarfile
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import ulid

from quantumvitas.history.digests import StepDigest, compute_step_digest, compute_run_digest

logger = logging.getLogger(__name__)


def _infer_engine_from_data(data: Dict[str, Any]) -> str:
    """
    Infer engine from run revision data.
    
    Tries:
    1. Explicit engine field
    2. Infer from step_types via registry
    3. Raise error if cannot determine
    """
    engine = data.get("engine")
    if engine:
        return engine
    
    # Try to infer from step_types
    step_types = data.get("step_types", [])
    if step_types:
        try:
            from quantumvitas.workflow.registry import get_registry
            registry = get_registry()
            # Try first step type
            first_step_type = step_types[0]
            spec = registry.get(first_step_type)
            if spec and spec.engine:
                return spec.engine
        except Exception:
            # If inference fails, continue to error
            pass
    
    # Cannot determine engine - raise error
    raise ValueError(
        f"Cannot determine engine for run revision. "
        f"Specify 'engine' field or ensure step_types are registered."
    )


class RunStatus:
    """Run status constants."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RUNNING = "running"


@dataclass
class RunRevision:
    """
    A run revision capturing execution state and results.
    
    Contains:
    - Metadata (IDs, timestamps, engine info)
    - Intention record (what was attempted)
    - Pseudo references (for reproducibility)
    - Step digests (computed results)
    - Run digest (overall summary)
    """
    ulid: str  # Run ULID
    project_ulid: str
    calc_ulid: str
    calc_name: Optional[str] = None
    
    # Timestamps
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    
    # Status
    status: str = RunStatus.RUNNING
    error_summary: Optional[str] = None
    
    # Engine info
    engine: str = "qe"
    engine_version: Optional[str] = None
    engine_path: Optional[str] = None
    
    # Intention record
    step_ulids: List[str] = field(default_factory=list)
    step_types: List[str] = field(default_factory=list)
    structure_ulid: Optional[str] = None
    structure_name: Optional[str] = None
    preset_options: Optional[Dict[str, str]] = None
    
    # Pseudo references
    pseudo_refs: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Working directory
    working_dir: Optional[str] = None
    
    # Digests (populated after run completes)
    step_digests: List[Dict[str, Any]] = field(default_factory=list)
    run_digest: Optional[Dict[str, Any]] = None
    
    # Snapshot info
    snapshot_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ulid": self.ulid,
            "project_ulid": self.project_ulid,
            "calc_ulid": self.calc_ulid,
            "calc_name": self.calc_name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "error_summary": self.error_summary,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "engine_path": self.engine_path,
            "step_ulids": self.step_ulids,
            "step_types": self.step_types,
            "structure_ulid": self.structure_ulid,
            "structure_name": self.structure_name,
            "preset_options": self.preset_options,
            "pseudo_refs": self.pseudo_refs,
            "working_dir": self.working_dir,
            "step_digests": self.step_digests,
            "run_digest": self.run_digest,
            "snapshot_path": self.snapshot_path,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunRevision":
        """Create from dictionary."""
        return cls(
            ulid=data.get("ulid", ""),
            project_ulid=data.get("project_ulid") or data.get("project_id", ""),
            calc_ulid=data.get("calc_ulid", ""),
            calc_name=data.get("calc_name"),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            status=data.get("status", RunStatus.RUNNING),
            error_summary=data.get("error_summary"),
            engine=_infer_engine_from_data(data),
            engine_version=data.get("engine_version"),
            engine_path=data.get("engine_path"),
            step_ulids=data.get("step_ulids", []),
            step_types=data.get("step_types", []),
            structure_ulid=data.get("structure_ulid"),
            structure_name=data.get("structure_name"),
            preset_options=data.get("preset_options"),
            pseudo_refs=data.get("pseudo_refs", {}),
            working_dir=data.get("working_dir"),
            step_digests=data.get("step_digests", []),
            run_digest=data.get("run_digest"),
            snapshot_path=data.get("snapshot_path"),
        )
    
    def save(self, run_dir: Path) -> None:
        """
        Save run revision to disk.
        
        Uses atomic write (temp file + rename) for crash safety.
        """
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        
        revision_file = run_dir / "run_revision.json"
        
        # Atomic write
        fd, tmp_path = tempfile.mkstemp(
            dir=run_dir,
            prefix="run_revision_",
            suffix=".json.tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
            os.rename(tmp_path, revision_file)
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def create_run_revision(
    project_root: Path,
    calc_ulid: str,
    calc_name: Optional[str] = None,
    step_ulids: Optional[List[str]] = None,
    step_types: Optional[List[str]] = None,
    structure_ulid: Optional[str] = None,
    structure_name: Optional[str] = None,
    engine: str = "qe",
    engine_version: Optional[str] = None,
    engine_path: Optional[str] = None,
    preset_options: Optional[Dict[str, str]] = None,
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
    working_dir: Optional[Path] = None,
    create_snapshot: bool = True,
    run_ulid: Optional[str] = None,
) -> RunRevision:
    """
    Create a new run revision at the start of a run.
    
    This should be called at the beginning of CalculationRunner.run().
    
    Args:
        project_root: Path to project root
        calc_ulid: Calculation ULID
        calc_name: Human-readable calculation name
        step_ulids: List of step ULIDs to execute
        step_types: List of step types
        structure_ulid: Structure ULID
        structure_name: Structure name
        engine: Engine name (default "qe")
        engine_version: Engine version string
        engine_path: Path to engine executable
        preset_options: Detected/applied preset options
        species_map: Pseudopotential mapping
        working_dir: Working directory path
        create_snapshot: Whether to create a snapshot tar
        run_ulid: External run ID to use (e.g., job_id from JobManager).
                If provided, this ID will be used instead of generating a new one,
                ensuring job_id == run_ulid identity.
        
    Returns:
        Initialized RunRevision
    """
    from quantumvitas.history.storage import ProjectHistory, generate_run_ulid
    
    project_root = Path(project_root).resolve()
    
    # Use external run_ulid if provided, otherwise generate one
    if run_ulid is None:
        run_ulid = generate_run_ulid()
    
    # Get project ID
    try:
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        project_ulid = config.get("project", {}).get("meta", {}).get("ulid", "")
    except Exception:
        project_ulid = ""
    
    # Create run directory
    history = ProjectHistory(project_root)
    run_dir = history.create_run_dir(run_ulid)
    
    # Build pseudo refs from species_map
    pseudo_refs = {}
    if species_map:
        for element, settings in species_map.items():
            pseudo_refs[element] = {
                "filename": settings.get("pseudopot", ""),
                "sha256": settings.get("pseudo_sha256", ""),
                "sha_family": settings.get("pseudo_sha_family", ""),
            }
    
    now = datetime.now(timezone.utc).isoformat()
    
    revision = RunRevision(
        ulid=run_ulid,
        project_ulid=project_ulid,
        calc_ulid=calc_ulid,
        calc_name=calc_name,
        created_at=now,
        started_at=now,
        status=RunStatus.RUNNING,
        engine=engine,
        engine_version=engine_version,
        engine_path=engine_path,
        step_ulids=step_ulids or [],
        step_types=step_types or [],
        structure_ulid=structure_ulid,
        structure_name=structure_name,
        preset_options=preset_options,
        pseudo_refs=pseudo_refs,
        working_dir=str(working_dir) if working_dir else None,
    )
    
    # Create snapshot
    if create_snapshot:
        try:
            snapshot_path = _create_snapshot(project_root, calc_ulid, run_dir)
            revision.snapshot_path = str(snapshot_path.relative_to(run_dir))
        except Exception as e:
            logger.warning(f"Failed to create run snapshot: {e}")
    
    # Save initial revision
    revision.save(run_dir)
    
    return revision


def _create_snapshot(
    project_root: Path,
    calc_ulid: str,
    run_dir: Path,
) -> Path:
    """
    Create a snapshot of structure + YAML tree at run start.
    
    Does NOT include pseudopotentials (they're referenced by sha).
    Uses zstd compression if available, otherwise gzip.
    """
    snapshot_path = run_dir / "snapshot.tar.zst"
    
    # Collect files to snapshot
    files_to_include: List[Path] = []
    
    # Project config
    project_config = project_root / "project.qv.yml"
    if project_config.exists():
        files_to_include.append(project_config)
    
    # Structures
    structures_dir = project_root / "structures"
    if structures_dir.exists():
        for f in structures_dir.glob("*.json"):
            files_to_include.append(f)
    
    # Calculation directory (find by ID or scan)
    calc_dir = None
    calculations_dir = project_root / "calculations"
    if calculations_dir.exists():
        for d in calculations_dir.iterdir():
            if not d.is_dir():
                continue
            calc_yaml = d / "calculation.yaml"
            if calc_yaml.exists():
                try:
                    import yaml
                    data = yaml.safe_load(calc_yaml.read_text()) or {}
                    meta_id = data.get("meta", {}).get("ulid", "")
                    if meta_id == calc_ulid:
                        calc_dir = d
                        break
                except Exception:
                    continue
    
    if calc_dir:
        # Include calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        if calc_yaml.exists():
            files_to_include.append(calc_yaml)
        
        # Include step files
        steps_dir = calc_dir / "steps"
        if steps_dir.exists():
            for f in steps_dir.glob("*.step.yaml"):
                files_to_include.append(f)
    
    # Create tar archive
    try:
        import zstandard as zstd
        
        with open(snapshot_path, "wb") as fh:
            cctx = zstd.ZstdCompressor(level=3)
            with cctx.stream_writer(fh) as compressor:
                with tarfile.open(fileobj=compressor, mode="w|") as tar:
                    for file_path in files_to_include:
                        arcname = str(file_path.relative_to(project_root))
                        tar.add(file_path, arcname=arcname)
    except ImportError:
        # Fall back to gzip
        snapshot_path = run_dir / "snapshot.tar.gz"
        with tarfile.open(snapshot_path, "w:gz") as tar:
            for file_path in files_to_include:
                arcname = str(file_path.relative_to(project_root))
                tar.add(file_path, arcname=arcname)
    
    return snapshot_path


def complete_run_revision(
    project_root: Path,
    run_ulid: str,
    status: str,
    step_results: List[Dict[str, Any]],
    working_dir: Path,
    error_summary: Optional[str] = None,
) -> RunRevision:
    """
    Complete a run revision after execution finishes.
    
    Computes digests and updates the revision file.
    
    Args:
        project_root: Path to project root
        run_ulid: Run ULID
        status: Final status ("success", "failed", "cancelled")
        step_results: List of step result summaries from runner
        working_dir: Working directory with outputs
        error_summary: Optional error description
        
    Returns:
        Updated RunRevision
    """
    from quantumvitas.history.storage import ProjectHistory
    
    history = ProjectHistory(project_root)
    run_dir = history.get_run_dir(run_ulid)
    
    if not run_dir:
        raise ValueError(f"Run directory not found for run_ulid: {run_ulid}")
    
    # Load existing revision
    revision = load_run_revision(run_dir)
    
    # Update timestamps
    finished_at = datetime.now(timezone.utc)
    revision.finished_at = finished_at.isoformat()
    revision.status = status
    revision.error_summary = error_summary
    
    # Compute step digests
    step_digests: List[StepDigest] = []
    
    for i, step_result in enumerate(step_results):
        step_ulid = step_result.get("step_ulid", "")
        step_type_spec = step_result.get("step_type_spec", "")

        step_status = step_result.get("status", "success")
        if hasattr(step_status, "value"):
            step_status = step_status.value

        step_name = step_result.get("step_name")
        error_msg = step_result.get("message") if step_status == "failed" else None

        digest = compute_step_digest(
            step_ulid=step_ulid,
            step_type_spec=step_type_spec,
            working_dir=working_dir,
            step_name=step_name,
            step_status=step_status,
            error_message=error_msg,
        )
        
        step_digests.append(digest)
    
    revision.step_digests = [d.to_dict() for d in step_digests]
    
    # Compute run digest
    started_at = datetime.fromisoformat(revision.started_at) if revision.started_at else finished_at
    
    revision.run_digest = compute_run_digest(
        run_ulid=run_ulid,
        calc_ulid=revision.calc_ulid,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        step_digests=step_digests,
        error_summary=error_summary,
    )
    
    # Save updated revision
    revision.save(run_dir)
    
    return revision


def load_run_revision(run_dir: Path) -> RunRevision:
    """
    Load a run revision from disk.
    
    Args:
        run_dir: Path to run directory
        
    Returns:
        RunRevision instance
        
    Raises:
        FileNotFoundError: If revision file not found
    """
    run_dir = Path(run_dir)
    revision_file = run_dir / "run_revision.json"
    
    if not revision_file.exists():
        raise FileNotFoundError(f"Run revision not found: {revision_file}")
    
    with open(revision_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return RunRevision.from_dict(data)

