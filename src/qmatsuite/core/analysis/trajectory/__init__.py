"""
Trajectory analysis object.

The first fully-specified analysis object in the framework.
Supports MD, relax, and NEB trajectories.
"""

from qmatsuite.core.analysis.trajectory.model import (
    Frame,
    Trajectory,
)
from qmatsuite.core.analysis.trajectory.utils import (
    wrap_positions,
)

__all__ = [
    "Frame",
    "Trajectory",
    "wrap_positions",
]
