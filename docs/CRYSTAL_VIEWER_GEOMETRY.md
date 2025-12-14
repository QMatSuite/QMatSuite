# Crystal Viewer Geometry: Algorithms and Design

This document describes the mathematical algorithms, design choices, and implementation details for the 3D crystal structure viewer in QuantumVITAS.

## Overview

The crystal viewer supports four display modes:
1. **Primitive** - Shows the primitive unit cell with wrapped coordinates
2. **Supercell** - Shows an N×M×P supercell expansion
3. **Conventional** - Shows the conventional/standard cell (via pymatgen)
4. **Box** - Shows all atoms within an arbitrary axis-aligned bounding box

All modes use a **single-source-of-truth** bond construction function and enforce coordinate wrapping.

## Coordinate Canonicalization and Wrapping

### Single-Point Canonicalization Rule

**CRITICAL**: Fractional coordinates are canonicalized exactly once at the entry point of the visualization pipeline, never again downstream.

**Entry Points** (where canonicalization happens):
- `build_display_atoms()` - main entry for GUI visualization
- `visualize_structure()` - high-level API entry point
- `plot_structure_3d()` - matplotlib visualization entry point

**Forbidden**: Internal helpers (bond detection, supercell generation, boundary atom generation) MUST NOT canonicalize.

**Why**: This ensures:
- Deterministic, stable bond counts across small coordinate shifts
- No double-canonicalization that could fold boundary images back into the main cell
- Clear separation: canonicalization is pre-processing, not geometry logic

**Detailed Documentation**: See `docs/CANONICALIZATION_DESIGN.md` for complete design rationale and implementation details.

### Canonicalization Algorithm

The canonicalization algorithm (`canonicalize_frac_coords()`) performs:

1. **Integer Snapping**: Snap values very close to integers (within `BOUNDARY_FRAC_TOL = 1e-8`) to those integers
2. **Modulo Wrapping**: Wrap into `[0, 1)` using modulo 1
3. **Boundary Snapping**: Snap values near boundaries to 0.0:
   - Values within 0.0101 of 1.0 → snap to 0.0 (handles 0.99 from -0.01 shifts)
   - Values within 0.0101 of 0.0 → snap to 0.0 (handles 0.01 from +0.01 shifts)

**BOUNDARY_FRAC_TOL = 1e-8**:
- Chosen through extensive testing (values from 1e-12 to 1e-4 all work)
- 100x smaller than previous 1e-4
- Handles typical floating point errors in integer snapping
- Works correctly with boundary atom detection

**Implementation**: `src/quantumvitas/analysis/structure_viz.py::canonicalize_frac_coords()` and `canonicalize_structure_in_place()`

### Coordinate Wrapping (Legacy/Compatibility)

For backward compatibility, `wrap_fractional_coords()` is a thin wrapper around `canonicalize_frac_coords()`:

```python
def wrap_fractional_coords(frac: np.ndarray, eps: float = BOUNDARY_FRAC_TOL) -> np.ndarray:
    """Wrap fractional coordinates into [0, 1) with epsilon handling."""
    return canonicalize_frac_coords(frac, eps=eps)
```

For Cartesian coordinates, we convert to fractional, wrap, then convert back:
- `wrap_cartesian_coords()` - wraps Cartesian coords via fractional conversion

## Conventional Cell Display

### Algorithm
Uses pymatgen's `SpacegroupAnalyzer` to derive the conventional standard cell:

```python
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

analyzer = SpacegroupAnalyzer(structure)
conventional = analyzer.get_conventional_standard_structure()
```

**Fallback**: If symmetry analysis fails, the original structure is used with a warning logged.

**Why**: The conventional cell often provides better visual intuition (e.g., Si diamond appears cubic rather than rhombohedral).

**Implementation**: `src/quantumvitas/analysis/structure_viz.py::get_conventional_cell()`

## Box Enumeration (Method 2: Solve k-Range Intervals)

### Problem
For very skewed primitive cells, generating a huge supercell then clipping to a box can create millions of atoms. We need efficient enumeration.

### Algorithm: Method 2

Given:
- Lattice matrix A = [a, b, c] (3×3, rows are lattice vectors)
- Basis atom at fractional f → Cartesian r₀ = A·f
- Axis-aligned box: [xmin, xmax] × [ymin, ymax] × [zmin, zmax]

Find all integer translations n=(i,j,k) such that:
```
r = r₀ + i·a + j·b + k·c  lies inside the box
```

**Step 1: Compute tight bounds for i, j, k**
- For each of 8 box corners rc:
  - Compute nc = A⁻¹(rc - r₀)  (fractional translation needed)
- i ∈ [floor(min nc_x), ceil(max nc_x)] (with safety margin)
- Similar for j, k

**Step 2: For each (i, j), solve for k-interval**
- Compute r_ij = r₀ + i·a + j·b
- For each axis t ∈ {x, y, z}:
  - Constraint: tmin ≤ r_ij[t] + k·c[t] ≤ tmax
  - Solve: k ∈ [(tmin - r_ij[t])/c[t], (tmax - r_ij[t])/c[t]]
  - Handle sign of c[t] (inequalities flip if c[t] < 0)
  - If |c[t]| < eps, constraint becomes feasibility check on (i,j)
- Intersect the three k-intervals
- Convert to integer k range: k ∈ [floor(k_lower), ceil(k_upper)]

**Step 3: For each k in range, verify and emit**
- Compute r = r_ij + k·c
- Check if r is inside box (with eps tolerance)
- Emit atom with stable ID

**Complexity**: O(N_basis × (i_range × j_range × k_range_avg))
- Typically much smaller than generating full supercell
- Works even for very skewed cells (e.g., 1×1×100 supercell)

**Implementation**: `src/quantumvitas/analysis/structure_viz.py::enumerate_atoms_in_aabb()`

### Why Method 2?
- **Efficiency**: Only enumerates atoms that could be in the box
- **Scalability**: Works for arbitrary box sizes without memory explosion
- **Robustness**: Handles degenerate cases (c[t] ≈ 0) correctly

## Bond Construction: Single Source of Truth

### Function Signature
```python
def build_bonds(
    atoms_cart: np.ndarray,           # (N, 3) Cartesian coordinates
    species: List[str],                # N element symbols
    radii_map: Dict[str, float],      # Element → radius mapping
    *,
    max_factor: float = 1.2,          # Multiplier for sum of radii
    tolerance: float = 0.3,           # Extra tolerance (Å)
    max_cutoff: float = 3.5,          # Maximum distance (Å)
    neighbor_shell: Optional[int] = None,
    lattice_matrix: Optional[np.ndarray] = None,  # 3x3 lattice for PBC
) -> List[Bond]:
```

### Bond Criterion
```
distance < (r_i + r_j) * max_factor + tolerance
```

Where:
- r_i, r_j are covalent radii of elements i, j
- max_factor = 1.2 (default)
- tolerance = 0.3 Å (default)
- **distance**: Minimum-image distance if `lattice_matrix` is provided, else Euclidean

### PBC-Aware Bond Detection

**Critical**: For periodic structures (primitive, supercell, conventional), bonds are detected using **minimum-image convention** to correctly find bonds across periodic boundaries.

**Why PBC is essential**: In a supercell, atoms at edges need to bond to neighbors in adjacent periodic images. Without PBC-aware distance calculation, these bonds are missed, leading to under-counting (e.g., 18 bonds instead of 32 for Si 2×2×2).

**Algorithm** (when `lattice_matrix` is provided):
1. Convert Cartesian coordinates to fractional: `frac = A⁻¹ @ cart`
2. For each atom pair (i, j):
   - Compute fractional delta: `delta_frac = frac_j - frac_i`
   - Wrap to minimum image: `delta_frac = delta_frac - round(delta_frac)` (maps to [-0.5, 0.5))
   - Convert back to Cartesian: `delta_cart = A @ delta_frac`
   - Distance = `||delta_cart||`
3. Apply bond criterion using minimum-image distance
4. Return bonds with minimum-image coordinates for rendering

**Non-periodic mode** (when `lattice_matrix` is None):
- Uses standard Euclidean distance
- Appropriate for box mode (AABB in Cartesian space)

**Efficiency**: 
- PBC mode: O(N²) brute force with minimum-image (required for correctness; KD-tree in Cartesian space can miss PBC neighbors)
- Non-PBC mode: O(N log N) with KD-tree
- Both modes use a precomputed global cutoff to reduce candidate pairs

**Numerical robustness**:
- Fractional wrapping uses epsilon guards near ±0.5 boundaries to prevent jitter
- Invalid or near-singular lattice matrices fall back to non-periodic detection with warnings

**Implementation**: `src/quantumvitas/analysis/structure_viz.py::build_bonds()`

### Boundary Repeat vs Bond Detection

**Important distinction**:
- **PBC bond detection**: Always uses minimum-image convention for periodic modes (primitive, supercell, conventional). This ensures correct connectivity regardless of whether boundary atoms are displayed. Bond detection is **always PBC-aware** when a lattice matrix is provided.
- **Boundary repeat** (display): Only affects whether extra boundary atoms/images are displayed for visualization. This is a **display-only** feature and does NOT affect bond detection correctness or bond counts.

**Example**: In a 2×2×2 supercell:
- With `repeat_boundary=False`: 16 atoms displayed, 32 bonds detected (using PBC minimum-image)
- With `repeat_boundary=True`: 16 atoms + boundary duplicates displayed, same 32 bonds detected

**Deprecation note**: The `include_periodic_images` parameter in `detect_bonds()` is deprecated and no longer affects bond detection. Bond detection always uses PBC-aware minimum-image convention. The parameter is kept for backward compatibility only.

### Why Single Source of Truth?
- **Consistency**: All modes (primitive, supercell, conventional, box) use identical bond logic
- **Maintainability**: One function to update for bond algorithm changes
- **Correctness**: PBC-aware detection ensures full connectivity in supercells

## Display Atom Building Pipeline

### Unified Function
```python
def build_display_atoms(
    structure: PMGStructure,
    params: DisplayModeParams,
    *,
    wrap_coords: bool = True,
) -> Tuple[List[DisplayAtom], PMGStructure]:
```

**Pipeline**:
1. **Normalize structure** based on mode:
   - Primitive: use original (wrapped)
   - Supercell: expand via pymatgen
   - Conventional: get via SpacegroupAnalyzer
   - Box: use original (enumeration handles expansion)
2. **Wrap coordinates** (if wrap_coords=True)
3. **Generate display atoms**:
   - Primitive/Supercell/Conventional: iterate sites
   - Box: call `enumerate_atoms_in_aabb()`
4. **Add boundary atoms** (if repeat_boundary=True)
5. **Return** (display_atoms, display_structure)

**Implementation**: `src/quantumvitas/analysis/structure_viz.py::build_display_atoms()`

## Known Limitations and Epsilon Handling

### Epsilon Values
- `FRAC_EPS = 1e-9`: Fractional coordinate boundary tolerance
- `eps = 1e-6`: Box enumeration boundary tolerance
- Bond detection uses `tolerance = 0.3 Å` (configurable)

### Limitations
1. **Symmetry analysis**: Conventional cell may fail for disordered structures
   - **Mitigation**: Falls back to original structure with warning
2. **Very large boxes**: Box enumeration can still be slow for huge boxes
   - **Mitigation**: User should use reasonable box sizes
3. **Bond detection**: Uses covalent radii, may miss weak bonds
   - **Mitigation**: Adjustable `max_factor` and `tolerance` parameters
4. **Periodic boundaries**: Box mode doesn't consider periodicity for bonds
   - **Mitigation**: Box atoms are already expanded, bonds computed directly

### Edge Cases Handled
- Degenerate lattice vectors (c[t] ≈ 0 in box enumeration)
- Atoms exactly on cell boundaries (wrapping handles this)
- Empty boxes (returns empty list)
- Invalid box bounds (xmax < xmin, etc.)

## Code Pointers

### Key Functions

1. **Bond construction (single source of truth)**:
   - File: `src/quantumvitas/analysis/structure_viz.py`
   - Function: `build_bonds()` (line ~200)
   - Signature: `build_bonds(atoms_cart, species, radii_map, *, max_factor=1.2, tolerance=0.3, max_cutoff=3.5) -> List[Bond]`

2. **Box enumeration (method 2)**:
   - File: `src/quantumvitas/analysis/structure_viz.py`
   - Function: `enumerate_atoms_in_aabb()` (line ~400)
   - Signature: `enumerate_atoms_in_aabb(structure, box_bounds, *, eps=1e-6) -> List[DisplayAtom]`

3. **Coordinate wrapping**:
   - File: `src/quantumvitas/analysis/structure_viz.py`
   - Functions: `wrap_fractional_coords()`, `wrap_cartesian_coords()` (line ~130)

4. **Display atom building**:
   - File: `src/quantumvitas/analysis/structure_viz.py`
   - Function: `build_display_atoms()` (line ~550)

5. **Conventional cell**:
   - File: `src/quantumvitas/analysis/structure_viz.py`
   - Function: `get_conventional_cell()` (line ~350)

### API Integration

- **Backend API**: `src/quantumvitas/api.py::get_structure_vis_data()`
  - Accepts `display_mode` and `box_bounds` parameters
  - Calls `build_display_atoms()` and `build_bonds()`

- **Frontend**: `gui/src/components/panels/StructureViewer3D.tsx`
  - UI controls for mode selection and box bounds
  - Calls backend via `get_structure_vis` RPC

## Summary

The crystal viewer uses:
- **Wrapping**: Stable fractional coordinate wrapping with epsilon handling
- **Conventional cell**: pymatgen SpacegroupAnalyzer for standard cell
- **Box enumeration**: Efficient interval-based method (Method 2) to avoid supercell explosion
- **Bond construction**: Single-source-of-truth function using KD-tree for efficiency
- **Unified pipeline**: `build_display_atoms()` handles all modes consistently

All modes ensure atoms are wrapped into the display cell and bonds are computed using the same algorithm for consistency and correctness.

