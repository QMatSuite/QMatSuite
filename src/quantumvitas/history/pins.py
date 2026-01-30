"""
Pin-to-History functionality.

Allows users to persist analysis results (plots, data) to history.

Invariants:
1. Pins are only allowed for steps included in the MOST RECENT run.
2. De-duplicated: (run_id, step_id, analysis_kind) is unique.
3. Backend writes files; UI must not write directly.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.history.storage import ProjectHistory
from quantumvitas.history.events import PinCreatedEvent

logger = logging.getLogger(__name__)


class PinError(Exception):
    """Error during pin operation."""
    pass


@dataclass
class PinResult:
    """Result of a pin operation."""
    success: bool
    run_ulid: str
    step_ulid: str
    analysis_kind: str
    png_path: Optional[str] = None
    json_path: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "run_ulid": self.run_ulid,
            "step_ulid": self.step_ulid,
            "analysis_kind": self.analysis_kind,
            "png_path": self.png_path,
            "json_path": self.json_path,
            "error": self.error,
        }


def pin_analysis_to_history(
    project_root: Path,
    run_id: str,
    step_id: str,
    analysis_kind: str,
    *,
    png_data: Optional[bytes] = None,
    json_payload: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> PinResult:
    """
    Pin analysis results to history.
    
    This is the main backend API for pinning. The UI must call this;
    it must not write files directly.
    
    Args:
        project_root: Path to project root
        run_id: ULID of the run
        step_id: ULID of the step
        analysis_kind: Type of analysis (e.g., "bands", "dos", "scf_convergence")
        png_data: Optional PNG image data
        json_payload: Optional JSON data payload
        force: If True, allow pinning to non-latest run (for testing)
        
    Returns:
        PinResult with paths to created files
        
    Raises:
        PinError: If pin is not allowed (not latest run, etc.)
    """
    project_root = Path(project_root).resolve()
    history = ProjectHistory(project_root)
    
    # Check 1: Run must exist
    run_dir = history.get_run_dir(run_id)
    if not run_dir:
        raise PinError(f"Run not found: {run_id}")
    
    # Check 2: Only allow pins for latest run (unless force=True)
    if not force:
        latest_run_id = history.get_latest_run_id()
        if latest_run_id and latest_run_id != run_id:
            raise PinError(
                f"Pins are only allowed for the most recent run. "
                f"Latest run is {latest_run_id}, but trying to pin to {run_id}."
            )
    
    # Check 3: Step must be part of the run
    run_step_ids = history.get_run_step_ids(run_id)
    if run_step_ids and step_id not in run_step_ids:
        raise PinError(
            f"Step {step_id} was not part of run {run_id}. "
            f"Run steps: {run_step_ids}"
        )
    
    # Check 4: De-duplicate - skip if pin already exists
    if history.pin_exists(run_id, step_id, analysis_kind):
        logger.info(f"Pin already exists for ({run_id}, {step_id}, {analysis_kind})")
        # Return success without creating duplicate
        existing_pins = history.get_pins_for_run(run_id)
        for pin in existing_pins:
            if pin["step_id"] == step_id and pin["analysis_kind"] == analysis_kind:
                return PinResult(
                    success=True,
                    run_ulid=run_id,
                    step_ulid=step_id,
                    analysis_kind=analysis_kind,
                    png_path=pin.get("pin_path"),
                    error="Pin already exists (de-duplicated)",
                )
        # Shouldn't reach here, but return success anyway
        return PinResult(
            success=True,
            run_ulid=run_id,
            step_ulid=step_id,
            analysis_kind=analysis_kind,
            error="Pin already exists",
        )
    
    # Create pin directory
    pins_dir = run_dir / "pins" / step_id
    pins_dir.mkdir(parents=True, exist_ok=True)
    
    png_path = None
    json_path = None
    
    # Save PNG data
    if png_data:
        png_file = pins_dir / f"{analysis_kind}.png"
        _atomic_write_bytes(png_file, png_data)
        png_path = str(png_file.relative_to(run_dir))
    
    # Save JSON payload
    if json_payload:
        json_file = pins_dir / f"{analysis_kind}.json"
        # Downsample if needed
        downsampled = _downsample_payload(json_payload)
        _atomic_write_json(json_file, downsampled)
        json_path = str(json_file.relative_to(run_dir))
    
    # Get project ID
    try:
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        project_id = config.get("project", {}).get("meta", {}).get("ulid", "")
    except Exception:
        project_id = ""
    
    # Get calc_id from run revision
    calc_id = ""
    try:
        from quantumvitas.history.run_revision import load_run_revision
        revision = load_run_revision(run_dir)
        calc_id = revision.calc_id
    except Exception:
        pass
    
    # Record pin event
    event = PinCreatedEvent.create(
        project_id=project_id,
        calc_id=calc_id,
        step_id=step_id,
        run_id=run_id,
        analysis_kind=analysis_kind,
        pin_path=png_path or json_path,
    )
    history.append_event(event)
    
    return PinResult(
        success=True,
        run_ulid=run_id,
        step_ulid=step_id,
        analysis_kind=analysis_kind,
        png_path=png_path,
        json_path=json_path,
    )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write bytes to file."""
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.stem + "_",
        suffix=path.suffix + ".tmp",
    )
    try:
        os.write(fd, data)
        os.close(fd)
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomically write JSON to file."""
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.stem + "_",
        suffix=".json.tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=_json_default)
        os.rename(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _json_default(obj):
    """Default JSON serializer for numpy types."""
    import numpy as np
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _downsample_payload(payload: Dict[str, Any], max_points: int = 2000) -> Dict[str, Any]:
    """
    Downsample arrays in payload to reduce storage size.
    
    Applies adaptive sampling to arrays with more than max_points elements.
    """
    import numpy as np
    
    result = {}
    
    for key, value in payload.items():
        if isinstance(value, (list, np.ndarray)):
            arr = np.array(value) if isinstance(value, list) else value
            
            if arr.ndim == 1 and len(arr) > max_points:
                # Uniform downsampling
                indices = np.linspace(0, len(arr) - 1, max_points, dtype=int)
                result[key] = arr[indices].tolist()
            elif arr.ndim == 2 and arr.shape[1] > max_points:
                # For 2D arrays (e.g., bands), sample along k-points axis
                indices = np.linspace(0, arr.shape[1] - 1, max_points, dtype=int)
                result[key] = arr[:, indices].tolist()
            else:
                result[key] = arr.tolist() if isinstance(arr, np.ndarray) else value
        elif isinstance(value, dict):
            result[key] = _downsample_payload(value, max_points)
        else:
            result[key] = value
    
    return result


def get_pin_data(
    project_root: Path,
    run_id: str,
    step_id: str,
    analysis_kind: str,
) -> Dict[str, Any]:
    """
    Get pinned data for a step analysis.
    
    Args:
        project_root: Path to project root
        run_id: ULID of the run
        step_id: ULID of the step
        analysis_kind: Type of analysis
        
    Returns:
        Dict with 'png_path', 'json_path', 'json_data' if available
    """
    history = ProjectHistory(project_root)
    run_dir = history.get_run_dir(run_id)
    
    if not run_dir:
        return {"error": f"Run not found: {run_id}"}
    
    pins_dir = run_dir / "pins" / step_id
    
    result: Dict[str, Any] = {
        "run_id": run_id,
        "step_id": step_id,
        "analysis_kind": analysis_kind,
    }
    
    png_file = pins_dir / f"{analysis_kind}.png"
    if png_file.exists():
        result["png_path"] = str(png_file)
    
    json_file = pins_dir / f"{analysis_kind}.json"
    if json_file.exists():
        result["json_path"] = str(json_file)
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                result["json_data"] = json.load(f)
        except Exception as e:
            result["json_error"] = str(e)
    
    return result


def list_pins_for_step(
    project_root: Path,
    run_id: str,
    step_id: str,
) -> List[str]:
    """
    List analysis kinds that have been pinned for a step.
    
    Args:
        project_root: Path to project root
        run_id: ULID of the run
        step_id: ULID of the step
        
    Returns:
        List of analysis_kind values
    """
    history = ProjectHistory(project_root)
    run_dir = history.get_run_dir(run_id)
    
    if not run_dir:
        return []
    
    pins_dir = run_dir / "pins" / step_id
    
    if not pins_dir.exists():
        return []
    
    kinds = set()
    for f in pins_dir.iterdir():
        if f.suffix in (".png", ".json"):
            kinds.add(f.stem)
    
    return sorted(kinds)


def can_pin_to_run(project_root: Path, run_id: str, step_id: str) -> Dict[str, Any]:
    """
    Check if pinning is allowed for a specific run and step.
    
    Args:
        project_root: Path to project root
        run_id: ULID of the run to check
        step_id: ULID of the step
        
    Returns:
        Dict with 'allowed' bool and 'reason' if not allowed
    """
    history = ProjectHistory(project_root)
    
    # Check run exists
    run_dir = history.get_run_dir(run_id)
    if not run_dir:
        return {"allowed": False, "reason": f"Run not found: {run_id}"}
    
    # Check if this is the latest run
    latest_run_id = history.get_latest_run_id()
    if latest_run_id and latest_run_id != run_id:
        return {
            "allowed": False,
            "reason": f"Only the latest run can be pinned. Latest: {latest_run_id}",
            "latest_run_id": latest_run_id,
        }
    
    # Check if step was part of the run
    run_step_ids = history.get_run_step_ids(run_id)
    if run_step_ids and step_id not in run_step_ids:
        return {
            "allowed": False,
            "reason": f"Step {step_id} was not part of this run",
            "run_step_ids": run_step_ids,
        }
    
    return {"allowed": True}

