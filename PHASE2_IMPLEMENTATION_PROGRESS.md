# Phase 2 Implementation Progress

**Status**: Core implementation complete, testing in progress  
**Date**: 2025-01-XX

## Completed Tasks

### 1. Engine-Prefixed Step Types ✅
- Updated `src/quantumvitas/workflow/registry.py` to use engine-prefixed step types (qe_*, w90_*, pyscf_*)
- Added backward compatibility mapping in `StepTypeRegistry.get()` and `has()` methods
- All step types now consistently use engine prefixes

### 2. Generalized Step Taxonomy ✅
- Created `src/quantumvitas/workflow/generalized_steps.py` with:
  - `GeneralizedStep` enum defining engine-agnostic physical operations
  - `MATERIALIZATION_MAP` for (engine_family, generalized_step) → engine_specific_step_type
  - `materialize_step()` and `materialize_workflow()` functions
  - `dematerialize_step()` and `dematerialize_to_generalized_step()` for reverse mapping
  - Support functions for listing supported steps per family

### 3. Calc.yaml Metadata (structure_kind + engine_family) ✅
- Updated `src/quantumvitas/core/models.py::CalculationModel` to include:
  - `structure_kind: Optional[str]` (periodic | molecule)
  - `engine_family: Optional[str]` (qe | pyscf | etc.)
- Added `to_dict()` serialization for these fields
- Added `from_dict()` with backward compatibility recovery:
  - `_infer_engine_family_from_steps()` function for best-effort inference
  - Defaults: periodic → qe, molecule → pyscf

### 4. Workflow Materialization ✅
- Updated `src/quantumvitas/workflow/templates.py`:
  - Workflow templates now use generalized steps (SCF, NSCF, DOS, etc.)
  - `instantiate_workflow()` materializes generalized steps to engine-specific steps
  - `detect_workflow()` maps engine-specific steps back to generalized steps for matching
- Added BANDS_POST generalized step for bands.x post-processing

### 5. CLI Updates ✅
- Updated `src/quantumvitas/cli/main.py`:
  - `KNOWN_STEP_TYPES` now includes both engine-prefixed and legacy names
  - `init_calculation_command()` adds structure_kind and engine_family to calc.yaml (defaults to periodic/qe)

### 6. Step Defaults Backward Compatibility ✅
- Updated `src/quantumvitas/calculation/step_defaults.py::get_default_step_params()`:
  - Supports both engine-prefixed (qe_scf) and legacy (scf) step type names
  - Maps engine-prefixed names to legacy defaults

## Remaining Tasks

### 1. Tests
- [ ] Add unit tests for generalized step materialization
- [ ] Add unit tests for backward compatibility recovery
- [ ] Add integration tests for workflow instantiation with materialization
- [ ] Update existing tests that reference legacy step types

### 2. StepType Enum (Optional)
- [ ] Consider updating `StepType` enum values to engine-prefixed names
- [ ] Or add mapping layer if enum values need to stay as-is

### 3. Structure Kind Inference
- [ ] Implement actual structure inspection to determine structure_kind
- [ ] Currently defaults to "periodic" for all calculations

### 4. Documentation
- [ ] Update workflow documentation to reflect generalized steps
- [ ] Document materialization behavior and 0-1 mapping rule

## Key Files Modified

- `src/quantumvitas/workflow/registry.py`: Engine-prefixed step types, backward compat mapping
- `src/quantumvitas/workflow/generalized_steps.py`: **NEW** - Generalized step taxonomy and materialization
- `src/quantumvitas/workflow/templates.py`: Updated to use generalized steps, materialization logic
- `src/quantumvitas/core/models.py`: Added structure_kind and engine_family fields
- `src/quantumvitas/cli/main.py`: Updated KNOWN_STEP_TYPES, added structure_kind/engine_family to calc creation
- `src/quantumvitas/calculation/step_defaults.py`: Backward compatibility for engine-prefixed step types

## Architecture Notes

### Invariants Enforced

1. **step.yaml is ONLY SSOT**: ✅ Verified - no workflow/generalized_step written to step.yaml
2. **calc.yaml contains structure_kind and engine_family**: ✅ Implemented - immutable metadata fields
3. **engine_family used only for materialization**: ✅ Implemented - not written to step.yaml
4. **Generalized steps never written to disk**: ✅ Enforced - materialization happens before step creation
5. **0-1 mapping rule**: ✅ Enforced - `materialize_step()` returns single step or None

### Backward Compatibility

- Legacy step types (scf, nscf, etc.) are mapped to engine-prefixed names during lookup
- Old calc.yaml files without structure_kind/engine_family are handled with best-effort inference
- Step defaults support both legacy and engine-prefixed names

### Known Limitations

1. **Structure kind inference**: Currently defaults to "periodic" for all calculations. Actual structure inspection not yet implemented.
2. **StepType enum**: Still uses legacy names. Enum values could be updated, but this is a larger refactoring.
3. **Workflow detection**: May not work perfectly for old workflows that used legacy step types, but should be handled by dematerialization.

## Next Steps

1. Add comprehensive tests for materialization and backward compatibility
2. Run full test suite to identify any breakages
3. Consider updating StepType enum if needed
4. Implement actual structure kind inference

---

**End of Progress Report**

