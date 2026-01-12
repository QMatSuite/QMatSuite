# Contract I1: Step ULID Stability Fix

## Problem

Integration tests were failing because step ULIDs were changing between fixture creation and execution. The test fixture created a step with ULID A, but during execution, the step had ULID B.

## Root Cause Analysis

The issue was in `src/quantumvitas/calculation/calculation.py`, in the `_build_step` function:

1. `_build_step` calls `require_step()` which resolves the step file and returns `step_resolved` with `step_resolved.meta.id` containing the ULID from step.yaml.

2. However, `_build_step` was then calling `_build_step_meta(step_data=step_data, ...)` where `step_data` comes from `calculation.yaml`, which does NOT contain a `meta` field.

3. `_build_step_meta` calls `ResourceMeta.from_dict(step_data.get("meta"), ...)`, which receives `None` (since calculation.yaml doesn't have a `meta` field).

4. When `ResourceMeta.from_dict()` receives `None`, it calls `generate_resource_id()` as a fallback, creating a NEW ULID.

5. This newly generated ULID was then used to create the Step object, causing the ULID mismatch.

## Solution

**CONTRACT I1: Step ULID is the identity of a step resource. Step ULID must NOT change after creation.**

The fix:
- Use `step_resolved.meta` directly (from step.yaml) instead of calling `_build_step_meta()` with `step_data` from calculation.yaml.
- Add an assertion to ensure `step_id` from calculation.yaml matches `step_meta.id` from step.yaml, preventing silent ULID mismatches.

## Files Changed

- `src/quantumvitas/calculation/calculation.py`:
  - Modified `_build_step()` to use `step_resolved.meta` instead of `_build_step_meta(step_data)`.
  - Added assertion to enforce ULID consistency.

## Impact

- Step ULIDs are now stable across materialization and execution.
- Tests can safely assert against step ULIDs from fixtures.
- No silent ULID replacement occurs.

## Notes

- `_build_step_meta` is still used in `_build_step_inspection` for legacy/fallback paths, but it is no longer used in the primary `_build_step` path.
- The assertion ensures that calculation.yaml and step.yaml remain consistent.

