# Trajectory / Time-Series Analysis Design Document

**Status:** Design Document (not implementation plan)
**Domain:** Analysis pipeline — trajectory / time-series
**Predecessor:** Multi-engine bands/DOS/PDOS/fatbands matrix (closed, 4767+ tests)

---

## Table of Contents

1. [What Is "Trajectory"?](#1-what-is-trajectory)
   - 1.1 [Definition & Scope](#11-definition--scope)
   - 1.2 [External Codebase Survey](#12-external-codebase-survey)
   - 1.3 [Coordinate Conventions](#13-coordinate-conventions)
   - 1.4 [Per-Frame Observable Taxonomy](#14-per-frame-observable-taxonomy)
   - 1.5 [Engine Output File Taxonomy](#15-engine-output-file-taxonomy)
2. [QMatSuite Current State — Deep Audit](#2-qmatsuite-current-state--deep-audit)
   - 2.1 [Data Model](#21-data-model)
   - 2.2 [Parser Architecture](#22-parser-architecture)
   - 2.3 [Engine Parser Status Matrix](#23-engine-parser-status-matrix)
   - 2.4 [Convergence–Trajectory Boundary](#24-convergencetrajectory-boundary)
   - 2.5 [VASP Parser as Template](#25-vasp-parser-as-template)
3. [Proposed Design](#3-proposed-design)
   - 3.1 [Engine x Trajectory-Type Matrix](#31-engine-x-trajectory-type-matrix)
   - 3.2 [Frame Model Assessment](#32-frame-model-assessment)
   - 3.3 [Parser Architecture Per Engine](#33-parser-architecture-per-engine)
   - 3.4 [Molecular Engine Trajectory](#34-molecular-engine-trajectory)
   - 3.5 [Memory Management](#35-memory-management)
   - 3.6 [Transform Extensions](#36-transform-extensions)
   - 3.7 [AnalysisCapability Declarations](#37-analysiscapability-declarations)
   - 3.8 [Priority & Phasing](#38-priority--phasing)

---

## 1. What Is "Trajectory"?

### 1.1 Definition & Scope

A **trajectory** is an ordered sequence of atomic configurations along a physical or optimization path. Each frame records atomic positions and (optionally) per-frame scalar observables (energy, temperature, pressure) and per-atom vector observables (forces, velocities, momenta).

**Three trajectory types:**

| Type | Physical meaning | X-axis | Typical observables |
|------|-----------------|--------|-------------------|
| **MD** | Molecular dynamics time evolution | Time (fs) | Energy, temperature, pressure, KE, velocities |
| **Relax** | Geometry optimization (ionic steps) | Iteration | Energy, forces, stress |
| **NEB** | Nudged elastic band (reaction path) | Image index | Energy, forces |

**Boundary with Convergence:** Convergence tracks electronic (SCF) and ionic solver progress — whether the self-consistent loop and ionic optimizer actually converged. Trajectory tracks the resulting physical evolution of atomic positions. A relaxation run produces *both*: a Convergence object monitoring SCF/ionic loop convergence, and a Trajectory recording how atoms moved between ionic steps. They share energy data at the ionic level, but Convergence also captures inner SCF loop detail (every electronic step, dE per step) that Trajectory does not. Conversely, Trajectory carries full geometry data (positions, cell, forces) that Convergence does not.

**What trajectory is NOT:**
- Not a scalar convergence monitor (that is `Convergence`)
- Not a band structure along k-path (that is `BandStructure`)
- Not a density of states (that is `DOS`)
- Not a 3D field (that is `Field3D`)

### 1.2 External Codebase Survey

#### 1.2.1 ASE (Atomic Simulation Environment)

ASE provides four trajectory file formats, each with distinct on-disk representations:

**Native `.traj` (ULM binary format):**
- Binary data with custom ULM (Unified Logfile Manager) backend
- Magic: `"- of Ulm"` (8 bytes) + tag + version + JSON header + binary frames
- Per-frame: positions (Nx3), cell (3x3), PBC (3-bool), atomic numbers, momenta, charges
- Calculator results attached via `SinglePointCalculator`: energy, forces, stress (Voigt 6-element), dipole, magmoms
- Offset table at EOF enables O(1) random access to any frame

**Bundle directory format (`.bundle/`):**
- Directory-per-frame: `F0/`, `F1/`, ... each containing `smalldata.ulm` + large arrays
- Supports `'once'` write-mode for data constant across frames (numbers, masses)
- Designed for very large MD runs (avoids single giant file)

**NetCDF format (`.nc`):**
- HDF5/NetCDF4 backend with dimensions: frame, spatial(3), atom
- Variables: `coordinates(frame,atom,3)`, `cell_lengths(frame,3)`, `cell_angles(frame,3)`, `velocities`, `time`
- Chunk-based reading (`chunk_size` parameter) for memory control

**Pickle format (deprecated):** Legacy Python pickle, replaced by ULM.

**Key API patterns:**
```
traj = Trajectory('file.traj')
traj[i]        -> Atoms object (lazy load)
traj[i:j:k]   -> SlicedTrajectory (lazy)
len(traj)      -> frame count
for atoms in traj: ...  # sequential iteration
iread('file.traj')  # streaming iterator, minimal memory
```

**Coordinate convention:** Cartesian Angstrom internally. Fractional available via `get_scaled_positions()` (computed on the fly from cell).

**Units:** eV (energy), eV/A (forces), eV/A^3 (stress, Voigt), A/fs (velocities stored as momenta), amu (masses).

**Memory management:**
- Frame-by-frame lazy loading via ULM offsets
- `iread()` generator for sequential streaming with O(1) memory
- No frame caching in reader (each `traj[i]` re-reads from disk)

#### 1.2.2 pymatgen

**`Trajectory` class** (`pymatgen.core.trajectory`):
- Universal container for both `Structure`-based (periodic) and `Molecule`-based (non-periodic) systems
- Core layout: `coords` as `(M, N, 3)` numpy array — M frames, N atoms, 3 coordinates
- `species: list[N]` — constant across all frames (no atom insertion/deletion)
- `lattice`: single `(3,3)` if `constant_lattice=True`, or `(M, 3, 3)` if variable
- `frame_properties: list[M dicts]` — per-frame scalars (energy, pressure, etc.)
- `site_properties: dict | list[dict]` — per-atom properties (forces, velocities, magmoms)
- `coords_are_displacement: bool` — displacement mode stores deltas, reconstructed via cumsum
- `time_step: float | None` — MD time step in fs

**File format readers:**
- `from_file(filename)` — auto-detects XDATCAR, vasprun.xml, ASE `.traj`, JSON
- `from_structures(list[Structure])` — batch constructor
- `from_molecules(list[Molecule])` — batch constructor for molecular codes
- `Xdatcar(filename)` — dedicated VASP XDATCAR reader with streaming line-by-line parser

**Per-frame access:**
```
traj[i]       -> Structure or Molecule
traj[i:j:k]  -> new Trajectory (sliced)
traj[[1,3,5]] -> fancy indexing
for struct in traj: ...
```

**Coordinate convention:** Fractional for Structure-based (periodic), Cartesian for Molecule-based.

**VASP-specific:** `Vasprun.get_trajectory()` extracts `ionic_steps[i]["structure"]` + `ionic_steps[i]["forces"]` as site_properties, returns `Trajectory` with `constant_lattice=False`.

#### 1.2.3 AiiDA

**`TrajectoryData` node** (`aiida.orm.nodes.data.array.trajectory`):
- "World-independent" stored arrays persisted in AiiDA database
- Core arrays: `positions(steps, natoms, 3)`, `steps(steps,)`, `cells(steps, 3, 3)`, `times(steps,)`, `velocities(steps, natoms, 3)`
- Metadata attributes: `symbols: list[natoms]`, `units|positions: 'A'`, `units|times: 'ps'`
- Per-frame access: `get_step_data(idx)` returns tuple of `(stepid, time, cell, symbols, positions, velocities)`
- Provenance-tracked via node graph (parents/children links)
- Export: XSF (XCrySDen), CIF for single frames

**Key difference from pymatgen:** Separate named arrays per property (AiiDA approach) vs. attached per-frame dicts (pymatgen approach). QMatSuite's `Frame` dataclass uses the explicit-field approach (closer to AiiDA but with typed fields instead of generic arrays).

#### 1.2.4 py4vasp

- Lazy HDF5 slicing: loads frames on demand from `vasprun.xml` converted to HDF5
- Frame-on-demand pattern: no full trajectory in memory
- VASP-specific — not a general-purpose trajectory library

### 1.3 Coordinate Conventions

All reference libraries (ASE, pymatgen, AiiDA, py4vasp) store positions as Cartesian Angstrom internally, with optional fractional-coordinate accessors. QMatSuite follows this convention:

**QMatSuite standard:** `Frame.positions` stores UNWRAPPED Cartesian coordinates in Angstrom (A). Conversion from fractional to Cartesian happens at parse time.

**Per-engine conversion requirements:**

| Engine | Native coord system | Conversion |
|--------|-------------------|------------|
| VASP | Fractional | `frac_coords @ lattice` at parse time |
| QE | `crystal` (frac), `bohr`, `angstrom`, `alat` | Unit-dependent at parse time |
| ABINIT | Fractional (`xred`) or Cartesian (`xcart` in Bohr) | Bohr->A: * 0.529177 |
| CP2K | Cartesian A (in XYZ trajectory files) | Direct |
| LAMMPS | Cartesian A (or scaled in dump) | Box-dependent |
| Siesta | Fractional or Cartesian (Bohr) | Bohr->A: * 0.529177 |
| GPAW | Cartesian A (ASE convention) | Direct |
| xTB | Cartesian A (XYZ format) | Direct |
| ORCA | Cartesian A | Direct (molecular, no cell) |
| Gaussian | Cartesian A | Direct (molecular, no cell) |

**Cell convention:** `(3, 3)` numpy array in Angstrom, row-major (lattice vectors as rows). `None` for molecular systems without periodic boundary conditions.

### 1.4 Per-Frame Observable Taxonomy

| Observable | Field | Type | Unit | Engines that produce it |
|-----------|-------|------|------|----------------------|
| Energy | `energy` | `float` | eV | ALL (universal) |
| Forces | `forces` | `(N,3)` | eV/A | VASP, QE, ABINIT, CP2K, LAMMPS, Siesta, GPAW, xTB, ORCA, Gaussian |
| Stress | `stress` | `(3,3)` | GPa | VASP, QE, ABINIT, CP2K, LAMMPS, Siesta |
| Temperature | `temperature` | `float` | K | VASP(MD), QE(MD), ABINIT(MD), CP2K(MD), LAMMPS(MD), Siesta(MD), GPAW(MD) |
| Pressure | `pressure` | `float` | GPa | VASP(MD), QE(MD), ABINIT(MD), CP2K(MD), LAMMPS, Siesta |
| Kinetic energy | `kinetic_energy` | `float` | eV | VASP(MD), QE(MD), CP2K(MD), LAMMPS(MD), GPAW(MD) |
| Velocities | `velocities` | `(N,3)` | A/fs | VASP(MD), QE(MD), LAMMPS(MD), Siesta(MD) |
| Momenta | `momenta` | `(N,3)` | amu*A/fs | ASE-based engines (GPAW) |
| Cell | `cell` | `(3,3)` | A | All periodic engines (per-frame for vc-relax/NPT) |
| Time | `time` | `float` | fs | All MD-capable engines |
| Iteration | `iteration` | `int` | — | All relax-capable engines |
| Image index | `image_index` | `int` | — | QE(NEB), VASP(NEB) |

### 1.5 Engine Output File Taxonomy

Complete mapping of trajectory-producing output files across all 15 engines:

| Engine | Trajectory output files | Format | Content |
|--------|----------------------|--------|---------|
| **VASP** | `vasprun.xml` | XML (iterparse-friendly) | Full: positions, cell, energy, forces, stress per `<calculation>` |
| | `XDATCAR` | Text (line-per-atom) | Positions only (fractional), per-frame lattice optional |
| | `OSZICAR` | Text (line-per-step) | Energies per ionic step (fallback for XDATCAR) |
| **QE** | `*.relax.out` / `*.vc-relax.out` | Embedded text | ATOMIC_POSITIONS + CELL_PARAMETERS + energies per BFGS step |
| | `*.md.out` | Embedded text | Same blocks but with time steps (stub parser) |
| **ABINIT** | `*o_HIST.nc` | NetCDF binary | Full trajectory: positions, cell, forces, stress, energy per step |
| | `*.abo` | Text | Embedded ionic steps with positions, cell, energy, forces |
| **CP2K** | `*-pos-*.xyz` | Extended XYZ | Positions per frame (Cartesian A) |
| | `*-frc-*.xyz` | Extended XYZ | Forces per frame (atomic units) |
| | `*-1.cell` | Text | Cell vectors per frame |
| | `*.ener` | Text (columnar) | Step, time, KE, temperature, PE, conserved, volume, pressure |
| **LAMMPS** | `*.lammpstrj` / `dump.*` | LAMMPS dump text | Configurable columns: id, type, x, y, z, vx, vy, vz, fx, fy, fz |
| | `log.lammps` | Text (thermo output) | Step, temp, PE, KE, press, volume, etc. |
| **Siesta** | `*.MDE` | Text (columnar) | Step, temperature, E_KS, E_total, volume, pressure |
| | `*.XV` | Text (per-step) | Positions + velocities per step |
| | `*.ANI` | XYZ animation | Multi-frame XYZ (positions only) |
| | `*.STRUCT_OUT` | Text | Final structure only |
| **GPAW** | `relax.traj` / `md.traj` | ASE binary (.traj/ULM) | Full Atoms objects: positions, cell, energy, forces |
| | `opt.log` | Text | Optimizer log (step, energy, fmax) |
| **xTB** | `xtbopt.log` | Multi-frame XYZ | Optimization trajectory (positions per step) |
| | `xtb.trj` | Multi-frame XYZ | MD trajectory |
| | `xtbopt.xyz` | XYZ | Final optimized geometry |
| **ORCA** | `*.xyz` | Multi-frame XYZ | Optimization trajectory (positions per step) |
| | `*.engrad` | Text | Energies + gradients per step |
| | `*.out` | Embedded text | Geometry optimization steps with energies and coordinates |
| **Gaussian** | `*.log` | Embedded text | Standard orientation geometry + energies per optimization step |
| | `*.chk` | Binary (Fortran) | Full checkpoint (not directly parseable without formchk) |
| **W90** | — | — | N/A (postprocessing engine, no trajectory) |
| **Psi4** | `results.json` / `*.out` | Text | Optimization energies/geometries in output |
| **PySCF** | `*.out` / `*.chk` | Text/Binary | Optimization geometries in output |
| **QMCPACK** | — | — | N/A (fixed nuclei QMC, no trajectory) |
| **Yambo** | — | — | N/A (MBPT postprocessing, no trajectory) |

---

## 2. QMatSuite Current State — Deep Audit

### 2.1 Data Model

#### Frame (16 fields)

`src/quantumvitas/core/analysis/trajectory/model.py`

```
@dataclass
class Frame:
    # Required (5)
    frame_index: int
    positions: np.ndarray              # (N, 3) UNWRAPPED Cartesian A
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]

    # Time/iteration axis (2)
    time: Optional[float] = None       # fs (MD)
    iteration: Optional[int] = None    # relax/NEB

    # Observables (7)
    energy: Optional[float] = None             # eV
    forces: Optional[np.ndarray] = None        # (N, 3) eV/A
    temperature: Optional[float] = None        # K
    pressure: Optional[float] = None           # GPa
    stress: Optional[np.ndarray] = None        # (3, 3) GPa
    kinetic_energy: Optional[float] = None     # eV
    velocities: Optional[np.ndarray] = None    # (N, 3) A/fs
    momenta: Optional[np.ndarray] = None       # (N, 3) amu*A/fs

    # NEB (1)
    image_index: Optional[int] = None

    # Identity (1)
    atom_ids: Optional[List[str]] = None
```

**Validation in `__post_init__`:** cell/pbc consistency, positions shape `(N, 3)`, species count == atom count.

**Properties:** `n_atoms` (derived from species length).

**Serialization:** `to_dict()` / `from_dict()` for JSON round-trip (numpy arrays via `.tolist()`).

#### Trajectory (4 fields + rich API)

```
@dataclass
class Trajectory:
    meta: AnalysisObjectMeta
    frames: List[Frame]
    trajectory_type: str              # "md" | "relax" | "neb"
    n_images: Optional[int] = None    # NEB only
```

**Properties:** `n_frames`, `n_atoms`.

**Iteration:** `__len__`, `__getitem__`, `__iter__` — trajectory behaves like a list of frames.

**Observable extraction:** `get_observable_series(name)` returns `Series1D` for `"energy"`, `"temperature"`, `"pressure"`, `"max_force"`, or `None`. X-axis is time (fs) for MD, iteration for relax/NEB, with fallback to frame index.

**Available observables:** `get_available_observables()` checks first frame, returns list of `["energy", "temperature", "pressure", "max_force", "kinetic_energy"]` based on what fields are non-None.

**Primitives bridge:** `to_primitives()` produces a `CanonicalPrimitiveBundle` containing:
- `geometry_frames: GeometryFrames` — positions, species, cell, pbc, forces, velocities per frame
- `series: List[Series1D]` — one series per available observable
- `arrays: {}` — empty (unlike Convergence which populates arrays)
- `render_meta` — axis labels, units, trajectory_type/n_frames/n_atoms/n_images in `extra`
- `provenance_meta` — from `AnalysisObjectMeta`

#### GeometryFrame (6 fields) — Primitive subset of Frame

`src/quantumvitas/core/analysis/primitives.py`

```
@dataclass
class GeometryFrame:
    positions: np.ndarray              # (N, 3) Cartesian A
    species: List[str]
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]
    forces: Optional[np.ndarray] = None
    velocities: Optional[np.ndarray] = None
```

`GeometryFrame` strips all scalar observables, time/iteration, NEB index, and atom_ids from `Frame`. It is purely geometric data for visualization.

`GeometryFrames` wraps `List[GeometryFrame]` with optional `time`, `iteration`, and `image_indices` arrays.

### 2.2 Parser Architecture

The trajectory parser pipeline follows the same evidence-based dispatch used for all analysis types:

```
Engine driver declares ANALYSIS_CAPABILITIES
    |
    v
run_post_run_analysis() matches gen_steps -> AnalysisCapability
    |
    v
get_parser(engine, "trajectory") -> registered provider class
    |
    v
provider.can_parse(raw_dir) -> bool
    |
    v
provider.parse(evidence: EvidenceBundle) -> Trajectory
    |
    v
trajectory.to_primitives() -> CanonicalPrimitiveBundle
```

**Registration:** `@register_parser("engine", "trajectory")` in `src/quantumvitas/parsers/registry.py`.

**EvidenceBundle** (8 fields): `primary_raw_dir`, `calc_dir`, `run_ulid`, `calc_ulid`, `step_ulids`, `gen_steps`, `engine_name`, `evidence_steps`.

**AnalysisCapability** (3 fields): `object_type`, `gen_step_sequence`, `evidence_files`.

**Dispatch rule:** Longest `gen_step_sequence` match wins. One match per `object_type`. Contiguous sliding-window matching against ordered gen steps.

### 2.3 Engine Parser Status Matrix

| Engine | `@register_parser` trajectory? | `ANALYSIS_CAPABILITIES` trajectory? | Parse functions | Status |
|--------|:---:|:---:|---|---|
| **VASP** | YES | YES (relax + md) | `parse_vasprun_trajectory` (iterparse), `parse_xdatcar` (fallback), `_parse_oszicar_energies` | **COMPLETE** |
| **QE** | YES | YES (relax only) | `_parse_relax_output` (regex), `_parse_md_output` (stub: returns `[]`) | **PARTIAL** — MD stub, relax works |
| **ABINIT** | NO | NO | None | **MISSING** — has `*o_HIST.nc` but no parser |
| **CP2K** | NO | NO | None (handler has `RelaxArtifactSpec` only) | **MISSING** — has `*-pos-*.xyz`, `*-frc-*.xyz` |
| **ORCA** | NO | NO (no ANALYSIS_CAPABILITIES at all) | None | **MISSING** — opt trajectory in `*.xyz` / `*.out` |
| **Gaussian** | NO | NO (no ANALYSIS_CAPABILITIES at all) | None | **MISSING** — opt steps in `*.log` |
| **LAMMPS** | NO | NO (has `"trajectory"` in `get_capabilities()` set only) | None | **MISSING** — `*.lammpstrj` + `log.lammps` |
| **Siesta** | NO | NO | `parse_mde_file()` — raw dict, scalars only, NO positions | **PARTIAL** — thermodynamics only |
| **GPAW** | NO | NO | None (writer creates ASE `.traj`) | **MISSING** — `relax.traj` / `md.traj` exist |
| **xTB** | NO | NO | None (artifact pattern: `xtbopt.log`) | **MISSING** — `xtbopt.log` / `xtb.trj` XYZ |
| **W90** | N/A | N/A | N/A | **N/A** — postprocessing engine |
| **Psi4** | NO | NO | None | **LOW PRIORITY** — molecular opt output |
| **PySCF** | NO | NO | None | **LOW PRIORITY** — molecular opt output |
| **QMCPACK** | N/A | N/A | N/A | **N/A** — fixed nuclei QMC |
| **Yambo** | N/A | N/A | N/A | **N/A** — MBPT postprocessing |

**Summary:** 2 registered (VASP complete, QE partial), 8 missing but capable (ABINIT, CP2K, LAMMPS, Siesta, GPAW, xTB, ORCA, Gaussian), 2 low priority (Psi4, PySCF), 3 not applicable (W90, QMCPACK, Yambo).

**QE parser signature mismatch:** QE's `parse()` takes `(raw_dir, calc_dir, *, run_ulid, step_ulids, gen_steps, calc_ulid, engine_name)` directly, while VASP takes `(evidence: EvidenceBundle)`. The QE parser predates the `EvidenceBundle` API and needs updating to match.

### 2.4 Convergence–Trajectory Boundary

#### Convergence model (9 fields)

`src/quantumvitas/core/analysis/convergence/model.py`

```
@dataclass
class Convergence:
    meta: AnalysisObjectMeta
    scf_step: np.ndarray       # int[n_total_scf], cumulative
    scf_energy: np.ndarray     # float[n_total_scf], eV
    scf_de: np.ndarray         # float[n_total_scf], energy change per step
    ionic_step: np.ndarray     # int[n_ionic]
    ionic_energy: np.ndarray   # float[n_ionic], eV
    ionic_max_force: Optional[np.ndarray] = None  # float[n_ionic], eV/A
    converged: bool = False
    n_ionic_steps: int = 0
    algorithm: str = ""
```

#### Overlap analysis

| Data | Trajectory | Convergence | Notes |
|------|:---:|:---:|---|
| Ionic energy | YES (`frame.energy`) | YES (`ionic_energy`) | Same data, different context |
| Ionic max force | YES (`get_observable_series("max_force")`) | YES (`ionic_max_force`) | Same data |
| SCF energy (every electronic step) | NO | YES (`scf_energy`) | Convergence-exclusive |
| SCF dE | NO | YES (`scf_de`) | Convergence-exclusive |
| Converged flag | NO | YES | Convergence-exclusive |
| Algorithm name | NO | YES | Convergence-exclusive |
| Atomic positions | YES (`frame.positions`) | NO | Trajectory-exclusive |
| Cell vectors | YES (`frame.cell`) | NO | Trajectory-exclusive |
| Forces (N,3) | YES (`frame.forces`) | NO (only max_force scalar) | Trajectory has full tensor |
| Stress tensor | YES (`frame.stress`) | NO | Trajectory-exclusive |
| Temperature | YES (`frame.temperature`) | NO | Trajectory-exclusive (MD) |
| Velocities | YES (`frame.velocities`) | NO | Trajectory-exclusive (MD) |

#### Proposed delineation

The current boundary is clean and should be preserved:

- **Convergence** = "Did the solver converge?" — monitors every SCF iteration, tracks convergence status, algorithm. No geometry data.
- **Trajectory** = "How did atoms move?" — records geometry evolution, physical observables per ionic step. No inner SCF loop detail.

A relaxation produces both objects from the same run. They are independent: neither depends on the other's output. They share the same `ANALYSIS_CAPABILITIES` gen_step match (e.g., both match `gen_step_sequence=["relax"]`). The orchestrator already handles this via per-object_type dispatch — trajectory and convergence are different `object_type` values, each matched independently.

**No merging recommended.** The separation is clean, each serves a distinct visualization purpose, and the data overlap (ionic energy) is small enough that duplication is acceptable.

### 2.5 VASP Parser as Template

The VASP trajectory parser (`src/quantumvitas/drivers/vasp/parsers/trajectory.py`, 300 lines) is the template for all future engine trajectory parsers.

**Architecture:**

1. **Standalone parse functions** (reusable, no class state):
   - `parse_vasprun_trajectory(path) -> dict` — streaming iterparse of XML
   - `parse_xdatcar(path) -> dict` — text line-by-line
   - `_parse_oszicar_energies(path) -> List[float]` — auxiliary

2. **Provider class** (`VASPTrajectoryProvider`):
   - `can_parse(raw_dir) -> bool` — checks file existence
   - `parse(evidence: EvidenceBundle) -> Trajectory` — orchestrates parse functions, builds `Frame` objects, constructs `AnalysisObjectMeta`

3. **Primary/fallback pattern**:
   - Primary: `vasprun.xml` (full data: positions + cell + energy + forces + stress)
   - Fallback: `XDATCAR` + `OSZICAR` (positions + energies only)
   - Size warning: logs warning if `vasprun.xml` > 100 MB and fallback exists

4. **Memory management via iterparse**:
   - Uses `ET.iterparse(path, events=("end",))` to stream XML elements
   - Calls `elem.clear()` after processing each `<calculation>` block
   - Avoids loading entire DOM into memory (critical for large MD runs with 100k+ frames)

5. **Coordinate conversion at parse time**:
   - VASP stores fractional coordinates → `frac_coords @ lattice` → Cartesian
   - All `Frame.positions` stored as Cartesian A

6. **Trajectory type detection**:
   - If any `gen_step` contains `"md"` → type `"md"`
   - Otherwise → type `"relax"`

**Key qualities to replicate:**
- Standalone parse functions separate from provider class
- `EvidenceBundle`-based API (not ad-hoc keyword arguments like QE)
- Primary + fallback file strategy
- Streaming parse for large files
- Coordinate conversion at parse time
- Registration via `@register_parser`

---

## 3. Proposed Design

### 3.1 Engine x Trajectory-Type Matrix

For each engine, whether trajectory parsing should be implemented for each trajectory type:

| Engine | relax | md | vc-relax | neb | Notes |
|--------|:---:|:---:|:---:|:---:|---|
| **VASP** | DONE | DONE | DONE (same as relax) | DEFER | NEB via VTST plugin, low priority |
| **QE** | DONE | IMPLEMENT | DONE (same as relax) | IMPLEMENT | MD stub exists, NEB via neb.x |
| **ABINIT** | IMPLEMENT | IMPLEMENT | IMPLEMENT | N/A | All via `*o_HIST.nc` or `.abo` text |
| **CP2K** | IMPLEMENT | IMPLEMENT | IMPLEMENT | IMPLEMENT (CI-NEB) | Via `*-pos-*.xyz` + `*.ener` + `*-frc-*.xyz` |
| **LAMMPS** | IMPLEMENT | IMPLEMENT | N/A | N/A | Via `*.lammpstrj` + `log.lammps` |
| **Siesta** | IMPLEMENT | IMPLEMENT | IMPLEMENT | N/A | Via `*.ANI` + `*.MDE` + `*.XV` |
| **GPAW** | IMPLEMENT | IMPLEMENT | N/A | N/A | Via ASE `.traj` binary (need ase dependency) |
| **xTB** | IMPLEMENT | IMPLEMENT | N/A | N/A | Via `xtbopt.log` / `xtb.trj` (multi-frame XYZ) |
| **ORCA** | IMPLEMENT | N/A | N/A | N/A | Geometry opt only (molecular code) |
| **Gaussian** | IMPLEMENT | N/A | N/A | N/A | Geometry opt only (molecular code) |
| **Psi4** | LOW PRIORITY | N/A | N/A | N/A | Geometry opt in output |
| **PySCF** | LOW PRIORITY | N/A | N/A | N/A | Geometry opt in output |
| **W90** | N/A | N/A | N/A | N/A | Postprocessing engine |
| **QMCPACK** | N/A | N/A | N/A | N/A | Fixed nuclei QMC |
| **Yambo** | N/A | N/A | N/A | N/A | MBPT postprocessing |

**Legend:** DONE = already implemented, IMPLEMENT = should be implemented, DEFER = possible but low priority, N/A = engine does not support this type, LOW PRIORITY = minimal user demand.

### 3.2 Frame Model Assessment

The current `Frame` dataclass (16 fields) is **sufficient** for all planned engine trajectory parsers. No additions are needed.

**Assessment by field:**

| Field | Used by VASP? | Needed by new engines? | Verdict |
|-------|:---:|:---:|---|
| `frame_index` | YES | YES (all) | Keep |
| `positions` | YES | YES (all) | Keep |
| `species` | YES | YES (all) | Keep |
| `cell` | YES | YES (periodic), None (molecular) | Keep |
| `pbc` | YES | YES (periodic), (F,F,F) (molecular) | Keep |
| `time` | NO (VASP sets None) | YES (MD engines) | Keep |
| `iteration` | YES | YES (relax engines) | Keep |
| `energy` | YES | YES (all) | Keep |
| `forces` | YES | YES (most) | Keep |
| `temperature` | NO | YES (MD: CP2K, LAMMPS, Siesta) | Keep |
| `pressure` | NO | YES (MD: LAMMPS, Siesta) | Keep |
| `stress` | YES | YES (ABINIT, CP2K) | Keep |
| `kinetic_energy` | NO | YES (MD: CP2K, LAMMPS) | Keep |
| `velocities` | NO | YES (Siesta, LAMMPS) | Keep |
| `momenta` | NO | YES (GPAW via ASE) | Keep |
| `image_index` | NO | YES (NEB: QE, CP2K) | Keep |
| `atom_ids` | NO | YES (LAMMPS: atom IDs may reorder) | Keep |

**No new fields proposed.** The 16-field model covers all observables produced by all 15 engines. Fields like `enthalpy` or `free_energy` can be stored via `energy` (the distinction is engine-specific and recorded in parser metadata). Per-engine extra data (e.g., LAMMPS thermo columns beyond the standard set) should NOT be added to `Frame` — instead, such data can be placed in `RenderMeta.extra` or a future extension mechanism.

### 3.3 Parser Architecture Per Engine

Each engine trajectory parser follows the VASP template: standalone parse functions + registered provider class taking `EvidenceBundle`.

#### 3.3.1 QE (fix existing)

**Current issues:**
1. `parse()` signature uses ad-hoc keywords instead of `EvidenceBundle`
2. `_parse_md_output()` is a stub returning `[]`
3. Only one `AnalysisCapability` (relax); missing `md`

**Parse strategy:**
- **Relax/vc-relax:** Keep existing regex parser, fix coordinate conversion edge cases
- **MD:** Parse `ATOMIC_POSITIONS` blocks + `! total energy` + time steps from pw.x MD output
- **NEB:** Parse neb.x output (multiple image blocks per NEB iteration)
- **Files:** `*.relax.out`, `*.vc-relax.out`, `*.md.out`, `*.neb.out`

**Fields populated:** positions, species, cell, pbc, iteration (relax) / time (MD) / image_index (NEB), energy, forces (from `Total force` line — note: QE only outputs max force scalar in some modes)

#### 3.3.2 CP2K

**Parse strategy:**
- **Multi-file merge:** `*-pos-*.xyz` (positions, species) + `*-frc-*.xyz` (forces) + `*.ener` (energy, temperature, KE, pressure, volume) + `*-1.cell` (cell vectors)
- **Format:** All text-based. Position/force files are extended XYZ (comment line + atom lines per frame). Energy file is columnar (one line per step).
- **Alignment:** Match frames by step number across files

**Files:** `cp2k_calc-pos-1.xyz`, `cp2k_calc-frc-1.xyz`, `cp2k_calc.ener`, `cp2k_calc-1.cell`

**Fields populated:** positions, species, cell, pbc, iteration, time (from ener file), energy, forces, temperature, kinetic_energy, pressure

**Fallback:** If only `*-pos-*.xyz` exists → positions-only trajectory

#### 3.3.3 LAMMPS

**Parse strategy:**
- **Primary:** `*.lammpstrj` (LAMMPS dump format) — structured text with `ITEM:` headers per frame
- **Auxiliary:** `log.lammps` (thermo output) — scalar observables per step
- **Format:** Dump file has variable columns (configurable by user's `dump` command). Parser must read `ITEM: ATOMS` header to discover available columns.

**Column mapping:**
```
id -> atom_ids
type -> (mapped to species via data file types)
x/y/z or xu/yu/zu -> positions (unwrapped preferred)
xs/ys/zs -> scaled positions (need box for conversion)
vx/vy/vz -> velocities
fx/fy/fz -> forces
```

**Box format:** `ITEM: BOX BOUNDS` gives lo/hi (orthogonal) or lo/hi/tilt (triclinic). Convert to `(3,3)` cell matrix.

**Fields populated:** positions, species (via type mapping), cell, pbc, time (from timestep), energy (from thermo), forces, velocities, temperature (from thermo), pressure (from thermo), kinetic_energy (from thermo), atom_ids

**Complication:** LAMMPS dump columns are user-configurable. The parser must be column-adaptive, not assume a fixed layout.

#### 3.3.4 ABINIT

**Parse strategy (two paths):**
- **Primary:** `*o_HIST.nc` (NetCDF4 binary) — full history file with all ionic steps. Requires `netCDF4` or `scipy.io.netcdf` for reading. Contains: `xcart` (Cartesian Bohr), `xred` (fractional), `rprimd` (cell), `fcart` (forces Cartesian Ha/Bohr), `strten` (stress), `etotal` (Ha).
- **Fallback:** `*.abo` text output — parse embedded ionic step blocks (already partially handled by existing output parser for convergence).

**Unit conversions:** Ha->eV (27.211386), Bohr->A (0.529177), Ha/Bohr->eV/A (51.422067).

**Fields populated:** positions, species, cell, pbc, iteration, energy, forces, stress

**Complexity note:** `_HIST.nc` is the cleanest format (structured, binary, complete). Text fallback is more fragile. Prefer NetCDF primary path.

#### 3.3.5 Siesta

**Parse strategy:**
- **Positions:** `*.ANI` (multi-frame XYZ animation file) — standard XYZ format, easy to parse
- **Scalars:** `*.MDE` (existing `parse_mde_file()`) — step, temperature, E_KS, E_tot, volume, pressure
- **Velocities/positions (alt):** `*.XV` (per-step file with positions + velocities in Bohr)
- **Cell:** Extract from main output or `*.STRUCT_OUT` (if vc-relax)

**Merge:** Align ANI frames with MDE rows by step index.

**Fields populated:** positions, species, cell, pbc, time (from MDE step), energy, temperature, pressure, velocities (from XV)

**Existing code to leverage:** `parse_mde_file()` already extracts MDE data into raw dict. Needs wrapping into canonical `Frame` objects and merging with ANI position data.

#### 3.3.6 GPAW

**Parse strategy:**
- **Primary:** ASE `.traj` binary file — requires `ase` as import dependency
- **Read via:** `ase.io.Trajectory` reader or `ase.io.read(filename, index=':')`
- **Per-frame:** `atoms.get_positions()`, `atoms.get_cell()`, `atoms.get_pbc()`, `atoms.get_potential_energy()`, `atoms.get_forces()`, `atoms.info` (temperature, etc.)

**Dependency consideration:** GPAW is a Python-script engine that already requires ASE. Using ASE's trajectory reader here is natural and does not introduce a new dependency.

**Fields populated:** positions, species, cell, pbc, energy, forces, stress (if available), momenta (ASE stores velocities as momenta)

**Fallback:** `opt.log` for relax — text file with step, energy, fmax per line (positions not available from this file alone)

#### 3.3.7 xTB

**Parse strategy:**
- **Primary:** `xtbopt.log` (optimization) / `xtb.trj` (MD) — both are multi-frame XYZ format
- **Format:** Standard XYZ: line 1 = atom count, line 2 = comment (may contain energy), lines 3..N+2 = element x y z
- **Energy extraction:** From comment line (xTB writes energy there) or from `xtb.out` output

**Fields populated:** positions, species, cell (None — molecular code unless `--periodic`), pbc, energy, forces (from xtb output gradient section)

**Note:** xTB supports periodic systems with `--periodic` flag, in which case cell/pbc would be populated. Parser should handle both.

#### 3.3.8 ORCA (molecular)

**Parse strategy:**
- **Primary:** `*.xyz` trajectory file — multi-frame XYZ from geometry optimization
- **Auxiliary:** `*.out` — parse optimization energy + gradient norm per step
- **Format:** Standard multi-frame XYZ (same as xTB)

**Fields populated:** positions, species, cell=None, pbc=(F,F,F), iteration, energy, forces (from engrad or gradient section in output)

**No cell/stress:** ORCA is a molecular code. All trajectories are non-periodic.

#### 3.3.9 Gaussian (molecular)

**Parse strategy:**
- **Primary:** `*.log` — parse "Standard orientation" geometry blocks + "SCF Done" energies per optimization step
- **Format:** Embedded text with well-known regex patterns (already partially handled by GaussianOutputParser for scf_digest)

**Fields populated:** positions, species, cell=None, pbc=(F,F,F), iteration, energy

**Existing code to leverage:** `GaussianOutputParser` already parses Standard orientation geometries and SCF energies. Trajectory parser can reuse these regex patterns.

### 3.4 Molecular Engine Trajectory

ORCA, Gaussian, Psi4, PySCF, and xTB (in molecular mode) produce trajectories without periodic boundary conditions. Design considerations:

1. **`cell = None`, `pbc = (False, False, False)`** — the `Frame` model already supports this
2. **No stress tensor** — stress is meaningless without periodicity
3. **Cartesian only** — no fractional coordinates, no cell for conversion
4. **No temperature/pressure** — these engines typically do geometry optimization, not MD. (Exception: xTB has `--md` mode with temperature)
5. **Smaller systems** — molecular trajectories are typically 10-200 atoms, so memory is not a concern

The existing `Frame` model handles molecular trajectories without modification. The `cell=None` + `pbc=(False, False, False)` combination is already validated in `__post_init__`.

### 3.5 Memory Management

Trajectory files can be very large (VASP vasprun.xml for long MD > 1 GB, LAMMPS dumps > 10 GB). Memory management strategies per format:

#### 3.5.1 XML (VASP vasprun.xml)

**Strategy:** `xml.etree.ElementTree.iterparse` with `elem.clear()` after each `<calculation>`.

Already implemented in VASP parser. Key pattern:
```python
for event, elem in ET.iterparse(str(path), events=("end",)):
    if elem.tag == "calculation":
        # extract frame data
        elem.clear()  # free memory immediately
```

Memory: O(1 frame) during parsing, O(N frames) for final `List[Frame]`.

#### 3.5.2 Text (QE, CP2K, Siesta, xTB, ORCA, Gaussian)

**Strategy:** Line-by-line text parsing with regex.

Most text formats are parsed line-by-line already. For very large files (>1 GB), consider:
- Generator-based parsing that yields frames one at a time
- File reading via `for line in open(path)` (Python handles buffered line reads)
- Frame construction in-place, not accumulating all text then processing

Memory: O(1 line) during parsing + O(1 frame) per frame construction.

#### 3.5.3 LAMMPS dump

**Strategy:** Line-by-line with frame detection via `ITEM: TIMESTEP` markers.

LAMMPS dumps can be very large. Parse line-by-line, accumulate within a frame block, emit when complete. Same O(1) memory pattern as text engines.

#### 3.5.4 NetCDF (ABINIT `_HIST.nc`)

**Strategy:** Selective variable reading via `netCDF4` or `scipy.io.netcdf`.

NetCDF supports lazy variable access — read only the variables needed (xcart, rprimd, fcart, etotal). Do NOT load entire file into memory.

```python
import netCDF4 as nc
ds = nc.Dataset(path)
n_frames = len(ds.dimensions['time'])
for i in range(n_frames):
    positions = ds.variables['xcart'][i]  # reads single frame
```

Memory: O(1 frame) per read.

#### 3.5.5 ASE binary `.traj` (GPAW)

**Strategy:** Use ASE's lazy `TrajectoryReader` with frame-by-frame access.

```python
from ase.io.trajectory import Trajectory as AseTrajectory
traj = AseTrajectory(str(path))
for atoms in traj:
    # atoms loaded one at a time
```

Memory: O(1 frame) per access.

#### 3.5.6 Final Trajectory Object

All parsers accumulate `List[Frame]` in memory. For typical trajectories (< 10k frames, < 1k atoms), this is fine. For extreme cases (100k+ frames MD):

**Current approach (adequate for v1):** Full `List[Frame]` in memory. A 100k-frame, 100-atom trajectory with energy+forces is approximately:
- 100k frames * (100 atoms * 3 * 8 bytes positions + 100 * 3 * 8 bytes forces + 72 bytes cell + scalars) ≈ 500 MB
- Acceptable for modern workstations.

**Future extension (not in scope):** Lazy Trajectory backed by mmap or HDF5 for 1M+ frame trajectories. Would require a `LazyTrajectory` subclass with `__getitem__` reading from disk.

### 3.6 Transform Extensions

The `DerivedPrimitiveBundle` with `transform_chain` already supports derived trajectory analysis. Potential transforms (design-only, not implementing):

| Transform | Input | Output | Use case |
|-----------|-------|--------|----------|
| **Frame slicing** | Trajectory | Trajectory (subset) | `traj[100:200]` — zoom into region of interest |
| **Smoothing** | Series1D | Series1D | Running average of energy, temperature |
| **Unwrapping** | Trajectory (wrapped) | Trajectory (unwrapped) | MSD computation requires unwrapped coords |
| **MSD** | Trajectory | Series1D | Mean squared displacement vs time |
| **RDF** | Trajectory | Series1D | Radial distribution function (time-averaged) |
| **Velocity autocorrelation** | Trajectory (with velocities) | Series1D | VACF → phonon DOS via FFT |
| **Diffusion coefficient** | Trajectory | float | From MSD slope |
| **Frame interpolation** | Trajectory (sparse) | Trajectory (dense) | NEB image refinement |

Each transform records itself in `DerivedPrimitiveBundle.transform_chain` as a `TransformRecord(transform_name, parameters)`.

**Design principle:** Transforms are post-parse operations on canonical bundles. They do NOT modify the parser or the canonical bundle. They produce a new `DerivedPrimitiveBundle`.

### 3.7 AnalysisCapability Declarations

Each engine that gets trajectory support needs `AnalysisCapability` entries in its `driver.py`. The pattern from VASP:

```python
ANALYSIS_CAPABILITIES = [
    # ... existing capabilities (bands, dos, convergence) ...
    AnalysisCapability(
        object_type="trajectory",
        gen_step_sequence=["relax"],
        evidence_files=["<primary_trajectory_file>"],
    ),
    AnalysisCapability(
        object_type="trajectory",
        gen_step_sequence=["md"],
        evidence_files=["<primary_trajectory_file>"],
    ),
]
```

**Per-engine capability declarations:**

| Engine | gen_step_sequence | evidence_files |
|--------|------------------|----------------|
| QE (add md) | `["md"]` | `["*.md.out"]` |
| ABINIT | `["relax"]` | `["*o_HIST.nc"]` |
| CP2K | `["relax"]`, `["md"]` | `["*-pos-*.xyz"]` |
| LAMMPS | `["minimize"]`, `["md"]` | `["*.lammpstrj"]` |
| Siesta | `["relax"]`, `["md"]` | `["*.ANI"]` |
| GPAW | `["relax"]`, `["md"]` | `["relax.traj"]`, `["md.traj"]` |
| xTB | `["relax"]` | `["xtbopt.log"]` |
| ORCA | `["relax"]` | `["*.xyz"]` |
| Gaussian | `["relax"]` | `["*.log"]` |

### 3.8 Priority & Phasing

Ordered by user demand, ecosystem maturity, and implementation difficulty:

#### Phase 1: Fix QE + Add ABINIT + CP2K (highest value)

| Engine | Work | Difficulty | Rationale |
|--------|------|-----------|-----------|
| **QE** | Fix EvidenceBundle API, implement MD parser, add md capability | Medium | Second-most-used engine, relax already works, MD stub exists |
| **CP2K** | New parser (multi-file XYZ merge) | Medium | Third solid-state engine, text-based, clean format |
| **ABINIT** | New parser (NetCDF primary, text fallback) | Medium-High | Fourth solid-state engine, NetCDF requires dependency check |

#### Phase 2: LAMMPS + Siesta (classical MD + established periodic)

| Engine | Work | Difficulty | Rationale |
|--------|------|-----------|-----------|
| **LAMMPS** | New parser (column-adaptive dump) | High | Most complex format (variable columns), but LAMMPS is the primary MD engine |
| **Siesta** | New parser (ANI + MDE merge) | Medium | Existing `parse_mde_file()` gives head start |

#### Phase 3: Lightweight engines (xTB + GPAW)

| Engine | Work | Difficulty | Rationale |
|--------|------|-----------|-----------|
| **xTB** | New parser (multi-frame XYZ) | Low | Simple XYZ format, fast to implement |
| **GPAW** | New parser (ASE .traj reader) | Low | ASE dependency already exists, trivial reader |

#### Phase 4: Molecular codes (ORCA + Gaussian)

| Engine | Work | Difficulty | Rationale |
|--------|------|-----------|-----------|
| **ORCA** | New parser (XYZ + output scraping) | Low-Medium | Molecular opt only, XYZ format is simple |
| **Gaussian** | New parser (log scraping) | Low-Medium | Can leverage existing GaussianOutputParser regex |

#### Phase 5: Low priority (Psi4 + PySCF)

| Engine | Work | Difficulty | Rationale |
|--------|------|-----------|-----------|
| **Psi4** | New parser (JSON/output) | Low | Very few users do geometry opt with Psi4 in QMatSuite |
| **PySCF** | New parser (output) | Low | Same — rare use case |

#### Not planned: W90, QMCPACK, Yambo

These engines do not produce trajectory data. No trajectory parser needed.

---

## Appendix A: Key Source Files

| File | Role |
|------|------|
| `src/quantumvitas/core/analysis/trajectory/model.py` | Frame (16 fields) + Trajectory dataclasses |
| `src/quantumvitas/core/analysis/primitives.py` | GeometryFrame, GeometryFrames, Series1D |
| `src/quantumvitas/core/analysis/bundles.py` | CanonicalPrimitiveBundle, DerivedPrimitiveBundle, RenderMeta, ProvenanceMeta |
| `src/quantumvitas/core/analysis/orchestrator.py` | `run_post_run_analysis()` — evidence-based dispatch |
| `src/quantumvitas/core/analysis/capability.py` | AnalysisCapability, CapabilityMatch, `find_contiguous_match()` |
| `src/quantumvitas/core/analysis/convergence/model.py` | Convergence dataclass (boundary reference) |
| `src/quantumvitas/core/analysis/evidence.py` | EvidenceBundle (8 fields) |
| `src/quantumvitas/core/analysis/base.py` | AnalysisObjectMeta (13 fields), SourceFileStat |
| `src/quantumvitas/parsers/registry.py` | `@register_parser`, `get_parser()` |
| `src/quantumvitas/drivers/vasp/parsers/trajectory.py` | **TEMPLATE** — VASPTrajectoryProvider (300 lines) |
| `src/quantumvitas/drivers/qe/parsers/trajectory.py` | QETrajectoryParser — partial, needs fixes |
| `src/quantumvitas/drivers/siesta/parser.py` | `parse_mde_file()` — raw dict, scalars only |

## Appendix B: Data Flow Diagram

```
Engine Run Completes
        |
        v
driver.ANALYSIS_CAPABILITIES
        |
        v
orchestrator: find_contiguous_match(capability, ordered_gen_steps)
        |
        v  (CapabilityMatch or None)
get_parser(engine, "trajectory") -> TrajectoryProvider
        |
        v
provider.can_parse(primary_raw_dir) -> bool
        |
        v
EvidenceBundle(primary_raw_dir, calc_dir, ulids, gen_steps, engine)
        |
        v
provider.parse(evidence) -> Trajectory
        |   |
        |   +-- parse_primary_file(path) -> dict {species, frames}
        |   +-- parse_fallback_file(path) -> dict (if primary missing)
        |   +-- build Frame objects (coordinate conversion, unit conversion)
        |   +-- build AnalysisObjectMeta
        |
        v
Trajectory (List[Frame] + meta + trajectory_type)
        |
        v
trajectory.to_primitives() -> CanonicalPrimitiveBundle
        |
        v  (returned to orchestrator)
{object_type: "trajectory",
 canonical: CanonicalPrimitiveBundle,
 analysis_object: Trajectory}
```

## Appendix C: External Reference Summary

| Library | Key class/file | QMatSuite alignment |
|---------|---------------|-------------------|
| ASE | `TrajectoryReader` (`ase/io/trajectory.py`) | Lazy loading model — future extension for large trajectories |
| ASE | `Atoms` (`ase/atoms.py`) | Similar to Frame: positions, cell, pbc, calculator results |
| pymatgen | `Trajectory` (`pymatgen/core/trajectory.py`) | `(M,N,3)` layout differs from QMatSuite's `List[Frame]` approach |
| pymatgen | `Xdatcar` (`pymatgen/io/vasp/outputs.py:4651`) | VASP XDATCAR parser — compare with our `parse_xdatcar()` |
| pymatgen | `Vasprun.get_trajectory()` (`outputs.py:1303`) | Forces as site_properties — QMatSuite stores forces as Frame field |
| AiiDA | `TrajectoryData` (`aiida/orm/nodes/data/array/trajectory.py`) | Named arrays approach — QMatSuite uses typed Frame fields instead |
| py4vasp | Lazy HDF5 | Lazy loading pattern — possible future optimization |

## Appendix D: SUPPORTED_GEN_STEPS per Engine

Complete reference for trajectory-relevant gen steps:

| Engine | SUPPORTED_GEN_STEPS (trajectory-relevant subset) |
|--------|------------------------------------------------|
| VASP | `scf`, `nscf`, `relax`, `md`, `bandspw` |
| QE | `scf`, `nscf`, `relax`, `bands`, `bandspw`, `dos`, ... |
| ABINIT | `scf`, `nscf`, `relax`, ... |
| CP2K | `scf`, `relax`, `md`, `bandspw`, `dos` |
| LAMMPS | `minimize`, `md`, `relax` |
| Siesta | `scf`, `relax`, `md`, `bands`, `dos`, ... |
| GPAW | `scf`, `nscf`, `relax`, `bandspw`, `dos`, `md`, ... |
| xTB | `relax` |
| ORCA | `scf`, `hf`, `relax`, `td` |
| Gaussian | `scf`, `hf`, `relax`, `freq`, `mp2`, `td` |
| Psi4 | `scf`, `hf`, `mp2`, `relax`, `td` |
| PySCF | `scf`, `relax`, `mp2`, `td` |
| W90 | `wannierprep`, `wannier` (no trajectory) |
| QMCPACK | `vmc`, `dmc`, `wfopt` (no trajectory) |
| Yambo | `setup`, `gw`, `bse`, `optics` (no trajectory) |
