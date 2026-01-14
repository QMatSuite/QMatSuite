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

- [x] Review `src/quantumvitas/workflow/registry.py`:
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

- [x] Check `src/quantumvitas/workflow/step_factory.py`:
  - [x] Confirm `step_type` field in created YAML uses SPEC (machine_type) - line 73
- [x] Check `src/quantumvitas/calculation/manifest.py`:
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

- [x] Create `src/quantumvitas/execution/__init__.py`
- [x] Create `src/quantumvitas/execution/job_graph.py`:
  - [x] Define `Job` dataclass with all specified fields
  - [x] Define `JobGraph` dataclass with helper methods
  - [x] Add `SelectionMode` enum (ALL, TARGET)
  - [x] Add `compute_job_fingerprint(step_shas: List[str]) -> str`

### P2.2: Create Recipe Protocol and Implementations ✅

- [x] Create `src/quantumvitas/execution/recipes.py`:
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

- [x] Create `src/quantumvitas/execution/executor.py`:
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

### P3.2: Integrate Executor into Runner (DEFERRED)

- [ ] Modify `src/quantumvitas/calculation/runner.py`:
  - [ ] Add recipe selection logic (detect engine family from first step)
  - [ ] Materialize JobGraph using appropriate recipe
  - [ ] Delegate execution to JobExecutor
  - [ ] Keep existing: Step0 pseudo prep, manifest handling, history recording
- [ ] Update `CalculationRunner.run()` signature with `target_step_id` param

NOTE: Full runner integration deferred to future work. Current executor can be
used standalone or integrated incrementally.

### P3.3: Unify Run Step into Same Pipeline (DEFERRED)

- [ ] Update `src/quantumvitas/api.py` `QVService.run_step()`:
  - [ ] Call `CalculationRunner.run(calc, target_step_id=step_id)`
  - [ ] Remove separate run_step logic

NOTE: Run Step unification deferred to future work.

### P3.4: Run Focused Tests ✅

```bash
pytest tests/unit/execution/ -v  # 72 passed (including executor tests)
```

---

## Phase 4: Integration + Cleanup (No Debt)

**Goal**: Full integration test suite passes, no backwards compat shims.

### P4.1: Run ORCA Integration Tests

- [ ] Ensure ORCA binary is available (local or via env var)
- [ ] Run ORCA tests:
  ```bash
  pytest tests/integration -k "orca" -q
  ```
- [ ] Fix any failures by updating tests to new spec-truth rules (NOT by adding shims)

### P4.2: Run QE + Wannier Integration Tests

- [ ] Run QE tests:
  ```bash
  pytest tests/integration -k "qe or wannier" -q
  ```
- [ ] Fix any failures by updating tests to new rules

### P4.3: Run PySCF Full Suite

- [ ] Run all PySCF tests:
  ```bash
  pytest tests/integration/test_pyscf_phase3c.py -q
  ```

### P4.4: Run Registry/Mapping Tests

- [ ] Run full registry test suite:
  ```bash
  pytest tests/unit -k "registry or mapping or step_type" -q
  ```

### P4.5: Cleanup

- [ ] Remove any dead code from old runner paths
- [ ] Remove any backwards compat shims (if any were added, remove them)
- [ ] Ensure no GEN→SPEC normalization in YAML I/O

### P4.6: Final Verification

- [ ] Run curated test suite:
  ```bash
  pytest tests/unit -k "registry or mapping or jobgraph or runner" -q
  pytest tests/integration -k "orca or pyscf" -q
  pytest tests/integration/test_pyscf_phase3c.py -q
  ```

---

## What Changed

### Code Changes

**New Files Created:**

1. `src/quantumvitas/execution/__init__.py` - Module exports
2. `src/quantumvitas/execution/job_graph.py` - Job, JobGraph, SelectionMode, compute_job_fingerprint
3. `src/quantumvitas/execution/recipes.py` - QERecipe, ORCARecipe, PySCFRecipe, get_recipe_for_engine
4. `src/quantumvitas/execution/executor.py` - JobExecutor, JobResult, ExecutionResult
5. `tests/unit/test_step_type_mapping.py` - 10 dispatch mapping completeness tests
6. `tests/unit/execution/__init__.py` - Test module
7. `tests/unit/execution/test_job_graph.py` - 26 JobGraph tests
8. `tests/unit/execution/test_recipes.py` - 30 recipe tests
9. `tests/unit/execution/test_executor.py` - 16 executor tests

**Files Modified:**

1. `docs/plans/engine_recipes_jobgraph_plan.md` - Updated with Constitution and progress

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

# All execution tests
pytest tests/unit/execution/ -v  # 72 passed
```

### Known Follow-ups

1. **Runner Integration (P3.2)**: Integrate JobExecutor into CalculationRunner.run()
   - Add recipe selection based on engine family
   - Materialize JobGraph before execution
   - Wire up engine handlers to existing engine code

2. **Run Step Unification (P3.3)**: Unify QVService.run_step() with CalculationRunner
   - Pass target_step_id through to runner
   - Remove duplicate run_step logic in api.py

3. **normalize_step_type_to_public Cleanup**: Remove backwards compat shim
   - Location: `src/quantumvitas/calculation/structure_steps.py:105-106`
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

**File**: `src/quantumvitas/calculation/runner.py`
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

**File**: `src/quantumvitas/core/locking.py`
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

From `src/quantumvitas/workflow/registry.py`:

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

**End of Plan**
