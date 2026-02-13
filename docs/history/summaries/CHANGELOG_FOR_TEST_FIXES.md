# Changelog for Test Fixes

This document tracks changes made to fix tests or address test-related issues that were not part of the original implementation plan.

## 2025-01-10: Contract Cleanup (Phase 3C)

### Contract I1: Step ULID Stability Fix
**File**: `src/quantumvitas/calculation/calculation.py`

**Change**: Modified `_build_step()` to use `step_resolved.meta` directly (from step.yaml) instead of calling `_build_step_meta()` with `step_data` from calculation.yaml. This fixes step ULID stability - ULIDs no longer change between fixture creation and execution.

**Why Required**: Integration tests were failing because step ULIDs were changing, causing test assertions to fail. The root cause was that `_build_step_meta()` was generating new ULIDs when `step_data.get("meta")` returned `None` (calculation.yaml doesn't have a `meta` field).

**Impact**: Tightens contract - step ULID is now guaranteed to be stable across materialization and execution. Added assertion to enforce ULID consistency between calculation.yaml and step.yaml.

**Documentation**: See `docs/design/CONTRACT_I1_STEP_ULID_FIX.md`

