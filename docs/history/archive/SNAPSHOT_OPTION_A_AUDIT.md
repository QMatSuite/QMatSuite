# Snapshot Implementation Audit: Option A Compliance

**Date**: 2025-12-XX  
**Purpose**: Audit current snapshot implementation against "Option A" (snapshots store real ULIDs and reuse them on restore)

---

## What is Option A?

**Option A** (desired behavior):
- Snapshots are backup/demo artifacts, not templates
- Snapshots store real ULIDs and reuse them on restore
- Snapshot contains `meta.id` for all resources (project/structure/calculation/step)
- All cross-references inside snapshot are by `*_id` only (no name/slug/path)
- When materializing a snapshot, **keep the same ULIDs exactly** (do not regenerate)
- IDs only need to be unique within a project, not globally

**Future "template/clone with fresh IDs"** will be a separate flow (`qms snapshot materialize --fresh-ids`).

---

## Current Behavior

### ✅ Export (`export_project_to_snapshot`)

**Location**: `src/qmatsuite/project/snapshot.py:97-209`

**Current behavior**: ✅ **Already matches Option A**
- Exports `meta.id` for all resources (project, structures, calculations, steps)
- Exports `structure_id` and `step_id` for cross-references (ID-only)
- Preserves all ULIDs in snapshot YAML

**Evidence**:
- Line 117: `"meta": project_model.meta.to_dict()` - includes `id`
- Line 138: `"meta": struct_entry.meta.to_dict()` - includes `id`
- Line 155: `calculation_meta_dict = calculation_entry.meta.to_dict()` - includes `id`
- Line 167: `calculation_dict["structure_id"] = calculation_model.structure_id` - ID-only reference
- Line 186: `step_dict = step_spec.to_dict()` - includes `meta.id` and `structure_id`

**Demo snapshot example** (`resources/demo_projects/si_bands_demo.yml`):
```yaml
project:
  meta:
    id: 01KBH0N8H2W53FFED02D8T3W3T  # Real ULID preserved
structures:
- meta:
    id: 01KBH0RFSSZ1G305C8PS5F1WHC  # Real ULID preserved
calculations:
- meta:
    id: 01KBH0S...  # Real ULID preserved
  structure_id: 01KBH0RFSSZ1G305C8PS5F1WHC  # ID-only reference
```

### ❌ Materialize (`materialize_project_from_snapshot`)

**Location**: `src/qmatsuite/project/snapshot.py:212-541`

**Current behavior**: ❌ **Does NOT match Option A**
- **Regenerates ALL IDs** instead of keeping snapshot IDs
- Builds `id_mapping: Dict[str, str]` to map old_id → new_id
- Uses `generate_resource_id()` for all resources

**Evidence of ID regeneration**:
- Line 263: `new_project_id = generate_resource_id()` - regenerates project ID
- Line 274: `new_struct_id = generate_resource_id()` - regenerates structure IDs
- Line 286: `new_calculation_id = generate_resource_id()` - regenerates calculation IDs
- Line 296: `new_step_id = generate_resource_id()` - regenerates step IDs
- Line 325: `new_struct_id = id_mapping.get(old_struct_id, generate_resource_id())` - fallback regeneration
- Line 368: `new_calculation_id = id_mapping.get(old_calculation_id, generate_resource_id())` - fallback regeneration
- Line 442: `new_step_id = id_mapping.get(old_step_id, generate_resource_id())` - fallback regeneration

**Docstring contradiction** (line 48-49 in `ProjectSnapshot` class):
```python
"""
ULIDs are preserved for reference but will be regenerated when materializing the project.
"""
```
This explicitly states IDs are regenerated, contradicting Option A.

**Docstring in `materialize_project_from_snapshot`** (line 220):
```python
"""
Generates new ULIDs for all resources and rewrites references to maintain consistency.
"""
```

### ✅ Cross-References in Snapshot

**Current behavior**: ✅ **Already matches Option A**
- Snapshots use `structure_id` (ULID) for calculation → structure references
- Snapshots use `step_id` (ULID) for calculation → step references (via step meta.id)
- Snapshots use `parent_calculation_id` (ULID) for step → calculation references
- No name/slug/path stored as cross-references (only in resource's own meta)

**Evidence**:
- Line 167-171: `calculation_dict["structure_id"] = calculation_model.structure_id`
- Line 186: `step_dict = step_spec.to_dict()` - includes `parent_calculation_id` and `structure_id`

### ✅ Demo Project Creation Path

**Location**: `src/qmatsuite/api.py:2898-2987`

**Current behavior**: ✅ **Uses snapshot materialization correctly**
- `create_demo_project()` calls `materialize_project_from_snapshot()`
- Stores demo origin info in `project.qms.yml` settings
- No assumptions about new IDs (just passes through to materialize)

**No changes needed** - once materialization is fixed, demo creation will work correctly.

### ✅ ResourceIndex

**Location**: `src/qmatsuite/core/resolution.py:168-256`

**Current behavior**: ✅ **No global uniqueness assumption**
- `ResourceIndex` is built per-project (scans one project_root)
- `by_id: Dict[str, ResourceMeta]` is project-scoped
- No cross-project ID lookups
- IDs only need to be unique within a project

**No changes needed** - ResourceIndex already assumes project-scoped uniqueness.

---

## Where Current Implementation Diverges from Option A

### 1. ❌ `materialize_project_from_snapshot` Regenerates All IDs

**Location**: `src/qmatsuite/project/snapshot.py:257-297`

**Problem**: 
- Lines 263, 274, 286, 296: All IDs are regenerated via `generate_resource_id()`
- Lines 325, 368, 442: Fallback regeneration if ID not in mapping
- This contradicts Option A which requires keeping snapshot IDs

**Impact**: 
- Demo projects created from snapshots have different IDs than the snapshot
- Cannot use snapshot as "exact backup" - IDs change on restore
- Breaks any code that expects snapshot IDs to match materialized IDs

### 2. ❌ Test Asserts IDs Are Different

**Location**: `tests/unit/test_project_snapshot.py:151-153`

**Problem**:
```python
# ULIDs should be different
assert original_project.meta.id != new_project.meta.id
assert original_calculation.meta.id != new_calculation.meta.id
```

**Impact**: 
- Test explicitly enforces ID regeneration behavior
- Will fail if we switch to Option A (keeping IDs)
- Needs to be updated or removed

### 3. ❌ Docstring Contradicts Option A

**Location**: `src/qmatsuite/project/snapshot.py:48-49`

**Problem**:
```python
"""
ULIDs are preserved for reference but will be regenerated when materializing the project.
"""
```

**Impact**: 
- Documentation explicitly states IDs are regenerated
- Misleading for Option A (should say IDs are preserved and reused)

---

## What Changes Are Needed to Adopt Option A

### High-Level Changes

#### 1. Remove ID Regeneration in `materialize_project_from_snapshot`

**File**: `src/qmatsuite/project/snapshot.py`

**Changes needed**:
- **Remove** lines 257-297 (id_mapping construction and ID regeneration)
- **Change** line 263: `new_project_id = old_project_id` (keep snapshot ID)
- **Change** line 274: `new_struct_id = old_struct_id` (keep snapshot ID)
- **Change** line 286: `new_calculation_id = old_calculation_id` (keep snapshot ID)
- **Change** line 296: `new_step_id = old_step_id` (keep snapshot ID)
- **Remove** all `id_mapping.get(old_id, generate_resource_id())` fallbacks
- **Update** all references to use snapshot IDs directly (no mapping needed)
- **Update** structure_id and parent_calculation_id references to use snapshot IDs directly

**Lines to modify**:
- Lines 257-297: Remove id_mapping construction
- Line 301: `id=new_project_id` → `id=old_project_id`
- Line 325: `new_struct_id = id_mapping.get(...)` → `new_struct_id = old_struct_id`
- Line 333: `"id": new_struct_id` → `"id": old_struct_id`
- Line 348: `id=new_struct_id` → `id=old_struct_id`
- Line 368: `new_calculation_id = id_mapping.get(...)` → `new_calculation_id = old_calculation_id`
- Line 422: `id=new_calculation_id` → `id=old_calculation_id`
- Line 428: `structure_id=calculation_structure_id` → `structure_id=old_calculation_structure_id` (from snapshot)
- Line 442: `new_step_id = id_mapping.get(...)` → `new_step_id = old_step_id`
- Line 447: `"id": new_step_id` → `"id": old_step_id`
- Line 455: `step_spec_dict["parent_calculation_id"] = new_calculation_id` → `step_spec_dict["parent_calculation_id"] = old_calculation_id`
- Line 465: `step_spec_dict["structure_id"] = new_structure_id` → `step_spec_dict["structure_id"] = old_structure_id` (from snapshot)
- Line 521: `id=new_calculation_id` → `id=old_calculation_id`

**Simplification**: Since we're keeping IDs, we don't need the `id_mapping` dictionary at all. All references can use snapshot IDs directly.

#### 2. Update Docstrings

**File**: `src/qmatsuite/project/snapshot.py`

**Changes needed**:
- **Line 48-49** (ProjectSnapshot class docstring):
  ```python
  """
  ULIDs are preserved and reused when materializing the project.
  This allows exact reconstruction of the project with the same internal relationships.
  """
  ```

- **Line 220** (materialize_project_from_snapshot docstring):
  ```python
  """
  Creates a new project directory from a ProjectSnapshot.
  
  Preserves all ULIDs from the snapshot, allowing exact reconstruction
  of the project with the same internal relationships.
  """
  ```

#### 3. Update Test Assertions

**File**: `tests/unit/test_project_snapshot.py`

**Changes needed**:
- **Line 151-153**: Remove or update assertions:
  ```python
  # ULIDs should be preserved (Option A)
  assert original_project.meta.id == new_project.meta.id
  assert original_calculation.meta.id == new_calculation.meta.id
  ```

  OR if we want to keep the test flexible for future "fresh IDs" option:
  ```python
  # ULIDs are preserved by default (Option A)
  # Note: Future --fresh-ids option will regenerate IDs
  assert original_project.meta.id == new_project.meta.id
  assert original_calculation.meta.id == new_calculation.meta.id
  ```

#### 4. Verify Cross-Reference Resolution

**No changes needed** - current code already:
- Uses `structure_id` (ULID) from snapshot
- Uses `parent_calculation_id` (ULID) from snapshot
- Maps these correctly during materialization (just need to keep IDs instead of regenerating)

---

## Subtle Pitfalls and Edge Cases

### ✅ No Global Uniqueness Assumption

**Finding**: ✅ **Safe**
- `ResourceIndex` is project-scoped (built from one `project_root`)
- No cross-project ID lookups
- IDs only need to be unique within a project
- Multiple projects can have the same ULIDs without conflict

**No changes needed**.

### ✅ ID Collision Within Project

**Finding**: ✅ **Safe**
- Snapshot materialization creates a new project directory
- All IDs come from the snapshot (which was internally consistent)
- No risk of ID collision within the new project
- If user materializes same snapshot twice, they get two separate projects (different directories)

**No changes needed**.

### ⚠️ Project Name/Slug Changes

**Finding**: ⚠️ **Handled correctly**
- Line 236: `project_name = new_project_name or original_name` - allows renaming
- Line 237: `project_slug = slugify(project_name)` - slug derived from name
- **But**: Project ID stays the same (from snapshot), only name/slug change
- This is correct for Option A - ID is preserved, name/slug can differ

**No changes needed**.

### ✅ Structure/Calculation/Step Name Changes

**Finding**: ✅ **Handled correctly**
- Names/slugs are derived from snapshot meta
- IDs are preserved from snapshot
- If user wants to rename after materialization, they can use `qms configure`
- This is correct for Option A

**No changes needed**.

### ✅ Missing IDs in Snapshot (Backwards Compatibility)

**Finding**: ⚠️ **Needs consideration**
- Current code has fallbacks: `id_mapping.get(old_id, generate_resource_id())`
- If snapshot is missing an ID, current code generates a new one
- For Option A: If snapshot is missing an ID, we should either:
  - Generate a new ID (acceptable for backwards compat with old snapshots)
  - Or raise an error (strict Option A)

**Recommendation**: Keep fallback for backwards compatibility, but log a warning if ID is missing.

---

## Summary

### Current State

| Component | Status | Notes |
|-----------|--------|-------|
| Export | ✅ Matches Option A | Preserves all IDs in snapshot |
| Materialize | ❌ Diverges | Regenerates all IDs instead of keeping them |
| Cross-references | ✅ Matches Option A | Uses `*_id` (ULID) only |
| Demo creation | ✅ Uses materialize | Will work once materialize is fixed |
| ResourceIndex | ✅ Safe | Project-scoped, no global uniqueness |
| Tests | ❌ Enforces divergence | Asserts IDs are different |
| Docstrings | ❌ Contradicts | Says IDs are regenerated |

### Required Changes

1. **Remove ID regeneration** in `materialize_project_from_snapshot` (lines 257-541)
2. **Update docstrings** to reflect Option A (lines 48-49, 220)
3. **Update test assertions** to check IDs are preserved (line 151-153)
4. **Keep fallback** for missing IDs (backwards compatibility with old snapshots)

### Estimated Impact

- **Low risk**: ResourceIndex already assumes project-scoped uniqueness
- **No breaking changes**: Existing projects are unaffected
- **Backwards compatible**: Can handle old snapshots with missing IDs
- **Future-proof**: Leaves room for `--fresh-ids` option later

### Implementation Complexity

- **Low**: Mostly removing code (id_mapping construction) and using snapshot IDs directly
- **Estimated LOC change**: ~50 lines removed, ~20 lines modified
- **Test updates**: 1-2 assertions to change

---

## Recommendation

**Proceed with Option A adoption**. The changes are straightforward:
1. Remove ID regeneration logic
2. Use snapshot IDs directly
3. Update tests and docs

This aligns with the design goal of snapshots as "exact backups" rather than templates, and leaves room for a future "template with fresh IDs" feature.

