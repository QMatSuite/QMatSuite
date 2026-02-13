# Phase 3C Confusion & Evidence Report

**Date**: 2025-01-10  
**Goal**: Identify architectural clarifications needed before implementing remaining Phase 3C features

---

## Section 0: Spec Excerpt Mapping

### Required Phase 3C Behaviors (from PHASE3C_RUNNER_SPEC.md)

- **A3.1 Run Calc (Default) = Incremental**: 
  - SCF may use chkfile init_guess when available (still run kernel)
  - All non-SCF steps ALWAYS full rerun
  - **Where it should live**: `CalculationRunner.run()` → step execution logic → PySCF runner

- **A3.2 Run Calc → Dropdown "Full Run"**:
  - SCF must NOT use chkfile init_guess (fresh start)
  - **Where it should live**: `QVService.run_calculation(run_mode="full")` → `CalculationRunner.run(run_mode="full")` → PySCF runner

- **A3.3 Run Step(X)**:
  - Resolve dependency chain from X back to root using nearest-provider rule
  - Execute chain in ONE session
  - Target step X always full rerun
  - If X is SCF: forbid chkfile init_guess
  - Prerequisite steps: use normal incremental semantics (SCF may use chkfile)
  - **Where it should live**: `QVService.run_step()` or new `run_step_with_chain()` → dependency resolution → one-session PySCF execution

- **A4 Checkpointing Policy**:
  - Only SCF produces restartable checkpoint (chkfile)
  - chkfile path: fixed convention `{step_artifacts_dir}/checkpoint.chk`
  - **Where it should live**: PySCF runner `run_scf()` function

- **A5 Step Spec Storage**:
  - step.yaml contains meta + machine step_type + parameters
  - step.yaml MUST NOT contain structure data
  - Downstream steps MUST NOT redundantly store SCF selections
  - **Where it should live**: Step factory/generation code + validation tests

---

## Section 1: Confusion Items

### Confusion 1: Run Calc incremental vs full selection and passing

**A) What exactly is unclear**: How does `run_mode` flow from UI/API through service layer to `CalculationRunner.run()`, and how should it control PySCF init_guess behavior in step execution?

**B) Where in code this is decided today**:
- `src/quantumvitas/api.py::QVService.run_calculation()` (line 1129-1138): Receives `run_mode: str = "incremental"` parameter
- `src/quantumvitas/api.py::QVService.run_calculation()` (line 1260-1263): Calls `runner.run(calculation, run_id=run_id, run_mode=run_mode)`
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 67-73): Receives `run_mode: str = "incremental"` parameter
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 267-447): Executes steps sequentially, but `run_mode` is only used for manifest reconciliation (line 176, 218), not passed to step execution
- Call chain: `QVService.run_calculation()` → `CalculationRunner.run()` → `step.run()` → `engine.run_step()` (no run_mode passed)

**C) What the spec requires**: RunCalc incremental should allow chkfile init_guess; RunCalc full should forbid it. (Section A3.1, A3.2)

**D) Two concrete implementation options**:

**Option 1**: Pass `run_mode` through step execution chain
- Modify `Step.run()` to accept optional `run_mode` parameter
- Modify `CalculationRunner.run()` to pass `run_mode` to `step.run(engine, ..., run_mode=run_mode)`
- Modify `PySCFEngine.run_step()` to accept `run_mode` and set `allow_chkfile_init_guess = (run_mode == "incremental")`
- Add `allow_chkfile_init_guess` to job.json
- Pros: Explicit, clear flow
- Cons: Requires changing Step.run() signature (may affect QE path)

**Option 2**: Store `run_mode` in step context/options
- Store `run_mode` in step.options dict before execution
- `PySCFEngine.run_step()` reads `step.options.get("run_mode", "incremental")`
- Set `allow_chkfile_init_guess = (step.options.get("run_mode", "incremental") == "incremental")`
- Pros: No signature changes, backward compatible
- Cons: Less explicit, relies on options dict

**E) Which option I will pick**: **Option 2** - Store run_mode in step.options. This matches spec requirement (run_mode controls behavior) and requires minimal changes. QE execution ignores this option, so no breaking changes.

**F) Files to re-read**: 
- `src/quantumvitas/calculation/runner.py` (step execution loop, where to set step.options)
- `src/quantumvitas/engine/pyscf_engine.py` (run_step method, where to read run_mode from options)

**G) Narrow question**: None - Option 2 is clear and minimal.

---

### Confusion 2: Run Step(X) entry point and current execution

**A) What exactly is unclear**: Where is the Run Step(X) entry point implemented, and how does it currently execute a single step? Does it need to change to support dependency chain resolution and one-session execution?

**B) Where in code this is decided today**:
- `src/quantumvitas/api.py::QVService.run_step()` (line 1302-1525): Entry point for Run Step
- `src/quantumvitas/api.py::QVService.run_step()` (line 1405): Calls `run_input_step()` (QE-specific, uses legacy input_runner)
- `src/quantumvitas/cli/main.py::run_step_command()` (line 1427-1456): CLI entry point (deprecated, redirects to API)
- Call chain: `QVService.run_step()` → `run_input_step()` (QE only) OR could call `CalculationRunner` for PySCF
- Current implementation: QE-specific, uses `run_input_step()` directly, does NOT use `CalculationRunner` or `Step.run()`

**C) What the spec requires**: Run Step(X) must resolve dependency chain and execute in ONE session. (Section A3.3)

**D) Two concrete implementation options**:

**Option 1**: Create new PySCF-specific RunStep path
- Add new method `QVService.run_step_with_chain()` or modify `run_step()` to detect PySCF steps
- For PySCF steps: resolve dependency chain using `resolve_dependency_chain()`
- Call new `_run_pyscf_chain()` function that executes chain in one session
- For QE steps: keep existing `run_input_step()` path (unchanged)
- Pros: Clear separation, QE path unchanged
- Cons: Duplicate entry point logic

**Option 2**: Integrate into CalculationRunner with step selector
- Modify `CalculationRunner.run()` to accept optional `target_step_ulid` parameter
- If `target_step_ulid` provided: resolve chain, execute only that chain
- If not provided: execute all steps (current behavior)
- `QVService.run_step()` loads calculation, calls `CalculationRunner.run(target_step_ulid=step_ulid)`
- Pros: Reuses CalculationRunner infrastructure
- Cons: CalculationRunner becomes more complex

**E) Which option I will pick**: **Option 1** - Create PySCF-specific RunStep path. This matches spec (RunStep has different semantics than RunCalc) and keeps QE behavior unchanged. Clear separation of concerns.

**F) Files to re-read**:
- `src/quantumvitas/api.py::QVService.run_step()` (current implementation)
- `src/quantumvitas/engines/pyscf/chain.py` (resolve_dependency_chain function)
- `src/quantumvitas/calculation/runner.py` (to understand CalculationRunner structure for reference)

**G) Narrow question**: None - Option 1 is clear and preserves QE behavior.

---

### Confusion 3: PySCF execution model (per-step vs same process)

**A) What exactly is unclear**: Does PySCF currently run each step in a separate subprocess, or in the same process? How should one-session chain execution work?

**B) Where in code this is decided today**:
- `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()` (line 145-304): Creates job.json, runs subprocess
- `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()` (line 235): `cmd = self._get_runner_command() + [str(job_file)]` - ONE subprocess per step
- `src/quantumvitas/engines/pyscf/runner.py::run_job()` (line 568): Entry point for subprocess, runs ONE step per invocation
- Call chain: `PySCFEngine.run_step()` → subprocess → `runner.run_job(job.json)` → `run_scf()` or `run_mp2()`
- Current model: Each step runs in SEPARATE subprocess (one job.json per step, one Python process per step)

**C) What the spec requires**: Run Step(X) must execute dependency chain in ONE session (one subprocess). RunCalc can continue using per-step subprocesses. (Section A3.3, A4)

**D) Two concrete implementation options**:

**Option 1**: New chain execution function in runner.py
- Create `run_job_chain()` function in `runner.py` that accepts multiple step specs
- Import PySCF once, execute steps sequentially in same process
- Maintain in-memory objects (mol, mf) between steps
- `PySCFEngine.run_step_chain()` creates job_chain.json, calls subprocess once
- Pros: Clear separation, one subprocess for chain
- Cons: New execution path, need to handle state passing

**Option 2**: Modify run_job() to accept chain spec
- Extend `run_job()` to accept `job_chain.json` with array of step specs
- Execute steps sequentially in same process
- Backward compatible: single step = array with one element
- Pros: Reuses existing runner infrastructure
- Cons: Mixes single-step and chain execution logic

**E) Which option I will pick**: **Option 1** - New `run_job_chain()` function. This matches spec requirement (one session for RunStep chain) and keeps single-step execution unchanged. Clear separation.

**F) Files to re-read**:
- `src/quantumvitas/engines/pyscf/runner.py::run_job()` (current structure)
- `src/quantumvitas/engines/pyscf/runner.py::run_scf()` and `run_mp2()` (to understand how to chain them)

**G) Narrow question**: None - Option 1 is clear.

---

### Confusion 4: Step artifacts directory management

**A) What exactly is unclear**: Where and how are step artifact directories created and cleared? The spec says "clear that step's artifacts directory before each step run".

**B) Where in code this is decided today**:
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 437): `raw_dir = calculation.raw_dir` (single raw_dir for all steps)
- `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()` (line 158): `working_dir.mkdir(parents=True, exist_ok=True)` (creates working_dir if needed)
- No evidence of per-step artifact directories or clearing logic found in codebase search
- Current model: All steps write to `calculation.raw_dir` (single directory)

**C) What the spec requires**: "Before each step run, clear that step's artifacts directory". (Section Implementation Notes)

**D) Two concrete implementation options**:

**Option 1**: Per-step artifact directories in raw_dir
- Create `raw_dir / "step_artifacts" / {step_ulid}` for each step
- Clear directory before step execution: `shutil.rmtree(artifacts_dir, ignore_errors=True); artifacts_dir.mkdir()`
- PySCF runner writes to step-specific artifacts dir
- Pros: Clear separation, matches spec requirement
- Cons: New directory structure

**Option 2**: Clear step-specific files in raw_dir
- Identify step-specific files (e.g., `{step_type}*.json`, `{step_type}*.chk`)
- Clear matching files before step execution
- Pros: Minimal changes, reuses raw_dir
- Cons: Less clean, file naming conventions needed

**E) Which option I will pick**: **Option 1** - Per-step artifact directories. This matches spec requirement ("per-step artifacts directory") and provides clean separation. For PySCF, use `raw_dir / "step_artifacts" / {step_ulid}`.

**F) Files to re-read**:
- `src/quantumvitas/calculation/runner.py` (where to create/clear artifacts dir)
- `src/quantumvitas/engine/pyscf_engine.py` (where to set working_dir to artifacts dir)

**G) Narrow question**: None - Option 1 matches spec requirement.

---

### Confusion 5: Chkfile creation, location, and init_guess control

**A) What exactly is unclear**: Where is chkfile created today, and is the path constant? How is init_guess currently controlled, and how should run_mode affect it?

**B) Where in code this is decided today**:
- `src/quantumvitas/engines/pyscf/runner.py::run_scf()` (line 180): `checkpoint_file = working_dir / "checkpoint.chk"` (constant path)
- `src/quantumvitas/engines/pyscf/runner.py::run_scf()` (line 181): `mf.chkfile = str(checkpoint_file)` (sets chkfile path)
- `src/quantumvitas/engines/pyscf/runner.py::run_scf()` (line 184-189): Always uses checkpoint if exists: `if checkpoint_file.exists(): mf.init_guess = 'chkfile'`
- `src/quantumvitas/engines/pyscf/runner.py::run_scf()` (line 117): Now accepts `allow_chkfile_init_guess: bool = True` parameter (recently added)
- `src/quantumvitas/engines/pyscf/runner.py::run_job()` (line 632): Calls `run_scf(params, working_dir)` - does NOT pass allow_chkfile_init_guess yet
- Current model: Chkfile path is constant (`working_dir / "checkpoint.chk"`), init_guess always uses chkfile if exists

**C) What the spec requires**: Chkfile path is fixed convention. Init_guess control: incremental=True, full=False, RunStep(scf)=False. (Section A3, A4, A5)

**D) Two concrete implementation options**:

**Option 1**: Pass allow_chkfile_init_guess through job.json
- Add `allow_chkfile_init_guess: bool` to job.json
- `run_job()` reads it and passes to `run_scf(..., allow_chkfile_init_guess=job.get("allow_chkfile_init_guess", True))`
- `PySCFEngine.run_step()` sets it based on run_mode from step.options
- Pros: Already implemented in run_scf(), just needs wiring
- Cons: None (this is straightforward)

**Option 2**: Infer from run_mode in runner
- `run_job()` reads `run_mode` from job.json
- Set `allow_chkfile_init_guess = (run_mode == "incremental")`
- Pros: Single source of truth (run_mode)
- Cons: Need to handle RunStep case (target step vs prerequisite)

**E) Which option I will pick**: **Option 1** - Pass `allow_chkfile_init_guess` through job.json. This is already partially implemented (run_scf accepts parameter), just needs wiring through job.json and PySCFEngine. Clear and explicit.

**F) Files to re-read**:
- `src/quantumvitas/engines/pyscf/runner.py::run_job()` (where to read allow_chkfile_init_guess)
- `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()` (where to set it in job.json)

**G) Narrow question**: None - Option 1 is straightforward.

---

### Confusion 6: Minimal insertion point for one-session chain run

**A) What exactly is unclear**: Where should the one-session chain execution be inserted for RunStep mode, without breaking QE/W90 behavior?

**B) Where in code this is decided today**:
- `src/quantumvitas/api.py::QVService.run_step()` (line 1302): Current entry point
- `src/quantumvitas/api.py::QVService.run_step()` (line 1405): Calls `run_input_step()` (QE-specific)
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` (line 442): Calls `step.run()` for each step
- `src/quantumvitas/calculation/step.py::Step.run()` (line 78-79): `if engine.name != "qe": return engine.run_step(self, calculation_raw_dir)` (PySCF path)
- Current model: RunStep uses QE-specific path, does NOT use CalculationRunner

**C) What the spec requires**: Run Step(X) for PySCF must resolve chain and execute in one session. QE/W90 behavior unchanged. (Section A3.3)

**D) Two concrete implementation options**:

**Option 1**: Engine-specific run_step_with_chain method
- Add `run_step_with_chain(step, chain_steps, ...)` method to Engine interface (optional, PySCF implements it)
- `QVService.run_step()` detects PySCF steps, resolves chain, calls `engine.run_step_with_chain()`
- QE/W90 engines don't implement it (fallback to run_step)
- Pros: Engine-specific, QE unchanged
- Cons: New interface method

**Option 2**: PySCFEngine.run_step() detects chain context
- Add optional `chain_context` parameter to `run_step()`
- If provided: execute chain in one session
- If not provided: execute single step (current behavior)
- `QVService.run_step()` for PySCF resolves chain, calls `engine.run_step(step, ..., chain_context=chain_steps)`
- Pros: Reuses run_step() signature
- Cons: Parameter pollution, less clear

**E) Which option I will pick**: **Option 1** - Engine-specific `run_step_with_chain()` method. This matches spec (RunStep has different semantics) and keeps QE/W90 engines unchanged (they don't implement the method). Clear separation.

**F) Files to re-read**:
- `src/quantumvitas/engine/base.py` (Engine interface)
- `src/quantumvitas/api.py::QVService.run_step()` (where to add PySCF chain detection)
- `src/quantumvitas/engine/pyscf_engine.py` (where to implement run_step_with_chain)

**G) Narrow question**: None - Option 1 is clear and preserves QE behavior.

---

## Appendix: Files That Must Change for Phase 3C

### UI Layer
- (None - run_mode already flows from API, no UI changes needed for this phase)

### Service/Core Runner Layer
1. `src/quantumvitas/api.py::QVService.run_step()` - Add PySCF chain resolution and execution
2. `src/quantumvitas/calculation/runner.py::CalculationRunner.run()` - Set run_mode in step.options before execution

### Engine/PySCF Runner Layer
3. `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()` - Read run_mode from step.options, set allow_chkfile_init_guess in job.json
4. `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine` - Add `run_step_with_chain()` method (new)
5. `src/quantumvitas/engines/pyscf/runner.py::run_job()` - Read allow_chkfile_init_guess from job.json, pass to run_scf()
6. `src/quantumvitas/engines/pyscf/runner.py` - Add `run_job_chain()` function (new)
7. `src/quantumvitas/engines/pyscf/runner.py` - Add `_run_pyscf_chain_session()` helper (new, for one-session execution)
8. `src/quantumvitas/engine/base.py` - Add optional `run_step_with_chain()` to Engine interface (optional method)

### Tests
9. `tests/unit/test_pyscf_chain.py` - Unit tests for chain resolution (already created)
10. `tests/unit/test_pyscf_integration.py` - Unit tests for run_mode plumbing (add tests)
11. `tests/integration/test_pyscf_execution.py` - Integration tests for chain execution and init_guess behavior
12. `tests/unit/test_step_spec_storage.py` - NEW: Tests for step.yaml storage invariants (Task 3.5)

**Total: 12 files**

---

## Summary

All confusion items have clear resolution paths. No blocking questions remain. The implementation approach is:
- Use step.options to pass run_mode (minimal changes)
- Create PySCF-specific RunStep path with chain execution (preserves QE behavior)
- New run_job_chain() function for one-session execution (clear separation)
- Per-step artifact directories (matches spec requirement)
- Wire allow_chkfile_init_guess through job.json (already partially implemented)
- Engine-specific run_step_with_chain() method (optional, QE unchanged)

All options match the spec and require minimal changes while preserving QE/W90 behavior.

