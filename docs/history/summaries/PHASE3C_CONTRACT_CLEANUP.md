# Phase 3C Contract Cleanup

This document tracks the contract cleanup pass required before Phase 3C can be considered complete.

## Issues Identified

### I1. Step ULID Stability Violation

**Symptom**: Test fixture creates step with ULID A, but execution result shows ULID B.

**Root Cause Analysis** (IN PROGRESS):
- `QVService.init_step()` creates step via `create_step_doc()` → generates ULID, saves to step.yaml
- `Calculation.from_yaml(materialize_steps=True)` loads steps via `_build_step()` → reads step_id from calculation.yaml
- Step file resolved via `require_step(..., step_id)` → should return same step file with same ULID
- **HYPOTHESIS**: Step ULID should be stable. Need to verify if any code path creates new steps or modifies ULIDs.

**Status**: Analysis in progress

### I2. Structure Resolution Hack

**Current State**: 
- `CalculationRunner` passes `structure_id` and `project_root` via `step.options`
- `PySCFEngine.run_step()` reads structure from `step.options['structure_id']` and `step.options['project_root']`

**Contract Violation**: 
- Structure should be resolved via `calculation.structure_id` directly, not via step.options
- Engine should not depend on step.options for structure resolution

**Fix Required**:
- Engine should receive structure_id directly or resolve from calculation context
- Remove step.options hacks

**Status**: Identified, fix pending

### I3. Verification Logic Uses Step-Type String Matching

**Current State**:
- `evaluate_step_result()` detects PySCF steps by checking step_type string against a set
- This is fragile and not engine-driven

**Contract Violation**:
- Verification should be engine-specific, not step-type-heuristic
- Each engine should have its own verification logic

**Fix Required**:
- Introduce `Engine.verify_step_done()` or similar hook
- Move verification logic to engines
- Remove step-type string matching from verification

**Status**: Identified, fix pending

### I4. Artifact Directory Contract

**Current State**:
- Artifacts stored in `raw/step_artifacts/{step_ulid}/`
- This is correct (step_ulid-keyed, not step_type-keyed)

**Verification Needed**:
- Confirm no step_type-based directories exist
- Add test for multiple steps of same type (should have separate artifact dirs)

**Status**: Need verification

## Fix Plan

1. **Step ULID Stability** (HIGH PRIORITY)
   - Trace step ULID flow end-to-end
   - Identify where ULID changes (if it does)
   - Fix or document the behavior
   - Update tests to assert stable ULIDs

2. **Structure Resolution** (HIGH PRIORITY)
   - Remove step.options hacks
   - Engine should resolve structure from calculation context
   - Update PySCFEngine to use calculation.structure_id directly

3. **Engine-Driven Verification** (MEDIUM PRIORITY)
   - Add Engine.verify_step_done() hook
   - Move verification logic to engines
   - Update evaluate_step_result to use engine verification

4. **Artifact Directory Tests** (MEDIUM PRIORITY)
   - Add test for multiple steps of same type
   - Verify artifact dirs are step_ulid-keyed

5. **Regression Tests** (MEDIUM PRIORITY)
   - Step ULID stability test
   - Engine routing test
   - Artifact directory contract test

6. **Changelog** (LOW PRIORITY)
   - Document all changes
   - Explain why changes were needed

