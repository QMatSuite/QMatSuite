# Pseudo Migration Audit: sha_token → sha_family Backward Compatibility

**Audit Date**: Code-only review (no assumptions)  
**Scope**: Backward compatibility/migration from `pseudo_sha_token` to `pseudo_sha_family`  
**Method**: Extract exact behavior from code as it exists today

---

## 1. Persisted Schema

### 1.1 Where calc pseudo metadata is stored

**File**: `src/qmatsuite/core/models.py` (lines 147-152)

**Location**: `CalculationModel.species_map` field

**Schema definition** (line 147):
```python
# Calculation-level pseudopotential mapping: element -> {pseudopot, mass, pseudo_sha256, pseudo_sha_family, pseudo_basename}
```

**Storage format**: YAML file at `calculations/<calc_id>/calculation.yaml` under `species_map` key

### 1.2 Fields: Optional vs Expected

**File**: `src/qmatsuite/core/models.py` (lines 147-152, 186-188, 253-254)

**All fields are optional** in the schema (no validation enforces presence)

**Fields defined**:
- `pseudopot`: Optional string (legacy filename, backward compatibility)
- `pseudo_basename`: Optional string (filename in project/pseudo)
- `pseudo_sha256`: Optional string (strict bytes identity - PRIMARY selection key)
- `pseudo_sha_family`: Optional string (physical equivalence hash - for warnings/collision detection)
- `mass`: Optional float (atomic mass)

**Evidence**: Schema is `Dict[str, Dict[str, Any]]` with no required field validation.

### 1.3 What is written when user changes selection in UI

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 755-797)

**Function**: `handlePseudoChange()`

**Written fields** (lines 783-787):
```typescript
onUpdate(
  { [species]: variant.basename },           // filename mapping
  libraryPreference,
  { [species]: variant.sha256 },             // sha256Map
  { [species]: variant.sha_family }          // shaFamilyMap (note: variable name is shaTokenMap but value is sha_family)
)
```

**Backend handler**: `src/qmatsuite/api.py` (lines 5272-5331)

**Function**: `update_calculation_species_map()`

**What gets written** (line 5319):
- Entire `species_map` dict is replaced: `wf_model.species_map = species_map`
- All fields passed in are written together (no selective update)
- Fields written: `pseudopot`, `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family`, `mass` (if provided)

**Evidence**: Line 5319 shows direct assignment of entire dict, so all provided fields are written together.

### 1.4 What is written after Step0 refresh

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 672-738)

**Function**: `refresh_calc_pseudo_records_after_step0()`

**Written fields** (lines 722-725):
```python
calc_entry["pseudopot"] = basename
calc_entry["pseudo_basename"] = basename
calc_entry["pseudo_sha256"] = actual_sha256
calc_entry["pseudo_sha_family"] = actual_sha_family
```

**Computation** (lines 718-719):
- `actual_sha256 = compute_sha256_file(actual_file)` - computed from file
- `actual_sha_family = compute_sha_family_file(actual_file)` - computed from file

**Condition**: Only writes if `actual_file.exists()` (line 717)

**Missing file handling** (lines 726-733):
- If file doesn't exist: logs warning, keeps stored triplet unchanged (no mutation)
- Does NOT compute or write `sha_family` if file missing

---

## 2. Read Path: Restoring Selection / Loading Calc

### 2.1 Exact restore logic in UI

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 495-633)

**Function**: `restoreSelectionFromCalc()`

**Restore algorithm**:

1. **Primary: Match by sha256** (lines 510-577):
   - Reads: `entry.pseudo_sha256` (line 510)
   - Does NOT read: `entry.pseudo_sha_family` or `entry.pseudo_sha_token`
   - Filters variants: `variants.filter(v => v.sha256 === calcSha256)`
   - If multiple matches: applies tie-break (filename → source priority → lexicographic)

2. **Fallback: Match by filename** (lines 579-633):
   - Reads: `entry.pseudo_basename || entry.pseudopot` (line 511)
   - Does NOT read: `pseudo_sha_family` or `pseudo_sha_token`
   - Tries project → internal → lib (with tie-break)

**Key finding**: Restore logic **NEVER reads `pseudo_sha_family`** or `pseudo_sha_token` for matching. It only uses `pseudo_sha256` and filename.

### 2.2 Confirm: "restore default selection does NOT write yml"

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 495-633)

**Evidence**:
- Line 148: `hasRestoredRef` tracks if restore has run
- Lines 620-622: Only calls `setLocalMapping`, `setLocalMappingSha256`, `setLocalMappingShaFamily`, `setSelectedSha256ByElement`
- Does NOT call `onUpdate()` (which would write calc.yml)
- Comment on line 495: "Restore selection from calc.yml (does NOT write calc.yml)"

**Confirmed**: ✅ Restore does NOT write calc.yml.

### 2.3 Cases where UI overwrites/normalizes fields automatically

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 369-493)

**Function**: `useEffect` hook that syncs local state when mapping changes

**Auto-normalization** (lines 406-413):
- Reads `entry.pseudo_sha_family` if present (line 406)
- If `pseudo_sha_family` missing but `pseudo_sha256` present (lines 409-412):
  - Comment: "Backward compatibility: if calc has sha256 but not sha_family, try to map it"
  - Action: Only sets `initialSha256[species] = entry.pseudo_sha256`
  - Does NOT compute or write `sha_family` automatically
  - Comment says "This will be resolved when options load and we can match sha256 to sha_family"
  - **However**: No code actually performs this resolution

**Finding**: UI does NOT automatically compute or write `pseudo_sha_family` when it's missing. It only preserves `pseudo_sha256` if present.

---

## 3. Run Path: Step0 + Refresh

### 3.1 Exact Step0 behavior if selection is project/internal/lib

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 349-532)

**Function**: `prepare_project_pseudos_for_run()`

**Project source** (lines 394-408):
- If `source_kind == "project"`: **noop** (action: "noop", detail: "Using existing project pseudo")
- Verifies file exists, but does NOT compute or write hashes
- Does NOT call refresh function for project selections

**Internal/lib source** (lines 410-435):
- Resolves source path via `_resolve_internal_source_path()` or `_resolve_lib_source_path()`
- Both functions accept `requested_sha_family` parameter (lines 207, 90)
- If `requested_sha_family` provided: verifies match (lines 225-227, 234-236, 122-123)
- If `requested_sha_family` is None: matches by basename only

**Collision resolution** (lines 456-515):
- Computes `existing_sha_family = compute_sha_family_file(dst)` (line 459)
- Computes `source_sha_family = compute_sha_family_file(source_path)` (line 439)
- Uses `sha_family` for collision detection:
  - Same `sha_family`, different `sha256`: overwrite (line 471)
  - Different `sha_family`: rename existing (line 484)

### 3.2 Where sha256 and sha_family are computed, and when written back

**Computation locations**:

1. **Step0 executor** (`prepare_project_pseudos_for_run`):
   - Line 438: `source_sha256 = compute_sha256_file(source_path)`
   - Line 439: `source_sha_family = compute_sha_family_file(source_path)`
   - Line 459: `existing_sha_family = compute_sha_family_file(dst)`
   - **Does NOT write back to calc.yml** (only mutates filesystem)

2. **Step0 refresh** (`refresh_calc_pseudo_records_after_step0`):
   - Line 718: `actual_sha256 = compute_sha256_file(actual_file)`
   - Line 719: `actual_sha_family = compute_sha_family_file(actual_file)`
   - Lines 722-725: Writes all fields to `calc_entry`
   - Line 737: Saves via `save_calculation()`

**When written back**: Only in `refresh_calc_pseudo_records_after_step0()`, which is called after Step0 completes (line 92-96 in `runner.py`).

### 3.3 What happens if file referenced in calc is missing from project/pseudo at refresh time

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 715-733)

**Behavior**:
- Checks `if actual_file.exists()` (line 717)
- If file missing (lines 726-733):
  - Logs warning: `"Pseudo file '{basename}' for element '{element}' not found in {project_pseudo_dir}. Keeping stored triplet unchanged."`
  - **Keeps existing values in calc_entry (no mutation)**
  - Does NOT compute or write `sha_family`
  - Does NOT clear or modify any fields

**Evidence**: Lines 726-733 show explicit "no mutation" behavior when file missing.

---

## 4. Backward Compat Behavior Today (AS-IS)

### 4.1 If calc.yml has `pseudo_sha_token` but not `pseudo_sha_family`

**Search results**: No code references `pseudo_sha_token` anywhere in the codebase (only in documentation files).

**Finding**: ✅ **Code does NOT read `pseudo_sha_token` at all** - it is completely ignored.

### 4.2 What happens on project open (UI restore)

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 495-633)

**Behavior**:
- Restore function reads: `entry.pseudo_sha256` and `entry.pseudo_basename || entry.pseudopot`
- Does NOT read: `entry.pseudo_sha_token` or `entry.pseudo_sha_family`
- If `pseudo_sha256` present: matches by sha256
- If `pseudo_sha256` missing: falls back to filename match
- **Result**: Selection restored successfully even if `pseudo_sha_family` missing
- **Gap**: `pseudo_sha_family` remains missing in calc.yml (not written)

### 4.3 What happens on user changing selection

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 755-797)

**Behavior**:
- User picks new variant from dropdown
- `handlePseudoChange()` called with `variant.sha_family` (line 767)
- Writes triplet: `{pseudo_basename, pseudo_sha256, pseudo_sha_family}` (lines 783-787)
- **Result**: `pseudo_sha_family` is written to calc.yml (migration happens)

**Evidence**: Line 787 shows `{ [species]: variant.sha_family }` is passed to `onUpdate()`.

### 4.4 What happens on Run (Step0 + refresh)

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 614-669, 672-738)

**Step0 conversion** (`species_map_to_selections`, lines 614-669):
- Reads: `sha_family = entry.get("pseudo_sha_family")` (line 638)
- If `pseudo_sha_family` missing: `sha_family = None`
- Passes `requested_sha_family=sha_family` to `PseudoSelection` (line 664)
- **Result**: Step0 proceeds with `sha_family=None` (no error)

**Step0 execution** (`prepare_project_pseudos_for_run`, lines 349-532):
- If `requested_sha_family` is None: matches by basename only (lines 122-123, 225-227)
- Computes `source_sha_family` from file (line 439)
- Uses `sha_family` for collision detection (lines 471, 484)
- **Result**: Step0 works correctly even if `pseudo_sha_family` missing

**Step0 refresh** (`refresh_calc_pseudo_records_after_step0`, lines 672-738):
- Computes `actual_sha_family = compute_sha_family_file(actual_file)` (line 719)
- Writes `calc_entry["pseudo_sha_family"] = actual_sha_family` (line 725)
- **Result**: `pseudo_sha_family` is written to calc.yml (migration happens)

### 4.5 Does any code still read `pseudo_sha_token`?

**Search results**: 
- `grep -r "pseudo_sha_token"` found 7 matches, all in documentation files:
  - `BEHAVIOR_SPEC_FROM_CODE.md` (outdated audit)
  - `docs/PSEUDO_SELECTION_V2_IMPLEMENTATION_SUMMARY.md` (outdated doc)
  - `docs/PSEUDO_SELECTION_V2_SHA256_KEYED_ALIGNMENT.md` (outdated doc)

**Code search**: No code files read `pseudo_sha_token`.

**Confirmed**: ✅ **No code reads `pseudo_sha_token`** - migration is complete from code perspective, but backward compatibility for old calc.yml files is missing.

---

## 5. Migration Gap Analysis (NO FIXES)

### 5.1 Missing behavior vs desired

**Desired behavior**: "if triplet lacks sha_family, fill it in at next user change or next Step0 refresh without changing selection"

**Current behavior**:
- ✅ **Step0 refresh DOES fill in `sha_family`** (line 725 in `pseudo_runtime.py`)
- ❌ **User change DOES fill in `sha_family`** (line 787 in `CommonCardPseudo.tsx`)
- ❌ **UI restore does NOT fill in `sha_family`** (only reads, doesn't write)
- ❌ **No automatic migration on calc load** (no code computes `sha_family` from file when field missing)

**Gap**: If a calc.yml has `pseudo_sha256` and `pseudo_basename` but missing `pseudo_sha_family`:
- UI restore works (matches by sha256)
- But `pseudo_sha_family` remains missing until:
  - User changes selection (writes new triplet), OR
  - Step0 runs and refresh executes (computes from file)

**Unclear scenario**: What if file doesn't exist in `project/pseudo`? Then Step0 refresh won't compute `sha_family` (lines 726-733 show no mutation when file missing).

### 5.2 Concrete places that would need changes

**To implement automatic migration on calc load**:

1. **File**: `src/qmatsuite/core/models.py`
   - **Function**: `CalculationModel.from_dict()` (lines 192-264)
   - **Change**: After loading `species_map` (line 254), iterate through entries and if `pseudo_sha_family` missing but `pseudo_basename` present, compute from file
   - **Challenge**: Need project_root to resolve file path, need to handle missing files gracefully

2. **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
   - **Function**: `restoreSelectionFromCalc()` (lines 495-633)
   - **Change**: After matching variant, if `entry.pseudo_sha_family` missing, compute from matched variant's `sha_family` and write back
   - **Challenge**: Would require calling `onUpdate()` during restore (violates "restore does NOT write" rule)

3. **File**: `src/qmatsuite/core/pseudo_runtime.py`
   - **Function**: `species_map_to_selections()` (lines 614-669)
   - **Change**: If `pseudo_sha_family` missing but file exists, compute from file before creating `PseudoSelection`
   - **Challenge**: Need to resolve file path (project/internal/lib), may not be available at this stage

4. **File**: `src/qmatsuite/core/pseudo_runtime.py`
   - **Function**: `refresh_calc_pseudo_records_after_step0()` (lines 672-738)
   - **Change**: Already computes `sha_family` from file (line 719), but only if file exists
   - **Enhancement**: Could compute from other sources (internal/lib) if project file missing

**To implement migration on UI restore** (without writing calc.yml):

5. **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
   - **Function**: `restoreSelectionFromCalc()` (lines 495-633)
   - **Change**: After matching variant (line 621), if `entry.pseudo_sha_family` missing, could set local state with variant's `sha_family` but NOT write to calc.yml
   - **Note**: This would only update UI state, not persist migration

**Recommended approach**: Migration should happen in Step0 refresh (already implemented) OR in a separate migration pass that runs before UI restore.

---

## 6. Evidence Summary

### 6.1 Schema Definition
- **File**: `src/qmatsuite/core/models.py`
- **Lines**: 147-152 (schema comment), 186-188 (to_dict), 253-254 (from_dict)
- **Finding**: Schema supports `pseudo_sha_family`, all fields optional

### 6.2 UI Restore Logic
- **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
- **Lines**: 495-633 (`restoreSelectionFromCalc`)
- **Finding**: Only reads `pseudo_sha256` and filename, never reads `pseudo_sha_family` or `pseudo_sha_token`

### 6.3 User Selection Change
- **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx`
- **Lines**: 755-797 (`handlePseudoChange`)
- **Finding**: Writes `pseudo_sha_family` together with `pseudo_sha256` and `pseudo_basename`

### 6.4 Step0 Refresh
- **File**: `src/qmatsuite/core/pseudo_runtime.py`
- **Lines**: 672-738 (`refresh_calc_pseudo_records_after_step0`)
- **Finding**: Computes `sha_family` from file and writes to calc.yml (if file exists)

### 6.5 Legacy Field References
- **Search**: `grep -r "pseudo_sha_token"`
- **Finding**: Only found in documentation files, no code references

### 6.6 Missing File Handling
- **File**: `src/qmatsuite/core/pseudo_runtime.py`
- **Lines**: 726-733
- **Finding**: If file missing, keeps stored triplet unchanged (no mutation, no `sha_family` computation)

---

## 7. Summary

**Current State**:
- ✅ Code fully migrated to `pseudo_sha_family` (no `pseudo_sha_token` references)
- ✅ Step0 refresh computes and writes `pseudo_sha_family` (if file exists)
- ✅ User selection change writes `pseudo_sha_family` (migration happens)
- ❌ UI restore does NOT read or write `pseudo_sha_family` (only uses sha256/filename)
- ❌ No automatic migration on calc load (no code computes `sha_family` when field missing)

**Backward Compatibility Gap**:
- If calc.yml has `pseudo_sha_token`: **Completely ignored** (no code reads it)
- If calc.yml has `pseudo_sha256` but missing `pseudo_sha_family`: 
  - UI restore works (matches by sha256)
  - `pseudo_sha_family` remains missing until user changes selection OR Step0 runs
  - If file missing from `project/pseudo`, Step0 refresh won't compute `sha_family`

**Migration Path**:
- **Automatic**: Happens on next user selection change (writes new triplet)
- **Automatic**: Happens on next Step0 run + refresh (computes from file, if file exists)
- **Manual**: User must change selection or run calculation to trigger migration

**Recommendation**: Migration is functional but not immediate. Old calc.yml files will work but `pseudo_sha_family` will remain missing until user interaction or Step0 execution.

