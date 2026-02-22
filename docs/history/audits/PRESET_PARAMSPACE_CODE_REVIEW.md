# Preset ParamSpace Code Review

**Date**: 2025-01-XX  
**Purpose**: Establish current reality of presets system before migrating to ParamSpace framework  
**Constitution Reference**: Chapter 10.7 (Preset Space 统一框架)

---

## Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    UI Layer (TypeScript)                        │
├─────────────────────────────────────────────────────────────────┤
│  gui/src/components/presets/PresetSection.tsx                  │
│  gui/src/hooks/usePresets.ts                                    │
│  gui/src/types/qms.ts (type definitions)                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │ RPC (JSON-RPC)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Daemon Layer (Python)                         │
├─────────────────────────────────────────────────────────────────┤
│  src/qmatsuite/daemon/server.py                             │
│    - _handle_detect_presets()                                  │
│    - _handle_apply_presets_to_calculation()                    │
│    - _handle_apply_presets_to_step()                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Integration Layer (Python)                        │
├─────────────────────────────────────────────────────────────────┤
│  src/qmatsuite/presets/integration.py                       │
│    - detect_presets_from_calculation()                         │
│    - apply_presets_to_step()                                   │
│    - get_step_preset_footprints()                              │
│    - DIMENSION_OWNED_KEYS (dimension isolation)                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Compiler    │ │  Detector    │ │  Receivers   │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ compiler.py  │ │ detector.py  │ │ receivers.py │
│              │ │              │ │              │
│ - compile_*() │ │ - detect_*() │ │ - Registry   │
│ - Per dim    │ │ - Per dim    │ │ - Filter     │
└──────────────┘ └──────────────┘ └──────────────┘
        │              │
        └──────┬───────┘
               ▼
┌─────────────────────────────────────────────────────────────────┐
│              Dimension Definitions                              │
├─────────────────────────────────────────────────────────────────┤
│  src/qmatsuite/presets/dimensions.py                        │
│    - SpinOption, SOCOption, OccupationsSchemeOption,           │
│      PrecisionOption, CUSTOM                                    │
│    - DIMENSION_* constants                                      │
│    - V0_DIMENSIONS, V1_DIMENSIONS                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Specialized Modules                               │
├─────────────────────────────────────────────────────────────────┤
│  src/qmatsuite/presets/precision.py                        │
│    - PrecisionAdvisor (structure-dependent)                    │
│    - PRECISION_CONSTANTS (centralized config)                  │
│  src/qmatsuite/presets/precision_context.py                │
│    - resolve_precision_context() (unified resolver)            │
└─────────────────────────────────────────────────────────────────┘
```

**Data Flow**:
1. **UI** → calls RPC `detect_presets` / `apply_presets_to_calculation`
2. **Daemon** → calls `detect_presets_from_calculation()` / `apply_presets_to_step()`
3. **Integration** → orchestrates compiler/detector/receiver logic
4. **Compiler** → writes canonical YAML (step.yml)
5. **Detector** → reads YAML and infers preset state
6. **Receivers** → filter which dimensions each step_type accepts

---

## Where Presets Live

### Backend (Python)

**Core Modules**:
- `src/qmatsuite/presets/dimensions.py` - Enum definitions (SpinOption, SOCOption, OccupationsSchemeOption, PrecisionOption, CUSTOM)
- `src/qmatsuite/presets/compiler.py` - Forward compilation (compile_spin, compile_soc, compile_occupations_scheme, compile_precision)
- `src/qmatsuite/presets/detector.py` - Reverse detection (detect_spin, detect_soc, detect_occupations_scheme, detect_precision, detect_all_presets)
- `src/qmatsuite/presets/integration.py` - Integration glue (apply_presets_to_step, detect_presets_from_calculation, get_step_preset_footprints)
- `src/qmatsuite/presets/receivers.py` - Receiver registry (PresetReceiverRegistry, filter_presets_for_step, get_precision_receiver_spec)
- `src/qmatsuite/presets/__init__.py` - Public API exports

**Specialized Modules**:
- `src/qmatsuite/presets/precision.py` - PrecisionAdvisor, PRECISION_CONSTANTS, cutoff/kmesh computation
- `src/qmatsuite/presets/precision_context.py` - Unified resolver for structure/pseudo mapping

**Daemon Handlers**:
- `src/qmatsuite/daemon/server.py`:
  - `_handle_detect_presets()` (line 3376)
  - `_handle_apply_presets_to_calculation()` (line 3522)
  - `_handle_apply_presets_to_step()` (line 3448)

### Frontend (TypeScript)

**UI Components**:
- `gui/src/components/presets/PresetSection.tsx` - Preset UI (dropdowns, Custom badges)
- `gui/src/components/presets/index.ts` - Component exports

**Hooks**:
- `gui/src/hooks/usePresets.ts` - React hook for preset detection/application

**Types**:
- `gui/src/types/qms.ts` - TypeScript type definitions (PresetValue, PresetDetectionResult, ApplyPresetsToCalcResult, etc.)

### Tests

**Unit Tests**:
- `tests/unit/test_detector_b.py` - Detector logic tests (single-step, multi-step, roundtrip)
- `tests/unit/test_preset_integration.py` - Integration tests (apply/detect from calculation)

**Integration Tests**:
- `tests/integration/test_preset_broadcast.py` - BROADCAST apply tests
- `tests/integration/test_precision_roundtrip.py` - Precision roundtrip tests
- `tests/integration/test_precision_integration.py` - Precision integration tests
- `tests/integration/test_precision_detection_custom.py` - Precision custom detection tests

---

## Single Source of Truth Check

### Dimension: `spin`

**Canonical YAML Representation (Compiler writes)**:
- `SYSTEM.nspin = 1` (NONSPIN)
- `SYSTEM.nspin = 2` (COLLINEAR)
- `SYSTEM.noncolin = ".true."` (NONCOLLINEAR, no nspin written)

**Detector reads**:
- `SYSTEM.nspin` (case-insensitive via `_get_system_param`)
- `SYSTEM.noncolin` (case-insensitive, parsed as bool via `_parse_bool`)

**Canonicalization rules**:
- ✅ Compiler: Explicit values (1, 2, ".true.")
- ✅ Detector: Case-insensitive section/key lookup, Fortran bool parsing (".true."/".false."/True/False)
- ✅ **Consistent**: Both use same keys (`nspin`, `noncolin`)

**Silent fallbacks / "try both formats"**:
- ❌ **None found** - Clean implementation

**Tech Debt**:
- None identified

---

### Dimension: `soc`

**Canonical YAML Representation (Compiler writes)**:
- `SYSTEM.lspinorb = ".false."` (NO_SOC)
- `SYSTEM.lspinorb = ".true."` (WITH_SOC)

**Detector reads**:
- `SYSTEM.lspinorb` (case-insensitive, parsed as bool)

**Canonicalization rules**:
- ✅ Compiler: Explicit ".false." / ".true." strings
- ✅ Detector: Fortran bool parsing (handles ".true."/".false."/True/False)
- ✅ **Consistent**: Both use same key (`lspinorb`)

**Silent fallbacks / "try both formats"**:
- ❌ **None found** - Clean implementation

**Tech Debt**:
- None identified

---

### Dimension: `occupations_scheme`

**Canonical YAML Representation (Compiler writes)**:
- `SYSTEM.occupations = "fixed"` (FIXED, smearing/degauss removed)
- `SYSTEM.occupations = "smearing"`, `SYSTEM.smearing = "gaussian"`, `SYSTEM.degauss = 0.02` (SMEARING_GAUSSIAN)
- `SYSTEM.occupations = "tetrahedra"` (TETRAHEDRA, smearing/degauss removed)

**Detector reads**:
- `SYSTEM.occupations` (case-insensitive, normalized to lowercase)
- `SYSTEM.smearing` (case-insensitive, normalized, accepts "gaussian" or "gauss" as synonyms)
- `SYSTEM.degauss` (parsed as float, compared with abs_tol=1e-12)

**Canonicalization rules**:
- ✅ Compiler: Always writes "gaussian" (canonical spelling)
- ⚠️ Detector: Accepts "gaussian" OR "gauss" as synonyms (line 222 in detector.py: `if smearing_str not in ("gaussian", "gauss")`)
- ⚠️ **Inconsistency**: Compiler writes "gaussian", detector accepts both - but this is intentional (alias support)
- ✅ Degauss tolerance: 1e-12 (hardcoded in detector, line 234)

**Silent fallbacks / "try both formats"**:
- ⚠️ **Alias handling**: Detector accepts "gauss" as synonym for "gaussian" (line 222)
  - **Status**: Intentional alias support, but not declared in ParamSpace
  - **Tech Debt**: Aliases should be in ParamSpace declaration, not hardcoded in detector

**Tech Debt**:
1. **Alias handling scattered**: `gaussian`/`gauss` synonym is hardcoded in `detect_occupations_scheme()` (line 222), not declared in a ParamSpace
2. **Tolerance hardcoded**: `DEGAUSS_TOL = 1e-12` is hardcoded in detector (line 234), should be in ParamSpace

---

### Dimension: `precision`

**Canonical YAML Representation (Compiler writes)**:
- `SYSTEM.ecutwfc = <integer>` (rounded via `round_cutoff_integer()`)
- `SYSTEM.ecutrho = <integer>` (rounded via `round_cutoff_integer()`)
- `ELECTRONS.conv_thr = <float>` (canonical: 1e-6/1e-8/1e-10)
- `cards.K_POINTS = {"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}`

**Detector reads**:
- `SYSTEM.ecutwfc` (parsed as int, exact match required)
- `SYSTEM.ecutrho` (parsed as int, exact match required)
- `ELECTRONS.conv_thr` (parsed as float, compared with abs_tol=1e-11)
- `cards.K_POINTS` (via `_get_kpoints_mesh()`, expects `{"option": "automatic", "data": [[...]]}`)

**Canonicalization rules**:
- ✅ Compiler: Integer-rounded cutoffs, canonical conv_thr values, K_POINTS in cards format
- ✅ Detector: Integer comparison for cutoffs, float tolerance for conv_thr, K_POINTS from cards only
- ✅ **Consistent**: Both use same keys and format

**Silent fallbacks / "try both formats"**:
- ✅ **K_POINTS format**: Detector reads ONLY from `cards.K_POINTS` (line 284-285 in detector.py)
  - Comment on line 278: "QE kpoints are represented as cards.K_POINTS only"
  - ✅ **No fallback**: Clean implementation, no parameters.K_POINTS support

**Tech Debt**:
- ⚠️ **Tolerance hardcoded**: `CONV_THR_ABS_TOL = 1e-11` is in precision.py (line 64), but should be in ParamSpace
- ⚠️ **Legacy aliases**: `PrecisionConfig` and `PRECISION_CONFIGS` exist for "backward compatibility" (lines 75-92 in precision.py)
  - **Status**: Marked as legacy, but still present
  - **Tech Debt**: Should be removed per Constitution 10.7.6 (zero tech debt)

---

## Explicit vs Implicit Defaults

### Spin Dimension

**Keys considered defaults when missing**:
- `nspin`: Default = 1 (NONSPIN)
- `noncolin`: Default = False (not NONCOLLINEAR)

**Where defaults are defined**:
- **Detector** (detector.py line 133): `nspin_val = _parse_int(nspin, default=1)`
- **Detector** (detector.py line 128): `if noncolin is not None and _parse_bool(noncolin)` (implicit False if None)
- **Compiler**: Always writes explicit values (no defaults used)

**Does detector distinguish present vs effective_value?**:
- ❌ **NO**: Detector checks `if nspin is None` but doesn't explicitly track `present` vs `effective_value`
- **Current logic**: `nspin_val = _parse_int(nspin, default=1)` - if missing, uses default directly
- **Problem**: Cannot distinguish "nspin=1 explicitly written" vs "nspin missing → default=1"
- **Impact**: Cannot implement NOT_APPLICABLE semantics (must check `present==False`)

---

### SOC Dimension

**Keys considered defaults when missing**:
- `lspinorb`: Default = False (NO_SOC)

**Where defaults are defined**:
- **Detector** (detector.py line 166-172): `if lspinorb is not None and _parse_bool(lspinorb)` → implicit False if None
- **Compiler**: Always writes explicit values (".false." or ".true.")

**Does detector distinguish present vs effective_value?**:
- ❌ **NO**: Same issue as spin - checks `if lspinorb is not None` but doesn't track `present` separately
- **Problem**: Cannot distinguish "lspinorb=.false. explicitly written" vs "lspinorb missing → default=False"

---

### Occupations Scheme Dimension

**Keys considered defaults when missing**:
- `occupations`: Default = "fixed" (FIXED)
- `smearing`: No default (if occupations="smearing" but smearing missing → CUSTOM)
- `degauss`: No default (if occupations="smearing" but degauss missing → CUSTOM)

**Where defaults are defined**:
- **Detector** (detector.py line 202): `if occupations is None or occupations == ""` → return FIXED
- **Compiler**: Always writes explicit "fixed" (line 136)

**Does detector distinguish present vs effective_value?**:
- ❌ **NO**: Checks `if occupations is None` but doesn't track `present` separately
- **Problem**: Cannot distinguish "occupations='fixed' explicitly written" vs "occupations missing → default='fixed'"
- **Impact**: For FIXED profile, if user manually writes `occupations='fixed'`, detector can't tell if it was explicit or implicit

**Special case - smearing/degauss**:
- If `occupations='smearing'` but `smearing` or `degauss` missing → returns CUSTOM (lines 218-227)
- ✅ **Correct behavior**: Missing required keys for smearing → CUSTOM

---

### Precision Dimension

**Keys considered defaults when missing**:
- `ecutwfc`: No default (if missing → strict detection fails, returns None/CUSTOM)
- `ecutrho`: No default (if missing → strict detection fails, returns None/CUSTOM)
- `conv_thr`: Default = 1e-6 in simple detection (line 369), but strict detection requires it
- `K_POINTS`: No default (if missing or not automatic → strict detection fails)

**Where defaults are defined**:
- **Simple detection** (detector.py line 364-367): `if conv_thr is None: return PrecisionOption.MED` (generous default)
- **Strict detection** (detector.py line 417-420): If any essential param missing → returns None (no match)
- **Compiler**: Always writes explicit values (no defaults)

**Does detector distinguish present vs effective_value?**:
- ❌ **NO**: Checks `if actual_conv_thr is None` but doesn't track `present` separately
- **Problem**: Cannot distinguish "conv_thr=1e-8 explicitly written" vs "conv_thr missing → use default"
- **Impact**: Simple detection uses default (MED), strict detection requires explicit values

**Special case - fallback detection**:
- `detect_precision()` (simple heuristic, line 344) uses conv_thr ranges only
- `detect_precision_strict()` (line 380) requires all 3 aspects (conv_thr + kmesh + cutoffs)
- ⚠️ **Two detection paths**: Simple (heuristic) vs Strict (canonical) - should be unified

---

## Cross-Dimension Contamination Risks

### Current Protection Mechanism

**Dimension Ownership Mapping** (integration.py lines 229-245):
```python
DIMENSION_OWNED_KEYS: dict[str, dict[str, set[str]]] = {
    DIMENSION_SPIN: {"SYSTEM": {"nspin", "noncolin"}},
    DIMENSION_SOC: {"SYSTEM": {"lspinorb"}},
    DIMENSION_OCCUPATIONS_SCHEME: {"SYSTEM": {"occupations", "smearing", "degauss"}},
    DIMENSION_PRECISION: {"SYSTEM": {"ecutwfc", "ecutrho"}, "ELECTRONS": {"conv_thr"}, "cards": {"K_POINTS"}},
}
```

**Apply Logic** (integration.py lines 392-406):
1. Compile each dimension separately (lines 324-354)
2. Collect owned keys only into `compiled_patches`
3. Remove only keys owned by applied dimensions (lines 392-398)
4. Add only compiled patches (lines 407-412)

**Status**: ✅ **Protected** - Dimension isolation implemented (from recent hardening work)

---

### Potential Risks (Historical / Edge Cases)

**Risk 1: Precision K_POINTS vs Occupations Scheme**
- **Location**: `integration.py` line 388-390
- **Issue**: Precision writes `cards.K_POINTS`, but this doesn't conflict with occupations_scheme (different sections)
- **Status**: ✅ **Safe** - Different YAML sections

**Risk 2: Compiler merge in compile_presets()**
- **Location**: `compiler.py` lines 297-310
- **Issue**: `compile_presets()` compiles ALL dimensions together and merges into single dict
- **Status**: ⚠️ **Not used in apply path** - `apply_presets_to_step()` compiles dimensions separately (line 330-354)
- **Risk**: If `compile_presets()` is called directly, it could merge dimensions
- **Mitigation**: Apply path doesn't use `compile_presets()`, uses individual `compile_*()` functions

**Risk 3: Receiver boundaries**
- **Location**: `receivers.py` - Receiver registry defines which dimensions each step_type accepts
- **Status**: ✅ **Clear boundaries** - Receivers filter dimensions before compilation
- **Example**: `bands_pw` accepts spin/soc/precision but NOT occupations_scheme (line 208-213)

---

## Tests

### Test Coverage Summary

**Unit Tests** (`tests/unit/test_detector_b.py`):
- ✅ Spin detection (explicit, implicit defaults, edge cases)
- ✅ SOC detection (explicit, implicit defaults)
- ✅ Occupations scheme detection (fixed, smearing_gaussian with aliases, tetrahedra, custom cases)
- ✅ Multi-step aggregation (homogeneous → single value, heterogeneous → CUSTOM)
- ✅ Roundtrip tests (compile → detect equivalence)
- ✅ Real QE input parsing tests

**Integration Tests** (`tests/unit/test_preset_integration.py`):
- ✅ `detect_presets_from_calculation()` - aggregate from calculation
- ✅ `apply_presets_to_step()` - apply to single step
- ✅ Roundtrip: apply → detect (line 340-363)

**Broadcast Tests** (`tests/integration/test_preset_broadcast.py`):
- ✅ BROADCAST apply to all steps
- ✅ Receiver vs non-receiver step filtering
- ✅ Dimension isolation (apply one dimension doesn't affect others)

**Precision Tests**:
- ✅ `test_precision_roundtrip.py` - Precision roundtrip (apply MED → detect MED)
- ✅ `test_precision_integration.py` - Precision integration with structure/pseudo
- ✅ `test_precision_detection_custom.py` - Custom detection scenarios

---

### Roundtrip Contract Tests

**Spin Dimension**:
- ✅ **Present**: `test_roundtrip_detection()` in `test_preset_integration.py` (line 340)
  - Tests: apply noncollinear + with_soc + smearing_gaussian → detect same values
- ✅ **Coverage**: Covers all three spin options

**SOC Dimension**:
- ✅ **Present**: Included in `test_roundtrip_detection()` (line 340)
- ✅ **Coverage**: Tests with_soc and no_soc

**Occupations Scheme Dimension**:
- ✅ **Present**: Included in `test_roundtrip_detection()` (line 340)
- ✅ **Coverage**: Tests smearing_gaussian
- ⚠️ **Missing**: No explicit test for FIXED → detect FIXED (relies on implicit default)
- ⚠️ **Missing**: No explicit test for TETRAHEDRA → detect TETRAHEDRA

**Precision Dimension**:
- ✅ **Present**: `test_precision_roundtrip.py` - Multiple roundtrip tests
- ✅ **Coverage**: Tests LOW/MED/HIGH roundtrips
- ✅ **Coverage**: Tests step-type-aware detection (SCF vs NSCF mesh factor)

---

### Alias Tests

**Occupations Scheme - gaussian/gauss**:
- ✅ **Present**: `test_smearing_gauss_synonym()` in `test_detector_b.py` (line 129)
  - Tests: `smearing='gauss'` → detects as SMEARING_GAUSSIAN
- ✅ **Coverage**: Both "gaussian" and "gauss" are tested

**Other Aliases**:
- ❌ **Missing**: No tests for Fortran bool aliases (".true." vs True vs "true")
  - **Status**: Detector handles these (via `_parse_bool()`), but no explicit tests

---

### Tests That May Pass Due to Implicit Fallbacks

**Test: `test_implicit_default_nonspin()`** (test_detector_b.py line 68):
- **What it tests**: Missing `nspin` → detects as NONSPIN
- **Status**: ✅ **Correct behavior** (implicit default)
- **Risk**: If we implement NOT_APPLICABLE, this test may need updating

**Test: `test_fixed_missing_occupations()`** (test_detector_b.py line 149):
- **What it tests**: Missing `occupations` → detects as FIXED
- **Status**: ✅ **Correct behavior** (implicit default)
- **Risk**: If we implement NOT_APPLICABLE, this test may need updating

**Test: `test_custom_on_missing_calculation_data()`** (test_precision_detection_custom.py):
- **What it tests**: Missing calculation.yaml → returns CUSTOM for precision
- **Status**: ✅ **Correct behavior** (cannot do strict detection without context)
- **Risk**: None - this is expected behavior

---

## Known Inconsistencies / Tech Debt

### High Priority

1. **No present vs effective_value distinction**
   - **Location**: All detector functions (`detect_spin`, `detect_soc`, `detect_occupations_scheme`, `detect_precision`)
   - **Problem**: Cannot distinguish "key explicitly written" vs "key missing → use default"
   - **Impact**: Cannot implement NOT_APPLICABLE semantics (Constitution 10.7.3)
   - **Fix Required**: Refactor all detectors to track `present` separately from `effective_value`

2. **Aliases hardcoded in detector, not in ParamSpace**
   - **Location**: `detector.py` line 222 (`gaussian`/`gauss` synonym)
   - **Problem**: Aliases are scattered in detector logic, not declared in ParamSpace
   - **Impact**: Violates Constitution 10.7.2 (aliases must be in ParamSpace)
   - **Fix Required**: Move alias definitions to ParamSpace declaration

3. **Tolerances hardcoded, not in ParamSpace**
   - **Location**: 
     - `detector.py` line 234: `DEGAUSS_TOL = 1e-12`
     - `precision.py` line 64: `CONV_THR_ABS_TOL = 1e-11`
   - **Problem**: Tolerances are hardcoded constants, not in ParamSpace
   - **Impact**: Violates Constitution 10.7.2 (numeric tolerances must be in ParamSpace)
   - **Fix Required**: Move tolerances to ParamSpace declaration

4. **Legacy backward compatibility code**
   - **Location**: `precision.py` lines 75-92 (`PrecisionConfig`, `PRECISION_CONFIGS`)
   - **Problem**: Marked as "Legacy alias for backward compatibility"
   - **Impact**: Violates Constitution 10.7.6 (zero tech debt, no backward compatibility)
   - **Fix Required**: Remove legacy code, update any tests that use it

### Medium Priority

5. **Two precision detection paths (simple vs strict)**
   - **Location**: `detector.py` - `detect_precision()` (simple) vs `detect_precision_strict()` (strict)
   - **Problem**: Two different detection algorithms for same dimension
   - **Impact**: Inconsistency - simple detection uses conv_thr ranges, strict uses 3-way match
   - **Fix Required**: Unify into single ParamSpace-based detection

6. **Default handling scattered**
   - **Location**: Multiple places:
     - `detector.py` line 133: `default=1` for nspin
     - `detector.py` line 202: implicit FIXED for missing occupations
     - `detector.py` line 367: `PrecisionOption.MED` for missing conv_thr (simple detection)
   - **Problem**: Defaults are hardcoded in detector logic, not declared in ParamSpace
   - **Impact**: Violates Constitution 10.7.2 (defaults must be in ParamSpace)
   - **Fix Required**: Move all defaults to ParamSpace declaration

7. **Compiler always writes explicit values (no explicit_defaults switch)**
   - **Location**: All `compile_*()` functions
   - **Problem**: Compiler always writes values, even if they equal defaults
   - **Impact**: Cannot implement Constitution 10.7.5 (explicit_defaults switch)
   - **Fix Required**: Add `explicit_defaults` parameter to compiler functions

### Low Priority

8. **Case-insensitive lookup logic duplicated**
   - **Location**: `detector.py` - `_get_system_param()`, `_get_electrons_param()`
   - **Problem**: Case-insensitive lookup logic is duplicated in multiple helper functions
   - **Impact**: Code duplication, but functionally correct
   - **Fix Required**: Consolidate into single canonicalization function (part of ParamSpace)

9. **Fortran bool parsing logic duplicated**
   - **Location**: `detector.py` - `_parse_bool()` function
   - **Problem**: Fortran bool parsing is separate function, not part of canonicalizer
   - **Impact**: Works correctly, but should be in ParamSpace canonicalizer
   - **Fix Required**: Move to ParamSpace canonicalizer

---

## Prioritized Refactor List

### Phase 1: Foundation (Safe, No Breaking Changes)

**Goal**: Establish ParamSpace infrastructure without changing behavior

1. **Create ParamSpace base class / dataclass**
   - Define `ParamSpace` structure: `keys`, `defaults`, `aliases`, `profiles`, `tolerances`
   - Location: New file `src/qmatsuite/presets/paramspace.py`
   - **Safe**: Additive only, doesn't change existing code

2. **Extract defaults to constants**
   - Move all default values from detector logic to centralized constants
   - Location: `dimensions.py` or new `paramspace.py`
   - **Safe**: Constants only, no behavior change

3. **Extract tolerances to constants**
   - Move `DEGAUSS_TOL`, `CONV_THR_ABS_TOL` to ParamSpace declarations
   - Location: ParamSpace for each dimension
   - **Safe**: Constants only, no behavior change

4. **Extract aliases to declarations**
   - Move `gaussian`/`gauss` synonym to ParamSpace declaration
   - Location: OccupationsScheme ParamSpace
   - **Safe**: Declaration only, detector logic unchanged

### Phase 2: Detector Refactoring (Breaking Changes - Requires Tests)

**Goal**: Implement present vs effective_value distinction

5. **Refactor detector helpers to track present**
   - Modify `_get_system_param()` to return `(present: bool, value: Any)`
   - Update all detector functions to use new signature
   - **Breaking**: Changes detector function signatures
   - **Tests Required**: Update all detector tests

6. **Implement effective_value computation**
   - Add `compute_effective_value(present, yaml_value, default, canonicalizer)` helper
   - Use in all detector functions
   - **Breaking**: Changes detector logic (but should preserve behavior)
   - **Tests Required**: Verify all existing tests still pass

7. **Implement Cell matching logic**
   - Add `match_cell(cell, present, effective_value, tolerance)` function
   - Implement VALUE/NOT_APPLICABLE/WILDCARD matching per Constitution 10.7.3
   - **Breaking**: Changes detection semantics for NOT_APPLICABLE
   - **Tests Required**: Add explicit NOT_APPLICABLE tests

### Phase 3: Compiler Refactoring (Breaking Changes)

**Goal**: Implement explicit_defaults switch and ParamSpace-based compilation

8. **Add explicit_defaults parameter to compiler**
   - Modify all `compile_*()` functions to accept `explicit_defaults: bool = True`
   - Implement logic: if `explicit_defaults=False` and `value == default`, don't write
   - **Breaking**: Changes compiler function signatures
   - **Tests Required**: Add explicit_defaults tests

9. **Refactor compiler to use ParamSpace**
   - Replace hardcoded compilation logic with ParamSpace profile lookup
   - Use Cell semantics (VALUE/NOT_APPLICABLE/WILDCARD) for compilation
   - **Breaking**: Changes compiler implementation (but should preserve output)
   - **Tests Required**: Verify roundtrip tests still pass

### Phase 4: Integration & Cleanup (Breaking Changes)

**Goal**: Remove legacy code and unify detection paths

10. **Remove legacy PrecisionConfig code**
    - Delete `PrecisionConfig` and `PRECISION_CONFIGS` from `precision.py`
    - Update any tests that reference them
    - **Breaking**: Removes public API
    - **Tests Required**: Update precision tests

11. **Unify precision detection paths**
    - Remove `detect_precision()` (simple heuristic)
    - Use only `detect_precision_strict()` with ParamSpace
    - **Breaking**: Changes precision detection behavior (may return CUSTOM more often)
    - **Tests Required**: Update precision detection tests

12. **Remove dimension-specific compiler/detector functions**
    - Replace `compile_spin()`, `detect_spin()`, etc. with generic ParamSpace-based functions
    - Keep functions as thin wrappers for backward compatibility (deprecate)
    - **Breaking**: Changes internal implementation
    - **Tests Required**: All existing tests should still pass (wrappers preserve API)

### Phase 5: Contract Tests (Mandatory Before Merge)

**Goal**: Ensure Constitution 10.7.7 compliance

13. **Add roundtrip contract tests for all profiles**
    - For each dimension, test each profile: `apply(profile) → detect() == profile`
    - Location: New test file `tests/unit/test_paramspace_roundtrip.py`
    - **Required**: Must pass before merge

14. **Add NOT_APPLICABLE contract tests**
    - Test: If key is NOT_APPLICABLE but explicitly written → detect returns CUSTOM
    - Location: `tests/unit/test_paramspace_roundtrip.py`
    - **Required**: Must pass before merge

15. **Add alias contract tests**
    - Test: All declared aliases must detect to same profile
    - Location: `tests/unit/test_paramspace_roundtrip.py`
    - **Required**: Must pass before merge

---

## Safe Order Summary

**Recommended implementation order** (minimizes risk):

1. **Phase 1** (Foundation) - Additive only, no behavior changes
2. **Phase 5** (Contract Tests) - Write tests first, then implement to pass them
3. **Phase 2** (Detector) - Core logic changes, but tests guide implementation
4. **Phase 3** (Compiler) - Depends on Phase 2, but tests ensure correctness
5. **Phase 4** (Cleanup) - Remove legacy code after everything works

**Critical Path**:
- Cannot implement ParamSpace without Phase 1 (foundation)
- Cannot verify correctness without Phase 5 (contract tests)
- Cannot implement Cell semantics without Phase 2 (present vs effective_value)
- Cannot implement explicit_defaults without Phase 3 (compiler refactoring)

---

## Appendix: Key Code Locations

### Dimension Ownership
- **Definition**: `integration.py` lines 229-245 (`DIMENSION_OWNED_KEYS`)
- **Usage**: `integration.py` lines 392-406 (remove/add keys during apply)

### Default Values
- **Spin**: `detector.py` line 133 (`default=1` for nspin)
- **SOC**: `detector.py` line 171 (implicit False)
- **Occupations**: `detector.py` line 202 (implicit "fixed")
- **Precision**: `detector.py` line 367 (MED for simple detection)

### Tolerances
- **Degauss**: `detector.py` line 234 (`DEGAUSS_TOL = 1e-12`)
- **Conv_thr**: `precision.py` line 64 (`CONV_THR_ABS_TOL = 1e-11`)

### Aliases
- **gaussian/gauss**: `detector.py` line 222 (`if smearing_str not in ("gaussian", "gauss")`)

### Legacy Code
- **PrecisionConfig**: `precision.py` lines 75-92

### K_POINTS Format
- **Compiler writes**: `compiler.py` line 219 (`cards.K_POINTS` format)
- **Detector reads**: `detector.py` line 284 (`cards.K_POINTS` only, no parameters.K_POINTS)

---

**End of Report**

