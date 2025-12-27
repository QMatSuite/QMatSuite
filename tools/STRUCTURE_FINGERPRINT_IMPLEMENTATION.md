# Structure Fingerprint Implementation Summary

## Completed Tasks

### Task A: Structure Fingerprint Module ✅
- **File**: `src/quantumvitas/core/structure_fingerprint.py`
- **Functions**:
  - `canonicalize_structure_for_identity()` - Wraps to [-WRAP_TOL, 1-WRAP_TOL) then snaps to [0,1)
  - `structure_fingerprint()` - Quantizes with tol=1e-5, sorts sites, hashes with SHA256
  - `structures_semantically_equal()` - Verification helper with tol=1e-5

### Task A2: Fingerprint Storage ✅
- Fingerprint stored in structure metadata (`__qv_meta__["fingerprint"]`)
- Survives snapshot export/import (metadata is preserved in JSON structure files)

### Task A3: QVService Fingerprint Dedup ✅
- **`QVService.import_structure()`**: Computes fingerprint, checks existing structures, reuses if match found
- **`QVService.import_step_from_qe_input()`**: Uses fingerprint for dedup (with samefile fallback for optimization)

### Task B: Multi-Structure Calculations ✅
- **`build_calculation_from_qe_inputs()`**: Removed single structure_id enforcement
- Steps can now have different structure_ids (enables relax/vc-relax flows naturally)

### Task C: Global Folder Import API ✅
- **File**: `src/quantumvitas/calculation/folder_import.py`
- **Function**: `materialize_project_from_qe_input_folder()`
- Discovers .in files, sorts by execution order, imports via QVService, exports to snapshot

## Remaining Tasks

### Task C (continued): Refactor tools/import_tutorial_datasets.py
- Replace `materialize_project_from_input_folder()` with call to global API
- Keep dataset discovery, pseudo mapping, demo manifest generation
- Simplify to thin glue layer

### Task D: Strengthen Verify
- Add round-trip regeneration check in `--verify` mode
- Regenerate .in from step specs, compare semantically
- Verify ATOMIC_SPECIES presence, no placeholders, no structure cards in step.cards
- Write regenerated inputs to `generated_inputs/` for inspection

### Task E: Tests
- Fingerprint stability tests (tiny perturbations, unit/representation stability)
- QVService dedup behavior tests
- Multi-structure calculation tests

## Key Design Decisions

1. **Fingerprint quantization**: tol=1e-5 for both lattice (Å) and fractional coords
2. **Canonicalization**: Uses WRAP_TOL=1e-4, then snaps to [0,1) for fingerprinting
3. **Dedup scope**: Within single project only (not across projects)
4. **Multi-structure**: Each step can reference different structure (enables relax flows)

## Files Modified

1. `src/quantumvitas/core/structure_fingerprint.py` (NEW)
2. `src/quantumvitas/api.py` (updated import_structure, import_step_from_qe_input)
3. `src/quantumvitas/calculation/importers.py` (removed single structure_id enforcement)
4. `src/quantumvitas/calculation/folder_import.py` (NEW)

## Next Steps

1. Refactor tools script to use global API
2. Add comprehensive tests
3. Strengthen verify with round-trip checks

