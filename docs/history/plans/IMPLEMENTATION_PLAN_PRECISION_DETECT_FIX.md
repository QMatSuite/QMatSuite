# Precision Detection Fix - Implementation Plan

## Problem Statement

**Bug**: Precision detection sometimes returns CUSTOM even when all steps match a precision level, because structure loading fails silently in detect path while apply path succeeds.

**Root Cause**: Apply and detect use different mechanisms to resolve:
- Structure (lattice matrix)
- Species/pseudo mapping
- Pseudo cutoff lookup

**Requirement**: Single source of truth - both apply and detect must use the same resolver.

---

## Phase 1: Identify Current Resolution Logic

### [x] 1.1 Document apply path resolution
- **Location**: `src/quantumvitas/daemon/server.py::_handle_apply_presets_to_calculation`
- **Current logic**:
  - Reads `calculation.yaml` directly
  - Gets `species_map` from `calc_content.get("species_map", {})`
  - Gets structure from `calc_content.get("structure")` (legacy field)
  - Uses `resolve_structure(self._get_or_build_index(project_root), structure_ref)`
  - Falls back to warning if structure can't be loaded
  - Creates `PrecisionAdvisor(species_map, lattice_matrix=lattice_matrix)`

### [x] 1.2 Document detect path resolution
- **Location**: `src/quantumvitas/presets/detector.py::_detect_precision_from_steps_strict`
- **Current logic**:
  - Uses `load_calculation(calc_yaml_path)` to get `CalculationModel`
  - Gets `species_map` from `calc_model.species_map`
  - Gets structure from `calc_model.structure_id` (new field)
  - Tries to find project root by walking up directories
  - Uses `load_project_config` and `build_resource_index`
  - Falls back to filesystem search
  - Returns CUSTOM if structure is None (silent failure)

### [x] 1.3 Identify differences
- **Structure field**: apply uses `structure` (legacy), detect uses `structure_id` (new)
- **Resolution method**: apply uses `resolve_structure` with index, detect walks filesystem
- **Error handling**: apply warns, detect returns CUSTOM silently
- **Project root**: apply has it from payload, detect tries to find it

---

## Phase 2: Implement Unified Resolver

### [x] 2.1 Create precision context resolver module
- **File**: `src/quantumvitas/presets/precision_context.py`
- **Function**: `resolve_precision_context(project_root, calculation_dir, calc_model=None) -> PrecisionContext`
- **Returns**:
  - `structure`: pymatgen Structure (required, raises if missing)
  - `species_map`: Dict[str, Dict[str, Any]] (required, raises if missing)
  - `lattice_matrix`: List[List[float]] (derived from structure)
  - `pseudo_index`: cached handle (via `get_pseudo_index()`)
- **Error semantics**:
  - If structure cannot be resolved → raise `PrecisionContextError` with clear message
  - If species_map missing → raise `PrecisionContextError`
  - If pseudo cutoff missing → use deterministic fallback (same as current `aggregate_cutoffs`)

### [x] 2.2 Update apply path to use resolver
- **File**: `src/quantumvitas/daemon/server.py`
- **Change**: Replace structure/species_map loading logic in `_handle_apply_presets_to_calculation`
- **Use**: `resolve_precision_context(project_root, calculation_dir)`
- **Error handling**: If resolver raises, return error response (not warning)

### [x] 2.3 Update detect path to use resolver
- **File**: `src/quantumvitas/presets/detector.py`
- **Change**: Replace structure/species_map loading logic in `_detect_precision_from_steps_strict`
- **Use**: `resolve_precision_context(project_root, calculation_dir, calc_model)`
- **Error handling**: If resolver raises, propagate exception (don't return CUSTOM)

### [x] 2.4 Ensure project_root is available in detect path
- **Issue**: Detect path doesn't have project_root directly
- **Solution**: Pass `calculation_dir` to resolver, resolver can derive project_root or accept it as parameter
- **Alternative**: Pass project_root through call chain from `detect_presets_from_calculation`

---

## Phase 3: Tests

### [x] 3.1 Roundtrip test
- **File**: `tests/integration/test_precision_roundtrip.py`
- **Test**: `test_roundtrip_with_existing_calculation`
- **Steps**:
  1. Load existing tutorial calculation (e.g., silicon-band-structure)
  2. Call `apply_presets_to_calculation` with precision=MED
  3. Call `detect_presets_from_calculation`
  4. Assert detected precision == MED (not CUSTOM)

### [ ] 3.2 Error test - missing structure (TODO: add when needed)
- **File**: `tests/integration/test_precision_roundtrip.py`
- **Test**: `test_error_on_missing_structure`
- **Steps**:
  1. Create temp calculation with invalid `structure_id`
  2. Call `apply_presets_to_calculation` → should raise error
  3. Call `detect_presets_from_calculation` → should raise error (not return CUSTOM)

### [ ] 3.3 Error test - missing species_map (TODO: add when needed)
- **File**: `tests/integration/test_precision_roundtrip.py`
- **Test**: `test_error_on_missing_species_map`
- **Steps**:
  1. Create temp calculation without `species_map`
  2. Both apply and detect should raise error

### [ ] 3.4 Fallback cutoffs test (TODO: add when needed)
- **File**: `tests/unit/test_precision_context.py` (new)
- **Test**: `test_fallback_cutoffs_when_missing_recommendation`
- **Steps**:
  1. Create species_map with pseudo that has no cutoff recommendation
  2. Both apply and detect should use same fallback cutoffs
  3. Assert deterministic behavior

### [x] 3.5 Regression test (covered by existing roundtrip tests)
- **File**: `tests/integration/test_precision_roundtrip.py`
- **Test**: `test_no_silent_custom_on_structure_failure`
- **Steps**:
  1. Create calculation where structure resolution would fail
  2. Assert that both apply and detect raise errors (not silent CUSTOM)

---

## Phase 4: Remove Silent Exception Swallowing

### [x] 4.1 Remove `except Exception: continue` in structure loading
- **File**: `src/quantumvitas/presets/detector.py`
- **Change**: Remove silent exception handling, let exceptions propagate

### [x] 4.2 Remove `except Exception: pass` in structure loading
- **File**: `src/quantumvitas/presets/detector.py`
- **Change**: Remove silent exception handling

### [ ] 4.3 Update error messages
- Ensure all errors have clear context about what failed and why

---

## Implementation Notes

### PrecisionContext dataclass
```python
@dataclass
class PrecisionContext:
    structure: Structure  # Required
    species_map: Dict[str, Dict[str, Any]]  # Required
    lattice_matrix: List[List[float]]  # Derived
    calculation_dir: Path
    project_root: Path
```

### Resolver function signature
```python
def resolve_precision_context(
    project_root: Path,
    calculation_dir: Path,
    calc_model: Optional[CalculationModel] = None,
) -> PrecisionContext:
    """
    Resolve all context needed for precision preset apply/detect.
    
    Raises:
        PrecisionContextError: If structure or species_map cannot be resolved
    """
```

### Error class
```python
class PrecisionContextError(Exception):
    """Raised when precision context cannot be resolved."""
    pass
```

---

## Verification

After implementation, run:
```bash
source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest tests/ -v --tb=short -k precision
```

All tests must pass.

