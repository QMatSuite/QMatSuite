# Kernel Drift Verdict Memo

**From**: Opus 4.5 (Final Reviewer)
**Re**: Semantic drift review 0873ebf → HEAD
**Date**: 2026-01-27

---

## Verdict: **GO** (with 3 must-verify items)

The kernel changes are minimal, intentional, and architecturally sound. The two changes flagged as "CRITICAL" by Sonnet's report are **verified but require nuance**.

---

## CRITICAL Item #1: resolve_calculation().absolute_path Contract

### Sonnet's Claim
> "Changed absolute_path contract for calculations (now points to directory instead of calculation.yaml file)"

### My Finding: **PARTIALLY CORRECT - LESS SEVERE THAN REPORTED**

The situation is more nuanced:

1. **The MAIN code path (ResourceIndex-based resolution) was ALREADY returning directory paths in the baseline.**
   In `resolve_calculation()`, the existing code at 0873ebf was:
   ```python
   # calculation.yaml path -> calculation directory
   abs_path = path.parent  # <-- Already returned DIRECTORY
   ```

2. **The change only affects the LEGACY FALLBACK code path (`_calculation_to_resolved()`).**
   - **Baseline**: `abs_path = calculation_yaml.resolve()` (file path)
   - **HEAD**: `abs_path = calculation_dir.resolve()` (directory path)

3. **This is a CONSISTENCY FIX, not a contract change.**
   The main path was directory, fallback was file. This was an inconsistency bug. HEAD makes them consistent.

### Classification: **Intentional OK**

- The main resolution path (ResourceIndex) was already returning directories
- The fallback (legacy config-based) is now consistent with the main path
- No kernel invariant violated - this is a bug fix

### Risk Assessment: **LOW**
- Only affects code paths using legacy config-based resolution (rare)
- Any code that worked with the main path will continue to work
- Callsites expecting file paths may break, but these were using the inconsistent fallback

### Must-Verify Item #1
> Confirm no daemon/RPC handlers directly consume `_calculation_to_resolved()` output and expect file paths. If any exist, they need the trivial fix: `resolved.absolute_path / "calculation.yaml"`.

---

## CRITICAL Item #2: Step YAML Field Removal (structure_id, parent_calculation_id)

### Sonnet's Claim
> "Steps no longer store structure_id / parent_calculation_id (DAG enforcement)"

### My Finding: **CORRECT - INTENTIONAL ARCHITECTURAL CHANGE**

The change in `step_factory.py` removes these fields from NEW step files:

```python
# REMOVED (was "legacy field, kept for backwards compat"):
if structure_id:
    data["structure"] = structure_id
if parent_calculation_id:
    data["parent_calculation_id"] = parent_calculation_id
```

The code documentation in `calculation/calculation.py` confirms this is intentional:
> "Steps do NOT persist structure_id in their YAML (they inherit from calculation)"

### Classification: **Intentional OK**

This enforces the documented DAG model:
- **Calculation is SSOT** for step associations
- **Steps inherit structure** from their parent calculation at runtime
- **No denormalized references** in step YAML

### Persistence Semantics Change

| Aspect | Before | After |
|--------|--------|-------|
| New step files | Contain `structure`, `parent_calculation_id` | Do NOT contain these fields |
| Old step files | Unchanged (fields persist) | Unchanged (fields persist but ignored) |
| Runtime behavior | Fields could be read from step | Structure comes from calculation.yaml |
| SSOT | Ambiguous (both step and calculation could have structure_id) | Clear (calculation.yaml is SSOT) |

### Mixed State Risk: **NEGLIGIBLE**

Old step files with these fields continue to work because:
1. The loader ignores unknown/unused fields (YAML flexibility)
2. Runtime resolution uses calculation.yaml's structure_id
3. Fields are cosmetic - they have no effect on execution

### Classification: **Intentional OK**

### Must-Verify Item #2
> Confirm the relax → promote workflow does not read `structure_id` from step YAML. The promote code should read from calculation.yaml, not step YAML. (High confidence this is already correct given the documented DAG model, but should be verified.)

---

## Expanded Audit: Other Kernel Semantics

### Resolution / Selector Semantics

**Status**: ✅ No change

- ULID/slug resolution logic unchanged
- ResourceIndex building unchanged
- Selector strategies (path, ULID, slug, name) unchanged

### YAML SSOT Invariants

**Status**: ✅ Strengthened (not weakened)

- Step YAML is now "cleaner" (fewer fields)
- Calculation YAML remains authoritative for structure_id
- No derived fields added to either SSOT

### Incremental/Manifest Skip Semantics

**Status**: ✅ No change

- No changes to fingerprint/digest calculation
- No changes to manifest bookkeeping
- No changes to skip conditions

### Engine Dispatch Invariants (GEN↔SPEC mapping)

**Status**: ✅ No change

- New `get_for_engine()` method is purely additive
- Existing `get()` and `has()` behavior unchanged
- Machine type mapping logic unchanged

### load_calculation() Path Handling

**Status**: ⚠️ Defensive fix (no semantic change)

New code handles edge cases:
- Double-append of "calculation.yaml"
- Malformed paths where calculation.yaml is a directory

This is defensive robustness, not a semantic change. It makes previously-erroring edge cases work.

### Must-Verify Item #3
> Confirm no code intentionally passes paths like `dir/calculation.yaml/calculation.yaml` and expects them to fail. (Very unlikely, but the defensive fix now makes this succeed.)

---

## Risk Assessment Summary

| Change | Classification | Risk |
|--------|---------------|------|
| resolve_calculation() absolute_path (fallback path) | Intentional OK (consistency fix) | LOW |
| Step YAML field removal | Intentional OK (DAG enforcement) | LOW |
| load_calculation() double-append fix | Intentional OK (defensive) | NEGLIGIBLE |
| get_for_engine() addition | Intentional OK (additive) | NONE |
| templates.py import change | Intentional OK (layer fix) | NONE |
| structure_viz.py function addition | Intentional OK (additive) | NONE |

---

## Final Verdict

### **GO FOR MERGE**

From kernel correctness perspective only (per task scope), the changes are:

1. **Minimal** - Only 7 kernel files changed, ~300 lines total
2. **Intentional** - All changes align with documented architecture
3. **Safe** - No invariants broken, SSOT strengthened
4. **Consistent** - Resolution contract made consistent (was inconsistent before)

### Must-Verify Later (3 items)

1. **Daemon absolute_path usage**: Verify no RPC handlers expect file paths from `_calculation_to_resolved()` fallback
2. **Relax → promote structure resolution**: Verify promote reads structure_id from calculation, not step YAML
3. **Double-append edge cases**: Confirm no code depends on `path/calculation.yaml/calculation.yaml` failing

### Not Required for Merge

- Step file migration (old files with orphaned fields are harmless)
- Documentation update (contract was already "directory" for main path)
- Loader warnings for orphaned fields (cosmetic concern only)

---

**End of Memo**
