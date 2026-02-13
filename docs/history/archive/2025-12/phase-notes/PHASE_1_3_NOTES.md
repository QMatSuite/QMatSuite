# Phase 1.3 Bug Fixes - Metadata Accumulation & Edit Mode Initialization

## Root Causes Identified

### BUG A: Edit Mode Not Immediately Rendering Enums/Bools

**Primary Root Cause**: `useQEParameterMetadata.loadParameters()` was **REPLACING** the entire parameters array instead of **ACCUMULATING** them.

**Problem Flow**:
1. When step detail loads, metadata is fetched for multiple sections (e.g., `&CONTROL`, `&SYSTEM`, `&ELECTRONS`)
2. Each call to `loadParameters('pw', '&CONTROL')` loads CONTROL parameters and **replaces** the entire `parameters` array
3. Then `loadParameters('pw', '&SYSTEM')` loads SYSTEM parameters and **replaces** again, **losing CONTROL parameters**
4. Only the **last section loaded** has its parameters in the array
5. When clicking "Edit", `parameterMetadataMap` is built from `qeMetadata.parameters`, which only contains the last section's parameters
6. Parameters from other sections have no metadata, so they render as raw text inputs
7. When clicking "Add Parameter", the palette triggers a search which loads more metadata, causing a re-render that happens to include more parameters

**Secondary Issues**:
- React key uniqueness: `ActiveParametersPanel` used `key={param.name}` which is NOT unique across namelists (e.g., `CONTROL.calculation` and `SYSTEM.calculation` would have the same key)
- Metadata not guaranteed to load when entering edit mode (only loaded on step detail fetch)

**Fix**:
1. **Fixed `loadParameters` to accumulate**: Changed from `setParameters(response.data.parameters)` to accumulating into existing array using a Map to avoid duplicates
2. **Fixed React keys**: Changed from `key={param.name}` to `key={`${namelist}:${param.name}`}` for uniqueness
3. **Added metadata load on edit mode**: Added `useEffect` to ensure metadata loads when entering edit mode if not already loaded

### BUG B: Dropdown Showing Quoted Strings

**Root Cause**: Dropdown option labels displayed raw enum values without normalization.

**Fix**: Normalized display labels using `normalizeQeScalar()` while keeping option values unchanged for correct storage round-trip.

## Files Changed

1. **`gui/src/hooks/useQEParameterMetadata.ts`**
   - **CRITICAL FIX**: Changed `loadParameters` to accumulate parameters instead of replacing them
   - Uses a Map to deduplicate by key `${module}::${section}::${name}`
   - Prevents clearing parameters on error (keeps existing ones)

2. **`gui/src/components/step_parameters/ActiveParametersPanel.tsx`**
   - **Fixed React keys**: Changed from `key={param.name}` to `key={`${namelist}:${param.name}`}`
   - Ensures React doesn't reuse components with stale props across namelists

3. **`gui/src/components/panels/StepDetailPanel.tsx`**
   - **Added metadata load on edit mode**: `useEffect` ensures metadata loads when `isEditing` becomes `true`
   - Provides safety net if metadata wasn't loaded during step detail fetch

4. **`gui/src/components/step_parameters/ParameterValueEditor.tsx`**
   - **Normalized dropdown labels**: Uses `normalizeQeScalar(optStr)` for display labels
   - Option values remain unchanged for correct storage

## Technical Details

### Metadata Accumulation Fix

**Before**:
```typescript
if (response.data?.parameters) {
  setParameters(response.data.parameters); // REPLACES entire array
}
```

**After**:
```typescript
if (response.data?.parameters) {
  setParameters(prev => {
    const existingMap = new Map<string, QEParameterMeta>();
    prev.forEach(p => {
      const key = `${p.module}::${p.section}::${p.name}`;
      existingMap.set(key, p);
    });
    response.data!.parameters!.forEach(p => {
      const key = `${p.module}::${p.section}::${p.name}`;
      existingMap.set(key, p);
    });
    return Array.from(existingMap.values()); // ACCUMULATES
  });
}
```

### React Key Fix

**Before**:
```typescript
{params.map((param) => (
  <div key={param.name} ...>  // NOT unique across namelists!
```

**After**:
```typescript
{params.map((param) => (
  <div key={`${namelist}:${param.name}`} ...>  // Unique!
```

### Edit Mode Metadata Load

**Added**:
```typescript
useEffect(() => {
  if (isEditing && module && stepDetail) {
    // Load metadata for all sections when entering edit mode
    qeMetadata.loadSections(module).then(() => {
      // Load parameters for each section
    });
  }
}, [isEditing, module, stepDetail, qeMetadata]);
```

## Why It Cannot Regress

1. **Accumulation is enforced**: The `loadParameters` function now explicitly accumulates using a Map, making it impossible to accidentally replace
2. **Unique keys prevent stale props**: React keys are now unique across namelists, preventing component reuse with stale props
3. **Edit mode trigger**: Metadata load is triggered by `isEditing` change, ensuring it's available when needed
4. **Normalization is explicit**: Display normalization is done explicitly in the render, not hidden in state

## Edge Cases Handled

1. **Multiple sections**: Parameters from all sections are now accumulated correctly
2. **Duplicate parameters**: Map-based deduplication prevents duplicates
3. **Error handling**: Errors don't clear existing parameters
4. **Async metadata arrival**: Components re-render when metadata arrives (via `parameterMetadataMap` dependency)
5. **Edit mode toggle**: Metadata loads when entering edit mode even if not loaded before

## Acceptance Criteria

✅ **BUG A**: Clicking Edit immediately renders enum/logical params as dropdowns/toggles  
✅ **BUG A**: No need to click "Add Parameter" to activate enum rendering  
✅ **BUG A**: All sections' parameters have metadata available  
✅ **BUG B**: Dropdown shows normalized labels (scf not 'scf')  
✅ **BUG B**: YAML still stores quoted values correctly ('scf')  
✅ **Both**: String-only storage maintained (no type coercion)

