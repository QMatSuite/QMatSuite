# Implementation Plan: ParamSpace Invariant-Aware Apply

## Phase 0 – Ground Rules (Read Only)

- [x] Read and understand the ParamSpace Constitution (Chinese doc)
- [x] Confirm single-writer ownership for all keys
- [x] Confirm degauss writer = PrecisionParamSpace

## Phase 1 – ParamSpace API Extension

**Goal:** Allow every ParamSpace to enforce invariants even when CUSTOM.

- [x] Add a new hook method to ParamSpace:

```python
def apply_invariants(self, yaml_state, oracle):
    pass  # default no-op
```

- [x] Ensure this method is called unconditionally during apply

## Phase 2 – Apply Scheduler Update

**Goal:** Guarantee oracle reads YAML truth.

- [x] Split apply execution into two ordered phases:
  - Prerequisite ParamSpaces (occupation, step_type, etc.)
  - Dependent ParamSpaces (precision)
- [x] Hardcode the order (no DAG needed yet)
- [x] Ensure YAML state is mutated in-place between phases

## Phase 3 – Oracle Implementation

**Goal:** Centralize semantic prerequisite logic.

- [x] Implement Oracle (or equivalent) as a read-only helper
- [x] Add `degauss_applicability()`:
  - Reads parsed YAML
  - Returns True iff occupations indicate smearing
- [x] Ensure oracle does NOT access preset IDs or detect results

## Phase 4 – PrecisionParamSpace Changes

**Goal:** Enforce degauss invariants correctly.

- [x] Move all degauss writing/deleting logic exclusively into PrecisionParamSpace
- [x] Override `apply_invariants()` in PrecisionParamSpace:
  - If `oracle.degauss_applicability() == False`:
    - Ensure `SYSTEM.degauss` is absent (delete if present)
  - Else:
    - Do nothing (Strategy A)
- [x] Ensure this invariant enforcement runs even when precision is CUSTOM
- [x] Add degauss writing logic to precision preset compilation (LOW/MED/HIGH → 0.01/0.02/0.03)

## Phase 5 – Preserve Existing Matrix Logic

**Goal:** Do not regress detect/apply symmetry.

- [x] Do NOT modify existing precision matrices except:
  - degauss column remains dynamic (depends on oracle)
- [x] Ensure NOT_APPLICABLE semantics remain unchanged
- [x] Ensure detect logic is untouched

## Phase 6 – Tests (Mandatory)

Add or update tests to cover:

- [x] smearing → fixed: degauss is removed even if precision is CUSTOM
- [x] precision CUSTOM (conv_thr changed) still deletes degauss when not applicable
- [x] smearing + no degauss: detect = CUSTOM, apply does not auto-fill
- [x] user changes precision preset: degauss written correctly
- [x] apply order correctness (occupation before precision)

## Phase 7 – Code Review Checklist

Before merging:

- [x] No ParamSpace writes keys it does not own
  - Verified: degauss is only written/deleted by Precision ParamSpace
  - OccupationsScheme ParamSpace does not write degauss (only detects it)
- [x] No Oracle function reads preset IDs
  - Verified: Oracle only reads YAML state (SYSTEM.occupations)
  - Oracle.degauss_applicability() returns bool, not preset IDs
- [x] No invariant logic hidden in detect
  - Verified: degauss deletion is in apply_invariants(), not in detect
  - Detect logic unchanged (only reads, never deletes)
- [x] No shared writing or post-hoc cleanup code
  - Verified: degauss deletion is in PrecisionParamSpace.apply_invariants()
  - No cleanup code in integration layer
- [x] Custom apply behavior explicitly tested
  - Verified: test_a2_precision_custom_still_deletes_degauss covers this
  - All 8 tests in test_paramspace_invariants.py pass
