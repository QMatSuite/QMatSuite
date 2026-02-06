# QMCPACK Phase B1 Worklog

## 2026-02-06 — Session Start

### Plan Written
- Created `PHASE_B1_PLAN.md` covering stages 1-3 exploration
- QMCPACK 4.1.0 binary at `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack`
- Also available: `convert4qmc`, `convertpw4qmc`, `ppconvert`, `qmcfinitesize`, `gpaw4qmcpack.py`
- QE pw2qmcpack.x at `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x`
- Build is MPI-enabled (openmpi 5.0.9)

### Stage 1: Corpus Collection — DONE
- Explored QMCPACK source tree: labs/ (5 tutorials), examples/ (He, H2O, solids), tests/ (25 molecule + 19 solid systems)
- Read XSD schema (`schema/qmcpack.xsd`): 886 lines, defines all major types
- Crawled readthedocs pages: input_overview, running, hamiltonians, methods, wavefunctions, examples, output_overview, afqmc, labs
- Key XML structure mapped: simulation > {project, qmcsystem > {simulationcell, particleset, wavefunction, hamiltonian}, qmc, loop}
- XSD enums cataloged: QMCEngineEnum (vmc/dmc/rmc/optimize/test), QMCMoveEnum (pbyp/walker), JastrowFunctionEnum (One-Body/Two-Body/Three-Body/Polarization), etc.
- Extracted 1,438 XML files to `.tmp/engine_research/qmcpack/extracted/`:
  - `labs/` (5 lab tutorials)
  - `examples/` (He, H2O, solids)
  - `tests_molecules/` (22 subdirectories: H2_ae, Be_STO, FeCO6, etc.)
  - `tests_solids/` (28 subdirectories: diamondC, bccMo, graphene, NiO, etc.)
  - `tests_converter/` (22 converter test directories)
  - `schema/` (10 XSD/XML schema files)
  - `pseudopotentials_for_tests/` (PP library)
- Crawled community/academic sources: GitHub workshops, Nexus docs, pseudopotential libraries, AFQMC tutorials

### Stage 2: Metadata Seed — DONE
- Created `metadata/qmcpack_xml_elements.json`: **175 entries** (71KB)
  - Categories: simulation root, system/cell, particles, wavefunction, SPO builders, Jastrow, hamiltonian, estimators, QMC blocks, loop, includes
  - Each entry: xpath, kind, type, description, allowed_values, default, required, provenance
- Created `metadata/qmcpack_qmc_parameters.json`: per-method parameter catalog
  - VMC, DMC, linear optimization, general optimize
  - All parameters with type, default, description, provenance
- Created `metadata/qmcpack_estimators.json`: estimator type catalog
  - LocalEnergy, density, spindensity, gofr, sk, dm1b, Force, Pressure, chiesa, etc.

### Stage 3: Normalized Case Library — DONE
- Created **13 normalized cases** under `.tmp/engine_research/qmcpack/normalized/`:
  - Each case: `qmc_input.xml` + `case.yaml` + `source.txt`

| Case ID | System | Method | Wavefunction | BC | External Assets |
|---------|--------|--------|-------------|-----|-----------------|
| he_vmc_sto | He atom | VMC | STO + Pade Jastrow | open | none |
| he_opt_pade | He atom | linear opt (4 loops) | STO + Pade Jastrow | open | none |
| he_dmc | He atom | VMC + DMC | STO + Pade Jastrow | open | none |
| he_bspline_jastrow | He atom | VMC | STO + bspline Jastrow | open | none |
| be_sto_vmc | Be atom | VMC | STO (Bunge basis) | open | none |
| h2_ae_vmc | H2 molecule | VMC | Gaussian LCAO + J1+J2 | open | none |
| h2o_vmc_pp | H2O | VMC | BFD PP | open | PP XMLs (ResourceRef) |
| lih_pp_vmc | LiH molecule | VMC | BFD PP | open | PP XMLs (ResourceRef) |
| heg_vmc | Electron gas | VMC | Free particle | PBC | none |
| o2_opt_bspline | O2 dimer | optimization | bspline/HDF5 | open | HDF5 (ResourceRef) |
| o2_dmc_bspline | O2 dimer | VMC+DMC | bspline/HDF5 | open | HDF5 (ResourceRef) |
| lih_solid_vmc_pp | LiH solid | VMC | einspline/HDF5 | PBC | HDF5 + PP (ResourceRef) |
| diamond_vmc_pp | Diamond C | VMC | bspline/HDF5 | PBC | HDF5 + PP (ResourceRef) |

### Stage 3: Fast Case Execution — DONE
- Executed **5 fast self-contained cases** with QMCPACK 4.1.0:

| Case | Method | Energy (Ha) | Reference (Ha) | Wall Time | Status |
|------|--------|-------------|-----------------|-----------|--------|
| he_vmc_sto | VMC | -2.773 | -2.904 | 1.1s | SUCCESS |
| he_dmc | VMC+DMC | -2.870 (DMC) | -2.904 | 4.9s | SUCCESS |
| he_opt_pade | opt+VMC | -2.897 (final) | -2.904 | 6.9s | SUCCESS |
| be_sto_vmc | VMC | -14.626 | -14.667 | 7.8s | SUCCESS |
| h2_ae_vmc | VMC | -1.177 | -1.175 | 1.7s | SUCCESS |

- Run manifests + digests stored in `.tmp/engine_research/qmcpack/runs/<case_id>/`
- Key observations:
  - Batch driver (QMCPACK 4.x) requires `driver_version=batch` or `legacy`
  - Legacy driver needed for `samples` parameter in optimization (batch driver checks `samples <= walkers * blocks * steps`)
  - All-electron cases (He, Be, H2) run in <10s each
  - DMC energy (-2.870 Ha) approaches exact He energy (-2.904 Ha) despite small walker population

### Lessons Learned
1. **driver_version matters**: batch vs legacy have different sample semantics
2. **Self-contained inputs**: He/Be/H2 are fully self-contained (STO/Gaussian basis, no external files)
3. **HDF5-dependent cases**: O2/LiH/Diamond require pw2qmcpack preprocessing (not executed)
4. **Optimization with loop**: `<loop max="N">` wraps `<qmc method="linear">` for iterative optimization
5. **QMCPACK output structure**: scalar.dat (block-averaged), dmc.dat (step-level), opt.xml (optimized params)
