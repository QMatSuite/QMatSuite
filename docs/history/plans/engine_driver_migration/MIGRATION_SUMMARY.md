# Engine Driver Migration Plan - Summary

All migration plan documents have been written. Here's the final summary:

---

## Summary: Engine Driver Migration Plan

### Files Created in docs/plan/engine_driver_migration/

**File: 00_spec_delta_from_engine_driver_arch.md**  
Purpose: Changes/clarifications from original design docs

────────────────────────────────────────

**File: 01_registry_and_dispatch_contract.md**  
Purpose: Exact routing contract and exception handling

────────────────────────────────────────

**File: 02_driver_bundle_minimum_surface.md**  
Purpose: MUST/SHOULD/PLUGIN interface definitions

────────────────────────────────────────

**File: 03_test_gates_and_ci_strategy.md**  
Purpose: Test gates (0-4) and CI workflow

────────────────────────────────────────

**File: 10_prereq_pr_remove_fallback_and_add_hard_errors.md**  
Purpose: PR 1: Remove silent QE fallbacks

────────────────────────────────────────

**File: 11_prereq_pr_registry_scaffold_and_kernel_touchpoints_refactor.md**  
Purpose: PR 2: Create DriverRegistry

────────────────────────────────────────

**File: 20_vasp_plan.md**  
Purpose: VASP driver migration

────────────────────────────────────────

**File: 21_orca_plan.md**  
Purpose: ORCA driver migration

────────────────────────────────────────

**File: 22_pyscf_plan.md**  
Purpose: PySCF driver migration

────────────────────────────────────────

**File: 23_lammps_plan.md**  
Purpose: LAMMPS driver migration

────────────────────────────────────────

**File: 24_cp2k_plan.md**  
Purpose: CP2K driver migration

────────────────────────────────────────

**File: 25_wannier90_plan.md**  
Purpose: Wannier90 driver migration

---

## Recommended PR Execution Order

```
┌───────┬───────────┬─────────────────────────────────────────────────┐
│ Order │    PR     │                   Description                   │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 1     │ PR 1      │ Remove fallbacks and add hard errors            │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 2     │ PR 2      │ Registry scaffold and kernel refactor           │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 3     │ ORCA      │ First engine (validates chain pattern)          │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 4     │ PySCF     │ Second engine (similar to ORCA)                 │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 5     │ VASP      │ Third engine (per-step pattern, CHGCAR/WAVECAR) │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 6     │ LAMMPS    │ Fourth engine (restart logic)                    │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 7     │ CP2K      │ Fifth engine (follows LAMMPS pattern)           │
├───────┼───────────┼─────────────────────────────────────────────────┤
│ 8     │ Wannier90 │ Last engine (cross-engine dependency)           │
└───────┴───────────┴─────────────────────────────────────────────────┘
```

QE excluded - will be migrated in a separate dedicated effort.

---

## Complexity Rating per Engine

```
┌───────────┬────────────┬──────────────────────────────────────────┐
│  Engine   │ Complexity │               Biggest Risk               │
├───────────┼────────────┼──────────────────────────────────────────┤
│ ORCA      │ S (Low)    │ Chain handler pattern                    │
├───────────┼────────────┼──────────────────────────────────────────┤
│ PySCF     │ S (Low)    │ Python-native execution                  │
├───────────┼────────────┼──────────────────────────────────────────┤
│ VASP      │ M (Medium) │ CHGCAR/WAVECAR staging, workdir cleanup  │
├───────────┼────────────┼──────────────────────────────────────────┤
│ LAMMPS    │ M (Medium) │ Restart file handling, MD continuation   │
├───────────┼────────────┼──────────────────────────────────────────┤
│ CP2K      │ M (Medium) │ Hierarchical input format                │
├───────────┼────────────┼──────────────────────────────────────────┤
│ Wannier90 │ L (High)   │ Cross-engine artifact dependency with QE │
└───────────┴────────────┴──────────────────────────────────────────┘
```

---

## Critical Vulnerability Fixed

**Location**: `src/qmatsuite/core/calc_identity.py` lines 96-108

**Issue**: Silent QE fallback for unknown step types

```python
else:
    families.add("qe")  # DANGEROUS - removed in PR 1
```

**Impact**: Unknown/typo step types silently routed to QE instead of failing

---

## Key Technical Decisions

1. QE excluded from this migration round (separate effort later)
2. Protocol + BaseEngineDriver pattern for flexibility
3. Eager driver loading at import time
4. String set for capabilities (extensible, no schema changes)
5. One minor version backward compatibility with deprecation warnings
6. w90_preproc stays with QE until QE is migrated

