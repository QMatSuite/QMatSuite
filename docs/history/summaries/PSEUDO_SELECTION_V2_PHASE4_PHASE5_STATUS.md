# Pseudo Selection V2 - Phase 4 & 5 Implementation Status

## Completed Work

### Phase 4.1-4.3: Backend sha_token-first Refactor ✓

**File: `src/qmatsuite/core/pseudo_options.py`**

1. **New Schema:**
   - Added `PseudoOptionGroup` dataclass (sha_token-primary)
   - Added `Variant` dataclass (sha256 variants within a group)
   - Updated `PseudoSource` to include `library_name` and `library_version`
   - Kept legacy `PseudoOption` for backward compatibility

2. **New Function:**
   - `get_pseudo_options_for_elements_sha_token()` - Groups by sha_token first
   - Handles name collisions with sha_token disambiguation: `basename (tok-<sha_token[:8]>)`
   - Aggregates sources from all variants within a group
   - Sets `recommended_source` (project > internal > first installed lib)

3. **Source Scanning:**
   - Scans project/pseudo (with LRU cache)
   - Scans internal resources/pseudo
   - Scans library archives from vendored index/manifest
   - Marks installed/corrupt status correctly

### Phase 4.4: API & RPC Wiring ✓

**Files:**
- `src/qmatsuite/api.py`: Updated `get_pseudo_options_for_elements()` with `use_sha_token_grouping` flag
- `src/qmatsuite/daemon/server.py`: Updated `_handle_get_pseudo_options_for_calculation()` to use sha_token-first function

### Phase 4.5-4.7: UI Refactor ⏳ (Partially Complete)

**File: `gui/src/components/common_cards/CommonCardPseudo.tsx`**

**Completed:**
- Added `PseudoOptionGroup` TypeScript interface
- Added state for both legacy and new formats
- Updated fetch logic to detect format and store appropriately

**Remaining:**
- Update selection logic to use `sha_token` instead of `sha256`
- Update dropdown rendering to show `display_label` from groups
- Update chip rendering to use group sources
- Add warnings display using `analyze_project_pseudo_effects()`
- Update `handlePseudoChange` to store sha_token as primary key
- Update `onUpdate` to send sha_token-based selections

### Phase 5: Tests ⏳ (Pending)

**Required Tests:**
1. `tests/unit/test_pseudo_runtime_step0.py`:
   - Noop test (same sha256)
   - Overwrite test (same sha_token, different sha256)
   - Rename test (different sha_token, same basename)
   - Analyzer read-only test (monkeypatch filesystem ops)
   - Calc refresh test

2. `tests/unit/test_pseudo_options_shatoken_grouping.py`:
   - Grouping by sha_token
   - Name collision disambiguation
   - Source aggregation
   - Installed/corrupt flag propagation

## Next Steps

### Immediate (Complete UI Refactor)

1. **Update selection logic in CommonCardPseudo.tsx:**
   ```typescript
   // Change from:
   value={currentOption ? (currentOption.sha256 || ...) : ''}
   // To:
   value={currentGroup ? currentGroup.sha_token : ''}
   
   // Change selection matching from sha256 to sha_token
   const currentGroup = groups.find(g => g.sha_token === currentShaToken);
   ```

2. **Update dropdown rendering:**
   ```typescript
   {groups.map((group) => (
     <option key={group.sha_token} value={group.sha_token}>
       {group.display_label}
     </option>
   ))}
   ```

3. **Add warnings display:**
   - Call `qms.analyzeProjectPseudoEffects()` on selection change
   - Render warnings inline next to pseudo row
   - Show predicted effects (rename/overwrite)

4. **Update apply/run gating:**
   - Check if selected lib source is installed and not corrupt
   - Block with clear message if not

### Tests (Phase 5)

1. Create `test_pseudo_runtime_step0.py` with temp project setup
2. Create `test_pseudo_options_shatoken_grouping.py` with synthetic data
3. Ensure all tests are offline (no network)

## Constitution Compliance Checklist

✅ **Three Sources Only:** project, internal, lib
✅ **sha_token Primary:** Backend groups by sha_token
✅ **No UI Mutations:** Analyzer is read-only
⏳ **UI sha_token Selection:** Needs completion
⏳ **Warnings Display:** Needs implementation
⏳ **Tests:** Need creation

