"""
High-symmetry k-path generation for band structure calculations.

Uses pymatgen's symmetry analysis to automatically generate k-paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure


@dataclass
class KPathSegment:
    """A segment of the k-path between two high-symmetry points."""
    start_label: str
    end_label: str
    start_coords: Tuple[float, float, float]
    end_coords: Tuple[float, float, float]
    n_points: int = 20


@dataclass  
class KPathResult:
    """Result of k-path generation."""
    segments: List[KPathSegment]
    labels: List[str]  # Ordered list of all high-symmetry point labels
    coords: List[Tuple[float, float, float]]  # Corresponding coordinates
    lattice_type: str
    spacegroup_symbol: str
    spacegroup_number: int
    
    # Metadata for plotting (tick positions after bands.x)
    # These can be filled in after running bands.x
    tick_positions: Optional[List[float]] = None
    tick_labels: Optional[List[str]] = None
    
    def to_qe_kpoints_crystal_b(self) -> Dict[str, Any]:
        """
        Convert to QE K_POINTS card format (crystal_b).
        
        Returns dict with 'option' and 'data' for step spec cards.
        
        Format:
            K_POINTS crystal_b
            nks                    <- number of k-points (REQUIRED)
            k1 k2 k3 npts          <- k-point coordinates and weight
            ...
        """
        # Build k-point list
        kpoints = []
        
        for i, segment in enumerate(self.segments):
            if i == 0:
                # First point - convert numpy floats to Python floats
                kpoints.append([
                    round(float(segment.start_coords[0]), 8),
                    round(float(segment.start_coords[1]), 8), 
                    round(float(segment.start_coords[2]), 8),
                    int(segment.n_points),
                ])
            
            # End point of this segment
            kpoints.append([
                round(float(segment.end_coords[0]), 8),
                round(float(segment.end_coords[1]), 8),
                round(float(segment.end_coords[2]), 8),
                int(segment.n_points) if i < len(self.segments) - 1 else 0,  # Last point has 0
            ])
        
        # Prepend count as first row (required by QE crystal_b format)
        data = [[len(kpoints)]] + kpoints
        
        return {
            "option": "crystal_b",
            "data": data,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/YAML serialization."""
        # Helper to convert numpy types to Python types
        def to_python_floats(coords):
            return [float(c) for c in coords]
        
        return {
            "segments": [
                {
                    "start_label": seg.start_label,
                    "end_label": seg.end_label,
                    "start_coords": to_python_floats(seg.start_coords),
                    "end_coords": to_python_floats(seg.end_coords),
                    "n_points": seg.n_points,
                }
                for seg in self.segments
            ],
            "labels": self.labels,
            "coords": [to_python_floats(c) for c in self.coords],
            "lattice_type": self.lattice_type,
            "spacegroup_symbol": self.spacegroup_symbol,
            "spacegroup_number": int(self.spacegroup_number),
            "tick_positions": self.tick_positions,
            "tick_labels": self.tick_labels,
        }
    
    def path_string(self) -> str:
        """Return human-readable path string like 'Γ-X-M-Γ'."""
        if not self.labels:
            return ""
        return "-".join(self.labels)


def generate_kpath(
    structure: "PMGStructure",
    points_per_segment: int = 20,
    path_type: str = "hinuma",
) -> KPathResult:
    """
    Generate high-symmetry k-path for a structure.
    
    Args:
        structure: pymatgen Structure object
        points_per_segment: Number of k-points per path segment
        path_type: Path type - "hinuma" (pymatgen's HighSymmKpath, default),
                   "seekpath", or "latimer_munro"
        
    Returns:
        KPathResult with k-path information
    """
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    from pymatgen.symmetry.bandstructure import HighSymmKpath
    
    # Get spacegroup info
    sga = SpacegroupAnalyzer(structure)
    spg_symbol = sga.get_space_group_symbol()
    spg_number = sga.get_space_group_number()
    lattice_type = sga.get_lattice_type()
    
    # Generate k-path based on type - try different methods
    kpath = None
    kpath_data = None
    
    for ptype in [path_type, "hinuma", "setyawan_curtarolo"]:
        try:
            kpath = HighSymmKpath(structure, path_type=ptype)
            # Access kpath differently depending on pymatgen version
            if hasattr(kpath, 'kpath') and kpath.kpath is not None:
                kpath_data = kpath.kpath
                break
            elif hasattr(kpath, '_kpath') and kpath._kpath is not None:
                kpath_data = kpath._kpath
                break
        except Exception:
            continue
    
    if kpath_data is None:
        raise ValueError(
            f"Could not generate k-path for structure. Tried path types: {path_type}, hinuma, setyawan_curtarolo"
        )
    
    # Extract path information
    path = kpath_data.get("path", [])
    kpoints = kpath_data.get("kpoints", {})
    
    # Build segments
    segments: List[KPathSegment] = []
    all_labels: List[str] = []
    all_coords: List[Tuple[float, float, float]] = []
    
    for path_segment in path:
        for i in range(len(path_segment) - 1):
            start_label = path_segment[i]
            end_label = path_segment[i + 1]
            
            start_coords = tuple(kpoints.get(start_label, [0, 0, 0]))
            end_coords = tuple(kpoints.get(end_label, [0, 0, 0]))
            
            segments.append(KPathSegment(
                start_label=_format_label(start_label),
                end_label=_format_label(end_label),
                start_coords=start_coords,
                end_coords=end_coords,
                n_points=points_per_segment,
            ))
            
            # Track unique labels in order
            if not all_labels or all_labels[-1] != _format_label(start_label):
                all_labels.append(_format_label(start_label))
                all_coords.append(start_coords)
        
        # Add final label of this path segment
        if path_segment:
            final_label = _format_label(path_segment[-1])
            if not all_labels or all_labels[-1] != final_label:
                all_labels.append(final_label)
                all_coords.append(tuple(kpoints.get(path_segment[-1], [0, 0, 0])))
    
    return KPathResult(
        segments=segments,
        labels=all_labels,
        coords=all_coords,
        lattice_type=lattice_type,
        spacegroup_symbol=spg_symbol,
        spacegroup_number=spg_number,
    )


def _format_label(label: str) -> str:
    """Format k-point label for display (e.g., 'GAMMA' -> 'Γ')."""
    label_map = {
        "GAMMA": "Γ",
        "\\Gamma": "Γ",
        "Gamma": "Γ",
    }
    return label_map.get(label, label)


def kpath_to_qe_input_data(
    kpath: KPathResult,
    n_points_per_segment: Optional[int] = None,
) -> Tuple[str, List[List[Any]]]:
    """
    Convert KPathResult to QE K_POINTS card data.
    
    Args:
        kpath: KPathResult from generate_kpath
        n_points_per_segment: Override points per segment
        
    Returns:
        Tuple of (option, data) for K_POINTS card
    """
    card = kpath.to_qe_kpoints_crystal_b()
    
    if n_points_per_segment is not None:
        # Update n_points in data
        for row in card["data"]:
            if row[3] > 0:  # Don't update the last point (which has 0)
                row[3] = n_points_per_segment
    
    return card["option"], card["data"]


# Common paths for quick reference (can be used as fallback)
COMMON_PATHS = {
    "fcc": ["Γ", "X", "W", "K", "Γ", "L", "U", "W", "L", "K"],
    "bcc": ["Γ", "H", "N", "Γ", "P", "H"],
    "cubic": ["Γ", "X", "M", "Γ", "R", "X"],
    "hexagonal": ["Γ", "M", "K", "Γ", "A", "L", "H", "A"],
    "tetragonal": ["Γ", "X", "M", "Γ", "Z", "R", "A", "Z"],
}

