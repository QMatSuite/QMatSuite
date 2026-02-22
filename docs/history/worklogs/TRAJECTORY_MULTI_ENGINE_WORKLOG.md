# Trajectory Multi-Engine Implementation Worklog

## Summary

Implemented trajectory parsing across 10 engines (VASP was already done, 1 rewritten, 8 new). All parsers use the `EvidenceBundle` API, produce `Trajectory` objects with `Frame` dataclass instances, and follow the 7-test template. All fixtures are from real engine runs.

**Baseline:** 4767 passed, 20 skipped
**Final:** 4875 passed, 19 skipped, 0 failures
**Delta:** +108 new tests

## Engine Coverage Matrix

| Engine | Parser | Fixture | Tests | Relax | MD | Notes |
|--------|--------|---------|-------|-------|----|-------|
| VASP | pre-existing | pre-existing | 14 | Y | Y | Template reference |
| QE | rewritten | new (pw.x 7.5) | 12 | Y | Y | EvidenceBundle + MD parser |
| CP2K | new | new (cp2k.psmp) | 10 | Y | - | Multi-file merge |
| LAMMPS | new | new (lmp_serial) | 11 | - | Y | Column-adaptive dump |
| ABINIT | new | new (abinit 10.4) | 9 | Y | - | _HIST.nc via scipy |
| Siesta | new | copied from .tmp/ | 9 | Y | - | ANI + MDE merge |
| xTB | new | copied from .tmp/ | 9 | Y | - | Multi-frame XYZ |
| GPAW | new | new (gpaw+ase) | 9 | Y | - | ASE .traj reader |
| ORCA | new | new (orca 6.1.1) | 9 | Y | - | _trj.xyz + energy |
| Gaussian | new | copied from .tmp/ | 9 | Y | - | Standard orientation |

## Files Created

### New parser source files (8)
- `src/qmatsuite/drivers/cp2k/parsers/trajectory.py`
- `src/qmatsuite/drivers/lammps/parsers/trajectory.py`
- `src/qmatsuite/drivers/abinit/parsers/trajectory.py`
- `src/qmatsuite/drivers/siesta/parsers/trajectory.py`
- `src/qmatsuite/drivers/xtb/parsers/trajectory.py`
- `src/qmatsuite/drivers/gpaw/parsers/trajectory.py`
- `src/qmatsuite/drivers/orca/parsers/trajectory.py`
- `src/qmatsuite/drivers/gaussian/parsers/trajectory.py`

### New test files (9)
- `tests/drivers/qe/test_qe_trajectory_parser.py` (12 tests)
- `tests/drivers/cp2k/test_cp2k_trajectory_parser.py` (10 tests)
- `tests/drivers/lammps/test_lammps_trajectory_parser.py` (11 tests)
- `tests/drivers/abinit/test_abinit_trajectory_parser.py` (9 tests)
- `tests/drivers/siesta/test_siesta_trajectory_parser.py` (9 tests)
- `tests/drivers/xtb/test_xtb_trajectory_parser.py` (9 tests)
- `tests/drivers/gpaw/test_gpaw_trajectory_parser.py` (9 tests)
- `tests/drivers/orca/test_orca_trajectory_parser.py` (9 tests)
- `tests/drivers/gaussian/test_gaussian_trajectory_parser.py` (9 tests)

### New fixture directories (9)
- `tests/data/analysis_qe_trajectory/` (si.relax.out, si.md.out)
- `tests/data/analysis_cp2k_trajectory/` (pos, frc, cell, ener, out)
- `tests/data/analysis_lammps_trajectory/` (dump.lammpstrj, log.lammps)
- `tests/data/analysis_abinit_trajectory/` (_HIST.nc, .abo)
- `tests/data/analysis_siesta_trajectory/` (.ANI, .MDE, .out)
- `tests/data/analysis_xtb_trajectory/` (xtbopt.log, xtb.out, xtb_md.trj)
- `tests/data/analysis_gpaw_trajectory/` (relax.traj)
- `tests/data/analysis_orca_trajectory/` (water_opt.out, water_opt_trj.xyz)
- `tests/data/analysis_gaussian_trajectory/` (water_opt.log)

## Files Modified

### Rewritten
- `src/qmatsuite/drivers/qe/parsers/trajectory.py` — Full rewrite: EvidenceBundle API, `_parse_relax_output()` + `_parse_md_output()`, position unit handling

### ANALYSIS_CAPABILITIES added (9 driver.py files)
- `src/qmatsuite/drivers/{qe,cp2k,lammps,abinit,siesta,xtb,gpaw,orca,gaussian}/driver.py`

### Parser registration wired (8 parsers/__init__.py files)
- `src/qmatsuite/drivers/{cp2k,lammps,abinit,siesta,xtb,gpaw,orca,gaussian}/parsers/__init__.py`

### Gate tests added
- `tests/gates/test_analysis_invariants.py` — `test_trajectory_parser_matrix` (10 engines) + `test_trajectory_engine_has_analysis_capabilities` (10 engines) = +20 gate tests

### Renamed (basename collision fix)
- `tests/unit/test_qe_trajectory_parser.py` → `tests/unit/test_qe_trajectory_units.py`

## Key Design Decisions

1. **All fixtures from real engine runs** — no synthesized data. Used actual binaries for QE, CP2K, LAMMPS, ABINIT, GPAW, ORCA; copied existing research data for Siesta, xTB, Gaussian.

2. **Unit conversion at parse time** — all energies in eV, positions in Angstrom, forces in eV/A, pressure in GPa.

3. **EvidenceBundle API** — all parsers use `parse(evidence: EvidenceBundle) -> Trajectory`, consistent with VASP template.

4. **Multi-file merge for CP2K** — positions, forces, cell, energy from separate output files, aligned by step index.

5. **Column-adaptive LAMMPS** — reads `ITEM: ATOMS` header to discover available columns dynamically.

6. **ABINIT _HIST.nc primary** — uses scipy.io.netcdf_file for binary NetCDF; text .abo as fallback.

7. **GPAW via ASE** — reads binary .traj files using ase.io.read, which is already a project dependency.

## Verification Commands

```bash
# Full suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Per-engine
python -m pytest tests/drivers/<engine>/test_<engine>_trajectory_parser.py -v --tb=short

# Gate tests
python -m pytest tests/gates/test_analysis_invariants.py -v -k trajectory

# Registration check
python -c "
import qmatsuite.drivers
from qmatsuite.parsers.registry import _PARSERS
for e in ['qe','vasp','abinit','siesta','cp2k','gpaw','lammps','xtb','orca','gaussian']:
    p = _PARSERS.get((e, 'trajectory'))
    print(f'  {e}/trajectory: {p.__name__ if p else \"MISSING\"}')"
```
