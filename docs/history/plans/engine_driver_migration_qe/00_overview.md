# QE Driver Migration Plan: Executive Overview

> **Status**: Migration Plan
> **Target**: Quantum ESPRESSO (QE) engine migration to DriverBundle architecture
> **Prerequisite**: All other engines (VASP, ORCA, PySCF, LAMMPS, CP2K, W90) already migrated

## Summary

This document outlines the comprehensive plan to migrate Quantum ESPRESSO (QE) from its current "shim" implementation to a proper DriverBundle under `src/qmatsuite/drivers/qe/`. QE is the **final and most complex** engine migration due to its historical coupling across the kernel.

## Current State

QE currently exists as:
1. **qe_shim** - A minimal driver shim at `src/qmatsuite/drivers/qe_shim/__init__.py` that wraps legacy code
2. **Scattered QE code** - 54+ files containing QE-specific logic across the codebase
3. **Legacy implementations** - Full QE engine code in `src/qmatsuite/core/engines/qe*.py` (9 files, ~3000+ lines)

## End State

After migration:
1. **All QE code** under `src/qmatsuite/drivers/qe/` (DriverBundle)
2. **Kernel contains NO QE special-casing** (engine-agnostic)
3. **DriverRegistry-based dispatch** for all QE operations
4. **QE shim deleted** (replaced by proper driver bundle)

## Key Challenges

### 1. Deep Kernel Coupling
- `step.py` has `engine: str = "qe"` as DEFAULT
- `runner.py` has QE fallbacks and defaults
- `calc_identity.py` has special W90 → QE mapping
- `workflow/registry.py` has ~25 QE step types hardcoded

### 2. QE-Only Subsystems
- **IR Backend** - Only QE has `ir/backends/qe/` mapping
- **Pseudo handling** - `core/pseudo.py` is QE-centric
- **Installation detection** - `core/engines/qe_installation.py` with shell config parsing
- **Two-state resolver** - `core/engines/qe_resolver.py` for bin directory resolution

### 3. W90 Integration Complexity
- W90 step types (`w90_preproc`, `w90_run`) currently have `engine="qe"` for backward compatibility
- `pw2wannier90` is a QE step but bridges to W90
- W90 has its own driver but depends on QE toolchain

### 4. I/O Layer Coupling
- `io/model.py` defines QEModule, QECardType, QEInput, etc.
- `io/parser/qe_parser.py` and `io/generator/qe_generator.py`
- Used by IR layer and step compilation

## Migration Strategy

### Phase 1: Foundation (PR 1-2)
- Create `drivers/qe/` bundle structure
- Move QE step type specs to driver bundle
- Preserve backward-compatible imports

### Phase 2: Engine Migration (PR 3-4)
- Move `core/engines/qe*.py` → `drivers/qe/engine/`
- Move handlers and recipes → `drivers/qe/`
- Update DriverRegistry to use new locations

### Phase 3: I/O Layer (PR 5-6)
- Move QE I/O models → `drivers/qe/io/`
- Move parsers and generators
- Maintain public API via re-exports

### Phase 4: IR Backend (PR 7)
- Move `ir/backends/qe/` → `drivers/qe/ir/`
- Update IR integration to use driver bundle

### Phase 5: Kernel Cleanup (PR 8-9)
- Remove QE default from `step.py`
- Remove QE fallbacks from runner
- Generalize pseudo handling
- Remove QE shim

### Phase 6: Finalization (PR 10)
- Delete legacy code
- Update all imports
- Final validation

## File Count Summary

| Category | Files | Lines (est.) |
|----------|-------|--------------|
| Core Engines (qe*.py) | 9 | ~3,200 |
| Driver Shim | 1 | 194 |
| Execution (handler/recipe) | 2 | ~400 |
| I/O Layer | 4 | ~800 |
| IR Backend | 1 | 463 |
| Parsers | 2 | ~350 |
| Registry/Workflow | 1 | ~300 (QE portion) |
| Misc (pseudo, settings, etc.) | 10+ | ~500 |
| **Total** | **30+** | **~6,000+** |

## Risk Assessment

### High Risk
- Kernel default removal (`engine="qe"`) affects ALL existing calculations
- W90 integration changes could break Wannier90 workflows
- IR backend move could break preset application

### Medium Risk
- Pseudo handling changes affect all QE calculations
- I/O layer moves require careful re-export maintenance
- Test coverage gaps in QE-specific paths

### Low Risk
- Engine file moves (well-isolated)
- Parser/generator moves (stable interfaces)
- Recipe/handler moves (already behind registry)

## Success Criteria

1. **All QE tests pass** - Integration tests, unit tests, example calculations
2. **No kernel QE references** - grep for `"qe"` in kernel returns zero
3. **Existing calculations work** - Legacy projects run without modification
4. **W90 workflows work** - Wannier90 integration unbroken
5. **DriverRegistry dispatch** - All QE operations via registry, no direct imports

## Timeline Estimate

- **PRs 1-2**: Foundation - Medium complexity
- **PRs 3-4**: Engine Migration - High complexity
- **PRs 5-6**: I/O Layer - Medium complexity
- **PR 7**: IR Backend - Low complexity
- **PRs 8-9**: Kernel Cleanup - High complexity (most breaking)
- **PR 10**: Finalization - Low complexity

## Related Documents

- [01_qe_code_inventory.md](./01_qe_code_inventory.md) - Complete file inventory
- [02_qe_kernel_touchpoints_audit.md](./02_qe_kernel_touchpoints_audit.md) - Kernel coupling analysis
- [03_qe_driver_bundle_spec.md](./03_qe_driver_bundle_spec.md) - Target architecture
- [04_pr_breakdown_and_checklists.md](./04_pr_breakdown_and_checklists.md) - PR-by-PR checklists
- [05_test_gates_and_ci_strategy_qe.md](./05_test_gates_and_ci_strategy_qe.md) - Test strategy
- [06_open_questions_qe.md](./06_open_questions_qe.md) - Unresolved decisions
