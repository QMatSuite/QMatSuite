# Yambo Engine Integration Plan for QMatSuite

## Status: IMPLEMENTED

All Phase 1 items are complete. Tests green: 3234 passed, 21 skipped.

---

## Implementation Checklist

### Files Modified
- [x] `src/quantumvitas/workflow/gen_steps.py` — Added "setup", "gw", "bse", "optics" to GEN_STEPS
- [x] `src/quantumvitas/workflow/step_type_convert.py` — Added "yambo" to ENGINE_PREFIXES
- [x] `src/quantumvitas/workflow/registry.py` — Added yambo_setup/gw/bse/optics StepTypeSpecs + "yambo_" prefix
- [x] `src/quantumvitas/drivers/__init__.py` — Added `from quantumvitas.drivers import yambo`
- [x] `src/quantumvitas/core/engines/discovery.py` — Added yambo EngineProbe (binaries: yambo, p2y, ypp)
- [x] `tests/unit/test_engine_discovery.py` — Added "yambo" to expected engine set
- [x] `tests/unit/test_step_type_mapping.py` — Added "yambo_" to valid SPEC prefixes

### Files Created
- [x] `src/quantumvitas/drivers/yambo/__init__.py` — `DriverRegistry.register(YamboDriver())`
- [x] `src/quantumvitas/drivers/yambo/driver.py` — YamboDriver (PREFIX="yambo", 4 step types)
- [x] `src/quantumvitas/drivers/yambo/handler.py` — yambo_step_handler (setup/gw/bse/optics)
- [x] `src/quantumvitas/drivers/yambo/recipe.py` — YamboRecipe (ISOLATED workdir, SAVE symlink)
- [x] `src/quantumvitas/drivers/yambo/writer.py` — GWParams, BSEParams, IPOpticsParams + writers
- [x] `src/quantumvitas/drivers/yambo/parser.py` — QPResult, SpectrumResult, YamboReportInfo + parsers
- [x] `src/quantumvitas/drivers/yambo/artifact_resolver.py` — QE save dir + SAVE/ + GW QP DB resolution
- [x] `tests/integration/test_yambo_execution.py` — Raw execution + driver registration + parser + writer tests

### Gate Tests
- [x] `tests/gates/test_step_type_declared_sets.py` — yambo types in GEN_SET and SPEC_SET (via registry)
- [x] `tests/gates/test_supported_subset.py` — yambo gen steps ⊆ GenStepRegistry.GEN_STEPS (automatic)
- [x] `tests/gates/test_underscore_ban.py` — GEN steps have no underscores (automatic)

---

## 1. Overview

Yambo is a postprocessing engine for many-body perturbation theory (GW, BSE)
and TDDFT calculations. It consumes DFT wavefunctions from Quantum ESPRESSO
(via the `p2y` converter). It does NOT support VASP.

**Engine family**: `yambo`
**PREFIX**: `yambo`
**Recipe archetype**: Directory-state (QE-like, but with ISOLATED workdir policy)

---

## 2. Driver Bundle Structure

```
src/quantumvitas/drivers/yambo/
├── __init__.py              # DriverRegistry.register(YamboDriver())
├── driver.py                # YamboDriver class (PREFIX + SUPPORTED_GEN_STEPS)
├── handler.py               # yambo_step_handler function
├── recipe.py                # YamboRecipe class
├── writer.py                # Input file generation
├── parser.py                # Output file parsing
└── artifact_resolver.py     # Resolve SAVE/ artifacts from upstream QE steps
```

---

## 3. Step Types

### 3.1 Implemented Step Types

| GEN Step    | SPEC Step         | Executable | Description                    | Category     |
|-------------|-------------------|------------|--------------------------------|-------------|
| `setup`     | `yambo_setup`     | `yambo`    | p2y + init combined            | postprocess |
| `gw`        | `yambo_gw`        | `yambo`    | G0W0 quasiparticle energies    | postprocess |
| `bse`       | `yambo_bse`       | `yambo`    | BSE optical spectra            | postprocess |
| `optics`    | `yambo_optics`    | `yambo`    | IP/RPA/TDDFT optics           | postprocess |

### 3.2 SUPPORTED_GEN_STEPS

```python
SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
    "setup", "gw", "bse", "optics"
})
```

---

## 4. Recipe Archetype

### 4.1 WorkdirPolicy: ISOLATED

Each step gets its own working directory. The setup step creates
the SAVE/ database in `calc/raw/SAVE/`, and subsequent steps symlink to it.

### 4.2 Working Directory Layout

```
calc/raw/
├── SAVE/                    # Shared SAVE (created by setup, read by all)
├── <step_ulid_gw>/          # GW working directory
│   ├── gw.in                # Input file
│   ├── gw_run/              # GW databases (-J gw_run)
│   │   ├── ndb.QP
│   │   └── ndb.em1d*
│   └── gw_output/           # Text output (-C gw_output)
│       ├── o-gw_run.qp
│       └── r-gw_run_*
├── <step_ulid_bse>/         # BSE working directory
└── <step_ulid_optics>/      # Optics working directory
```

---

## 5. Handler Design

### 5.1 Setup Handler (p2y + init)

1. Find QE NSCF output (`prefix.save/` directory)
2. Run `p2y` inside `prefix.save/`
3. Copy `SAVE/` to `calc/raw/SAVE/`
4. Run bare `yambo` to initialize databases

### 5.2 GW/BSE/Optics Handler

1. Create workdir
2. Symlink `SAVE/` from `calc/raw/SAVE/`
3. Write input file via writer
4. Run `yambo -F <input> -J <jobname> -C <output_dir>`
5. Parse results

---

## 6. Testing

### Integration Tests (in `tests/integration/test_yambo_execution.py`)

**TestYamboRawExecution** (requires yambo + QE installed):
- `test_ip_optics_si`: Full QE→yambo IP optics pipeline
- `test_gw_si`: Full QE→yambo GW pipeline

**TestYamboDriverRegistration** (no binary required):
- 7 tests: registry lookup, step type specs, handler, materialization, discovery, recipe, workdir policy

**TestYamboParser**: Golden reference parsing tests
- GW QP (40 corrections), IP spectrum (100 points), BSE spectrum (200 points)

**TestYamboWriter**: Input file generation tests
- GW, BSE, IP optics input files

---

## 7. Implementation Issues and Solutions

### Issue 1: Two StepTypeSpec classes — driver protocol vs workflow registry

**Problem**: QMatSuite has two separate `StepTypeSpec` dataclasses:
- `quantumvitas.core.driver_protocol.StepTypeSpec` — used by engine drivers. Fields: `step_type_spec`, `engine`, `executable`, `description`, `category`, `supports_restart`, `mpi_aware`. **No `step_type_gen` field.**
- `quantumvitas.workflow.registry.StepTypeSpec` — used by the workflow system. Has `step_type_gen`, `requires_structure`, `produces_charge_density`, etc.

The gate test `test_step_type_declared_sets.py` builds GEN_SET and SPEC_SET from the workflow registry (`registry._types`), not from the driver protocol's StepTypeSpec. So registering step types only in the DriverRegistry (via `driver.get_step_type_specs()`) is insufficient — the gate test never sees the GEN types and fails with "undeclared SPEC type" violations.

All existing engines (QE, VASP, xTB, QMCPACK, etc.) have their step types registered in **both** the driver protocol's DriverRegistry AND the workflow registry's `_STEP_TYPES` dict.

**Solution**: Added yambo step types to `_STEP_TYPES` in `registry.py` with the workflow registry's StepTypeSpec (including `step_type_gen`). Also added `"yambo_"` to the `ENGINE_PREFIXES` tuple in `normalize_step_type_to_gen()`.

**Lesson**: When adding a new engine, you must register step types in TWO places:
1. `src/quantumvitas/drivers/<engine>/driver.py` → `get_step_type_specs()` (driver protocol StepTypeSpec)
2. `src/quantumvitas/workflow/registry.py` → `_STEP_TYPES` dict (workflow registry StepTypeSpec)

### Issue 2: Gate test passes in isolation, fails with all gates

**Problem**: `test_step_type_declared_sets.py` passed when run alone (3 passed) but failed when running all gates together (1 failed, 148 passed). The GEN_SET had 29 types but was missing "setup", "gw", "bse", "optics".

**Root cause**: The gate test's `_build_gen_set()` Source 2 calls `DriverRegistry.get_step_type_spec(step_type_spec)` and checks `hasattr(spec, 'step_type_gen')`. But the driver protocol's `StepTypeSpec` doesn't have `step_type_gen`, so this returns False for ALL drivers. When running in isolation, Source 2 of `_build_spec_set()` still added yambo types directly from `DriverRegistry.get_all_step_types()`. But when running all gates, Source 4 (cross-product of ALL gen types × ALL engines) dominated and produced 370 types — none of which included "yambo_setup" etc. because "setup" wasn't in the GEN_SET.

**Solution**: Same as Issue 1 — register in workflow registry. Once "setup", "gw", "bse", "optics" are in `_STEP_TYPES` with proper `step_type_gen`, the workflow registry Source 1 adds them to GEN_SET.

### Issue 3: Hardcoded engine lists in unit tests

**Problem**: Two unit test files had hardcoded lists of known engine prefixes:
- `tests/unit/test_engine_discovery.py` — `expected` set of engine names
- `tests/unit/test_step_type_mapping.py` — `valid_prefixes` tuple (in 2 locations)

These lists didn't include "yambo" / "yambo_", causing assertion failures.

**Solution**: Added "yambo" and "yambo_" to all three hardcoded lists.

**Lesson**: When adding a new engine, grep for existing engine name lists in tests and update them. These are discovery-related tests, not gate tests, so they can be updated.

### Issue 4: Engine discovery fails under pytest-xdist workers

**Problem**: `discover_engine("yambo")` (and QE) failed in pytest-xdist worker processes because `_find_project_root()` walks up from `Path.cwd()`, but xdist workers may have a different CWD than the repo root. The bundled binary search (`Tier 1: .qmatsuite/engines/`) couldn't find the repo's `.qmatsuite/` directory.

This caused two symptoms:
- `_find_yambo_bin("p2y")` raised AssertionError in the test fixture
- `test_engine_discovery` test failed (yambo "not found")

**Solution**: Pass explicit `project_root=_REPO_ROOT` to all `discover_engine()` and `is_engine_available()` calls in the test file, where `_REPO_ROOT = Path(__file__).resolve().parent.parent.parent`.

**Lesson**: Integration tests that rely on bundled engine discovery MUST pass `project_root` explicitly. The auto-detection from CWD is unreliable under xdist.

### Issue 5: Pseudopotential not found for raw execution tests

**Problem**: The raw execution tests (test_ip_optics_si, test_gw_si) require a Si norm-conserving pseudopotential (`Si_ONCV_PBE-1.2.upf`) for yambo compatibility. The test searched only two hardcoded paths, neither of which existed. The test skipped with "pseudopotential not found".

**Solution**: Replaced the hardcoded search with `_find_si_oncv_pseudo()` that:
1. Checks explicit paths first (exploration smoke test, resources/pseudo)
2. Searches recursively under `resources/pseudo/` and `.qmatsuite/engines/qe/` for any `Si_ONCV_PBE-*.upf` variant
3. Checks system pseudo directories as fallback

Found `Si_ONCV_PBE-1.1.upf` bundled inside QE's wannier90 examples. Updated QE input templates to use the found filename rather than hardcoding version 1.2.

### Issue 6: Recipe class does not carry SUPPORTED_GEN_STEPS

**Discovery during debugging**: The gate test's `_build_gen_set()` Source 3 checks `recipe_class.SUPPORTED_GEN_STEPS`. However, NO engine in the codebase puts `SUPPORTED_GEN_STEPS` on the recipe class — it's always on the driver class. This means Source 3 of the gate test contributes nothing for any engine. This is a pre-existing pattern (not yambo-specific) and is worked around by Source 1 (workflow registry) and Source 2 (DriverRegistry.get_all_step_types()).

---

## 8. Future Work (Phase 2-3)

### Phase 2: Advanced Artifact Chaining
- GW→BSE QP database chaining (KfnQPdb)
- Cross-engine artifact preflight checks

### Phase 3: Additional Features
- Add `ypp` step type (post-processing: bands, DOS)
- Add convergence parameter metadata (managed keys)
- Add scan support for convergence studies (BndsRnXp, NGsBlkXp, etc.)
- Add `yambo_sc`, `yambo_rt` step types (optional)
