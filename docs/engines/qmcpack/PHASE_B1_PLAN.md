# QMCPACK Phase B1: Full Implementation (Stages 1-8)

**Status**: COMPLETE
**Started**: 2026-02-06
**Baseline**: 3921 passed, 24 skipped (post-Gaussian)
**Constraint Stages 1-3**: Exploration only — no src/quantumvitas/ changes
**Stages 4-8**: Implementation — parser/writer, output digest, tests

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

Run frequently to confirm no regressions.

---

## Stage 4: XML Input Parser + Enhanced Writer

### 4a. Parser (`_parse_qmcpack_text`)

**File**: `src/quantumvitas/drivers/qmcpack/inputspec.py`

XML parser using `xml.etree.ElementTree` that returns `{"params": {...}, "structure": {...}}`
for content_role="combined" convention. Extracts:
- Project (id, series, driver_version)
- Simulationcell (lattice, bconds, LR_dim_cutoff, rs)
- Ion particleset → structure (species, frac_coords/cart_coords)
- Electron particleset → electron counts
- Wavefunction (preserved as XML string + key semantic fields)
- Hamiltonian (preserved as XML string + key semantic fields)
- QMC blocks (list of dicts with method + parameters + costs + estimators)
- Loop wrappers (_loop_max)
- Resource refs (wavefunction_hrefs, pseudopotential_hrefs, include_hrefs)

Handles two position layouts: flat (with ionid) and grouped.

### 4b. Enhanced Writer (`_write_qmcpack_text`)

Reconstructs full XML from params + structure:
- Uses preserved `_wavefunction_xml` / `_hamiltonian_xml` for lossless roundtrip
- Generates project, simulationcell, particlesets, qmc blocks from structured params
- Handles loop wrappers, cost elements, estimators

### 4c. Wiring

`custom_parser=_parse_qmcpack_text` added to `InputFileSpec` in `get_qmcpack_input_spec()`.

**Status**: [x] DONE

---

## Stage 5: Output Digest (Parser Registry)

**New files**:
- `src/quantumvitas/drivers/qmcpack/parsers/__init__.py`
- `src/quantumvitas/drivers/qmcpack/parsers/output.py`

`QMCPACKDigest` dataclass (14 fields) + `QMCPACKOutputParser` registered as
`("qmcpack", "scf_digest")`. Reuses existing `parser.py` functions. Includes
`parse_qmcpack_stdout_text()` convenience function for unit testing.

**Status**: [x] DONE

---

## Stage 6: ResourceRef Handling

`_extract_resource_refs()` in `inputspec.py` extracts `href` attributes from:
- `<determinantset href="...">` (wavefunction HDF5)
- `<pseudo href="...">` (pseudopotentials)
- `<include href="...">` (XML includes)

Stored in `params["_resource_refs"]`. Tested without requiring actual asset files.

**Status**: [x] DONE

---

## Stage 7: QE→QMCPACK Workflow Validation

Complete QE→pw2qmcpack→QMCPACK workflow validated:
- `lih_qe_workflow`: QE SCF (1.5s) → pw2qmcpack (0.2s) → QMCPACK VMC (0.1s)
- Energy: -8.087 Ha (LiH solid, Gamma-point, unoptimized Jastrow)
- 6 total validation runs (5 self-contained + 1 QE workflow)

**Status**: [x] DONE

---

## Stage 8: Tests

### 8a. Curated Samples (`tests/inputformat/samples/qmcpack/`)
5 XML samples: he_vmc_sto, h2_ae_vmc, lih_solid_vmc_pp, he_opt_pade, heg_vmc

### 8b. `test_qmcpack_parse.py` (~50 tests)
Parser, writer, roundtrip, resource refs, orchestrator integration

### 8c. `test_qmcpack_digest.py` (~15 tests)
Stdout parsing, scalar.dat parsing, registry registration, error handling

**Status**: [x] DONE

---

## Acceptance Criteria (Stages 4-8)

- [x] `_parse_qmcpack_text` parses all 5 curated samples correctly
- [x] `_write_qmcpack_text` produces valid XML from parsed params
- [x] Roundtrip (parse → write → parse) holds for all 5 samples
- [x] `QMCPACKOutputParser` registered with parser registry
- [x] ResourceRef extraction tested for PP and HDF5 hrefs
- [x] QE→QMCPACK workflow validated with live execution
- [x] All new tests pass, zero regressions from baseline
