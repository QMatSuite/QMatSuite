# Phase 2: Workflow + Generalized Step Materialization Implementation Plan

**Version**: 1.0  
**Status**: Ready for Implementation  
**Date**: 2025-01-XX  
**Purpose**: Detailed implementation plan for Phase 2: workflow + generalized step materialization

---

## Core Invariants (Non-Negotiable)

1. **step.yaml is the ONLY execution SSOT**
   - step.yaml contains ONLY engine-specific execution data
   - step.yaml MUST NOT contain: workflow, generalized_step, engine_family, structure_kind

2. **calc.yaml MUST contain**
   - `structure_kind`: "periodic" | "molecule" (immutable once set)
   - `engine_family`: immutable string (immutable once set)
   These fields are IMMUTABLE once set.

3. **engine_family**
   - Loose, complementary toolchain namespace
   - Used ONLY for materialization (general_step → specific_step)
   - NOT used for execution dispatch
   - NOT written into step.yaml

4. **generalized steps**
   - Exist ONLY in UI / in-memory workflow definitions
   - Never written to disk
   - Each generalized step maps to AT MOST ONE engine-specific step within a given engine_family (0–1 rule)

5. **Engine-specific steps**
   - Have engine-prefixed step types (qe_*, w90_*, pyscf_*)
   - Are the ONLY steps written to step.yaml
   - Execution logic MUST remain unchanged

---

## Implementation Tasks

### STEP 1: Update / Finalize Implementation Plan ✅
- [x] Create Phase 2 implementation plan with all invariants
- [x] Mark what is implemented in Phase 2
- [x] Mark what is intentionally deferred

### STEP 2: Engine-Prefixed Step Types
**Goal**: Ensure all existing step types are explicitly engine-prefixed

**Files to modify**:
- `src/qmatsuite/workflow/registry.py`: Update `_STEP_TYPES` dict to use engine-prefixed IDs
- `src/qmatsuite/calculation/types.py`: Update `StepType` enum to use engine-prefixed names
- Update all references to step types throughout codebase

**Changes needed**:
- Rename "scf" → "qe_scf", "nscf" → "qe_nscf", etc.
- Keep existing execution logic unchanged
- Update step factory, workflow templates, CLI validation

**Backward compatibility**: Add mapping for old step types during load (if needed)

### STEP 3: Generalized Step Taxonomy
**Goal**: Define generalized steps and mapping (family, general) → specific

**Files to create/modify**:
- `src/qmatsuite/workflow/generalized_steps.py`: New file with generalized step definitions
- `src/qmatsuite/workflow/materialization.py`: New file with materialization logic

**Generalized steps to define**:
- SCF (self-consistent field)
- NSCF (non-self-consistent field)
- RELAX (atomic relaxation)
- VC_RELAX (variable-cell relaxation)
- BANDS (band structure)
- DOS (density of states)
- WANNIER_CONVERT (pw2wannier90 conversion)
- WANNIER (wannier90 MLWF optimization)
- PHONON (phonon calculation)
- ... (others as needed)

**Mapping structure**:
```python
MATERIALIZATION_MAP: Dict[Tuple[str, str], Optional[str]] = {
    # (engine_family, generalized_step) → engine_specific_step_type | None
    ("qe", "SCF"): "qe_scf",
    ("qe", "NSCF"): "qe_nscf",
    ("qe", "WANNIER_CONVERT"): "qe_pw2wannier90",
    ("qe", "WANNIER"): "w90_run",
    ("pyscf", "SCF"): "pyscf_scf",
    # Unsupported combinations return None
}
```

### STEP 4: Calc.yaml Metadata (structure_kind + engine_family)
**Goal**: Add structure_kind and engine_family to calculation model

**Files to modify**:
- `src/qmatsuite/core/models.py`: Add `structure_kind` and `engine_family` fields to `CalculationModel`
- `src/qmatsuite/cli/main.py`: Add structure_kind selection in `init_calculation_command`
- Update calc.yaml I/O to persist these fields

**Default logic**:
- periodic → default engine_family = "qe"
- molecule → default engine_family = "pyscf"

**Validation**: Ensure fields are immutable after creation

### STEP 5: Workflow Materialization
**Goal**: Materialize generalized steps → engine-specific steps

**Files to create/modify**:
- `src/qmatsuite/workflow/materialization.py`: Implement `materialize_workflow()` function
- `src/qmatsuite/workflow/templates.py`: Update `instantiate_workflow()` to use materialization

**Function signature**:
```python
def materialize_workflow(
    generalized_steps: List[str],
    engine_family: str,
) -> List[str]:
    """
    Materialize generalized steps to engine-specific steps.
    
    Args:
        generalized_steps: List of generalized step identifiers
        engine_family: Engine family identifier (e.g., "qe", "pyscf")
    
    Returns:
        List of engine-specific step type identifiers
    
    Raises:
        ValueError: If a generalized step is unsupported by the family
    """
```

### STEP 6: Backward Compatibility & Recovery
**Goal**: Handle existing calcs without engine_family metadata

**Files to modify**:
- `src/qmatsuite/core/models.py`: Add recovery logic in `CalculationModel.from_dict()`
- `src/qmatsuite/calculation/calculation.py`: Add inference logic

**Recovery logic**:
1. If all steps belong to one family → infer it
2. Otherwise → fallback to default family ("qe")

**Note**: This is best-effort only; no guarantees required

### STEP 7: Tests
**Goal**: Add backend tests for Phase 2 functionality

**Files to create**:
- `tests/workflow/test_generalized_steps.py`: Test generalized step definitions
- `tests/workflow/test_materialization.py`: Test materialization mapping (0–1 invariant)
- `tests/workflow/test_calc_metadata.py`: Test structure_kind and engine_family handling
- `tests/workflow/test_backward_compat.py`: Test backward compatibility recovery

**Test coverage**:
- Generalized → specific mapping (0–1 invariant)
- Workflow materialization by family
- Backward compatibility recovery
- Immutability of structure_kind and engine_family

**Note**: No UI tests; document manual UI verification steps instead

---

## Deferred Items

1. **UI Integration**: Document manual UI verification steps only (no UI code changes in Phase 2)
2. **Full PySCF support**: v0 focuses on QE primarily; PySCF skeleton exists but limited
3. **Multi-engine workflows**: v0 supports single engine_family per calculation only
4. **Workflow editing**: Workflow is immutable after materialization in v0

---

## Migration Notes

**Existing calculations**:
- Will be loaded with inferred engine_family (best-effort)
- No automatic migration required
- New calculations must specify structure_kind explicitly

**Step type references**:
- All code paths should use engine-prefixed step types going forward
- Legacy step types are mapped during load (if needed)

---

**End of Plan**

