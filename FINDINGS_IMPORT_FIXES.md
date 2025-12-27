# Findings: Import Architecture and LR/TDDFT Fix

## Where calculation.structure_id is stored and used

- **Storage**: `calculation.structure_id` is stored in `calculation.yaml` as a ULID (canonical reference). The `CalculationModel` class (`src/quantumvitas/core/models.py`) has `structure_id: Optional[str]` field that persists to YAML via `to_dict()`.

- **Usage during run/export**:
  - `api.py:run_step()` (line 1216-1226): Loads calculation, reads `calculation.structure_id`, then calls `require_structure(project_root, calculation.structure_id)` to resolve the structure for step execution.
  - `snapshot.py:export_project_to_snapshot()` (line 311-314): Exports `calculation.structure_id` to snapshot YAML.
  - Structure resolution follows DAG model: steps inherit structure from calculation, not from step YAML.

## Why step YAML does not contain structure_id (ID-only DAG model)

- **Design principle**: Steps are part of a calculation DAG where the calculation owns the structure reference. Steps should not duplicate this reference.
- **Implementation**: `StructureStepSpec.to_dict()` (line 167-198 in `structure_steps.py`) explicitly excludes `structure_id`, `parent_calculation_id`, and `structure` fields from YAML serialization.
- **Runtime resolution**: When a step needs structure, it resolves via `calculation.structure_id` through `_resolve_structure_for_spec()` which checks calculation.yaml first (line 707-765 in `structure_steps.py`).

## Where post-processing step generation branches away from structure-based generation

- **Branch point**: `generate_qe_input_from_spec()` in `structure_steps.py` (line 311-327).
- **Condition**: Checks if `step_type_lower in POST_PROCESSING_STEP_TYPES` (line 325).
- **Branch behavior**: 
  - If post-processing (dos, bands, projwfc, etc.): calls `_generate_postprocessing_input()` which creates QEInput with only namelist parameters, no structure cards.
  - Otherwise: calls `generate_qe_input_from_structure()` which builds full structure-based input with ATOMIC_POSITIONS, CELL_PARAMETERS, etc.
- **Note**: Even post-processing steps currently require a `structure: PMGStructure` parameter in the function signature, but it's not used for post-processing steps.

## Where demo import currently fails for LR/TDDFT and why

- **Failure location**: `build_step_spec_from_qe_input()` in `importers.py` (line 138-158).
- **Current behavior**: 
  - Line 140: Checks `qe_input_has_structure(qe_input)` (this helper already exists and works correctly).
  - Line 157-158: If `has_structure` is True, calls `structure_from_qe_input(qe_input)`.
  - **Problem**: For LR/TDDFT inputs that have no structure, `has_structure` correctly returns False, but the code path still tries to set `structure_id = None` which is fine, BUT the issue is in `materialize_project_from_qe_input_folder()` which may not handle structure-less steps properly when determining the calculation's structure_id.

- **Root cause in folder_import.py**:
  - The global API `materialize_project_from_qe_input_folder()` (line 52-285) tries to find a reference structure file (line 112-149), but if ALL files are structure-less (e.g., pure LR/TDDFT folder), it will fail.
  - When importing steps via `service.import_step_from_qe_input()` (line 260-265), structure-less steps should succeed, but the calculation needs a structure_id from the FIRST file that has structure.

- **Additional issue**: The preprocessing logic (line 151-220) skips files without SYSTEM namelist entirely (line 157-158), which is correct for LR files, but the calculation still needs a structure_id from somewhere.

## Summary

The architecture correctly separates structure (calculation-level) from step parameters. The failure occurs because:
1. LR/TDDFT inputs correctly skip structure parsing (already handled).
2. But `materialize_project_from_qe_input_folder()` needs to determine calculation.structure_id from the FIRST file with structure, and handle the case where some steps have no structure.
3. The calculation must have exactly one structure_id, even if some steps don't contain structure blocks.

