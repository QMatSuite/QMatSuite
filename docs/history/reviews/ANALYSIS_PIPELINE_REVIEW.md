# Analysis Pipeline Review

**Date:** 2026-02-19
**Scope:** End-to-end trace of QMatSuite's analysis pipeline from engine output parsing through CanonicalPrimitiveBundle to visualization/file export.

---

## 1. Entry Points

### Q1: How does the GUI go from "user selects a step" to AnalysisObject?

There are **two operational paths** through the service layer:

**Path A — Live derivation (Surface C):**
```
svc.analysis.get_analysis(run_ulid, object_type, transforms=[])
```
File: `src/quantumvitas/api/service.py:1062`

Internally calls:
1. `_resolve_run_analysis_context(run_ulid)` — resolves calc, engine, driver, and ordered gen-steps from provenance DB
2. `_derive_canonical_for_run_object(run_ulid, object_type)` — orchestrates the full pipeline
3. `run_post_run_analysis(engine, driver, ordered_gen_steps, ...)` — the kernel-layer orchestrator at `src/quantumvitas/core/analysis/orchestrator.py:22`
4. Returns `{"run_ulid", "object_type", "canonical_sha", "bundle": {...}}`

**Path B — Replay from cache:**
```
svc.analysis.get_analysis_snapshot(run_ulid, object_type)
```
File: `src/quantumvitas/api/service.py:1093`

Reads pre-computed canonical bundle from CAS (`.provenance/.cas/analysis/<sha>.json.gz`) using SQLite linkage in `analysis_snapshots` table.

**Path C — Step-scoped enumeration (Domain B):**
```
svc.analysis.get_analysis_instances_for_step(calc_selector, step_ulid)
```
File: `src/quantumvitas/api/service.py:1105`

Lists ALL analysis instances whose matched step_ulids include the given step. Used by the GUI to show "what analyses are available for this step."

### Q2: How does the system know which AnalysisObject types are available?

Each engine driver declares `ANALYSIS_CAPABILITIES: List[AnalysisCapability]` as a class attribute on its driver class. This is a static declaration — no computation needed to enumerate what's possible.

**AnalysisCapability** (`src/quantumvitas/core/analysis/capability.py:42`):
```python
@dataclass(frozen=True)
class AnalysisCapability:
    object_type: str            # "bands", "dos", "convergence", etc.
    gen_step_sequence: list[str]  # Required GEN steps, e.g. ["scf"] or ["bandspw"]
    evidence_files: list[str]    # Glob patterns for expected output files
```

Example from QE driver (`src/quantumvitas/drivers/qe/driver.py`):
```python
ANALYSIS_CAPABILITIES = [
    AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"], evidence_files=["*.bands.dat.gnu"]),
    AnalysisCapability(object_type="dos", gen_step_sequence=["dos"], evidence_files=["*.dos.dat"]),
    AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"], evidence_files=["*.out"]),
    AnalysisCapability(object_type="convergence", gen_step_sequence=["relax"], evidence_files=["*.out"]),
    AnalysisCapability(object_type="trajectory", gen_step_sequence=["relax"], evidence_files=["*.relax.out"]),
    AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"], evidence_files=["*.md.out"]),
    AnalysisCapability(object_type="field3d", gen_step_sequence=["scf"], evidence_files=["*.cube"]),
    # ...
]
```

### Q3: Can availability be checked without parsing?

**Yes.** The `enumerate_all_matches()` function (`src/quantumvitas/core/analysis/capability.py`) performs pure capability-to-step matching using only step type sequences. No file I/O is needed. This provides the lightweight "this step COULD produce X" check.

The heavier `can_parse()` method on each provider does check for actual file existence (glob-based) but still doesn't parse content.

### Q4: Entry point signature

The kernel-layer entry point is:

```python
# src/quantumvitas/core/analysis/orchestrator.py:22
def run_post_run_analysis(
    engine: str,
    driver: Any,                          # Driver instance with ANALYSIS_CAPABILITIES
    ordered_gen_steps: List[Tuple[str, str, Path]],  # [(step_ulid, gen_step, evidence_dir), ...]
    *,
    run_ulid: Optional[str] = None,
    calc_ulid: Optional[str] = None,
    calc_dir: Optional[Path] = None,
) -> List[AnalysisResult]
```

---

## 2. AnalysisObject Types

### Complete Catalog

There are **7 canonical analysis object types** + **1 lightweight digest type**:

| Object Type | Class | File | Purpose |
|---|---|---|---|
| `convergence` | `Convergence` | `core/analysis/convergence/model.py` | SCF/ionic convergence history |
| `dos` | `DOS` | `core/analysis/dos/model.py` | Density of states (total + projected) |
| `bands` | `BandStructure` | `core/analysis/band_structure/model.py` | Electronic band structure + fatbands |
| `trajectory` | `Trajectory` | `core/analysis/trajectory/model.py` | MD / relax / NEB geometry evolution |
| `field3d` | `Field3D` | `core/analysis/field3d.py` | 3D volumetric data (charge, ELF, etc.) |
| `neb_trajectory` | `Trajectory` | `core/analysis/trajectory/model.py` | NEB-specific trajectory (QE only) |
| `scf_digest` | `*Digest` (per-engine) | `drivers/*/parsers/output.py` | Lightweight single-point summary |

### Detailed Data Structures (3 examples)

#### Convergence (`core/analysis/convergence/model.py`)
```python
@dataclass
class Convergence:
    meta: AnalysisObjectMeta
    scf_step: np.ndarray          # Cumulative SCF step indices (int)
    scf_energy: np.ndarray        # Energy per SCF step (eV)
    scf_de: np.ndarray            # dE per SCF step (eV)
    ionic_step: np.ndarray        # Ionic step indices (int)
    ionic_energy: np.ndarray      # Energy per ionic step (eV)
    ionic_max_force: Optional[np.ndarray]  # Max force per ionic step (eV/A)
    converged: bool
    n_ionic_steps: int
    algorithm: str                # "CG", "DAV", "RMM", etc.
```

#### DOS (`core/analysis/dos/model.py`)
```python
@dataclass
class DOS:
    meta: AnalysisObjectMeta
    energies: np.ndarray          # 1D energy grid (nedos,), eV
    total_dos: np.ndarray         # 1D (nedos,) or 2D (2, nedos) for spin
    fermi_energy: Optional[float] # Fermi energy in eV
    integrated_dos: Optional[np.ndarray]  # (nedos,)
    pdos: Optional[np.ndarray]    # (n_atoms, nedos, n_orbitals)
    atom_labels: Optional[List[str]]      # "Ti_1", "O_1", etc.
    orbital_labels: Optional[List[str]]   # "s", "p", "d", etc.
    spin_polarized: bool
```

#### BandStructure (`core/analysis/band_structure/model.py`)
```python
@dataclass
class BandStructure:
    meta: AnalysisObjectMeta
    k_distances: np.ndarray       # 1D k-path distances
    eigenvalues: np.ndarray       # 2D (nk, nb) or 3D (nspin, nk, nb)
    high_symmetry_points: List[HighSymPoint]  # (k_distance, label)
    fermi_energy: Optional[float]
    spin_polarized: bool
    projections: Optional[np.ndarray]  # 4D (nk, nb, natoms, norb) for fatbands
    projection_labels: Optional[Dict[str, List[str]]]
```

### Per-Engine Analysis Support Matrix

| Engine | convergence | dos | bands | trajectory | field3d | scf_digest |
|---|---|---|---|---|---|---|
| **QE** | scf, relax, md | dos | bandspw | relax, md, neb | scf | yes |
| **VASP** | scf, relax, md | dos | bandspw | relax, md | scf | yes |
| **ABINIT** | scf, relax | nscf | nscf | relax, md | scf | yes |
| **CP2K** | scf, relax | dos | bandspw | relax, md | scf | yes |
| **Siesta** | scf, relax | dos | bands | relax, md | scf | yes |
| **GPAW** | scf, relax, bandspw | dos | bandspw | relax, md | scf | yes |
| **ORCA** | scf, relax | - | - | relax | scf | yes |
| **Gaussian** | scf,hf,relax,td,mp2,freq | - | - | relax | scf | yes |
| **PySCF** | scf, relax | - | - | relax | scf | yes |
| **Psi4** | scf, relax | - | - | relax | scf | yes |
| **QMCPACK** | vmc, dmc | - | - | - | - | yes |
| **LAMMPS** | - | - | - | md, minimize | - | yes |
| **xTB** | - | - | - | relax, md | - | yes |
| **Wannier90** | - | - | - | - | wannier | yes |
| **Yambo** | - | - | - | - | - | yes |

---

## 3. CanonicalPrimitive

### Core Primitive Data Types (`core/analysis/primitives.py`)

```python
@dataclass
class Series1D:
    x: np.ndarray       # X-axis values
    y: np.ndarray       # Y-axis values
    x_label: str        # Axis label
    y_label: str
    x_unit: str         # Physical unit
    y_unit: str
    name: Optional[str] = None

@dataclass
class GeometryFrame:
    positions: np.ndarray              # (N, 3) UNWRAPPED Cartesian A
    species: List[str]                 # N element symbols
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]
    forces: Optional[np.ndarray] = None        # (N, 3) eV/A
    velocities: Optional[np.ndarray] = None    # (N, 3) A/fs

@dataclass
class GeometryFrames:
    frames: List[GeometryFrame]
    time: Optional[np.ndarray] = None          # fs
    iteration: Optional[np.ndarray] = None
    image_indices: Optional[np.ndarray] = None # NEB

@dataclass
class Marker:
    position: float
    label: str
    axis: str = "x"  # "x" or "y"
```

### Bundle Types (`core/analysis/bundles.py`)

**CanonicalPrimitiveBundle** — immutable output of `to_primitives()`:
```python
@dataclass
class CanonicalPrimitiveBundle:
    bundle_kind: str = "canonical"
    object_type: str               # "dos", "bands", "convergence", etc.
    render_meta: RenderMeta        # Display hints (labels, units, Fermi ref, markers)
    provenance_meta: ProvenanceMeta # Tracking (run/calc/step ULIDs, parser info)
    series: List[Series1D]         # All 1D curves
    geometry_frames: Optional[GeometryFrames] = None  # For trajectory
    arrays: Dict[str, Any] = {}    # Raw numpy arrays for downstream use
```

**RenderMeta** — display hints (NOT style, data only):
```python
@dataclass
class RenderMeta:
    axis_labels: Dict[str, str]              # {"x": "Energy", "y": "DOS"}
    units: Dict[str, str]                    # {"x": "eV", "y": "states/eV"}
    series_labels: Optional[List[str]] = None
    reference_energy: Optional[float] = None  # Fermi level for FermiShift
    reference_position: Optional[float] = None
    markers: List[Marker] = []               # K-path labels, etc.
    extra: Dict[str, Any] = {}               # Type-specific hints
```

**DerivedPrimitiveBundle** — post-transform output:
```python
@dataclass
class DerivedPrimitiveBundle(CanonicalPrimitiveBundle):
    bundle_kind: str = "derived"
    transform_chain: List[TransformRecord] = []  # Audit trail
```

### Conversion: AnalysisObject -> CanonicalPrimitiveBundle

Every AnalysisObject implements `.to_primitives() -> CanonicalPrimitiveBundle`. This is a method on the object itself, not a separate converter:

```
AnalysisObject.to_primitives()
  -> CanonicalPrimitiveBundle(
       series=[Series1D(...)],
       render_meta=RenderMeta(...),
       provenance_meta=ProvenanceMeta(...),
       arrays={...raw numpy data...}
     )
```

**Per-type conversion highlights:**
- **Convergence**: 4 series (SCF energy, SCF dE, ionic energy, ionic max force)
- **DOS**: 1+ series (total DOS, optional per-spin, optional per-atom PDOS)
- **BandStructure**: N series (one per band), markers for high-symmetry points
- **Trajectory**: GeometryFrames + observable series (energy, temperature, pressure)
- **Field3D**: No series (volumetric); arrays contain downsampled preview + metadata. Full grid is **primitive-by-reference** (not embedded due to size).

### Transform Layer (`core/analysis/transforms/`)

Transforms operate on bundles and produce `DerivedPrimitiveBundle`:

| Transform | File | Purpose |
|---|---|---|
| `FermiShift` | `fermi_shift.py` | Shift energy axis by reference_energy |
| `EnergyCrop` | `energy_crop.py` | Window to [emin, emax] |
| `Smoothing` | `smoothing.py` | Running average (np.convolve) |
| `FrameSlice` | `frame_slice.py` | Subset trajectory frames |
| `MSD` | `msd.py` | Mean square displacement |
| `RDF` | `rdf.py` | Radial distribution function |
| `VACF` | `vacf.py` | Velocity autocorrelation |
| `DiffusionCoefficient` | `diffusion.py` | From MSD slope (D = slope/6) |

Base class at `core/analysis/transforms/base.py`:
```python
class PrimitiveTransform(ABC):
    name: str
    version: str = "1.0"
    def apply(self, bundle: PrimitiveBundle) -> DerivedPrimitiveBundle: ...
    def validate(self, bundle: PrimitiveBundle) -> list[str]: ...
```

Currently the service API only exposes FermiShift through `get_analysis(..., transforms=["fermi_shift"])`.

---

## 4. Visualization Pipeline

### Two Visualization Systems

QMatSuite has **two** visualization layers, serving different purposes:

#### System 1: Legacy QE-specific plotting (`analysis/plotting.py` + `analysis/parsers.py`)

- Uses QE-native data structures (`SCFResult`, `DOSData`, `BandStructureData` from `analysis/parsers.py`)
- Direct matplotlib rendering: `plot_dos()`, `plot_bands()`, `plot_scf_convergence()`
- File export via `save_figure(fig, path, formats=['png', 'svg', 'pdf'])`
- **Fully headless**: `matplotlib.use('Agg')` set at import time
- Tested in `tests/unit/test_analysis_plotting.py`

```python
# Example usage
from quantumvitas.analysis.parsers import parse_dos_data
from quantumvitas.analysis.plotting import plot_dos, save_figure

dos_data = parse_dos_data("si.dos.dat")
fig, ax = plot_dos(dos_data, shift_fermi=True)
save_figure(fig, "dos.png", formats=["png", "svg"])
```

#### System 2: Canonical pipeline (CanonicalPrimitiveBundle)

- Engine-agnostic data structures (Series1D, GeometryFrames)
- Bundles carry all data + render hints for any frontend
- Serializable to JSON via `.to_dict()`
- **No built-in renderer** — bundles are designed for external consumers (GUI, web, MCP)
- The GUI renders bundles directly; no headless PNG/SVG exporter exists for canonical bundles

### Structure Visualization (`analysis/structure_viz.py`, 2062 lines)

Separate from the analysis pipeline — renders atomic structures:
- `visualize_structure(structure, output_path=..., supercell=..., ...)` — matplotlib 3D
- `build_structure_vis_payload(structure, params)` — JSON payload for daemon RPC
- Ball-and-stick with CPK colors, bond detection (O(N) cell-list), supercell expansion
- Fully headless: `matplotlib.use('Agg')`

### Can the viz module output to file?

**System 1**: Yes, via `save_figure(fig, path, dpi=150, formats=['png', 'svg', 'pdf'])`
**System 2 (canonical)**: No built-in file renderer. Bundles serialize to JSON for external consumers.
**Structure viz**: Yes, via `visualize_structure(..., output_path="structure.png")`

### Non-GUI programmatic rendering?

**System 1**: Yes, fully programmatic:
```python
from quantumvitas.analysis.plotting import plot_dos, save_figure
fig, ax = plot_dos(dos_data)
save_figure(fig, "output.png")
```

**System 2**: Would require writing a thin adapter:
```python
# Hypothetical: CanonicalPrimitiveBundle -> matplotlib
bundle = convergence_obj.to_primitives()
fig, ax = plt.subplots()
for s in bundle.series:
    ax.plot(s.x, s.y, label=s.name)
ax.set_xlabel(f"{bundle.render_meta.axis_labels['x']} ({bundle.render_meta.units['x']})")
fig.savefig("convergence.png")
```

---

## 5. results/ Directory

### Where is it created?

The `results/` directory is created inside `analyze_calculation()` at `src/quantumvitas/analysis/calculation_analysis.py:17`:

```python
def analyze_calculation(calculation: Calculation, result: CalculationResult) -> None:
    results_dir = calculation.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    # Writes summary.json, energy summaries, DOS analysis
```

This is a **legacy path** that creates `<calc_dir>/results/` and writes:
- `summary.json` — calculation result dict
- Energy summaries (from `analysis/energy.py`)
- DOS analysis files (from `analysis/dos.py`)

### What's currently written?

For a QE calculation, the `results/` directory contains legacy artifacts from System 1:
- `summary.json` — raw calculation result
- Energy-related summaries
- DOS data files (if applicable)

### Conventions

No formal naming conventions documented. The legacy system uses descriptive names (`summary.json`, etc.). The canonical pipeline does NOT write to `results/` — it uses CAS instead (`.provenance/.cas/analysis/<sha>.json.gz`).

---

## 6. Full Path Traces

### Trace 1: Si DOS (completed QE DOS workflow, step 2 = qe_dos)

```
1. User calls: svc.analysis.get_analysis(run_ulid="01ABC...", object_type="dos")
   File: src/quantumvitas/api/service.py:1062

2. _resolve_run_analysis_context(run_ulid)
   File: src/quantumvitas/api/service.py:379
   -> Loads calc from provenance DB
   -> Gets engine="qe", driver=QEDriver
   -> Builds ordered_gen_steps = [
        ("step0_ulid", "scf", /path/to/raw/scf/),
        ("step1_ulid", "nscf", /path/to/raw/nscf/),
        ("step2_ulid", "dos", /path/to/raw/dos/)
      ]

3. _derive_canonical_for_run_object(run_ulid, "dos")
   File: src/quantumvitas/api/service.py:441
   -> Calls run_post_run_analysis(...)

4. run_post_run_analysis("qe", qe_driver, ordered_gen_steps)
   File: src/quantumvitas/core/analysis/orchestrator.py:22
   -> capabilities = qe_driver.ANALYSIS_CAPABILITIES
   -> matches = enumerate_all_matches(capabilities, ordered_gen_steps)
      -> Finds AnalysisCapability(object_type="dos", gen_step_sequence=["dos"])
      -> Match: step_ulids=["step2_ulid"], evidence_dirs=[/path/to/raw/dos/]

5. get_parser("qe", "dos")
   File: src/quantumvitas/parsers/registry.py
   -> Returns QEDOSProvider class

6. provider.can_parse(evidence_dir)
   File: src/quantumvitas/drivers/qe/parsers/dos.py
   -> Checks for *.dos.dat files in evidence dir

7. provider.parse(evidence_bundle)
   File: src/quantumvitas/drivers/qe/parsers/dos.py
   -> Reads si.dos.dat: energy grid, total DOS, integrated DOS
   -> If PDOS files exist, reads per-atom projections
   -> Constructs DOS(meta=..., energies=..., total_dos=..., fermi_energy=...)

8. dos_obj.to_primitives()
   File: src/quantumvitas/core/analysis/dos/model.py
   -> Creates Series1D(x=energies, y=total_dos, x_label="Energy", y_label="DOS", ...)
   -> Sets render_meta.reference_energy = fermi_energy
   -> Returns CanonicalPrimitiveBundle(object_type="dos", series=[...], ...)

9. write_canonical_to_cas(canonical, cas_dir)
   File: src/quantumvitas/core/analysis/cas_writer.py
   -> Computes SHA of serialized bundle
   -> Writes .provenance/.cas/analysis/<sha>.json.gz

10. Returns to caller: {"run_ulid": ..., "object_type": "dos",
                         "canonical_sha": ..., "bundle": {...}}
```

### Trace 2: SCF Convergence (step 0 = qe_scf)

```
1. svc.analysis.get_analysis(run_ulid, "convergence")

2. _resolve_run_analysis_context(run_ulid)
   -> ordered_gen_steps = [("step0_ulid", "scf", /path/to/raw/scf/)]

3. run_post_run_analysis("qe", driver, ordered_gen_steps)
   -> Matches AnalysisCapability(object_type="convergence", gen_step_sequence=["scf"])

4. get_parser("qe", "convergence")
   -> Returns QEConvergenceProvider

5. provider.parse(evidence_bundle)
   File: src/quantumvitas/drivers/qe/parsers/convergence.py
   -> Reads *.out file
   -> Extracts per-SCF-iteration: step index, energy (Ry->eV), dE
   -> Extracts per-ionic-step: energy, max force
   -> Returns Convergence(scf_step=[...], scf_energy=[...], ...)

6. convergence.to_primitives()
   File: src/quantumvitas/core/analysis/convergence/model.py
   -> Series1D: SCF energy vs step
   -> Series1D: SCF dE vs step
   -> Series1D: Ionic energy vs step (if relax)
   -> Series1D: Ionic max force vs step (if available)
   -> CanonicalPrimitiveBundle(object_type="convergence", series=[...])

7. CAS persistence + return bundle dict
```

### Trace 3: Band Structure (bands workflow: scf -> nscf -> bandspw)

```
1. svc.analysis.get_analysis(run_ulid, "bands")

2. _resolve_run_analysis_context(run_ulid)
   -> ordered_gen_steps = [
        ("s0", "scf", /raw/scf/),
        ("s1", "nscf", /raw/nscf/),     # (if present)
        ("s2", "bandspw", /raw/bandspw/)
      ]

3. run_post_run_analysis("qe", driver, ordered_gen_steps)
   -> Matches AnalysisCapability(object_type="bands", gen_step_sequence=["bandspw"])
   -> evidence_dir = /raw/bandspw/

4. get_parser("qe", "bands")
   -> Returns QEBandsProvider

5. provider.parse(evidence_bundle)
   File: src/quantumvitas/drivers/qe/parsers/bands.py
   -> Reads *.bands.dat.gnu (gnuplot format)
   -> Extracts k_distances, eigenvalues per band
   -> Reads high_symmetry_points from bands.x output
   -> Gets fermi_energy from SCF output (via evidence_steps)
   -> Returns BandStructure(k_distances=..., eigenvalues=...,
                            high_symmetry_points=[...], fermi_energy=...)

6. bands.to_primitives()
   File: src/quantumvitas/core/analysis/band_structure/model.py
   -> Series1D per band: x=k_distances, y=eigenvalues[band_i]
   -> Markers from high_symmetry_points (Gamma, X, L, etc.)
   -> render_meta.reference_energy = fermi_energy
   -> arrays["eigenvalues"], arrays["k_distances"], arrays["projections"]
   -> CanonicalPrimitiveBundle(object_type="bands", series=[...], ...)

7. CAS persistence + return bundle dict
```

---

## 7. Gaps & Missing Pieces

### Can we call the pipeline from outside the GUI without modification?

**Yes.** All imports are headless-safe:
```python
# Verified working (2026-02-19):
from quantumvitas.core.analysis.convergence.model import Convergence     # OK
from quantumvitas.core.analysis.dos.model import DOS                      # OK
from quantumvitas.core.analysis.band_structure.model import BandStructure # OK
from quantumvitas.core.analysis.trajectory.model import Trajectory        # OK
from quantumvitas.core.analysis.field3d import Field3D                    # OK
from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle   # OK
from quantumvitas.core.analysis.orchestrator import run_post_run_analysis # OK
from quantumvitas.core.analysis.transforms.fermi_shift import FermiShift  # OK
from quantumvitas.analysis.plotting import plot_dos, save_figure          # OK (Agg backend)
from quantumvitas.parsers.registry import get_parser                      # OK
```

No circular dependencies or GUI imports block headless use.

### Is there a non-GUI renderer?

**For System 1 (legacy QE-specific):** Yes, `analysis/plotting.py` with Agg backend produces PNG/SVG/PDF headlessly.

**For System 2 (canonical bundles):** **No.** There is no `render_bundle(bundle) -> Figure` function. Canonical bundles serialize to JSON dicts for external consumers. Building a headless renderer for canonical bundles requires:
1. A `bundle_to_matplotlib(bundle) -> Figure` adapter (~100 LOC per object type)
2. Dispatch on `bundle.object_type` to select appropriate plot layout
3. Reading axis labels, units, markers from `render_meta`

### Are there any circular dependencies or GUI imports?

**No.** Both `analysis/plotting.py` and `analysis/structure_viz.py` force `matplotlib.use('Agg')` at import time. The core analysis package (`core/analysis/`) has zero GUI dependencies. The `analysis/` package depends only on matplotlib and numpy.

### Two-system gap

The **legacy parsers** (`analysis/parsers.py`) produce `SCFResult`, `DOSData`, `BandStructureData` — these are QE-specific and feed into `analysis/plotting.py`.

The **canonical parsers** (`drivers/*/parsers/*.py`) produce `Convergence`, `DOS`, `BandStructure` — these are engine-agnostic and produce `CanonicalPrimitiveBundle`.

These are **parallel systems** that don't share data structures. For MCP integration, the canonical pipeline is the right target — but it lacks a headless file renderer.

### What exists vs what needs building

| Component | Status | Notes |
|---|---|---|
| Engine output parsers (canonical) | Complete | All 15 engines have scf_digest; 7 have full coverage |
| AnalysisObject types | Complete | convergence, dos, bands, trajectory, field3d |
| CanonicalPrimitiveBundle | Complete | Serializable, with render hints |
| Transform layer | Complete | 8 transforms (FermiShift, EnergyCrop, MSD, RDF, etc.) |
| CAS persistence | Complete | Content-addressed JSON storage + SQLite linkage |
| Service API | Complete | get_analysis, get_analysis_snapshot, get_instances_for_step |
| Legacy matplotlib renderer | Complete | QE-specific, PNG/SVG/PDF |
| Canonical bundle renderer | **MISSING** | Need bundle -> matplotlib adapter for headless PNG/SVG |
| MCP tool for analysis | **MISSING** | Need `get_results_summary` to call canonical pipeline |

---

## 8. Source File Index

### Core Analysis Framework
| File | Description |
|---|---|
| `src/quantumvitas/core/analysis/__init__.py` | Public API exports |
| `src/quantumvitas/core/analysis/base.py` | AnalysisObjectMeta, SourceFileStat |
| `src/quantumvitas/core/analysis/capability.py` | AnalysisCapability, CapabilityMatch, AnalysisResult, ResultState |
| `src/quantumvitas/core/analysis/evidence.py` | EvidenceBundle passed to parsers |
| `src/quantumvitas/core/analysis/orchestrator.py` | run_post_run_analysis() kernel orchestrator |
| `src/quantumvitas/core/analysis/cas_writer.py` | CAS + SQLite persistence |
| `src/quantumvitas/core/analysis/primitives.py` | Series1D, GeometryFrame, GeometryFrames, Marker |
| `src/quantumvitas/core/analysis/bundles.py` | CanonicalPrimitiveBundle, DerivedPrimitiveBundle, RenderMeta |

### Analysis Object Models
| File | Description |
|---|---|
| `src/quantumvitas/core/analysis/convergence/model.py` | Convergence dataclass + to_primitives() |
| `src/quantumvitas/core/analysis/dos/model.py` | DOS dataclass + to_primitives() |
| `src/quantumvitas/core/analysis/band_structure/model.py` | BandStructure + HighSymPoint + to_primitives() |
| `src/quantumvitas/core/analysis/trajectory/model.py` | Trajectory, Frame + to_primitives() |
| `src/quantumvitas/core/analysis/field3d.py` | Field3D + primitive-by-reference |

### Transforms
| File | Description |
|---|---|
| `src/quantumvitas/core/analysis/transforms/base.py` | PrimitiveTransform ABC |
| `src/quantumvitas/core/analysis/transforms/fermi_shift.py` | Shift energies by Fermi level |
| `src/quantumvitas/core/analysis/transforms/energy_crop.py` | Window to energy range |
| `src/quantumvitas/core/analysis/transforms/smoothing.py` | Running average |
| `src/quantumvitas/core/analysis/transforms/frame_slice.py` | Subset trajectory frames |
| `src/quantumvitas/core/analysis/transforms/msd.py` | Mean square displacement |
| `src/quantumvitas/core/analysis/transforms/rdf.py` | Radial distribution function |
| `src/quantumvitas/core/analysis/transforms/vacf.py` | Velocity autocorrelation |
| `src/quantumvitas/core/analysis/transforms/diffusion.py` | Diffusion coefficient |

### Parser Registry
| File | Description |
|---|---|
| `src/quantumvitas/parsers/registry.py` | Global parser registry (engine, type) -> class |
| `src/quantumvitas/parsers/__init__.py` | Re-exports ParserRegistry |

### Per-Engine Parsers (representative)
| File | Description |
|---|---|
| `src/quantumvitas/drivers/qe/parsers/output.py` | QE scf_digest parser |
| `src/quantumvitas/drivers/qe/parsers/convergence.py` | QE convergence parser |
| `src/quantumvitas/drivers/qe/parsers/dos.py` | QE DOS parser |
| `src/quantumvitas/drivers/qe/parsers/bands.py` | QE band structure parser |
| `src/quantumvitas/drivers/vasp/parsers/output.py` | VASP scf_digest (vasprun.xml + OUTCAR) |
| `src/quantumvitas/drivers/vasp/parsers/bands.py` | VASP band structure parser |
| `src/quantumvitas/drivers/vasp/parsers/dos.py` | VASP DOS parser (DOSCAR) |

### Visualization
| File | Description |
|---|---|
| `src/quantumvitas/analysis/plotting.py` | Legacy matplotlib plots (DOS, bands, SCF conv) |
| `src/quantumvitas/analysis/parsers.py` | Legacy QE parsers (SCFResult, DOSData, BandStructureData) |
| `src/quantumvitas/analysis/structure_viz.py` | 3D structure visualization (ball-and-stick) |
| `src/quantumvitas/analysis/calculation_analysis.py` | Legacy results/ directory writer |
| `src/quantumvitas/viz/data_models.py` | High-level viz data models |

### Service Layer
| File | Description |
|---|---|
| `src/quantumvitas/api/service.py` | QVService.analysis.* methods (lines 1062-1300+) |
| `src/quantumvitas/provenance/schema.py` | analysis_snapshots SQLite table definition |

### Driver Declarations (ANALYSIS_CAPABILITIES)
| File | Description |
|---|---|
| `src/quantumvitas/drivers/qe/driver.py` | QE: 9 capabilities (most complete) |
| `src/quantumvitas/drivers/vasp/driver.py` | VASP: 8 capabilities |
| `src/quantumvitas/drivers/abinit/driver.py` | ABINIT: 7 capabilities |
| `src/quantumvitas/drivers/cp2k/driver.py` | CP2K: 7 capabilities |
| `src/quantumvitas/drivers/siesta/driver.py` | Siesta: 7 capabilities |
| `src/quantumvitas/drivers/gpaw/driver.py` | GPAW: 7 capabilities |
| `src/quantumvitas/drivers/orca/driver.py` | ORCA: 4 capabilities |
| `src/quantumvitas/drivers/gaussian/driver.py` | Gaussian: 8 capabilities |
| `src/quantumvitas/drivers/lammps/driver.py` | LAMMPS: 2 capabilities |
| `src/quantumvitas/drivers/xtb/driver.py` | xTB: 2 capabilities |
| `src/quantumvitas/drivers/w90/driver.py` | Wannier90: 1 capability |
| `src/quantumvitas/drivers/qmcpack/driver.py` | QMCPACK: 2 capabilities |
| `src/quantumvitas/drivers/pyscf/driver.py` | PySCF: 4 capabilities |
| `src/quantumvitas/drivers/psi4/driver.py` | Psi4: 4 capabilities |
| `src/quantumvitas/drivers/yambo/driver.py` | Yambo: 0 capabilities |
