# Analysis Pipeline Comprehensive Review

**Date:** 2026-02-10
**Status:** Review document (not binding spec)
**Baseline:** 5104 tests collected, 5085 passed, 19 skipped
**Purpose:** Assess spec compliance, engine coverage, and GUI readiness for closing out the backend analysis pipeline and beginning frontend visualization construction.

---

## Table of Contents

1. [Spec Compliance Analysis](#1-spec-compliance-analysis)
2. [Quality Matrix: Playbook Adherence](#2-quality-matrix-playbook-adherence)
3. [Engine x Analysis Capability Matrix](#3-engine-x-analysis-capability-matrix)
4. [Missing Analysis Pipelines](#4-missing-analysis-pipelines)
5. [GUI Readiness Assessment](#5-gui-readiness-assessment)
6. [End-to-End Walkthrough: From Calculation to Plot](#6-end-to-end-walkthrough)
7. [Recommendations and Priority](#7-recommendations-and-priority)

---

## 1. Spec Compliance Analysis

Reference: `docs/architecture/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` (Binding v1.4, 14 invariants)

### 1.1 Invariant Compliance Matrix

| Inv | Title | Status | Evidence | Notes |
|-----|-------|--------|----------|-------|
| **A1** | Raw Artifacts Are Evidence, Not SSOT | PASS | All providers read from `calc/raw/` via EvidenceBundle | No provider reads `.tmp/` |
| **A2** | AnalysisObjects Universal & Engine-Agnostic | PASS | All 5 domain objects in `core/analysis/`, each has `meta: AnalysisObjectMeta` class annotation | Field3D promoted from VASP to core |
| **A3** | AnalysisObjectMeta Single Schema | PASS | All providers populate all 13 required fields | Gate test enforces |
| **A4** | Canonical Bundles Only From to_primitives() | PASS | All 5 domain objects have parameterless `to_primitives()` | Determinism verified by `test_sha_deterministic` per engine |
| **A5** | Derived Bundles Only From PrimitiveTransform | PASS | 8 transforms produce DerivedPrimitiveBundle | No other code path creates derived bundles |
| **A6** | Bundles = Data + RenderMeta + ProvenanceMeta | PASS | No view parameters in any bundle | Gate test scans for forbidden fields |
| **A7** | Transforms = Only Data Manipulation | PASS | All 8 transforms are pure math, no raw artifact reads | Gate test verifies no driver imports |
| **A8** | Viz Consumes Only PrimitiveBundles | PASS | GUI reads `bundle.series` + `bundle.render_meta` | No engine branching in viz code |
| **A9** | Lazy = Trigger Timing Only | PASS | No LazyArray, deferred, or proxy objects in domain models | Gate test scans AST |
| **A10** | Canonical-Only Memoization | PASS | `DerivedPrimitiveBundle` never cached | Gate test verifies no `@lru_cache` on transforms |
| **A11** | CAS Content-Addressed | PARTIAL | `compute_canonical_sha()` exists, SQLite links exist | CAS tier is 0.8 (design complete, partial implementation) |
| **A12** | Layering: Kernel vs API vs Frontend | PASS | Frontend imports zero Python modules | Gate test enforces |
| **A13** | No Engine Branching in Universal Layer | PASS | Orchestrator, transforms, renderers have zero `if engine ==` | Gate test scans source |
| **A14** | Evidence Corpus Isolation | PASS | No `.tmp/` references in runtime code | Gate test scans all tracked files |

**Overall: 13/14 PASS, 1 PARTIAL (Inv-A11 CAS at tier 0.8 by design)**

### 1.2 Gate Test Coverage

| Gate Test | Invariant(s) | Parametrized | Count |
|-----------|-------------|-------------|-------|
| `test_analysis_object_meta_required` | A2, A3 | Per domain object class | 5 |
| `test_to_primitives_parameterless` | A4 | Per domain object | 5 |
| `test_canonical_bundle_deterministic` | A4 | Per domain object | 5 |
| `test_derived_never_cached` | A5, A10 | Per transform | 8 |
| `test_no_view_params_in_bundles` | A6 | Per domain object | 5 |
| `test_transforms_no_driver_imports` | A7 | Per transform module | 8 |
| `test_no_engine_branching_in_orchestrator` | A13 | Source scan | 1 |
| `test_no_lazy_payloads` | A9 | Per domain object module | 5 |
| `test_bands_dos_parser_matrix` | Registry | 6 engines | 6 |
| `test_trajectory_parser_matrix` | Registry | 12 engines | 12 |
| `test_convergence_parser_matrix` | Registry | 5 engines | 5 |
| `test_field3d_parser_matrix` | Registry | 11 engines | 11 |
| `test_field3d_engine_has_analysis_capabilities` | Registry | 11 engines | 11 |
| `test_field3d_core_importable` | A2 | Import check | 1 |
| `test_field3d_cube_parser_importable` | Shared parser | Import check | 1 |
| `test_vasp_analysis_capabilities_cover_five_types` | VASP completeness | 1 engine | 1 |
| `test_field3d_bundle_excludes_full_grid` | Primitive-by-ref | Source scan | 1 |
| Various other invariant tests | A1-A14 | Various | ~18 |
| **Total gate analysis tests** | | | **109** |

### 1.3 Post-Run Pipeline Phase Compliance

| Phase | Spec Requirement | Status | Notes |
|-------|-----------------|--------|-------|
| **Phase 1**: Step Digests | Parser called, digest to SQLite | DONE | 13 engines have scf_digest parsers |
| **Phase 2**: Capability Matching + Canonical | Match caps → parse → to_primitives() → CAS | DONE | Orchestrator fully implemented |
| **Phase 3**: Default Thumbnails | Headless thumbnail per bundle | NOT DONE | No thumbnail renderer exists |
| **Phase 4**: Provenance Writes | Update run status in SQLite | DONE | Provenance layer operational |

**Gap: Phase 3 (thumbnails) is not implemented. The spec marks this as a future tier.**

---

## 2. Quality Matrix: Playbook Adherence

Reference: `docs/architecture/ANALYSIS_PIPELINE_PLAYBOOK.md`

### 2.1 Per-Engine Playbook Compliance

The Playbook defines a "Recipe A" pattern for extending analysis to new engines with 7 steps and acceptance criteria.

| Criterion | Description | Status |
|-----------|------------|--------|
| Real fixtures only | All test data from real engine runs | PASS — all 449 analysis tests use real fixtures |
| EvidenceBundle API | All providers use `parse(evidence: EvidenceBundle)` | PASS — no legacy `raw_dir` signatures remain |
| 7-test template | can_parse_true/false, parse_returns, shapes, physics, to_primitives, sha_deterministic | PASS — all providers follow template (8 tests for field3d) |
| No engine branching | Orchestrator/transforms engine-agnostic | PASS — gate test enforces |
| Registration chain | `parsers/__init__.py` imports trigger `@register_parser` | PASS — all 64 parsers properly wired |
| ANALYSIS_CAPABILITIES | Each engine driver declares capabilities | PARTIAL — 2 engines (QMCPACK, Yambo) have parsers but no declared capabilities |
| Full test suite | Zero failures after changes | PASS — 5085 passed, 0 failed |

### 2.2 Provider Quality by Analysis Type

| Analysis Type | Domain Object | to_primitives() | Transforms | Test Count | Engines |
|---------------|--------------|-----------------|------------|------------|---------|
| **bands** | BandStructure | Series1D[] + markers | FermiShift, EnergyCrop | 145 | 6 |
| **dos** | DOS | Series1D[] (total + PDOS) | FermiShift, EnergyCrop | 132 | 6 |
| **trajectory** | Trajectory | GeometryFrames + Series1D[] | FrameSlice, Smoothing, MSD, VACF, RDF, DiffusionCoeff | 60 | 12 |
| **convergence** | Convergence | Series1D[] (SCF + ionic) | Smoothing | 45 | 5 |
| **field3d** | Field3D | Arrays (preview only) + metadata | None | 47 (gate) + 80 (unit) | 11 |
| **scf_digest** | (flat dict) | N/A (not AnalysisObject) | N/A | Various | 13 |
| **neb_trajectory** | Trajectory (type="neb") | Same as trajectory | Same | ~8 | 1 (QE) |

### 2.3 Unit Convention Compliance

| Domain | Required Units | Implemented | Evidence |
|--------|---------------|-------------|----------|
| Energy | eV | YES | Ha→eV at parse time (ABINIT, QE, ORCA, Gaussian, Psi4, PySCF) |
| Length | Angstrom | YES | Bohr→A at parse time (cube_parser.py, all ABINIT/QE parsers) |
| Force | eV/A | YES | Ha/Bohr→eV/A at parse time |
| Pressure/Stress | GPa | YES | kbar→GPa where applicable |
| Coordinates | Cartesian Angstrom (unwrapped) | YES | Fractional→Cartesian conversion in structure parsers |
| Time | fs | YES | For MD trajectories |

---

## 3. Engine x Analysis Capability Matrix

### 3.1 Complete Registration Matrix

Legend:
- **BOTH** = Parser registered + ANALYSIS_CAPABILITIES declared (fully operational)
- **REG** = Parser registered but no capability declared (orphaned — cannot be dispatched by orchestrator)
- **--** = Not implemented
- **N/A** = Not applicable for this engine type

| Engine | scf_digest | bands | dos | trajectory | convergence | field3d | neb |
|--------|:---------:|:-----:|:---:|:----------:|:-----------:|:-------:|:---:|
| **VASP** | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH | -- |
| **QE** | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH |
| **ABINIT** | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH | -- |
| **CP2K** | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH | -- |
| **Siesta** | BOTH | BOTH | BOTH | BOTH | BOTH | BOTH | -- |
| **GPAW** | -- | BOTH | BOTH | BOTH | -- | BOTH | -- |
| **LAMMPS** | BOTH | N/A | N/A | BOTH | N/A | N/A | N/A |
| **ORCA** | BOTH | -- | -- | BOTH | -- | BOTH | N/A |
| **Gaussian** | BOTH | -- | -- | BOTH | -- | BOTH | N/A |
| **xTB** | BOTH | -- | -- | BOTH | -- | N/A | N/A |
| **Psi4** | -- | -- | -- | BOTH | -- | BOTH | N/A |
| **PySCF** | -- | -- | -- | BOTH | -- | BOTH | N/A |
| **QMCPACK** | REG | N/A | N/A | N/A | N/A | N/A | N/A |
| **W90** | REG | N/A | N/A | N/A | N/A | BOTH | N/A |
| **Yambo** | REG | -- | -- | N/A | N/A | N/A | N/A |

**Totals:**
- bands: 6 engines (VASP, QE, ABINIT, CP2K, Siesta, GPAW)
- dos: 6 engines (same as bands)
- trajectory: 12 engines (all except QMCPACK, W90, Yambo)
- convergence: 5 engines (VASP, QE, ABINIT, CP2K, Siesta)
- field3d: 11 engines (all except LAMMPS, xTB, QMCPACK, Yambo)
- neb_trajectory: 1 engine (QE)
- scf_digest: 13 engines (all except GPAW, Psi4, PySCF)

### 3.2 Orphaned Parsers (REG without ANALYSIS_CAPABILITIES)

| Engine | Parser | Issue | Impact |
|--------|--------|-------|--------|
| QMCPACK | scf_digest | No ANALYSIS_CAPABILITIES in driver.py | Digest still works via direct parser call, but orchestrator cannot auto-dispatch |
| W90 | scf_digest | Same | Same |
| Yambo | scf_digest | Same | Same |

**Risk: LOW** — scf_digest parsers are called directly by the step-digest path (Phase 1), not via capability matching (Phase 2). The orchestrator path is irrelevant for digests. However, for consistency, these drivers should declare capabilities or the gate tests should explicitly exclude scf_digest from capability-matching requirements.

### 3.3 What Each Engine Can Actually Calculate

This matrix shows what calculations each engine supports and whether our analysis pipeline can consume the results.

| Engine | SCF | Relax | VC-Relax | MD | Bands | DOS | NEB | Phonons | TDDFT | GW/BSE |
|--------|:---:|:-----:|:--------:|:--:|:-----:|:---:|:---:|:-------:|:-----:|:------:|
| **VASP** | S | S | S | S | S | S | P | P | -- | -- |
| **QE** | S | S | S | S | S | S | S | P | P | -- |
| **ABINIT** | S | S | S | S | S | S | -- | P | P | P |
| **CP2K** | S | S | S | S | S | S | P | P | S | -- |
| **Siesta** | S | S | S | S | S | S | -- | P | P | -- |
| **GPAW** | S | S | -- | S | S | S | -- | P | P | P |
| **LAMMPS** | N/A | S | N/A | S | N/A | N/A | N/A | P | N/A | N/A |
| **ORCA** | S | S | N/A | N/A | -- | -- | N/A | P | P | -- |
| **Gaussian** | S | S | N/A | N/A | -- | -- | N/A | P | P | -- |
| **xTB** | S | S | N/A | S | -- | -- | N/A | P | -- | -- |
| **Psi4** | S | S | N/A | N/A | -- | -- | N/A | P | P | -- |
| **PySCF** | S | S | N/A | N/A | -- | -- | N/A | -- | P | -- |
| **QMCPACK** | S | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **W90** | N/A | N/A | N/A | N/A | P | N/A | N/A | N/A | N/A | N/A |
| **Yambo** | N/A | N/A | N/A | N/A | P | P | N/A | N/A | N/A | P |

Legend:
- **S** = Supported (parser + capability declared, fully operational)
- **P** = Possible (engine supports it, but no analysis parser yet)
- **--** = Engine supports it but not practical/priority
- **N/A** = Engine cannot produce this output

---

## 4. Missing Analysis Pipelines

### 4.1 High-Value Gaps (Engine Supports, Pipeline Missing)

#### Gap M1: Phonon/Vibrational Analysis
- **Affects:** VASP (DYNMAT, PHON), QE (matdyn, q2r), ABINIT (anaddb), CP2K, Siesta, ORCA (freq), Gaussian (freq), Psi4 (freq)
- **Output types:** Phonon dispersion (similar to bands), phonon DOS, IR/Raman spectra, thermodynamic properties
- **Domain object needed:** `PhononBandStructure` (reuse BandStructure?) + `VibrationalSpectrum`
- **Complexity:** HIGH — requires multi-step workflows (SCF→DFPT→post-process), different per engine
- **Priority:** HIGH — vibrational analysis is fundamental in materials science

#### Gap M2: ORCA/Gaussian Bands and DOS
- **Affects:** ORCA, Gaussian (molecular orbital eigenvalues)
- **Why different:** Molecular codes don't have k-points. "Bands" is just MO energy levels; "DOS" is a broadened MO spectrum.
- **Possible approach:** Repurpose DOS domain object with delta-function broadening of MO eigenvalues
- **Priority:** MEDIUM — common analysis but different physics from periodic codes

#### Gap M3: xTB Electronic Structure
- **Affects:** xTB (orbital energies, partial charges)
- **Output types:** MO levels, Mulliken charges, Wiberg bond orders
- **Priority:** LOW — xTB is a semi-empirical screening tool

#### Gap M4: Yambo GW/BSE Spectra
- **Affects:** Yambo (quasiparticle band structure, optical absorption)
- **Output types:** QP-corrected bands, optical spectrum (Im[eps])
- **Domain object needed:** Could reuse BandStructure (QP bands) + new `OpticalSpectrum`
- **Priority:** MEDIUM — GW/BSE is niche but growing

#### Gap M5: W90 Interpolated Bands
- **Affects:** Wannier90 (band interpolation from MLWF)
- **Output types:** Interpolated band structure along arbitrary k-path
- **Domain object:** Reuse BandStructure
- **Priority:** MEDIUM — Wannier interpolation is widely used

#### Gap M6: GPAW/Psi4/PySCF scf_digest
- **Affects:** GPAW, Psi4, PySCF (Python-script engines)
- **Why missing:** These engines produce output via Python objects, not parseable text files
- **Possible approach:** Write digest info to structured JSON during script execution
- **Priority:** LOW — these engines work but lack step-level summary

#### Gap M7: GPAW/Siesta Convergence
- **Affects:** GPAW (no convergence parser), Siesta (has convergence but limited SCF detail)
- **Why missing:** GPAW outputs to Python logging; Siesta SCF detail in .out files
- **Priority:** LOW

#### Gap M8: NEB for Non-QE Engines
- **Affects:** VASP (VTST NEB), CP2K (NEB), LAMMPS (NEB fix)
- **Output types:** Minimum energy path, barrier height, image structures
- **Priority:** MEDIUM — NEB is used across many engines

### 4.2 Edge Case / Low Priority Gaps

| Gap | Engine(s) | Analysis | Reason for Low Priority |
|-----|-----------|----------|------------------------|
| Elastic constants | VASP, QE | Stress-strain tensor analysis | Requires special workflow |
| Optical spectra | QE (epsilon.x), VASP (OPTIC) | Dielectric function | Post-processing tool |
| Charge analysis | All DFT | Bader, Mulliken, Lowdin | External tools (bader, critic2) |
| Magnetic properties | VASP, QE, ABINIT | Magnetic moments, spin texture | Available in digest, not full analysis |
| Transport | QE (BoltzTraP), VASP | Seebeck, conductivity | External post-processing |
| Fermi surface | QE, VASP | 3D Fermi surface mesh | Existing BXSF parser in io/, not wired |

### 4.3 Capability Expansion Feasibility

| Gap | New Domain Object? | Reuse Existing? | Shared Parser? | Effort |
|-----|-------------------|----------------|---------------|--------|
| M1: Phonons | YES (PhononDispersion, VibrationalSpectrum) | Partial (BandStructure-like) | No (engine-specific) | LARGE |
| M2: Molecular MO levels | No | DOS (broadened MO) | No | SMALL |
| M3: xTB electronic | No | DOS | No | SMALL |
| M4: Yambo GW/BSE | Partial (OpticalSpectrum) | BandStructure | No | MEDIUM |
| M5: W90 bands | No | BandStructure | No | SMALL |
| M6: Script engine digests | No | scf_digest | No | SMALL |
| M7: Convergence expansion | No | Convergence | No | SMALL |
| M8: NEB expansion | No | Trajectory (type="neb") | No | MEDIUM |

---

## 5. GUI Readiness Assessment

### 5.1 Current GUI Architecture

```
Electron App (gui/)
├── React 18 + TypeScript 5
├── Vite build system
├── Recharts (2D charts)
├── React Three Fiber + Three.js (3D)
└── JSON-RPC over stdio ←→ Python daemon
```

### 5.2 GUI Analysis Rendering Status

| Analysis Type | Backend Ready | RPC Endpoint | GUI Component | Render Status |
|---------------|:------------:|:------------:|:-------------:|:-------------:|
| **bands** | YES | `get_analysis` | AnalysisVizPanel (LineChart) | WORKING |
| **dos** | YES | `get_analysis` | AnalysisVizPanel (LineChart) | BLOCKED (see 5.3) |
| **trajectory** | YES | `get_analysis` | None | NOT STARTED |
| **convergence** | YES | `get_analysis` | None | NOT STARTED |
| **field3d** | YES | `get_analysis` | VolumeViewerSandbox (dev-only) | NOT INTEGRATED |
| **PDOS** | YES (in dos bundle) | `get_analysis` | None | NOT STARTED |
| **fatbands** | YES (in bands bundle) | `get_analysis` | None | NOT STARTED |
| **neb** | YES | `get_analysis` | None | NOT STARTED |
| **scf_digest** | YES | `get_step_digest` | StepDigestPanel (key-value) | WORKING |

### 5.3 Detailed GUI Blockage Analysis

#### B1: DOS Not Rendered (Backend Ready, GUI Blocked)

**Root cause:** `CalculationAnalysisPanel.tsx` hardcodes `ANALYSIS_OBJECT_TYPES = ['bands']`

**What's needed:**
1. Add `'dos'` to `ANALYSIS_OBJECT_TYPES` array
2. `AnalysisVizPanel` already renders `bundle.series` as LineChart — DOS bundles produce Series1D[] with energy on x-axis and DOS on y-axis, so the **existing chart renderer should work** for total DOS
3. PDOS requires stacked area chart or multi-line with legend grouping

**Effort:** TRIVIAL for total DOS (1-line change), SMALL for PDOS (AreaChart component)

#### B2: Trajectory Not Rendered

**Root cause:** No trajectory visualization component exists

**What's needed:**
1. Add `'trajectory'` to `ANALYSIS_OBJECT_TYPES`
2. **Frame viewer component**: Read `bundle.geometry_frames` and render with StructureViewer3D
3. **Playback controls**: Play/pause, frame slider, step forward/backward
4. **Observable plots**: Read `bundle.series` for energy, forces, temperature vs frame/time
5. **Split layout**: Structure viewer (left) + time series (right)

**Effort:** MEDIUM — StructureViewer3D exists for static structures, needs frame-stepping logic

**Bundle field mapping:**
- `bundle.geometry_frames.positions` → atom positions per frame
- `bundle.geometry_frames.species` → atom types
- `bundle.geometry_frames.cell` → unit cell per frame
- `bundle.series` → scalar observables (energy, temperature, etc.)

#### B3: Convergence Not Rendered

**Root cause:** No convergence visualization component exists

**What's needed:**
1. Add `'convergence'` to `ANALYSIS_OBJECT_TYPES`
2. **Chart component**: Convergence bundles produce Series1D[] with:
   - SCF energy vs iteration
   - Ionic energy vs ionic step
   - Max force vs ionic step (if available)
3. The existing AnalysisVizPanel LineChart **should work as-is** for convergence plots (same series format as bands)
4. Optional: Log-scale y-axis for energy differences

**Effort:** TRIVIAL to SMALL — existing line chart should handle it, just add to object types

#### B4: Field3D Not Rendered in Production

**Root cause:** VolumeViewerSandbox exists but is development-only (not in main UI flow)

**What's needed:**
1. Add `'field3d'` to `ANALYSIS_OBJECT_TYPES`
2. Integrate VolumeViewerSandbox into production analysis panel
3. **Critical issue:** Field3D bundles use primitive-by-reference — `bundle.arrays` contains only `preview_data` (downsampled) and `lattice`, NOT the full grid. The VolumeViewerSandbox currently reads XSF files directly.
4. **New RPC needed:** `get_field3d_full_grid` or extend `get_analysis` to optionally include full grid
5. **Isosurface rendering:** VolumeViewerSandbox has marching cubes — needs to consume bundle format
6. **Performance:** 200^3 grid = 8M floats = ~64MB — cannot send via JSON-RPC. Need binary transfer (e.g., base64-encoded numpy array or file path reference)

**Effort:** LARGE — requires both backend RPC changes and frontend integration

#### B5: PDOS Projected Visualization

**Root cause:** No specialized PDOS renderer

**What's needed:**
1. Backend already includes PDOS in dos bundle: `bundle.arrays["pdos"]` (3D: n_atoms x n_energies x n_orbitals) + `render_meta.extra["atom_labels"]` + `render_meta.extra["orbital_labels"]`
2. **Stacked area chart** or multi-line chart with color coding
3. **Atom/orbital selector**: Checkboxes to filter which projections to show
4. **Spin channels**: Up/down mirrored if spin-polarized

**Effort:** MEDIUM — needs new Recharts AreaChart component + selector UI

#### B6: Fatband Rendering

**Root cause:** No projection-weighted band rendering

**What's needed:**
1. Backend includes projections in bands bundle: `bundle.arrays["projections"]` (4D) + `render_meta.extra["projection_labels"]`
2. **Variable-width lines**: Each band colored/sized by projection weight
3. **Color map**: Map projection character to color (e.g., s=red, p=blue, d=green)
4. **Projection selector**: Choose which atom/orbital to project

**Effort:** MEDIUM-LARGE — Recharts doesn't natively support variable-width lines; may need custom SVG rendering or switch to D3 direct

#### B7: NEB Visualization

**Root cause:** No NEB-specific component

**What's needed:**
1. NEB trajectory produces: energy vs image_index (reaction coordinate)
2. **Energy profile plot**: Energy vs reaction coordinate with barrier annotation
3. **Structure viewer**: Step through images along the path
4. The line chart component should work for the energy profile
5. Frame viewer from B2 would handle image stepping

**Effort:** SMALL — reuses trajectory frame viewer + existing line chart

### 5.4 RPC Layer Status

| RPC Endpoint | Backend | Daemon Handler | GUI Usage | Status |
|-------------|:-------:|:--------------:|:---------:|:------:|
| `get_analysis` | YES | YES | YES (bands only) | OPERATIONAL |
| `get_analysis_snapshot` | YES | YES | NO | UNUSED |
| `get_step_digest` | YES | YES | YES | OPERATIONAL |
| `get_reference_analysis` | YES | YES | YES (demo projects) | OPERATIONAL |
| `pin_analysis_to_history` | YES | YES | YES | OPERATIONAL |
| `get_structure_vis` | YES | YES | YES | OPERATIONAL |
| `list_raw_files` | YES | YES | YES | OPERATIONAL |
| `read_raw_file` | YES | YES | YES | OPERATIONAL |
| `get_field3d_full_grid` | NO | NO | NO | NOT EXISTS |

**Gap:** No mechanism to transfer full Field3D grid data to GUI. The `get_analysis` RPC returns the canonical bundle which by design excludes the full grid (primitive-by-reference, Inv spec §9). A new RPC endpoint or binary transfer mechanism is needed.

### 5.5 Transform Pipeline in GUI

| Transform | Backend | GUI Control | Status |
|-----------|:-------:|:-----------:|:------:|
| FermiShift | YES | Checkbox | WORKING |
| EnergyCrop | YES | None | NOT EXPOSED |
| FrameSlice | YES | None | NOT EXPOSED |
| Smoothing | YES | None | NOT EXPOSED |
| MSD | YES | None | NOT EXPOSED |
| VACF | YES | None | NOT EXPOSED |
| RDF | YES | None | NOT EXPOSED |
| DiffusionCoefficient | YES | None | NOT EXPOSED |

**Gap:** Only 1 of 8 transforms is exposed in the GUI. The `get_analysis` RPC supports a `transforms` parameter (list of transform names), but the GUI only sends `['fermi_shift']` via checkbox.

---

## 6. End-to-End Walkthrough: From Calculation to Plot

Let's trace what happens when a user runs a VASP Si band structure calculation and wants to see the result.

### 6.1 Bands (WORKING)

```
User clicks "Run" → daemon spawns VASP →
  VASP produces: EIGENVAL, KPOINTS, POSCAR, vasprun.xml, OUTCAR →

Phase 1 (Step Digest):
  VASPOutputParser.parse() → VASPDigest → SQLite digest_json ✓

Phase 2 (Capability Matching):
  ANALYSIS_CAPABILITIES: bands requires gen_step_sequence=["bandspw","bands"]
  Orchestrator matches contiguous ["bandspw","bands"] in run steps
  VASPBandsProvider.parse(evidence) → BandStructure → to_primitives() →
    CanonicalPrimitiveBundle {
      series: [Series1D(x=k_distances, y=eigenvalues[band_i])...],
      render_meta: {markers: [high_sym_points], reference_energy: fermi_eV},
      arrays: {projections: 4D fatband data}
    }

GUI:
  CalculationAnalysisPanel → RPC get_analysis(run_ulid, "bands") →
  AnalysisVizPanel → Recharts LineChart(series, markers) → ✓ VISIBLE
```

### 6.2 DOS (BLOCKED — trivial fix)

```
Same flow as bands but with DOSProvider → DOS → to_primitives() →
  CanonicalPrimitiveBundle {
    series: [Series1D(energy, total_dos), Series1D(energy, pdos_atom1_s), ...],
    arrays: {pdos: 3D array}
  }

GUI:
  BLOCKED at: ANALYSIS_OBJECT_TYPES = ['bands'] — 'dos' not listed
  FIX: Add 'dos' to the array → LineChart renders Series1D[] → ✓
  PDOS needs AreaChart or multi-line selection UI → requires new component
```

### 6.3 Convergence (NOT STARTED — easy)

```
VASPConvergenceProvider.parse() → Convergence → to_primitives() →
  CanonicalPrimitiveBundle {
    series: [
      Series1D(scf_step, scf_energy, name="SCF Energy"),
      Series1D(ionic_step, ionic_energy, name="Ionic Energy"),
      Series1D(ionic_step, max_force, name="Max Force"),
    ]
  }

GUI:
  NOT STARTED — needs 'convergence' in ANALYSIS_OBJECT_TYPES
  Existing LineChart renderer should work for convergence plots
  Optional: Log scale y-axis for deltaE convergence
```

### 6.4 Trajectory (NOT STARTED — medium effort)

```
VASPTrajectoryProvider.parse() → Trajectory → to_primitives() →
  CanonicalPrimitiveBundle {
    series: [Series1D(time, energy), Series1D(time, temperature), ...],
    geometry_frames: {
      positions: [[frame0_atoms], [frame1_atoms], ...],
      species: ["Si", "Si"],
      cell: [[frame0_cell], [frame1_cell], ...],
    }
  }

GUI:
  NOT STARTED — needs:
  1. 'trajectory' in ANALYSIS_OBJECT_TYPES
  2. TrajectoryPanel component:
     - StructureViewer3D with frame index state
     - Playback controls (play/pause/slider)
     - Observable time-series plots (reuse LineChart for series)
  3. Split layout: 3D viewer + time series side-by-side
```

### 6.5 Field3D (NOT INTEGRATED — large effort)

```
VASPField3DProvider.parse() → Field3D → to_primitives() →
  CanonicalPrimitiveBundle {
    arrays: {
      preview_data: [downsampled 1D array],
      lattice: [[3x3 matrix]],
    },
    render_meta.extra: {
      volume_metadata: {grid_shape, grid_vectors, value_min/max/mean, ...},
      field_kind: "charge_density",
    }
  }

  NOTE: Full grid_data is NOT in the bundle! (primitive-by-reference)
  Full grid lives on the Field3D object in Python memory only.

GUI:
  NOT INTEGRATED:
  1. VolumeViewerSandbox exists (marching cubes, isosurface) but reads XSF files directly
  2. No RPC to fetch full grid data from daemon
  3. CRITICAL BLOCKER: JSON-RPC cannot efficiently transfer 8M+ float arrays
     Options:
     a) Base64-encode numpy binary in RPC response (~100MB for 200^3)
     b) Write to temp file, return path (daemon writes, GUI reads)
     c) Shared memory / IPC channel
     d) Send only preview, let GUI render low-res isosurface
     e) Server-side rendering → send image/mesh to GUI
  4. Need new RPC: get_field3d_grid(run_ulid) → full grid + metadata
```

---

## 7. Recommendations and Priority

### 7.1 Quick Wins (Close Backend Gaps)

| # | Action | Files to Change | Effort | Impact |
|---|--------|----------------|--------|--------|
| Q1 | Add QMCPACK/W90/Yambo ANALYSIS_CAPABILITIES for scf_digest | 3 driver.py files | 15 min | Consistency |
| Q2 | Add GPAW scf_digest parser | 1 new parser file | 2 hr | Complete GPAW |
| Q3 | Add Psi4/PySCF scf_digest parsers | 2 new parser files | 2 hr | Complete Python engines |

### 7.2 Frontend: Enable Existing Backend Features

| # | Action | GUI Files | Effort | Impact |
|---|--------|-----------|--------|--------|
| F1 | Enable DOS in GUI (add to ANALYSIS_OBJECT_TYPES) | CalculationAnalysisPanel.tsx | TRIVIAL | DOS visible for 6 engines |
| F2 | Enable convergence in GUI | CalculationAnalysisPanel.tsx | TRIVIAL | Convergence visible for 5 engines |
| F3 | Enable NEB in GUI | CalculationAnalysisPanel.tsx | TRIVIAL | NEB visible for QE |
| F4 | PDOS renderer (AreaChart + selector) | New component | SMALL-MEDIUM | PDOS for 6 engines |
| F5 | Trajectory viewer (frames + plots) | New component | MEDIUM | Trajectory for 12 engines |
| F6 | Expose more transforms (EnergyCrop, Smoothing) | CalculationAnalysisPanel.tsx | SMALL | Better interactivity |
| F7 | Fatband renderer | New component | MEDIUM-LARGE | Fatbands for VASP/QE |
| F8 | Field3D isosurface (integrate VolumeViewerSandbox) | Multiple files + new RPC | LARGE | Field3D for 11 engines |

### 7.3 Backend: New Analysis Pipelines

| # | Action | New Domain Object? | Effort | Impact |
|---|--------|-------------------|--------|--------|
| N1 | Phonon dispersion + DOS | YES (PhononDispersion) | LARGE | All DFT engines |
| N2 | Molecular MO levels (ORCA/Gaussian) | No (reuse DOS) | SMALL | 2 engines |
| N3 | W90 interpolated bands | No (reuse BandStructure) | SMALL | 1 engine |
| N4 | NEB for VASP/CP2K | No (reuse Trajectory, type="neb") | MEDIUM | 2 engines |
| N5 | Yambo GW bands + optical spectrum | Partial (OpticalSpectrum) | MEDIUM | 1 engine |
| N6 | IR/Raman spectra | YES (VibrationalSpectrum) | MEDIUM | Multiple engines |

### 7.4 Suggested Implementation Order

**Phase I — GUI Quick Wins (unlock existing backend)**
1. F1: DOS in GUI (trivial)
2. F2: Convergence in GUI (trivial)
3. F3: NEB in GUI (trivial)
4. F6: Expose transforms (small)
5. Q1-Q3: Backend consistency fixes

**Phase II — Core Visualization**
6. F4: PDOS renderer
7. F5: Trajectory viewer with playback
8. N2: Molecular MO levels for ORCA/Gaussian

**Phase III — Advanced Visualization**
9. F7: Fatband renderer
10. F8: Field3D isosurface integration
11. N3: W90 interpolated bands
12. N4: NEB expansion to VASP/CP2K

**Phase IV — New Physics**
13. N1: Phonon dispersion (large effort, high value)
14. N5: Yambo GW/BSE
15. N6: IR/Raman spectra

---

## Appendix A: Test Coverage Summary

| Category | Test Count |
|----------|-----------|
| Band structure tests | 145 |
| DOS tests | 132 |
| Trajectory tests | 60 |
| Convergence tests | 45 |
| Field3D tests (gate + unit) | 127 |
| Gate analysis invariant tests | 109 |
| Other analysis tests | ~30 |
| **Total analysis-related** | **~449+** |
| **Total project tests** | **5104 collected, 5085 passed** |

## Appendix B: Domain Object to Bundle Field Mapping

| Domain Object | series[] | geometry_frames | arrays | render_meta keys |
|---------------|:--------:|:---------------:|:------:|:----------------:|
| BandStructure | eigenvalue traces per band | -- | projections (4D) | markers (k-points), reference_energy |
| DOS | total_dos + PDOS traces | -- | pdos (3D) | reference_energy, atom_labels, orbital_labels |
| Trajectory | energy, temperature, pressure, forces... | positions + species + cell per frame | -- | trajectory_type |
| Convergence | scf_energy, ionic_energy, max_force | -- | -- | algorithm, converged |
| Field3D | -- | -- | preview_data, lattice | volume_metadata, field_kind, discovered_files |

## Appendix C: Parser Registration Count by Engine

| Engine | Total Parsers | Types |
|--------|:------------:|-------|
| VASP | 6 | scf_digest, bands, dos, trajectory, convergence, field3d |
| QE | 7 | scf_digest, bands, dos, trajectory, convergence, field3d, neb_trajectory |
| ABINIT | 6 | scf_digest, bands, dos, trajectory, convergence, field3d |
| CP2K | 6 | scf_digest, bands, dos, trajectory, convergence, field3d |
| Siesta | 6 | scf_digest, bands, dos, trajectory, convergence, field3d |
| GPAW | 4 | bands, dos, trajectory, field3d |
| ORCA | 3 | scf_digest, trajectory, field3d |
| Gaussian | 3 | scf_digest, trajectory, field3d |
| LAMMPS | 2 | scf_digest, trajectory |
| xTB | 2 | scf_digest, trajectory |
| Psi4 | 2 | trajectory, field3d |
| PySCF | 2 | trajectory, field3d |
| W90 | 2 | scf_digest, field3d |
| QMCPACK | 1 | scf_digest |
| Yambo | 1 | scf_digest |
| **Total** | **53** | 7 distinct types |
