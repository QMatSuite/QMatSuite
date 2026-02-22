# PySCF v0 Implementation Execution Plan

**Status**: Execution Plan (Final)  
**Engine Family**: `pyscf` (molecular quantum chemistry)  
**Target**: v0 Stable (scf, scf_analysis, scf_td, scf_mp2, scf_freq)  
**Last Updated**: 2025-01-10

---

## Execution Principles

**Ordering Strategy**:
1. **Lowest coupling first**: Implement steps that have minimal dependencies on other steps first
2. **Fastest feedback**: Implement and test incrementally to get feedback quickly
3. **Minimal refactoring risk**: Build on existing Phase 3C infrastructure, avoid large refactors

**Completion Criteria**: Each step is considered "done" when:
- Code is implemented and follows SSOT constraints
- Unit tests pass
- Integration tests pass (if applicable)
- No linter errors
- Documentation is updated (if needed)

---

## Step 1: Verify and Refine SCF Implementation (M0)

**Goal**: Verify Phase 3C SCF implementation matches final design and fix any issues.

**Why First**: This is the foundation. All downstream steps depend on SCF working correctly. Verifying/fixing SCF first ensures downstream steps have a solid base.

**Dependencies**: None (baseline)

**What to Implement**:
1. Verify `pyscf_scf` uses unified `method` parameter (`hf` or `dft`)
2. Verify checkpoint behavior matches conservative policy (no mf shim, only init_guess from chkfile)
3. Verify `step.yaml` does NOT contain structure payload
4. Verify structure (atoms, charge, spin, unit) comes from `calculation.yaml` (via structure_id)
5. Verify artifacts layout: per-step artifacts directory, cleared before each step run
6. Verify `basis` is in step.yaml parameters (not structure resource)
7. Verify `pyscf_scf` `results.json` includes `method` and `xc` fields (for downstream inference)

**Files to Touch**:
- `src/qmatsuite/engines/pyscf/runner.py` (verify/update `run_scf()`)
- `src/qmatsuite/workflow/registry.py` (verify step type spec)
- `src/qmatsuite/calculation/step_defaults.py` (verify defaults)
- `tests/integration/test_pyscf_execution.py` (verify/fix tests)

**Tests to Add/Verify**:
- Unit tests: SCF step type spec, parameter defaults, step.yaml structure
- Integration tests: Run SCF with `method=hf` and `method=dft`, verify checkpoint behavior, verify restart semantics
- **Numeric Validation Tests**:
  - Test system: H2/cc-pVDZ RHF
  - Golden value: **-1.1287000935564406 Hartree** (from PySCF Tutorial `user_guide.ipynb` Cell 4)
  - Tolerance: ±0.0001 Hartree
  - File: `tests/integration/test_pyscf_execution.py::TestPySCFScf`

**When Done**:
- All Phase 3C tests pass
- SCF checkpoint can be loaded as `init_guess` for rerun (no mf shim)
- Unified `method` parameter works for both HF and DFT
- No structure data in step.yaml
- Artifacts are written to per-step directories
- `results.json` includes `method` and `xc` fields for downstream inference

---

## Step 2: Implement Runner Helper for SCF Metadata Inference

**Goal**: Create a reusable helper function that reads SCF metadata (method, xc, checkpoint path) from upstream SCF step artifacts. This helper will be used by all downstream steps (analysis, td, mp2, freq).

**Why Second**: This is a critical infrastructure piece that all downstream steps need. Implementing it early ensures consistency and reduces duplication.

**Dependencies**: Step 1 (SCF implementation verified)

**What to Implement**:
1. Create helper function `_get_scf_metadata_from_upstream()` in `src/qmatsuite/engines/pyscf/runner.py`
   - Input: upstream step's artifacts directory path
   - Output: dict with `method`, `xc` (if DFT), `checkpoint_path`
   - Logic:
     - Read `results.json` from upstream step's artifacts directory
     - Extract `method` and `xc` (if present) from results.json
     - Construct checkpoint path: `artifacts_dir / "checkpoint.chk"`
     - Validate checkpoint file exists and is readable
     - Return dict
2. Update `run_mp2()` to use this helper (refactor existing code)
3. Add unit tests for the helper function

**Files to Touch**:
- `src/qmatsuite/engines/pyscf/runner.py` (add helper function, refactor `run_mp2()`)
- `tests/unit/test_pyscf_runner.py` (new file, test helper function)

**Tests to Add**:
- Unit tests: Test `_get_scf_metadata_from_upstream()` with valid/invalid inputs
  - Test: Valid SCF results.json with HF method
  - Test: Valid SCF results.json with DFT method (has xc field)
  - Test: Missing results.json → raises error
  - Test: Missing checkpoint.chk → raises error
  - Test: Invalid results.json format → raises error
  - File: `tests/unit/test_pyscf_runner.py::TestGetScfMetadata`

**When Done**:
- Helper function is implemented and tested
- `run_mp2()` uses the helper (refactored)
- All unit tests pass
- Helper function handles error cases gracefully (clear error messages)

---

## Step 3: Implement Analysis Step (M1)

**Goal**: Implement `pyscf_analysis` step type and `scf_analysis` workflow.

**Why Third**: Analysis is a simple property calculation (cheap, fast feedback). It depends only on SCF and exercises the SCF metadata inference helper from Step 2.

**Dependencies**: Step 1 (SCF), Step 2 (SCF metadata inference helper)

**What to Implement**:
1. **Step Type Registry** (`src/qmatsuite/workflow/registry.py`):
   - Add `pyscf_analysis` step type spec
   - `id`: `"analysis"`, `machine_type`: `"pyscf_analysis"`, `public_type`: `"analysis"`
   - `supports_incremental_skip`: `False`
2. **Workflow Materialization** (`src/qmatsuite/workflow/generalized_steps.py`):
   - Add `("pyscf", "analysis"): "pyscf_analysis"` to `MATERIALIZATION_MAP`
   - Update `materialize_public_step_key()` if needed
3. **Workflow Template** (`src/qmatsuite/workflow/templates.py`):
   - Add `scf_analysis` workflow template
   - `step_sequence`: `("scf", "analysis")`
4. **Step Defaults** (`src/qmatsuite/calculation/step_defaults.py`):
   - Add defaults for `pyscf_analysis`: `population_method="mulliken"`, `verbose=4`
   - **Do NOT include `scf_method`, `scf_xc`, `scf_chkfile`** (inferred by runner)
5. **Execution Engine** (`src/qmatsuite/engines/pyscf/runner.py`):
   - Implement `run_analysis()` function
   - Use `_get_scf_metadata_from_upstream()` to get SCF metadata
   - Load SCF checkpoint, rebuild mol/mf, rerun SCF kernel (conservative policy)
   - Compute dipole, population analysis, frontier orbitals
   - Write `results.json` and `stdout.txt`
   - Update `run_job()` to dispatch to `run_analysis()` for `pyscf_analysis` step type

**Files to Touch**:
- `src/qmatsuite/workflow/registry.py`
- `src/qmatsuite/workflow/generalized_steps.py`
- `src/qmatsuite/workflow/templates.py`
- `src/qmatsuite/calculation/step_defaults.py`
- `src/qmatsuite/engines/pyscf/runner.py`
- `tests/unit/test_pyscf_integration.py`
- `tests/integration/test_pyscf_execution.py`

**Tests to Add**:
- **Unit tests**:
  - Test: `materialize_public_step_key("analysis", "pyscf")` → `"pyscf_analysis"`
  - Test: `pyscf_analysis` step type exists in registry with correct properties
  - Test: `pyscf_analysis` has `supports_incremental_skip=False`
  - Test: `scf_analysis` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_analysis")` returns expected defaults (no scf_method/scf_xc)
  - File: `tests/unit/test_pyscf_integration.py::TestPySCFAnalysis`
- **Integration tests**:
  - Test: Run `scf_analysis` workflow on OH molecule (cc-pVDZ UHF)
    - Assert: SCF step produces checkpoint and results.json with `method` field
    - Assert: Analysis step reads checkpoint successfully (uses helper)
    - Assert: Analysis `results.json` contains dipole, population analysis, frontier orbitals
    - Assert: Dipole matches golden value (from PySCF Tutorial): [0.00000, 0.00000, 1.80400], tolerance: ±0.01
    - Assert: Mulliken charge (O) matches golden value: -0.323214025599, tolerance: ±0.01
  - Test: Analysis step fails if checkpoint missing (clear error message)
  - Test: Analysis step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py::TestPySCFAnalysis`

**When Done**:
- `pyscf_analysis` step type exists in registry
- `scf_analysis` workflow materializes correctly
- Analysis calculation runs successfully on OH molecule
- Analysis results.json contains dipole, population analysis, frontier orbitals
- Analysis step uses SCF metadata inference (does NOT read scf_method/scf_xc from step.yaml)
- Analysis step always reruns (incremental skip gating works)
- All tests pass (unit + integration)
- Numeric validation passes (dipole and Mulliken charges match golden values)

---

## Step 4: Implement Workflow Validation Infrastructure

**Goal**: Add workflow validation infrastructure to emit OK/WARNING/ERROR for physics rules. This infrastructure will be used by TD and MP2 workflows.

**Why Fourth**: This is needed before TD and MP2 implementations (which have validation rules). Implementing it early ensures validation is consistent across workflows.

**Dependencies**: Step 3 (Analysis) - but can be done in parallel if needed

**What to Implement**:
1. **Workflow Validation Function** (`src/qmatsuite/workflow/templates.py`):
   - Enhance `WorkflowService.validate_workflow()` to check PySCF-specific validation rules
   - Add validation for:
     - DFT → TDHF: ERROR (hard error, blocked)
     - DFT → MP2: WARNING (allowed but non-standard)
     - HF → MP2: OK (no warning)
   - Return `WorkflowIssue` objects with severity: `ERROR`, `WARNING`, `INFO`
2. **Validation Helper Functions**:
   - `_validate_td_workflow()`: Check DFT → TDHF error
   - `_validate_mp2_workflow()`: Check DFT → MP2 warning
   - These functions read upstream SCF step's results.json to get method/xc

**Files to Touch**:
- `src/qmatsuite/workflow/templates.py` (enhance `validate_workflow()`)
- `tests/unit/test_workflow_validation.py` (new file or add to existing)

**Tests to Add**:
- **Unit tests**:
  - Test: `scf_td` workflow with DFT SCF → ERROR (DFT → TDHF blocked)
  - Test: `scf_td` workflow with HF SCF → OK (no errors)
  - Test: `scf_mp2` workflow with DFT SCF → WARNING (allowed but non-standard)
  - Test: `scf_mp2` workflow with HF SCF → OK (no warnings)
  - File: `tests/unit/test_workflow_validation.py::TestPySCFWorkflowValidation`

**When Done**:
- Workflow validation infrastructure is in place
- Validation rules are implemented (DFT → TDHF error, DFT → MP2 warning)
- All unit tests pass
- Validation happens at workflow/materialization level (NOT in runner)

---

## Step 5: Implement TD Step (M2)

**Goal**: Implement `pyscf_td` step type and `scf_td` workflow. Unified TDDFT/TDHF with automatic backend selection.

**Why Fifth**: TD depends on workflow validation infrastructure from Step 4. It's more complex than analysis but simpler than freq (no Hessian calculation).

**Dependencies**: Step 1 (SCF), Step 2 (SCF metadata inference), Step 4 (Workflow validation)

**What to Implement**:
1. **Step Type Registry** (`src/qmatsuite/workflow/registry.py`):
   - Add `pyscf_td` step type spec
   - `id`: `"td"`, `machine_type`: `"pyscf_td"`, `public_type`: `"td"`
   - `supports_incremental_skip`: `False`
2. **Workflow Materialization** (`src/qmatsuite/workflow/generalized_steps.py`):
   - Add `("pyscf", "td"): "pyscf_td"` to `MATERIALIZATION_MAP`
3. **Workflow Template** (`src/qmatsuite/workflow/templates.py`):
   - Add `scf_td` workflow template
   - `step_sequence`: `("scf", "td")`
   - Use workflow validation from Step 4 (DFT → TDHF error)
4. **Step Defaults** (`src/qmatsuite/calculation/step_defaults.py`):
   - Add defaults for `pyscf_td`: `nroots=10`, `tda=False`, `conv_tol=1e-9`, `max_cycle=50`, `verbose=4`
   - **Do NOT include `scf_method`, `scf_xc`, `scf_chkfile`** (inferred by runner)
5. **Execution Engine** (`src/qmatsuite/engines/pyscf/runner.py`):
   - Implement `run_td()` function
   - Use `_get_scf_metadata_from_upstream()` to get SCF metadata
   - Load SCF checkpoint, rebuild mol/mf, rerun SCF kernel (conservative policy)
   - Backend selection (automatic, inferred from upstream SCF):
     - If upstream SCF `method == "dft"` → TDDFT backend
     - If upstream SCF `method == "hf"` → TDHF backend
   - Run TD calculation, extract results
   - Write `results.json` (include `method` field: `"tddft"` or `"tdhf"`) and `stdout.txt`
   - Update `run_job()` to dispatch to `run_td()` for `pyscf_td` step type

**Files to Touch**:
- `src/qmatsuite/workflow/registry.py`
- `src/qmatsuite/workflow/generalized_steps.py`
- `src/qmatsuite/workflow/templates.py`
- `src/qmatsuite/calculation/step_defaults.py`
- `src/qmatsuite/engines/pyscf/runner.py`
- `tests/unit/test_pyscf_integration.py`
- `tests/integration/test_pyscf_execution.py`

**Tests to Add**:
- **Unit tests**:
  - Test: `materialize_public_step_key("td", "pyscf")` → `"pyscf_td"`
  - Test: `pyscf_td` step type exists in registry with correct properties
  - Test: `pyscf_td` has `supports_incremental_skip=False`
  - Test: `scf_td` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_td")` returns expected defaults (no scf_method/scf_xc)
  - File: `tests/unit/test_pyscf_integration.py::TestPySCFTd`
- **Integration tests**:
  - Test: Run `scf_td` workflow with DFT SCF → TDDFT backend used
  - Test: Run `scf_td` workflow with HF SCF → TDHF backend used
  - Test: `scf_td` workflow validation blocks DFT → TDHF (hard error)
  - Test: TD results.json contains excitation energies, oscillator strengths
  - Test: TD results.json `method` field indicates correct backend (`"tddft"` or `"tdhf"`)
  - Test: TD step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py::TestPySCFTd`

**When Done**:
- `pyscf_td` step type exists in registry
- `scf_td` workflow materializes correctly
- TD calculation runs successfully (TDDFT and TDHF backends)
- TD step uses SCF metadata inference (does NOT read scf_method/scf_xc from step.yaml)
- Workflow validation blocks DFT → TDHF (hard error)
- TD step always reruns (incremental skip gating works)
- All tests pass (unit + integration)

---

## Step 6: Refine MP2 Implementation (M3)

**Goal**: Refine existing Phase 3C MP2 implementation to use SCF metadata inference helper and ensure it matches final design.

**Why Sixth**: MP2 is already implemented (Phase 3C), but needs refinement to use the SCF metadata inference helper and ensure it follows SSOT constraints.

**Dependencies**: Step 1 (SCF), Step 2 (SCF metadata inference), Step 4 (Workflow validation)

**What to Implement**:
1. **Refactor `run_mp2()`** (`src/qmatsuite/engines/pyscf/runner.py`):
   - Use `_get_scf_metadata_from_upstream()` helper (should already be done in Step 2)
   - Remove any `scf_method`, `scf_xc`, `scf_chkfile` parameters from step.yaml reading
   - Ensure MP2 step does NOT read these from step.yaml (inferred from upstream)
2. **Step Defaults** (`src/qmatsuite/calculation/step_defaults.py`):
   - Verify `pyscf_mp2` defaults do NOT include `scf_method`, `scf_xc`, `scf_chkfile`
3. **Workflow Validation** (`src/qmatsuite/workflow/templates.py`):
   - Ensure `scf_mp2` workflow uses validation from Step 4 (DFT → MP2 warning)

**Files to Touch**:
- `src/qmatsuite/engines/pyscf/runner.py` (refactor `run_mp2()` if needed)
- `src/qmatsuite/calculation/step_defaults.py` (verify defaults)
- `tests/integration/test_pyscf_execution.py` (verify/fix tests)

**Tests to Add**:
- **Integration tests**:
  - Test: `scf_mp2` workflow with HF SCF → OK (no warnings)
  - Test: `scf_mp2` workflow with DFT SCF → WARNING (allowed but non-standard)
  - Test: MP2 step uses SCF metadata inference (does NOT read scf_method/scf_xc from step.yaml)
  - Test: MP2 step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py::TestPySCFMp2`

**When Done**:
- MP2 implementation uses SCF metadata inference helper
- MP2 step does NOT read scf_method/scf_xc from step.yaml
- Workflow validation warns for DFT → MP2 (but allows execution)
- MP2 step always reruns (incremental skip gating works)
- All tests pass

---

## Step 7: Implement Freq Step (M4)

**Goal**: Implement `pyscf_freq` step type and `scf_freq` workflow. Fixed-geometry harmonic frequencies, ZPE, thermochemistry.

**Why Seventh (Last)**: Freq is the most complex step (Hessian calculation, expensive). It depends on all previous infrastructure and should be implemented last.

**Dependencies**: Step 1 (SCF), Step 2 (SCF metadata inference)

**What to Implement**:
1. **Step Type Registry** (`src/qmatsuite/workflow/registry.py`):
   - Add `pyscf_freq` step type spec
   - `id`: `"freq"`, `machine_type`: `"pyscf_freq"`, `public_type`: `"freq"`
   - `supports_incremental_skip`: `False`
2. **Workflow Materialization** (`src/qmatsuite/workflow/generalized_steps.py`):
   - Add `("pyscf", "freq"): "pyscf_freq"` to `MATERIALIZATION_MAP`
3. **Workflow Template** (`src/qmatsuite/workflow/templates.py`):
   - Add `scf_freq` workflow template
   - `step_sequence`: `("scf", "freq")`
4. **Step Defaults** (`src/qmatsuite/calculation/step_defaults.py`):
   - Add defaults for `pyscf_freq`: `thermo=False`, `temperature=298.15`, `pressure=101325`, `verbose=4`
   - **Do NOT include `scf_method`, `scf_xc`, `scf_chkfile`** (inferred by runner)
5. **Execution Engine** (`src/qmatsuite/engines/pyscf/runner.py`):
   - Implement `run_freq()` function
   - Use `_get_scf_metadata_from_upstream()` to get SCF metadata
   - Load SCF checkpoint, rebuild mol/mf, rerun SCF kernel (conservative policy)
   - Compute Hessian, frequencies, normal modes
   - Compute ZPE and thermochemistry (if `thermo=True`)
   - Write `results.json` and `stdout.txt`
   - Update `run_job()` to dispatch to `run_freq()` for `pyscf_freq` step type

**Files to Touch**:
- `src/qmatsuite/workflow/registry.py`
- `src/qmatsuite/workflow/generalized_steps.py`
- `src/qmatsuite/workflow/templates.py`
- `src/qmatsuite/calculation/step_defaults.py`
- `src/qmatsuite/engines/pyscf/runner.py`
- `tests/unit/test_pyscf_integration.py`
- `tests/integration/test_pyscf_execution.py`

**Tests to Add**:
- **Unit tests**:
  - Test: `materialize_public_step_key("freq", "pyscf")` → `"pyscf_freq"`
  - Test: `pyscf_freq` step type exists in registry with correct properties
  - Test: `pyscf_freq` has `supports_incremental_skip=False`
  - Test: `scf_freq` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_freq")` returns expected defaults (no scf_method/scf_xc)
  - File: `tests/unit/test_pyscf_integration.py::TestPySCFFreq`
- **Integration tests**:
  - Test: Run `scf_freq` workflow on H2O molecule
    - Assert: Freq results.json contains frequencies, normal modes, ZPE
    - Assert: Frequencies are positive (for stable molecule)
    - Assert: ZPE is positive
  - Test: Freq step with `thermo=True` computes thermochemistry
  - Test: Freq step uses SCF metadata inference (does NOT read scf_method/scf_xc from step.yaml)
  - Test: Freq step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py::TestPySCFFreq`

**When Done**:
- `pyscf_freq` step type exists in registry
- `scf_freq` workflow materializes correctly
- Freq calculation runs successfully on H2O molecule
- Freq results.json contains frequencies, normal modes, ZPE
- Freq step with `thermo=True` computes thermochemistry
- Freq step uses SCF metadata inference (does NOT read scf_method/scf_xc from step.yaml)
- Freq step always reruns (incremental skip gating works)
- All tests pass (unit + integration)

---

## Final Checklist

After completing all steps:

- [ ] All v0 workflows implemented: `scf`, `scf_analysis`, `scf_td`, `scf_mp2`, `scf_freq`
- [ ] All step types use SCF metadata inference (no scf_method/scf_xc/scf_chkfile in step.yaml)
- [ ] Workflow validation infrastructure in place (OK/WARNING/ERROR)
- [ ] All tests pass (unit + integration)
- [ ] Numeric validation passes (golden values from PySCF Tutorial)
- [ ] Documentation updated (catalog and roadmap)
- [ ] No linter errors
- [ ] Code follows SSOT constraints (step.yaml contains only step-specific parameters, no structure, no upstream metadata)

---

---

## Phase 3C: Runner Semantics + UI Alignment (NEW)

**Status**: 📋 Implementation Required  
**Goal**: Implement PySCF runner chain execution, dependency resolution, and UI behavior alignment (QE-style)

**Dependencies**: Phase 2 + Phase 3A/3B + existing PySCF v0 scaffolding

**Specification**: See `docs/design/PHASE3C_RUNNER_SPEC.md`

### Phase 3C Tasks

#### C1: Generalized Step Key "td"
- [ ] Add `"td"` to workflow templates (generalized key)
- [ ] Ensure QE materialization: `"td"` → existing QE TD step machine type (no rename)
- [ ] Ensure PySCF materialization: `"td"` → `pyscf_td`
- [ ] Update workflow templates to use `"td"` instead of `"tddft"`/`"tdhf"`
- [ ] Verify workflow detection and instantiation use generalized `"td"`

**Files to Touch**:
- `src/qmatsuite/workflow/templates.py` (add `scf_td` workflow with `"td"` key)
- `src/qmatsuite/workflow/generalized_steps.py` (add `("pyscf", "td"): "pyscf_td"` mapping)
- `src/qmatsuite/workflow/registry.py` (verify `pyscf_td` step type exists)

**Tests to Add**:
- Unit test: `materialize_public_step_key("td", "qe")` → existing QE TD machine type
- Unit test: `materialize_public_step_key("td", "pyscf")` → `"pyscf_td"`
- Unit test: `scf_td` workflow template uses `"td"` key
- File: `tests/unit/test_workflow_materialization_phase3b.py`

**When Done**:
- Generalized `"td"` key exists and materializes correctly for both QE and PySCF
- All unit tests pass

---

#### C2: Add Run Mode Plumbling (Incremental vs Full)
- [ ] Verify `run_mode` parameter exists in `CalculationRunner.run()` and `QMSService.run_calculation()` (already exists)
- [ ] Add UI dropdown for "Full Run" option (if not already present)
- [ ] Ensure `run_mode` reaches PySCF runner layer
- [ ] For QE: Preserve existing behavior (no change)
- [ ] For PySCF: Implement behavior differences (SCF init_guess control)

**Files to Touch**:
- `src/qmatsuite/calculation/runner.py` (verify `run_mode` handling)
- `src/qmatsuite/api.py` (verify `run_mode` passed through)
- `src/qmatsuite/engines/pyscf/runner.py` (add `run_mode` parameter handling)
- UI code (if separate, verify dropdown exists)

**Tests to Add**:
- Unit test: `run_mode="incremental"` vs `run_mode="full"` passed to runner
- Integration test: RunCalc(incremental) vs RunCalc(full) behavior difference
- File: `tests/integration/test_pyscf_execution.py`

**When Done**:
- `run_mode` parameter flows through service → runner → PySCF engine
- UI has "Full Run" dropdown option
- Tests verify parameter passing

---

#### C3: PySCF Runner Chain Execution
- [ ] Add `consumes_state` and `produces_state` to `StepTypeSpec` in registry
- [ ] Update PySCF step type specs:
  - `pyscf_scf`: `produces_state="mf"`, `consumes_state=None`
  - `pyscf_mp2`: `produces_state=None`, `consumes_state="mf"`
  - `pyscf_td`: `produces_state=None`, `consumes_state="mf"`
  - `pyscf_analysis`: `produces_state=None`, `consumes_state="mf"`
  - `pyscf_freq`: `produces_state=None`, `consumes_state="mf"`
- [ ] Implement dependency chain resolution:
  - Function: `_resolve_dependency_chain(target_step_ulid, calculation_steps)`
  - Returns: (chain_root_index, run_sequence_indices)
  - Uses nearest-provider rule (scan left for `produces_state`)
- [ ] Implement PySCF session execution:
  - Function: `_run_pyscf_chain(chain_steps, calculation, run_mode, target_step_ulid)`
  - One subprocess session, import PySCF once
  - Execute steps in order, build in-memory objects
  - Write artifacts per step (clear artifacts dir before each step)
- [ ] Implement SCF init_guess control:
  - Incremental mode: Allow `chkfile` init guess when present
  - Full mode OR RunStep(target=scf): Forbid `chkfile` init guess
- [ ] Ensure non-SCF steps always rerun (regardless of done flags)

**Files to Touch**:
- `src/qmatsuite/workflow/registry.py` (add `consumes_state`, `produces_state` to `StepTypeSpec`)
- `src/qmatsuite/engines/pyscf/runner.py` (add chain resolution and session execution)
- `src/qmatsuite/calculation/runner.py` (integrate PySCF chain execution for RunStep mode)
- `src/qmatsuite/engines/pyscf_engine.py` (if needed for engine interface)

**Tests to Add**:
- Unit test: Dependency chain resolution (nearest-provider rule)
- Unit test: Missing provider → HARD ERROR
- Unit test: SCF init_guess control (incremental vs full)
- Integration test: RunStep(mp2) resolves chain to scf, executes in one session
- Integration test: RunStep(scf) does NOT use chkfile init guess
- Integration test: RunCalc(incremental) uses chkfile init guess when present
- Integration test: RunCalc(full) does NOT use chkfile init guess
- File: `tests/unit/test_pyscf_runner.py` (new)
- File: `tests/integration/test_pyscf_execution.py`

**When Done**:
- Dependency chain resolution works correctly
- PySCF session execution runs steps in one process
- SCF init_guess control works (incremental vs full)
- Non-SCF steps always rerun
- All tests pass

---

#### C4: Step Spec Storage Verification
- [ ] Verify `step.yaml` does NOT contain structure data
- [ ] Verify SCF step.yaml contains SCF-relevant choices (method, xc, basis, etc.)
- [ ] Verify downstream steps do NOT redundantly store SCF selections
- [ ] Verify `chkfile` path is fixed convention (not stored as parameter)

**Files to Touch**:
- `src/qmatsuite/workflow/step_factory.py` (verify step.yaml generation)
- `src/qmatsuite/calculation/step_defaults.py` (verify defaults don't include structure)

**Tests to Add**:
- Unit test: `step.yaml` structure validation (no structure data)
- Unit test: SCF step.yaml contains method/xc/basis
- Unit test: Downstream steps do NOT contain scf_method/scf_xc
- File: `tests/unit/test_step_factory.py` or new test file

**When Done**:
- All step.yaml files follow SSOT constraints
- Tests verify structure is NOT in step.yaml
- Tests verify downstream steps don't duplicate SCF metadata

---

### Phase 3C Test Commands

**Targeted Tests** (run frequently):
```bash
# Unit tests
pytest tests/unit/test_workflow_materialization_phase3b.py -v
pytest tests/unit/test_pyscf_runner.py -v  # (new file)

# Integration tests
pytest tests/integration/test_pyscf_execution.py -v
```

**Regression Suite** (run at milestones):
```bash
# Workflow tests
pytest tests/unit/test_workflow.py -v

# Incremental run tests
pytest tests/integration/test_incremental_run.py -v

# Project snapshot tests
pytest tests/integration/test_project_snapshot.py -v

# PySCF integration tests
pytest tests/integration/test_pyscf_*.py -v
```

---

### Phase 3C Exit Conditions

Phase 3C is considered complete when:

- [ ] Generalized `"td"` key exists and materializes correctly for QE and PySCF
- [ ] Run mode plumbing works (incremental vs full)
- [ ] PySCF runner chain execution works (dependency resolution + session execution)
- [ ] SCF init_guess control works (incremental vs full)
- [ ] Step spec storage invariants verified (SSOT)
- [ ] All targeted tests pass
- [ ] Regression suite passes
- [ ] UI has "Full Run" dropdown option
- [ ] Documentation updated (spec doc exists)

---

**Document Status**: ✅ Complete (Execution Plan + Phase 3C)  
**Next Step**: Begin Phase 3C implementation (C1: Generalized Step Key "td")

