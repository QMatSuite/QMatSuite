"""
Visual primitives for analysis objects.

DATA ONLY - no style fields. Styling is the viz layer's responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Series1D:
    """1D data series for line plots. DATA ONLY."""
    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x.tolist(),
            "y": self.y.tolist(),
            "x_label": self.x_label,
            "y_label": self.y_label,
            "x_unit": self.x_unit,
            "y_unit": self.y_unit,
            "name": self.name,
        }


@dataclass
class GeometryFrame:
    """
    Single frame of atomic geometry. DATA ONLY.
    
    Positions are UNWRAPPED Cartesian in Å.
    """
    positions: np.ndarray              # (N, 3) UNWRAPPED Å
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]       # Periodic boundary conditions
    
    # Per-atom data properties
    forces: Optional[np.ndarray] = None        # (N, 3) eV/Å
    velocities: Optional[np.ndarray] = None    # (N, 3) Å/fs
    
    @property
    def n_atoms(self) -> int:
        """Number of atoms in this frame."""
        return len(self.species)
    
    def __post_init__(self):
        """Validate cell/pbc consistency."""
        if any(self.pbc) and self.cell is None:
            raise ValueError("PBC requires cell to be provided")
        if self.cell is not None and self.cell.shape != (3, 3):
            raise ValueError(f"Cell must be (3, 3), got {self.cell.shape}")


@dataclass
class GeometryFrames:
    """Sequence of geometry frames for animation."""
    frames: List[GeometryFrame]
    time: Optional[np.ndarray] = None          # Frame timestamps in fs
    iteration: Optional[np.ndarray] = None     # Frame iteration numbers
    image_indices: Optional[np.ndarray] = None # For NEB


@dataclass
class Marker:
    """Annotation marker for plots. Position only, NO style."""
    position: float
    label: str
    axis: str = "x"  # "x" or "y"

