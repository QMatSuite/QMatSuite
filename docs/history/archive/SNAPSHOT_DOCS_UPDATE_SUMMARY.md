# Snapshot Documentation and Test Update Summary

**Date**: 2025-12-XX  
**Purpose**: Clarify snapshot semantics (Option B: Template with Fresh IDs) in docs and add explicit tests

---

## Changes Made

### 1. Documentation Updates (AI_understanding.md)

**Section 23.3 - Updated to "Snapshot Semantics (Option B: Template with Fresh IDs)"**

**Added explicit documentation**:
- **Export behavior**: Preserves all `id` and `*_id` fields as recorded
- **Materialize behavior**: Always regenerates new ULIDs, uses snapshot IDs only as template graph
- **Key implications**: 
  - ✅ Multiple projects from same snapshot are independent with distinct ULIDs
  - ✅ Graph structure is preserved
  - ❌ Snapshot is NOT a bit-for-bit backup
  - ❌ Original ULIDs are NOT preserved
- **Demo/Reference Features**: Explicitly documented that they use `origin.kind`, `origin.demo_id`, and `origin.reference_artifacts` - NOT snapshot ULIDs

**Section 23.1 - Updated schema example**:
- Changed `structure: "si-bulk"` → `structure_id: "<structure_ulid>"` to reflect ID-only references
- Changed step `structure: "si-bulk"` → `structure_id: "<structure_ulid>"` to reflect ID-only references

**Section 23 - Updated introduction**:
- Clarified that snapshots are **templates**, not bit-for-bit backups
- Added note about ULID regeneration on materialization

---

### 2. New Test: `test_snapshot_id_regeneration.py`

**File**: `tests/unit/test_snapshot_id_regeneration.py`

**Test**: `test_id_regeneration_and_graph_preservation`

**What it asserts**:

1. **ID Regeneration**:
   - Collects all IDs from snapshot (project, structures, calculations, steps)
   - Collects all IDs from materialized project (via `build_resource_index`)
   - Asserts: **No intersection** between snapshot IDs and materialized IDs
   - Confirms all ULIDs are regenerated

2. **Graph Structure Preservation**:
   - **Counts**: Same number of structures, calculations, steps
   - **Step types**: Each calculation has same number and types of steps
   - **Cross-references**: All `structure_id`, `parent_calculation_id` references are valid
   - **Graph pattern**: Same pattern of calculation→structure relationships

3. **Cross-Reference Validity**:
   - All `structure_id` references point to existing structures
   - All `parent_calculation_id` references point to existing calculations
   - Step `parent_calculation_id` matches the calculation containing the step
   - No broken links in the materialized project

**Test Results**: ✅ **1 passed** (uses `project2_bands` fixture with multiple steps)

---

### 3. Code Comments Added

**File**: `src/qmatsuite/api.py`

**Location 1**: `create_demo_project` (lines ~2972-2987)
- Added comment: "Demo recognition relies on origin.kind and demo_id, NOT on preserving snapshot ULIDs"
- Added comment: "Reference analysis lookup uses origin.reference_artifacts or snapshot.meta.reference_artifacts, NOT project ULIDs"

**Location 2**: `get_reference_analysis` (lines ~1868-1893)
- Added comment: "Demo recognition uses origin.kind == 'demo' and origin.demo_id (stable identifier), NOT project/calculation ULIDs"
- Added comment: "Reference lookup uses origin.reference_artifacts or snapshot.meta.reference_artifacts, NOT project/calculation ULIDs"

**Purpose**: Clarify that demo/reference features do NOT depend on preserving snapshot ULIDs

---

## Audit Results: Demo/Reference Logic

### ✅ Confirmed: Demo/Reference Logic Does NOT Rely on Snapshot ULIDs

**Evidence**:

1. **`create_demo_project`** (api.py:2907-3020):
   - Uses `demo_id` (stable string identifier like "si_bands_demo") from snapshot meta
   - Stores `origin.kind = "demo"` and `origin.demo_id = demo_name` in project settings
   - Stores `origin.reference_artifacts` from snapshot meta
   - **No use of project/calculation ULIDs for demo recognition**

2. **`get_reference_analysis`** (api.py:1840-1940):
   - Checks `origin.kind == "demo"` (not ULID-based)
   - Uses `origin.demo_id` to locate snapshot file (not ULID-based)
   - Uses `origin.reference_artifacts` or `snapshot.meta.reference_artifacts` to find artifact filenames
   - Loads reference JSON from `resources/demo_projects/{artifact_filename}`
   - **No use of project/calculation ULIDs for reference lookup**

3. **Reference Artifact Lookup**:
   - Uses stable artifact filenames (e.g., "si_bands_demo.bands.json")
   - Filenames are stored in `snapshot.meta.reference_artifacts` mapping
   - **Not tied to any project/calculation ULIDs**

**Conclusion**: ✅ **Demo/reference logic is completely independent of snapshot ULIDs**. It uses stable identifiers (`demo_id`, artifact filenames) that survive materialization.

---

## Test Results

```
tests/unit/test_project_snapshot.py: 10 passed
tests/unit/test_snapshot_id_regeneration.py: 1 passed
Total: 11 tests passed ✅
```

All tests confirm:
- ✅ IDs are regenerated (no intersection with snapshot IDs)
- ✅ Graph structure is preserved (counts, relationships, cross-references)
- ✅ All cross-references are valid (no broken links)

---

## Summary

### What Was Added to AI_understanding.md

1. **Section 23.3**: New subsection "Snapshot Semantics (Option B: Template with Fresh IDs)"
   - Explicit documentation of export vs materialize behavior
   - Key implications (what's preserved, what's changed)
   - Demo/Reference features documentation

2. **Section 23.1**: Updated schema example to use `structure_id` (ID-only references)

3. **Section 23**: Updated introduction to clarify snapshots are templates, not backups

### New Test(s) and What They Assert

**File**: `tests/unit/test_snapshot_id_regeneration.py`

**Test**: `test_id_regeneration_and_graph_preservation`

**Asserts**:
1. All materialized IDs are different from snapshot IDs (no intersection)
2. Graph structure is preserved:
   - Same counts of structures/calculations/steps
   - Each calculation has same number and types of steps
   - Same pattern of calculation→structure relationships
3. All cross-references are valid:
   - `structure_id` references point to existing structures
   - `parent_calculation_id` references point to existing calculations
   - Step `parent_calculation_id` matches containing calculation
   - No broken links

### Confirmation from Audit

✅ **Demo/reference paths do NOT depend on preserving snapshot ULIDs**:

- Demo recognition: Uses `origin.kind == "demo"` and `origin.demo_id` (stable string)
- Reference analysis: Uses `origin.reference_artifacts` or `snapshot.meta.reference_artifacts` (stable filenames)
- All lookups use stable identifiers that survive materialization
- No code assumes snapshot ULIDs are preserved

**Comments added** in `api.py` to document this explicitly for future maintainers.

---

## Files Modified

1. `AI_understanding.md` - Updated section 23 with Option B semantics
2. `tests/unit/test_snapshot_id_regeneration.py` - New test file (created)
3. `src/qmatsuite/api.py` - Added clarifying comments (no behavior changes)

**No runtime code paths or behavior were changed** - only documentation, tests, and comments.

