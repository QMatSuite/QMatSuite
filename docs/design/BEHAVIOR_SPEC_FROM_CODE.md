# Behavior Spec from Code: Pseudo Selection V2 + Step0

**Audit Date**: Code-only review (no prior assumptions)  
**Scope**: Pseudo Selection V2 + Step0 implementation  
**Method**: Extract exact runtime/UI behavior from code as it exists today

---

## 1. Entities & Persisted Fields

### 1.1 calc.yml Storage for Pseudos

**File**: `src/qmatsuite/core/models.py` (lines 147-152, 186-188, 253-254)

**Fields stored in `species_map`**:
- `pseudopot`: Optional string (legacy filename field, for backward compatibility)
- `pseudo_basename`: Optional string (filename in project/pseudo)
- `pseudo_sha256`: Optional string (strict bytes identity - PRIMARY selection key)
- `pseudo_sha_token`: Optional string (physical equivalence hash - for warnings/collision detection)
- `mass`: Optional float (atomic mass)

**Required vs Optional**:
- All fields are optional in the schema
- When user selects a pseudo, all three (`pseudo_basename`, `pseudo_sha256`, `pseudo_sha_token`) are written together as a triplet
- Legacy calculations may have only `pseudopot` (filename-only)

**When fields are written/refreshed**:
1. **User-initiated selection change**: Written immediately via `update_calculation_species_map()` → `save_calculation()` (see Section 5)
2. **After Step0**: Refreshed via `refresh_calc_pseudo_records_after_step0()` (lines 672-725 in `pseudo_runtime.py`) which:
   - Reads actual file from `project/pseudo/<basename>`
   - Computes `sha256` and `sha_token` from file
   - Updates all three fields in `species_map`
   - Saves via `save_calculation()`

**Unclear / needs confirmation**:
- What happens if `refresh_calc_pseudo_records_after_step0()` is called but file doesn't exist? Code checks `if actual_file.exists()` (line 714) but doesn't handle missing file case explicitly.

---

## 2. Pseudo Sources Model

### 2.1 Exact Pseudo Sources Used at Runtime

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 41-45, 243-346, 349-532)

**Three sources only** (constitution-compliant):
1. **`project`**: `project_root/pseudo/` directory
2. **`internal`**: `resources/pseudo/` (via `get_system_pseudo_dir()`)
3. **`lib`**: Installed archives in `temp/pseudo/...` (extracted from archives)

**Filesystem locations**:
- Project: `project_root/pseudo/` (scanned for `*.UPF` and `*.upf`)
- Internal: `resources/pseudo/` (scanned for `*.UPF` and `*.upf`)
- Lib: Extracted from installed archives (location determined by `get_pseudo_install_root()` → `get_archives_dir()`)

### 2.2 Selectable vs Informational

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 936-941)

**Selectable in UI**:
- Only variants with filesystem-real sources are shown in dropdown:
  - Project source (file exists in `project/pseudo`)
  - Internal source (file exists in `resources/pseudo`)
  - Installed lib source (`installed=True` AND `corrupt=False`)

**Filtering logic** (lines 936-941):
```typescript
const realVariants = variants.filter(v => {
  const hasProject = v.sources.some(s => s.kind === 'project' && s.installed);
  const hasInternal = v.sources.some(s => s.kind === 'internal' && s.installed);
  const hasInstalledLib = v.sources.some(s => s.kind === 'lib' && s.installed && !s.corrupt);
  return hasProject || hasInternal || hasInstalledLib;
});
```

**Informational only**:
- Uninstalled lib sources are shown as provenance chips but not selectable
- Corrupt lib sources are shown with warning but not selectable

**Unclear / needs confirmation**:
- Are "not installed" libs included in the options list but disabled, or excluded entirely? Code shows they're filtered out of `realVariants` but may still appear in source chips.

---

## 3. Option Building (Backend)

### 3.1 Exact Data Returned for Pseudo Options

**File**: `src/qmatsuite/core/pseudo_options.py` (lines 218-601)

**Function**: `get_pseudo_options_for_elements()`

**Return shape**: `Dict[str, List[Dict[str, Any]]]` mapping element → list of `PseudoVariant` dicts

**PseudoVariant structure** (lines 64-109):
```python
{
    "sha256": str,  # Primary selection key
    "sha_token": str,  # For warnings/collision detection
    "basename": str,
    "element": str,
    "sources": List[PseudoSource],  # Array of source chips
    "size_bytes": Optional[int],
    "upf_format": Optional[str],
    "is_project_local_unknown": bool,  # True if project has basename but sha256 not in index
    "token_match_warnings": List[str],  # Warnings about token matches
    "display_label": str,  # Computed: "Element: basename" or "Element: basename (project-local)"
    "availability": {
        "any_installed": bool
    }
}
```

**PseudoSource structure** (lines 51-61):
```python
{
    "kind": "project" | "internal" | "lib",
    "label": str,  # Human-readable (e.g., "SSSP Precision 1.3.0 PBE")
    "installed": bool,
    "corrupt": bool,
    "warning": Optional[str],
    "archive_asset": Optional[str],  # For lib sources
    "library_name": Optional[str],  # For lib sources
    "library_version": Optional[str]  # For lib sources
}
```

### 3.2 How Candidates are Collected

**Collection order** (lines 282-571):
1. **Scan project pseudos** (lines 282-401):
   - Scan `project_root/pseudo/` for `*.UPF` and `*.upf`
   - Compute `sha256` and `sha_token` for each file
   - Parse element from file content or filename
   - If `sha256` in index: create variant with project source + library chips
   - If `sha256` not in index: create variant with `is_project_local_unknown=True`

2. **Scan internal pseudos** (lines 403-506):
   - Scan `resources/pseudo/` for `*.UPF` and `*.upf`
   - Compute `sha256` and `sha_token`
   - Parse element
   - Add internal source chip to variant
   - Check for token-match with project files (different sha256, same sha_token) → add warnings

3. **Add library-only variants** (lines 508-571):
   - Iterate through `bundle.index.get("files", [])`
   - For each file entry, infer element from basenames
   - If `sha256` not already in variants (from project/internal scan), create new variant
   - Add library chips from occurrences

### 3.3 Sorting/Stability Rules

**File**: `src/qmatsuite/core/pseudo_options.py` (lines 573-599)

**Sorting key** (lines 584-596):
```python
def sort_key(v: PseudoVariant) -> tuple:
    has_project = any(s.kind == "project" and s.installed for s in v.sources)
    has_internal = any(s.kind == "internal" and s.installed for s in v.sources)
    any_installed_lib = any(s.kind == "lib" and s.installed and not s.corrupt for s in v.sources)
    any_available_lib = any(s.kind == "lib" for s in v.sources)
    
    return (
        not has_project,  # Project first (False sorts before True)
        not has_internal,  # Then internal
        not any_installed_lib,  # Then installed lib
        not any_available_lib,  # Then available lib
        v.basename,  # Then by basename (lexicographic)
    )
```

**Stability**: Deterministic (same inputs → same order)

---

## 4. UI Rendering + Selection Key

### 4.1 Dropdown Value Key

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 984-1029)

**Value key**: `sha256` (strict bytes identity) - PRIMARY selection key

**Evidence**:
- Line 985: `<select value={useVariants && currentVariant ? currentVariant.sha256 : ...}`
- Line 1026: `<option key={variant.sha256} value={variant.sha256}>`

**Label shown**: `variant.display_label` (computed as `"Element: basename"` or `"Element: basename (project-local)"`)

### 4.2 Provenance Chips Computation and Coloring

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 1048-1067)

**Chip rendering**:
- Each variant's `sources` array is rendered as chips
- Chip class determined by:
  - `common-card-pseudo__source-chip--installed`: If `kind === 'project' || kind === 'internal' || (kind === 'lib' && installed && !corrupt)`
  - `common-card-pseudo__source-chip--available`: Otherwise (uninstalled/corrupt lib)

**Chip content**:
- Shows `source.label` (human-readable library name)
- If `corrupt`: Prefix with `⚠️`
- Tooltip shows `source.warning` if corrupt, else `source.archive_asset || source.label`

### 4.3 "Not Installed" Libs Inclusion

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 936-941)

**Exclusion rule**: Variants are filtered to only include those with filesystem-real sources:
- Project source exists
- Internal source exists
- Installed lib source (installed AND not corrupt)

**Result**: Uninstalled libs are NOT included in dropdown options, but may appear as provenance chips on installed variants.

---

## 5. Default Selection / Restore Logic

### 5.1 Step-by-Step Algorithm When Opening a Calc

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 352-504)

**Function**: `restoreSelectionFromCalc()`

**Algorithm**:

1. **Primary: Match by sha256** (lines 372-434):
   - Extract `calcSha256` from `mapping.species_map[element].pseudo_sha256`
   - Filter variants: `variants.filter(v => v.sha256 === calcSha256)`
   - If 0 matches: proceed to fallback
   - If 1 match: select it
   - If multiple matches: apply tie-break (see below)

2. **Tie-break for multiple sha256 matches** (lines 380-433):
   - **Step 1**: If `calcFilename` exists, prefer filename match: `candidates.filter(v => v.basename === calcFilename)`
   - **Step 2**: Source priority: project > internal > lib (installed, not corrupt)
   - **Step 3**: If multiple libs, sort by `library_name + archive_asset` lexicographically
   - **Step 4**: If same lib (or non-lib), sort by `basename` lexicographically
   - Select first candidate after all tie-breaks

3. **Fallback: Match by filename** (lines 436-489):
   - Extract `calcFilename` from `entry.pseudo_basename || entry.pseudopot`
   - Filter to filesystem-real variants only
   - Try project first: `realVariants.find(v => v.basename === calcFilename && hasProject)`
   - Then internal: `realVariants.find(v => v.basename === calcFilename && hasInternal)`
   - Then lib: Filter lib matches, sort by library/asset name + basename, select first

4. **If no match found**: Log warning, leave selection empty

### 5.2 Confirm: Does Restore Write calc.yml?

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 352-504)

**Answer**: **NO** - restore does NOT write calc.yml

**Evidence**:
- Line 148: `hasRestoredRef` tracks if restore has run (prevents multiple restores)
- Lines 494-496: Only calls `setLocalMapping`, `setLocalMappingSha256`, `setLocalMappingShaToken`, `setSelectedSha256ByElement`
- Does NOT call `onUpdate()` (which would write calc.yml)
- Comment on line 352: "Restore selection from calc.yml (does NOT write calc.yml)"

### 5.3 Corner Cases

**Renamed files**: Handled by fallback filename match (if sha256 not found, try filename)

**Missing sha256**: Falls back to filename match

**Missing filename**: If both sha256 and filename missing, no match found (warning logged)

**Partial triplets**: Code handles missing fields gracefully:
- Line 368: `const calcSha256 = entry.pseudo_sha256;` (may be undefined)
- Line 369: `const calcFilename = entry.pseudo_basename || entry.pseudopot;` (fallback chain)

---

## 6. User-Initiated Selection Change

### 6.1 Step-by-Step What Happens When User Picks New Option

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 604-646)

**Function**: `handlePseudoChange(species: string, variant: PseudoVariant)`

**Steps**:

1. **Update local state** (lines 606-622):
   - `setLocalMapping({...prev, [species]: variant.basename})`
   - `setLocalMappingSha256({...prev, [species]: variant.sha256})`
   - `setLocalMappingShaToken({...prev, [species]: variant.sha_token})`
   - `setSelectedSha256ByElement({...prev, [species]: variant.sha256})`

2. **Determine source kind** (lines 624-628):
   - Priority: project > internal > lib
   - Used for debug log only

3. **Write triplet to calc.yml** (lines 630-642):
   - Calls `onUpdate()` with:
     - `mapping`: `{ [species]: variant.basename }`
     - `sha256Map`: `{ [species]: variant.sha256 }`
     - `shaTokenMap`: `{ [species]: variant.sha_token }`
   - This triggers `update_calculation_species_map()` RPC call

4. **Debug log** (line 639):
   - Logs: `[CommonCardPseudo] User selection changed: element=..., filename=..., sha256=..., sha_token=..., source=...`

5. **Trigger analysis** (line 645):
   - Calls `analyzeSelections()` after 100ms delay (to allow state to settle)

### 6.2 What is Written to calc.yml

**File**: `src/qmatsuite/api.py` (lines 5272-5330)

**Function**: `update_calculation_species_map()`

**Written fields**:
- `pseudopot`: basename (legacy compatibility)
- `pseudo_basename`: basename
- `pseudo_sha256`: sha256
- `pseudo_sha_token`: sha_token
- `mass`: preserved if exists

**All fields written together** in single `save_calculation()` call.

### 6.3 Logging

**Backend**: No explicit logging in `update_calculation_species_map()` (only via daemon RPC logging)

**Frontend**: Debug log on line 639 of `CommonCardPseudo.tsx`

### 6.4 Warning Generation / Analyzer Calls

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 506-602)

**Function**: `analyzeSelections()`

**Called**:
- After user selection change (line 645, 100ms delay)
- After options load (line 188, if selections exist)
- Before Apply button (line 718)

**What it does**:
1. Builds `selections` array from `selectedSha256ByElement`
2. Determines `source_kind` for each (project > internal > lib priority)
3. Calls `qms.analyzeProjectPseudoEffects()` RPC
4. Parses warnings/errors from response
5. Adds token-match warnings from variants
6. Updates `warningsByElement` and `errorsByElement` state

### 6.5 Whether Selection Updates Can Be Blocked/Gated

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 694-714, 716-730)

**Gating logic**: `canApply()` function

**Blocks Apply/Run if**:
- Any selected variant has no viable source (not project, not internal, not installed+not-corrupt lib)

**Evidence**:
- Line 702-707: Checks `hasViableSource` for each selection
- Line 721-724: `handleApply()` checks `canApply()` before proceeding
- Line 1440: Apply button is `disabled={!canApply()}`

**Note**: User can still change selection in dropdown (not blocked), but Apply/Run is disabled.

---

## 7. Warnings Model

### 7.1 What Warnings Exist and How They're Computed

**Backend analyzer**:
- **File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 243-346)
- **Function**: `analyze_project_pseudo_effects()`
- **Returns**: `PseudoPrepareReport` with `actions`, `warnings`, `errors`

**Warning types**:
1. **Same sha_token, different sha256** (lines 310-313):
   - Message: `"{element}: Project pseudo will be overwritten with canonical library/internal version (sha_token same but sha256 differs)"`

2. **Different sha_token** (lines 322-325):
   - Message: `"{element}: Project pseudo '{basename}' exists with different sha_token. Run will rename existing file and update affected calcs."`

3. **Token-match warnings** (from options):
   - **File**: `src/qmatsuite/core/pseudo_options.py` (lines 438-452)
   - Added to `variant.token_match_warnings` when project file has same basename with token-match but different sha256

**UI-only warnings**:
- **No viable source** (line 1116-1120): "Selected pseudo requires installing archive(s). Go to Settings → Pseudopotentials."
- **Token-match warnings** displayed inline (lines 1091-1099)

### 7.2 Token-Match Edge Case Presentation

**File**: `src/qmatsuite/core/pseudo_options.py` (lines 438-452)

**Enforcement**: Backend adds warnings to variants during option building

**UI presentation**:
- **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 1091-1099)
- Token-match warnings displayed as separate inline warning divs
- Each variant with token-match shows warning: `"project has same filename with token-match but different bytes; selecting this will overwrite on Run"`

**Separation**: Variants are NOT merged - project variant and external variant are separate entries in dropdown (keyed by different sha256)

---

## 8. Run Pipeline (Step0)

### 8.1 Exact Call Stack from Clicking Run to Step0 Execution

**File**: `src/qmatsuite/calculation/runner.py` (lines 62-124)

**Call stack**:
1. User clicks Run → `run_calculation` RPC
2. `CalculationRunner.run()` called (line 62)
3. **Step0 executes** (lines 69-124):
   - `species_map_to_selections()` (line 79-82)
   - `prepare_project_pseudos_for_run()` (line 86-89)
   - `refresh_calc_pseudo_records_after_step0()` (line 92-96)

### 8.2 Step0 Executor Algorithm

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 349-532)

**Function**: `prepare_project_pseudos_for_run()`

**Algorithm per selection**:

1. **Project source behavior** (lines 394-408):
   - If `source_kind == "project"`:
     - Verify file exists at `project_pseudo_dir / requested_basename`
     - If exists: **noop** (action: "noop", detail: "Using existing project pseudo")
     - If not exists: error

2. **External selection behavior** (lines 410-435):
   - If `source_kind == "internal"` or `"lib"`:
     - Resolve source path via `_resolve_internal_source_path()` or `_resolve_lib_source_path()`
     - If not found: error

3. **Collision resolution rules** (lines 456-515):
   - **If destination exists** (`project_pseudo_dir / requested_basename`):
     - Compute `existing_sha256` and `existing_sha_token`
     - **Same sha256** (line 461): **noop** (action: "noop")
     - **Same sha_token, different sha256** (line 471): **overwrite** (action: "overwrite", `shutil.copy2(source_path, dst)`)
     - **Different sha_token** (line 483): **rename_existing**:
       - Rename pattern: `{stem}__tok-{sha_token[:10]}{suffix}`
       - If name collision, append `_{counter}`
       - Call `update_project_calcs_filename_by_sha_token()` to update other calcs

4. **Renaming scheme** (lines 485-495):
   - Pattern: `{basename_stem}__tok-{sha_token[:10]}{extension}`
   - Example: `Si.upf` → `Si__tok-abc123def4.upf`
   - Uniqueness: If exists, append `_1`, `_2`, etc.

5. **How calc references are updated** (lines 505-511):
   - `update_project_calcs_filename_by_sha_token()`:
     - Scans all calculations in project
     - Finds entries with matching `sha_token` and old filename
     - Updates only `pseudopot` and `pseudo_basename` fields (keeps sha256/sha_token unchanged)
     - Saves each updated calculation

6. **How calc records are refreshed** (lines 672-725):
   - `refresh_calc_pseudo_records_after_step0()`:
     - Loads calculation from `calculation.yaml`
     - For each element in `species_map`:
       - Gets basename from entry
       - Reads actual file from `project_pseudo_dir / basename`
       - Computes `sha256` and `sha_token` from file
       - Updates entry: `pseudopot`, `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_token`
     - Saves calculation

**Unclear / needs confirmation**:
- What happens if file doesn't exist during refresh? Code checks `if actual_file.exists()` but doesn't handle missing file.

---

## 9. Determinism & Tie-Break

### 9.1 Where Determinism is Enforced

**Backend**:
- **File**: `src/qmatsuite/core/pseudo_options.py` (lines 584-596)
- Sorting is deterministic (same inputs → same order)
- Tie-break rules are stable (project > internal > lib, then lexicographic)

**UI**:
- **File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 380-433, 466-480)
- Restore algorithm applies same tie-break rules as backend
- Multi-lib matches sorted by `library_name + archive_asset` lexicographically, then by `basename`

### 9.2 Multi-Lib Match Resolution

**File**: `gui/src/components/common_cards/CommonCardPseudo.tsx` (lines 404-424, 466-480)

**Tie-break for multi-lib matches**:
1. Sort by `library_name + archive_asset` (concatenated, lowercased) lexicographically
2. If same lib, sort by `basename` lexicographically
3. Select first after sorting

**Evidence**:
- Lines 406-423: Multi-sha256 match tie-break
- Lines 466-480: Filename fallback tie-break

---

## 10. Potential Drift / Inconsistencies

### 10.1 UI Restore vs UI Selection Persistence

**Issue**: Restore uses `sha256` as primary key, but selection persistence also uses `sha256`. These should be consistent.

**Evidence**:
- Restore: `selectedSha256ByElement[element] = variant.sha256` (line 492)
- Selection: `setSelectedSha256ByElement({...prev, [species]: variant.sha256})` (line 619)

**Status**: ✅ **Consistent** - Both use `sha256` as primary key.

### 10.2 Backend Option Identity vs UI Selection Key

**Issue**: Backend returns variants keyed by `sha256`, UI uses `sha256` as dropdown value. Should match.

**Evidence**:
- Backend: `PseudoVariant.sha256` (line 72 in `pseudo_options.py`)
- UI: `<option value={variant.sha256}>` (line 1026 in `CommonCardPseudo.tsx`)

**Status**: ✅ **Consistent** - Both use `sha256`.

### 10.3 Step0 Rules vs What UI Implies

**Issue**: UI shows token-match warnings, but Step0 overwrites on same sha_token. Is this consistent?

**Evidence**:
- UI: Shows warning "token matches ... (bytes differ)" (line 450 in `pseudo_options.py`)
- Step0: Overwrites if `existing_sha_token == source_sha_token` (line 471 in `pseudo_runtime.py`)

**Status**: ✅ **Consistent** - UI warns, Step0 overwrites (user must explicitly select external variant).

**Potential issue**: UI restore might select project variant (sha256 match), but if user later selects external variant (same sha_token), Step0 will overwrite. This is intentional (user explicitly selected external).

### 10.4 Tests vs Implementation

**Issue**: Need to verify tests cover all Step0 scenarios.

**Evidence**:
- **File**: `tests/unit/test_pseudo_runtime_step0.py`
- Tests exist for:
  - `test_step0_noop_project_source` (line 111)
  - `test_step0_noop_same_sha256` (line 147)
  - `test_analyzer_read_only` (line 316)
  - `test_calc_refresh_after_step0` (line 353)
  - `test_species_map_to_selections` (line 391)

**Status**: ⚠️ **Needs confirmation** - Tests exist but coverage completeness unclear.

### 10.5 Missing File Handling in Refresh

**Issue**: `refresh_calc_pseudo_records_after_step0()` checks `if actual_file.exists()` but doesn't handle missing file case.

**File**: `src/qmatsuite/core/pseudo_runtime.py` (lines 712-722)

**Evidence**:
- Line 714: `if actual_file.exists():`
- No `else` clause - missing file case is silently ignored

**Status**: ⚠️ **Unclear / needs confirmation** - What should happen if file doesn't exist after Step0? Should it error? Clear fields? Log warning?

---

## 11. Manual Scenarios to Verify

Based on code behavior, verify these scenarios:

1. **Restore by sha256**:
   - Create calc with `pseudo_sha256` set
   - Open calculation panel
   - Verify: Selection restored by sha256 match
   - Verify: calc.yml modification time unchanged

2. **Restore by filename fallback**:
   - Create calc with only `pseudo_basename` (no sha256)
   - Open calculation panel
   - Verify: Selection restored by filename match (project > internal > lib priority)

3. **Multi-sha256 tie-break**:
   - Create calc with sha256 that matches multiple variants
   - Set `pseudo_basename` to match one variant
   - Open calculation panel
   - Verify: Variant with matching basename is selected

4. **User selection change**:
   - Change selection in dropdown
   - Verify: Browser console shows debug log with triplet
   - Verify: calc.yml has all three fields updated together

5. **Step0 project source noop**:
   - Select project pseudo
   - Run calculation
   - Verify: File unchanged, calc records refreshed with actual sha256/sha_token

6. **Step0 external overwrite**:
   - Project has file with same sha_token but different sha256
   - Select external variant
   - Run calculation
   - Verify: Project file overwritten, calc records updated

7. **Step0 rename existing**:
   - Project has file with different sha_token
   - Select external variant
   - Run calculation
   - Verify: Existing file renamed to `__tok-{sha_token[:10]}.upf`, calc records updated

8. **Token-match warning**:
   - Project has file with same basename, token-match but different sha256
   - Open calculation panel
   - Verify: Both project and external variants shown separately with token-match warnings

9. **Uninstalled lib gating**:
   - Select variant that requires uninstalled archive
   - Verify: Apply button disabled, warning shown

10. **Missing file after Step0**:
    - Run calculation, then manually delete file from `project/pseudo`
    - Open calculation panel
    - Verify: Behavior (should restore fail? Should it clear selection? Should it error?)

---

## Summary

**Key Findings**:
- ✅ Selection key is `sha256` (consistent across backend and UI)
- ✅ Restore does NOT write calc.yml (read-only)
- ✅ User selection writes triplet together (filename + sha256 + sha_token)
- ✅ Step0 handles project source as noop, external as copy/overwrite/rename
- ✅ Token-match variants are shown separately (not merged)
- ⚠️ Missing file handling in refresh is unclear
- ⚠️ Test coverage completeness needs verification

**Files Referenced**:
- `src/qmatsuite/core/pseudo_options.py` (option building)
- `src/qmatsuite/core/pseudo_runtime.py` (Step0 execution)
- `src/qmatsuite/core/models.py` (calc.yml schema)
- `src/qmatsuite/calculation/runner.py` (Step0 integration)
- `gui/src/components/common_cards/CommonCardPseudo.tsx` (UI restore/selection)
- `gui/src/types/qms.ts` (TypeScript types)
- `gui/src/hooks/useQMSClient.ts` (RPC calls)

