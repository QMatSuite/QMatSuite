"""
Trajectory analysis object.

The first fully-specified analysis object in the framework.
Supports MD, relax, and NEB trajectories.
"""

from quantumvitas.core.analysis.trajectory.model import (
    Frame,
    Trajectory,
)
from quantumvitas.core.analysis.trajectory.io import (
    save_trajectory,
    load_trajectory,
)
from quantumvitas.core.analysis.trajectory.utils import (
    wrap_positions,
)

__all__ = [
    "Frame",
    "Trajectory",
    "save_trajectory",
    "load_trajectory",
    "wrap_positions",
]

