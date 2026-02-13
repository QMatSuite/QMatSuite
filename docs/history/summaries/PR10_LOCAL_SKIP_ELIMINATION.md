# PR10 Local Skip Elimination Log

## Goal
Eliminate all engine-related skips on local machine. Engines are installed and must be discovered.

## Engine Locations
- VASP: ~/QMatSuite/.qmatsuite/engines/vasp/*/vasp_std
- PySCF: in .venv
- CP2K + LAMMPS: brew (on PATH)
- ORCA: TBD

---

## Engine 1: PySCF

### Status: COMPLETE ✓

### Tests Skipping
- `tests/integration/test_pyscf_phase3c.py` - 5 tests (module-level pytestmark skip)
- `tests/integration/test_pyscf_relax_real.py` - 2 tests (module-level pytestmark skip)

### Root Cause
Module-level `pytestmark = [pytest.mark.skip(reason="Pending migration from compat to domain API")]`
plus undefined functions `init_step`, `configure_step`, `run_step` (not imported/migrated).

### Fix Applied
1. Removed module-level skip markers
2. Replaced `init_step(` with `QVService.init_step(`
3. Replaced `configure_step(...)` with domain accessor pattern:
   ```python
   svc = QVService(project_root)
   svc.calculation.update_step_params(calc_id, step_id, {"parameters": {...}})
   ```
4. Replaced `run_step(` with `QVService.run_step(`

### Proof
```
python -m pytest tests/ -k "pyscf" --tb=short -n auto --dist=loadfile
====================== 115 passed, 14 warnings in 23.83s =======================
```

---

## Engine 2: ORCA

### Status: COMPLETE ✓

### Tests Skipping
- `tests/integration/orca/test_orca_project_level.py` - 6 tests (module-level pytestmark skip)
- `tests/integration/test_orca_relax_real.py` - 3 tests (module-level pytestmark skip)

### Root Cause
Same pattern - module-level skip markers + undefined `init_step`/`configure_step`/`run_step` functions.

### Fix Applied
1. Removed module-level skip markers
2. Replaced `init_step(` with `QVService.init_step(`
3. Replaced `configure_step(...)` with domain accessor pattern
4. Replaced `run_step(` with `QVService.run_step(`

### Proof
```
python -m pytest tests/ -k "orca" --tb=short -n auto --dist=loadfile
====================== 202 passed, 28 warnings in 14.37s =======================
```

---

## Engine 3: CP2K

### Status: COMPLETE ✓

### Tests Skipping
- `tests/integration/test_cp2k_integration.py` - 3 tests (module-level pytestmark skip)

### Root Cause
Same pattern - module-level skip markers + undefined `init_step`/`configure_step` functions.

### Fix Applied
1. Removed module-level skip markers (8 occurrences)
2. Replaced `init_step(` with `QVService.init_step(`
3. Replaced `configure_step(...)` with domain accessor pattern

### Proof
```
python -m pytest tests/integration/test_cp2k_integration.py -v --tb=short
====================== 3 passed =======================
```

---

## Engine 4: LAMMPS

### Status: COMPLETE ✓

### Tests Skipping
- `tests/integration/test_lammps_long_smoke.py` - 4 tests (module-level pytestmark skip)
- `tests/integration/test_lammps_restart_parallel.py` - 3 tests (module-level pytestmark skip)

### Root Cause
Same pattern - module-level skip markers + undefined `init_step`/`configure_step` functions.

### Fix Applied
1. Removed module-level skip markers (9 occurrences per file)
2. Replaced `init_step(` with `QVService.init_step(`
3. Added helper function `configure_step()` that wraps domain accessor:
   ```python
   def configure_step(project_root, calculation_selector, step_selector, parameters):
       svc = QVService(project_root)
       svc.calculation.update_step_params(
           calc_selector=calculation_selector,
           step_selector=step_selector,
           params={"parameters": parameters},
       )
   ```

### Proof
```
python -m pytest tests/integration/test_lammps_long_smoke.py tests/integration/test_lammps_restart_parallel.py -v --tb=short
====================== 7 passed =======================
```

---

## Engine 5: VASP

### Status: COMPLETE ✓

### Tests Skipping
- `tests/integration/vasp/test_vasp_project_e2e.py` - 4 tests (module-level pytestmark skip)

### Root Cause
Same pattern - module-level skip markers + undefined `init_step`/`run_step` functions.

### Fix Applied
1. Removed module-level skip markers (3 occurrences)
2. Replaced `init_step(` with `QVService.init_step(`
3. Replaced `run_step(` with `QVService.run_step(`

### Proof
```
python -m pytest tests/integration/vasp/test_vasp_project_e2e.py -v --tb=short
====================== 4 passed =======================
```

---

## Summary

All engine-related skips have been eliminated:
- **PySCF**: 7 tests unskipped
- **ORCA**: 9 tests unskipped
- **CP2K**: 3 tests unskipped
- **LAMMPS**: 7 tests unskipped
- **VASP**: 4 tests unskipped

**Total: 30 engine tests unskipped and now passing**
