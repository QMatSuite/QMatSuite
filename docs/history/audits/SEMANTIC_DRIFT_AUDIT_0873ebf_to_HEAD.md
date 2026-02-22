# Semantic Drift Audit: 0873ebf → HEAD

**Date**: 2026-01-27
**Baseline Commit**: 0873ebf (last known-good all-green)
**Target Commit**: HEAD (2db7ebd)
**Auditor**: Claude Sonnet 4.5
**Total Files Changed**: 150
**Kernel Files Changed**: 7

---

## Executive Summary

### Overall Risk: **MEDIUM-HIGH**

The refactor introduces **two critical semantic changes** in the kernel layer that alter core behavior and contracts:

1. **CRITICAL**: `core/resolution.py` - Changed absolute_path contract for calculations (now points to directory instead of calculation.yaml file)
2. **CRITICAL**: `workflow/step_factory.py` - Removed `structure_id` and `parent_calculation_id` from step YAML files (DAG model enforcement)

These changes represent **intentional architectural improvements** but carry **high regression risk** because:
- They alter fundamental contracts that many code paths depend on
- Existing step YAML files may contain now-unused fields
- The absolute_path change affects every code path that uses `resolve_calculation()`

### Major Findings

| Change | Severity | Type | Risk |
|--------|----------|------|------|
| Resolution absolute_path contract | HIGH | Semantic change | Breaking contract |
| Step YAML field removal | HIGH | Data model change | Silent compatibility |
| load_calculation() double-append fix | MEDIUM | Bug fix | Improves robustness |
| New get_for_engine() method | LOW | New capability | Additive only |
| New build_structure_vis_payload | LOW | New function | Additive only |

### Potential Regressions

1. **absolute_path contract violation** - Any code expecting `resolved.absolute_path` to point to `calculation.yaml` will now get the parent directory
2. **Orphaned step fields** - Existing step YAML files with `structure_id` or `parent_calculation_id` will have unused fields (may cause confusion)
3. **No migration path** - Old step files are not updated; fields persist but are ignored

### Recommended Actions

1. **IMMEDIATE**: Verify all callsites of `resolve_calculation()` handle directory path correctly
2. **IMMEDIATE**: Audit daemon/RPC layer for absolute_path assumptions
3. **NEXT**: Add validation that warns on orphaned step fields
4. **NEXT**: Consider migration utility to clean up old step files

---

## Kernel Scope Definition

### Included (Kernel)

The following directories/modules are considered **kernel scope** for this audit:

- `src/qmatsuite/core/*` - Resource models, resolution, context, selectors, SSOT
- `src/qmatsuite/workflow/*` - Step type registry, step factory, templates, DAG
- `src/qmatsuite/calculation/*` - Structure steps, parameter handling
- `src/qmatsuite/analysis/*` - Artifact parsing, structure visualization
- `src/qmatsuite/io/*` - Persistence, manifest, fingerprinting
- `src/qmatsuite/drivers/*` - QE, VASP, LAMMPS, etc. input/output
- `src/qmatsuite/engine/*` - Engine dispatch, writer utilities
- `src/qmatsuite/presets/*` - Preset system, parameter spaces
- `src/qmatsuite/project/*` - Project model, snapshot

**Rationale**: These modules define core semantics, invariants, and data contracts. Changes here affect reproducibility, correctness, and architectural integrity.

### Excluded (Non-Kernel)

- `src/qmatsuite/api/*` - New API facade layer (pure wrapper, no logic)
- `src/qmatsuite/_api_legacy.py` - Legacy API wrapper (facade only)
- `src/qmatsuite/api_legacy.py` - Renamed old API (legacy compatibility)
- `src/qmatsuite/cli/*` - CLI frontend (presentation layer)
- `src/qmatsuite/daemon/*` - RPC/daemon server (transport layer)
- `tests/*` - Test code (may be overfit)
- `docs/*` - Documentation
- `scripts/*` - Utility scripts

**Rationale**: These are presentation/transport layers. While they may have bugs, they don't affect kernel semantics or reproducibility guarantees.

### Borderline Cases

- `src/qmatsuite/__init__.py` - Package exports (borderline: affects public API but not kernel logic)
  - **Decision**: Include for API contract review only

---

## Diff Inventory

### Kernel-Scope Files Changed

| File | Status | Lines Changed | Risk |
|------|--------|---------------|------|
| `src/qmatsuite/core/models.py` | M | 29 | MEDIUM |
| `src/qmatsuite/core/resolution.py` | M | 56 | **HIGH** |
| `src/qmatsuite/workflow/step_factory.py` | M | 15 | **HIGH** |
| `src/qmatsuite/workflow/registry.py` | M | 37 | LOW |
| `src/qmatsuite/workflow/templates.py` | M | 4 | LOW |
| `src/qmatsuite/analysis/structure_viz.py` | M | 159 | LOW |
| `src/qmatsuite/engine/vasp_writer.py` | M | 1 | NONE |

**Total kernel changes**: 301 lines across 7 files

---

## Detailed Per-File Analysis

### 1. `src/qmatsuite/core/models.py`

**Diff Summary**: Bug fix for path handling in `load_calculation()`

**Semantic Delta**:
```python
# BEFORE: Simple is_dir() check
if path.is_dir():
    path = path / "calculation.yaml"

# AFTER: Robust handling with double-append detection
path_str = str(path)
if path_str.endswith("/calculation.yaml/calculation.yaml"):
    # Extract directory, remove double-append
    dir_part = path_str[:-len("/calculation.yaml/calculation.yaml")]
    path = Path(dir_part) / "calculation.yaml"
elif path.is_dir():
    path = path / "calculation.yaml"
elif path.name == "calculation.yaml":
    # Verify it's actually a file, fallback to parent if not
    if not path.is_file():
        if path.parent.is_dir():
            path = path.parent / "calculation.yaml"
```

**Impact**:
- **Positive**: Fixes edge case where callers accidentally double-append "calculation.yaml"
- **No breaking change**: Makes the function more robust without changing correct usage
- **Error handling**: Adds verification that resolved path actually exists

**Risk Level**: **MEDIUM**

**Rationale**: This is a defensive fix that shouldn't change behavior for correct callers, but it's unclear if the double-append bug existed in practice or was theoretical.

**Suggested Follow-up**:
- Search codebase for patterns like `path / "calculation.yaml" / "calculation.yaml"`
- Verify daemon/RPC layer doesn't accidentally double-append

---

### 2. `src/qmatsuite/core/resolution.py` ⚠️ CRITICAL

**Diff Summary**: Changed `absolute_path` contract for calculations

**Semantic Delta**:
```python
# BEFORE (implied): absolute_path pointed to calculation.yaml file
# Code would do: resolved.absolute_path (was calculation.yaml path)

# AFTER: absolute_path points to calculation directory
# index.by_path stores calculation.yaml, but we return parent:
abs_path = path.parent  # path is calculation.yaml, return directory

# Fallback also changed:
# OLD: abs_path = (project_root / meta.path / "calculation.yaml").resolve()
# NEW: abs_path = (project_root / calc_dir_path).resolve()
```

**Impact**:
- **Breaking contract change**: All code expecting `resolved.absolute_path` to be a file path will now get a directory
- **Affects**: Every callsite of `resolve_calculation()` that uses `.absolute_path`
- **Backwards incompatible**: No migration or warning

**Callsite Analysis**:

Common patterns that may break:
```python
# BROKEN (if absolute_path was used as file):
calc_yaml = resolved.absolute_path  # Now a directory, not a file

# CORRECT (if caller expects directory):
calc_dir = resolved.absolute_path
calc_yaml = calc_dir / "calculation.yaml"
```

**Risk Level**: **HIGH**

**Rationale**: This is an intentional architectural change to make the contract consistent (calculations are directories, not files), but it's a breaking change. The comment in the code acknowledges this: "absolute_path points to the calculation directory, not the calculation.yaml file."

**Suggested Follow-up**:
1. **IMMEDIATE**: Audit all callsites of `resolve_calculation()`:
   ```bash
   git grep -n "resolve_calculation" | grep -v test_
   git grep -n "\.absolute_path" | grep -v test_
   ```
2. **VERIFY**: Check daemon handlers that serialize resolved resources
3. **TEST**: Ensure legacy API wrappers handle directory path correctly
4. **DOCUMENT**: Update docs to clarify absolute_path contract for calculations vs structures vs steps

---

### 3. `src/qmatsuite/workflow/step_factory.py` ⚠️ CRITICAL

**Diff Summary**: Removed `structure_id` and `parent_calculation_id` from step YAML

**Semantic Delta**:
```python
# BEFORE: Step YAML contained parent references
data = {
    "meta": {...},
    "step_type": machine_step_type,
}
if structure_id:
    data["structure"] = structure_id  # Legacy field
if parent_calculation_id:
    data["parent_calculation_id"] = parent_calculation_id

# AFTER: Step YAML is self-contained, no parent references
data = {
    "meta": {...},
    "step_type": machine_step_type,
}
# Comment: "DAG model: Do NOT store structure_id in step YAML"
# Comment: "Step inherits structure from its parent calculation at runtime"
```

**Impact**:
- **Data model change**: Step YAML files no longer contain parent references
- **Enforces DAG architecture**: Calculation is SSOT for step associations
- **Existing files**: Old step YAML files with these fields will have orphaned data (fields ignored but still present on disk)
- **No migration**: Fields are not stripped from existing files

**Compatibility**:
- **Read**: Old step files can still be loaded (extra fields ignored)
- **Write**: New step files won't have these fields
- **Mixed state**: Projects may have mix of old/new step files

**Risk Level**: **HIGH**

**Rationale**: This is an intentional architectural improvement (enforcing SSOT), but it creates a silent compatibility issue. Users may see old fields in step files and be confused about whether they're still used.

**Suggested Follow-up**:
1. **VALIDATE**: Add loader warning if step YAML contains orphaned fields (`structure_id`, `parent_calculation_id`)
2. **MIGRATE**: Provide utility to clean up old step files
3. **DOCUMENT**: Update docs to clarify step YAML schema
4. **TEST**: Verify mixed old/new projects work correctly

---

### 4. `src/qmatsuite/workflow/registry.py`

**Diff Summary**: Added `get_for_engine()` method

**Semantic Delta**:
- **New capability**: `get_for_engine(step_type, engine)` returns engine-specific step type spec
- **No existing behavior changed**: Existing `get()` and `has()` methods unchanged
- **Additive only**: New method doesn't affect current code paths

**Example**:
```python
# New method allows:
spec = registry.get_for_engine("relax", "lammps")  # Returns lammps_relax spec
spec = registry.get_for_engine("relax", "qe")      # Returns qe_relax spec

# Fallback behavior if engine doesn't have that type:
spec = registry.get_for_engine("bands", "lammps")  # Falls back to qe_bands
```

**Impact**:
- **No breaking changes**: Purely additive
- **Intended use**: Template/step creation code can use this to resolve engine-specific types

**Risk Level**: **LOW**

**Rationale**: New capability, well-documented, doesn't change existing behavior.

**Suggested Follow-up**:
- Verify the fallback behavior is intentional (returns qe spec if engine doesn't have that type)
- Consider if fallback should return None instead for stricter validation

---

### 5. `src/qmatsuite/workflow/templates.py`

**Diff Summary**: Import change (domain API → LegacyService)

**Semantic Delta**:
```python
# BEFORE:
from qmatsuite.api import QMSService
QMSService.calc_set_steps(...)

# AFTER:
from qmatsuite._api_legacy import QMSService as LegacyService
LegacyService.calc_set_steps(...)
```

**Impact**:
- **Layer change only**: Switches from domain API to legacy API
- **No behavior change**: Both call the same underlying implementation
- **Architecture compliance**: Templates are kernel, so this is proper layering

**Risk Level**: **LOW**

**Rationale**: This is a layer boundary fix, not a semantic change.

**Suggested Follow-up**:
- None (this is correct layering)

---

### 6. `src/qmatsuite/analysis/structure_viz.py`

**Diff Summary**: Added new `build_structure_vis_payload()` function

**Semantic Delta**:
- **New function**: Pure transformation (Structure → visualization dict)
- **No existing behavior changed**: Existing functions unchanged
- **Additive only**: New export in `__all__`

**Function signature**:
```python
def build_structure_vis_payload(
    structure: PMGStructure,
    params: DisplayModeParams,
    structure_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure transformation: Structure → visualization primitives"""
```

**Impact**:
- **No breaking changes**: Purely additive
- **Intended use**: Frontends can use this for structure visualization without matplotlib
- **Re-exported**: Available via `api/utils.py` for daemon access

**Risk Level**: **LOW**

**Rationale**: New capability, well-documented, doesn't change existing behavior.

**Suggested Follow-up**:
- None (this is a clean addition)

---

### 7. `src/qmatsuite/engine/vasp_writer.py`

**Diff Summary**: Whitespace change (added blank line at EOF)

**Semantic Delta**: None

**Impact**: None

**Risk Level**: **NONE**

---

## Invariants Checklist

### 1. SSOT Boundaries

**Rule**: Only `calculation.yaml` + `step.yaml` are SSOT; input files are materialized artifacts.

**Status**: ✅ **NO CHANGE DETECTED** (but enforced more strictly)

**Evidence**:
- `step_factory.py` now explicitly prevents storing parent references in step YAML
- Comment: "Step inherits structure from its parent calculation at runtime"
- This **strengthens** the SSOT invariant

**Impact**: Positive (stronger enforcement)

---

### 2. Step Type Mapping

**Rule**: Public vs machine step types; explicit mapping rules; no prefix/startswith inference.

**Status**: ✅ **NO CHANGE DETECTED** (new capability added)

**Evidence**:
- `registry.py` added `get_for_engine()` but doesn't change existing mapping logic
- Existing `get()` and `has()` methods unchanged
- Machine type mapping still explicit via registry

**Impact**: None (additive only)

---

### 3. Slug/ULID Semantics

**Rule**: Internal references must use ULID; slug is cosmetic.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No changes to slug or ULID generation
- No changes to selector resolution logic (except path handling bug fix)
- ULID usage remains consistent

**Impact**: None

---

### 4. Locks

**Rule**: `edit.lock` vs `run.lock` behavior; reentrancy pitfalls.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No files in `io/`, `core/locks.*`, or lock-related modules changed
- No changes to lock acquisition/release logic

**Impact**: None

---

### 5. Incremental Skip Semantics

**Rule**: Manifest bookkeeping; fingerprints (step_sha/structure/pseudo assets); no output-hash skip.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No changes to manifest files
- No changes to fingerprint calculation
- No changes to incremental skip logic

**Impact**: None

---

### 6. Scan Semantics

**Rule**: `ScanRef` representation and resolve/fingerprint rules; deterministic ordering; `parameter_scan` not in fingerprint.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No changes to scan-related modules
- No changes to parameter scan logic

**Impact**: None

---

### 7. Relax Semantics

**Rule**: Relax is structure transformer, does not provide electronic reference; promote behavior.

**Status**: ⚠️ **POTENTIAL IMPACT** (step YAML change)

**Evidence**:
- Step YAML no longer stores `structure_id`
- Relax steps must now inherit structure from parent calculation at runtime
- **Question**: Does this affect relax → promote workflow?

**Impact**: Unclear - requires validation

**Follow-up**: Test relax → promote workflow to ensure structure association works correctly

---

### 8. Species Map / Pseudo Contract

**Rule**: Project-run SSOT in `calculation.yaml`; overrides behavior.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No changes to species map handling
- No changes to pseudo resolution
- Calculation YAML remains SSOT

**Impact**: None

---

### 9. Provenance / .history Constraints

**Rule**: What is allowed to persist; what is derived/cache.

**Status**: ✅ **NO CHANGE DETECTED**

**Evidence**:
- No changes to provenance modules
- No changes to history storage

**Impact**: None

---

## Questions for Opus / Maintainer

### 1. Resolution absolute_path Contract

**Question**: Was the change from file path to directory path intentional and fully validated?

**Context**: `resolve_calculation()` now returns `absolute_path` pointing to calculation directory instead of `calculation.yaml` file.

**Concerns**:
- Many callsites may assume file path
- Daemon serialization may break
- No migration guide for downstream code

**Recommendation**: Audit all callsites and add explicit documentation

---

### 2. Step YAML Orphaned Fields

**Question**: Should we provide a migration tool to clean up old step files?

**Context**: Existing step YAML files may contain `structure_id` and `parent_calculation_id` that are now ignored.

**Concerns**:
- User confusion ("Why is this field here if it's not used?")
- Mixed old/new state in projects
- No validation warning

**Recommendation**: Add loader warning or migration utility

---

### 3. Relax → Promote Workflow

**Question**: Does the step YAML change affect relax → promote workflow?

**Context**: Steps no longer store `structure_id`; they inherit from parent calculation at runtime.

**Concerns**:
- Promote may depend on step-level structure association
- Need to verify promote reads from calculation, not step

**Recommendation**: Add integration test for relax → promote with new model

---

### 4. get_for_engine Fallback Behavior

**Question**: Should `get_for_engine()` return None if engine doesn't have that step type?

**Context**: Currently falls back to `get(step_type)` which may return a different engine's spec.

**Concerns**:
- Fallback behavior may be surprising
- May hide misconfiguration

**Recommendation**: Consider stricter validation (return None instead of fallback)

---

### 5. Absolute Path in RPC/Daemon

**Question**: Does the daemon layer correctly handle calculation directory paths?

**Context**: Daemon may serialize `resolved.absolute_path` and expect file paths.

**Concerns**:
- RPC handlers may break if they expect file paths
- Frontend may not handle directory paths correctly

**Recommendation**: Audit daemon handlers for absolute_path usage

---

## Summary of Risks

### High-Risk Changes

1. **Resolution absolute_path contract** (core/resolution.py)
   - **Impact**: Breaking change for all code using `resolve_calculation().absolute_path`
   - **Mitigation**: Audit callsites, test daemon serialization

2. **Step YAML field removal** (workflow/step_factory.py)
   - **Impact**: Silent compatibility issue, orphaned fields in old files
   - **Mitigation**: Add validation warning, provide migration tool

### Medium-Risk Changes

1. **load_calculation path handling** (core/models.py)
   - **Impact**: Fixes edge case, may change error behavior
   - **Mitigation**: Test edge cases, verify error messages

### Low-Risk Changes

1. **get_for_engine method** (workflow/registry.py)
   - **Impact**: Additive only, well-documented
   - **Mitigation**: None needed

2. **build_structure_vis_payload** (analysis/structure_viz.py)
   - **Impact**: Additive only, pure function
   - **Mitigation**: None needed

3. **Layer change in templates** (workflow/templates.py)
   - **Impact**: Correct layering, no behavior change
   - **Mitigation**: None needed

---

## Test Coverage Concerns

### Tests May Be Overfit

The baseline is "all tests pass", but tests may have been adjusted to match new behavior. Key concerns:

1. **Resolution tests**: May now expect directory paths instead of file paths
2. **Step creation tests**: May not catch orphaned fields issue
3. **Integration tests**: May use new step files (without `structure_id`) exclusively

**Recommendation**:
- Review test changes between 0873ebf and HEAD
- Add negative tests for old step file compatibility
- Add tests for absolute_path contract expectations

---

## Conclusion

The refactor introduces **two critical semantic changes**:

1. **Resolution absolute_path contract** - intentional but breaking
2. **Step YAML field removal** - intentional architectural improvement but creates compatibility ambiguity

Both changes are **architecturally sound** but carry **high regression risk** due to:
- Breaking contracts without clear migration path
- Silent compatibility issues (orphaned fields)
- Potential daemon/RPC layer assumptions

**Overall Assessment**: The kernel changes are **minimal and focused**, but the two critical changes require **careful validation** of:
1. All `resolve_calculation()` callsites
2. Daemon/RPC serialization
3. Old step file compatibility
4. Relax → promote workflow

**Recommendation**:
- Add explicit validation for orphaned fields
- Document absolute_path contract clearly
- Test mixed old/new project states
- Audit daemon layer for path assumptions

---

**End of Audit Report**
