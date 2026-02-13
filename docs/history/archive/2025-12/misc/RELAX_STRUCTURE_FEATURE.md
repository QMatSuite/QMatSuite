# Relax/Vc-Relax Structure Extraction Feature

## Summary

This feature allows users to extract the final relaxed structure from QE relax/vc-relax step outputs and save it as a new Structure resource in the project. The feature follows strict architectural constraints:

- **ULID-only DAG**: All cross-resource references use ULIDs only
- **Geometry canonization**: Structures are canonized exactly once at creation time using the existing `canonicalize_structure_in_place()` function
- **No automatic creation**: Structures are only created when the user explicitly clicks "Save as new Structure"
- **Idempotent saves**: Repeated saves return the same structure ULID

## Implementation Details

### Backend Changes

1. **Step Types** (`src/quantumvitas/calculation/types.py`):
   - Added `RELAX = "relax"` and `VC_RELAX = "vc-relax"` to `StepType` enum

2. **Geometry Parsing** (`src/quantumvitas/calculation/geometry.py`):
   - `read_final_geometry_from_output_text(text: str) -> (QEGeometrySnapshot, species: list[str])`:
     - Parses the LAST "Begin final coordinates ... End final coordinates" block from QE output
     - Extracts alat (from CELL_PARAMETERS or celldm(1) earlier in output)
     - Extracts 3x3 cell matrix (dimensionless, multiples of alat)
     - Extracts atomic positions (dimensionless, multiples of alat)
     - Returns species list in order
   
   - `structure_from_qe_geometry_snapshot(snapshot, species) -> pymatgen Structure`:
     - Converts QEGeometrySnapshot to pymatgen Structure
     - **CRITICAL**: Applies canonization via `canonicalize_structure_in_place()` exactly once
     - This ensures the structure follows the same canonization path as structures loaded from JSON

3. **Step Results** (`src/quantumvitas/calculation/results.py`):
   - Added `produced_structure_ulid: Optional[str]` field to `StepResultSummary`
   - Serialized in `to_dict()` method

4. **API Service** (`src/quantumvitas/api.py`):
   - `get_relax_final_structure_preview()`: Preview-only RPC (no side effects)
     - Validates step type is relax/vc-relax
     - Finds output file in calculation/raw/
     - Parses final geometry
     - Returns preview payload (cell, species, positions, volume)
   
   - `save_relax_final_structure()`: Save RPC (idempotent)
     - Checks step YAML for existing `produced_structure_ulid` (idempotency)
     - Parses final geometry
     - Creates Structure via canonical path (with canonization)
     - Writes structure JSON with provenance (parent_structure_ulid, source_calculation_ulid, source_step_ulid)
     - Updates step YAML with `produced_structure_ulid`
     - Adds structure to project config
     - Updates registry

5. **Daemon RPC Handlers** (`src/quantumvitas/daemon/server.py`):
   - `_handle_get_relax_final_structure_preview()`: Preview handler
   - `_handle_save_relax_final_structure()`: Save handler (rebuilds registry after save)

### Frontend Changes

1. **TypeScript Types** (`gui/src/types/qv.ts`):
   - Added `get_relax_final_structure_preview` and `save_relax_final_structure` to `QVCommandMap`

2. **RPC Client Hook** (`gui/src/hooks/useQVClient.ts`):
   - Added `getRelaxFinalStructurePreview()` and `saveRelaxFinalStructure()` methods

3. **Step Detail Panel** (`gui/src/components/panels/StepDetailPanel.tsx`):
   - Added "Relaxed Structure" section (only visible for relax/vc-relax steps)
   - Loads preview on step detail fetch (lazy, no side effects)
   - Shows preview info (n_atoms, volume)
   - "Save as new Structure" button (disabled if calculation has no structure_id)
   - Shows success/error messages
   - Idempotent: repeated clicks return existing structure

### Tests

1. **Unit Tests** (`tests/unit/test_relax_structure_extraction.py`):
   - `test_read_final_geometry_from_output_text()`: Parses real QE output
   - `test_structure_from_qe_geometry_snapshot()`: Verifies canonization is applied
   - `test_read_final_geometry_handles_multiple_blocks()`: Selects LAST block
   - `test_read_final_geometry_raises_on_missing_block()`: Error handling
   - `test_read_final_geometry_handles_alat_without_explicit_value()`: Extracts alat from elsewhere

2. **Integration Tests** (`tests/integration/test_relax_structure_save.py`):
   - `test_save_relax_structure_idempotency()`: Verifies idempotent behavior

## Files Changed

### Python Backend
- `src/quantumvitas/calculation/types.py`: Added RELAX, VC_RELAX step types
- `src/quantumvitas/calculation/geometry.py`: Added parser and structure converter
- `src/quantumvitas/calculation/results.py`: Added `produced_structure_ulid` field
- `src/quantumvitas/api.py`: Added preview and save RPC methods
- `src/quantumvitas/daemon/server.py`: Added RPC handlers

### TypeScript Frontend
- `gui/src/types/qv.ts`: Added RPC type definitions
- `gui/src/hooks/useQVClient.ts`: Added RPC client methods
- `gui/src/components/panels/StepDetailPanel.tsx`: Added "Relaxed Structure" UI section

### Tests
- `tests/unit/test_relax_structure_extraction.py`: Parser tests
- `tests/integration/test_relax_structure_save.py`: Idempotency test

## Manual Testing Instructions

1. **Create a relax/vc-relax step**:
   - Create a calculation with a structure
   - Add a step with `step_type: "relax"` or `"vc-relax"`
   - Run the step to completion

2. **View step detail**:
   - Open the step in Step Detail Panel
   - Scroll to "Relaxed Structure" section
   - Verify preview shows: "Final structure detected" with atom count and volume

3. **Save structure**:
   - Click "Save as new Structure" button
   - Verify success message appears
   - Check Structures panel - new structure should appear
   - Click "Save as new Structure" again - should show "already exists" message

4. **Verify structure**:
   - Open the saved structure
   - Verify it matches the final coordinates from QE output
   - Check structure JSON has `extra.relax_provenance` with ULIDs

## Architecture Compliance

✅ **ULID-only DAG**: All references use ULIDs (parent_structure_ulid, source_calculation_ulid, source_step_ulid)

✅ **Geometry canonization**: Structures go through `canonicalize_structure_in_place()` exactly once at creation

✅ **No automatic creation**: Preview is lazy-loaded, save requires explicit user action

✅ **Idempotent saves**: Step YAML stores `produced_structure_ulid`, repeated saves return existing ULID

✅ **String-only storage**: Structure JSON stores raw pymatgen format (no type coercion)

✅ **Python parsing**: All QE output parsing is in Python, UI only renders preview

