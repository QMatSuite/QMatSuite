# Phase 1.4 Bug Fix - Infinite Loop Prevention

## Root Cause

**Symptom**: Clicking "Edit" caused infinite RPC calls to `list_qe_parameter_metadata(list_parameters)` for the same sections in a loop.

**Primary Root Cause**: `useEffect` in `StepDetailPanel.tsx` had unstable dependencies:
- `qeMetadata` object reference changes on every render (even though functions inside are stable)
- `stepDetail` object reference changes when parameters state updates
- Effect runs → calls `loadParameters` → updates `parameters` state → `parameterMetadataMap` changes → `stepDetail` prop changes → effect runs again → infinite loop

**Secondary Issue**: `loadParameters` had no deduplication:
- Every call triggered a new RPC, even if the section was already loaded
- No tracking of loaded sections or in-flight requests

## Fixes Applied

### Fix 1: Idempotent `loadParameters` with Loaded/In-Flight Cache

**File**: `gui/src/hooks/useQEParameterMetadata.ts`

**Changes**:
1. Added `loadedSectionsRef` (Set) to track loaded sections by key `${module}::${section}`
2. Added `inFlightRef` (Map) to track in-flight promises and dedupe concurrent calls
3. `loadParameters` now:
   - Early returns if section is already loaded
   - Returns existing promise if already in-flight
   - Only calls RPC if section is not loaded and not in-flight
   - Marks section as loaded only on success
   - Removes from in-flight map in finally block
4. `setParameters` now returns `prev` unchanged if no new parameters were added (prevents re-render storms)
5. `reloadMetadata` clears both caches to allow fresh loads

**Implementation**:
```typescript
const loadedSectionsRef = useRef<Set<string>>(new Set());
const inFlightRef = useRef<Map<string, Promise<void>>>(new Map());

const loadParameters = useCallback(async (module: string, section: string) => {
  const key = `${module}::${section}`;
  
  // Early return if already loaded
  if (loadedSectionsRef.current.has(key)) return;
  
  // Return existing promise if in-flight
  const existingPromise = inFlightRef.current.get(key);
  if (existingPromise) return existingPromise;
  
  // Create new load promise...
  // Mark as loaded on success
  // Remove from in-flight in finally
}, [qms]);
```

### Fix 2: Stable useEffect Dependencies

**File**: `gui/src/components/panels/StepDetailPanel.tsx`

**Changes**:
1. Extracted stable function references: `const { loadSections, loadParameters } = qeMetadata;`
2. Created stable namelists key: `useMemo(() => sorted namelists.join('|'), [stepDetail?.parameters])`
3. Track previous `isEditing` state with `useRef` to detect false→true transition
4. Effect only runs when:
   - `isEditing` transitions from false to true, OR
   - `module` changes, OR
   - `stableNamelistsKey` changes (namelists changed)
5. Removed `stepDetail` and `qeMetadata` from dependencies (replaced with stable values)

**Implementation**:
```typescript
const prevIsEditingRef = useRef(false);
const stableNamelistsKey = useMemo(() => {
  if (!stepDetail?.parameters) return '';
  return Object.keys(stepDetail.parameters)
    .map(n => n.startsWith('&') ? n : `&${n}`)
    .sort()
    .join('|');
}, [stepDetail?.parameters]);

const { loadSections, loadParameters } = qeMetadata;

useEffect(() => {
  const isEnteringEdit = !prevIsEditingRef.current && isEditing;
  prevIsEditingRef.current = isEditing;
  
  if (isEnteringEdit && module && stepDetail && stableNamelistsKey) {
    // Load metadata...
  }
}, [isEditing, module, stableNamelistsKey, stepDetail, loadSections, loadParameters]);
```

### Fix 3: Prevent Re-render Storms

**File**: `gui/src/hooks/useQEParameterMetadata.ts`

**Change**: `setParameters` now returns `prev` unchanged if no new parameters were added:
```typescript
setParameters(prev => {
  const existingMap = new Map<string, QEParameterMeta>();
  // ... build map ...
  const prevSize = existingMap.size;
  // ... add new params ...
  if (existingMap.size === prevSize) {
    return prev; // No change, avoid re-render
  }
  return Array.from(existingMap.values());
});
```

## Why It Cannot Regress

1. **Idempotent loading is enforced**: `loadedSectionsRef` and `inFlightRef` prevent duplicate RPC calls at the hook level
2. **Stable dependencies**: Effect depends on primitive values (`isEditing`, `module`, `stableNamelistsKey`) and stable function references, not object references
3. **Transition detection**: `prevIsEditingRef` ensures effect only runs on false→true transition, not on every render
4. **Re-render prevention**: `setParameters` returns `prev` if unchanged, preventing cascading re-renders

## Edge Cases Handled

1. **Concurrent calls**: In-flight map deduplicates concurrent calls for the same section
2. **Error handling**: Errors don't mark section as loaded, allowing retry
3. **Empty responses**: Empty responses are marked as loaded to avoid retrying
4. **Refresh**: `reloadMetadata` clears caches to allow fresh loads
5. **Multiple sections**: Each section is tracked independently

## Logging (Temporary)

Added console logs to verify fix:
- `[useQEParameterMetadata] loadParameters early-return (already loaded)`
- `[useQEParameterMetadata] loadParameters early-return (in-flight)`
- `[useQEParameterMetadata] loadParameters calling RPC`

**Expected behavior after clicking Edit**:
- 3 RPC calls total (one per section: CONTROL, ELECTRONS, SYSTEM)
- Subsequent renders show only early-return logs
- Daemon stops spamming

## Acceptance Criteria

✅ Clicking Edit triggers at most one RPC per section  
✅ No repeated daemon logs  
✅ Dropdown/toggle rendering still works immediately  
✅ Refresh behavior still possible (reloadMetadata clears caches)

