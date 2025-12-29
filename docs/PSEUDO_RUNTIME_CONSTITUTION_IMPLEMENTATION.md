# Pseudo Runtime Constitution Implementation

## Implementation Status

### Completed Phases

**Phase 0: Code Mapping** ✓
- Identified all key call sites
- Documented run flow and Step0 insertion point

**Phase 1: Core Step0 Module** ✓
- Created `src/quantumvitas/core/pseudo_runtime.py`
- Implemented `analyze_project_pseudo_effects()` (read-only analyzer)
- Implemented `prepare_project_pseudos_for_run()` (Step0 executor)
- Implemented collision rules (noop/overwrite/rename_existing)
- Implemented `update_project_calcs_filename_by_sha_token()` (project-wide consistency)

**Phase 2: Calc Schema & Consistency** ✓
- Updated `CalculationModel.species_map` schema documentation
- Implemented `refresh_calc_pseudo_records_after_step0()` (refresh after Step0)
- Implemented `species_map_to_selections()` (convert calc records to Step0 input)

**Phase 3: Runner Integration** ✓
- Integrated Step0 into `CalculationRunner.run()` (before first step)
- Updated `qe_calculation.py` to use `project/pseudo` (not `working_dir/pseudo`)
- Updated `input_runner.py` to remove old materialization (Step0 handles it)
- Added RPC handler `analyze_project_pseudo_effects` for UI

**Phase 4: UI Refactor** ⏳ (Pending)
- Need to refactor UI to sha_token-primary grouping
- Need to add warnings display using analyzer

**Phase 5: Tests** ⏳ (Pending)
- Need comprehensive tests for Step0 scenarios

## Key Implementation Details

### Step0 Flow

1. User clicks "Run" → `CalculationRunner.run()` is called
2. **Step0 executes** (before any QE steps):
   - `species_map_to_selections()` converts calc records to `PseudoSelection[]`
   - `prepare_project_pseudos_for_run()` mutates `project/pseudo`:
     - Copies from internal/lib sources
     - Handles collisions (rename/overwrite/noop)
     - Updates project calcs by sha_token on rename
   - `refresh_calc_pseudo_records_after_step0()` updates calc with actual file info
3. QE steps execute, reading from `project/pseudo` only

### Constitution Compliance

✅ **Three Sources Only:**
- `internal`: `repo/resources/pseudo`
- `lib`: `temp/pseudo/...` (installed libraries)
- `project`: `project/pseudo`

✅ **QE Runtime:**
- Only reads `project/pseudo`
- `ESPRESSO_PSEUDO` set to `project/pseudo` (or `working_dir/pseudo` in standalone)

✅ **UI/Settings:**
- No filesystem mutations
- `analyze_project_pseudo_effects()` is read-only (safe for UI)

✅ **SHA Semantics:**
- `sha_token` is primary for physical equivalence
- `sha256` is strict bytes identity
- Collision rules based on sha_token

✅ **Conflict Resolution:**
- Same basename, different sha_token → rename existing
- Same sha_token, different sha256 → overwrite with canonical
- Updates project calcs by sha_token on rename

## Remaining Work

### Phase 4: UI Refactor
- Refactor `pseudo_options.py` to group by sha_token (not sha256)
- Update UI dropdown to show sha_token-primary options
- Add warnings display using `analyze_project_pseudo_effects()`

### Phase 5: Tests
- Step0 prepare tests (noop/overwrite/rename scenarios)
- Project calc update tests
- sha_token collision tests
- No repo_root/pseudo creation tests
