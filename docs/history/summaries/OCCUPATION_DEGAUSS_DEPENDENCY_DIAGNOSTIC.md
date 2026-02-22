# Occupation Detection Dependency on Degauss/Precision - Diagnostic Report

## Summary

**Observed Behavior**: When precision = MED (degauss = 0.02), occupation is detected as `smearing_gaussian`. When precision = LOW or HIGH (degauss = 0.01 / 0.03), occupation becomes `CUSTOM`.

**Root Cause**: Occupation detection directly reads `degauss` from YAML and matches against a hardcoded profile `SMEARING_GAUSSIAN_0.02` that requires `degauss = 0.02` (tolerance 1e-12). When precision compilation writes `degauss = 0.01` or `0.03`, occupation detection fails to match because there is no profile for those values.

**Stage of Issue**: The issue occurs in the **detect stage**, not in compile/aggregation. Occupation detection itself returns `CUSTOM` when `degauss != 0.02`.

**Coupling Type**: Indirect coupling via shared YAML state. Precision compilation writes degauss values; occupation detection reads them. There is no direct dependency on precision detection results.

---

## Observed Behavior

### Symptom
- **Precision = MED** (degauss = 0.02): → occupation detected as `smearing_gaussian` ✅
- **Precision = LOW** (degauss = 0.01): → occupation becomes `CUSTOM` ❌
- **Precision = HIGH** (degauss = 0.03): → occupation becomes `CUSTOM` ❌

### Expected vs Actual
- **Expected**: Occupation should be detected as `smearing_gaussian` regardless of degauss value (0.01, 0.02, or 0.03), as long as `occupations="smearing"`, `smearing="gaussian"`, and degauss is present.
- **Actual**: Occupation is only detected as `smearing_gaussian` when degauss = 0.02 exactly.

---

## Relevant Code Paths

### Call Graph

```
UI: detect_presets (daemon call)
  ↓
integration.py: detect_presets_from_calculation()
  ↓
detector.py: detect_all_presets()
  ↓
detector.py: detect_dimension_from_steps(dimension="occupations_scheme")
  ↓
variants_registry.py: detect_dimension_for_step("occupations_scheme", step_type, step_yaml)
  ↓
paramspace.py: match_profile(occupations_scheme_paramspace, step_yaml)
  ↓
paramspace.py: ParamKey.matches(actual_degauss, expected_degauss=0.02)
  → Returns None (no match) if degauss != 0.02
  → Returns "SMEARING_GAUSSIAN_0.02" if degauss == 0.02
```

### Key Files

1. **`src/qmatsuite/presets/paramspace.py`** (lines 482-548)
   - Defines `build_occupations_scheme_paramspace()`
   - Profile `SMEARING_GAUSSIAN_0.02` requires `degauss = 0.02` (line 540)
   - `key_degauss` has tolerance `1e-12` (line 519)

2. **`src/qmatsuite/presets/variants_registry.py`** (lines 417-461)
   - `detect_dimension_for_step()` calls `match_profile()` for occupations_scheme
   - Returns `CUSTOM` if `match_profile()` returns `None` (line 456)

3. **`src/qmatsuite/presets/variants_registry.py`** (lines 371-387)
   - `_compile_precision_patch_for_step()` writes degauss values:
     - LOW → 0.01
     - MED → 0.02
     - HIGH → 0.03

4. **`src/qmatsuite/presets/paramspace.py`** (lines 260-328)
   - `match_profile()` compares actual YAML values against profile cells
   - For `VALUE` cells, uses `ParamKey.matches()` with tolerance

5. **`src/qmatsuite/presets/paramspace.py`** (lines 95-114)
   - `ParamKey.matches()` uses tolerance for numeric comparison
   - Tolerance is `1e-12` for degauss, effectively requiring exact match

---

## Findings

### Finding 1: Occupation Detection Reads Degauss Directly from YAML

**Location**: `src/qmatsuite/presets/paramspace.py:260-328` (`match_profile()`)

**Evidence**:
- `match_profile()` calls `get_yaml_value(yaml_tree, "SYSTEM", "degauss")` (line 295)
- No dependency on precision detection results
- Reads directly from step YAML state

**Answer to Q1**: ✅ **YES** - Occupation detect reads degauss directly from YAML via `get_yaml_value()`.

---

### Finding 2: Occupation Detection Does NOT Depend on Precision Detect Results

**Location**: `src/qmatsuite/presets/variants_registry.py:417-461` (`detect_dimension_for_step()`)

**Evidence**:
- Occupation detection path does not call precision detection
- No usage of preset registry or resolved precision state
- No inference from precision to occupation

**Answer to Q2**: ❌ **NO** - Occupation detect does not depend on precision detect results. They are independent detection paths.

---

### Finding 3: Hardcoded Profile Requires Degauss = 0.02 Exactly

**Location**: `src/qmatsuite/presets/paramspace.py:537-541`

**Evidence**:
```python
"SMEARING_GAUSSIAN_0.02": {
    key_occupations: Cell.VALUE("smearing"),
    key_smearing: Cell.VALUE("gaussian"),
    key_degauss: Cell.VALUE(0.02),  # Hardcoded to 0.02
}
```

**Tolerance**: `1e-12` (line 519) - effectively exact match for 0.01, 0.02, 0.03

**Answer to Q3**: ⚠️ **YES** - There is implicit inference: "if degauss present and equals 0.02, then occupation must be smearing_gaussian". This is encoded in the ParamSpace profile definition. It is **intentional** (per design), but creates coupling with precision values.

---

### Finding 4: Why Only Degauss=0.02 Behaves Differently

**Root Cause**: The occupations_scheme ParamSpace has only one smearing profile: `SMEARING_GAUSSIAN_0.02`, which requires `degauss = 0.02`.

**Matching Logic**:
- `match_profile()` iterates through all profiles (line 284)
- For `SMEARING_GAUSSIAN_0.02`, it checks if `degauss` matches `0.02` using tolerance `1e-12` (lines 312-314)
- If `degauss = 0.01` or `0.03`, the match fails because:
  - `abs(0.01 - 0.02) = 0.01 > 1e-12` ❌
  - `abs(0.03 - 0.02) = 0.01 > 1e-12` ❌
- If `degauss = 0.02`, the match succeeds:
  - `abs(0.02 - 0.02) = 0.0 <= 1e-12` ✅

**No Special Case for MED**: There is no special handling for MED precision. The behavior is a side effect of:
1. Precision MED writes `degauss = 0.02`
2. Occupation profile requires `degauss = 0.02`
3. They happen to match

**Answer to Q4**: Only `degauss=0.02` works because it's the only value defined in the occupation profile. `0.01` and `0.03` fail because there is no profile for those values. MED is not treated as default; it's coincidental that MED's degauss value matches the hardcoded profile.

---

### Finding 5: Issue is in Detect Stage, Not Compile/Aggregation

**Evidence**:

1. **Detect Stage Output**:
   - When `degauss = 0.02`: `detect_dimension_for_step()` returns `OccupationsSchemeOption.SMEARING_GAUSSIAN`
   - When `degauss = 0.01` or `0.03`: `detect_dimension_for_step()` returns `CUSTOM` (line 456)

2. **Aggregation Logic** (lines 410-415):
   - Simply collects values from all steps
   - If all steps return the same value → return that value
   - If values differ → return CUSTOM
   - **No transformation of detect results**

3. **No Compile/Aggregation Artifact**:
   - The `CUSTOM` result originates from `match_profile()` returning `None`
   - Aggregation does not modify the detect result

**Answer to Q5**: The issue is in the **detect stage**. `match_profile()` returns `None` when `degauss != 0.02`, causing `detect_dimension_for_step()` to return `CUSTOM`. Compile/aggregation does not introduce divergence; it faithfully propagates the detect result.

---

## Data Flow

### YAML → Parsed State → Detect → Compile → UI

```
1. YAML State (step.step.yaml):
   SYSTEM:
     occupations: "smearing"
     smearing: "gaussian"
     degauss: 0.02  (or 0.01, 0.03)

2. Detect Pipeline:
   detect_dimension_from_steps("occupations_scheme")
     ↓
   detect_dimension_for_step("occupations_scheme", step_type, step_yaml)
     ↓
   match_profile(occupations_scheme_paramspace, step_yaml)
     ↓
   For each profile:
     - Check occupations == "smearing" ✅
     - Check smearing == "gaussian" ✅
     - Check degauss == 0.02 (with tolerance 1e-12)
       - If degauss = 0.02: ✅ Match → return "SMEARING_GAUSSIAN_0.02"
       - If degauss = 0.01: ❌ No match (0.01 - 0.02 = 0.01 > 1e-12)
       - If degauss = 0.03: ❌ No match (0.03 - 0.02 = 0.01 > 1e-12)
     ↓
   If no match: return None → CUSTOM

3. Compile/Aggregation:
   detect_dimension_from_steps() collects results from all steps
   - If all steps return SMEARING_GAUSSIAN → return SMEARING_GAUSSIAN
   - If any step returns CUSTOM → return CUSTOM

4. UI:
   integration.py: detect_presets_from_calculation()
     ↓
   Converts enum to string: "smearing_gaussian" or "Custom"
     ↓
   Returns to daemon → UI displays result
```

---

## Case-by-Case Analysis

| Case | Degauss Value | Precision | Occupation Detect Result | Why |
|------|---------------|-----------|--------------------------|-----|
| 1 | 0.01 | LOW | `CUSTOM` | `abs(0.01 - 0.02) = 0.01 > 1e-12` → No match |
| 2 | 0.02 | MED | `SMEARING_GAUSSIAN` | `abs(0.02 - 0.02) = 0.0 <= 1e-12` → Match ✅ |
| 3 | 0.03 | HIGH | `CUSTOM` | `abs(0.03 - 0.02) = 0.01 > 1e-12` → No match |

**What Each Stage Sees**:

| Stage | Degauss = 0.01 | Degauss = 0.02 | Degauss = 0.03 |
|-------|----------------|----------------|----------------|
| **YAML Input** | `degauss: 0.01` | `degauss: 0.02` | `degauss: 0.03` |
| **match_profile()** | No match (profile requires 0.02) | Match ✅ | No match (profile requires 0.02) |
| **detect_dimension_for_step()** | Returns `CUSTOM` | Returns `SMEARING_GAUSSIAN` | Returns `CUSTOM` |
| **detect_dimension_from_steps()** | Returns `CUSTOM` | Returns `SMEARING_GAUSSIAN` | Returns `CUSTOM` |
| **UI Display** | "Custom" | "smearing_gaussian" | "Custom" |

---

## Root Cause Hypotheses (Ranked)

### Hypothesis 1: Hardcoded Profile Value (MOST LIKELY) ⭐

**Description**: The occupations_scheme ParamSpace has only one smearing profile that hardcodes `degauss = 0.02`. When precision writes `degauss = 0.01` or `0.03`, there is no matching profile.

**Evidence**:
- Profile definition: `key_degauss: Cell.VALUE(0.02)` (paramspace.py:540)
- No profiles for `SMEARING_GAUSSIAN_0.01` or `SMEARING_GAUSSIAN_0.03`
- Tolerance `1e-12` is too strict to allow 0.01 or 0.03 to match 0.02

**Confidence**: **HIGH** - This is the direct cause.

---

### Hypothesis 2: Design Intent vs Implementation Mismatch

**Description**: The design may have intended occupation detection to be independent of degauss value (only check that smearing is active), but the implementation requires exact degauss matching.

**Evidence**:
- Documentation suggests occupation detection should work for any degauss value when smearing is active
- Implementation requires exact match to 0.02

**Confidence**: **MEDIUM** - Requires design documentation review to confirm.

---

### Hypothesis 3: Missing Profiles for LOW/HIGH Degauss Values

**Description**: The system should have separate profiles for `SMEARING_GAUSSIAN_0.01` and `SMEARING_GAUSSIAN_0.03`, but they were never added.

**Evidence**:
- Only `SMEARING_GAUSSIAN_0.02` exists
- Precision can write 0.01, 0.02, 0.03, but occupation only matches 0.02

**Confidence**: **HIGH** - This is a consequence of Hypothesis 1.

---

## Non-Findings (What is NOT Happening)

### ❌ NOT: Occupation Detection Reads Precision State

- Occupation detection does not call precision detection
- No shared state between occupation and precision detection
- No inference from precision to occupation

### ❌ NOT: Compile/Aggregation Transforms Results

- `detect_dimension_from_steps()` faithfully propagates detect results
- No transformation of `SMEARING_GAUSSIAN` to `CUSTOM` in aggregation
- No special handling for MED precision

### ❌ NOT: UI Rendering Artifact

- UI displays exactly what `detect_presets_from_calculation()` returns
- No filtering or transformation in UI layer
- Issue originates in backend detection logic

### ❌ NOT: Tolerance Calculation Error

- Tolerance `1e-12` is correctly applied
- `abs(0.01 - 0.02) = 0.01` correctly fails tolerance check
- No floating-point precision issues

### ❌ NOT: MED Treated as Default

- No special case for MED precision in occupation detection
- MED works only because its degauss value (0.02) matches the hardcoded profile
- No fallback logic that triggers only for MED

---

## Conclusion

**Root Cause**: The occupations_scheme ParamSpace defines only one smearing profile (`SMEARING_GAUSSIAN_0.02`) that requires `degauss = 0.02` exactly. When precision compilation writes `degauss = 0.01` (LOW) or `0.03` (HIGH), occupation detection fails to match because there is no profile for those values.

**Coupling Type**: Indirect coupling via shared YAML state. Precision compilation writes degauss values; occupation detection reads them. There is no direct dependency on precision detection results.

**Stage of Issue**: The issue occurs in the **detect stage** (`match_profile()`), not in compile/aggregation.

**Is This a Bug?**: This appears to be a **design limitation** rather than a bug. The system was designed with a single smearing profile for `degauss = 0.02`, but precision can write other values. The behavior is consistent with the implementation, but may not match user expectations.

**Is This Intentional?**: The hardcoded profile is intentional (per ParamSpace design), but the coupling with precision values may be unintentional. The system should either:
1. Add profiles for `SMEARING_GAUSSIAN_0.01` and `SMEARING_GAUSSIAN_0.03`, OR
2. Make occupation detection independent of degauss value (only check that smearing is active), OR
3. Coordinate precision and occupation presets to use consistent degauss values

---

## Recommendations for Further Investigation

1. **Review Design Documentation**: Check if occupation detection was intended to be independent of degauss value, or if multiple profiles were planned.

2. **Check Historical Context**: Review git history to see if profiles for 0.01/0.03 were ever considered or removed.

3. **Verify User Expectations**: Confirm whether users expect occupation to be detected as smearing regardless of degauss value, or if they expect CUSTOM when degauss != 0.02.

4. **Consider ParamSpace Constitution**: Review if the current design violates any principles in the ParamSpace Constitution regarding dimension independence.

---

**Report Generated**: Independent code review (read-only investigation)  
**Scope**: Detect and compile pipelines only (no apply logic, no tests, no UI rendering code)  
**Method**: Static code analysis, call graph tracing, data flow analysis

