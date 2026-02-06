# QMCPACK Phase B1: Exploration (Stages 1-3)

**Status**: COMPLETE
**Started**: 2026-02-06
**Baseline**: 3691 passed, 24 skipped
**Final**: 3864 passed, 24 skipped (no regressions; +173 from parallel Gaussian work)
**Constraint**: Exploration only — no src/quantumvitas/ changes

---

## Overview

QMCPACK is syntax family F6 (XML) per UNIVERSAL_PARSER_WRITER_DESIGN.md. It uses a
structured `<simulation>` XML format with `<parameter name="key">value</parameter>`
convention. This exploration track collects documentation, builds a metadata seed,
normalizes tutorial/test cases, and validates fast cases with the local QMCPACK install.

**QMCPACK specifics:**
- Version: 4.1.0 (built Jan 27 2026 with GCC)
- Binary: `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack`
- QE pw2qmcpack: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x`
- MPI-enabled build (requires `mpirun`)
- XSD schema available at `schema/qmcpack.xsd`

**Key characteristics:**
- XML root: `<simulation>` containing `<project>`, `<qmcsystem>`, `<qmc>`, `<loop>`
- Structure embedded in `<simulationcell>` (lattice) + `<particleset>` (ions + electrons)
- Wavefunction: `<wavefunction>` with `<determinantset>` and `<jastrow>` children
- Hamiltonian: `<hamiltonian>` with `<pairpot>` children (coulomb, pseudo, mpc)
- QMC methods: `<qmc method="vmc|dmc|linear|optimize">` with `<parameter>` children
- Loop construct: `<loop max="N">` wraps `<qmc>` for iterative optimization
- Include mechanism: `<include href="file.xml"/>` for external structure/wavefunction
- Resource files: HDF5 wavefunctions (from pw2qmcpack), XML pseudopotentials

---

## Stage 1: Documentation + Raw Corpus

### Objectives
- Collect official QMCPACK documentation (readthedocs, manual)
- Extract bundled examples and test cases from source tree
- Collect ecosystem docs (pw2qmcpack, pseudopotential libraries)
- Catalog XSD schema elements

### Sources
1. **Bundled source tree** (primary):
   - `labs/` (5 lab tutorials with reference inputs)
   - `examples/molecules/` (He, H2O with multiple wavefunction forms)
   - `examples/solids/` (LiH, RMG-diamond)
   - `tests/molecules/` (25 test systems: H2, He, Be, C2, C4, LiH, FeCO6, etc.)
   - `tests/solids/` (19 test systems: diamond, bcc, graphene, NiO, etc.)
   - `tests/converter/` (converter gold-standard XML files)
   - `schema/` (XSD schema files)
   - `tests/pseudopotentials_for_tests/` (PP library)
2. **Online docs** (supplementary):
   - qmcpack.readthedocs.io (input overview, methods, wavefunctions, hamiltonians)
   - GitHub qmcpack/qmcpack README and examples

### Deliverables
- `.tmp/engine_research/qmcpack/extracted/` — XML inputs extracted from source tree
- `.tmp/engine_research/qmcpack/raw_web/` — Crawled documentation pages
- `docs/engines/qmcpack/SOURCES.md` — Provenance catalog

---

## Stage 2: Metadata Seed

### Objectives
- Build comprehensive metadata catalog for QMCPACK XML elements and attributes
- Derive from XSD schema + documentation + example analysis
- Each entry: XPath, kind, type, description, allowed values, provenance

### Categories
1. **Simulation** — `<simulation>` root, `<project>`, `<random>`
2. **System** — `<qmcsystem>`, `<simulationcell>` (lattice, bconds, LR_dim_cutoff)
3. **Particles** — `<particleset>`, `<group>`, `<attrib>` (position, ionid, charge)
4. **Wavefunction** — `<wavefunction>`, `<determinantset>`, `<slaterdeterminant>`
5. **SPO builders** — `<sposet_builder>` (bspline, MO, einspline), `<sposet>`
6. **Jastrow** — `<jastrow>` (One-Body, Two-Body, Three-Body), `<correlation>`, `<coefficients>`
7. **Hamiltonian** — `<hamiltonian>`, `<pairpot>` (coulomb, pseudo, mpc), `<pseudo>`
8. **Estimators** — `<estimator>` types (density, spindensity, gofr, sk, dm1b, Force, etc.)
9. **QMC blocks** — `<qmc method="...">` (vmc, dmc, linear, optimize) + all parameters
10. **Loop** — `<loop max="N">` wrapper
11. **Include/Refs** — `<include href>`, HDF5 href, pseudo href

### Deliverables
- `.tmp/engine_research/qmcpack/metadata/qmcpack_xml_elements.json`
- `.tmp/engine_research/qmcpack/metadata/qmcpack_qmc_parameters.json`
- `.tmp/engine_research/qmcpack/metadata/qmcpack_estimators.json`

---

## Stage 3: Normalized Case Library

### Objectives
- Create 10-12 normalized cases covering major QMCPACK workflows
- Each case: `qmc_input.xml` + `case.yaml` + `source.txt`
- Asset-heavy files use ResourceRef placeholders (no large binaries committed)
- Run a subset of fast cases with local QMCPACK install

### Case Selection Criteria
Maximize diversity across:
- **Methods**: VMC, DMC, wavefunction optimization (linear)
- **Systems**: molecular (open BC) vs periodic (PBC)
- **Wavefunctions**: STO analytic, bspline/HDF5, MO/Gaussian
- **Pseudopotentials**: all-electron vs PP
- **Complexity**: single atom → multi-atom molecule → solid

### Planned Cases

| Case ID | System | Method | Wavefunction | BC | Notes |
|---------|--------|--------|-------------|-----|-------|
| he_vmc_sto | He atom | VMC | STO analytic | open | Simplest; no external assets |
| he_opt_pade | He atom | linear opt | Pade Jastrow | open | Optimization loop |
| he_dmc | He atom | VMC+DMC | STO+Jastrow | open | DMC with walker population |
| h2o_vmc_pp | H2O | VMC | BFD PP basis | open | Multi-atom molecule + PP |
| h2o_dmc_pp | H2O | VMC+DMC | BFD PP basis | open | Molecular DMC |
| o2_opt_bspline | O2 dimer | optimization | bspline from QE | open | Requires HDF5 wavefunction |
| o2_dmc_bspline | O2 dimer | VMC+DMC | bspline from QE | open | Production-like workflow |
| lih_solid_vmc | LiH solid | VMC | einspline/HDF5 | PBC | Periodic solid + PP |
| lih_solid_dmc | LiH solid | VMC+DMC | einspline/HDF5 | PBC | Solid DMC |
| be_sto_vmc | Be atom | VMC | STO basis | open | All-electron, no PP |
| diamond_vmc_pp | Diamond C | VMC | bspline/HDF5 | PBC | Periodic covalent solid |
| h2_ae_vmc | H2 molecule | VMC | STO basis | open | Simplest all-electron molecule |

### Asset Handling
- **Self-contained** (no external assets): he_vmc_sto, he_opt_pade, he_dmc, be_sto_vmc, h2_ae_vmc
- **PP-only** (small XML files): h2o_vmc_pp, h2o_dmc_pp
- **HDF5-dependent** (ResourceRef placeholders): o2_opt_bspline, o2_dmc_bspline, lih_solid_vmc, lih_solid_dmc, diamond_vmc_pp

### Fast Cases for Execution
Self-contained cases (no external HDF5/QE dependency):
1. **he_vmc_sto** — ~5 seconds
2. **he_opt_pade** — ~10 seconds
3. **he_dmc** — ~30 seconds
4. **be_sto_vmc** — ~10 seconds
5. **h2_ae_vmc** — ~5 seconds

### Deliverables
- `.tmp/engine_research/qmcpack/normalized/<case_id>/` (10-12 cases)
- `.tmp/engine_research/qmcpack/runs/<case_id>/` (fast-case runs)
  - `run_manifest.json` (binary path, input hash, walltime, success/failure)
  - `digest.json` (success, energy estimate, key summary)

---

## Acceptance Criteria

- [x] Plan doc written at `docs/engines/qmcpack/PHASE_B1_PLAN.md`
- [x] Substantial offline corpus exists under `.tmp/engine_research/qmcpack/` (1,438 XML files)
- [x] `docs/engines/qmcpack/SOURCES.md` committed with provenance
- [x] Metadata seed exists for major XML elements/attributes with provenance (175 entries)
- [x] 10+ normalized cases with broad workflow coverage (13 cases: VMC/DMC/opt/periodic)
- [x] 3+ fast cases executed with run manifests + digests (5 cases, all SUCCESS)
- [x] `docs/engines/qmcpack/PHASE_B1_WORKLOG.md` maintained throughout

---

## Test Command

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Run frequently to confirm no regressions (exploration track should not change code).
