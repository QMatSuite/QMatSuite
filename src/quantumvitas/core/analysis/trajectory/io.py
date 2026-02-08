"""
Trajectory serialization helpers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from quantumvitas.core.analysis.trajectory.model import Trajectory

_ANALYSIS_OBJECTS_DIR = "analysis_objects"
_TRAJECTORY_FILENAME = "trajectory.json"


def _trajectory_path(calc_dir: Path) -> Path:
    return calc_dir / _ANALYSIS_OBJECTS_DIR / _TRAJECTORY_FILENAME


def save_trajectory(
    trajectory: Trajectory,
    calc_dir: Path,
    cache_manager: Optional[Any] = None,
) -> Path:
    """
    Save trajectory JSON payload to a deterministic local path.
    """
    del cache_manager
    target_path = _trajectory_path(calc_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(trajectory.to_dict(), indent=2), encoding="utf-8")
    return target_path


def load_trajectory(
    calc_dir: Path,
    cache_manager: Optional[Any] = None,
) -> Optional[Trajectory]:
    """
    Load trajectory if present at the deterministic local path.
    """
    del cache_manager
    target_path = _trajectory_path(calc_dir)
    if not target_path.exists():
        return None

    data = json.loads(target_path.read_text(encoding="utf-8"))
    return Trajectory.from_dict(data)
