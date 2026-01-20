# ULID Collision Ubuntu CI - Root Cause Analysis

**Date**: 2026-01-20  
**Status**: ✅ FIXED  
**Failing Tests**:
- `tests/integration/test_lammps_long_smoke.py::test_workflow_d_restart`
- `tests/integration/test_lammps_chain.py::test_chain_workflow`

## 1. Error Summary

```
ERROR tests/integration/test_lammps_long_smoke.py::test_workflow_d_restart
AssertionError: ULID COLLISION: md1_step_id == md2_step_id (01KFD0TV8H6ENQQR378FPFEC71)
assert '01KFD0TV8H6ENQQR378FPFEC71' != '01KFD0TV8H6ENQQR378FPFEC71'
```

## 2. Root Cause Analysis

### The Bug Location

In `src/quantumvitas/api.py`, `QVService.init_step()` line 946:

```python
# Line 846: Generate NEW step_id
step_id = generate_resource_id()
step_slug = slugify(step_name)  # step_name defaults to step_type

# Lines 849-854: Generate unique FILENAME (e.g., "md", "md-1", "md-2")
base_name = step_slug
suffix = 1
while (steps_dir / f"{base_name}.step.yaml").exists():
    base_name = f"{step_slug}-{suffix}"  # ← base_name becomes "md-1"
    suffix += 1

step_yaml_path = steps_dir / f"{base_name}.step.yaml"  # ← Correct: unique file

# ... creates step with correct step_id ...

# BUG: Line 946 - Returns using step_slug, NOT base_name!
return require_step(project_root, calculation_selector, step_slug)  # ← Always "md"!
```

### What Happens

1. **First call**: `init_step(step_type="md")`
   - `step_slug = "md"`
   - `base_name = "md"` (file doesn't exist)
   - Creates `md.step.yaml` with ULID `01ABC...`
   - Returns `require_step(..., "md")` → finds `md.step.yaml` ✅

2. **Second call**: `init_step(step_type="md")`
   - `step_slug = "md"` (same!)
   - `base_name = "md-1"` (because `md.step.yaml` exists)
   - Creates `md-1.step.yaml` with ULID `01XYZ...`
   - Returns `require_step(..., "md")` → finds **first** `md.step.yaml`! ❌

**Result**: Both calls return the SAME step (first one), hence `md1_step_id == md2_step_id`.

### Why This Appears as "ULID Collision"

The test gets the same `meta.id` from both calls because it's the same step object, not because ULID generation failed.

## 3. Evidence Collection Plan

Add debug logging to verify this hypothesis:

```python
# In init_step(), after require_step:
print(f"[INIT_STEP_DEBUG] step_slug={step_slug}, base_name={base_name}")
print(f"[INIT_STEP_DEBUG] step_yaml_path={step_yaml_path}")
print(f"[INIT_STEP_DEBUG] returned step meta.id={returned_step.meta.id}")
```

## 4. Fix Strategy

### Option A (Minimal Fix - RECOMMENDED)

Change line 946 to use `base_name` instead of `step_slug`:

```python
# Before (BUG):
return require_step(project_root, calculation_selector, step_slug)

# After (FIX):
return require_step(project_root, calculation_selector, base_name)
```

But wait - `require_step` searches by slug, and the step's meta.slug is still set to `step_slug` (line 926).

### Option B (Correct Fix)

The step's `meta.slug` should also be unique. Fix both:

1. Line 926: Set slug to unique base_name
2. Line 946: Return using base_name (or use step_id which is always unique)

```python
# Line 926: Use unique slug
step_doc.set(["meta", "slug"], base_name)  # Was: step_slug

# Line 946: Return using step_id (guaranteed unique)
return require_step(project_root, calculation_selector, step_id)
```

### Option C (Most Robust)

Return using step_id (ULID) which is always unique:

```python
return require_step(project_root, calculation_selector, step_id_from_doc)
```

This avoids any slug-based ambiguity entirely.

## 5. Why Ubuntu CI Only?

This is NOT Ubuntu-specific - it would fail anywhere. However:
- macOS tests may have different timing/ordering
- pytest-xdist parallelism may expose race conditions
- The assertion was only recently added, so the bug was latent

## 6. Files to Modify

| File | Change |
|------|--------|
| `src/quantumvitas/api.py` | Fix `init_step()` return value and slug assignment |

## 7. Verification

After fix, the test should pass because:
- First `init_step("md")` → returns step with id=`01ABC...`, slug=`md`
- Second `init_step("md")` → returns step with id=`01XYZ...`, slug=`md-1`
- Assertion `md1_step_id != md2_step_id` passes ✅

## 8. Fix Applied

### Changes to `src/quantumvitas/api.py` (line 924-949)

```python
# BEFORE (BUG):
step_doc.set(["meta", "slug"], step_slug)  # Always "md"
# ...
return require_step(project_root, calculation_selector, step_slug)  # Always finds first "md"

# AFTER (FIX):
step_doc.set(["meta", "slug"], base_name)  # Unique: "md", "md-1", "md-2"
# ...
return require_step(project_root, calculation_selector, step_id_from_doc)  # Uses unique ULID
```

### Test Results

```
================ 2245 passed, 143 warnings in 78.67s =================
```

All tests pass, including the previously failing:
- `test_workflow_d_restart`: ✅ PASS
- `test_chain_workflow`: ✅ PASS

