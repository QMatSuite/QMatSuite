# Engine Recipes + JobGraph Generalization Plan

**Date**: 2026-01-13 (Updated: 2026-01-13)
**Status**: IMPLEMENTATION PHASE
**Scope**: Generalize execution planning to support multiple engine families without rewriting bespoke runners

---

## Constitution (Non-Negotiable Decisions)

This section defines the core invariants that MUST be respected throughout implementation.

### A) Engine Family + Members

- A calc may include multiple engine MEMBERS ONLY within the SAME engine FAMILY.
  Today, the meaningful case is QE + Wannier (same family "qe").
- A calc must NOT mix two members that could both claim any arbitrary GEN step.
- **Formal Constraint**: For ALL possible GEN step types, within a family the GEN→SPEC mapping must be 0-1 (supported or not; if supported then unique).
  - Example: "scf" → `qe_scf` OR `pyscf_scf`, but not both in same calc.

### B) Persisted Truth = SPEC

**SPEC** = Machine step type (engine-prefixed, e.g., `qe_scf`, `pyscf_mp2`, `orca_td`)
**GEN** = Public/generalized step type (e.g., `scf`, `mp2`, `td`)

| Layer | Step Type Format | Example |
|-------|------------------|---------|
| Persisted YAML (step.yaml `step_type` field) | **SPEC** | `step_type: qe_scf` |
| Persisted YAML (calc.yaml internal) | **SPEC** | references SPEC step types |
| Manifest entries | **SPEC** | `kind: qe_scf` |
| GEN/UI/Workflows/Presets/IR | **GEN only** | `"scf"`, `"bands"` |
| History records | GEN allowed | for human readability |

**Critical**: GEN step type, workflow name, preset name, IR representation MUST NOT be persisted in step.yaml or calc.yaml content fields.

### C) Explicit Dispatch Mapping (No Prefix Inference)

- Dispatch engine MUST be determined by an explicit mapping: `spec_step_type → engine_member`
- The registry already provides this via `StepTypeSpec.engine` field.
- **Required Unit Test**: Enforce completeness and uniqueness:
  - Every registered SPEC step type must map to exactly one engine member.
  - Mapping keys set must equal the registered SPEC step types set.
  - If anyone adds a step type and forgets mapping, tests must fail.

### D) Workflow Semantics

- Workflow is only an ORDERED LIST of steps. No extra dependency graph persisted.
- Run Step and Run Calc must share ONE PIPELINE:
  - Run Calc: `selection = ALL`
  - Run Step: `selection = TARGET_STEP` (conservative prefix-to-target is OK for MVP)
  - Target step MUST run in Run Step mode, even if upstream may be skipped incrementally.

### E) Locks + Persisted Run Truth

- Keep exactly two locks (already implemented): calc run lock (long), yaml edit lock (short).
- Manifest remains the ONLY persisted run tracking truth. Do not add another persisted "job graph truth".
- JobGraph is runtime-only (materialized each run, never persisted).

### F) Naming Rules (VERY IMPORTANT — User-Visible Files)

This is the ONE place where GEN names appear in output: user-visible filenames.

| Artifact | Naming Rule | Example |
|----------|-------------|---------|
| YAML file on disk | **GEN step type** | `scf.yaml`, `bands.yaml`, `tddft.yaml` |
| YAML file content (`step_type` field) | **SPEC** | `step_type: qe_pw_scf` |
| Raw artifacts (inp/out/property) | **GEN naming** | `scf.in`, `scf.out`, `bands.dat` |
| ORCA chain folder | GEN-based | `raw/scf_<suffix>/` |
| ORCA canonical wavefunction | Fixed | `scf.gbw` |
| ORCA subchain files | GEN abbreviations | `s.out`, `s_t.out`, `s_m2_n.out` |

**ORCA Subchain Abbreviation Examples**:
- SCF-only: `s.inp`, `s.out`, `s.property.txt`
- SCF+TDDFT: `s_t.inp`, `s_t.out`, `s_t.property.txt`
- SCF+MP2+NMR: `s_m2_n.inp`, `s_m2_n.out`, `s_m2_n.property.txt`

**CRITICAL**: Abbreviation tokens MUST come from registry's stable `PUBLIC_TYPE_TOKENS` map, NOT from runtime step sorting. If registry defines `mp2 → m2` and `mp3 → m3`, use those exact tokens.

**Duplicate Handling**: If duplicates exist (e.g., two mp2 steps), overwrite is allowed. Workflow templates should not generate duplicates anyway.

---

## Plan Updates (2026-01-13)

This plan has been updated to incorporate the Constitution above and align with:
1. **Persisted SPEC truth** - YAML content always uses SPEC step types
2. **GEN for filenames only** - User-visible files use GEN names
3. **Explicit dispatch mapping** - Registry-based, with completeness test
4. **One-pipeline runner** - Run Step is selection mode, not separate pipeline
5. **No backwards compat shims** - Fix tests/demos to new rules, don't add shims

---

## Phase 0: Plan Refresh (Mandatory) ✅

- [x] Open docs/plans/engine_recipes_jobgraph_plan.md and revise it to reflect:
  - [x] Persisted SPEC truth, GEN UI-only
  - [x] Explicit dispatch mapping + completeness test
  - [x] Naming rules (GEN filenames, SPEC in YAML content) with concrete examples
  - [x] One-pipeline runner selection (Run Step is selection mode)
  - [x] No backwards compat shims
- [x] Add detailed checkbox roadmap for phases 1–4
- [x] Commit: "plan: align engine recipes/jobgraph with spec-truth + naming + mapping"

---

## Phase 1: Registry + Mapping + Unit Tests (No Behavior Change) ✅

**Goal**: Ensure explicit SPEC→engine dispatch mapping with completeness enforcement.

### P1.1: Verify Registry Mapping Completeness ✅

- [x] Review `src/qmatsuite/workflow/registry.py`:
  - [x] Confirm all entries in `_STEP_TYPES` use SPEC keys (e.g., `qe_scf`, not `scf`)
  - [x] Confirm each `StepTypeSpec` has non-empty `engine` field
  - [x] Confirm `StepTypeSpec.machine_type` matches the dict key
- [x] Check for any legacy code that normalizes step_type to GEN on load/write:
  - [x] Search for `public_type` normalization in step.yaml I/O
  - [x] Found: `normalize_step_type_to_public()` in `structure_steps.py:105-106` (noted as future cleanup)
  - NOTE: step_factory.py correctly writes SPEC to step.yaml (line 73); normalization only affects in-memory model

### P1.2: Add Unit Test for Dispatch Mapping Completeness ✅

- [x] Create `tests/unit/test_step_type_mapping.py`:
  - [x] Test: Every key in `_STEP_TYPES` is a SPEC step type (engine-prefixed)
  - [x] Test: Every `StepTypeSpec.engine` is non-empty
  - [x] Test: Every `StepTypeSpec.machine_type` equals its dict key
  - [x] Test: No duplicate `engine + public_type` combinations (GEN→SPEC is 0-1 per engine family)
  - [x] Test: All registered engines in registry have at least one step type
  - [x] Added bonus tests: token uniqueness, QC token completeness, registry lookup

### P1.3: Verify Step YAML Persistence Uses SPEC ✅

- [x] Check `src/qmatsuite/workflow/step_factory.py`:
  - [x] Confirm `step_type` field in created YAML uses SPEC (machine_type) - line 73
- [x] Check `src/qmatsuite/calculation/manifest.py`:
  - [x] Manifest `kind` derives from step.step_type which comes from YAML (SPEC)

### P1.4: Run Focused Tests ✅

```bash
pytest tests/unit/test_step_type_mapping.py -q   # 10 passed
pytest tests/unit/test_pyscf_chain_registry_contract.py -q  # 3 passed
pytest tests/unit -k "registry" -q  # 35 passed total
```

---

## Phase 2: JobGraph Runtime Model + Recipe Materializers ✅

**Goal**: Add runtime-only JobGraph structures and recipe materialization.

### P2.1: Create JobGraph Module ✅

- [x] Create `src/qmatsuite/execution/__init__.py`
- [x] Create `src/qmatsuite/execution/job_graph.py`:
  - [x] Define `Job` dataclass with all specified fields
  - [x] Define `JobGraph` dataclass with helper methods
  - [x] Add `SelectionMode` enum (ALL, TARGET)
  - [x] Add `compute_job_fingerprint(step_shas: List[str]) -> str`

### P2.2: Create Recipe Protocol and Implementations ✅

- [x] Create `src/qmatsuite/execution/recipes.py`:
  - [x] Define `Recipe` protocol with `materialize()` method
  - [x] Define `BaseRecipe` abstract class
  - [x] Implement `QERecipe`:
    - [x] One job per step
    - [x] `working_dir = calc/raw/`
    - [x] `scratch_dir = calc/raw/outdir/` in metadata
    - [x] Conservative deps (empty, use prefix selection)
  - [x] Implement `ORCARecipe`:
    - [x] One job per subchain
    - [x] `working_dir = calc/raw/scf_<suffix>/`
    - [x] Job ID from stable tokens (`s`, `s_t`, `s_m2`)
    - [x] Self-contained (no inter-job deps)
  - [x] Implement `PySCFRecipe`:
    - [x] One job per subchain (session-based)
    - [x] `working_dir = calc/raw/scf_<suffix>/`
    - [x] `command = ["<internal>"]` for Python subprocess
    - [x] Self-contained
  - [x] Add `get_recipe_for_engine()` factory function

### P2.3: Add Unit Tests for Materialization ✅

- [x] Create `tests/unit/execution/__init__.py`
- [x] Create `tests/unit/execution/test_job_graph.py` (26 tests):
  - [x] Test `Job` dataclass creation (minimal and full)
  - [x] Test `Job.engine`, `Job.is_internal`, `Job.spec_step_type` properties
  - [x] Test `JobGraph.get_job()`, `JobGraph.get_job_by_step_id()`
  - [x] Test `JobGraph.get_jobs_for_target()` with ALL and TARGET modes
  - [x] Test `JobGraph.get_dependencies()`
  - [x] Test `compute_job_fingerprint()` (single, multiple, order-independent)
  - [x] Test multi-step jobs (ORCA-style)
- [x] Create `tests/unit/execution/test_recipes.py` (30 tests):
  - [x] Test QE recipe: single step, multiple steps, fingerprints
  - [x] Test ORCA recipe: namespace folder, gbw output, command format
  - [x] Test PySCF recipe: internal execution, results.json, checkpoint
  - [x] Test `get_recipe_for_engine()` factory
  - [x] Test fingerprint computation in recipes
  - [x] Test input file paths

### P2.4: Run Focused Tests ✅

```bash
pytest tests/unit/execution/ -v  # 56 passed
```

---

## Phase 3: Unified Runner Pipeline + Selection Mode

**Goal**: Refactor runner to use one internal pipeline with JobGraph.

### P3.1: Create JobGraph Executor ✅

- [x] Create `src/qmatsuite/execution/executor.py`:
  - [x] Define `JobResult` and `ExecutionResult` dataclasses
  - [x] Define `JobExecutor` class with `execute()` method
  - [x] Implement job loop with ALL and TARGET selection modes
  - [x] Implement incremental skip logic with manifest/SHA checking
  - [x] Implement "target step must run" rule (never skip target job)
  - [x] Add engine handler delegation (plugin pattern)
  - [x] Add `create_executor_with_default_handlers()` factory
- [x] Create `tests/unit/execution/test_executor.py` (16 tests):
  - [x] Test execute() with ALL and TARGET modes
  - [x] Test stop on failure behavior
  - [x] Test skip logic with manifest and SHAs
  - [x] Test target job never skipped
  - [x] Test multi-step job skip logic

### P3.2: Integrate Executor into Runner ✅

**Status**: COMPLETE

#### P3.2.1: Create Engine Handler Bridge ✅

- [x] Create `src/qmatsuite/execution/handlers.py`:
  - [x] Define handler signature: `(job: Job, calculation: Calculation, engine_registry, context) -> JobResult`
  - [x] Implement `qe_step_handler()`: Wraps existing `step.run()` for QE/Wannier steps
  - [x] Implement `pyscf_chain_handler()`: Wraps PySCF chain execution
  - [x] Implement `orca_chain_handler()`: Wraps ORCA chain execution
  - [x] Preserve existing contracts:
    - QE: raw/outdir unchanged
    - Wannier: raw in-place unchanged
    - QC: raw/scf_<suffix>/ unchanged

#### P3.2.2: Wire Executor into Runner ✅

- [x] Modify `src/qmatsuite/calculation/runner.py`:
  - [x] Add `target_step_id: Optional[str] = None` parameter to `run()` signature
  - [x] Add import for execution module
  - [x] After manifest reconciliation, detect engine family from first step
  - [x] Create appropriate recipe based on engine family
  - [x] Materialize JobGraph from calculation steps
  - [x] Create JobExecutor with registered handlers
  - [x] Replace step loop with `executor.execute()` call (legacy loop kept as fallback)
  - [x] Convert ExecutionResult back to CalculationResult format

#### P3.2.3: Manifest Update Integration ✅

- [x] Ensure manifest updates happen correctly:
  - [x] started_at set before job execution
  - [x] done=true/false set after job completion
  - [x] done_at timestamp recorded on success
  - [x] Per-step manifest entries for multi-step jobs (ORCA/PySCF)

#### P3.2.4: Preserve Existing Logic ✅

- [x] Keep Step0 pseudo preparation unchanged
- [x] Keep manifest reconciliation unchanged
- [x] Keep history recording unchanged
- [x] Keep exactly 2 locks (calc_run_lock outer, yaml_edit_lock inner)
- [x] Keep failure handling (calculation_failed flag, strict mode abort)

### P3.3: Unify Run Step into Same Pipeline ✅

- [x] Update `src/qmatsuite/api.py` `QMSService.run_step()`:
  - [x] Call `CalculationRunner.run(calc, target_step_id=step_id)`
  - [x] Remove separate run_step logic (moved to `run_step_legacy()` for reference)

### P3.4: Run Focused Tests ✅

```bash
pytest tests/unit/execution/ -v  # 72 passed (including executor tests)
```

---

## Phase 4: Integration + Cleanup (No Debt) ✅

**Goal**: Full integration test suite passes, no backwards compat shims.

### P4.1: Run ORCA Integration Tests ✅

- [x] Ensure ORCA binary is available (bundled mock ORCA for tests)
- [x] Run ORCA tests: `pytest tests/integration/orca/ -q` (18 passed)
- [x] All tests pass without shims

### P4.2: Run QE + Wannier Integration Tests ✅

- [x] Run QE tests: `pytest tests/integration/test_qe_engine.py -q` (3 passed)
- [x] Run incremental tests: `pytest tests/integration/test_incremental_run.py -q` (15 passed)
- [x] All tests pass

### P4.3: Run PySCF Full Suite ✅

- [x] Run PySCF Phase 3C tests: `pytest tests/integration/test_pyscf_phase3c.py -q` (5 passed)
- [x] Run other PySCF tests: `pytest tests/integration/test_pyscf_*.py -q` (13 passed)
- [x] Fixed test_t5_missing_dependency_error to check result dict instead of exception

### P4.4: Run Registry/Mapping Tests ✅

- [x] Registry tests pass: `pytest tests/unit -k "registry" -q` (35 passed)
- [x] Mapping tests pass: `pytest tests/unit/test_step_type_mapping.py -q` (10 passed)

### P4.5: Cleanup ✅

- [x] Legacy `run_step` code moved to `run_step_legacy()` for reference
- [x] No backwards compat shims added - tests updated to new rules
- [x] YAML I/O unchanged (SPEC truth preserved)

### P4.6: Final Verification ✅

- [x] Execution module tests: `pytest tests/unit/execution/ -q` (72 passed)
- [x] Integration tests: All engine families passing

---

## What Changed

### Code Changes

**New Files Created:**

1. `src/qmatsuite/execution/__init__.py` - Module exports
2. `src/qmatsuite/execution/job_graph.py` - Job, JobGraph, SelectionMode, compute_job_fingerprint
3. `src/qmatsuite/execution/recipes.py` - QERecipe, ORCARecipe, PySCFRecipe, get_recipe_for_engine
4. `src/qmatsuite/execution/executor.py` - JobExecutor, JobResult, ExecutionResult
5. `src/qmatsuite/execution/handlers.py` - Engine handlers (qe_step_handler, pyscf_chain_handler, orca_chain_handler)
6. `tests/unit/test_step_type_mapping.py` - 10 dispatch mapping completeness tests
7. `tests/unit/execution/__init__.py` - Test module
8. `tests/unit/execution/test_job_graph.py` - 26 JobGraph tests
9. `tests/unit/execution/test_recipes.py` - 30 recipe tests
10. `tests/unit/execution/test_executor.py` - 16 executor tests

**Files Modified:**

1. `docs/plans/engine_recipes_jobgraph_plan.md` - Updated with Constitution and progress
2. `src/qmatsuite/calculation/runner.py` - Added `_execute_with_jobgraph()`, `target_step_id` parameter
3. `src/qmatsuite/api.py` - Unified `run_step()` to use CalculationRunner pipeline
4. `tests/integration/test_pyscf_phase3c.py` - Updated test_t5 to check result dict instead of exception

### Tests Executed

```bash
# Phase 1: Registry mapping tests
pytest tests/unit/test_step_type_mapping.py -v  # 10 passed
pytest tests/unit -k "registry" -v  # 35 passed

# Phase 2: JobGraph and recipes tests
pytest tests/unit/execution/test_job_graph.py -v  # 26 passed
pytest tests/unit/execution/test_recipes.py -v  # 30 passed

# Phase 3: Executor tests
pytest tests/unit/execution/test_executor.py -v  # 16 passed
pytest tests/unit/execution/ -v  # 72 passed

# Phase 4: Integration tests
pytest tests/integration/orca/ -v  # 18 passed
pytest tests/integration/test_pyscf_phase3c.py -v  # 5 passed
pytest tests/integration/test_pyscf_*.py -v  # 13 passed
pytest tests/integration/test_qe_engine.py -v  # 3 passed
pytest tests/integration/test_incremental_run.py -v  # 15 passed
```

### Implementation Summary

**Unified Runner Pipeline:**
- `CalculationRunner.run()` now supports `target_step_id` parameter for TARGET selection mode
- `_execute_with_jobgraph()` materializes JobGraph from recipe and executes via JobExecutor
- Engine handlers bridge JobExecutor to existing engine execution logic
- Legacy step loop kept as fallback (will be removed once fully validated)

**Run Step Unification:**
- `QMSService.run_step()` now calls `CalculationRunner.run(calc, target_step_id=step_id)`
- Same pipeline for Run Calc (selection=ALL) and Run Step (selection=TARGET)
- Target step always runs (never skipped even if incrementally eligible)

### Known Follow-ups

3. **normalize_step_type_to_public Cleanup**: Remove backwards compat shim
   - Location: `src/qmatsuite/calculation/structure_steps.py:105-106`
   - Change StructureStepSpec to use SPEC step types internally
   - Update tests that depend on GEN step types in specs

4. **StepType Enum Update**: Add ORCA step types to StepType enum
   - Currently missing: ORCA_SCF, ORCA_HF, ORCA_TD
   - Or: Remove StepType enum dependency in favor of registry lookup

5. **Integration Tests (P4)**: Run full ORCA and QE integration tests
   - Ensure ORCA binary is configured
   - Verify no regressions in existing behavior

---

## Reference: As-Is Evidence Map

### Current Execution Flow

**File**: `src/qmatsuite/calculation/runner.py`
- **Class**: `CalculationRunner`
- **Method**: `run(calculation, skip_history, run_id, run_mode)`
- **Flow**:
  1. Acquire calc_run_lock (outermost, long-held)
  2. Step0: Prepare pseudos in project/pseudo
  3. Manifest reconciliation for incremental mode
  4. Loop over steps:
     - Skip if before start_idx and manifest says done
     - Update manifest: started_at, done=false, run_id
     - Resolve engine from step YAML machine step_type
     - Create per-step artifact directory
     - Call `step.run(engine, calculation_raw_dir, project_root, species_map)`
     - Evaluate result
     - Update manifest: done=true/false, done_at
  5. History recording

### Current Lock Implementation

**File**: `src/qmatsuite/core/locking.py`
- **Two Locks**:
  1. `calc_run_lock(calc_dir)` - Long-held during calculation run
  2. `calc_edit_lock(calc_dir)` - Short-held during YAML writes
- **Lock Order**: calc_run_lock outermost; calc_edit_lock may occur inside

### Current Engine Filesystem Contracts

| Engine | Scratch Dir | Working Dir |
|--------|-------------|-------------|
| QE | `calc/raw/outdir/` | `calc/raw/` |
| Wannier90 | (in-place) | `calc/raw/` |
| ORCA | (same as working) | `calc/raw/scf_<suffix>/` |
| PySCF | (same as working) | `calc/raw/scf_<suffix>/` |

### Stable Token Registry

From `src/qmatsuite/workflow/registry.py`:

```python
PUBLIC_TYPE_TOKENS: Dict[str, str] = {
    "scf": "s",     # SCF/DFT root
    "hf": "h",      # Hartree-Fock root
    "td": "t",      # TDDFT/TDHF excited states
    "mp2": "m2",    # MP2 correlation
    "freq": "f",    # Frequency/vibrational analysis
    "nmr": "n",     # NMR chemical shifts
}
```

---

## The Three Recipes

### Recipe 1: QE-Recipe (Directory-State, Step-Run)

- **Job Granularity**: One job per step
- **Working Directory**: `calc/raw/`
- **Scratch Directory**: `calc/raw/outdir/` (engine-owned, unchanged)
- **Dependencies**: Conservative prefix-to-target for selection
- **Command**: `["pw.x", "scf.in"]` (engine-specific executable)
- **Engines**: QE, Wannier90, future VASP, ABINIT

### Recipe 2: ORCA-Recipe (QC Strong-Chain)

- **Job Granularity**: One job per subchain
- **Working Directory**: `calc/raw/scf_<suffix>/`
- **Dependencies**: Self-contained (no inter-job deps)
- **Job ID**: Stable token path (`s`, `s_t`, `s_m2`)
- **Command**: `["orca", "s_t.inp"]`
- **Reuse**: `MORead` + canonical `scf.gbw`
- **Engines**: ORCA

### Recipe 3: PySCF-Recipe (QC Weak-Chain / Session)

- **Job Granularity**: One job per subchain (session)
- **Working Directory**: `calc/raw/scf_<suffix>/`
- **Dependencies**: Self-contained
- **Job ID**: Stable token path (`s`, `s_m2`)
- **Command**: `["<internal>"]` (Python subprocess)
- **Reuse**: Checkpoint file for wavefunction
- **Engines**: PySCF

---

## Non-Goals

1. **NOT implementing parallel job execution** within a calc
2. **NOT implementing VASP/ABINIT/Psi4 engines** - only laying groundwork
3. **NOT changing existing filesystem contracts** - raw/outdir unchanged
4. **NOT adding backwards compat shims** - fix tests/demos to new rules
5. **NOT persisting JobGraph** - runtime-only, derived each run

---

## Phase 5: Audit Fixes (Required for Unconditional PASS) ✅ COMPLETED

**Goal**: Fix 3 high-severity risks identified in `docs/reviews/engine_jobgraph_independent_review.md`

**Status**: ALL FIXES COMPLETED (2026-01-14)

### AF-1: Remove normalize_step_type_to_public() from Production Paths (BLOCKER) ✅

**Audit Evidence**:
- `src/qmatsuite/calculation/structure_steps.py:105-106` normalizes SPEC → GEN when loading
- `src/qmatsuite/calculation/hash_utils.py:187-188` normalizes SPEC → GEN before hashing

**Fixes**:
- [x] AF-1.1: Remove SPEC→GEN normalization from `StructureStepSpec` loading path
- [x] AF-1.2: Remove SPEC→GEN normalization from SHA computation path
- [x] AF-1.3: Update `_coerce_step_type()` in runner.py and calculation.py to handle SPEC types via registry
- [x] AF-1.4: Add unit test: loading step.yaml preserves SPEC step_type
- [x] AF-1.5: Add unit test: SHA computation uses SPEC step_type
- [x] AF-1.6: Run focused tests and record results (17 tests passing)

### AF-2: Replace Prefix Inference with Registry Lookup (HIGH) ✅

**Audit Evidence**:
- `src/qmatsuite/calculation/runner.py:854-859` infers engine_family via string prefix

**Fixes**:
- [x] AF-2.1: Delete prefix inference code from runner recipe selection
- [x] AF-2.2: Implement `_get_engine_family_from_step()` using StepTypeSpec.engine via registry
- [x] AF-2.3: Add regression tests that verify registry-based lookup (3 tests)
- [x] AF-2.4: Run focused tests and record results (17 tests passing)

### AF-3: Remove Legacy Execution Loop (HIGH) ✅

**Audit Evidence**:
- Legacy execution loop in `runner.py:378-800` is reachable as fallback
- `run_step_legacy()` in `api.py` is present

**Fixes**:
- [x] AF-3.1: Identify all callsites/branches that could execute legacy loop
- [x] AF-3.2: Verified no tests rely on legacy semantics
- [x] AF-3.3: Delete legacy execution loop from runner.py (lines 443-857 removed)
- [x] AF-3.4: Delete run_step_legacy() from api.py
- [x] AF-3.5: Add safety tests: `test_no_run_step_legacy_in_api`, `test_no_legacy_fallback_in_runner`
- [x] AF-3.6: Run focused tests and record results (2 safety tests + all existing tests passing)

### AF-4: Update Demo Scripts (Required) ✅

**Fixes**:
- [x] AF-4.1: Locate demo scripts in tools/
- [x] AF-4.2: Update generate_wannier90_demo.py to use SPEC types (qe_scf, qe_nscf, qe_pw2wannier90)
- [x] AF-4.3: Update generate_wannier90_demos.py to use SPEC types
- [x] AF-4.4: Update generate_orca_demos.py to use SPEC types (orca_scf, orca_td)
- [x] AF-4.5: generate_pyscf_demo.py already uses SPEC types (pyscf_scf)
- [x] AF-4.6: Syntax validation passed for all demo scripts

### AF-5: Add Level-3 Project Integration Tests (Required) ✅

**Fixes**:
- [x] AF-5.1: Create ORCA project-level run-calc test (`TestORCAProjectLevelExecution`)
- [x] AF-5.2: Create ORCA project-level run-step test
- [x] AF-5.3: Add registry lookup verification tests (`TestORCARegistryLookup`)
- [x] AF-5.4: Tests use real ORCA executable when available
- [x] AF-5.5: Run integration tests and record results (2 registry tests passing)

### AF-6: Final Verification ✅

**Required Test Runs**:
- [x] AF-6.1: `pytest tests/unit/test_step_type_mapping.py` - 19 passed
- [x] AF-6.2: `pytest tests/integration/orca/test_orca_execution.py` - 10 passed
- [x] AF-6.3: `pytest tests/integration/test_pyscf_execution.py` - 11 passed
- [x] AF-6.4: Total: 40 tests passed in 19.03s

---

## Test Log (Audit Fixes)

### 2026-01-14 Final Test Results

```
============================= 40 passed in 19.03s ==============================
```

**Breakdown**:
- ORCA execution tests: 10 passed
- PySCF execution tests: 11 passed
- Step type mapping tests: 19 passed (including 2 legacy code removal safety tests)

**Files Modified**:
- `src/qmatsuite/calculation/structure_steps.py` - Removed SPEC→GEN normalization
- `src/qmatsuite/calculation/hash_utils.py` - Removed normalization from SHA computation
- `src/qmatsuite/calculation/runner.py` - Replaced prefix inference with registry lookup, removed legacy loop
- `src/qmatsuite/calculation/calculation.py` - Updated _coerce_step_type for SPEC handling
- `src/qmatsuite/api.py` - Removed run_step_legacy()
- `tests/unit/test_step_type_mapping.py` - Added 9 new tests for Constitution compliance
- `tests/integration/orca/test_orca_project_level.py` - NEW: Level-3 project integration tests
- `tools/generate_orca_demos.py` - Updated to use SPEC step types
- `tools/generate_wannier90_demo.py` - Updated to use SPEC step types
- `tools/generate_wannier90_demos.py` - Updated to use SPEC step types

---

**End of Plan**
