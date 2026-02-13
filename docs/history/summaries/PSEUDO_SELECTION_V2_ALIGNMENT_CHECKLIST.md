# Pseudo Selection V2 Alignment Checklist

**Date**: 2025-01-XX  
**Purpose**: Ensure full alignment between implementation and CONSTITUTION_ZH.md Chapter 7

## Constitution Rules → Implementation Mapping

### Rule 7.4: sha256 vs sha_token semantics
**Constitution**: UI dropdown selection key is sha256 (not sha_token). sha_token only for conflict handling, warnings, cross-calc updates.

**Implementation Status**: ✅ OK
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Uses `selectedSha256ByElement` state
- `src/quantumvitas/core/pseudo_options.py`: Returns `PseudoVariant[]` keyed by sha256
- `gui/src/types/qv.ts`: `PseudoVariant` interface has `sha256` as primary field

**Action**: None

---

### Rule 7.5.1: UI display/selectable options
**Constitution**: Options must correspond to filesystem-real UPF files (project/internal/installed-lib only). No disabled entries for not-installed libs.

**Implementation Status**: ✅ OK
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Filters to `realVariants` (filesystem-real only)
- `src/quantumvitas/core/pseudo_options.py`: Only includes installed lib sources

**Action**: None

---

### Rule 7.5.1.1: Deterministic tie-break rules
**Constitution**: When sha256 matches multiple candidates:
1. If calc.yml has pseudo_filename, prefer filename match
2. Then source priority: project → internal → lib
3. If multiple libs, sort by library/asset name lexicographically
4. If same lib, sort by relative_path/basename lexicographically

**Implementation Status**: ✅ OK
- `gui/src/components/common_cards/CommonCardPseudo.tsx::restoreSelectionFromCalc()`: 
  - ✅ Implements filename match first
  - ✅ Implements source priority (project > internal > lib)
  - ✅ Implements library/asset name lexicographic sort for multiple libs
  - ✅ Implements basename sort as final tie-break

**Action**: None

---

### Rule 7.5.2: Restore selection (no YAML write)
**Constitution**: Restore by sha256 first (with tie-break), then fallback by filename. Must NOT write calc.yml.

**Implementation Status**: ✅ OK
- `gui/src/components/common_cards/CommonCardPseudo.tsx::restoreSelectionFromCalc()`: 
  - ✅ Only calls `setLocalMapping*` (no `onUpdate`)
  - ✅ Uses `hasRestoredRef` to prevent multiple restores

**Action**: None (but tie-break needs completion)

---

### Rule 7.5.3: User selection change (write triplet)
**Constitution**: Only on explicit user change, write triplet (filename+sha256+sha_token) together. Emit debug log.

**Implementation Status**: ✅ OK
- `gui/src/components/common_cards/CommonCardPseudo.tsx::handlePseudoChange()`:
  - ✅ Calls `onUpdate()` with triplet
  - ✅ Emits debug log: `[CommonCardPseudo] User selection changed: ...`

**Action**: None

---

### Rule 7.5.4: Token-match edge case
**Constitution**: If project basename and external have same sha_token but different sha256 → separate entries (no merge). Show token-match hints.

**Implementation Status**: ✅ OK
- `src/quantumvitas/core/pseudo_options.py`: Creates separate variants, adds `token_match_warnings`
- `gui/src/components/common_cards/CommonCardPseudo.tsx`: Displays token-match warnings inline

**Action**: None

---

### Rule 7.7.1: Step0 project source = noop
**Constitution**: If user selects project/pseudo file, Step0 must noop (no overwrite/rename), but refresh calc sha256/sha_token.

**Implementation Status**: ✅ OK
- `src/quantumvitas/core/pseudo_runtime.py::prepare_project_pseudos_for_run()`:
  - ✅ Checks `source_kind == "project"` and does noop
  - ✅ Still refreshes calc records

**Action**: None

---

### Rule 7.7.2: Step0 external selection collision rules
**Constitution**: 
- same sha256 → noop
- same sha_token, different sha256 → overwrite
- different sha_token → rename_existing + update calcs by sha_token

**Implementation Status**: ✅ OK
- `src/quantumvitas/core/pseudo_runtime.py::prepare_project_pseudos_for_run()`:
  - ✅ Implements all three collision rules correctly

**Action**: None

---

### Rule 7.7.3: Stale sha256 allowed
**Constitution**: Calc can have stale sha256 (sha_token unchanged). Only sha_token change indicates physical change.

**Implementation Status**: ✅ OK
- `src/quantumvitas/core/pseudo_runtime.py`: Handles stale sha256 correctly
- `src/quantumvitas/calculation/runner.py`: Refreshes after Step0

**Action**: None

---

## Summary

**Total Rules**: 9  
**OK**: 9  
**Needs Update**: 0  
**Missing**: 0

**Status**: ✅ All constitution rules are implemented and aligned.

## Files Changed for Alignment

1. **CONSTITUTION_ZH.md** (Chapter 7):
   - Added 7.5.1.1: Deterministic tie-break rules
   - Updated 7.5.2: Clarified tie-break usage in restore selection

2. **gui/src/components/common_cards/CommonCardPseudo.tsx**:
   - Updated `restoreSelectionFromCalc()`: Full tie-break implementation (filename → source → library/asset name → basename)
   - Updated fallback filename matching: Same tie-break for lib matches

3. **tests/unit/test_pseudo_options_shatoken_grouping.py**:
   - Added `test_tie_break_multiple_libs()`: Verifies tie-break structure support

4. **docs/PSEUDO_SELECTION_V2_IMPLEMENTATION_SUMMARY.md**:
   - Updated "Default Selection Priority" section to include tie-break rules

5. **docs/PSEUDO_SELECTION_V2_ALIGNMENT_CHECKLIST.md** (this file):
   - Created alignment checklist mapping constitution rules to implementation

