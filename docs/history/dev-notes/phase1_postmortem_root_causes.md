# Phase 1 IR Landing - Postmortem: Root Cause Analysis

**Date**: 2025-01-XX  
**Status**: Forensic Review (No Fixes Implemented)  
**Goal**: Identify root causes of 11 test failures without changing logic

---

## A) Minimal Reproduction Summary

### Test Failures (11 total, 177 passing)

#### Group 1: Boolean Format Mismatch (6 failures)

Tests expecting `.true.`/`.false.` (QE string format) but receiving Python `True`/`False`:

1. `tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_explicit_noncolin`
2. `tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_soc_explicit`
3. `tests/unit/test_preset_integration.py::TestApplyPresetsToStep::test_apply_can_skip_physics_validation`
4. `tests/unit/test_detector_b.py::TestCompilerStringOptions::test_compile_presets_string_noncollinear_soc`
5. `tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_deletes_nspin`
6. `tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_soc_deletes_nspin`

**Failure Pattern**: `assert system["noncolin"] == ".true."` fails with `AssertionError: assert True == '.true.'`

#### Group 2: Precision Detection Returns Custom (5 failures)

Tests expecting `PrecisionOption` but receiving `CUSTOM`:

1. `tests/unit/test_precision_advisor.py::TestCompilerDetectorEquivalence::test_equivalence_via_variants_detection`
2. `tests/unit/test_paramspace_contract.py::TestPrecisionRoundtrip::test_roundtrip_low`
3. `tests/unit/test_paramspace_contract.py::TestPrecisionRoundtrip::test_roundtrip_med`
4. `tests/unit/test_paramspace_contract.py::TestPrecisionRoundtrip::test_roundtrip_high`
5. `tests/unit/test_paramspace_contract.py::TestPrecisionRoundtrip::test_unrelated_key_wildcard`

**Failure Pattern**: `assert detected == PrecisionOption.MED` fails with `AssertionError: assert Custom == <PrecisionOption.MED: 'med'>`

---

## B) ParamSpace Invariants Audit

### Files Touched for IR Migration

**Core ParamSpace Logic Files**:
- `src/quantumvitas/presets/paramspace.py` - Core ParamSpace definition and matching/compilation logic
- `src/quantumvitas/presets/spaces_registry.py` - Registry API (detect_dimension, compile_dimension_patch)
- `src/quantumvitas/presets/variants_registry.py` - Variant-specific API (detect_dimension_for_step, compile_dimension_patch_for_step)

### Change Categories

#### (i) Rename/Key-Space Substitution Only

**Files**: `src/quantumvitas/presets/paramspace.py`
- **Function**: `ParamKey.key` field (conceptually renamed to IR key, but no code changes)
- **Evidence**: Documentation comment added (line 64): "key: IR parameter key name (conceptually IR, but values same as QE in v0)"
- **Status**: ✅ No semantic changes - keys are now understood to be IR keys, but ParamSpace logic unchanged

#### (ii) Normalization/Type Conversion Changes

**Files**: `src/quantumvitas/presets/spaces_registry.py`, `src/quantumvitas/presets/variants_registry.py`

1. **`detect_dimension()` (spaces_registry.py, lines 190-193, 220-221)**:
   - **Change**: Added `qe_yaml_to_ir_yaml()` conversion before `match_profile()` or `match_precision_profile()`
   - **Type**: Normalization (QE YAML → IR YAML)
   - **Evidence**: ParamSpace matching now operates on IR keys/values instead of QE keys/values

2. **`compile_dimension_patch()` (spaces_registry.py, lines 353-382)**:
   - **Change**: Added `qe_yaml_to_ir_yaml()` before compilation, `ir_patch_to_qe_patch()` after
   - **Type**: Normalization (bidirectional conversion at boundaries)
   - **Evidence**: ParamSpace compilation now produces IR patches, then converts to QE patches

3. **`detect_dimension_for_step()` (variants_registry.py, lines 499-501)**:
   - **Change**: Added `qe_yaml_to_ir_yaml()` before `match_profile()`
   - **Type**: Normalization (same as detect_dimension)

4. **`compile_dimension_patch_for_step()` (variants_registry.py, lines 311-340)**:
   - **Change**: Added `qe_yaml_to_ir_yaml()` before compilation, `ir_patch_to_qe_patch()` after
   - **Type**: Normalization (same as compile_dimension_patch)

**Key Finding**: ParamSpace core logic (`match_profile()`, `compile_profile_patch()`) was NOT modified. Only boundaries added conversion layers.

#### (iii) Semantic Logic Changes (NOT ALLOWED)

**Status**: ✅ **NO SEMANTIC CHANGES FOUND**

**Evidence**:
- `match_profile()` function signature and logic unchanged (lines 241-309 in paramspace.py)
- `compile_profile_patch()` function signature and logic unchanged (lines 316-377 in paramspace.py)
- Wildcard/NotApplicable/Oracle handling unchanged
- Canonical deletion rules unchanged
- Matching tolerance logic unchanged
- Value comparison semantics unchanged

**Conclusion**: ParamSpace logic is preserved. Only dimension-2 keys are conceptually renamed to IR keys, and conversion layers added at boundaries.

---

## C) Canonical Encoding Contract Audit

### Question: What is the canonical boolean representation in step.yaml?

**Investigation Results**:

1. **YAML Serialization Default Behavior**:
   - PyYAML `yaml.safe_dump()` serializes Python `bool` as `true`/`false` (YAML boolean literals)
   - PyYAML does NOT automatically convert `True` → `.true.` string
   - **Evidence**: Test with `yaml.safe_dump({'noncolin': True})` produces `noncolin: true` (YAML bool, not string)

2. **StepDoc Write Path**:
   - **Location**: `src/quantumvitas/core/yaml_io.py::save_yaml_doc()` (line 117-147)
   - **Serialization**: Uses `yaml.safe_dump(data, default_flow_style=False, sort_keys=False)` (line 77 in yaml_io.py)
   - **Conclusion**: step.yaml uses YAML boolean literals (`true`/`false`), not QE strings (`.true.`/`.false.`)

3. **Pre-IR Compiler Output Format**:
   - **Evidence**: Docstring in `compile_presets()` (line 217) shows example: `'noncolin': '.false.'`
   - **Evidence**: Tests assert `system["noncolin"] == ".true."` (expecting QE string format)
   - **Conclusion**: Pre-IR compiler returned `.true.`/`.false.` strings in patch dicts

4. **Current IR Migration Behavior**:
   - **Location**: `src/quantumvitas/ir/backends/qe/mapping.py::ir_to_qe_param()` (line 83)
   - **Code**: `qe_value = ir_value` (no conversion for booleans)
   - **Result**: Compiler output now contains Python `True`/`False` instead of `.true.`/`.false.`
   - **Evidence**: Test run shows `compile_magnetism()` returns `{'SYSTEM': {'noncolin': True}}` (Python bool)

5. **Step.yaml Format (Post-IR)**:
   - **Evidence**: Test with `apply_presets_to_step()` shows step.yaml contains Python `True`/`False`
   - **Conclusion**: step.yaml uses Python bools (serialized as YAML `true`/`false`)

**Summary**:
- **Pre-IR compiler output**: `.true.`/`.false.` strings (QE format)
- **Post-IR compiler output**: Python `True`/`False` (IR format, passed through)
- **step.yaml format**: Python `True`/`False` (serialized as YAML `true`/`false`)

**Boundary Question**: Where should QE string format exist?
- **Answer**: Tests expect QE strings in compiler OUTPUT (patch dicts), but step.yaml uses Python bools
- **Conclusion**: The boundary shifted - compiler output format changed from QE strings to Python bools

---

## D) Precision Detector Pipeline Audit

### Test Case: `test_roundtrip_med`

**Expected Flow**:
1. `compile_precision(PrecisionOption.MED, ...)` returns patch with `K_POINTS_CARD` at top level
2. Test builds params dict: `{"SYSTEM": ..., "ELECTRONS": ..., "cards": {"K_POINTS": compiled["K_POINTS_CARD"]}}`
3. `detect_precision(params, ...)` → `detect_dimension("precision", params, ...)` → `match_precision_profile()`
4. `match_precision_profile()` calls `get_yaml_value(ir_yaml, "cards", "K_POINTS")`
5. Return: `PrecisionOption.MED`

**Actual Flow (Traced)**:
1. `compile_precision()` returns patch with BOTH `cards.K_POINTS` AND `K_POINTS_CARD` (backward compat shim at line 152-153 in compiler.py)
2. Test uses `compiled["K_POINTS_CARD"]` to build params dict (line 206 in test_paramspace_contract.py)
3. `detect_dimension()` calls `qe_yaml_to_ir_yaml(params, qe_module="pw")` (line 190 in spaces_registry.py)
4. **PROBLEM**: `qe_yaml_to_ir_yaml()` iterates over `params.items()`:
   - Sees `"cards": {"K_POINTS": {...}}` → converts `cards.K_POINTS` → IR `cards.K_POINTS` ✓
   - Sees `"K_POINTS_CARD": {...}` at top level → NOT in IR mapping → skipped ✗
5. Result: `ir_yaml` has empty `CARDS: {}` (normalized to uppercase) and empty `K_POINTS_CARD: {}`
6. `match_precision_profile()` calls `get_yaml_value(ir_yaml, "cards", "K_POINTS")` (line 762 in paramspace.py)
7. **PROBLEM**: `get_yaml_value()` looks for `cards.K_POINTS`, but `ir_yaml["CARDS"]` is empty dict
8. Result: `present=False`, `match_precision_profile()` returns `None` (line 765)
9. `detect_dimension()` returns `CUSTOM` (line 229 in spaces_registry.py)

**Root Cause**: Structural mismatch between compilation output and detection input:
- **Compilation**: Returns `K_POINTS_CARD` at top level (backward compat shim in `compile_precision()`, line 152-153)
- **Detection**: Expects `cards.K_POINTS` (IR mapping structure)
- **Conversion**: `qe_yaml_to_ir_yaml()` only converts mapped keys, skips `K_POINTS_CARD` (not in mapping)

**Evidence**:
- `compile_precision()` line 152-153: Backward compat shim creates `K_POINTS_CARD` from `cards.K_POINTS`
- IR mapping (`IR_TO_QE_MAPPING`) has `"K_POINTS": ("pw", "cards", "K_POINTS")`, NOT `K_POINTS_CARD`
- Test line 206: Uses `compiled["K_POINTS_CARD"]` (not `compiled["cards"]["K_POINTS"]`)
- `qe_yaml_to_ir_yaml()` line 224-227: Skips unmapped keys with `continue` on `KeyError`

---

## E) Root Cause Analysis (Final)

### Root Cause #1: Boolean Format Boundary Shift

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py::ir_to_qe_param()` (line 83)

**Pre-IR Behavior** (CONFIRMED):
- Compiler output contained `.true.`/`.false.` strings (QE format)
- Evidence: Docstring in `compile_presets()` shows `.false.` string format (line 217)
- Evidence: Tests assert against QE string format

**Post-IR Behavior**:
- `ir_to_qe_param()` returns Python bools (no conversion, line 83: `qe_value = ir_value`)
- Compiler output contains Python `True`/`False`
- Tests fail because they expect QE strings

**Impact**: 6 test failures

### Root Cause #2: K_POINTS_CARD Structure Mismatch

**Location**: `src/quantumvitas/presets/compiler.py::compile_precision()` (line 152-153)

**Problem**:
- `compile_precision()` returns `K_POINTS_CARD` at top level (backward compat shim)
- IR mapping expects `cards.K_POINTS` (not `K_POINTS_CARD`)
- `qe_yaml_to_ir_yaml()` skips `K_POINTS_CARD` (not in mapping)
- `match_precision_profile()` looks for `cards.K_POINTS`, finds empty dict, returns `None`

**Impact**: 5 test failures

**Evidence Chain**:
1. `compile_precision()` line 152-153: Creates `K_POINTS_CARD` from `cards.K_POINTS`
2. Test line 206: Uses `compiled["K_POINTS_CARD"]` to build params dict
3. `qe_yaml_to_ir_yaml()` line 224-227: Skips `K_POINTS_CARD` (not in mapping)
4. `match_precision_profile()` line 762: Looks for `cards.K_POINTS`, finds empty dict
5. Returns `None` → `detect_dimension()` returns `CUSTOM`

---

## F) Fix Options (NOT IMPLEMENTED)

### Option A: Restore QE String Format in IR→QE Adapter (Boolean)

**Change**: Modify `ir_to_qe_param()` to convert Python bool → QE string for boolean parameters

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py::ir_to_qe_param()` (line 83)

**Implementation**:
```python
# In ir_to_qe_param(), after getting qe_key:
if isinstance(ir_value, bool) and qe_key in ["noncolin", "lspinorb", "nosym", "noinv"]:
    qe_value = ".true." if ir_value else ".false."
else:
    qe_value = ir_value
```

**Pros**:
- Matches pre-IR compiler output format
- Tests pass without modification
- Keeps QE format at compiler output boundary

**Cons**:
- Requires explicit conversion logic
- Breaks symmetry: QE→IR normalizes strings to bool, but IR→QE converts back to strings
- step.yaml would contain QE strings (but PyYAML serializes as YAML bools anyway)

**Risk**: Low - Restores pre-IR behavior at compiler output boundary

### Option B: Update Tests to Expect Python Bools

**Change**: Modify test assertions to expect Python `True`/`False` instead of `.true.`/`.false.`

**Locations**: 6 test files (see Group 1 failures)

**Pros**:
- Aligns with Python-native types in step.yaml
- Simpler (no conversion needed)
- More Pythonic

**Cons**:
- Changes test contract (tests are the spec for compiler output format)
- If external code expects QE strings, this breaks backward compatibility
- Violates "no behavior change" constraint if pre-IR used QE strings

**Risk**: High - Changes compiler output contract, violates backward compatibility

### Option C: Fix K_POINTS_CARD Conversion in qe_yaml_to_ir_yaml

**Change**: Handle `K_POINTS_CARD` → `cards.K_POINTS` conversion in `qe_yaml_to_ir_yaml()`

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py::qe_yaml_to_ir_yaml()` (line 179)

**Implementation**:
```python
# After converting all mapped keys, handle K_POINTS_CARD special case:
if "K_POINTS_CARD" in qe_yaml and "cards" not in ir_yaml:
    ir_yaml["cards"] = {}
if "K_POINTS_CARD" in qe_yaml:
    ir_yaml["cards"]["K_POINTS"] = qe_yaml["K_POINTS_CARD"]
```

**Pros**:
- Fixes precision detection without changing compilation logic
- Preserves backward compat shim in `compile_precision()`
- Minimal change

**Cons**:
- Adds special-case handling for backward compat format
- Creates asymmetry: compilation outputs both formats, detection handles both

**Risk**: Low - Adds compatibility layer for backward compat format

### Option D: Remove K_POINTS_CARD Backward Compat Shim

**Change**: Remove backward compat shim from `compile_precision()`, update tests to use `cards.K_POINTS`

**Location**: `src/quantumvitas/presets/compiler.py::compile_precision()` (line 152-153)

**Implementation**:
- Remove lines 152-153 (backward compat shim)
- Update tests to use `compiled["cards"]["K_POINTS"]` instead of `compiled["K_POINTS_CARD"]`

**Pros**:
- Cleaner: single canonical format
- Aligns with IR mapping structure
- No special-case handling needed

**Cons**:
- Requires updating tests (6 precision roundtrip tests)
- May break external code that expects `K_POINTS_CARD`

**Risk**: Medium - Requires test updates, but aligns with canonical format

---

## Summary

**Root Causes Identified**:
1. ✅ **Boolean format boundary shift**: Compiler output changed from QE strings to Python bools
2. ✅ **K_POINTS_CARD structure mismatch**: Backward compat shim creates format not handled by IR conversion

**ParamSpace Logic**:
- ✅ **UNCHANGED**: Core logic (`match_profile`, `compile_profile_patch`) preserved
- ✅ **ONLY boundary changes**: Conversion layers added at YAML I/O boundaries

**Recommended Fixes**:
1. **Boolean format**: Option A (restore QE strings in IR→QE adapter) - preserves pre-IR behavior
2. **K_POINTS_CARD**: Option C (handle in qe_yaml_to_ir_yaml) - minimal change, preserves backward compat

---

**Document Status**: Complete - All root causes identified with code evidence, fix options proposed
