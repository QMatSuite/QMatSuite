# Authorship Path (Path B) — Closeout Report

## Summary

All 52 Level-2 demo snapshots can now be compiled to fine-grained AuthoringOps,
replayed through QVService, and re-snapshotted to semantic equivalence with
the original. Both Path A (load snapshot) and Path B (authoring from scratch)
are working.

## Final Test Results

```
5615 passed, 0 failed, 31 skipped
```

### Breakdown

| Suite | Passed | Notes |
|-------|--------|-------|
| Roundtrip B (52 demos x 3 tests) | 156 | compile, no-bulk-ops, roundtrip equivalence |
| demo_store unit tests | 41 | authoring_ops, replay, patch_semantics |
| Gate tests | 590 | Including new cross-engine defaults gate |
| Full regression | 5615 | Zero failures |

## Phases Completed

### Phase 0A: Fix Second-Truth Daemon Handlers
- `_handle_set_engine_family` and `_handle_apply_presets_to_calculation` now delegate to `QVService` methods
- Daemon handlers are thin wrappers (~5 lines each)
- Gate test: `tests/gates/test_daemon_no_yaml_write.py`

### Phase 0B: Fix Default Resolution — Spec-Keyed Defaults
- `DEFAULT_STEP_PARAMS` keys renamed from GEN to SPEC (`"scf"` -> `"qe_scf"`)
- `get_defaults()` accepts `step_type_spec`, no cross-engine fallback
- Non-QE engines get empty defaults (no QE namelist leakage)
- Gate test: `tests/gates/test_no_cross_engine_defaults.py`

### Phase 0C: Hard-Ban add_step Fallback
- `registry.get(step_type_gen)` generic fallback removed from `add_step()`
- Replaced with `DriverRegistry.resolve_companion_step()` for companion engines
- Unknown step types raise hard errors

### Phase 1: AuthoringOps IR + Replay Engine
- 8 op types: InitProject, ImportStructure, CreateCalculation, AddStep, SetField, UnsetField, ReplaceMap, ConfigureSpeciesMap
- `authoring_ops.py` (137 lines): frozen dataclasses, serialization, `is_bulk_op()` gate
- `replay.py` (149 lines): dispatches ops through QVService (no direct YAML writes)
- `test_patch_semantics.py` (112 lines): locks yamldoc set/delete/apply_patch behavior

### Phase 2: Compiler + Roundtrip B Harness
- `compiler.py` (249 lines): `compile_snapshot()` -> fine-grained ops with default reconciliation
- `roundtrip.py` (249 lines): canonicalization + equivalence verification
- `test_roundtrip_b.py` (95 lines): parametrized over all 52 demos

## Bugs Found & Fixed During Implementation

### 1. StepDoc Normalization Cross-Engine Leak
`StepDoc._normalize_sections()` converted `electrons` -> `ELECTRONS` for ALL engines,
not just QE. This corrupted QMCPACK steps where `ELECTRONS` is a valid parameter section
with different semantics than QE's `ELECTRONS` namelist.

**Fix**: Conditioned normalization on `step_type_spec.startswith("qe_")`.

### 2. Missing `lammps_minimize` in Static Registry
The LAMMPS driver registered `lammps_minimize` via `get_step_type_specs()` but
the static `_STEP_TYPES` registry in `workflow/registry.py` lacked the entry.
This caused `ValidationError` during replay for LAMMPS minimize demos.

**Fix**: Added `lammps_minimize` StepTypeSpec to `_STEP_TYPES`.

### 3. Managed Keys Not Stripped Recursively
`_strip_managed_keys` only stripped at one nesting level. VASP's `SYSTEM` managed key
could appear at top-level (flat VASP params) or deeply nested (e.g.,
`engine_params.vasp.incar.SYSTEM` in composite pipelines).

**Fix**: Made stripping fully recursive via `_strip_keys_recursive()`.

### 4. Empty Dict Residue After Stripping
After stripping managed keys, empty parent dicts remained (e.g., `parameters: {}`),
causing mismatches between demos (which have `parameters: {}`) and replayed
projects (which omit the key entirely).

**Fix**: Added `_strip_empty_dicts()` recursive cleaner to canonicalization.

### 5. Slug Mismatch Between Hand-Authored and Generated
Demo slugs were hand-authored (e.g., `ch4-scf--plus-frequency` with double-dash),
but `slugify()` generates different slugs (e.g., `ch4-scf-frequency`).

**Fix**: Compiler uses `slugify(name)` for all selectors; canonicalizer strips slugs
from all meta blocks via `_strip_slugs()`.

## Deliverable Files

### Source (784 lines new)

| File | Action | Lines |
|------|--------|-------|
| `src/quantumvitas/demo_store/authoring_ops.py` | NEW | 137 |
| `src/quantumvitas/demo_store/replay.py` | NEW | 149 |
| `src/quantumvitas/demo_store/compiler.py` | NEW | 249 |
| `src/quantumvitas/demo_store/roundtrip.py` | MODIFY | 249 |
| `src/quantumvitas/core/yamldoc.py` | MODIFY | ~10 lines changed |
| `src/quantumvitas/workflow/registry.py` | MODIFY | +12 lines |
| `src/quantumvitas/calculation/step_defaults.py` | MODIFY | key renames |
| `src/quantumvitas/workflow/step_factory.py` | MODIFY | +1 line |
| `src/quantumvitas/api/service.py` | MODIFY | +140 lines |
| `src/quantumvitas/daemon/server.py` | MODIFY | -130, +12 lines |

### Tests (454 lines new)

| File | Action | Lines |
|------|--------|-------|
| `tests/demo_store/test_authoring_ops.py` | NEW | 87 |
| `tests/demo_store/test_replay.py` | NEW | 160 |
| `tests/demo_store/test_patch_semantics.py` | NEW | 112 |
| `tests/integrity/authoring/test_roundtrip_b.py` | NEW | 95 |
| `tests/gates/test_daemon_no_yaml_write.py` | NEW | ~40 |
| `tests/gates/test_no_cross_engine_defaults.py` | NEW | ~40 |
| `tests/unit/test_yamldoc.py` | MODIFY | 3 tests updated |

## Acceptance Criteria — All Met

1. All 52 demos compile to ops without errors
2. Zero bulk ops in any compiled ops list
3. All 52 demos complete Roundtrip B (semantic equivalence)
4. All existing tests remain green (5615 passed)
5. Demo content unchanged (no modifications to `resources/demo_projects/*.yml`)
6. Canonicalizer allowlist: minimal additions (pseudo-related + slug + empty dict)
7. No `skip_defaults` flag anywhere
8. Gate test: VASP/ORCA/LAMMPS steps have zero QE namelist keys
9. No `registry.get(step_type_gen)` fallback in `add_step`
