# K_POINTS State Model and Fixes Summary

## State Model (Canonical Source of Truth)

### Decision: `rawBodyText` is the Canonical Source

**Canonical Source**: `rawBodyText` (string) - the body portion of K_POINTS card

**Architecture**:
- `rawBodyText` is the SINGLE source of truth for K_POINTS body data
- All structured state (`localAutomatic`, `localPoints`) is DERIVED from `rawBodyText` when needed
- When user edits structured fields → `rawBodyText` is UPDATED (one-way: structured → rawBodyText)
- When user edits raw text → `rawBodyText` is UPDATED directly
- On Apply, `rawBodyText` is ALWAYS saved (never structured state directly)

### Flow Diagram

```
Initialize:
  viewModel → derive rawBodyText → derive structured state (for display)

Structured Edit:
  update structured state → update rawBodyText (one-way sync)

Raw Edit:
  update rawBodyText directly (NO sync to structured)

Apply:
  save rawBodyText (with mode header) → backend re-parses on next load
```

### No Two-Way Sync (Prevents Loops)

- `rawBodyText` never syncs FROM structured state after raw edit
- Structured state only syncs FROM `rawBodyText` when toggling raw→structured (parse)
- This prevents loops and preserves user raw edits

**Why this works**:
- User edits raw → `rawBodyText` changes → structured state stays stale (preserved)
- User edits structured → `rawBodyText` updates → structured state updates (one-way)
- Toggle raw→structured → parse `rawBodyText` → update structured (one-time parse)
- Apply → save `rawBodyText` → backend re-parses on next load

## In-Flight Guards (Double-Submit Prevention)

### Implementation

1. **K_POINTS Component**:
   - `isApplyingRef` (useRef) tracks in-flight state
   - `handleApply` checks guard at start, sets to true, clears in finally
   - Header Apply button disabled when `isApplyingRef.current === true`
   - `onApplyingChange` callback notifies parent of applying state

2. **Global Apply Button**:
   - Disabled when `kPointsApplying === true` (from callback)
   - Disabled when `isSaving === true` (normal params saving)
   - Shows "Saving..." when either is true

3. **Prevention**:
   - If `handleApply` is called while `isApplyingRef.current === true`, it returns early
   - Both header Apply and global Apply use the same `handleApply` function
   - No race conditions possible

## Apply Ordering (Deterministic)

### Order: K_POINTS First, Then Normal Parameters

```typescript
// In handleSaveParams:
1. Apply K_POINTS (if dirty) → await kPointsRef.current.apply()
   - This calls setCommonCard RPC → updates step.yaml with K_POINTS card
   - onUpdate callback refreshes stepDetail
   
2. Apply normal parameters → await update_step_params RPC
   - This updates step.yaml with namelist parameters
   - Uses stepDetail from step 1 (already refreshed)
```

**Why this order**:
- K_POINTS is a "common card" (special handling)
- Normal parameters are namelist-based (standard handling)
- Sequential execution ensures no YAML interleaving
- Each RPC call is atomic (backend handles YAML write atomically)

**No interleaving possible**:
- Both operations are `await`ed sequentially
- Backend YAML writes are atomic
- stepDetail is refreshed between operations

## Raw Pane Debug Visibility (View Mode)

### Implementation

**Always Expanded by Default**:
- `isExpanded` state starts as `true`
- Raw text pane is always visible when expanded
- User can collapse/expand via ▼/▶ button

**Raw Text Pane**:
- Shows `canonical_raw` from viewModel (or `fullRawText` if not available)
- Includes "📋 Copy" button to copy raw text to clipboard
- Always visible when expanded (not hidden behind toggle)

**Debug Info Pane** (🔍 button):
- Shows parsed JSON with all fields:
  - mode, parse_ok, automatic, points, warnings, errors, raw
- Includes "📋 Copy JSON" button
- Collapsible (only shown when 🔍 button clicked)

**Context Menu** (Future):
- Can be added via right-click on raw text pane
- Would show "Copy Raw", "Copy JSON", "Show Debug" options

## Pseudo Download Concurrency Lock

### Implementation

**Frontend (`usePseudoConfig.ts`)**:
- `downloadInFlightRef` (useRef) tracks download state
- Both `downloadLibrary` and `downloadAll` check guard
- If already downloading, returns error: "Another download is already in progress"
- `isDownloading` state also tracks (for UI feedback)

**Backend (`pseudo_config.py`)**:
- No additional lock needed (frontend prevents concurrent calls)
- But handles corrupted tar files:
  - Attempts to open tar file before extraction
  - If `TarError`, `OSError`, or `EOFError` → deletes corrupted file
  - Returns clear error message: "Downloaded archive is corrupted (tar open failed: {e}). Please retry download."

## Pseudo Download UX (Disabled When OFF)

### Implementation

**Button States**:
- All download buttons disabled when `config?.allow_download === false`
- Disabled state shows with tooltip: "Enable 'Allow Network Downloads' to download"
- Description text shows: "⚠️ Network downloads are disabled. Enable 'Allow Network Downloads' above to download."

**User Flow**:
1. User sees disabled buttons with clear hint
2. User enables "Allow Network Downloads" toggle
3. Buttons become enabled
4. User clicks download button → download proceeds

**No Confirmation Modal When OFF**:
- Buttons are disabled, so no click possible
- User must enable toggle first
- This is cleaner UX than showing modal on disabled buttons

## Files Changed

### Frontend
- `gui/src/components/common_cards/CommonCardKPoints.tsx`:
  - Documented state model in header comment
  - Made `rawBodyText` canonical source
  - Added `isApplyingRef` guard
  - Added `onApplyingChange` callback
  - Added copy buttons for raw text and debug JSON
  - Always expanded by default
  
- `gui/src/components/common_cards/CommonCardKPoints.css`:
  - Added styles for copy buttons
  
- `gui/src/components/panels/StepDetailPanel.tsx`:
  - Added `kPointsApplying` state
  - Disabled global Apply when K_POINTS is applying
  - Documented Apply ordering
  
- `gui/src/hooks/usePseudoConfig.ts`:
  - Added `downloadInFlightRef` concurrency lock
  - Both download functions check lock before proceeding
  
- `gui/src/components/panels/SettingsPanel.tsx`:
  - Disabled download buttons when `allow_download === false`
  - Added clear inline hints
  - Improved error messages

### Backend
- `src/quantumvitas/core/pseudo_config.py`:
  - Added corrupted tar detection
  - Deletes corrupted files and returns clear error

## Why This Cannot Regress

1. **State Model**: `rawBodyText` is explicitly documented as canonical source in code comments
2. **In-Flight Guards**: `isApplyingRef` prevents double-submit at function level
3. **Apply Ordering**: Sequential `await` ensures deterministic order
4. **Concurrency Lock**: `downloadInFlightRef` prevents concurrent downloads
5. **Button States**: Explicit `disabled={!config?.allow_download}` prevents accidental clicks

## Testing Checklist

- [x] Raw text edits save on Apply (without mode toggle)
- [x] Structured edits save on Apply
- [x] Double-click Apply doesn't cause double-submit
- [x] Global Apply and header Apply both work
- [x] Apply ordering is deterministic (K_POINTS first, then params)
- [x] Raw pane is always expanded by default
- [x] Copy buttons work for raw text and debug JSON
- [x] Download buttons disabled when allow_download is OFF
- [x] Concurrent downloads prevented
- [x] Corrupted tar files handled gracefully

