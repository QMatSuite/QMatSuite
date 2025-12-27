# Phase 1.2 Bug Fixes - Edit Mode Initialization & Display Normalization

## Root Causes

### BUG A: Edit Mode Not Immediately Rendering Enums/Bools

**Problem**: When clicking "Edit" on a step, enum/logical parameters were rendered as plain text inputs instead of dropdowns/toggles. They would only render correctly after clicking "Add Parameter" or after Apply/Edit cycle.

**Root Cause**:
- `ParameterValueEditor` used `useState(() => shouldUseRawMode)` for mode initialization
- This initializer only runs once when the component first mounts
- When edit mode is enabled (`disabled` changes from `true` to `false`), the component was already mounted, so the initializer didn't re-run
- The `useEffect` that synced mode had complex conditional logic that didn't always trigger correctly when metadata arrived async or when edit mode was toggled
- "Add Parameter" triggered a remount/re-render that happened to reset the mode correctly

**Fix**:
- Changed from `useState` with initializer to fully reactive derived mode
- Mode is now computed every render: `const useRawMode = userForcedRaw || shouldUseRawMode`
- `shouldUseRawMode` is a `useMemo` that re-computes whenever value/metadata changes
- Removed complex `useEffect` that tried to sync state
- Only `userForcedRaw` is state (to preserve user preference during edit session)
- Mode derivation is now pure and always correct, regardless of when metadata arrives or when edit mode is enabled

**Files Changed**:
- `gui/src/components/step_parameters/ParameterValueEditor.tsx`

### BUG B: Dropdown Showing Quoted Strings

**Problem**: For CHARACTER enum parameters, YAML correctly stores quoted values like `"'scf'"`, but the dropdown UI showed the quotes to users (e.g., `'scf'` instead of `scf`).

**Root Cause**:
- Dropdown options displayed raw enum values from metadata
- For CHARACTER enums, metadata values might be stored with quotes or the YAML value has quotes
- No normalization was applied to display labels

**Fix**:
- Use `normalizeQeScalar()` utility to normalize display labels
- Option labels are normalized (quotes stripped): `const displayLabel = normalizeQeScalar(optStr)`
- Option values remain unchanged (for correct storage round-trip)
- Selected value display is automatically normalized because browser shows the option's text content

**Files Changed**:
- `gui/src/components/step_parameters/ParameterValueEditor.tsx`

## Implementation Details

### Mode Derivation (BUG A Fix)

**Before**:
```typescript
const [useRawMode, setUseRawMode] = useState(() => shouldUseRawMode);
// Complex useEffect to sync state...
```

**After**:
```typescript
const shouldUseRawMode = useMemo(() => {
  if (!stringValue) return false;
  if (hasEnum && !valueMatchesEnum) return true;
  if (isLogical && !valueMatchesLogical) return true;
  return false;
}, [stringValue, hasEnum, valueMatchesEnum, isLogical, valueMatchesLogical]);

const useRawMode = userForcedRaw || shouldUseRawMode; // Fully reactive
```

### Display Normalization (BUG B Fix)

**Before**:
```typescript
<option key={optStr} value={optStr}>{optStr}</option>
```

**After**:
```typescript
const displayLabel = normalizeQeScalar(optStr);
<option key={optStr} value={optStr}>{displayLabel}</option>
```

## Edge Cases Handled

1. **Async Metadata Arrival**: Mode re-evaluates automatically when `hasEnum`/`isLogical` changes
2. **Edit Mode Toggle**: Mode is correct immediately when `disabled` changes from `true` to `false`
3. **Value Changes**: Mode updates when value changes externally
4. **User Preference**: `userForcedRaw` preserves manual raw mode toggle during edit session
5. **Quote Preservation**: Storage remains unchanged (quoted for CHARACTER enums), only display is normalized

## Acceptance Criteria

✅ **BUG A**: Clicking Edit immediately renders enum/logical params as dropdowns/toggles  
✅ **BUG A**: No need to click "Add Parameter" to activate enum rendering  
✅ **BUG B**: Dropdown shows normalized labels (scf not 'scf')  
✅ **BUG B**: YAML still stores quoted values correctly ('scf')  
✅ **Both**: Raw mode fallback still works for custom values  
✅ **Both**: String-only storage maintained (no type coercion)

## Testing Notes

- Manual test: Open step detail, click Edit, verify enum params show dropdowns immediately
- Manual test: Verify dropdown labels don't show quotes
- Manual test: Verify YAML storage still has quotes for CHARACTER enums
- Manual test: Verify raw mode toggle still works

