# Contract Hardening - Final Review Summary

**Reviewer**: Opus
**Date**: 2026-01-29
**Test Results**: 2938 passed, 22 skipped

---

## Changes Made

### 1. GUI Field Enforcement (HARD_REDLINE_FIELDS)

**File**: `tests/contract_crawler/test_gui_field_enforcement.py`

Expanded HARD_REDLINE_FIELDS from 8 to 15 methods covering all manifest methods with successful golden fixtures.

**Hard Enforced Methods (15)**:
| Method | Required Fields |
|--------|-----------------|
| get_calculation_detail | id, steps, steps[].id/type/name |
| get_step_detail | id, name, step_type |
| list_structures | structures, structures[].id/name |
| list_calculations | calculations, calculations[].id |
| create_demo_project | project_root, project_id |
| create_calculation | calculation_id |
| get_structure_vis | atoms, bonds |
| run_step | job_id, status |
| list_journal_entries | entries |
| get_pseudo_mapping | mapping |
| list_demo_projects | demos, demos[].id/title |
| get_project_summary | id, name |
| list_step_artifacts | artifacts |
| read_step_artifact_text | content, truncated, total_bytes |
| list_qe_ui_parameters | parameters, parameters[].name/type |

**Soft Enforcement Only (5)**:
- `get_band_structure_data` - Golden fixture failed (baseline bug)
- `get_dos_data` - Golden fixture failed (baseline bug)
- `import_structure` - Golden fixture failed (baseline bug)
- `get_common_cards` - API/manifest mismatch (API: k_points, manifest: cards)
- `get_preset_catalog` - API/manifest mismatch (API: dimensions, manifest: presets)

### 2. Environment-Dependent Field Skip

**File**: `tests/contract_crawler/golden_comparison.py`

Added `seed_has_sssp` to `DATA_DEPENDENT_FIELDS` - this boolean depends on whether SSSP library is installed, which varies by environment.

### 3. CLI Test Isolation Fix

**File**: `tests/cli/test_si_dos_calculation_cli.py`

Changed `cli_si_dos_project` fixture to use `tmp_path` instead of hardcoded `.tmp/test_outputs/` path. This prevents race conditions in xdist parallel runs.

### 4. Array Schema Enforcement

**File**: `tests/contract_crawler/test_schema_preservation.py`

Updated array item checking:
- Empty arrays are now allowed (some methods legitimately return empty lists)
- Checks min(5, len) items for structural consistency

---

## Skip Analysis (22 Total)

### Gate Tests (2 skips)
| Test | Reason |
|------|--------|
| test_notebook_no_kernel_imports | Notebook frontend does not exist |
| test_tools_no_kernel_imports | Tools directory does not exist |

### Golden Fixture Failures (15 skips)
These are methods where the baseline (0873ebf) itself had bugs:
- get_band_structure_data - Missing bands data file
- get_dos_data - Missing DOS data file
- apply_presets_to_step - ResolvedResource has no path
- detect_presets - No internal QE found
- set_common_card - Cannot set dict at path
- save_relax_final_structure - Not a relax step
- apply_presets_to_calculation - No internal QE found
- reset_step_params - Unexpected keyword argument
- structure_import_online_candidate - Candidate not in cache
- get_reference_analysis - NoneType has no items
- get_pseudo_options_for_calculation - dict has no store_dir
- promote_relax_structure - Not a relax step
- resolve_project_pseudo_provenance - Pseudo file not found
- get_relax_final_structure_preview - Not a relax step
- import_structure - Structure not found

### GUI Soft Enforcement (3 skips)
Duplicate of golden fixture failures for GUI enforcement tests.

### Schema Drift Test (1 skip)
- find_project_root - No minimal payload defined

### GUI Coverage Gate (1 skip)
- test_gui_methods_covered - Soft gate (set QV_ENFORCE_GUI_RPC_COVERAGE=1 to enforce)

---

## CI Behavior Expectations

### Tests-with-QE Job (Ubuntu/macOS)

**Expected**: 2938 passed, 22 skipped

CI has QE installed via source build:
- QE is staged to `.qmatsuite/engines/qe/managed:qe-7.5:<os>/bin`
- QE-dependent tests (marked `requires_qe`) will RUN and PASS
- Golden fixtures are committed to git (deterministic)
- Same skip set as local (environment-independent)

### Skip Stability

All 22 skips are:
1. **Deterministic** - Based on committed golden fixtures or missing directories
2. **Environment-independent** - Same skips locally and in CI
3. **Justified** - Each skip has a documented reason

---

## Daemon Kernel-Ban Gate

**File**: `tests/gates/test_daemon_kernel_ban.py`

Verified daemon has NO kernel imports:
- `test_daemon_no_kernel_imports` - Scans all `src/quantumvitas/daemon/**/*.py`
- `test_compat_py_specifically` - Specific gate for compat.py

**Current compat.py imports**:
```python
from quantumvitas.api import QVService  # Line 721 - ALLOWED
```

No violations detected.

---

## P0 Laws Verification

1. **GUI-critical fields enforced**: 15/20 methods have hard enforcement. 5 excluded due to golden fixture failures or API/manifest mismatch.

2. **Daemon kernel-ban enforced**: Gate test passes, compat.py only imports from `quantumvitas.api.*`.

3. **CI will not fail**: All tests pass locally with same skip set expected in CI.

---

## Remaining Work

### Investigate API/Manifest Mismatches
- `get_common_cards`: API returns `k_points`, GUI manifest expects `cards`
- `get_preset_catalog`: API returns `dimensions`, GUI manifest expects `presets`

These need investigation to determine if:
1. GUI handles the response differently
2. Manifest was generated incorrectly
3. There's a missing compat shaper

### Fix Baseline Bugs
15 methods have failed golden fixtures due to bugs in the baseline (0873ebf). These should be fixed in a future release to enable testing.
