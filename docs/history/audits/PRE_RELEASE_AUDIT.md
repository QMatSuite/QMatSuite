# QMatSuite Pre-Release Deep Audit

**Date**: 2026-02-11
**Branch**: `v2-python`
**Test Results**: 1 failed, 5093 passed, 19 skipped (69% code coverage)
**Auditor**: Claude Code (automated deep audit)

---

## Section 1: Architecture Layer Health

### 1.1 Kernel Layer

#### Engine Drivers (15 engines)

All 15 engines have **complete driver.py implementations** with the 7-item MUST interface (`engine_family`, `display_name`, `driver_api_version`, `get_step_type_specs`, `get_handler`, `get_recipe_class`, `get_materialization_map`).

| Engine | Driver Path | Input Gen | Output Parse | Metadata JSON | Field3D | Status |
|--------|------------|-----------|-------------|---------------|---------|--------|
| QE | `drivers/qe/driver.py` | ✅ full IO module | ✅ `parsers/qe/` | ✅ `qe_metadata.py` | ✅ | ✅ Complete (most mature) |
| VASP | `drivers/vasp/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 232 tags | ✅ | ✅ Phase B1 complete |
| ORCA | `drivers/orca/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 120+ keywords | ✅ | ✅ Phase B1 complete |
| CP2K | `drivers/cp2k/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 215 tags | ✅ | ✅ Phase B1 complete |
| LAMMPS | `drivers/lammps/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 114 cmds | N/A | ✅ Phase B1 complete |
| ABINIT | `drivers/abinit/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 170+ tags | ✅ | ✅ Phase B1 complete |
| Gaussian | `drivers/gaussian/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 130 keywords | ✅ | ✅ Phase B1 complete |
| Siesta | `drivers/siesta/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ⚠️ minimal | ✅ | ✅ Phase B1 complete |
| W90 | `drivers/w90/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ `w90_tags.json` | ✅ | ✅ Complete |
| GPAW | `drivers/gpaw/driver.py` | ✅ `inputspec.py` | ⚠️ in handler | ⚠️ minimal | ✅ | ✅ Complete (Python-script) |
| Psi4 | `drivers/psi4/driver.py` | ✅ `inputspec.py` | ⚠️ in handler | N/A | ✅ | ✅ Complete (Python-script) |
| PySCF | `drivers/pyscf/driver.py` | ✅ `inputspec.py` | ⚠️ in handler | N/A | ✅ | ✅ Complete (Python-script) |
| xTB | `drivers/xtb/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ `xtb_tags.json` | N/A | ✅ Complete |
| QMCPACK | `drivers/qmcpack/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ 65 tags | N/A | ✅ Phase B1 complete |
| Yambo | `drivers/yambo/driver.py` | ✅ `inputspec.py` | ✅ `parsers/output.py` | ✅ `yambo_tags.json` | N/A | ✅ Phase B1 complete |

#### GEN Step Coverage

30+ registered GEN step types:

| GEN Step | Engines Supporting It |
|----------|----------------------|
| `scf` | QE, VASP, ORCA, CP2K, ABINIT, Siesta, GPAW, Psi4, PySCF, Gaussian |
| `relax` | QE, VASP, ORCA, CP2K, ABINIT, Siesta, GPAW, LAMMPS, xTB, Psi4, PySCF |
| `md` | QE, VASP, CP2K, ABINIT, Siesta, GPAW, LAMMPS, xTB |
| `nscf` | QE, VASP, ABINIT, GPAW |
| `bandspw` | QE, VASP, CP2K, ABINIT, Siesta, GPAW |
| `dos` | QE, VASP, CP2K, ABINIT, Siesta, GPAW |
| `bands` | QE, Siesta |
| `ph` | QE |
| `gipaw` | QE |
| `neb` | QE |
| `hf` | ORCA, Psi4, Gaussian |
| `mp2` | ORCA, Psi4, PySCF, Gaussian |
| `td` | ORCA, Psi4, PySCF, Gaussian |
| `freq` | Gaussian |
| `wannierprep` / `wannier` | W90 |
| `pw2wannier` | QE |
| `vmc` / `dmc` / `wfopt` | QMCPACK |
| `setup` / `gw` / `bse` / `optics` | Yambo |

**Gaps vs. competitor common workflows** (see Section 4 for per-engine analysis):
- ⚠️ No `freq` GEN step for ORCA (users run frequency calculations very commonly)
- ⚠️ No `scan` (PES scan) GEN step for Gaussian or ORCA
- ⚠️ No `transport` step for Siesta (TranSIESTA is a major use case)
- ⚠️ No `neb` for VASP (CI-NEB is widely used)

#### Preset / ParamSpace System

**Location**: `src/qmatsuite/presets/`

7 declared variants in `variants_registry.py`:
1. `OCCUPATIONS_SCHEME_PW` (scf, nscf, relax, md)
2. `MAGNETISM_PW` (scf, nscf, bandspw, relax, md)
3. `PRECISION_PW_DEFAULT` (scf, relax, md)
4. `PRECISION_PW_NSCF` (nscf)
5. `PRECISION_PW_BANDSPW` (bandspw)
6. `CONVERGENCE_PW` (scf, nscf, relax, bandspw, md)
7. `QC_PRECISION_SCF` (scf for QC engines)

⚠️ **IR Integration Gap**: Only QE has full IR dialect/backend (`ir/backends/qe/`, `ir/dialects/pw/`). VASP, ORCA, CP2K etc. lack IR support, limiting preset application to non-QE engines.

#### Structure Handling

**Location**: `src/qmatsuite/io/structure_io.py`

Supported import formats (via pymatgen + ASE): CIF, POSCAR/CONTCAR, XYZ, PDB, MOL/MOL2, JSON, QE input files (.in, .pwi), XSF

**Structure builder**: ❌ No in-kernel structure builder. Relies entirely on pymatgen/ASE for structure manipulation. No supercell builder, surface/slab generator, defect generator, or atom placement tools in the GUI.

#### Pseudopotential Management

- ✅ QE: `resources/pseudo/` with 21 redistributable UPF files (SSSP). Download via `download_sssp_library()` RPC.
- ✅ VASP: `vasp_potcar.py` stages POTCARs from `~/.qmatsuite/engines/vasp/`
- ✅ LAMMPS: `lammps_potential.py` stages potentials from `resources/lammps/potentials/`
- ⚠️ Scattered across drivers, no centralized pseudo registry

#### Execution

**Location**: `src/qmatsuite/execution/`

- ✅ Local subprocess execution for all 12 binary engines (QE, VASP, ORCA, CP2K, LAMMPS, ABINIT, Siesta, W90, xTB, QMCPACK, Yambo, Gaussian)
- ✅ In-process Python execution for GPAW, Psi4, PySCF
- ✅ Incremental skip via manifest fingerprinting
- ✅ Scan expansion for parameter sweeps
- ✅ Preflight checking (`preflight.py`)
- ❌ No PBS/SLURM/HPC scheduler integration — localhost only
- ❌ No remote execution capability

---

### 1.2 Daemon Layer

**File**: `src/qmatsuite/daemon/server.py` (6,469 lines)

- ✅ **Fully functional** JSON-RPC 2.0 server over stdio
- ✅ **117 RPC handlers** covering: system, project, structure, calculation, step, execution, analysis, pseudos, presets, workflows, library management, history, demos
- ✅ **Job queue**: `ThreadPoolExecutor(max_workers=1)` — sequential execution by design (license serialization)
- ✅ **State management**: Per-project `ProjectCache` with lazy initialization and mutation-triggered invalidation
- ✅ **Graceful shutdown**: Handles SIGTERM, rejects pending requests on exit
- ⚠️ Single-threaded job execution means no parallel jobs (intentional for v1)

---

### 1.3 API Layer (QMSService)

**File**: `src/qmatsuite/api/service.py` (7,661 lines)

- ✅ **93 methods across 7 domain classes** — all fully implemented, zero stubs
- ✅ Domains: Structure (6), Calculation (14), Run (6), Project (7), Engine (3), History (4), + Analysis
- ✅ Error handling: `errors.py` with `APIError` hierarchy → `NotFoundError`, `ValidationError`, `ConflictError`, `EngineError`, `ConfigError`, `FilesystemError`, `InternalError`
- ✅ All kernel exceptions mapped via `_mapping/exc_mapping.py`
- ✅ DTO boundary: all data crossing API uses DTOs or primitives

---

### 1.4 CLI Layer

**File**: `src/qmatsuite/cli/main.py` (5,252 lines)

**31+ commands** organized into sub-apps:

| Command Group | Commands | Status |
|--------------|----------|--------|
| `qms init` | `project`, `calculation`, `step` | ✅ |
| `qms import-structure` | file import (CIF, POSCAR, XYZ, etc.) | ✅ |
| `qms list` | hierarchical listing | ✅ |
| `qms run` | `calculation`, `step` | ✅ |
| `qms rename` | `structure`, `calculation`, `step`, `project` | ✅ |
| `qms delete` | `structure`, `calculation`, `step`, `project`, `trash` | ✅ |
| `qms configure` | `step`, `calculation`, `project`, `species`, `structure` | ✅ |
| `qms analyze` | `band`, `dos`, `energy`, `scf`, `structure` | ✅ |
| `qms detect-qe` | QE binary detection | ✅ |
| `qms params` | QE parameter documentation | ✅ |

✅ **Full e2e CLI workflow** works: `qms init project` → `qms import-structure` → `qms init calculation` → `qms configure step` → `qms run calculation` → `qms analyze`

⚠️ CLI is QE-centric in documentation and examples. Multi-engine CLI workflows are supported but less documented.
⚠️ No `qms history` command — provenance accessible only via daemon/API.

---

### 1.5 GUI Layer (Electron + React)

**Architecture**: Electron 39 + React 18 + Vite 7 + TypeScript 5

#### Implemented & Functional Views

| View/Panel | Status | Library | Notes |
|-----------|--------|---------|-------|
| **3D Structure Viewer** | ✅ Working | react-three-fiber + Three.js | Ball-and-stick, bonds, unit cell, orbit controls, hover labels |
| **Project Summary / Welcome** | ✅ Working | React | Create/open/recent projects, close project |
| **Demo Gallery** | ✅ Working | React | Lists demos, one-click project creation |
| **Structure List / Detail** | ✅ Working | React | List, select, metadata display, formula, lattice params |
| **Calculation List / Overview** | ✅ Working | React | Step list, step detail, YAML viewer |
| **Calculation Run Tab** | ✅ Working | React | Submit job, monitor progress, step stepper |
| **Jobs Panel** | ✅ Working | React | Status badges, polling (3s), step progress, log viewing |
| **Band Structure Plot** | ✅ Working | Recharts | k-path with high-symmetry labels, spin channels |
| **DOS Plot** | ✅ Working | Recharts | PDOS filtering, element controls |
| **Convergence Plot** | ✅ Working | Recharts | SCF energy vs iteration |
| **Trajectory Animation** | ✅ Working | Recharts + Three.js | Frame playback, observable series |
| **Fatbands Visualization** | ✅ Working | Recharts | Atom/orbital projections, width scaling |
| **Field3D Isosurface** | ✅ Working | Three.js + marching cubes | Isovalue slider, opacity, atom/cell overlay |
| **Parameter Editor** | ✅ Working | React | Type-aware inputs, scan mode toggle, add from palette |
| **Preset Section** | ✅ Working | React | Per-dimension dropdowns, broadcast apply, toast feedback |
| **Engine Parameter Browser** | ✅ Working | React | Browse tags by engine with descriptions |
| **Online Structure Import** | ✅ Working | React | OPTIMADE search + import |
| **Settings Panel** | ✅ Working | React | Theme (dark/light), auto-analysis, default dirs |
| **History Panel** | ⚠️ Partial | React | Timeline exists but feature scope unclear |
| **Debug Panel** | ✅ Working | React | RPC call tester, request history |
| **Status Bar** | ✅ Working | React | Connection status, job counts |

#### Provenance Display in GUI
✅ `HistoryPanel.tsx` exists at `gui/src/components/panels/HistoryPanel.tsx`. It shows project timeline from the provenance DB. However, the UI surface for provenance is minimal compared to the backend capability.

#### E2E Tests
8 Playwright test files at `gui/tests/e2e/`:
- `welcome.spec.ts` — Welcome screen
- `demo_gallery.spec.ts` — Demo discovery and project creation
- `demo_calculation.spec.ts` — Calculation structure validation
- `demo_calculation_run.spec.ts` — Run and monitor
- `analysis_convergence.spec.ts` — Convergence visualization
- `analysis_dos.spec.ts` — DOS visualization
- `step_defaults.spec.ts` — Parameter defaults
- `structures_view.test.ts` — Structure list and import

---

### 1.6 Provenance System

**Location**: `src/qmatsuite/provenance/` (14 modules, ~2,400 lines)

- ✅ **SQLite database** at `.provenance/provenance.db` with tables: `operations`, `runs`, `run_steps`, `pins`
- ✅ **Content-Addressed Store (CAS)** at `.provenance/.cas/objects/` — SHA256-based snapshot storage
- ✅ **Operation tracking**: Step edits, preset applies, calc creates, restores
- ✅ **Run history**: Per-step timing, energy, SCF cycles, status
- ✅ **Pin system**: Pin analysis results to run history
- ✅ **World independence**: Deleting `.provenance/` leaves project fully runnable (Law P1)
- ✅ **Graceful degradation**: Provenance failures never fail YAML writes (Law P7)
- ✅ **API surface**: `query_operations()`, `query_runs()`, `get_run_details()`, `pin_analysis_to_history()`, etc.
- ✅ **Daemon surfaced**: `get_project_history()`, `get_run_revision()`, `pin_analysis_to_history()` RPCs
- ⚠️ No CLI commands for history query (`qms history` not implemented)

---

### 1.7 Jupyter Integration

- ✅ `import qmatsuite` works after `pip install -e .`
- ✅ API layer (`qmatsuite.api.QMSService`) is importable from notebooks
- ❌ No dedicated Jupyter kernel
- ❌ No example notebooks
- ❌ No `ipywidgets` or interactive visualization widgets
- ⚠️ The API layer is rich enough that programmatic use from notebooks is possible today, but it's not documented or showcased.

---

## Section 2: End-to-End Workflow Verification

### 2.1 "First 5 Minutes" Experience

**Path**: Open GUI → See welcome → Click "Demo Gallery" → Select "Silicon Band Structure" → Create project → Run → See bands

**Status**: ⚠️ **Mostly works but has friction points**

1. ✅ GUI opens, welcome screen shows with "Demo Gallery" button
2. ✅ Demo gallery loads 21 demo project snapshots from `resources/demo_projects/`
3. ✅ User selects demo → file picker opens → selects directory → project created from snapshot
4. ⚠️ **Running** requires QE to be installed. No bundled QE binary. No auto-download.
5. ⚠️ If QE is not found, user sees an error but no guidance on how to install QE.
6. ✅ If QE is available, calculation runs and convergence/band plots display.

**Critical gap**: No bundled engine binary or guided installation for the "first 5 minutes" experience. A PhD student trying QMatSuite for the first time will hit a wall if QE isn't already installed.

### 2.2 Structure Import Workflow

User has CIF → imports → views 3D → creates calculation.

✅ **Works end-to-end.** Both CLI (`qms import-structure Si.cif`) and GUI (Import Structure dialog with file picker). 3D viewer renders ball-and-stick with bonds and unit cell. Structure formats supported: CIF, POSCAR, XYZ, PDB, MOL/MOL2, JSON, QE .in files.

### 2.3 Online Structure Fetch

✅ **Working via OPTIMADE.** `OnlineImportPanel.tsx` in GUI supports formula search across OPTIMADE providers. Daemon handler `structure_search_online()` queries OPTIMADE databases. Import to project works.

⚠️ Only OPTIMADE is implemented as an online source. No Materials Project API, COD direct, AFLOW, or PubChem integration.
⚠️ OPTIMADE reliability varies by provider.

### 2.4 Custom Calculation Workflow

Create project → import structure → select engine → select workflow → adjust params → run → monitor → view results → modify → re-run → compare.

✅ **Works for QE.** Full parameter editing, preset application, run monitoring, and analysis visualization.
⚠️ **Other engines**: Calculation creation works for all 15 engines. Parameter editing works. Running works if engine binary is available. Analysis visualization depends on engine parser completeness.
❌ **No result comparison**: No side-by-side comparison view between two runs.

### 2.5 Multi-Step Workflow

SCF → Bands → DOS as multi-step → run sequentially → view combined results.

✅ **Works for QE.** Demo `07_Si_bandStructure.yml` demonstrates SCF→NSCF→Bands→BandsPostProc pipeline. Sequential execution with incremental skip. Analysis tab shows results per step.
✅ **Works for Wannier90.** Multi-step pipeline: QE SCF → pw2wannier → W90 wannierprep → W90 wannier.
⚠️ Analysis views are per-step, not combined. No unified "calculation summary" view aggregating results from all steps.

### 2.6 Engine Discovery & Setup

✅ **QE detection works**: `qms detect-qe` scans QE_HOME, PATH, shell configs, home directory. Works in CLI and daemon.
❌ **No engine download**: No built-in download/install for any engine. No portable Windows QE bundled.
❌ **No guided setup**: GUI has no "Engine Setup Wizard" guiding users to install engines.
⚠️ `LibrariesPanel.tsx` exists but library management RPCs may not be fully wired.

### 2.7 Pseudopotential Management

✅ **QE SSSP download works**: `download_sssp_library()` RPC downloads SSSP library.
✅ **Pseudo assignment UI**: CommonCardPseudo component in GUI for selecting pseudos.
✅ **CLI**: `qms configure project --pseudo Si:Si.pbe-n-kjpaw_psl.1.0.0.UPF`
⚠️ Pseudo management is QE-centric. VASP POTCARs require manual setup. No GUI for managing VASP/LAMMPS/ABINIT pseudos/potentials.

### 2.8 Cross-Engine Comparison

❌ **Not a supported workflow.** The GEN abstraction enables same-structure different-engine calculations, but there's no comparison view, no cross-engine result normalization, and no documentation showing how to do this.

---

## Section 3: Structure Handling Gap Analysis

### 3.1 Current State

| Capability | Status |
|-----------|--------|
| **Local file import** | ✅ CIF, POSCAR, XYZ, PDB, MOL/MOL2, JSON, QE .in |
| **Online import** | ✅ OPTIMADE only |
| **3D viewer** | ✅ Ball-and-stick, bonds, unit cell, labels, orbit controls |
| **Structure from scratch** | ❌ No builder |
| **Supercell generation** | ❌ Not in GUI (pymatgen can do it programmatically) |
| **Surface/slab creation** | ❌ |
| **Defect generation** | ❌ |
| **Structure transformation** | ❌ No rotate/translate/mirror in GUI |

### 3.2 Competitor Comparison

| Feature | ASE | VESTA | Materials Studio | pymatgen | QMatSuite |
|---------|-----|-------|-----------------|----------|-----------|
| Structure builder | ✅ bulk, surface, nanotube | ✅ crystal editor | ✅ full builder | ✅ programmatic | ❌ |
| Surface/slab | ✅ `build.surface` | ✅ GUI | ✅ GUI + wizard | ✅ `SlabGenerator` | ❌ |
| Supercell | ✅ `Atoms * (2,2,2)` | ✅ GUI | ✅ GUI | ✅ `make_supercell` | ❌ |
| Defect generation | ❌ | ❌ | ✅ | ✅ `pymatgen-analysis-defects` | ❌ |
| Nanoparticle | ✅ `cluster` module | ❌ | ✅ | ❌ | ❌ |
| Format support | 100+ formats | 30+ in, 13 out | Extensive | Extensive | 8 formats |

### 3.3 Gap Assessment

**Must-have for v1:**
- None strictly blocking — file import covers the basic use case.

**Nice-to-have for v1:**
- Supercell generation from GUI (pymatgen backend exists)
- More online sources (Materials Project API is widely used)

**Future roadmap:**
- Surface/slab builder
- Defect generation
- Structure transformation tools
- PubChem molecule import for QC engines

### 3.4 Online Structure Sources

| Database | Python Client | Integration Difficulty | Data Quality | Priority |
|----------|--------------|----------------------|-------------|----------|
| **OPTIMADE** | `optimade` on PyPI | ✅ Already done | Variable by provider | Done |
| **Materials Project** | `mp-api` on PyPI | Medium (API key required) | High (curated) | P1 |
| **COD** | REST API + OPTIMADE | Easy (open, CIF download) | High (experimental) | P2 |
| **PubChem** | PUG-REST (no client needed) | Easy (REST, molecular focus) | High (119M compounds) | P2 for QC |
| **AFLOW** | REST API | Medium | High (1.6M entries) | P3 |
| **NOMAD** | REST API | Medium | High (19M entries) | P3 |
| **ICSD** | Subscription API | Hard (requires license) | Gold standard | P3 |

---

## Section 4: Engine-Specific Coverage Audit

### Tier 1 — Must Be Solid for v1

#### Engine: Quantum ESPRESSO (QE)
```
Driver status:        ✅ Complete (most mature)
Supported GEN steps:  scf, nscf, relax, md, bandspw, dos, bands, ph, gipaw, neb, custom, pw2wannier
Missing workflows:    None critical — covers all top-5 QE use cases
Input generation:     ✅ Full (parser.py, generator.py, model.py, structure_io.py)
Output parsing:       ✅ Full (scf, bands, DOS, phonon, NEB)
Presets available:    ✅ Full (7 variants, precision/magnetism/convergence/occupations)
Demo projects:        11 (00_Si_scf, 03_Si_vc_relax, 04_Si_DOS, 06_Al_DOS, 07_Si_bandStructure,
                      08_Fe_DOS, 09_Si_phonon, 12_NMR_gipaw, 13_graphene, 15_bulk_modulus_Si,
                      19_Si_CPMD) + 2 standalone (si_bands_demo, si_dos_demo)
E2E tested:           ✅ Full (CLI + daemon + GUI e2e)
Known issues:         None critical
Priority for v1:      CRITICAL
```

#### Engine: VASP
```
Driver status:        ✅ Phase B1 complete (second-most mature)
Supported GEN steps:  scf, nscf, relax, md, bandspw, dos
Missing workflows:    ⚠️ No NEB (CI-NEB widely used), no hybrid functional step
Input generation:     ✅ INCAR/POSCAR/KPOINTS generation
Output parsing:       ✅ vasprun.xml (primary) + OUTCAR regex (fallback), PROCAR fatbands, DOSCAR PDOS
Presets available:    ⚠️ No VASP-specific presets (QE presets only)
Demo projects:        1 (si_bands_vasp_demo.yml)
E2E tested:           ⚠️ Partial (requires VASP binary, proprietary)
Known issues:         Asset policy: proprietary (POTCARs not redistributable)
Priority for v1:      CRITICAL
```

### Tier 2 — Should Work for v1

#### Engine: ORCA
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  scf, hf, relax, td, mp2
Missing workflows:    ⚠️ No freq (frequency analysis is #3 most common ORCA use case)
                      ⚠️ No scan (PES scan)
                      ⚠️ No ts (transition state search)
Input generation:     ✅ Keyword-block syntax, enhanced parser
Output parsing:       ✅ ORCADigest (energy, SCF cycles, geometry opt)
Presets available:    ⚠️ QC_PRECISION_SCF only
Demo projects:        3 (water_orca_scf, methane_orca_freq, formaldehyde_orca_tddft)
E2E tested:           ⚠️ Requires ORCA binary
Known issues:         None critical
Priority for v1:      IMPORTANT
```

#### Engine: CP2K
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  scf, relax, md, bandspw, dos
Missing workflows:    ⚠️ No cell optimization (cell_opt) as separate GEN step
Input generation:     ✅ Nested-section parser/writer
Output parsing:       ✅ CP2KDigest (17 fields)
Presets available:    ⚠️ No CP2K-specific presets
Demo projects:        0 (no CP2K demo in resources/demo_projects/)
E2E tested:           ⚠️ Requires CP2K binary
Known issues:         Recipe circular import (systemic, xfail)
Priority for v1:      IMPORTANT
```

#### Engine: LAMMPS
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  relax, md, minimize
Missing workflows:    None critical for classical MD
Input generation:     ✅ Command-stream + data file parser/writer
Output parsing:       ✅ LAMMPSDigest (16 fields)
Presets available:    ⚠️ No LAMMPS presets
Demo projects:        0 (no LAMMPS demo in resources/demo_projects/)
E2E tested:           ⚠️ Requires LAMMPS binary
Known issues:         None critical
Priority for v1:      IMPORTANT
```

### Tier 3 — Best-Effort for v1

#### Engine: ABINIT
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  scf, nscf, relax, md, bandspw, dos
Missing workflows:    ⚠️ No DFPT/phonon (top-5 use case for ABINIT)
Demo projects:        0
Priority for v1:      Nice-to-have
```

#### Engine: Gaussian
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  scf, hf, relax, td, mp2, freq
Missing workflows:    ⚠️ No scan, no NMR
Demo projects:        0
Priority for v1:      Nice-to-have
```

#### Engine: Siesta
```
Driver status:        ✅ Phase B1 complete
Supported GEN steps:  scf, relax, md, bandspw, dos, bands
Missing workflows:    ⚠️ No transport (TranSIESTA)
Demo projects:        0
Priority for v1:      Nice-to-have
```

#### Engine: Wannier90
```
Driver status:        ✅ Complete
Supported GEN steps:  wannierprep, wannier
Demo projects:        3 (copper, diamond, silicon)
Priority for v1:      Nice-to-have (postprocessing)
```

#### Engines: GPAW, Psi4, PySCF, xTB, QMCPACK, Yambo
```
Driver status:        ✅ All complete
Demo projects:        1 (water_pyscf_scf.yml)
Priority for v1:      Best-effort
```

---

## Section 5: Test Coverage Audit

### 5.1 Current Test Inventory

**Total**: 5,093 passed, 1 failed, 19 skipped (252.78s runtime)
**Code Coverage**: 69% overall

| Directory | Files | What It Covers |
|-----------|-------|---------------|
| `tests/gates/` | 59 | Constitutional invariant enforcement |
| `tests/unit/` | 144 | Models, presets, analysis, structure, pseudo, paramspace |
| `tests/drivers/` | 73 | Per-engine input/output/metadata (13 engines) |
| `tests/integration/` | 49 | Real engine execution (requires binaries) |
| `tests/inputformat/` | 21 | Parser/writer orchestration for all engines |
| `tests/api/` | 24 | QMSService API methods |
| `tests/daemon/` | 15 | JSON-RPC handlers, job management |
| `tests/cli/` | 10 | CLI commands |
| `tests/contract_crawler/` | 12 | Contract-based code analysis |
| `tests/core/` | 2 | Core kernel |
| `tests/ir/` | 2 | IR dialect |
| `tests/workflow/` | 3 | Workflow/DAG |
| `tests/provenance/` | 2 | Provenance system |
| `tests/presets/` | 2 | Preset system |
| `gui/tests/e2e/` | 8 | Electron + Playwright E2E |

**The 1 failure**: `tests/inputformat/test_xtb_parse.py::TestXTBNormalizedCorpus::test_parse_available_normalized_xyz_cases` — recursive `_parse_tmp/` directory creation (infinite loop bug creating nested temp dirs until path length exceeds OS limit).

### 5.2 Critical Test Gaps

**Must-add before release:**
- [ ] **Demo lifecycle test** — Load every demo → materialize → verify files exist → verify YAML valid. Currently no automated test that all 21 demos load successfully. ~4h
- [ ] **Fix xTB recursive parse_tmp bug** — The single test failure. Likely a bug in xTB inputspec.py where `_parse_tmp` is created recursively. ~1h
- [ ] **Multi-engine run smoke test** — At least verify `preflight_check()` passes for all engines with demo projects. ~2h

**Should-add before release:**
- [ ] **GUI e2e for non-QE engine** — Currently all e2e tests use QE demos. Add at least one ORCA or PySCF demo test. ~2h
- [ ] **Provenance roundtrip test** — Verify that after running a calculation, `get_project_history()` returns the expected timeline. ~2h
- [ ] **Online import test** — OPTIMADE search + import end-to-end (currently untested or mocked). ~2h

**Can defer:**
- [ ] Cross-engine comparison test (feature doesn't exist yet)
- [ ] HPC scheduler integration tests (feature doesn't exist yet)
- [ ] Performance/stress tests for large structures

---

## Section 6: Prioritized Action Items for 1-Week Closeout

### P0 — Release Blockers

| # | Task | Layer | Hours | Why |
|---|------|-------|-------|-----|
| 1 | **Fix xTB recursive _parse_tmp bug** | kernel | 1 | Only test failure. Infinite loop creating nested temp directories. |
| 2 | **Add engine setup guidance in GUI** | gui | 4 | When no engine is found, show clear instructions: "Install QE via..." with links. Without this, first-time users hit a wall. |
| 3 | **Verify all 21 demos load & materialize** | test | 4 | Create a parametrized test that loads each demo .yml, materializes it, and verifies YAML + structure files exist. Currently no automated demo integrity test. |
| 4 | **Update README.md for v2** | docs | 3 | README still references Java v1 as primary, JRE requirements, and outdated badges. Needs complete rewrite for Python v2 + Electron GUI. |

### P1 — High Impact (First Impression)

| # | Task | Layer | Hours | Why |
|---|------|-------|-------|-----|
| 5 | **Add "quick start" guide** | docs | 4 | Step-by-step guide: install → open → run demo → see results. Critical for adoption. |
| 6 | **Add non-QE demo projects** | kernel | 4 | CP2K, LAMMPS, and Gaussian demos to show multi-engine breadth. Currently 11/21 demos are QE. |
| 7 | **Add ORCA `freq` GEN step** | kernel | 3 | Frequency analysis is the #3 most common ORCA use case. Missing GEN step means users can't do it. |
| 8 | **Improve error messages for missing engine** | daemon | 2 | When `run_calculation` fails because engine binary isn't found, provide actionable message: which binary, where to install. |
| 9 | **Add demo pre-computed results display** | gui | 3 | When user views a demo but hasn't run it yet, show the pre-computed `.scf.json`/`.bands.json` as preview. The data files already exist. |
| 10 | **Clean up repo root** | repo | 2 | 40+ report/audit/progress `.md` files in repo root. Move to `docs/worklogs/` or `.tmp/`. |

### P2 — Medium Impact

| # | Task | Layer | Hours | Why |
|---|------|-------|-------|-----|
| 11 | **Add Materials Project API integration** | kernel | 6 | `mp-api` Python client exists. Second most requested structure source after OPTIMADE. |
| 12 | **Add `qms history` CLI command** | cli | 3 | Provenance system is fully functional but CLI has no way to access it. |
| 13 | **Add VASP-specific presets** | kernel | 4 | VASP has no presets despite being Tier 1. Need at least precision presets (ENCUT, EDIFF). |
| 14 | **Supercell builder in GUI** | gui | 4 | pymatgen `make_supercell` exists. Wire it to a simple 3x3 matrix input in GUI. |
| 15 | **Add Jupyter example notebook** | docs | 3 | Show `from qmatsuite.api import QMSService` + programmatic workflow. Low effort, high credibility. |
| 16 | **Calculation result comparison view** | gui | 6 | Side-by-side energy/bands/DOS from two runs of same calculation. Killer feature for parameter studies. |

### P3 — Low Impact / Defer

| # | Task | Layer | Hours | Why |
|---|------|-------|-------|-----|
| 17 | Add PubChem molecule import | kernel | 4 | For QC engine users (ORCA, Gaussian). Can defer to v1.1. |
| 18 | Add PBS/SLURM scheduler integration | execution | 20+ | HPC users need this but it's a major feature. v1.1 or v1.2. |
| 19 | Add IR dialects for VASP/ORCA/CP2K | kernel | 15+ | Would enable cross-engine presets. Major effort, defer. |
| 20 | Multi-engine comparison workflow | gui | 10 | No demand signal yet. Defer. |
| 21 | Structure builder (surfaces, defects) | gui | 20+ | pymatgen can do it programmatically. GUI builder is v2 scope. |

### Suggested Day-by-Day Schedule (1-Week Sprint)

**Day 1 (Mon)**: P0 items
- Fix xTB recursive bug (#1) — 1h
- Write demo integrity test (#3) — 4h
- Start README rewrite (#4) — 3h

**Day 2 (Tue)**: P0 + P1
- Finish README rewrite (#4) — 1h
- Add engine setup guidance in GUI (#2) — 4h
- Improve error messages for missing engine (#8) — 2h
- Start quick-start guide (#5) — 1h

**Day 3 (Wed)**: P1
- Finish quick-start guide (#5) — 3h
- Add ORCA `freq` GEN step (#7) — 3h
- Add demo pre-computed results display (#9) — 2h

**Day 4 (Thu)**: P1 + P2
- Add non-QE demo projects (#6) — 4h
- Clean up repo root (#10) — 2h
- Add `qms history` CLI command (#12) — 2h

**Day 5 (Fri)**: P2
- Add Materials Project API integration (#11) — 6h
- Add VASP-specific presets (#13) — 2h

**Day 6 (Sat, if needed)**: P2
- Supercell builder in GUI (#14) — 4h
- Jupyter example notebook (#15) — 3h

**Day 7 (Sun, if needed)**: Polish
- Final test run, fix any new failures
- Review all demo projects end-to-end manually
- Tag release candidate

---

## Section 7: "Wow Factor" Checklist

| # | Criterion | Status | Notes |
|---|----------|--------|-------|
| 1 | **One-click demo producing visible result** | ⚠️ | Demo gallery works, but requires engine installed. Pre-computed result preview (`.scf.json`, `.bands.json`) exists but isn't displayed before running. Fix: show preview data. |
| 2 | **Structure viewer with smooth 3D interaction** | ✅ | react-three-fiber + Three.js, orbit controls, hover labels, bonds, unit cell. Looks good. |
| 3 | **Real-time calculation progress indicator** | ✅ | JobsPanel with polling, step stepper, status badges, log tailing. |
| 4 | **Beautiful, modern-looking GUI** | ✅ | Dark/light theme, CSS variables, clean layout with resizable panes. Not "legacy scientific software." |
| 5 | **Clear error messages when things go wrong** | ⚠️ | API errors are structured, but user-facing messages often show raw error codes. Needs polish for "engine not found" and "pseudo not configured" cases. |
| 6 | **Provenance timeline showing what was computed** | ⚠️ | HistoryPanel exists and shows timeline, but it's minimal. Needs a richer "computation diary" feel — show energy values, convergence status inline. |
| 7 | **Preset system that "just works" for common materials** | ⚠️ | Works well for QE (7 presets). No presets for VASP, ORCA, CP2K — users must configure everything manually for these engines. |

**Biggest "wow" opportunity**: Show pre-computed band structure / DOS from demo projects BEFORE the user runs anything. The data is already in `.bands.json` / `.dos.json`. This would make the first 5 seconds impressive: open demo gallery → see a beautiful band structure plot immediately.

---

## Appendix: Competitor Research Summary

### Key Takeaways for QMatSuite Positioning

**vs. AiiDA**: AiiDA is a workflow engine with provenance — no GUI, no structure viewer, no parameter editor. QMatSuite offers a complete IDE experience. AiiDA has 100+ engine plugins; QMatSuite has 15 integrated drivers. Complementary, not competing.

**vs. atomate2**: atomate2 is a high-throughput workflow library for the Materials Project. No GUI. VASP-centric. QMatSuite is an IDE; atomate2 is infrastructure.

**vs. pyiron**: Jupyter-native IDE. Strongest on LAMMPS + SPHInX. QMatSuite offers a dedicated desktop GUI vs. pyiron's notebook approach. Different target audiences.

**vs. BURAI**: Direct predecessor/competitor as a QE GUI. BURAI bundles QE; QMatSuite does not (yet). BURAI is Java-only and appears unmaintained. QMatSuite is the modern successor.

**vs. Materials Studio**: Commercial ($$$) all-in-one suite. QMatSuite is open-source. Materials Studio has a mature structure builder and dozens of solvers. QMatSuite has broader engine coverage but less polished structure editing.

**QMatSuite's unique value proposition**: The only open-source tool that integrates 15 engines with a modern GUI, preset system, provenance tracking, and both CLI + GUI + API access. No competitor offers this combination.

### Structure Database Coverage (2025-2026)

| Database | Entries | API | QMatSuite Status |
|----------|---------|-----|-----------------|
| OPTIMADE (aggregated) | 26.9M structures, 27 providers | REST (standard) | ✅ Integrated |
| Materials Project | 130K+ compounds | `mp-api` Python | ❌ Not integrated |
| COD | 530K structures | REST + OPTIMADE | ⚠️ Via OPTIMADE only |
| AFLOW | 1.6M entries | REST + OPTIMADE | ⚠️ Via OPTIMADE only |
| NOMAD | 19M entries | REST + OPTIMADE | ⚠️ Via OPTIMADE only |
| ICSD | 318K entries | Subscription API | ❌ Not integrated |
| PubChem | 119M compounds | PUG-REST | ❌ Not integrated |

---

*End of audit.*
