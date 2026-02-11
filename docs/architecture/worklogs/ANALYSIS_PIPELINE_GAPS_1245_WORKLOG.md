# Analysis Pipeline Gap Closure: Gaps 1, 2, 4, 5 + Pre-Gaps

## Summary

Closed all identified gaps from the `TRAJECTORY_ANALYSIS_DESIGN.md` compliance review.
Baseline: 4874 passed. Final: 4980 passed (+106 new tests), 0 failures, 19 skipped.

## Pre-Gap Fixes (Design Doc Compliance)

### ABINIT md trajectory capability
- Added `"md"` to `SUPPORTED_GEN_STEPS` in `drivers/abinit/driver.py`
- Added `abinit_md` StepTypeSpec
- Added `AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"], evidence_files=["*_HIST.nc"])`
- Added `"md"` to `get_capabilities()`

### xTB md trajectory capability
- Added `"md"` to `SUPPORTED_GEN_STEPS` in `drivers/xtb/driver.py`
- Added `xtb_md` StepTypeSpec
- Added `AnalysisCapability(object_type="trajectory", gen_step_sequence=["md"], evidence_files=["xtb.trj"])`
- Added `"md"` to `get_capabilities()`

## Gap 1: Convergence Parsers (4 new engines)

Each parser follows the VASP convergence parser template: standalone parse function + `@register_parser` provider class.

| Engine | File | SCF Pattern | Ionic Pattern | Unit Conversion |
|--------|------|------------|---------------|-----------------|
| QE | `drivers/qe/parsers/convergence.py` | `iteration # N` + `total energy = X Ry` | `!  total energy` | Ry -> eV (x13.605693) |
| ABINIT | `drivers/abinit/parsers/convergence.py` | `ETOT N energy dE` | `Total energy (etotal) [Ha]` | Ha -> eV (x27.211386) |
| Siesta | `drivers/siesta/parsers/convergence.py` | `scf: N E_harris E_KS` | `siesta: E_KS(eV)` | Already eV |
| CP2K | `drivers/cp2k/parsers/convergence.py` | SCF table rows | `ENERGY\| Total FORCE_EVAL` | Ha -> eV (x27.211386) |

Each wired via:
- `parsers/__init__.py` import
- `driver.py` ANALYSIS_CAPABILITIES (scf + relax gen_step_sequences)

Tests: 36 total (9 per engine x 4 engines), all passing.

## Gap 2: Trajectory Transform Library (6 transforms)

All transforms at `src/quantumvitas/core/analysis/transforms/`. Each subclasses `PrimitiveTransform`, uses `clone_bundle_for_transform()`, appends `TransformRecord`. No engine imports.

| Transform | File | Input | Output |
|-----------|------|-------|--------|
| FrameSlice | `frame_slice.py` | geometry_frames + series | Subsetted frames + aligned series |
| Smoothing | `smoothing.py` | series y-values | Running average (np.convolve valid) |
| MSD | `msd.py` | positions over time | Mean square displacement Series1D |
| RDF | `rdf.py` | positions + cell (PBC) | Radial distribution function Series1D |
| VACF | `vacf.py` | velocities over time | Velocity autocorrelation Series1D |
| DiffusionCoefficient | `diffusion.py` | MSD series | D = slope/6 in arrays dict |

Tests: 23 total in `tests/core/analysis/test_trajectory_transforms.py`, all passing.

## Gap 4: QE NEB Trajectory

- Parser: `drivers/qe/parsers/neb_trajectory.py`
  - Parses AXSF (animated XSF) for per-image geometries
  - Parses `.path` file for per-image energies (Ry -> eV)
  - Returns `Trajectory` with `trajectory_type="neb"`, `n_images=N`
  - Each image has `image_index=N` (1-based)
- Added `"neb"` to QE `SUPPORTED_GEN_STEPS` and GenStepRegistry
- Added `qe_neb` StepTypeSpec (executable: `neb.x`)
- Added `AnalysisCapability(object_type="neb_trajectory", gen_step_sequence=["neb"])`
- Fixture: 12-image NH3 inversion NEB from `tests/data/5_NH3_inversion/reference_out/`
- Tests: 11 total, all passing.

## Gap 5: Psi4/PySCF Trajectory Parsers

Both are molecular codes (no PBC, `cell=None`). Fixtures generated from real engine runs.

### Psi4
- Fixture: `tests/data/analysis_psi4_trajectory/output.dat` — H2O B3LYP/cc-pVDZ, 3 opt steps
- Parser: `drivers/psi4/parsers/trajectory.py`
  - Parses `@DF-RKS Final Energy:` for energies (Ha -> eV)
  - Parses `==> Geometry <==` blocks for Cartesian coordinates (Angstrom)
  - Handles paired geometry blocks (SCF + gradient = 2 per step)
- Wiring: `parsers/__init__.py`, `__init__.py` import, ANALYSIS_CAPABILITIES
- Tests: 10 total, all passing.

### PySCF
- Fixture: `tests/data/analysis_pyscf_trajectory/output.out` — H2O B3LYP/STO-3G, 4 opt cycles
- Parser: `drivers/pyscf/parsers/trajectory.py`
  - Parses `converged SCF energy =` for energies (Ha -> eV)
  - Parses `Cartesian coordinates (Angstrom)` blocks for geometry
  - Splits on `Geometry optimization cycle N` markers
- Wiring: same pattern as Psi4
- Tests: 10 total, all passing.

## Gate Tests Added

In `tests/gates/test_analysis_invariants.py`:
- `test_trajectory_parser_matrix` expanded: 10 -> 12 engines (added psi4, pyscf)
- `test_trajectory_engine_has_analysis_capabilities` expanded: 10 -> 12 engines
- `test_convergence_parser_matrix` — new, parametrized for qe, vasp, abinit, siesta, cp2k
- `test_convergence_engine_has_analysis_capabilities` — new, 5 engines
- `test_trajectory_transforms_importable` — new, verifies all 6 transforms importable
- `test_neb_trajectory_parser_registered` — new, verifies qe/neb_trajectory parser

Gate test total: 85 (up from 69).

## Ancillary Fixes

1. **S1 sensitive paths**: Sanitized 3 fixture files (CP2K, ORCA, Siesta trajectory outputs)
2. **Daemon test**: Updated `test_si_bands_golden_daemon.py` to handle multiple analysis results (bands + convergence) instead of exactly 1
3. **GenStepRegistry**: Added `"neb"` gen step

## File Inventory

### New Files (21)
- `src/quantumvitas/drivers/qe/parsers/convergence.py`
- `src/quantumvitas/drivers/abinit/parsers/convergence.py`
- `src/quantumvitas/drivers/siesta/parsers/convergence.py`
- `src/quantumvitas/drivers/cp2k/parsers/convergence.py`
- `src/quantumvitas/core/analysis/transforms/frame_slice.py`
- `src/quantumvitas/core/analysis/transforms/smoothing.py`
- `src/quantumvitas/core/analysis/transforms/msd.py`
- `src/quantumvitas/core/analysis/transforms/rdf.py`
- `src/quantumvitas/core/analysis/transforms/vacf.py`
- `src/quantumvitas/core/analysis/transforms/diffusion.py`
- `src/quantumvitas/drivers/qe/parsers/neb_trajectory.py`
- `src/quantumvitas/drivers/psi4/parsers/__init__.py`
- `src/quantumvitas/drivers/psi4/parsers/trajectory.py`
- `src/quantumvitas/drivers/pyscf/parsers/__init__.py`
- `src/quantumvitas/drivers/pyscf/parsers/trajectory.py`
- `tests/drivers/qe/test_qe_convergence_parser.py`
- `tests/drivers/abinit/test_abinit_convergence_parser.py`
- `tests/drivers/siesta/test_siesta_convergence_parser.py`
- `tests/drivers/cp2k/test_cp2k_convergence_parser.py`
- `tests/core/analysis/test_trajectory_transforms.py`
- `tests/drivers/qe/test_qe_neb_trajectory_parser.py`
- `tests/drivers/psi4/test_psi4_trajectory_parser.py`
- `tests/drivers/pyscf/test_pyscf_trajectory_parser.py`

### New Fixture Directories (3)
- `tests/data/analysis_qe_neb_trajectory/` (nh3.2.axsf, nh3.2.path)
- `tests/data/analysis_psi4_trajectory/` (output.dat)
- `tests/data/analysis_pyscf_trajectory/` (output.out)

### Modified Files (18)
- `src/quantumvitas/drivers/qe/driver.py` (ANALYSIS_CAPABILITIES, SUPPORTED_GEN_STEPS)
- `src/quantumvitas/drivers/qe/parsers/__init__.py` (convergence + neb_trajectory imports)
- `src/quantumvitas/drivers/qe/step_types.py` (qe_neb StepTypeSpec)
- `src/quantumvitas/drivers/abinit/driver.py` (md gen_step, capabilities)
- `src/quantumvitas/drivers/abinit/parsers/__init__.py` (convergence import)
- `src/quantumvitas/drivers/siesta/driver.py` (capabilities)
- `src/quantumvitas/drivers/siesta/parsers/__init__.py` (convergence import)
- `src/quantumvitas/drivers/cp2k/driver.py` (capabilities)
- `src/quantumvitas/drivers/cp2k/parsers/__init__.py` (convergence import)
- `src/quantumvitas/drivers/xtb/driver.py` (md gen_step, capabilities)
- `src/quantumvitas/drivers/psi4/driver.py` (ANALYSIS_CAPABILITIES)
- `src/quantumvitas/drivers/psi4/__init__.py` (parsers import)
- `src/quantumvitas/drivers/pyscf/driver.py` (ANALYSIS_CAPABILITIES)
- `src/quantumvitas/drivers/pyscf/__init__.py` (parsers import)
- `src/quantumvitas/core/analysis/transforms/__init__.py` (6 new exports)
- `src/quantumvitas/workflow/gen_steps.py` (neb gen step)
- `tests/gates/test_analysis_invariants.py` (new gate tests)
- `tests/daemon/test_si_bands_golden_daemon.py` (convergence result handling)

## Verification

```
4980 passed, 0 failed, 19 skipped
```
