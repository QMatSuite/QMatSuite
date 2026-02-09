# VASP Analysis Deep Design Document

**Status:** v2.1 FINAL
**Date:** 2026-02-09
**Scope:** Complete VASP analysis implementation covering all five object_types, artifact source strategy, canonical bundle schemas, testing plan, and implementation order.
**Prerequisite reading:** `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`, `ANALYSIS_PIPELINE_PLAYBOOK.md`

---

## 1. Object-Type Taxonomy

VASP analysis uses exactly five `object_type` values. No more. These are the same engine-agnostic types used across all engines.

| object_type | What it captures | VASP gen_step_sequence | Evidence files (primary) |
|-------------|-----------------|----------------------|------------------------|
| `bands` | Electronic band structure along k-path | `["bandspw"]` | EIGENVAL, KPOINTS |
| `dos` | Density of states (total + projected) | `["dos"]` or `["nscf"]` | DOSCAR, vasprun.xml |
| `convergence` | SCF/ionic convergence history | `["scf"]` | OSZICAR, vasprun.xml |
| `trajectory` | Geometry + observables per ionic step | `["relax"]` or `["md"]` | vasprun.xml, XDATCAR, OUTCAR |
| `field3d` | Volumetric scalar fields | `["scf"]` | CHGCAR, LOCPOT, ELFCAR |

### What is NOT a separate object_type

These are properties of existing types or digest fields, not new object_types:

| Quantity | Where it lives | Rationale |
|----------|---------------|-----------|
| Band gap, VBM, CBM | `VASPDigest` (scf_digest) | Per-step scalar, not an analysis object |
| Fermi energy | `VASPDigest` + `BandStructure.fermi_energy` | Scalar metadata, not array data |
| Final energy | `VASPDigest.final_energy_eV` | Per-step scalar |
| Forces/stress snapshot | `VASPDigest` | Per-step scalars (max_force, pressure) |
| Fat bands (orbital projection) | Future extension of `bands` | Same object_type, extended arrays |
| Partial DOS (PDOS) | Part of `dos` | Sub-arrays within the same bundle |
| Phonons, elastic, dielectric | Future object_types | Not in this design scope |

---

## 2. Coverage Map

### 2.1 bands (IMPLEMENTED)

**Current state:** Fully implemented, golden-tested end-to-end.

| Sub-feature | Status | Implementation |
|------------|--------|---------------|
| Eigenvalues (non-spin) | Done | `parse_eigenval()` in `drivers/vasp/parsers/bands.py` |
| Eigenvalues (spin-polarized) | Done | 3D array `(n_spin, n_kpoints, n_bands)` |
| K-path distances | Done | Reciprocal-space Cartesian distance (see §2.1.1) |
| High-symmetry labels | Done | Parsed from line-mode KPOINTS |
| Fermi energy | Done | vasprun.xml primary, OUTCAR fallback |
| Occupations | Parsed but not in bundle | Available in `parse_eigenval()` result |

#### 2.1.1 K-distance computation: reciprocal Cartesian metric

K-path distances **must** be computed in Cartesian reciprocal space, not in fractional coordinates. The fractional Euclidean distance is incorrect for non-cubic cells because it ignores the metric tensor of reciprocal space.

**Correct formula:**
```
B = 2π * inv(A)^T          # reciprocal lattice matrix
k_cart = B @ k_frac         # transform to Cartesian reciprocal space
d_i = ||k_cart_i - k_cart_{i-1}||   # Euclidean in Cartesian
k_distance = cumsum(d_i)
```

Where `A` = real-space lattice matrix (rows = lattice vectors). Requires reading the lattice from POSCAR or vasprun.xml — POSCAR is always present in the bands step's raw_dir.

**Testing:** Regression test with a non-cubic lattice (e.g., hexagonal BN or FCC Al). The fractional Euclidean distance will differ from reciprocal Cartesian by a measurable amount for non-cubic cells.

**Cubic cell invariant:** For cubic cells (a=b=c, α=β=γ=90°), reciprocal Cartesian distances equal `(2π/a) × fractional Euclidean distances`. The fix changes only the scale factor, not the shape. Existing cubic Si golden tests survive: monotonicity preserved, no absolute k_distance values asserted, SHA determinism still holds (two calls produce identical results).

**File affected:** `drivers/vasp/parsers/bands.py:_compute_k_distances()` — currently lines 176-182. Also `_read_kpoints_labels()` uses fractional distances for high-sym point positions — must be updated similarly.

**Canonical bundle schema:**

```
CanonicalPrimitiveBundle:
  object_type: "bands"
  arrays:
    k_distances: float[n_kpoints]         # cumulative k-path distance (1/A)
    eigenvalues: float[n_kpoints, n_bands] # or float[n_spin, n_kpoints, n_bands]
  series: Series1D[]                       # one per band (or spin x band)
    x: k_distances, y: eigenvalues[:, band_i]
    x_label: "k-path", y_label: "Energy", x_unit: "1/A", y_unit: "eV"
  render_meta:
    axis_labels: {x: "k-path", y: "Energy"}
    units: {x: "1/A", y: "eV"}
    reference_energy: fermi_energy (eV) or null
    markers: [{position: k_dist, label: "G"}, ...]  # high-sym points
```

**Required VASP artifacts:** EIGENVAL (mandatory), KPOINTS (optional, for labels), POSCAR (for lattice → reciprocal metric), vasprun.xml or OUTCAR (optional, for E_F)

**Capability declaration:**
```python
AnalysisCapability(
    object_type="bands",
    gen_step_sequence=["bandspw"],
    evidence_files=["EIGENVAL"],
)
```

**Future extension: Fat bands (orbital projection)**

Requires PROCAR (needs `LORBIT=10` or `11` in INCAR). Would add:
```
arrays:
    projections: float[n_kpoints, n_bands, n_atoms, n_orbitals]  # or per-spin
    orbital_labels: str[n_orbitals]   # ["s", "py", "pz", "px", ...]
    atom_labels: str[n_atoms]         # ["Si", "Si", ...]
```

Not in initial scope. Can be added without schema break (new optional arrays).

### 2.2 dos (TO IMPLEMENT)

**Analysis model class:** `DOS` in `core/analysis/dos/model.py` (new)

| Sub-feature | Priority | Source file | Notes |
|------------|----------|-------------|-------|
| Total DOS | P0 | DOSCAR or vasprun.xml | Energy grid + DOS values |
| Spin-resolved total DOS | P0 | DOSCAR (ISPIN=2) | Separate up/down channels |
| Fermi energy | P0 | vasprun.xml or DOSCAR header | Reference line |
| NEDOS, energy range | P0 | DOSCAR header | Axis bounds |
| Integrated DOS | P1 | DOSCAR column 3 | Optional series |
| Atom-projected DOS (LDOS) | P1 | DOSCAR (with LORBIT) | Per-atom decomposition |
| Orbital-projected DOS (PDOS) | P1 | DOSCAR (with LORBIT) | Per-orbital decomposition |

**Canonical bundle schema:**

```
CanonicalPrimitiveBundle:
  object_type: "dos"
  arrays:
    energies: float[nedos]              # energy grid (eV)
    total_dos: float[nedos]             # total DOS (states/eV/cell)
    # spin-polarized:
    total_dos_up: float[nedos]          # spin-up DOS (if ISPIN=2)
    total_dos_down: float[nedos]        # spin-down DOS (if ISPIN=2)
    integrated_dos: float[nedos]        # integrated DOS (optional)
    # projected (optional, if LORBIT set):
    pdos: float[n_atoms, nedos, n_orbitals]  # atom+orbital projected
    atom_labels: str[n_atoms]
    orbital_labels: str[n_orbitals]
  series: Series1D[]
    - name: "Total DOS" (or "DOS up"/"DOS down")
      x: energies, y: total_dos
      x_label: "Energy", y_label: "DOS"
      x_unit: "eV", y_unit: "states/eV"
    - (optional per-atom/orbital series)
  render_meta:
    axis_labels: {x: "Energy", y: "DOS"}
    units: {x: "eV", y: "states/eV"}
    reference_energy: fermi_energy (eV)
```

**Capability declaration:**
```python
AnalysisCapability(
    object_type="dos",
    gen_step_sequence=["dos"],
    evidence_files=["DOSCAR"],
)
# Alternative: NSCF step also produces DOSCAR
AnalysisCapability(
    object_type="dos",
    gen_step_sequence=["nscf"],
    evidence_files=["DOSCAR"],
)
```

**Parser:** `VASPDOSProvider` in `drivers/vasp/parsers/dos.py` (new)

### 2.3 convergence (TO IMPLEMENT)

**Analysis model class:** `Convergence` in `core/analysis/convergence/model.py` (new)

This captures SCF convergence history as a time-series, distinct from the single-snapshot `VASPDigest`. Useful for diagnosing convergence problems and comparing convergence behavior across runs.

| Sub-feature | Priority | Source file | Notes |
|------------|----------|-------------|-------|
| Electronic step energy | P0 | OSZICAR | Free energy per SCF step |
| Electronic step dE | P0 | OSZICAR | Energy change |
| Electronic step rms | P1 | OSZICAR | Wavefunction residuum |
| Ionic step energy | P0 | OSZICAR | F, E0 summary lines |
| Ionic step max force | P1 | vasprun.xml or OUTCAR | Per ionic step |
| Convergence flags | P0 | OSZICAR | Converged yes/no per ionic step |

**Canonical bundle schema:**

```
CanonicalPrimitiveBundle:
  object_type: "convergence"
  arrays:
    # Electronic convergence (flat across all ionic steps):
    scf_step: int[n_total_scf]             # cumulative SCF step index
    scf_energy: float[n_total_scf]         # free energy per SCF step (eV)
    scf_de: float[n_total_scf]             # energy change per SCF step
    # Ionic convergence:
    ionic_step: int[n_ionic]               # ionic step index
    ionic_energy: float[n_ionic]           # energy per ionic step (eV)
    ionic_max_force: float[n_ionic]        # max force per ionic step (eV/A), optional
  series: Series1D[]
    - name: "SCF Energy"
      x: scf_step, y: scf_energy
    - name: "Ionic Energy"
      x: ionic_step, y: ionic_energy
    - name: "Max Force" (optional)
      x: ionic_step, y: ionic_max_force
  render_meta:
    axis_labels: {x: "Step", y: "Energy"}
    units: {x: "", y: "eV"}
    extra: {n_ionic_steps: N, converged: true/false}
```

**Capability declaration:**
```python
AnalysisCapability(
    object_type="convergence",
    gen_step_sequence=["scf"],
    evidence_files=["OSZICAR"],
)
```

**Parser:** `VASPConvergenceProvider` in `drivers/vasp/parsers/convergence.py` (new)

### 2.4 trajectory (TO IMPLEMENT)

**Analysis model class:** `Trajectory` in `core/analysis/trajectory/model.py` (EXISTS)

The Trajectory model already exists with Frame dataclass supporting positions, cell, forces, energy, temperature, pressure, stress, velocities. No new model needed.

| Sub-feature | Priority | Source file | Notes |
|------------|----------|-------------|-------|
| Positions per ionic step | P0 | vasprun.xml or XDATCAR | Cartesian, unwrapped |
| Cell per ionic step | P0 | vasprun.xml | Lattice vectors |
| Energy per ionic step | P0 | vasprun.xml or OSZICAR | Total energy |
| Forces per ionic step | P1 | vasprun.xml or OUTCAR | Per-atom forces |
| Stress per ionic step | P1 | vasprun.xml or OUTCAR | Stress tensor |
| Temperature (MD) | P0 | OSZICAR | Instantaneous T |
| Pressure | P1 | OUTCAR | External pressure |
| Kinetic energy (MD) | P1 | OSZICAR | Ionic KE |

**Canonical bundle schema:** Already defined by `Trajectory.to_primitives()` — uses `GeometryFrames` + observable `Series1D`.

**Capability declarations:**
```python
AnalysisCapability(
    object_type="trajectory",
    gen_step_sequence=["relax"],
    evidence_files=["vasprun.xml"],
)
AnalysisCapability(
    object_type="trajectory",
    gen_step_sequence=["md"],
    evidence_files=["vasprun.xml"],
)
```

**Parser:** `VASPTrajectoryProvider` in `drivers/vasp/parsers/trajectory.py` (new)

### 2.5 field3d (TO IMPLEMENT)

**Analysis model class:** Reuses existing `VolumeMetadata` in `analysis/volume_artifacts.py` (99 lines). No new model needed.

This captures volumetric scalar fields (charge density, electrostatic potential, ELF) on a real-space FFT grid. VASP writes these as CHGCAR, LOCPOT, and ELFCAR — all sharing an identical file format: POSCAR header + FFT grid data.

| Sub-feature | Priority | Source file | Notes |
|------------|----------|-------------|-------|
| FFT grid shape (NGXF, NGYF, NGZF) | P0 | CHGCAR/LOCPOT/ELFCAR/PARCHG | Header after blank line |
| Grid data (valence) | P0 | CHGCAR/LOCPOT/ELFCAR | Flat array, FORTRAN i-fastest order |
| Grid origin + vectors | P0 | POSCAR header in file | Real-space cell from lattice vectors |
| Augmentation charges | P1 | CHGCAR only | Second grid after blank separator |
| Preview grid | P0 | Derived | Downsampled by factor 4 for fast GUI rendering |
| Field kind metadata | P0 | Filename detection | charge_density, potential, elf |
| Statistics (min/max/mean) | P0 | Computed | Single pass over grid data |

**Existing code to reuse (NOT re-implement):**
- `analysis/volume_artifacts.py` — `VolumeMetadata` dataclass (grid_shape, origin_cart, grid_vectors_cart, data_order, blob_id, preview_blob_id, statistics) — 99 lines
- `io/parser/volume_parsers.py` — `parse_xsf_datagrid_3d()`, `parse_bxsf_bandgrid_3d()`, `downsample_grid()` — 641 lines
- `analysis/blob_store.py` — binary `.f32` storage with `index.json` allowlist — 207 lines
- Daemon RPC endpoint for volume compilation already wired

**Existing Wannier90 MLWF field3d infrastructure (pattern constraint):**

The GUI already has a complete volumetric rendering pipeline built for Wannier90 XSF/BXSF data. VASP field3d **MUST** produce `VolumeMetadata` + BlobStore blobs identical in contract to the XSF/BXSF pipeline. The GUI rendering code is NOT engine-aware — it consumes the same `VolumeMetadata.to_dict()` + `Float32Array` blobs regardless of source engine.

Key GUI files establishing the pattern:
- `gui/src/utils/marchingCubes.ts` (875 lines) — client-side marching cubes consuming `VolumeMetadata` + `Float32Array` blobs
- `gui/src/utils/volumeCoordinates.ts` (110 lines) — `gridToWorld()` using `VolumeMetadata.grid_vectors_cart`
- `gui/src/utils/volumeIndexing.ts` (80 lines) — data-order-aware flat index (FORTRAN/C)
- `gui/src/components/panels/VolumeViewerSandbox.tsx` (1053 lines) — volume viewer consuming blob data via RPC

**VASP-specific additions needed:**
- `parse_chgcar_text()` — POSCAR header + FFT grid (FORTRAN i-fastest order)
- CHGCAR, LOCPOT, ELFCAR, PARCHG share identical format; differentiated by `field_kind` metadata
- CHGCAR augmentation charges (second grid after blank line) — parse but store separately

**Serialization strategy:**
- JSON CAS is inappropriate for 100+ MB grids
- Use existing BlobStore (`.f32` binary) for full-resolution + preview grids
- CAS manifest (`.json.gz`) stores VolumeMetadata only (no grid data)
- BlobStore reference via `blob_id` field in VolumeMetadata

**Canonical bundle schema:**

```
CanonicalPrimitiveBundle:
  object_type: "field3d"
  arrays: {}  # Grid data NOT in JSON arrays — stored in BlobStore
  render_meta:
    volume_metadata: VolumeMetadata.to_dict()
    field_kind: "charge_density" | "potential" | "elf" | ...
    blob_store_root: relative path to blob store
  provenance_meta: {source_file, sha, ...}
```

**Capability declaration:**
```python
AnalysisCapability(
    object_type="field3d",
    gen_step_sequence=["scf"],
    evidence_files=["CHGCAR"],  # discovery: provider checks which files exist
)
```

**Key design decisions:**
1. **Discovery approach:** One capability registered; the provider discovers which files exist (CHGCAR, LOCPOT, ELFCAR, PARCHG) and produces one bundle per discovered file. This avoids capability explosion.
2. **Preview grid:** Downsample by factor 4 using existing `downsample_grid()` for fast GUI rendering.
3. **Augmentation charges:** Store as a separate blob, not merged with valence. p4vasp and py4vasp both treat these separately.
4. **Isosurface computation:** Client-side only (marching cubes in JS/WebGL). Server sends grid data; client renders. p4vasp implemented marching cubes/tetrahedra in C++ because Python was too slow — the modern equivalent is WebGL.

**Parser:** `VASPField3DProvider` in `drivers/vasp/parsers/field3d.py` (new)

---

## 3. Artifact Source Tradeoffs

VASP produces redundant data across multiple output files. Choosing the right source per object_type is a critical design decision.

### 3.1 Decision Matrix

| object_type | Primary source | Fallback source | Rationale |
|-------------|---------------|-----------------|-----------|
| bands | **EIGENVAL** | vasprun.xml | EIGENVAL is small, always produced for band calcs, simple text format. vasprun.xml contains the same data in XML but is much larger and slower to parse. |
| dos | **DOSCAR** | vasprun.xml | DOSCAR is purpose-built for DOS data. Simpler, smaller. PDOS columns are tricky but well-defined. vasprun.xml has the same data tagged but requires full XML parse. |
| convergence | **OSZICAR** | vasprun.xml, OUTCAR | OSZICAR is tiny (<1 KB typically), always produced, purpose-built for convergence tracking. Perfect primary source. |
| trajectory | **vasprun.xml** | XDATCAR + OSZICAR | vasprun.xml has everything (positions, forces, stress, energy) in one structured file. XDATCAR has only positions; would need OSZICAR for energies and OUTCAR for forces. |
| field3d | **CHGCAR/LOCPOT/ELFCAR** | (none) | Each file IS the artifact. No alternative source. CHGCAR format is self-contained (structure header + grid). |

### 3.2 vasprun.xml: When to Use and When Not To

**Use vasprun.xml for:**
- Trajectory extraction (positions + forces + stress + energy all in one place)
- Fermi energy (simple XPath: `.//i[@name='efermi']`)
- Fallback for any quantity when the dedicated file is missing

**Avoid vasprun.xml for:**
- Band structure (EIGENVAL is simpler and faster)
- DOS (DOSCAR is simpler)
- Convergence (OSZICAR is tiny and purpose-built)
- Large MD/relaxation runs (vasprun.xml can be hundreds of MB to GB)
- Field3d (CHGCAR etc. are the only source; vasprun.xml does not contain grid data)

**Size mitigation for trajectory:**
- Stream-parse using `xml.etree.ElementTree.iterparse()` with `events=("end",)` on `<calculation>` elements
- Clear each element after extraction to free memory
- Cap at configurable max_frames (e.g., 10000) with stride sampling for very long MD

### 3.3 Lessons from py4vasp and p4vasp

py4vasp (Apache-2.0, VASP Software GmbH) and p4vasp (GPLv2, Orest Dubay) take fundamentally different approaches, but converge on several key design insights relevant to QMatSuite.

1. **K-distance must use reciprocal Cartesian.** Both py4vasp and p4vasp compute `B @ k_frac` before taking Euclidean norm. p4vasp: `Structure.updateRecipBasis()` computes reciprocal lattice from direct lattice, then `Dyna.py:203 path+=(p2-p1).length()` operates on reciprocal vectors in Cartesian space. py4vasp: explicit `B = 2π * inv(A)^T` transform. Fractional Euclidean distance is wrong for any non-cubic cell.

2. **Isosurface = client-side marching cubes/tetrahedra.** p4vasp implemented marching tetrahedra in C++ (`isosurface.py` dispatches to 6-tetrahedra decomposition per cube, with `handle_type1()`/`handle_type2()` lookup tables). The C++ backend (`ChgcarSmear.cpp`, `Isosurface.cpp`) was necessary because pure Python was too slow. Modern alternative: send grid data to WebGL client, run marching cubes in JS (three.js MarchingCubes or custom). Server should NOT do isosurface extraction.

3. **CHGCAR format = POSCAR header + FFT grid.** Both p4vasp and py4vasp handle CHGCAR as structure header + flat grid. FORTRAN column-major order (i varies fastest). p4vasp memory layout: `data[i+(j+k*ny)*nx]`. Augmentation charges appear after a blank line separator — must be parsed but stored separately.

4. **Downsampling is essential for preview.** p4vasp's C++ `ChgcarSmear` implements Gaussian smearing for visualization; `downSampleByFactors(x,y,z)` averages over sub-blocks. Our existing `downsample_grid()` (block averaging) serves the same purpose more simply.

5. **HDF5 is VASP 6.4+ only.** py4vasp exclusively reads `vaspout.h5`. QMatSuite must support VASP 5.x text files. No HDF5 dependency.

6. **Schema-driven access is elegant but inapplicable.** py4vasp's `_raw/schema.py` maps HDF5 paths to Python objects via `@data_access` decorators. Our text-file parsers need format-specific logic instead — no universal schema mapping is possible for EIGENVAL, DOSCAR, CHGCAR, etc.

7. **Projection selection DSL.** py4vasp's `"Ti(d) - O(p)"` string DSL for projected DOS/bands is powerful UX. Not in initial scope but worth noting as future direction for fat bands and PDOS visualization.

8. **Stream parsing for large XML.** py4vasp avoids vasprun.xml entirely (HDF5 only). p4vasp also avoids large XML in favor of dedicated files (DOSCAR, EIGENVAL). We must use `iterparse()` with element clearing for trajectory extraction from vasprun.xml.

9. **Reciprocal lattice stored alongside real lattice.** p4vasp's `Structure` stores both `basis[9]` and `rbasis[9]`, updated via `updateRecipBasis()`. Our `BandStructure` model should carry the reciprocal lattice for k-distance computation rather than re-deriving it each time.

10. **Binary blob storage for volumetric data.** p4vasp uses raw C float arrays in memory (`float *data` in `Chgcar.cpp`). Our BlobStore (`.f32` + `index.json`) is the modern equivalent — already implemented and production-tested.

---

## 4. Implementation Architecture

### 4.1 File Layout

All new files follow existing patterns:

```
src/quantumvitas/
  core/analysis/
    evidence.py               # NEW: EvidenceBundle dataclass
    dos/
      __init__.py             # exports DOS
      model.py                # DOS dataclass + to_primitives()
    convergence/
      __init__.py             # exports Convergence
      model.py                # Convergence dataclass + to_primitives()
    # trajectory/ already exists
    # band_structure/ already exists
    # volume_artifacts.py already exists (VolumeMetadata)
    # blob_store.py already exists (BlobStore)
  drivers/vasp/parsers/
    bands.py                  # EXISTS: VASPBandsProvider
    output.py                 # EXISTS: VASPOutputParser (scf_digest)
    dos.py                    # NEW: VASPDOSProvider
    convergence.py            # NEW: VASPConvergenceProvider
    trajectory.py             # NEW: VASPTrajectoryProvider
    field3d.py                # NEW: VASPField3DProvider
```

### 4.2 Parser Contract

Every parser follows the same interface (from the playbook), using a typed `EvidenceBundle` instead of kwargs sprawl.

**Design choice:** `EvidenceBundle` was adopted as a deliberate replacement for the 6-kwarg `parse()` signature. Rationale: (1) typed context prevents kwarg misspelling bugs, (2) single construction point in orchestrator makes adding new context fields a one-line change, (3) providers can ignore fields they don't use without signature bloat. This is deferred to Phase 1 of the phased rollout (not Foundation Work) — only 2 providers exist today, making migration trivial.

```python
@dataclass
class EvidenceBundle:
    """Typed context passed to every analysis provider."""
    primary_raw_dir: Path
    calc_dir: Path
    run_ulid: str
    calc_ulid: str
    step_ulids: list[str]
    gen_steps: list[str]
    engine_name: str
    evidence_steps: list[EvidenceStep]  # always present, may be empty
```

**Where defined:** `core/analysis/evidence.py` (new file, leaf, no imports beyond stdlib + Path)

**Parser interface:**

```python
@register_parser("vasp", "<object_type>")
class VASPXxxProvider:
    engine = "vasp"
    object_type = "<object_type>"

    def can_parse(self, raw_dir: Path) -> bool:
        """Check if required evidence files exist."""
        ...

    def parse(self, evidence: EvidenceBundle) -> AnalysisObject:
        """Parse raw evidence into analysis object."""
        ...
```

**Orchestrator change:** `orchestrator.py` builds one `EvidenceBundle` instead of a kwargs dict (currently lines 80-93). Single point of construction.

**Migration:** All existing providers (VASPBandsProvider, QEBandsProvider) update their `parse()` signature. Since there are only 2 providers today, this is a clean break — no deprecation period needed.

### 4.3 Driver Registration

All capabilities must be declared in `drivers/vasp/driver.py`:

```python
ANALYSIS_CAPABILITIES = [
    # Existing
    AnalysisCapability(
        object_type="bands",
        gen_step_sequence=["bandspw"],
        evidence_files=["EIGENVAL"],
    ),
    # New
    AnalysisCapability(
        object_type="dos",
        gen_step_sequence=["dos"],
        evidence_files=["DOSCAR"],
    ),
    AnalysisCapability(
        object_type="convergence",
        gen_step_sequence=["scf"],
        evidence_files=["OSZICAR"],
    ),
    AnalysisCapability(
        object_type="trajectory",
        gen_step_sequence=["relax"],
        evidence_files=["vasprun.xml"],
    ),
    AnalysisCapability(
        object_type="trajectory",
        gen_step_sequence=["md"],
        evidence_files=["vasprun.xml"],
    ),
    AnalysisCapability(
        object_type="field3d",
        gen_step_sequence=["scf"],
        evidence_files=["CHGCAR"],
    ),
]
```

Note: Two trajectory capabilities (relax and md) — longest-match-first resolution ensures the right one is picked. field3d uses discovery: the provider checks which files (CHGCAR, LOCPOT, ELFCAR) exist and produces one bundle per discovered file.

### 4.4 Orchestration Flow (Existing — Minimal Changes)

```
Run completes
  → runner calls run_post_run_analysis(engine, driver, ordered_gen_steps, ...)
    → orchestrator iterates ANALYSIS_CAPABILITIES
      → find_contiguous_match(capability, ordered_gen_steps)
      → get_parser(engine, object_type) → provider_cls
      → provider.can_parse(raw_dir) → bool
      → orchestrator builds EvidenceBundle
      → provider.parse(evidence) → AnalysisObject
      → analysis_object.to_primitives() → CanonicalPrimitiveBundle
    → cas_writer writes .json.gz to CAS + SQLite row
    → (field3d: also writes .f32 blobs to BlobStore)
```

Only change to `orchestrator.py`: build `EvidenceBundle` instead of kwargs dict. No changes to `cas_writer.py` or kernel routing.

### 4.5 DOSCAR Parser Design

DOSCAR has a complex format. Key details:

```
Header: 5 lines (system info)
Line 6: EMAX EMIN NEDOS EFERMI ???
Lines 7..7+NEDOS-1: Total DOS
  Non-spin: energy, dos, integrated_dos
  Spin:     energy, dos_up, dos_down, int_up, int_down

If LORBIT/RWIGS set, repeat for each atom (NEDOS lines each):
  Non-spin: energy, s, p, d [, f]              (lm-decomposed with LORBIT=10)
  Or:       energy, s, py, pz, px, dxy, ...    (full lm with LORBIT=11)
  Spin:     double columns for each orbital
```

Parser approach:
1. Parse header to get NEDOS, EFERMI, n_atoms_for_pdos
2. Read total DOS block (NEDOS lines)
3. If more data follows: read per-atom PDOS blocks
4. Auto-detect spin from column count (3 = non-spin, 5 = spin for total; variable for PDOS)
5. Auto-detect orbital decomposition from column count in PDOS blocks

### 4.6 OSZICAR Parser Design

OSZICAR is simple line-oriented:

```
Electronic steps (within one ionic step):
   N       E                     dE             d eps             ncg     rms      rms(c)
CG :    1    0.134858E+03    0.13486E+03   -0.18116E+03    40   0.367E+01    0.340E-01

Ionic summary line:
    1 F= -.46855212E+02 E0= -.46855212E+02  d E =-.468552E+02
```

MD variant adds: `T= 300.0  E= -46.85  EK= 0.123  SP= 0.0  SK= 0.0`

Parser approach:
1. Iterate lines, classify: electronic step (starts with `CG :` or `DAV:` or `RMM:`) vs ionic summary (`F=`)
2. Extract energy, dE from electronic step lines
3. Extract F, E0 from ionic summary lines
4. For MD: extract T, EK from extended summary
5. Build flat arrays for SCF history + ionic-step arrays

### 4.7 Trajectory Parser Design (vasprun.xml)

Use streaming `iterparse()` to handle large files:

```python
for event, elem in ET.iterparse(vasprun_path, events=("end",)):
    if elem.tag == "calculation":
        # Extract: structure (positions, cell), forces, stress, energy
        # Build Frame object
        # Clear element to free memory
        elem.clear()
```

Key extractions per `<calculation>` element:
- `<structure>` → positions (direct or Cartesian), lattice
- `<varray name="forces">` → forces array
- `<varray name="stress">` → stress tensor
- `<energy>` → `<i name="e_fr_energy">` and `<i name="e_wo_entrp">`

Fallback path (no vasprun.xml):
- XDATCAR → positions only (sufficient for visualization but no forces/energy)
- Combine with OSZICAR for energy per ionic step

### 4.8 CHGCAR/LOCPOT/ELFCAR Parser Design

All three file types share an identical format:

```
POSCAR header (lattice + species + positions)
<blank line>
NGX NGY NGZ
data values (FORTRAN i-fastest order, whitespace-separated)
<blank line>           # CHGCAR only: separator before augmentation charges
augmentation data      # CHGCAR only: PAW augmentation occupancies
```

Parser approach (`parse_chgcar_text()`):
1. Parse POSCAR header to extract lattice vectors and species
2. Skip blank line, read NGX/NGY/NGZ grid dimensions
3. Read `NGX*NGY*NGZ` float values into flat array
4. Reshape to 3D grid with FORTRAN (i-fastest) ordering
5. For CHGCAR: detect blank line separator, parse augmentation grid separately
6. Compute VolumeMetadata: grid_shape, origin (always [0,0,0] for VASP), grid_vectors from lattice
7. Write full grid to BlobStore as `.f32`, compute preview via `downsample_grid(factor=4)`
8. Return VolumeMetadata with blob_id and preview_blob_id

---

## 5. Testing and Demo Strategy

### 5.1 Unit Tests Per Parser

Each new parser gets comprehensive unit tests following the `test_vasp_bands_parser.py` pattern:

| Parser | Test file | Fixture dir | Key assertions |
|--------|-----------|-------------|----------------|
| DOS | `tests/drivers/vasp/test_vasp_dos_parser.py` | `tests/data/analysis_vasp_dos/` | NEDOS count, energy range, Fermi, spin channels, PDOS shape |
| Convergence | `tests/drivers/vasp/test_vasp_convergence_parser.py` | `tests/data/analysis_vasp_convergence/` | SCF step count, ionic step count, energy monotonicity |
| Trajectory | `tests/drivers/vasp/test_vasp_trajectory_parser.py` | `tests/data/analysis_vasp_trajectory/` | Frame count, position shape, energy per frame, force shape |
| field3d | `tests/drivers/vasp/test_vasp_field3d_parser.py` | `tests/data/analysis_vasp_field3d/` | Grid shape, data_order, blob_id, preview dims, augmentation |

### 5.2 Test Fixtures Required

For each object_type, create curated VASP output fixtures:

**DOS fixtures** (`tests/data/analysis_vasp_dos/`):
- `DOSCAR` — Si total DOS (non-spin, NEDOS=301)
- `DOSCAR_spin` — Fe spin-polarized DOS
- `DOSCAR_pdos` — TiO2 with LORBIT=11 (full lm PDOS)
- `vasprun.xml` — minimal (just efermi)

**Convergence fixtures** (`tests/data/analysis_vasp_convergence/`):
- `OSZICAR_scf` — Single ionic step, ~15 SCF steps
- `OSZICAR_relax` — 10 ionic steps, converged
- `OSZICAR_md` — 50 MD steps with T, EK

**Trajectory fixtures** (`tests/data/analysis_vasp_trajectory/`):
- `vasprun_relax.xml` — Si relaxation, 5 ionic steps (small)
- `XDATCAR_md` — Al MD, 20 steps (fallback path)
- `OSZICAR_md` — matching energies for XDATCAR fallback

**field3d fixtures** (`tests/data/analysis_vasp_field3d/`):
- `CHGCAR_small` — 2-atom Si cell, small FFT grid (e.g., 24x24x24) for fast tests
- `LOCPOT_small` — matching LOCPOT for the same cell

### 5.3 field3d Unit Tests

- Parse CHGCAR → VolumeMetadata with correct grid_shape, origin, grid_vectors
- Verify data_order is FORTRAN_I_FASTEST
- Verify blob_id is registered in BlobStore
- Verify preview grid dimensions = full_grid / downsample_factor
- Verify augmentation charges separated from valence
- Parse LOCPOT → field_kind = "potential" (no augmentation section)

### 5.4 Golden Daemon E2E Tests

Extend the existing VASP golden test (`test_vasp_bands_golden_daemon.py`) or create per-object-type golden tests:

| object_type | Demo project | Assertion |
|-------------|-------------|-----------|
| bands | `si_bands_vasp_demo` (EXISTS) | `len(k_distances) == 200`, smooth band curves |
| dos | `si_dos_vasp_demo` (NEW) | `len(energies) == NEDOS`, energy range spans Fermi |
| convergence | (part of bands demo SCF step) | `len(scf_steps) > 5`, energy decreases |
| trajectory | `si_relax_vasp_demo` (NEW) | `len(frames) >= 3`, forces decrease |
| field3d | (part of existing SCF demo) | grid_shape matches NGXF/NGYF/NGZF, blob exists |

### 5.5 Gate Test Extensions

Add to `tests/gates/test_analysis_invariants.py`:

```python
def test_vasp_analysis_capabilities_cover_five_types():
    """Gate: VASP driver must declare capabilities for all 5 types."""
    from quantumvitas.drivers.vasp.driver import VASPDriver
    driver = VASPDriver()
    object_types = {cap.object_type for cap in driver.ANALYSIS_CAPABILITIES}
    assert {"bands", "dos", "convergence", "trajectory", "field3d"}.issubset(object_types)
```

---

## 6. Implementation Order

Strict dependency-aware ordering:

### Phase 1: K-distance fix + EvidenceBundle (small, foundational)

1. Create `core/analysis/evidence.py` — `EvidenceBundle` dataclass
2. Update `orchestrator.py` to build `EvidenceBundle`
3. Update VASPBandsProvider.parse() and QEBandsProvider.parse() signatures
4. Fix `_compute_k_distances()` to use reciprocal Cartesian (see §2.1.1)
5. Fix `_read_kpoints_labels()` similarly
6. Add non-cubic lattice regression test (hexagonal BN or FCC Al)
7. Update golden test expected values if canonical SHA changes

### Phase 2: DOS (highest user value among new types)

1. Create `core/analysis/dos/model.py` — `DOS` dataclass + `to_primitives()`
2. Create `drivers/vasp/parsers/dos.py` — `VASPDOSProvider` + `parse_doscar()`
3. Register capability in `drivers/vasp/driver.py`
4. Add `"dos"` to `SUPPORTED_GEN_STEPS` if not implicit via zero-mapping
5. Create test fixtures + unit tests
6. Create `si_dos_vasp_demo` demo project template
7. Golden daemon E2E test

### Phase 3: Convergence (simplest new parser)

1. Create `core/analysis/convergence/model.py` — `Convergence` dataclass + `to_primitives()`
2. Create `drivers/vasp/parsers/convergence.py` — `VASPConvergenceProvider` + `parse_oszicar()`
3. Register capability
4. Test fixtures + unit tests
5. (No separate demo needed; convergence extracted from existing SCF step)

### Phase 4: Trajectory (most complex, leverages existing model)

1. Create `drivers/vasp/parsers/trajectory.py` — `VASPTrajectoryProvider`
2. Implement vasprun.xml streaming parser
3. Implement XDATCAR + OSZICAR fallback
4. Register capabilities (both relax and md)
5. Test fixtures + unit tests
6. Create `si_relax_vasp_demo` demo project template
7. Golden daemon E2E test

### Phase 5: field3d (leverages existing ~930 lines of volumetric infra)

1. Create CHGCAR parser in `drivers/vasp/parsers/field3d.py` — `parse_chgcar_text()`
2. Reuse `VolumeMetadata`, `BlobStore`, `downsample_grid()`
3. Register capability in `drivers/vasp/driver.py`
4. Test fixtures (small CHGCAR/LOCPOT) + unit tests
5. Wire into CAS with JSON manifest + blob_id reference

---

## 7. Open Questions

**Q1: DOS gen_step_sequence — `["dos"]` vs `["nscf"]`**

VASP DOS can be computed from either an explicit `vasp_dos` step or as a byproduct of an NSCF calculation. Should we register two capabilities or just one?

**Recommendation:** Register both. The orchestrator's longest-match-first resolution handles conflicts. `["dos"]` matches `vasp_dos` step type; `["nscf"]` matches `vasp_nscf`.

**Q2: Convergence for relax/MD — separate or part of trajectory?**

Should the convergence object_type also be produced for relax/MD steps (where OSZICAR has both SCF and ionic convergence data)? Or should trajectory's `get_observable_series("energy")` suffice?

**Recommendation:** Convergence for `["scf"]` only initially. Trajectory already captures ionic-step energy/forces via `Frame.energy` and `Frame.forces`. SCF-within-ionic detail is niche and can be added later.

**Q3: DOSCAR PDOS column auto-detection**

DOSCAR projected DOS has variable column counts depending on LORBIT setting (10 vs 11 vs 12) and ISPIN and LNONCOLLINEAR. How robust does auto-detection need to be?

**Recommendation:** Support the two common cases: LORBIT=10 (spd only) and LORBIT=11 (full lm). Non-collinear is deferred. Column count math: `n_cols = 1 + n_orbitals * n_spin` where `n_orbitals` is 3 (spd), 9 (spdf), or 16 (full lm).

**Q4: vasprun.xml size limit for trajectory**

For very long MD runs, vasprun.xml can be hundreds of MB. Should we impose a hard size limit and fall back to XDATCAR + OSZICAR?

**Recommendation:** No hard limit. Use streaming `iterparse()` with element clearing. Add an optional `max_frames` parameter to the parser (default: unlimited). Log a warning if the file exceeds 100 MB.

**Q5: Demo project for DOS — what step YAML parameters?**

The Si bands demo uses `{kpoints: {mode: line, npoints: 40, path: G-X-W-K-G-L}}`. What should the DOS demo specify?

**Recommendation:** Si DOS with `{incar: {ISMEAR: -5, NEDOS: 301, LORBIT: 11}, kpoints: {mode: automatic, mesh: [12, 12, 12]}}`. This produces both total DOS and PDOS in a single run.

**Q6: field3d capability: one-per-file vs discovery?**

Should we register separate capabilities for CHGCAR, LOCPOT, and ELFCAR, or a single field3d capability whose provider discovers which files exist?

**Recommendation:** Discovery approach. Single capability registered; provider checks which files exist (CHGCAR, LOCPOT, ELFCAR, PARCHG) and produces one bundle per discovered file. Avoids capability explosion.

**Q7: field3d CAS extension — blob_id reference or bypass CAS?**

Should the JSON manifest in CAS contain a blob_id reference, or should field3d bypass CAS entirely and live only in BlobStore?

**Recommendation:** JSON manifest in CAS with blob_id reference. Maintains the provenance chain (CAS SHA tracks which blob was produced from which run). BlobStore holds the heavy data; CAS holds the lightweight metadata.

**Q8: EvidenceBundle backward compat — accept old-style kwargs during transition?**

Should providers continue to accept the old 6-kwarg `parse()` signature during a transition period?

**Recommendation:** No. Clean break. Only 2 providers exist today (VASPBandsProvider, QEBandsProvider). Both are updated in Phase 1 alongside the orchestrator. No deprecation shim needed.

---

## 8. Scope Boundaries

**IN scope:**
- 5 object_types for VASP: bands, dos, convergence, trajectory, field3d
- K-distance fix (reciprocal Cartesian metric)
- EvidenceBundle typed context (replaces kwargs sprawl)
- field3d design leveraging existing volumetric infrastructure

**OUT of scope:**
- Phonons, elastic, dielectric, optical analysis types
- Fat bands (orbital projection from PROCAR)
- Projection selection DSL (`"Ti(d) - O(p)"`)
- HDF5 support (VASP 6.4+ `vaspout.h5`)
- Non-VASP field3d (Wannier90 XSF/BXSF uses existing `volume_parsers.py` independently)

**DEFERRED:**
- Non-collinear spin / SOC bands
- GW self-energy (SIGMA file)
- BSE spectra (from vasprun.xml or dedicated files)
- PARCHG (partial charge density) — same format as CHGCAR, included in field3d discovery list

---

## Appendix A: VASP Output File Reference

| File | Size | Always produced | Content | Used by |
|------|------|----------------|---------|---------|
| EIGENVAL | ~100 KB | Yes (bands) | k-points + eigenvalues | bands |
| DOSCAR | ~50 KB | Yes (DOS calcs) | Energy grid + DOS/PDOS | dos |
| OSZICAR | <10 KB | Always | SCF/ionic convergence | convergence, trajectory (energy) |
| vasprun.xml | 1 MB - 1 GB | Always | Everything (XML) | trajectory (primary), fermi energy, fallback for all |
| OUTCAR | 10 MB - 500 MB | Always | Human-readable log | fermi energy fallback, timing |
| XDATCAR | ~100 KB | Relax/MD | Positions per ionic step | trajectory (fallback) |
| KPOINTS | <1 KB | Always | k-mesh or k-path definition | bands (labels) |
| PROCAR | ~10 MB | If LORBIT set | Orbital projections | bands (fat bands, future) |
| CHGCAR | 10 - 500 MB | If LCHARG=T | Charge density grid | field3d |
| LOCPOT | 10 - 500 MB | If written | Electrostatic potential | field3d |
| ELFCAR | 10 - 500 MB | If LELF=T | Electron localization function | field3d |
| PARCHG | 10 - 500 MB | If LPARD=T | Partial charge density | field3d |
| CONTCAR | ~1 KB | Always | Final structure | (not analysis; used for restart) |

## Appendix B: Cross-Engine Alignment

The five object_types are engine-agnostic. Here is the mapping to QE (the other mature engine):

| object_type | VASP parser | QE parser | Shared model |
|-------------|------------|-----------|--------------|
| bands | VASPBandsProvider (EIGENVAL) | QEBandsProvider (bands.dat) | `BandStructure` |
| dos | VASPDOSProvider (DOSCAR) | (future: QEDOSProvider) | `DOS` (new) |
| convergence | VASPConvergenceProvider (OSZICAR) | (future: QEConvergenceProvider) | `Convergence` (new) |
| trajectory | VASPTrajectoryProvider (vasprun.xml) | (future: QETrajectoryProvider) | `Trajectory` (exists) |
| field3d | VASPField3DProvider (CHGCAR/LOCPOT/ELFCAR) | (future: uses existing volume_parsers.py) | `VolumeMetadata` (exists) |

Both engines produce the same `CanonicalPrimitiveBundle` schema per object_type. The viz layer is truly engine-agnostic.
