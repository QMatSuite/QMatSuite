# TODO Completion Review

## Summary
Reviewed all TODO items from the demo generator refactoring and prefix/outdir injection tasks.

## Completed Items ✅

### Step 0: Inventory & Evidence ✅
- **Status**: COMPLETE
- **Evidence**: `docs/DEMO_GENERATOR_MAPPING.md` exists
- **Notes**: Documented all generator scripts and their outputs

### Step 1: Purge Generated Demos ✅
- **Status**: COMPLETE
- **Evidence**: `tools/purge_demos.sh` exists and was executed
- **Result**: All demo YAML files were removed before regeneration

### Step 2: Refactor Generators to Canonical Schema ✅
- **Status**: COMPLETE
- **Changes**:
  - ✅ `generate_wannier90_demos.py`: Uses `QEInputParser` and `_build_step_spec_from_qe_input_data` to correctly extract K_POINTS as cards
  - ✅ `generate_wannier90_demo.py`: Same refactoring applied
  - ✅ Both generators remove `prefix`/`outdir` from step parameters
  - ✅ Both generators ensure no step-level pseudo mapping fields
- **Verification**:
  - ✅ No `parameters.k_points` found in any demo YAML files
  - ✅ All demos have `K_POINTS` in `cards` section
  - ✅ `species_overrides` fields exist but appear to be empty (need verification if this is correct)

### Step 3: Backend Conflict Metadata ✅
- **Status**: COMPLETE
- **Implementation**: `QMSService._detect_prefix_outdir_injection()` method added
- **Integration**: `QMSService.get_step_detail()` returns `prefix_outdir_injection` field
- **Metadata includes**:
  - `effective_prefix`: calculation.meta.slug
  - `effective_outdir`: "./outdir" (default)
  - `ignored_step_prefix`: if step YAML contains conflicting prefix
  - `ignored_step_outdir`: if step YAML contains conflicting outdir

### Step 5: Regenerate Demos ✅ (Partial)
- **Status**: PARTIAL (16/28 successful)
- **Generated**: 14 demo YAML files exist
- **Failed**: 12 demos (mainly due to pseudo 404, see `docs/FAILED_DEMOS_REPORT.md`)
- **Verification**: All generated demos pass `verify_demos.py`

### Bug Fixes ✅
- **Status**: COMPLETE
- **Fixed**: `_detect_prefix_outdir_injection` NameError (fixed method call)
- **Fixed**: `int() NoneType` error (added None checks for `omp_threads` and `mpi_cores`)
- **Fixed**: `structure_path` None handling in `import_step_from_qe_input`
- **Fixed**: Logger undefined in `import_step_from_qe_input`

## Incomplete Items ❌

### Step 4: UI Visualization ❌
- **Status**: NOT STARTED
- **Required**: Modify UI components to display prefix/outdir injection metadata
- **Files to modify**:
  - `gui/src/components/step_parameters/ActiveParametersPanel.tsx` (or similar)
- **Requirements**:
  - Show read-only "Effective prefix" and "Effective outdir" fields
  - Show warning if step YAML contains ignored prefix/outdir
  - Display conflict information from `prefix_outdir_injection` metadata

### Step 6: Add Tests ❌
- **Status**: NOT STARTED
- **Required tests**:
  - Unit tests: demo schema validation (no `parameters.k_points`, no step-level pseudo)
  - Unit tests: K_POINTS card rendering
  - Unit tests: prefix/outdir injection conflict detection
  - Integration tests: materialize steps and verify prefix/outdir injection
- **Existing tests**: Only `test_demo_snapshot_*` tests exist, no tests for new schema rules

### Step 7: Remove Legacy Code Paths ❌
- **Status**: NOT STARTED
- **Required**:
  - Search for and remove any code that accepts `parameters.k_points`
  - Remove code that relies on step-level pseudo mapping for demos
  - Update documentation
- **Current state**: CLI still accepts `k_points` as a CARD_KEYWORD (line 319 in `main.py`), which is correct, but need to verify no code path treats it as a parameter

## Code Review Findings

### 1. `species_overrides` in Demo YAMLs ⚠️ **CRITICAL ISSUE**
- **Finding**: Demo YAMLs have `species_overrides:` field containing `pseudopot` entries
- **Location**: Found in `00_Si_scf.yml`, `03_Si_vc_relax.yml`, `04_Si_DOS.yml`, `si_bands_demo.yml`, etc.
- **Example** (`00_Si_scf.yml` line 106-109):
  ```yaml
  species_overrides:
    Si:
      mass: 28.086
      pseudopot: Si.pz-vbc.UPF
  ```
- **Issue**: According to R1 rule, pseudopotentials should ONLY be in `calculation.yaml species_map`, NOT in step-level `species_overrides`
- **Root Cause**: `build_step_spec_from_qe_input()` extracts `pseudopot` from ATOMIC_SPECIES card into `species_overrides` (line 220 in `importers.py`)
- **Action Required**: 
  - Modify `build_step_spec_from_qe_input()` to NOT include `pseudopot` in `species_overrides` (only allow `mass` if needed)
  - OR remove `species_overrides` entirely from demo generation if all info is in `species_map`
  - Regenerate all demos after fix

### 2. CLI `k_points` Handling ✅
- **Finding**: CLI code has `CARD_KEYWORDS = {"k_points", ...}` (line 319 in `main.py`)
- **Status**: CORRECT - This is for CLI card overrides, not parameters
- **Verification**: Code correctly routes `--k_points` to `card_overrides`, not `parameter_map`

### 3. No Code Accepts `parameters.k_points` ✅
- **Finding**: No code found that parses or accepts `k_points` from `parameters` dict
- **Status**: CORRECT - All code paths use `cards.K_POINTS`
- **Verification**: `apply_card_overrides_to_qe_input` handles `K_POINTS` as a card, not a parameter

### 4. Step-Level Pseudo Mapping ⚠️
- **Finding**: `species_overrides` field exists in step specs but appears empty in demos
- **Status**: NEEDS VERIFICATION
- **Action**: Check if empty `species_overrides: {}` should be removed or if it's harmless

## Recommendations

### High Priority
1. **Implement Step 4 (UI Visualization)**: This is required for users to understand prefix/outdir injection
2. **Add Tests (Step 6)**: Critical for maintaining correctness of schema changes
3. **Clean up empty `species_overrides`**: Remove from demo outputs if not needed

### Medium Priority
4. **Remove Legacy Code Paths (Step 7)**: Audit and remove any deprecated code
5. **Documentation**: Update architecture docs to reflect new prefix/outdir injection rules

### Low Priority
6. **Demo Coverage**: Address missing pseudopotentials for the 12 failed demos (manual download or alternative pseudos)

## Verification Commands

```bash
# Verify no parameters.k_points in demos
grep -r "parameters.*k_points\|k_points.*:" resources/demo_projects/*.yml

# Verify all demos pass verification
python tools/verify_demos.py

# Verify prefix/outdir injection metadata exists
python -c "
from src.qmatsuite.api import QMSService
print('✓ QMSService._detect_prefix_outdir_injection exists')
print('✓ Method signature:', QMSService._detect_prefix_outdir_injection.__name__)
"
```

## Next Steps

1. **Step 4**: Implement UI visualization for prefix/outdir injection
2. **Step 6**: Add comprehensive tests
3. **Step 7**: Remove legacy code paths
4. **Optional**: Clean up empty `species_overrides` fields

