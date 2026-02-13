# Phase 3A + 3B Implementation Plan

**Scope**: Calc identity immutability + best-effort recovery (3A) + Workflow materialization by engine_family (3B)

## Phase 3A: Calc Identity Immutability + Best-Effort Recovery

### A1. Central Identity Inference Function
- [ ] Create `src/quantumvitas/core/calc_identity.py` with:
  - `infer_calculation_identity(calc_dir: Path, steps: List[CalculationStepEntry]) -> Tuple[Optional[str], Optional[str]]`
    - Infers (structure_kind, engine_family) from steps
    - Uses MACHINE step types from step.yaml if calculation.yaml steps not available
    - Returns (structure_kind, engine_family) or (None, None) if inference fails
  - Helper: `_infer_engine_family_from_machine_types(machine_types: List[str]) -> Optional[str]`
    - Analyzes machine type prefixes (qe_, pyscf_, w90_)
    - Returns single family if all steps share one prefix, None if mixed/unknown
  - Helper: `_infer_structure_kind_from_engine_family(engine_family: str) -> str`
    - pyscf → molecule, else → periodic

### A2. Identity Recovery in CalculationModel.from_dict()
- [ ] Update `src/quantumvitas/core/models.py`:
  - Replace current `_infer_engine_family_from_steps()` logic with call to `infer_calculation_identity()`
  - When structure_kind/engine_family missing, call inference
  - Store inferred values in CalculationModel (but don't write to YAML yet)

### A3. Identity Recovery Hook in Calculation Loading
- [ ] Create `ensure_calculation_identity(calc_dir: Path, project_root: Optional[Path] = None) -> None`:
  - Loads calculation.yaml if exists
  - If structure_kind/engine_family missing, infers from steps
  - Writes inferred values back to calculation.yaml if file exists and is writable
  - Must not crash on errors (best-effort)
- [ ] Hook into:
  - `Calculation.from_yaml()` - call after loading, before returning
  - `QVService` calculation loading paths (via `ensure_calculation_identity()`)
  - Any other entry points that load calculations

### A4. Immutability Enforcement
- [ ] Update `save_calculation()` or `CalculationModel.to_dict()`:
  - Add check: if calculation.yaml exists, load existing values
  - Compare existing structure_kind/engine_family with new values
  - If changed and not None, raise ValueError with clear message
  - Only allow setting if current values are None (first-time write)
- [ ] Ensure all save paths go through this check:
  - `save_calculation()` in `models.py`
  - `QVService` methods that modify calculations
  - CLI/daemon paths

### A5. Tests for Phase 3A
- [ ] Create `tests/unit/test_calc_identity.py`:
  - [ ] `test_infer_identity_from_qe_steps()` - infers qe/periodic
  - [ ] `test_infer_identity_from_pyscf_steps()` - infers pyscf/molecule
  - [ ] `test_infer_identity_mixed_family_returns_none()` - mixed steps return None
  - [ ] `test_legacy_calc_loads_with_recovery()` - legacy calc loads, infers, writes back
  - [ ] `test_identity_immutability_rejects_change()` - changing identity raises error
  - [ ] `test_identity_immutability_allows_first_set()` - None → value is allowed
  - [ ] `test_ensure_identity_recovery_writes_back()` - recovery writes to calculation.yaml

## Phase 3B: Workflow Materialization by engine_family

### B1. Update Materialization to Use PUBLIC Step Keys
- [ ] Review `src/quantumvitas/workflow/generalized_steps.py`:
  - Confirm `materialize_workflow()` works with PUBLIC step keys (lowercase strings like "scf", not GeneralizedStep enum)
  - If needed, add helper: `materialize_public_step(public_step: str, engine_family: str) -> Optional[str]`
    - Converts public step key (e.g., "scf") → GeneralizedStep enum → machine type
  - Ensure 0-1 mapping invariant (each public step maps to at most one machine type)

### B2. Update Workflow Templates
- [ ] Verify `src/quantumvitas/workflow/templates.py`:
  - Templates already use PUBLIC step keys (lowercase) - confirm
  - Document that templates use PUBLIC keys, materialization converts to MACHINE

### B3. Update instantiate_workflow() to Use Materialization
- [ ] Update `WorkflowService.instantiate_workflow()` in `templates.py`:
  - Replace direct registry lookup with `materialize_workflow()` call
  - Use PUBLIC step keys from template.step_sequence
  - Materialize to MACHINE step types using engine_family
  - Handle unsupported steps: raise clear ValueError (not crash silently)
  - Keep backward compatibility: return created step paths (PUBLIC types for tests if needed)

### B4. Update Workflow Detection
- [ ] Verify `WorkflowService.detect_workflow()`:
  - Uses `dematerialize_to_generalized_step()` correctly
  - Converts MACHINE types from step.yaml → PUBLIC types for matching

### B5. Add Materialization Validation
- [ ] Create `validate_materialization(public_steps: List[str], engine_family: str) -> List[str]`:
  - Returns list of unsupported PUBLIC step keys
  - Used for UI to show disabled steps with tooltips

### B6. Tests for Phase 3B
- [ ] Update `tests/workflow/test_generalized_steps.py`:
  - [ ] Add test: `test_materialize_qe_workflow()` - PUBLIC → MACHINE mapping for QE
  - [ ] Add test: `test_materialize_unsupported_step()` - unsupported step returns None/raises
  - [ ] Add test: `test_materialize_wannier_workflow()` - wannier workflow materialization
- [ ] Update `tests/unit/test_workflow.py`:
  - [ ] Verify `test_instantiate_scf_workflow()` still passes (may need updates)
  - [ ] Add test: `test_instantiate_workflow_uses_engine_family()` - materialization uses engine_family
  - [ ] Add test: `test_instantiate_workflow_unsupported_step()` - unsupported step raises error

## Integration & Regression

### C1. Run Regression Tests (Mid-way, after Phase 3A)
- [ ] `pytest tests/unit/test_workflow.py -v`
- [ ] `pytest tests/integration/test_incremental_run.py -v`
- [ ] `pytest tests/unit/test_project_snapshot.py -v`
- [ ] `pytest tests/unit/test_calculation_importers.py -v`
- [ ] Fix any regressions

### C2. Run Full Test Suite (End)
- [ ] `pytest tests/unit/test_workflow.py -v`
- [ ] `pytest tests/integration/test_incremental_run.py -v`
- [ ] `pytest tests/unit/test_project_snapshot.py -v`
- [ ] `pytest tests/unit/test_calculation_importers.py -v`
- [ ] `pytest tests/workflow/test_generalized_steps.py -v`
- [ ] `pytest tests/unit/test_calc_identity.py -v` (new tests)

## Documentation

### D1. Update PHASE2_COMPAT_NOTES.md
- [ ] Add "Phase 3A/3B Additions" section:
  - Identity immutability enforcement
  - Best-effort recovery behavior
  - Workflow materialization by engine_family
  - PUBLIC → MACHINE step key mapping

## Files to Modify

1. `src/quantumvitas/core/calc_identity.py` (NEW)
2. `src/quantumvitas/core/models.py` (A2, A4)
3. `src/quantumvitas/calculation/calculation.py` (A3)
4. `src/quantumvitas/workflow/templates.py` (B3)
5. `src/quantumvitas/workflow/generalized_steps.py` (B1, B5)
6. `tests/unit/test_calc_identity.py` (NEW, A5)
7. `tests/workflow/test_generalized_steps.py` (B6)
8. `tests/unit/test_workflow.py` (B6)
9. `PHASE2_COMPAT_NOTES.md` (D1)

## Progress Tracking

- [ ] A1: Central identity inference function
- [ ] A2: Identity recovery in CalculationModel
- [ ] A3: Identity recovery hook
- [ ] A4: Immutability enforcement
- [ ] A5: Phase 3A tests
- [ ] B1: Materialization using PUBLIC keys
- [ ] B2: Verify workflow templates
- [ ] B3: Update instantiate_workflow()
- [ ] B4: Verify workflow detection
- [ ] B5: Materialization validation
- [ ] B6: Phase 3B tests
- [ ] C1: Mid-way regression tests
- [ ] C2: Final regression tests
- [ ] D1: Documentation

