"""
Data models for visualization.

This module defines data structures for visualization data:
- BandStructureData: Electronic band structure
- DOSData: Density of states
- StructureData: Atomic structure for 3D visualization
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np


@dataclass
class BandStructureData:
    """Electronic band structure data."""
    kpoints: np.ndarray  # k-point coordinates
    energies: np.ndarray  # Band energies [n_bands, n_kpoints, n_spins]
    kpath_labels: Optional[List[Tuple[str, float]]] = None  # High-symmetry point labels
    fermi_energy: Optional[float] = None  # Fermi energy in eV
    unit: str = "eV"  # Energy unit
    
    def __post_init__(self):
        """Validate band structure data."""
        if len(self.energies.shape) < 2:
            raise ValueError("Energies must be at least 2D [n_bands, n_kpoints]")
        if self.kpoints.shape[0] != self.energies.shape[1]:
            raise ValueError("Number of k-points must match between kpoints and energies")


@dataclass
class DOSData:
    """Density of states data."""
    energies: np.ndarray  # Energy values
    dos: np.ndarray  # Total DOS [n_energies]
    pdos: Optional[Dict[str, np.ndarray]] = None  # Projected DOS by atom/element/orbital
    fermi_energy: Optional[float] = None  # Fermi energy in eV
    unit: str = "eV"  # Energy unit
    
    def __post_init__(self):
        """Validate DOS data."""
        if len(self.energies) != len(self.dos):
            raise ValueError("Energies and DOS arrays must have same length")


@dataclass
class StructureData:
    """Atomic structure data for visualization."""
    positions: np.ndarray  # Atomic positions [n_atoms, 3]
    symbols: List[str]  # Atomic symbols
    cell: Optional[np.ndarray] = None  # Unit cell [3, 3]
    forces: Optional[np.ndarray] = None  # Atomic forces [n_atoms, 3]
    charges: Optional[np.ndarray] = None  # Atomic charges [n_atoms]
    properties: Dict[str, Any] = field(default_factory=dict)  # Additional properties
    
    def __post_init__(self):
        """Validate structure data."""
        if len(self.positions) != len(self.symbols):
            raise ValueError("Number of positions must match number of symbols")
        if self.positions.shape[1] != 3:
            raise ValueError("Positions must be 3D")

