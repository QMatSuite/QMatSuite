# Analysis Pipeline Specification

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: SPECIFICATION (No Implementation)  
**Constitution Reference**: Engine-specific parsing, Universal AnalysisObjects, Visualization primitives

---

## 1. Scope and Goals

### 1.1 Problems We Solve

This specification unifies the analysis pipeline across all engines (QE, VASP, ORCA, CP2K, LAMMPS, etc.) and all analysis domains (trajectory, bands, DOS, PDOS, projected bands, 3D grids, etc.). It establishes:

1. **Single unified pipeline**: One canonical path from raw artifacts → parser → AnalysisObject → visual primitives → visualization
2. **Elimination of bypasses**: All analysis results must flow through AnalysisObjects; no direct consumption of parsed data by visualization
3. **Enforced boundaries**: Clear separation between engine-specific parsing, canonical analysis objects, and visualization
4. **Engine-agnostic visualization**: Visualization layer consumes only mathematical primitives, not engine-specific or domain-specific dataclasses

### 1.2 What Is Explicitly Out of Scope

- **Persistence**: This spec defines in-memory-only AnalysisObjects. No `.analysis/` directory writes, no SQLite persistence, no CAS writes, no `.history` system. Persistence will be considered in a future spec.
- **Engine installation**: How engines are installed or configured
- **UI styling**: Visual styling, colors, themes, layout (handled by visualization layer)
- **Derived computation caching**: While derived computations (Fermi alignment, smoothing) are allowed, caching strategies are out of scope for this spec

---

## 2. Definitions and Terminology

### 2.1 Raw Artifacts

**Raw artifacts** are engine-native output files produced by computational engines. Examples:
- QE: `relax.out`, `bands.dat.gnu`, `dos.dat`, `scf.out`
- VASP: `vasprun.xml`, `EIGENVAL`, `DOSCAR`, `OUTCAR`
- ORCA: `.out`, `.molden`
- CP2K: `cp2k_calc-pos-N.xyz`, `cp2k_calc-N.ener`
- LAMMPS: `dump.lammpstrj`, `log.lammps`

Raw artifacts are stored in `<calculation>/raw/` and are the **single source of truth** for execution results.

### 2.2 Engine Parser / Extractor

An **engine parser** (also called "extractor") is a component that:
- Reads raw artifacts from a calculation's `raw/` directory
- Converts engine-specific formats into canonical, engine-agnostic data structures
- Handles unit conversions (Ry → eV, Bohr → Å, etc.)
- Handles coordinate transformations (fractional → Cartesian, etc.)
- Returns an `AnalysisObject` (never raw arrays or domain dataclasses)

Each parser is registered with a key `(engine_prefix, analysis_kind)`, e.g., `("qe", "trajectory")`.

**Current reference implementation**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:25-295` (`QETrajectoryParser`)

### 2.3 AnalysisObject

An **AnalysisObject** is a canonical, engine-agnostic in-memory data structure representing analysis results. All AnalysisObjects:

- Have a `meta: AnalysisObjectMeta` field
- Have a `kind: str` field (e.g., `"trajectory"`, `"bands"`, `"dos"`)
- Have a `payload` field containing domain-specific data (arrays, frames, etc.)
- Implement `to_visual_primitives() -> Dict[str, Primitives1D | Primitives2D | Primitives3D]`
- Are **in-memory only** (no persistence in this spec)

**Current reference implementation**: `src/quantumvitas/core/analysis/trajectory/model.py:130-303` (`Trajectory`)

### 2.4 AnalysisObjectMeta

**AnalysisObjectMeta** is the unified metadata container for all AnalysisObjects. It includes:

- **Provenance**: `run_ulid`, `step_ulid`, `calc_ulid`, `engine_name`, `engine_version` (if known)
- **Source files**: List of `SourceFileStat` (path + `size_bytes` + `mtime` for stale detection)
- **Parser info**: `parser_name`, `parser_version`, `warnings` (if any)
- **Manifest snapshot**: Minimal digests needed for stale detection (even if we do not persist now)

**Current implementation**: `src/quantumvitas/core/analysis/base.py:56-108` (`AnalysisObjectMeta`)

### 2.5 Visual Primitives (1D/2D/3D)

**Visual primitives** are engine-agnostic mathematical data structures consumed by the visualization layer. They contain **data only** (no styling). Types:

- **Primitives1D**: `Series1D` (x[], y[], labels, units, optional multiple series)
- **Primitives2D**: Line collections, heatmaps, grids (to be defined for bands)
- **Primitives3D**: Points, mesh, voxel grids (for 3D visualization)

**Current implementation**: `src/quantumvitas/core/analysis/primitives.py:14-81`

### 2.6 Derived Compute

**Derived compute** refers to operations performed on AnalysisObjects to produce modified or aggregated data:
- Fermi energy alignment (shift energies so Fermi = 0)
- Smoothing (Gaussian, moving average)
- Aggregation (projection onto atoms/orbitals for PDOS)
- Interpolation/resampling

Derived compute happens **after** parsing but **before** or **during** `to_visual_primitives()` conversion. It is **not** part of the parser.

### 2.7 Bypass / Legacy Pipeline

A **bypass** is any code path that violates the unified pipeline by:
- Passing domain dataclasses (e.g., `DOSData`, `BandStructureData`) directly to visualization
- Reading raw artifacts in visualization code
- Skipping the AnalysisObject layer
- Using engine-specific logic in visualization

**Current bypasses** are documented in Section 9.

---

## 3. Invariants (MUST / MUST NOT)

These are **hard laws** that all code must follow. Violations are architectural errors.

### 3.1 Visualization Layer

- **INV-V1**: Visualization MUST NOT read raw artifacts directly. It must only consume visual primitives.
- **INV-V2**: Visualization MUST NOT depend on engine names (e.g., `if engine == "qe"`). It must be engine-agnostic.
- **INV-V3**: Visualization MUST NOT depend on step types (e.g., `if step_type == "bands_pw"`). It must be domain-agnostic.
- **INV-V4**: Visualization MUST NOT consume domain dataclasses (e.g., `DOSData`, `BandStructureData`, `SCFResult`). It must only consume primitives.
- **INV-V5**: Visualization MUST NOT import from engine parser modules (e.g., `from quantumvitas.drivers.qe.parsers import ...`).

### 3.2 Parser Layer

- **INV-P1**: Parsers MUST NOT emit visual primitives directly. They must return AnalysisObjects.
- **INV-P2**: Parsers MUST convert units to canonical units (eV, Å, fs, etc.) before returning AnalysisObjects.
- **INV-P3**: Parsers MUST register with `@register_parser(engine, analysis_kind)` decorator.
- **INV-P4**: Parsers MUST raise typed exceptions: `ArtifactNotAvailable` if artifacts are missing, `ParseError` if parsing fails.

### 3.3 AnalysisObject Layer

- **INV-A1**: All AnalysisObjects MUST carry `meta: AnalysisObjectMeta`.
- **INV-A2**: All AnalysisObjects MUST implement `to_visual_primitives() -> Dict[str, Primitives1D | Primitives2D | Primitives3D]`.
- **INV-A3**: AnalysisObjects MUST be in-memory only (no disk writes in this spec).
- **INV-A4**: AnalysisObjects MUST NOT contain lazy payload loaders (no `LazyArray`/`LateList` in payload). "Lazy" is allowed only for derived compute caching (in-memory).

### 3.4 Pipeline Uniqueness

- **INV-U1**: There MUST be exactly one path from raw artifacts → parser → AnalysisObject → primitives → visualization. No bypasses.
- **INV-U2**: Old pipelines that bypass AnalysisObjects MUST be removed (spec explicitly bans them).

### 3.5 Data Model

- **INV-D1**: There MUST NOT be a second data model. Domain dataclasses (e.g., `DOSData`, `BandStructureData`) are forbidden as visualization inputs.
- **INV-D2**: Visual primitives MUST be purely mathematical (arrays, labels, units). No styling fields.

---

## 4. Data Model: AnalysisObject and Meta

### 4.1 AnalysisObject Base Protocol

All AnalysisObjects must conform to this interface:

```python
from typing import Protocol, Dict, Any
from quantumvitas.core.analysis.base import AnalysisObjectMeta
from quantumvitas.core.analysis.primitives import Primitives1D, Primitives2D, Primitives3D

class AnalysisObject(Protocol):
    """Base protocol for all analysis objects."""
    
    # Required fields
    kind: str                    # e.g., "trajectory", "bands", "dos"
    schema_version: str           # e.g., "1.0"
    meta: AnalysisObjectMeta      # Unified metadata container
    
    # Payload (domain-specific, in-memory only)
    payload: Any                 # Domain-specific data (arrays, frames, etc.)
    
    # Optional extras (domain-specific)
    extras: Dict[str, Any]       # Optional additional metadata
    
    # Required method
    def to_visual_primitives(
        self,
        *,
        shift_fermi: bool = False,
        energy_range: Optional[Tuple[float, float]] = None,
        **kwargs
    ) -> Dict[str, Union[Primitives1D, Primitives2D, Primitives3D]]:
        """
        Convert to visualization primitives.
        
        Args:
            shift_fermi: If True, shift energies so Fermi = 0 (derived compute)
            energy_range: Optional (Emin, Emax) filter (derived compute)
            **kwargs: Domain-specific options
        
        Returns:
            Dict mapping primitive names to primitive objects
        """
        ...
```

**Current reference implementation**: `src/quantumvitas/core/analysis/trajectory/model.py:130-303` (`Trajectory`)

### 4.2 AnalysisObjectMeta Required Fields

```python
@dataclass
class AnalysisObjectMeta:
    """Unified metadata for all analysis objects."""
    
    # Identity
    schema_version: str                    # e.g., "1.0"
    object_type: str                       # "trajectory" | "dos" | "bands" | "scf"
    created_at: str                        # ISO 8601 timestamp
    
    # Provenance (for UI explanation only, NOT for stale detection)
    run_ulid: Optional[str] = None
    step_ulid: Optional[str] = None
    calc_ulid: Optional[str] = None
    engine_name: Optional[str] = None      # e.g., "qe", "vasp"
    engine_version: Optional[str] = None   # e.g., "7.2", "6.4.1"
    
    # Source tracking (for stale detection)
    source_files: List[SourceFileStat]   # Files this object was derived from
    
    # Parser info
    parser_name: str = ""                  # e.g., "qe_trajectory", "vasp_bands"
    parser_version: str = ""               # For reproducibility
    parser_warnings: List[str] = field(default_factory=list)  # Warnings from parser


@dataclass
class SourceFileStat:
    """Stat of a source file for stale detection."""
    path: str                              # Calc-relative path, e.g., "raw/scf.out"
    size_bytes: int                        # File size
    mtime: float                           # Modification time (Unix timestamp)
    # Future: sha256: Optional[str] = None
```

**Current implementation**: `src/quantumvitas/core/analysis/base.py:12-108`

### 4.3 Units and Coordinate Conventions

All AnalysisObjects must use **canonical units**:

- **Energy**: eV (electronvolt)
- **Length**: Å (angstrom)
- **Time**: fs (femtosecond)
- **Force**: eV/Å
- **Pressure**: GPa
- **Temperature**: K (Kelvin)
- **DOS**: states/eV
- **k-distance**: 2π/a (dimensionless, cumulative path distance)

**Coordinate conventions**:
- Positions: UNWRAPPED Cartesian coordinates in Å
- Cell: Row vectors (3×3 matrix) in Å
- k-points: Fractional coordinates in reciprocal space (0-1 range)

Parsers are responsible for unit conversion from engine-specific units (Ry, Bohr, etc.) to canonical units.

---

## 5. Visual Primitives Model (1D/2D/3D)

### 5.1 Existing Primitives Inventory

**Current implementation location**: `src/quantumvitas/core/analysis/primitives.py:14-81`

#### Primitives1D

```python
@dataclass
class Series1D:
    """1D data series for line plots. DATA ONLY - no style."""
    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    name: Optional[str] = None
```

**Used by**: Trajectory (energy, temperature, pressure, max_force series)

#### Primitives2D

**Current status**: Not yet defined for bands/DOS. Must be added.

**Required for bands**:
- Line collection: Multiple 1D curves (one per band) sharing x-axis (k-distance)
- High-symmetry markers: Vertical lines at k-path boundaries

**Required for DOS**:
- Single 1D curve (can use `Series1D`)

**Required for PDOS**:
- Multiple 1D curves (one per atom/orbital projection) sharing x-axis (energy)

**Proposed structure** (to be finalized in implementation):

```python
@dataclass
class LineCollection2D:
    """2D line collection for band structures. DATA ONLY."""
    x: np.ndarray                    # Shared x-axis (k-distance)
    y_series: List[np.ndarray]       # List of y arrays (one per band)
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    markers: List[Marker] = field(default_factory=list)  # High-symmetry points


@dataclass
class Marker:
    """Annotation marker for plots. Position only, NO style."""
    position: float
    label: str
    axis: str = "x"  # "x" or "y"
```

**Current `Marker` implementation**: `src/quantumvitas/core/analysis/primitives.py:75-81`

#### Primitives3D

**Current status**: Not yet defined. Required for:
- 3D charge density grids
- 3D band structure (E vs kx, ky, kz)
- 3D geometry visualization (handled separately via `GeometryFrames`)

**Proposed structure** (to be finalized in implementation):

```python
@dataclass
class VoxelGrid3D:
    """3D voxel grid for charge density, etc. DATA ONLY."""
    grid: np.ndarray                 # (nx, ny, nz) or (nx, ny, nz, n_components)
    origin: np.ndarray               # (3,) origin in Å
    spacing: np.ndarray               # (3,) voxel size in Å
    unit: str                         # e.g., "e/Å³"
```

### 5.2 Primitives Design Principles

- **DATA ONLY**: No styling fields (color, linewidth, etc.). Styling is the visualization layer's responsibility.
- **Mathematical**: Pure arrays, labels, units. No engine-specific or domain-specific logic.
- **Composable**: Primitives can be combined (e.g., bands + DOS side panel).

---

## 6. The Pipeline: End-to-end Data Flow

### 6.1 ASCII Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Raw Artifacts                                │
│  <calculation>/raw/relax.out, bands.dat.gnu, dos.dat, etc.     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Engine Parser (registered)                          │
│  @register_parser("qe", "trajectory")                           │
│  @register_parser("qe", "bands")                                │
│  @register_parser("vasp", "dos")                                │
│                                                                  │
│  Responsibilities:                                               │
│  - Read raw artifacts from raw_dir                               │
│  - Parse engine-specific format                                  │
│  - Convert units (Ry→eV, Bohr→Å)                                │
│  - Transform coordinates (fractional→Cartesian)                  │
│  - Build AnalysisObjectMeta (source_files, parser info)          │
│  - Return AnalysisObject                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              AnalysisObject (canonical, in-memory)              │
│  - Trajectory: meta, frames, trajectory_type                   │
│  - Bands: meta, k_distances, energies, high_sym_points        │
│  - DOS: meta, energies, dos, fermi_energy                      │
│                                                                  │
│  All have:                                                      │
│  - meta: AnalysisObjectMeta                                     │
│  - to_visual_primitives() method                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│         Derived Compute (optional, in-memory)                   │
│  - Fermi alignment (shift energies so Fermi = 0)                │
│  - Smoothing (Gaussian, moving average)                         │
│  - Aggregation (PDOS projection)                               │
│  - Interpolation/resampling                                     │
│                                                                  │
│  Happens during to_visual_primitives() call                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│         Visual Primitives (1D/2D/3D, engine-agnostic)          │
│  - Series1D: x[], y[], labels, units                           │
│  - LineCollection2D: x[], y_series[], markers                   │
│  - VoxelGrid3D: grid, origin, spacing                           │
│                                                                  │
│  DATA ONLY - no styling                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              Visualization Layer                                 │
│  - GUI: React components consume primitives                     │
│  - CLI: Matplotlib plotting (if needed)                        │
│  - Styling: Colors, linewidth, themes (viz layer's job)        │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Who Calls the Parser?

**Current trajectory implementation** (reference):

The parser is invoked by the service layer when analysis is requested. Current entry point:
- `src/quantumvitas/api/service.py` (via `QVService.Analysis` methods)
- Service layer resolves calculation/step, finds `raw_dir`, calls parser registry

**Proposed unified entry point** (for all domains):

```python
# Service layer (pseudocode)
def get_analysis_object(
    calc_dir: Path,
    raw_dir: Path,
    analysis_kind: str,
    *,
    run_ulid: Optional[str] = None,
    step_ulid: Optional[str] = None,
    calc_ulid: Optional[str] = None,
) -> AnalysisObject:
    """Unified entry point for all analysis domains."""
    # Auto-detect engine from raw_dir
    parser_cls = find_parser_for_raw(raw_dir, analysis_kind)
    if parser_cls is None:
        raise ArtifactNotAvailable(f"No parser found for {analysis_kind}")
    
    parser = parser_cls()
    return parser.parse(raw_dir, calc_dir, run_ulid=run_ulid, step_ulid=step_ulid, calc_ulid=calc_ulid)
```

**Current trajectory parser call site**: Not yet unified; trajectory may be called directly. Bands/DOS use `ensure_analysis_artifact()` which calls parsers directly.

### 6.3 Derived Compute Ownership

**Derived compute** (Fermi alignment, smoothing, aggregation) belongs to the AnalysisObject's `to_visual_primitives()` method or a separate derived compute layer. It is **NOT** part of the parser.

**Current trajectory example**: `Trajectory.get_observable_series()` performs derived compute (aggregation of forces to max_force).

**Proposed pattern**:
- Derived compute happens in `to_visual_primitives()` via optional parameters (`shift_fermi=True`, `energy_range=(Emin, Emax)`)
- Or via separate derived compute methods that return modified AnalysisObjects (in-memory)

---

## 7. Engine Parser Interface and Registration

### 7.1 Parser Registration

**Current registry**: `src/quantumvitas/parsers/registry.py:12-58`

**Registration key**: `(engine_prefix, analysis_kind)`

- `engine_prefix`: Lowercase engine identifier (e.g., `"qe"`, `"vasp"`, `"orca"`)
- `analysis_kind`: Lowercase analysis domain (e.g., `"trajectory"`, `"bands"`, `"dos"`)

**Registration decorator**:

```python
from quantumvitas.parsers.registry import register_parser

@register_parser("qe", "trajectory")
class QETrajectoryParser:
    engine = "qe"
    object_type = "trajectory"
    
    def can_parse(self, raw_dir: Path) -> bool:
        """Check if this parser can handle the raw directory."""
        ...
    
    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_ulid: Optional[str] = None,
        step_ulid: Optional[str] = None,
        calc_ulid: Optional[str] = None,
    ) -> AnalysisObject:
        """Parse raw artifacts and return AnalysisObject."""
        ...
```

**Current reference implementation**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:25-295`

### 7.2 Parser Discovery

**Current implementation**: `src/quantumvitas/parsers/registry.py:29-41` (`find_parser_for_raw()`)

**Algorithm**:
1. Iterate over registered parsers for the requested `analysis_kind`
2. Instantiate parser and call `can_parse(raw_dir)`
3. Return first parser that returns `True`

**Auto-detection**: The service layer should auto-detect the engine from `raw_dir` contents, not require explicit engine specification.

### 7.3 Error Behavior

**Missing artifacts**:

```python
class ArtifactNotAvailable(Exception):
    """Raised when required raw artifacts are missing."""
    def __init__(self, message: str, missing_files: List[str]):
        self.message = message
        self.missing_files = missing_files
```

**Parser behavior**: If required artifacts are missing, parser MUST raise `ArtifactNotAvailable` (not return `None`).

**Parse failure**:

```python
class ParseError(Exception):
    """Raised when parsing fails."""
    def __init__(self, message: str, parser_name: str, parser_version: str, source_files: List[str]):
        self.message = message
        self.parser_name = parser_name
        self.parser_version = parser_version
        self.source_files = source_files
```

**Parser behavior**: If parsing fails (malformed file, unexpected format), parser MUST raise `ParseError` with provenance info.

---

## 8. Domain Specs (Minimum Required)

### 8.1 Trajectory

**AnalysisObject.kind**: `"trajectory"`

**Required payload fields**:
- `frames: List[Frame]` - Sequence of trajectory frames
- `trajectory_type: str` - `"md"` | `"relax"` | `"neb"`

**Frame fields** (required):
- `frame_index: int`
- `positions: np.ndarray` - (N, 3) UNWRAPPED Cartesian in Å
- `species: List[str]` - N element symbols
- `cell: Optional[np.ndarray]` - (3, 3) or None
- `pbc: Tuple[bool, bool, bool]`

**Frame fields** (optional):
- `time: Optional[float]` - fs (for MD)
- `iteration: Optional[int]` - (for relax/NEB)
- `energy: Optional[float]` - eV
- `forces: Optional[np.ndarray]` - (N, 3) eV/Å
- `temperature: Optional[float]` - K
- `pressure: Optional[float]` - GPa

**Required meta fields**:
- `source_files`: List of trajectory output files (e.g., `relax.out`, `md.out`)
- `parser_name`: e.g., `"qe_trajectory"`, `"vasp_trajectory"`
- `engine_name`: e.g., `"qe"`, `"vasp"`

**Required `to_visual_primitives()` outputs**:
- `"geometry": GeometryFrames` - Sequence of geometry frames
- `"series_<observable>": Series1D` - For each available observable (energy, temperature, pressure, max_force)

**Typical derived operations**:
- Observable extraction: `get_observable_series(name)` - Aggregates frame data into 1D series
- Time/iteration axis selection: MD uses `time`, relax uses `iteration`

**Current implementation**: `src/quantumvitas/core/analysis/trajectory/model.py:130-303`

### 8.2 Bands

**AnalysisObject.kind**: `"bands"`

**Required payload fields**:
- `k_distances: np.ndarray` - (n_kpoints,) cumulative k-path distances in 2π/a
- `energies: np.ndarray` - (n_bands, n_kpoints) band energies in eV
- `high_symmetry_points: List[HighSymmetryPoint]` - k-path boundaries
- `fermi_energy: Optional[float]` - eV

**HighSymmetryPoint fields**:
- `label: str` - e.g., `"Γ"`, `"X"`, `"L"`
- `k_distance: float` - x-coordinate in band plot
- `k_coords: Optional[Tuple[float, float, float]]` - Fractional k-coordinates

**Required meta fields**:
- `source_files`: List of band files (e.g., `bands.dat.gnu`, `bands.x.out`, `EIGENVAL`)
- `parser_name`: e.g., `"qe_bands"`, `"vasp_bands"`
- `engine_name`: e.g., `"qe"`, `"vasp"`

**Required `to_visual_primitives()` outputs**:
- `"bands": LineCollection2D` - Multiple 1D curves (one per band) sharing x-axis (k-distance)
- `"fermi_marker": Marker` - Optional marker at Fermi energy (y-axis)

**Typical derived operations**:
- Fermi alignment: `shift_fermi=True` - Shift energies so Fermi = 0
- Energy range filtering: `energy_range=(Emin, Emax)` - Filter bands to energy window
- Spin channel separation: For spin-polarized calculations, separate spin-up and spin-down bands

**Current bypass**: `src/quantumvitas/analysis/parsers.py:559-618` (`BandStructureData` dataclass, not AnalysisObject)

### 8.3 DOS

**AnalysisObject.kind**: `"dos"`

**Required payload fields**:
- `energies: np.ndarray` - (n_points,) energy values in eV
- `dos: np.ndarray` - (n_points,) DOS values in states/eV
- `idos: Optional[np.ndarray]` - (n_points,) integrated DOS (electrons)
- `fermi_energy: Optional[float]` - eV

**Required meta fields**:
- `source_files`: List of DOS files (e.g., `dos.dat`, `DOSCAR`)
- `parser_name`: e.g., `"qe_dos"`, `"vasp_dos"`
- `engine_name`: e.g., `"qe"`, `"vasp"`

**Required `to_visual_primitives()` outputs**:
- `"dos": Series1D` - x=energies, y=dos, labels and units

**Typical derived operations**:
- Fermi alignment: `shift_fermi=True` - Shift energies so Fermi = 0
- Energy range filtering: `energy_range=(Emin, Emax)` - Filter DOS to energy window
- Spin channel separation: For spin-polarized calculations, separate spin-up and spin-down DOS

**Current bypass**: `src/quantumvitas/analysis/parsers.py:434-479` (`DOSData` dataclass, not AnalysisObject)

### 8.4 PDOS / Projected Bands (Optional)

**AnalysisObject.kind**: `"pdos"` or `"projected_bands"`

**Required payload fields** (PDOS):
- `energies: np.ndarray` - (n_points,) energy values in eV
- `projections: Dict[str, np.ndarray]` - Keys: atom indices or orbital labels, Values: (n_points,) projected DOS
- `fermi_energy: Optional[float]` - eV

**Required `to_visual_primitives()` outputs**:
- `"pdos_<key>": Series1D` - One series per projection key

**Typical derived operations**:
- Aggregation: Sum projections over atoms/orbitals
- Fermi alignment: Same as DOS

**Current status**: Not yet implemented. Should follow same pattern as DOS.

---

## 9. Legacy/Bypass Identification (Current Repo Audit)

This section documents current bypasses that violate the unified pipeline. These must be eliminated during implementation.

### 9.1 Bypass #1: Bands Parser Returns Non-Canonical Dataclass

**Location**: `src/quantumvitas/analysis/parsers.py:559-618`

**Violation**: `parse_bands_gnu()` returns `BandStructureData` dataclass instead of `Bands` AnalysisObject.

**Evidence**:
```python
def parse_bands_gnu(...) -> BandStructureData:
    # Returns BandStructureData (no meta, no to_visual_primitives)
    return BandStructureData(...)
```

**How it violates**:
- **INV-A1**: No `meta: AnalysisObjectMeta`
- **INV-A2**: No `to_visual_primitives()` method
- **INV-U1**: Bypasses AnalysisObject layer

**Current consumption**: `src/quantumvitas/analysis/plotting.py:195-276` (`plot_bands()` consumes `BandStructureData` directly)

### 9.2 Bypass #2: DOS Parser Returns Non-Canonical Dataclass

**Location**: `src/quantumvitas/analysis/parsers.py:434-479`

**Violation**: `parse_dos_data()` returns `DOSData` dataclass instead of `DOS` AnalysisObject.

**Evidence**:
```python
def parse_dos_data(path: Path | str) -> DOSData:
    # Returns DOSData (no meta, no to_visual_primitives)
    return DOSData(...)
```

**How it violates**:
- **INV-A1**: No `meta: AnalysisObjectMeta`
- **INV-A2**: No `to_visual_primitives()` method
- **INV-U1**: Bypasses AnalysisObject layer

**Current consumption**: `src/quantumvitas/analysis/plotting.py:68-145` (`plot_dos()` consumes `DOSData` directly)

### 9.3 Bypass #3: Plotting Functions Consume Domain Dataclasses

**Location**: `src/quantumvitas/analysis/plotting.py:68-145, 195-276`

**Violation**: `plot_dos()` and `plot_bands()` accept `DOSData` and `BandStructureData` directly.

**Evidence**:
```python
def plot_dos(dos_data: DOSData, ...) -> Tuple[Figure, Axes]:
    # Direct consumption of DOSData
    energies = dos_data.energies
    dos = dos_data.dos

def plot_bands(band_data: BandStructureData, ...) -> Tuple[Figure, Axes]:
    # Direct consumption of BandStructureData
    k_distances = band_data.k_distances
    energies = band_data.energies
```

**How it violates**:
- **INV-V4**: Visualization consumes domain dataclasses
- **INV-D1**: Second data model used as visualization input

### 9.4 Bypass #4: API Service Returns Raw Dicts, Not AnalysisObjects

**Location**: `src/quantumvitas/api/service.py:663-761, 1285-1370`

**Violation**: `get_band_structure_data()` and `get_dos_data()` return raw dicts from artifacts, not AnalysisObjects.

**Evidence**:
```python
def get_band_structure_data(...) -> dict:
    cached = read_artifact(calculation_dir, AnalysisType.BANDS)
    return {
        "k_distances": cached.get("k_distances", []),
        "energies_ev": cached.get("energies_ev", []),
        # ... raw dict, not AnalysisObject
    }
```

**How it violates**:
- **INV-U1**: Bypasses AnalysisObject layer
- **INV-A2**: No `to_visual_primitives()` call

**Current consumption**: GUI consumes raw dicts directly (`gui/src/components/panels/CalculationAnalysisPanel.tsx:192-236`)

### 9.5 Bypass #5: Bands/DOS Parsers Not Registered

**Location**: `src/quantumvitas/analysis/parsers.py:481, 620`

**Violation**: `parse_dos_data()` and `parse_bands_gnu()` are standalone functions, not registered parser classes.

**Evidence**:
- Trajectory parser: `@register_parser("qe", "trajectory")` at `src/quantumvitas/drivers/qe/parsers/trajectory.py:25`
- Bands parser: No decorator, standalone function at `src/quantumvitas/analysis/parsers.py:620`
- DOS parser: No decorator, standalone function at `src/quantumvitas/analysis/parsers.py:481`

**How it violates**:
- **INV-P3**: Parsers must register with `@register_parser(engine, analysis_kind)`

### 9.6 Bypass #6: Duplicate Data Models

**Location**: `src/quantumvitas/viz/data_models.py:16-34`

**Violation**: `BandStructureData` and `DOSData` exist in both `analysis/parsers.py` and `viz/data_models.py`.

**Evidence**:
- `src/quantumvitas/analysis/parsers.py:434` (`DOSData`)
- `src/quantumvitas/analysis/parsers.py:559` (`BandStructureData`)
- `src/quantumvitas/viz/data_models.py:16` (`BandStructureData`)
- `src/quantumvitas/viz/data_models.py:33` (`DOSData`)

**How it violates**:
- **INV-D1**: Second data model exists
- Schema drift risk (two definitions can diverge)

### 9.7 Bypass #7: Artifacts Module Calls Parsers Directly

**Location**: `src/quantumvitas/analysis/artifacts.py:456-580`

**Violation**: `ensure_analysis_artifact()` calls `parse_dos_data()` and `parse_bands_gnu()` directly, bypassing parser registry.

**Evidence**:
```python
def ensure_analysis_artifact(...):
    if analysis_type == AnalysisType.BANDS:
        band_data = parse_bands_gnu(...)  # Direct call, not via registry
        write_artifact(..., band_data.to_dict())
    elif analysis_type == AnalysisType.DOS:
        dos_data = parse_dos_data(...)  # Direct call, not via registry
        write_artifact(..., dos_data.to_dict())
```

**How it violates**:
- **INV-P3**: Not using parser registry
- **INV-U1**: Bypasses unified entry point

---

## 10. Acceptance Criteria (Spec-level)

These are concrete, testable criteria that must be satisfied after implementation.

### 10.1 Pipeline Uniqueness

- **AC1**: For bands/dos/trajectory, there exists exactly one public entry path that ends at viz primitives.
  - **Test**: Search codebase for all code paths that produce bands/DOS/trajectory data for visualization. Verify only one path exists per domain.

- **AC2**: No code path passes domain dataclasses (`DOSData`, `BandStructureData`, `SCFResult`) into visualization.
  - **Test**: Grep for `plot_bands(`, `plot_dos(`, verify they accept primitives, not dataclasses.

### 10.2 Visualization Layer Isolation

- **AC3**: Viz layer has zero imports from engine parser modules.
  - **Test**: Grep for `from quantumvitas.drivers.*.parsers import` in visualization code. Must be zero.

- **AC4**: Viz layer has zero imports from `analysis.parsers` (domain dataclasses).
  - **Test**: Grep for `from quantumvitas.analysis.parsers import` in visualization code. Must be zero.

### 10.3 AnalysisObject Completeness

- **AC5**: All AnalysisObjects include `meta: AnalysisObjectMeta`.
  - **Test**: For each AnalysisObject class, verify `meta` field exists and is of type `AnalysisObjectMeta`.

- **AC6**: All AnalysisObjects implement `to_visual_primitives()`.
  - **Test**: For each AnalysisObject class, verify method exists and returns `Dict[str, Union[Primitives1D, Primitives2D, Primitives3D]]`.

### 10.4 Parser Registration

- **AC7**: All parsers are registered with `@register_parser(engine, analysis_kind)`.
  - **Test**: Grep for parser classes/functions that return AnalysisObjects. Verify all have registration decorator.

- **AC8**: Parser registry can discover parsers via `find_parser_for_raw(raw_dir, analysis_kind)`.
  - **Test**: For each engine/domain combination, verify `find_parser_for_raw()` returns correct parser.

### 10.5 Gates/Tests We Should Add Later

(These are spec-level requirements; implementation will add actual tests.)

- **Gate1**: Unit test: `test_bands_pipeline_unified()` - Verify bands flow: raw → parser → Bands AnalysisObject → primitives → (mock) viz
- **Gate2**: Unit test: `test_dos_pipeline_unified()` - Verify DOS flow: raw → parser → DOS AnalysisObject → primitives → (mock) viz
- **Gate3**: Integration test: `test_multi_engine_bands()` - Verify VASP and QE bands both produce same primitive structure
- **Gate4**: Integration test: `test_fermi_alignment_derived_compute()` - Verify Fermi alignment happens in `to_visual_primitives()`, not parser
- **Gate5**: Regression test: `test_no_bypass_imports()` - Verify no imports from `analysis.parsers` or `drivers.*.parsers` in viz code

---

## 11. Migration Notes (No Plan)

This section identifies what must be migrated/removed, but does not provide a step-by-step plan.

### 11.1 What Must Be Migrated

1. **Bands parser**: Convert `parse_bands_gnu()` → `QEBandsParser` class, register, return `Bands` AnalysisObject
2. **DOS parser**: Convert `parse_dos_data()` → `QEDOSParser` class, register, return `DOS` AnalysisObject
3. **Plotting functions**: Refactor `plot_bands()` and `plot_dos()` to accept primitives, not dataclasses
4. **API service**: Refactor `get_band_structure_data()` and `get_dos_data()` to return AnalysisObjects, call `to_visual_primitives()`
5. **Artifacts module**: Refactor `ensure_analysis_artifact()` to use parser registry, not direct parser calls
6. **GUI consumption**: Update GUI to consume primitives from `to_visual_primitives()`, not raw dicts

### 11.2 What Must Be Removed

1. **Domain dataclasses as viz inputs**: Remove `DOSData` and `BandStructureData` from visualization code paths
2. **Duplicate data models**: Remove `src/quantumvitas/viz/data_models.py` (or repurpose for primitives only)
3. **Direct parser calls**: Remove direct calls to `parse_bands_gnu()` and `parse_dos_data()` from non-parser code
4. **Artifact dict returns**: Remove raw dict returns from API service; return AnalysisObjects or primitives

### 11.3 Risks

1. **Unit conventions**: Different engines may use different units (Ry vs eV, Bohr vs Å). Parsers must convert to canonical units. Risk: Conversion errors.
2. **Fermi level definitions**: Different engines may define Fermi energy differently (e.g., VASP vs QE). Risk: Misalignment in derived compute.
3. **k-path labeling**: Different engines may label high-symmetry points differently (e.g., `"Gamma"` vs `"Γ"`). Risk: Inconsistent labels in primitives.
4. **Coordinate conventions**: Different engines may use different coordinate systems (fractional vs Cartesian, row vs column vectors). Risk: Misalignment in geometry.
5. **Missing data handling**: Some engines may not provide all fields (e.g., no `idos` in DOS). Risk: Inconsistent payloads across engines.

---

## Appendix A: Current Code References

### A.1 Trajectory (Reference Implementation)

- **Parser**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:25-295`
- **AnalysisObject**: `src/quantumvitas/core/analysis/trajectory/model.py:130-303`
- **Meta**: `src/quantumvitas/core/analysis/base.py:56-108`
- **Primitives**: `src/quantumvitas/core/analysis/primitives.py:14-81`
- **Registry**: `src/quantumvitas/parsers/registry.py:12-58`

### A.2 Bands (Current Bypass)

- **Parser**: `src/quantumvitas/analysis/parsers.py:620-732` (`parse_bands_gnu()`)
- **Dataclass**: `src/quantumvitas/analysis/parsers.py:559-618` (`BandStructureData`)
- **Plotting**: `src/quantumvitas/analysis/plotting.py:195-276` (`plot_bands()`)
- **API**: `src/quantumvitas/api/service.py:663-761` (`get_band_structure_data()`)
- **Artifacts**: `src/quantumvitas/analysis/artifacts.py:570-580` (bands artifact creation)

### A.3 DOS (Current Bypass)

- **Parser**: `src/quantumvitas/analysis/parsers.py:481-543` (`parse_dos_data()`)
- **Dataclass**: `src/quantumvitas/analysis/parsers.py:434-479` (`DOSData`)
- **Plotting**: `src/quantumvitas/analysis/plotting.py:68-145` (`plot_dos()`)
- **API**: `src/quantumvitas/api/service.py:1285-1370` (`get_dos_data()`)
- **Artifacts**: `src/quantumvitas/analysis/artifacts.py:456-461` (DOS artifact creation)

### A.4 Duplicate Data Models

- **Viz models**: `src/quantumvitas/viz/data_models.py:16-34` (`BandStructureData`, `DOSData`)

---

## Appendix B: Primitives2D/3D Design (To Be Finalized)

This section documents proposed structures for 2D/3D primitives. Final design will be determined during implementation.

### B.1 LineCollection2D (For Bands)

```python
@dataclass
class LineCollection2D:
    """2D line collection for band structures. DATA ONLY."""
    x: np.ndarray                    # Shared x-axis (k-distance), shape (n_kpoints,)
    y_series: List[np.ndarray]       # List of y arrays (one per band), each shape (n_kpoints,)
    x_label: str                     # e.g., "k-path"
    y_label: str                     # e.g., "Energy - E_F"
    x_unit: str                      # e.g., "2π/a"
    y_unit: str                      # e.g., "eV"
    markers: List[Marker] = field(default_factory=list)  # High-symmetry points
```

**Alternative**: Could use `List[Series1D]` instead of `y_series`, but `LineCollection2D` makes shared x-axis explicit.

### B.2 VoxelGrid3D (For Charge Density, etc.)

```python
@dataclass
class VoxelGrid3D:
    """3D voxel grid for charge density, etc. DATA ONLY."""
    grid: np.ndarray                 # (nx, ny, nz) or (nx, ny, nz, n_components)
    origin: np.ndarray               # (3,) origin in Å
    spacing: np.ndarray               # (3,) voxel size in Å
    unit: str                         # e.g., "e/Å³"
    label: str                        # e.g., "Charge Density"
```

---

**End of Specification**

