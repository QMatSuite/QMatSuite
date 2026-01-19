"""
Trajectory utilities.

Includes wrapping (called by viz, NOT by parser).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def wrap_positions(
    positions: np.ndarray,
    cell: np.ndarray,
    pbc: Tuple[bool, bool, bool],
) -> np.ndarray:
    """
    Wrap positions into cell.
    
    Called by visualization/analysis code when needed,
    NOT by parsers during parsing.
    
    Args:
        positions: (N, 3) Cartesian positions in Å
        cell: (3, 3) cell vectors (row vectors)
        pbc: Periodic boundary conditions
    
    Returns:
        (N, 3) wrapped positions
    """
    # Convert to fractional
    inv_cell = np.linalg.inv(cell)
    frac = positions @ inv_cell
    
    # Wrap in PBC directions
    for i in range(3):
        if pbc[i]:
            frac[:, i] = frac[:, i] % 1.0
    
    # Convert back to Cartesian
    return frac @ cell


def compute_rdf(
    positions: np.ndarray,
    cell: np.ndarray,
    species: list,
    r_max: float = 10.0,
    n_bins: int = 100,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute radial distribution function.
    
    Returns:
        (r_values, g_r)
    """
    # Placeholder implementation
    r = np.linspace(0, r_max, n_bins)
    g = np.ones(n_bins)  # Placeholder
    return r, g


def compute_msd(
    trajectory: "Trajectory",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute mean squared displacement.
    
    Returns:
        (time, msd)
    """
    # Placeholder implementation
    from quantumvitas.core.analysis.trajectory.model import Trajectory
    n_frames = len(trajectory)
    time = np.arange(n_frames)
    msd = np.zeros(n_frames)  # Placeholder
    return time, msd

