# Trajectory Core Specification

**Version**: 1.1.0  
**Date**: 2026-01-19  
**Status**: SUPERSEDED  
**Constitution Reference**: §2 (ULID-only DAG), §3 (Geometry), §5 (Units)

---

> ⚠️ **This document has been superseded.**
>
> **Current documents**:
> - **Framework**: [ANALYSIS_OBJECTS_FRAMEWORK.md](./ANALYSIS_OBJECTS_FRAMEWORK.md) — General analysis objects architecture
> - **Implementation Plan**: [IMPLEMENT_ANALYSIS_OBJECTS_TRAJECTORY_V1.md](../plans/IMPLEMENT_ANALYSIS_OBJECTS_TRAJECTORY_V1.md) — Step-by-step implementation guide
>
> The framework document establishes the two-layer philosophy (raw artifacts → canonical analysis objects)
> with Trajectory as the first fully-specified instance.
>
> **Confirmed Decisions** (see framework for details):
> - Cache location: `.analysis/` (hidden, parallel to raw/)
> - Provenance: `.runtime/provenance.json` (current-only, UI explanation)
> - Staleness: (size_bytes, mtime) only, no sha256 in v1
> - Positions: unwrapped Cartesian Å
> - Cell: supports None (molecular) and (3,3) arrays
> - Cache default: enabled, user-configurable in Settings/Advanced
>
> This document is retained for historical reference only.

---

## 0. Motivation: Why This Specification Is Necessary

### The Imminent Need

QMatSuite is about to integrate multiple computational engines (VASP, LAMMPS, CP2K, etc.) that produce **dynamic process outputs**: molecular dynamics trajectories, geometry optimization sequences, and NEB pathways.

**Without a stable trajectory data core:**
- Each parser would define its own frame schema → **format drift**
- UI/visualization code would need engine-specific branches → **coupling explosion**
- Plot/analysis modules would duplicate data extraction logic → **maintenance burden**
- Six months from now, we'd face a painful refactor → **technical debt**

**With a trajectory core:**
- Parsers map engine outputs to one canonical representation
- UI/viz/analysis code targets the stable core API
- New engines only require a parser, not UI changes
- The contract is stable; the edges (parsers) are iterable

### Alignment with Constitution

This specification extends the existing **relax artifact pattern** (see `docs/specs/RELAX_SPEC.md`):
- Relax already produces calc-scope structure artifacts (not ULID resources)
- Trajectory generalizes this: multiple frames per run, with observables
- Promote semantics remain consistent: explicit user action → ULID resource

---

## 1. Goals

1. **Unified representation** for multi-frame atomic states + observables + provenance, supporting MD, relax (optimization), and NEB from any engine.

2. **Engine-agnostic core**: Parsers map raw sandbox outputs → trajectory core. UI/viz/analysis never see engine-specific formats.

3. **Stable contract**: Frame schema is designed for longevity. Optional fields use extension mechanism. Schema versioning ensures forward compatibility.

4. **Calc-scope artifact semantics**: Trajectory lives in `raw/`, not in project resource DAG. No ULID. Not globally scanned. Can be arbitrarily large.

5. **Promote path**: User can extract individual frames → project structure resources (with ULID, fingerprint, dedup).

---

## 2. Invariants (Must Not Violate)

### 2.1 Raw Sandbox Placement

**INV-T1**: All trajectory artifacts MUST be written inside the run's raw sandbox directory.

```
project_root/
└── calculations/
    └── <calc_id>/
        └── raw/               ← trajectory lives here
            └── trajectory/
```

**Evidence**: This follows the raw sandbox contract from `docs/JOB_IO_DIRECTORY_SEMANTICS.md` and `docs/TERMINOLOGY_DIRECTORIES.md`.

### 2.2 Not a Project Resource

**INV-T2**: Trajectory artifacts do NOT:
- Receive a ULID
- Enter the project resource DAG
- Participate in global resource scanning
- Get indexed in ResourceIndex

**Evidence**: Consistent with `RELAX_SPEC.md` §2.3 which establishes that generated structures are artifacts, not ULID-tracked resources.

### 2.3 Promote is the Only Path to Resource Status

**INV-T3**: A trajectory frame becomes a project structure resource ONLY through explicit `promote_frame()` operation.

**Evidence**: `RELAX_SPEC.md` §2.1 - "Promoting relax output to a project resource is an explicit user action."

### 2.4 Algorithm Separation

**INV-T4**: The trajectory core does NOT implement:
- MD integrators
- Optimization algorithms
- NEB solvers
- Force calculations

These remain in the engines. The core only represents, stores, and provides access to trajectory data.

**Evidence**: From `docs/research/ASE_ARCHITECTURE_REPORT.md` - we adopt ASE's data model patterns but NOT its algorithm/Calculator layer.

### 2.5 Parser is Read-Only

**INV-T5**: Parsers MUST NOT:
- Modify files in raw/
- Depend on .history/
- Depend on project resources
- Write outside raw/trajectory/

---

## 3. Data Model

### 3.1 Frame (Core Unit)

The `Frame` is the fundamental unit representing a single snapshot of atomic state.

```python
@dataclass
class Frame:
    """
    A single frame in a trajectory.
    
    Required fields (parser MUST provide):
    - frame_index, positions, species, cell, pbc
    
    Optional fields (parser provides if available):
    - All others
    """
    # === REQUIRED FIELDS ===
    frame_index: int                    # 0-based index in trajectory
    positions: NDArray[np.float64]      # Shape (N, 3), unit: Å
    species: List[str]                  # Length N, element symbols (e.g., ["Si", "O", "O"])
    cell: NDArray[np.float64]           # Shape (3, 3), row vectors, unit: Å
    pbc: Tuple[bool, bool, bool]        # Periodic boundary conditions
    
    # === AXIS/TIME FIELDS ===
    time: Optional[float] = None        # Physical time in fs (MD) or None (relax/NEB)
    iteration: Optional[int] = None     # Iteration/step number (relax/NEB/MD)
    
    # === DYNAMICS FIELDS ===
    velocities: Optional[NDArray[np.float64]] = None    # Shape (N, 3), unit: Å/fs
    momenta: Optional[NDArray[np.float64]] = None       # Shape (N, 3), unit: amu·Å/fs
    
    # === ENERGY/FORCE FIELDS ===
    energy: Optional[float] = None                      # Total potential energy, unit: eV
    forces: Optional[NDArray[np.float64]] = None        # Shape (N, 3), unit: eV/Å
    
    # === THERMODYNAMIC FIELDS ===
    temperature: Optional[float] = None                 # Instantaneous T, unit: K
    pressure: Optional[float] = None                    # External/virial pressure, unit: GPa
    kinetic_energy: Optional[float] = None              # unit: eV
    
    # === STRESS TENSOR ===
    stress: Optional[NDArray[np.float64]] = None        # Shape (3, 3), unit: GPa
    # Note: Sign convention follows ASE: positive = tensile
    # Voigt representation available via utility function
    
    # === ATOM IDENTITY ===
    atom_ids: Optional[List[str]] = None                # Stable identifiers if atoms reordered
    
    # === NEB-SPECIFIC ===
    image_index: Optional[int] = None                   # For NEB: which image (0 to n_images-1)
    
    # === EXTENSION MECHANISM ===
    extras: Dict[str, Any] = field(default_factory=dict)
    # For engine-specific data not in schema (e.g., charges, magmoms, custom observables)
```

### 3.2 TrajectoryMeta (Artifact Metadata)

```python
@dataclass
class TrajectoryMeta:
    """
    Metadata for a trajectory artifact.
    Written alongside the trajectory file(s).
    """
    # === IDENTITY ===
    run_id: str                         # ULID of the run that produced this
    calc_ulid: str                      # Calculation ULID
    step_ulid: str                      # Step ULID that produced trajectory
    
    # === PROVENANCE ===
    engine: str                         # e.g., "qe", "vasp", "lammps", "ase"
    engine_version: Optional[str]       # e.g., "7.2"
    step_type: str                      # e.g., "qe_md", "vasp_md", "lammps_npt"
    input_structure_ulid: str           # ULID of input structure
    
    # === SCHEMA ===
    schema_version: str                 # e.g., "1.0"
    trajectory_type: str                # "md" | "relax" | "neb"
    
    # === DIMENSIONS ===
    n_atoms: int                        # Atoms per frame (constant for trajectory)
    n_frames: int                       # Total frames written
    n_images: Optional[int] = None      # For NEB: number of images
    
    # === OBSERVABLES MANIFEST ===
    available_observables: List[str]    # e.g., ["energy", "forces", "temperature"]
    
    # === STORAGE ===
    format: str                         # "bundle" | "hdf5" | "extxyz" | "json_stream"
    relative_path: str                  # Path relative to raw/, e.g., "trajectory/"
    
    # === TIMESTAMPS ===
    created_at: str                     # ISO 8601
    finalized_at: Optional[str] = None  # Set when trajectory is complete
```

### 3.3 ObservableSeries (For Plotting)

```python
@dataclass
class ObservableSeries:
    """
    A 1D series of scalar values across frames.
    Used for time-series plotting (E(t), T(t), max|F|(t), etc.)
    """
    name: str                           # e.g., "energy", "temperature", "max_force"
    values: NDArray[np.float64]         # Shape (n_frames,)
    unit: str                           # e.g., "eV", "K", "eV/Å"
    
    # For NEB: optionally indexed by (iteration, image)
    # Reshape to (n_iterations, n_images) for NEB analysis
```

---

## 4. Units and Conventions (MANDATORY)

These conventions are **non-negotiable** and must be enforced by parsers.

### 4.1 Units

| Quantity | Unit | Notes |
|----------|------|-------|
| Length (positions, cell) | Å (Ångström) | Constitution §5.3 |
| Energy | eV | |
| Forces | eV/Å | |
| Stress/Pressure | GPa | See §4.2 for sign convention |
| Time | fs (femtoseconds) | |
| Temperature | K (Kelvin) | |
| Velocities | Å/fs | |
| Momenta | amu·Å/fs | Atomic mass units |

**Evidence**: Consistent with ASE (`ase/units.py`) and QMatSuite constitution §5.3.

### 4.2 Stress Tensor Convention

**Layout**: 3×3 symmetric matrix, Cartesian coordinates.

**Sign**: Positive = tensile (material under tension). This matches ASE convention.

**Voigt**: When converting to 6-component Voigt notation:
```
[σ_xx, σ_yy, σ_zz, σ_yz, σ_xz, σ_xy]
```

**Evidence**: `ase/stress.py` lines 6, 61-68 define this mapping.

Utility functions:
```python
def stress_full_to_voigt(stress_3x3: NDArray) -> NDArray:
    """Convert (3,3) stress to (6,) Voigt notation."""
    
def stress_voigt_to_full(stress_voigt: NDArray) -> NDArray:
    """Convert (6,) Voigt to (3,3) full matrix."""
```

### 4.3 Cell Matrix Convention

**Layout**: Cell vectors are **row vectors**.

```python
# cell[i] is the i-th lattice vector
cell = np.array([
    [a_x, a_y, a_z],  # a vector
    [b_x, b_y, b_z],  # b vector  
    [c_x, c_y, c_z],  # c vector
])
```

This matches:
- ASE: `atoms.get_cell()` returns row vectors
- pymatgen: `Structure.lattice.matrix` uses row vectors
- QMatSuite constitution §5 and existing structure handling

### 4.4 Species Convention

Use standard element symbols (e.g., `"Si"`, `"O"`, `"Fe"`), not atomic numbers.

The `species` list must be in atom order matching `positions`.

---

## 5. On-Disk Contract (Storage Layout)

### 5.1 Directory Structure

```
project_root/
└── calculations/
    └── <calc_id>/
        └── raw/
            └── trajectory/
                ├── meta.json              # TrajectoryMeta serialized
                ├── frames/                # Bundle format (recommended)
                │   ├── frame_000000.json
                │   ├── frame_000001.json
                │   └── ...
                └── observables/           # Optional: pre-computed series
                    ├── energy.npy
                    ├── temperature.npy
                    └── max_force.npy
```

### 5.2 Supported Formats

| Format | Extension | Use Case | Random Access |
|--------|-----------|----------|---------------|
| Bundle | `frames/*.json` | Default, debuggable | Yes |
| HDF5 | `.h5` | Large trajectories (>10k frames) | Yes |
| extxyz | `.extxyz` | Interop with ASE/other tools | Sequential |
| JSON stream | `.jsonl` | Append-only, crash recovery | Sequential |

**Recommendation**: Use bundle format by default. Switch to HDF5 for production MD with >10k frames.

### 5.3 Bundle Format Details

Each frame file (`frame_NNNNNN.json`) contains:

```json
{
  "frame_index": 0,
  "positions": [[0.0, 0.0, 0.0], [1.35, 1.35, 1.35], ...],
  "species": ["Si", "Si", ...],
  "cell": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]],
  "pbc": [true, true, true],
  "energy": -158.723,
  "forces": [[-0.001, 0.002, -0.001], ...],
  "temperature": 300.5,
  "extras": {}
}
```

**Evidence**: Inspired by ASE's `BundleTrajectory` (`ase/io/bundletrajectory.py` lines 8-22) which uses per-frame directories for large-scale MD.

### 5.4 Writing Constraints

**Append-only**: Once a frame is written, it is never modified.

**Crash recovery**: Meta is updated after each frame write. On recovery, frames beyond meta.n_frames are ignored/deleted.

**Atomic finalization**: `meta.finalized_at` is set only when trajectory is complete.

### 5.5 Naming Convention

For engines that produce multiple trajectories (e.g., different MD runs):

```
raw/trajectory_{step_ulid}/
```

Or with variant:
```
raw/trajectory_{step_ulid}_{variant}/
```

---

## 6. API Contracts

### 6.1 Reading API

```python
class TrajectoryReader:
    """Read-only access to a trajectory artifact."""
    
    @classmethod
    def open(cls, raw_dir: Path) -> "TrajectoryReader":
        """Open trajectory from raw directory."""
    
    @property
    def meta(self) -> TrajectoryMeta:
        """Trajectory metadata."""
    
    def __len__(self) -> int:
        """Number of frames."""
    
    def __getitem__(self, index: int) -> Frame:
        """Random access to frame by index."""
    
    def __iter__(self) -> Iterator[Frame]:
        """Iterate over all frames (streaming)."""
    
    def get_observable(self, name: str) -> ObservableSeries:
        """Extract a scalar observable series (e.g., 'energy')."""
    
    def slice(self, start: int, stop: int, step: int = 1) -> Iterator[Frame]:
        """Iterate over frame slice."""
```

### 6.2 Writing API

```python
class TrajectoryWriter:
    """Append-only trajectory writer."""
    
    def __init__(
        self,
        raw_dir: Path,
        meta: TrajectoryMeta,
        format: str = "bundle",
    ):
        """Initialize writer. Creates trajectory directory."""
    
    def write_frame(self, frame: Frame) -> None:
        """Append a frame. Updates meta.n_frames."""
    
    def finalize(self) -> None:
        """Mark trajectory as complete. Sets meta.finalized_at."""
    
    def __enter__(self) -> "TrajectoryWriter":
        ...
    
    def __exit__(self, *args) -> None:
        self.finalize()
```

### 6.3 Promote API

```python
def promote_frame(
    project_root: Path,
    trajectory_path: Path,
    frame_index: int,
    name: Optional[str] = None,
) -> str:
    """
    Promote a trajectory frame to a project structure resource.
    
    Args:
        project_root: Project root directory
        trajectory_path: Path to trajectory (raw/trajectory/)
        frame_index: Which frame to promote
        name: Optional name for the new structure
        
    Returns:
        ULID of the created/deduped structure resource
        
    Process:
        1. Load frame
        2. Convert to pymatgen Structure
        3. Canonicalize (constitution §3)
        4. Compute fingerprint (for dedup)
        5. Check if equivalent structure exists (dedup)
        6. If not: create new structure resource with ULID
        7. Record provenance in structure metadata
    """
```

Provenance stored in promoted structure:
```python
{
    "__qv_meta__": {
        "type": "structure",
        "id": "01J...",  # ULID
        "provenance": {
            "source": "trajectory_frame",
            "source_run_id": "01J...",
            "source_trajectory_path": "raw/trajectory/",
            "source_frame_index": 42,
            "promoted_at": "2026-01-19T10:30:00Z",
        }
    }
}
```

---

## 7. Artifact Reference Syntax

### 7.1 Reference Token Format

Following the `@scan:<scan_id>` pattern from `scan_tokens.py`:

```
@traj:<run_id>:<relative_path>#frame=<index>
```

Examples:
```
@traj:01JXXXX:trajectory/#frame=0
@traj:01JXXXX:trajectory/#frame=-1        # last frame
@traj:01JXXXX:trajectory/#frame=10:20     # slice (future)
```

### 7.2 Reference Rules

**INV-R1**: Trajectory references are **calc-scope only**. No cross-calc references.

**INV-R2**: Reference is a **scalar string** (not dict). This preserves StepDoc invariants.

**INV-R3**: References do NOT grant ULID status. The frame remains a non-resource until promoted.

---

## 8. Parser Contract

Each engine needs a parser that converts raw output → trajectory core.

### 8.1 Parser Interface

```python
class TrajectoryParser(Protocol):
    """Contract for engine-specific trajectory parsers."""
    
    engine: str  # e.g., "qe", "vasp", "lammps"
    
    def can_parse(self, raw_dir: Path) -> bool:
        """Check if this parser can handle the raw directory."""
    
    def parse(
        self,
        raw_dir: Path,
        step_ulid: str,
        run_id: str,
        calc_ulid: str,
        input_structure_ulid: str,
    ) -> TrajectoryWriter:
        """
        Parse raw output and write trajectory.
        
        Returns:
            TrajectoryWriter with all frames written
        """
```

### 8.2 Parser Requirements

**MUST provide**:
- `frame_index` (sequential from 0)
- `positions` (in Å)
- `species` (element symbols)
- `cell` (row vectors, in Å)
- `pbc`

**SHOULD provide if available**:
- `energy` (in eV)
- `forces` (in eV/Å)
- `time` (in fs, for MD)
- `iteration` (for relax/NEB)
- `temperature`, `pressure` (if engine computes)

**Parser responsibilities**:
- Unit conversion to canonical units
- Coordinate transformation if needed
- Handle incomplete/crashed runs gracefully

### 8.3 Example: QE MD Parser

```python
def parse_qe_md(raw_dir: Path, ...) -> TrajectoryWriter:
    """Parse QE Car-Parrinello or Born-Oppenheimer MD output."""
    
    # 1. Find output file
    output_file = raw_dir / "md.out"
    
    # 2. Parse frames
    frames = _parse_qe_md_output(output_file)
    
    # 3. Create writer
    meta = TrajectoryMeta(
        run_id=run_id,
        calc_ulid=calc_ulid,
        step_ulid=step_ulid,
        engine="qe",
        step_type="qe_md",
        trajectory_type="md",
        n_atoms=len(frames[0].species),
        n_frames=len(frames),
        available_observables=["energy", "forces", "temperature"],
        format="bundle",
        relative_path="trajectory/",
        ...
    )
    
    writer = TrajectoryWriter(raw_dir, meta)
    for frame in frames:
        writer.write_frame(frame)
    writer.finalize()
    
    return writer
```

---

## 9. MD / Relax / NEB Unified Representation

### 9.1 MD (Molecular Dynamics)

- `trajectory_type = "md"`
- `time` field is populated (fs)
- `iteration` may also be set (step number)
- `velocities`/`momenta` typically available
- `temperature`, `pressure` for thermostated ensembles

### 9.2 Relax (Geometry Optimization)

- `trajectory_type = "relax"`
- `time` is typically None
- `iteration` is the optimization step (0, 1, 2, ...)
- `energy` decreases over iterations (for converging optimization)
- `forces` shows convergence via max|F|

**Relationship to existing relax artifact**:

Current `generated_structures/step_<ulid>/current.json` stores only the **final** structure.

Trajectory stores the **full optimization path**. The final frame equals current.json.

Migration path: Relax handlers can optionally write trajectory AND current.json for backward compatibility.

### 9.3 NEB (Nudged Elastic Band)

- `trajectory_type = "neb"`
- `n_images` in meta (e.g., 7 images)
- Frames have `image_index` field (0 to n_images-1)

**Storage layout**: Frames are stored sequentially with alternating images per iteration:

```
iteration 0: [image_0, image_1, ..., image_6]  → frame_index 0-6
iteration 1: [image_0, image_1, ..., image_6]  → frame_index 7-13
...
```

**Reconstruction**:
```python
def get_neb_frame(traj: TrajectoryReader, iteration: int, image: int) -> Frame:
    n_images = traj.meta.n_images
    frame_index = iteration * n_images + image
    return traj[frame_index]

def get_neb_iteration(traj: TrajectoryReader, iteration: int) -> List[Frame]:
    n_images = traj.meta.n_images
    start = iteration * n_images
    return [traj[start + i] for i in range(n_images)]
```

**Energy profile**: Extract energy vs image for each iteration:
```python
def neb_energy_profile(traj: TrajectoryReader, iteration: int) -> NDArray:
    frames = get_neb_iteration(traj, iteration)
    return np.array([f.energy for f in frames])
```

**Evidence**: ASE's NEB (`ase/mep/neb.py` lines 53-82) stores images as a list and tracks energies per image.

---

## 10. What We Explicitly Do NOT Do (Non-Goals)

### 10.1 No ASE Atoms/Calculator Dependency

We do NOT import or depend on ASE's `Atoms` class or `Calculator` interface at the core level.

**Rationale**: 
- ASE's `Atoms` includes calculator binding, constraint system, and caching that we don't need
- We want a minimal data representation, not a full simulation object
- Parsers MAY use ASE internally for reading formats, but core representation is independent

**Evidence**: `docs/research/ASE_ARCHITECTURE_REPORT.md` §C.6 recommends using ASE as middleware, not as core dependency.

### 10.2 No Algorithm Implementation

We do NOT implement:
- MD integrators (Verlet, Langevin, etc.)
- Optimizers (BFGS, FIRE, etc.)
- NEB algorithms
- Thermostats/barostats

These remain in engines.

### 10.3 No Global Trajectory Registry

Trajectories are NOT:
- Indexed in ResourceIndex
- Globally discoverable via scan
- Cross-calc referenceable

### 10.4 No Automatic Structure Promotion

We do NOT automatically promote frames to project structures. This requires explicit user action.

### 10.5 No IO Format Registry (Initially)

Unlike ASE's `ase.io.formats` registry, we start with explicit format handling. If we need dynamic format discovery later, we'll add it.

---

## 11. Testing Invariants

These MUST be tested for any parser/writer implementation:

### 11.1 Schema Consistency

| ID | Invariant | Test |
|----|-----------|------|
| T1 | `n_atoms` constant across frames | `assert all(len(f.positions) == meta.n_atoms for f in traj)` |
| T2 | `species` length matches `n_atoms` | `assert all(len(f.species) == meta.n_atoms for f in traj)` |
| T3 | `positions` shape is (n_atoms, 3) | `assert all(f.positions.shape == (meta.n_atoms, 3) for f in traj)` |
| T4 | `cell` shape is (3, 3) | `assert all(f.cell.shape == (3, 3) for f in traj)` |
| T5 | `pbc` length is 3 | `assert all(len(f.pbc) == 3 for f in traj)` |

### 11.2 Index/Ordering

| ID | Invariant | Test |
|----|-----------|------|
| T6 | `frame_index` is sequential from 0 | `assert [f.frame_index for f in traj] == list(range(len(traj)))` |
| T7 | `time` is non-decreasing (if present) | `assert all(t1 <= t2 for t1, t2 in zip(times, times[1:]))` |
| T8 | NEB: `image_index` in [0, n_images-1] | `assert all(0 <= f.image_index < meta.n_images for f if f.image_index)` |

### 11.3 Units

| ID | Invariant | Test |
|----|-----------|------|
| T9 | Energy in reasonable eV range | `assert all(-1e6 < f.energy < 1e6 for f if f.energy)` |
| T10 | Forces finite | `assert all(np.isfinite(f.forces).all() for f if f.forces)` |
| T11 | Temperature non-negative | `assert all(f.temperature >= 0 for f if f.temperature)` |

### 11.4 Promote Consistency

| ID | Invariant | Test |
|----|-----------|------|
| T12 | Promoted structure matches frame | Compare positions/cell/species |
| T13 | Promote is idempotent (dedup) | Same frame → same ULID (if fingerprint matches) |
| T14 | Provenance recorded | `promoted_structure.__qv_meta__["provenance"]["source"] == "trajectory_frame"` |

### 11.5 Parser Contract

| ID | Invariant | Test |
|----|-----------|------|
| T15 | Parser provides required fields | All frames have positions/species/cell/pbc |
| T16 | `available_observables` accurate | If "energy" listed, all frames have energy |
| T17 | Parser handles incomplete runs | Truncated output → partial trajectory, no crash |

---

## 12. Implementation Phases (Outline)

**Phase 1: Core Data Model**
- Define Frame, TrajectoryMeta, ObservableSeries dataclasses
- Implement TrajectoryReader/Writer for bundle format
- Unit tests for schema invariants

**Phase 2: First Parser (QE MD)**
- Implement QE MD output parser
- Integration test with real QE output
- Validate observable extraction

**Phase 3: Relax Integration**
- Extend existing relax handlers to optionally write trajectory
- Backward compatibility with current.json pattern

**Phase 4: UI/Visualization**
- Trajectory frame viewer
- Observable time-series plots
- Animation support

**Phase 5: Additional Parsers**
- VASP MD/relax parser
- LAMMPS parser
- NEB support

**Phase 6: Promote and HDF5**
- Implement promote_frame API
- HDF5 format for large trajectories

---

## 13. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema needs breaking changes | High | Version in meta; write migration tools; extensive initial design |
| Large trajectories slow | Medium | HDF5 format; lazy loading; streaming API |
| Engine atom reordering | Medium | `atom_ids` field; parser documents behavior |
| Unit confusion | High | Strict parser testing; unit in field name comments |
| NEB 2D complexity | Medium | Clear reconstruction API; dedicated NEB utilities |

---

## 14. Open Questions / Decisions Needed

**OQ-1: schema_version naming**  
Use semantic versioning (e.g., "1.0.0") or date-based (e.g., "2026-01-19")?

**Recommendation**: Semantic versioning for clarity on breaking changes.

**OQ-2: Stress sign convention verification**  
Need to verify each engine's stress sign and document parser conversion.

**Action**: Create stress convention test matrix during Phase 2.

**OQ-3: HDF5 chunk size**  
For HDF5 format, what chunk size optimizes both sequential and random access?

**Action**: Benchmark with real MD trajectories during Phase 6.

**OQ-4: Observable pre-computation**  
Should parsers pre-compute common observables (E, T, max|F|) as .npy files?

**Recommendation**: Yes, for plotting efficiency. Make optional.

**OQ-5: Trajectory deletion policy**  
Should trajectories be automatically deleted after N days? Or keep indefinitely?

**Recommendation**: User choice. Default: keep indefinitely (raw is user's sandbox).

**OQ-6: Multi-trajectory per step**  
Some engines produce multiple trajectories per step (e.g., replica exchange). How to handle?

**Recommendation**: Use `trajectory_{step_ulid}_{variant}/` naming. Defer full design to Phase 5.

---

## Appendix A: ASE Evidence Summary

Key patterns adopted from ASE (with file references):

| Pattern | ASE Location | Adoption |
|---------|--------------|----------|
| Trajectory stores calc properties | `ase/io/trajectory.py:187-207` | ✅ Frame has energy/forces/stress |
| Bundle for large MD | `ase/io/bundletrajectory.py:8-22` | ✅ Bundle format |
| Voigt stress convention | `ase/stress.py:6,61-68` | ✅ Same ordering |
| Cell as row vectors | `ase/atoms.py` (`get_cell()`) | ✅ Same convention |
| SinglePointCalculator for replay | `ase/io/trajectory.py:287-301` | ❌ Not needed (no Calculator) |
| NEB as image list | `ase/mep/neb.py:53-82` | ✅ image_index in Frame |

Patterns explicitly NOT adopted:

| Pattern | Reason |
|---------|--------|
| Atoms class dependency | We want minimal data-only representation |
| Calculator interface | Engines handle computation |
| Constraints system | Engine-specific |
| IO format registry | Overkill for initial scope |

---

## Appendix B: QMatSuite Evidence Summary

| Existing Pattern | Location | How Trajectory Extends It |
|------------------|----------|---------------------------|
| Relax artifacts in calc-scope | `src/quantumvitas/execution/relax_artifacts.py:24-82` | Trajectory is multi-frame artifact with same scope |
| Provenance tracking | `RELAX_SPEC.md` §3.1 | TrajectoryMeta includes run_id, calc_ulid, step_ulid |
| Structure fingerprint | `src/quantumvitas/core/structure_fingerprint.py` | promote_frame uses same fingerprinting |
| Raw sandbox contract | `docs/JOB_IO_DIRECTORY_SEMANTICS.md` | Trajectory in raw/trajectory/ |
| @scan: token pattern | `src/quantumvitas/calculation/scan_tokens.py` | @traj: follows same scalar-string pattern |
| ULID for resources | `src/quantumvitas/core/resources.py:40-42` | Frames get ULID only after promote |

---

**End of Specification**

