# Stop Conditions Document

## Overview

This document lists conditions under which the patch implementation should STOP and wait for user guidance.

---

## Condition 1: Core Skeleton Changes Required

### Evidence Required:
- If fixing integration tests requires changes to core files beyond:
  - Test files (`tests/`)
  - LAMMPS-specific files (`src/qmatsuite/engine/lammps_*.py`)
  - Step type registry (`src/qmatsuite/workflow/registry.py`)

### Current Status: ✅ NOT TRIGGERED

The patch plan only modifies:
- Test files (expected)
- Step type registry (minimal, additive `lammps_` prefix)
- LAMMPS engine files (renaming only)

No core skeleton changes are required.

---

## Condition 2: Service API Cannot Create LAMMPS Resources

### Evidence Required:
- If `QMSService.init_calculation()` or `QMSService.init_step()` cannot be used for LAMMPS
- If `engine_family="lammps"` is rejected by existing validators
- If step type `"relax"` cannot be resolved to `lammps_relax` without core changes

### Current Status: ✅ NOT TRIGGERED

Evidence from codebase review:
```python
# src/qmatsuite/workflow/registry.py
# After adding lammps_relax, GEN→SPEC resolution will work:
# "relax" → engine="lammps" → "lammps_relax"

# QMSService.init_step() already supports:
step_resolved = QMSService.init_step(
    project_root=project_root,
    calculation_selector=calc_id,
    step_type="relax",  # This will resolve to lammps_relax if engine_family=lammps
)
```

The existing Service API pattern from `test_pyscf_phase3c.py` and `test_vasp_project_e2e.py` works for LAMMPS.

---

## Condition 3: LAMMPS Binary/CI Installation Unstable

### Evidence Required:
- CI fails to install LAMMPS consistently
- Local LAMMPS binary produces different output across runs
- LAMMPS version differences cause parser failures

### Current Status: ✅ NOT TRIGGERED

Evidence:
- Local LAMMPS verified: `/opt/homebrew/opt/lammps/bin/lmp_serial`
- All 25 unit tests pass locally
- CI workflow uses standard `brew install lammps` / `apt install lammps`

### Mitigation (if triggered):
1. Pin LAMMPS version in CI: `brew install lammps@2024.1.10`
2. Add version detection in parser
3. Use mock/fake LAMMPS for unit tests (like `fake_vasp`)

---

## Condition 4: GEN→SPEC Resolution Ambiguity

### Evidence Required:
- If `step_type="relax"` could resolve to multiple LAMMPS step types
- If adding `lammps_relax` causes ambiguity with existing `qe_relax`, `orca_relax`, etc.

### Current Status: ✅ NOT TRIGGERED

Evidence:
- The registry design ensures GEN→SPEC is 0-1 per engine family
- Test `test_no_duplicate_engine_public_type_combinations` verifies this
- Each engine has at most one step type per GEN type

---

## Condition 5: `restart_from` Cannot Be Parameter-Only

### Evidence Required:
- If LAMMPS restart logic requires a separate step type
- If the existing `restart_from` parameter pattern cannot express LAMMPS restart semantics

### Current Status: ✅ NOT TRIGGERED

Evidence from `lammps_engine.py`:
```python
# The materialize_inputs already handles restart_from as parameter:
def materialize_inputs(self, step, working_dir, calculation):
    if step.parameters.get("restart_from"):
        # Resolve restart artifact from previous step
        # This works without lammps_restart step type
```

The parameter-based approach is already implemented and working.

---

## Summary

| Condition | Status | Action |
|-----------|--------|--------|
| Core skeleton changes | ✅ Not triggered | Proceed |
| Service API limitation | ✅ Not triggered | Proceed |
| CI/LAMMPS instability | ✅ Not triggered | Proceed |
| GEN→SPEC ambiguity | ✅ Not triggered | Proceed |
| restart_from limitation | ✅ Not triggered | Proceed |

**Conclusion: All stop conditions are NOT triggered. Proceed with patch plan.**

---

## Future Stop Conditions (for reference)

If any of these occur during implementation:

1. **Import cycles**: Adding `lammps_` prefix causes circular imports
   - Evidence: `ImportError` traceback
   - Stop and analyze dependency graph

2. **Test isolation failure**: LAMMPS tests pollute other tests
   - Evidence: Random test failures when run together
   - Stop and add proper cleanup/isolation

3. **Performance regression**: Runner becomes slow with LAMMPS
   - Evidence: >10x slowdown in existing QE tests
   - Stop and profile

These are not currently triggered based on the patch plan analysis.

