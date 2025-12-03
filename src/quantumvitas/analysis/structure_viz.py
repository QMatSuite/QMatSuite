"""
3D crystal structure visualization using matplotlib.

This module provides ball-and-stick visualization of crystal structures
with support for supercells and boundary repetition options.

Features:
- Ball-and-stick representation (atoms as spheres, bonds as lines)
- Supercell expansion
- Periodic boundary visualization
- Element-based coloring using CPK-like scheme
- Covalent radius-based bond detection

Functions are reusable from CLI, GUI, or notebooks.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # Headless-safe backend

import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pymatgen.core import Structure as PMGStructure
from pymatgen.core.periodic_table import Element


# =============================================================================
# CPK-like element colors (simplified palette)
# =============================================================================

ELEMENT_COLORS: Dict[str, str] = {
    # Common elements with distinctive colors
    "H": "#FFFFFF",   # White
    "C": "#333333",   # Dark gray
    "N": "#3050F8",   # Blue
    "O": "#FF0D0D",   # Red
    "F": "#90E050",   # Light green
    "S": "#FFFF30",   # Yellow
    "P": "#FF8000",   # Orange
    "Cl": "#1FF01F",  # Green
    "Br": "#A62929",  # Dark red
    "I": "#940094",   # Purple
    # Metals
    "Na": "#AB5CF2",  # Violet
    "K": "#8F40D4",   # Purple
    "Mg": "#8AFF00",  # Light green
    "Ca": "#3DFF00",  # Lime
    "Fe": "#E06633",  # Brown-orange
    "Cu": "#C88033",  # Copper
    "Zn": "#7D80B0",  # Gray-blue
    "Ag": "#C0C0C0",  # Silver
    "Au": "#FFD123",  # Gold
    "Al": "#BFA6A6",  # Light gray
    # Semiconductors
    "Si": "#F0C8A0",  # Tan/beige
    "Ge": "#668F8F",  # Gray-green
    "Ga": "#C28F8F",  # Pink-gray
    "As": "#BD80E3",  # Purple
    # Transition metals
    "Ti": "#BFC2C7",  # Silver
    "V": "#A6A6AB",   # Gray
    "Cr": "#8A99C7",  # Blue-gray
    "Mn": "#9C7AC7",  # Purple-gray
    "Co": "#F090A0",  # Pink
    "Ni": "#50D050",  # Green
    # Lanthanides/actinides (generic)
    "La": "#70D4FF",  # Light blue
    "U": "#008FFF",   # Blue
    # Default
    "_default": "#FF1493",  # Deep pink for unknown elements
}


def get_element_color(symbol: str) -> str:
    """Get color for an element symbol."""
    return ELEMENT_COLORS.get(symbol, ELEMENT_COLORS["_default"])


# Covalent radii in Angstroms (from Cordero et al., Dalton Trans. 2008)
# Used for bond detection
COVALENT_RADII: Dict[str, float] = {
    "H": 0.31, "He": 0.28,
    "Li": 1.28, "Be": 0.96, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "Ne": 0.58,
    "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05, "Cl": 1.02, "Ar": 1.06,
    "K": 2.03, "Ca": 1.76, "Sc": 1.70, "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39, "Fe": 1.32,
    "Co": 1.26, "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Ga": 1.22, "Ge": 1.20, "As": 1.19, "Se": 1.20,
    "Br": 1.20, "Kr": 1.16,
    "Rb": 2.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64, "Mo": 1.54, "Tc": 1.47, "Ru": 1.46,
    "Rh": 1.42, "Pd": 1.39, "Ag": 1.45, "Cd": 1.44, "In": 1.42, "Sn": 1.39, "Sb": 1.39, "Te": 1.38,
    "I": 1.39, "Xe": 1.40,
    "Cs": 2.44, "Ba": 2.15, "La": 2.07, "Ce": 2.04, "Pr": 2.03, "Nd": 2.01, "Pm": 1.99, "Sm": 1.98,
    "Eu": 1.98, "Gd": 1.96, "Tb": 1.94, "Dy": 1.92, "Ho": 1.92, "Er": 1.89, "Tm": 1.90, "Yb": 1.87,
    "Lu": 1.87, "Hf": 1.75, "Ta": 1.70, "W": 1.62, "Re": 1.51, "Os": 1.44, "Ir": 1.41, "Pt": 1.36,
    "Au": 1.36, "Hg": 1.32, "Tl": 1.45, "Pb": 1.46, "Bi": 1.48, "Po": 1.40, "At": 1.50, "Rn": 1.50,
    "Fr": 2.60, "Ra": 2.21, "Ac": 2.15, "Th": 2.06, "Pa": 2.00, "U": 1.96, "Np": 1.90, "Pu": 1.87,
}


def get_element_radius(symbol: str) -> float:
    """
    Get covalent radius for an element in Angstroms.
    
    Uses built-in covalent radii table, with fallback to pymatgen's atomic_radius.
    """
    # First check our built-in covalent radii table
    if symbol in COVALENT_RADII:
        return COVALENT_RADII[symbol]
    
    # Fallback to pymatgen's atomic_radius
    try:
        el = Element(symbol)
        if hasattr(el, 'atomic_radius') and el.atomic_radius is not None:
            return float(el.atomic_radius)
    except (ValueError, KeyError, AttributeError):
        pass
    
    return 1.0  # Default radius


# =============================================================================
# Bond detection
# =============================================================================

@dataclass
class Bond:
    """Represents a bond between two atoms."""
    idx1: int  # Index of first atom
    idx2: int  # Index of second atom
    coord1: np.ndarray  # Coordinates of first atom
    coord2: np.ndarray  # Coordinates of second atom
    distance: float


def _is_coord_in_cell(
    coord: np.ndarray,
    lattice,
    tolerance: float = 0.1,
) -> bool:
    """Check if Cartesian coordinate is within the cell (with tolerance)."""
    frac = lattice.get_fractional_coords(coord)
    return all(-tolerance <= f <= 1.0 + tolerance for f in frac)


def detect_bonds(
    structure: PMGStructure,
    tolerance: float = 0.3,
    max_cutoff: float = 3.5,
    include_periodic_images: bool = True,
) -> List[Bond]:
    """
    Detect bonds in a structure based on covalent radii.
    
    A bond is detected between atoms i and j if:
        distance(i, j) < R_i + R_j + tolerance
    
    Args:
        structure: pymatgen Structure object
        tolerance: Extra tolerance for bond detection (Å)
        max_cutoff: Maximum distance to consider (Å)
        include_periodic_images: If True, include bonds to periodic images
            outside the cell. If False, only include bonds where the neighbor
            is within the cell boundaries.
        
    Returns:
        List of Bond objects
    """
    bonds: List[Bond] = []
    # Track seen bonds by rounded endpoint coordinates to avoid duplicates
    seen_bonds: Set[Tuple[Tuple[float, ...], Tuple[float, ...]]] = set()
    
    n_sites = len(structure)
    lattice = structure.lattice
    
    for i in range(n_sites):
        site_i = structure[i]
        elem_i = site_i.specie.symbol
        radius_i = get_element_radius(elem_i)
        coord_i = np.array(site_i.coords)
        
        # Get neighbors within max_cutoff (includes periodic images)
        neighbors = structure.get_neighbors(site_i, r=max_cutoff)
        
        for neighbor in neighbors:
            coord_j = np.array(neighbor.coords)  # Actual neighbor position (may be periodic image)
            
            # Skip if neighbor is outside cell and we don't want periodic images
            if not include_periodic_images:
                if not _is_coord_in_cell(coord_j, lattice):
                    continue
            
            elem_j = neighbor.specie.symbol
            radius_j = get_element_radius(elem_j)
            
            # Check bond criterion
            max_bond_dist = radius_i + radius_j + tolerance
            
            if neighbor.nn_distance <= max_bond_dist:
                # Create a canonical key for this bond based on coordinates
                # Round to 3 decimal places to handle floating point precision
                c1_rounded = tuple(np.round(coord_i, 3))
                c2_rounded = tuple(np.round(coord_j, 3))
                
                # Order canonically to avoid A-B and B-A duplicates
                bond_key = (min(c1_rounded, c2_rounded), max(c1_rounded, c2_rounded))
                
                if bond_key not in seen_bonds:
                    seen_bonds.add(bond_key)
                    bonds.append(Bond(
                        idx1=i,
                        idx2=neighbor.index,
                        coord1=coord_i,
                        coord2=coord_j,
                        distance=neighbor.nn_distance,
                    ))
    
    return bonds


# =============================================================================
# Boundary repetition
# =============================================================================

@dataclass
class BoundaryAtom:
    """An atom repeated at a boundary position."""
    original_idx: int  # Index of original atom
    coords: np.ndarray  # Cartesian coordinates
    frac_coords: np.ndarray  # Fractional coordinates
    symbol: str


def generate_boundary_atoms(
    structure: PMGStructure,
    tolerance: float = 1e-6,
) -> List[BoundaryAtom]:
    """
    Generate periodic images of atoms that lie on cell boundaries.
    
    For an atom at fractional coordinate f:
    - If f < tolerance, it lies on the "lower" boundary and should be replicated at f+1
    - This creates the visual effect of atoms shared between adjacent cells
    
    Args:
        structure: pymatgen Structure object
        tolerance: Tolerance for boundary detection in fractional coordinates
        
    Returns:
        List of BoundaryAtom objects (periodic images)
    """
    boundary_atoms: List[BoundaryAtom] = []
    lattice = structure.lattice
    
    for idx, site in enumerate(structure):
        frac = np.array(site.frac_coords)
        symbol = site.specie.symbol
        
        # Check each dimension for boundary proximity
        on_boundary = [
            abs(frac[dim]) < tolerance or abs(frac[dim] - 1.0) < tolerance
            for dim in range(3)
        ]
        
        # Generate all combinations of shifts for boundary atoms
        shifts_list = []
        for dim in range(3):
            if abs(frac[dim]) < tolerance:
                # Near 0, replicate at +1
                shifts_list.append([0, 1])
            elif abs(frac[dim] - 1.0) < tolerance:
                # Near 1, replicate at 0 (i.e., shift by -1)
                shifts_list.append([0, -1])
            else:
                shifts_list.append([0])
        
        # Generate all shift combinations (except [0,0,0] which is original)
        from itertools import product
        for shift in product(*shifts_list):
            if shift == (0, 0, 0):
                continue  # Skip original position
            
            new_frac = frac + np.array(shift)
            # Keep within [0, 1] range for display
            new_frac = np.mod(new_frac + tolerance, 1.0 + 2*tolerance) - tolerance
            new_cart = lattice.get_cartesian_coords(new_frac)
            
            boundary_atoms.append(BoundaryAtom(
                original_idx=idx,
                coords=new_cart,
                frac_coords=new_frac,
                symbol=symbol,
            ))
    
    return boundary_atoms


# =============================================================================
# Supercell expansion
# =============================================================================

def make_supercell(
    structure: PMGStructure,
    scaling: Tuple[int, int, int],
) -> PMGStructure:
    """
    Create a supercell of the structure.
    
    Args:
        structure: Original pymatgen Structure
        scaling: Tuple of (a, b, c) scaling factors
        
    Returns:
        New Structure object representing the supercell
    """
    if scaling == (1, 1, 1):
        return structure.copy()
    
    supercell = structure.copy()
    supercell.make_supercell(scaling)
    return supercell


# =============================================================================
# Plotting
# =============================================================================

@dataclass
class StructurePlotOptions:
    """Options for structure visualization."""
    supercell: Tuple[int, int, int] = (1, 1, 1)
    repeat_boundary: bool = False
    atom_scale: float = 100.0  # Marker size scaling
    bond_width: float = 1.5
    bond_color: str = "#666666"
    show_cell: bool = True
    cell_color: str = "#000000"
    cell_width: float = 1.0
    cell_alpha: float = 0.5
    figsize: Tuple[float, float] = (10, 10)
    dpi: int = 150
    view_elevation: float = 20.0
    view_azimuth: float = 45.0


def plot_structure_3d(
    structure: PMGStructure,
    options: Optional[StructurePlotOptions] = None,
    ax: Optional[Axes3D] = None,
) -> Tuple[plt.Figure, Axes3D]:
    """
    Create a 3D ball-and-stick plot of a crystal structure.
    
    Args:
        structure: pymatgen Structure object
        options: Plotting options (uses defaults if None)
        ax: Optional existing 3D axes to plot on
        
    Returns:
        Tuple of (Figure, Axes3D)
    """
    if options is None:
        options = StructurePlotOptions()
    
    # Create supercell if requested
    plot_structure = make_supercell(structure, options.supercell)
    
    # Create figure if needed
    if ax is None:
        fig = plt.figure(figsize=options.figsize, dpi=options.dpi)
        ax = fig.add_subplot(111, projection='3d')
    else:
        fig = ax.get_figure()
    
    # Collect all atoms to plot
    atoms_to_plot: List[Tuple[np.ndarray, str, int]] = []  # (coords, symbol, original_idx)
    
    for idx, site in enumerate(plot_structure):
        atoms_to_plot.append((np.array(site.coords), site.specie.symbol, idx))
    
    # Add boundary atoms if requested
    if options.repeat_boundary:
        boundary_atoms = generate_boundary_atoms(plot_structure)
        for ba in boundary_atoms:
            atoms_to_plot.append((ba.coords, ba.symbol, ba.original_idx))
    
    # Detect bonds
    # Only include bonds to periodic images if we're showing boundary atoms
    bonds = detect_bonds(plot_structure, include_periodic_images=options.repeat_boundary)
    
    # Plot atoms (balls)
    for coords, symbol, _ in atoms_to_plot:
        color = get_element_color(symbol)
        radius = get_element_radius(symbol)
        size = options.atom_scale * (radius ** 2)  # Scale by r^2 for visual area
        
        ax.scatter(
            coords[0], coords[1], coords[2],
            c=color,
            s=size,
            edgecolors='black',
            linewidths=0.5,
            alpha=0.9,
            depthshade=True,
        )
    
    # Plot bonds (sticks)
    for bond in bonds:
        ax.plot(
            [bond.coord1[0], bond.coord2[0]],
            [bond.coord1[1], bond.coord2[1]],
            [bond.coord1[2], bond.coord2[2]],
            color=options.bond_color,
            linewidth=options.bond_width,
            alpha=0.8,
        )
    
    # Plot unit cell
    if options.show_cell:
        _plot_cell_wireframe(ax, plot_structure.lattice, options)
    
    # Set labels and aspect
    ax.set_xlabel('x (Å)')
    ax.set_ylabel('y (Å)')
    ax.set_zlabel('z (Å)')
    
    # Set equal aspect ratio
    _set_equal_aspect_3d(ax, plot_structure)
    
    # Set view angle
    ax.view_init(elev=options.view_elevation, azim=options.view_azimuth)
    
    # Clean up the plot
    ax.set_box_aspect([1, 1, 1])
    
    return fig, ax


def _plot_cell_wireframe(
    ax: Axes3D,
    lattice,
    options: StructurePlotOptions,
) -> None:
    """Plot the unit cell as a wireframe."""
    # Get cell vectors
    a1, a2, a3 = lattice.matrix
    origin = np.array([0.0, 0.0, 0.0])
    
    # Define the 8 corners of the parallelepiped
    corners = [
        origin,
        a1,
        a2,
        a3,
        a1 + a2,
        a1 + a3,
        a2 + a3,
        a1 + a2 + a3,
    ]
    
    # Define the 12 edges of the parallelepiped
    edges = [
        (0, 1), (0, 2), (0, 3),  # From origin
        (1, 4), (1, 5),          # From a1
        (2, 4), (2, 6),          # From a2
        (3, 5), (3, 6),          # From a3
        (4, 7), (5, 7), (6, 7),  # To opposite corner
    ]
    
    for i, j in edges:
        c1, c2 = corners[i], corners[j]
        ax.plot(
            [c1[0], c2[0]],
            [c1[1], c2[1]],
            [c1[2], c2[2]],
            color=options.cell_color,
            linewidth=options.cell_width,
            alpha=options.cell_alpha,
            linestyle='--',
        )


def _set_equal_aspect_3d(ax: Axes3D, structure: PMGStructure) -> None:
    """Set equal aspect ratio for 3D plot."""
    # Get all atom coordinates
    coords = np.array([site.coords for site in structure])
    
    if len(coords) == 0:
        return
    
    # Also include cell corners for proper scaling
    lattice = structure.lattice
    a1, a2, a3 = lattice.matrix
    origin = np.array([0.0, 0.0, 0.0])
    cell_corners = np.array([
        origin, a1, a2, a3, a1+a2, a1+a3, a2+a3, a1+a2+a3
    ])
    
    all_coords = np.vstack([coords, cell_corners])
    
    # Find data ranges
    x_range = all_coords[:, 0].max() - all_coords[:, 0].min()
    y_range = all_coords[:, 1].max() - all_coords[:, 1].min()
    z_range = all_coords[:, 2].max() - all_coords[:, 2].min()
    
    max_range = max(x_range, y_range, z_range)
    
    # Set limits
    x_mid = (all_coords[:, 0].max() + all_coords[:, 0].min()) / 2
    y_mid = (all_coords[:, 1].max() + all_coords[:, 1].min()) / 2
    z_mid = (all_coords[:, 2].max() + all_coords[:, 2].min()) / 2
    
    ax.set_xlim(x_mid - max_range/2 * 1.1, x_mid + max_range/2 * 1.1)
    ax.set_ylim(y_mid - max_range/2 * 1.1, y_mid + max_range/2 * 1.1)
    ax.set_zlim(z_mid - max_range/2 * 1.1, z_mid + max_range/2 * 1.1)


# =============================================================================
# High-level API
# =============================================================================

@dataclass
class StructureVisualizationResult:
    """Result of structure visualization."""
    output_path: Optional[Path] = None
    n_atoms: int = 0
    n_bonds: int = 0
    supercell: Tuple[int, int, int] = (1, 1, 1)
    repeat_boundary: bool = False
    
    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path) if self.output_path else None,
            "n_atoms": self.n_atoms,
            "n_bonds": self.n_bonds,
            "supercell": list(self.supercell),
            "repeat_boundary": self.repeat_boundary,
        }


def visualize_structure(
    structure: PMGStructure,
    output_path: Optional[Path] = None,
    supercell: Tuple[int, int, int] = (1, 1, 1),
    repeat_boundary: bool = False,
    show: bool = False,
    plot_format: str = "png",
    **kwargs,
) -> StructureVisualizationResult:
    """
    Visualize a crystal structure as a 3D ball-and-stick plot.
    
    This is the main entry point for structure visualization.
    
    Args:
        structure: pymatgen Structure object
        output_path: Path to save the plot (None to not save)
        supercell: Tuple of (a, b, c) supercell scaling factors
        repeat_boundary: If True, show periodic images at cell boundaries
        show: If True, attempt to display interactively (may not work headless)
        plot_format: Output format (png, svg, pdf)
        **kwargs: Additional options passed to StructurePlotOptions
        
    Returns:
        StructureVisualizationResult with metadata
    """
    options = StructurePlotOptions(
        supercell=supercell,
        repeat_boundary=repeat_boundary,
        **{k: v for k, v in kwargs.items() if hasattr(StructurePlotOptions, k)},
    )
    
    # Create the plot
    fig, ax = plot_structure_3d(structure, options)
    
    # Create supercell for counting (must match what plot_structure_3d does)
    plot_structure = make_supercell(structure, supercell)
    bonds = detect_bonds(plot_structure, include_periodic_images=repeat_boundary)
    
    # Count atoms (including boundary if applicable)
    n_atoms = len(plot_structure)
    if repeat_boundary:
        boundary_atoms = generate_boundary_atoms(plot_structure)
        n_atoms += len(boundary_atoms)
    
    result = StructureVisualizationResult(
        n_atoms=n_atoms,
        n_bonds=len(bonds),
        supercell=supercell,
        repeat_boundary=repeat_boundary,
    )
    
    # Save if output path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, format=plot_format, dpi=options.dpi, bbox_inches='tight')
        result.output_path = output_path
    
    # Show if requested
    if show:
        try:
            import matplotlib
            if matplotlib.get_backend().lower() != 'agg':
                plt.show()
            else:
                import warnings
                warnings.warn(
                    "Cannot show interactive plot with Agg backend. "
                    "Set a different backend or save to file instead."
                )
        except Exception:
            pass
    
    # Close figure to free memory
    plt.close(fig)
    
    return result
