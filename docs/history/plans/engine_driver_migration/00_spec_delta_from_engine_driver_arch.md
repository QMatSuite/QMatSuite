# Spec Delta from engine_driver_arch

**Version**: 1.0
**Date**: 2026-01-20
**Status**: IMPLEMENTATION SPECIFICATION

This document summarizes what is **changed, clarified, or resolved** compared to the original design docs in `docs/plan/engine_driver_arch/`.

---

## 1. Scope Change: QE Excluded

**Original spec**: Migrate all 7 engines (QE, VASP, ORCA, PySCF, LAMMPS, CP2K, W90)

**This round**: Migrate 6 engines only:
- VASP
- ORCA
- PySCF
- LAMMPS
- CP2K
- Wannier90

**QE migration is explicitly deferred** to a separate dedicated effort. Rationale:
- QE is the oldest engine with deepest kernel integration
- QE is the fallback target for unknown types (removing fallback is prereq)
- QE uses unique shared-outdir model requiring special handling
- Migrating QE last allows pattern validation with simpler engines

---

## 2. Resolved Open Questions

### From `05_open_questions.md`:

| Question | Resolution | Rationale |
|----------|------------|-----------|
| **Q2.1 Driver package location** | `src/qmatsuite/drivers/` | Clean separation, signals architectural change |
| **Q2.2 Protocol vs ABC** | Protocol with optional BaseDriver class | Flexibility for third-party; base class provides defaults |
| **Q3.2 Driver loading** | Eager (at import time) | Simple, catches errors early, matches current codebase |
| **Q2.3 Capability format** | String set `set[str]` | Extensible, no dataclass changes for new capabilities |
| **Q3.1 Backward compat duration** | 1 minor version with deprecation warnings | Balance between user migration time and code cleanliness |
| **Q9 Driver namespace** | `qmatsuite.drivers.*` | Confirmed |

### Deferred to QE Migration:

| Question | Reason |
|----------|--------|
| **Q2.5 Shared outdir model** | QE-specific; handle when migrating QE |
| **Q2.4 W90/QE dependency** | Artifact-based approach confirmed, but full implementation needs QE driver |

---

## 3. Clarifications to Original Spec

### 3.1 From `01_engine_code_inventory.md`

**Clarification**: The inventory correctly identifies kernel-embedded code. However:

- `calc_identity.py` lines 78-116: The function `_infer_engine_family_from_machine_types()` is the actual location (not `determine_engine_family` which doesn't exist)
- Handler line numbers in `handlers.py` verified:
  - `qe_step_handler`: line 140 (KEEP - QE not migrating)
  - `vasp_step_handler`: line 294
  - `lammps_step_handler`: line 459
  - `pyscf_chain_handler`: line 757
  - `orca_chain_handler`: line 887
  - `cp2k_step_handler`: line 1097
  - `create_handler_map`: line 1312

### 3.2 From `02_kernel_touchpoints_audit.md`

**Clarification**: The CRITICAL vulnerability is confirmed at:
- File: `src/qmatsuite/core/calc_identity.py`
- Function: `_infer_engine_family_from_machine_types()`
- Lines: 96-108
- Exact dangerous code:
```python
else:
    # Unknown prefix - could be legacy step type
    # Assume QE for backward compatibility
    families.add("qe")
```

**Additional touchpoints identified**:
- `src/qmatsuite/workflow/generalized_steps.py` line 368-379: `startswith("pyscf_")` and `startswith("orca_")` patterns
- `src/qmatsuite/calculation/calculation.py` lines 339, 455: `.get("engine", "qe")` fallbacks

### 3.3 From `03_driver_model_spec.md`

**Adopted with modifications**:
- MUST/SHOULD/PLUGIN tiers: ADOPTED as-is
- `StepTypeSpec` dataclass: ADOPTED, already exists in `workflow/registry.py`
- `WorkdirPolicy` enum: NEW, needs to be created
- `BaseEngineDriver` class: NEW, provides SHOULD/PLUGIN defaults

### 3.4 From `04_migration_assessment.md`

**Modified migration order** (QE excluded):
1. ORCA (Low complexity, validates chain pattern)
2. PySCF (Low complexity, similar to ORCA)
3. VASP (Medium, representative per-step engine)
4. LAMMPS (Medium, has restart logic)
5. CP2K (Medium, follows LAMMPS pattern)
6. Wannier90 (High, cross-engine but QE migration not needed for basic W90)

---

## 4. Non-Goals for This Migration Round

The following are **explicitly out of scope**:

| Non-Goal | Reason |
|----------|--------|
| QE migration | Separate dedicated effort |
| Changing computation semantics | Refactor only, preserve behavior |
| New features | Migration only |
| Plugin system (pip-installable drivers) | Future consideration after API stabilizes |
| Remote execution changes | Out of scope |
| Output parsing improvements | Not part of routing refactor |
| New step types | Only migrate existing types |
| Performance optimizations | Focus on correctness |

---

## 5. Semantic Preservation Requirements

The migration **MUST preserve** these existing semantics:

| Semantic | Description | Verification |
|----------|-------------|--------------|
| SSOT rules | `step.yaml` is step SSOT, `calculation.yaml` is calc SSOT | Integration tests |
| Runtime materialize | GEN→SPEC happens at runtime, not statically | Unit tests |
| Manifest/done rules | Fingerprinting, done detection unchanged | Existing tests pass |
| Project-run mode | Project context execution unchanged | Integration tests |
| Standalone mode | Single-calc execution unchanged | Integration tests |
| Compat mode | Legacy calculation execution unchanged | Integration tests |
| Workdir policies | VASP cleans, LAMMPS/CP2K accumulate | Handler tests |
| Artifact resolution | CHGCAR/WAVECAR staging for VASP | VASP tests |
| Chain execution | ORCA/PySCF chain linking unchanged | Chain tests |

---

## 6. Files Created vs Modified

### 6.1 New Files to Create

| File | Purpose |
|------|---------|
| `src/qmatsuite/core/driver_protocol.py` | EngineDriver protocol + base class |
| `src/qmatsuite/core/driver_registry.py` | DriverRegistry singleton |
| `src/qmatsuite/core/driver_exceptions.py` | Exception classes |
| `src/qmatsuite/drivers/__init__.py` | Auto-discovery |
| `src/qmatsuite/drivers/vasp/` | VASP driver bundle |
| `src/qmatsuite/drivers/orca/` | ORCA driver bundle |
| `src/qmatsuite/drivers/pyscf/` | PySCF driver bundle |
| `src/qmatsuite/drivers/lammps/` | LAMMPS driver bundle |
| `src/qmatsuite/drivers/cp2k/` | CP2K driver bundle |
| `src/qmatsuite/drivers/w90/` | Wannier90 driver bundle |

### 6.2 Files to Modify (Kernel)

| File | Change |
|------|--------|
| `src/qmatsuite/core/calc_identity.py` | Remove QE fallback, use registry |
| `src/qmatsuite/execution/handlers.py` | Remove migrated handlers, add registry dispatch |
| `src/qmatsuite/execution/recipes.py` | Remove migrated recipes, add registry dispatch |
| `src/qmatsuite/workflow/generalized_steps.py` | Remove hardcoded MATERIALIZATION_MAP entries for migrated engines |
| `src/qmatsuite/calculation/structure_steps.py` | Remove hardcoded step type sets |
| `src/qmatsuite/calculation/step_done.py` | Remove hardcoded step type sets |
| `src/qmatsuite/calculation/calculation.py` | Remove `.get("engine", "qe")` fallbacks |

### 6.3 Files NOT Modified (Preserved for QE)

| File | Reason |
|------|--------|
| `src/qmatsuite/core/qe/` | QE-specific, not migrating |
| `src/qmatsuite/io/generator/qe_generator.py` | QE-specific |
| `src/qmatsuite/io/parser/qe_parser.py` | QE-specific |
| QE handler in `handlers.py` | Stays until QE migration |
| QERecipe in `recipes.py` | Stays until QE migration |

---

## 7. Reference Documents

| Document | Location | Status |
|----------|----------|--------|
| Engine Code Inventory | `docs/plan/engine_driver_arch/01_engine_code_inventory.md` | INPUT |
| Kernel Touchpoints | `docs/plan/engine_driver_arch/02_kernel_touchpoints_audit.md` | INPUT |
| Driver Model Spec | `docs/plan/engine_driver_arch/03_driver_model_spec.md` | ADOPTED with mods |
| Migration Assessment | `docs/plan/engine_driver_arch/04_migration_assessment.md` | ADOPTED with mods |
| Open Questions | `docs/plan/engine_driver_arch/05_open_questions.md` | RESOLVED (see above) |
| Constitution | `docs/spec/engine_integration/engine_integration_constitution.md` | NORMATIVE |
| Driver Protocol | `docs/spec/engine_integration/engine_driver_protocol.md` | NORMATIVE |
| Registry Spec | `docs/spec/engine_integration/engine_registry_and_dispatch.md` | NORMATIVE |
