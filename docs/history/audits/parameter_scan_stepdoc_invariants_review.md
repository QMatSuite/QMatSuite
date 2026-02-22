# Parameter Scan StepDoc Invariants Review

**Date**: 2025-01-XX  
**Status**: READ-ONLY REVIEW (NO CODE CHANGES)  
**Purpose**: Re-evaluate StepDoc/YamlDoc mutation semantics for Parameter Scan feature

---

## Executive Summary

The current implementation attempts to represent ScanRef as a dict leaf `{scan_ref: "scan001"}` in parameter values, which violates YamlDoc's core invariant: **leaf values must be scalar or simple list, not dict**. While a workaround was added (`_is_scanref_leaf_dict()`), this creates a fragile exception that breaks the clean separation between "leaf replacement" (`set()`) and "subtree update" (`apply_patch()`).

Additionally, a UI persistence bug causes only the initial value to be saved in `parameter_scan.scan001.values`, losing user-entered lists.

**Recommendation**: Adopt **Option 1 (Token String)** representation: `"@scan:scan001"` as a string value. This preserves StepDoc invariants, avoids dict-recursion traps, and maintains single-source-of-truth semantics.

---

## A) StepDoc / YamlDoc Mutation Semantics

### A1) How `apply_patch()` Works

**File**: `src/qmatsuite/core/yamldoc.py:364-406`

```python
def apply_patch(self, patch: dict, base_path: PathType = ()) -> None:
    """Apply a nested patch dict.
    
    Recursively walks patch to leaves:
    - None values trigger delete (Delete Semantics A)
    - Dict values recurse deeper
    - Other values trigger set
    """
    self._apply_patch_recursive(patch, list(base_path))

def _apply_patch_recursive(self, patch: dict, current_path: list[str]) -> None:
    for key, value in patch.items():
        path = current_path + [key]
        
        if value is None:
            self.delete(path)
        elif isinstance(value, dict) and self._is_scanref_leaf_dict(value):
            # ScanRef dict: treat as leaf replacement (do not recurse)
            self.set(path, value)
        elif isinstance(value, dict):
            # Recurse into nested dict
            self._apply_patch_recursive(value, path)
        else:
            # Set leaf value
            self.set(path, value)
```

**Key Behavior**:
- **Dict values trigger recursion** by default (line 401-403)
- **Exception**: ScanRef dicts `{scan_ref: "id"}` are detected and treated as leaf replacements (line 397-400)
- **Non-dict values** (scalars, lists) trigger `set()` directly (line 404-406)

### A2) `set()` Method and Leaf Replacement

**File**: `src/qmatsuite/core/yamldoc.py:304-339`

```python
def set(self, path: PathType, value: Any) -> None:
    """Set leaf value at path.
    
    - Creates intermediate dicts as needed
    - Deep copies list values to prevent reference leakage
    - Setting to None is allowed (explicit null value)
    - Setting a dict is FORBIDDEN (use apply_patch for subtree updates)
    """
    # Reject dict values - use apply_patch for subtree updates
    # Exception: ScanRef dicts ({scan_ref: "id"}) are allowed as leaf replacements
    if isinstance(value, dict) and not self._is_scanref_leaf_dict(value):
        raise YamlDocError(
            f"Cannot set() a dict at path '{'.'.join(path)}'. "
            "Use apply_patch() for subtree updates."
        )
    
    parent, key = self._navigate_to_parent(path, create=True)
    parent[key] = value
```

**Key Behavior**:
- **Dict values are rejected** by default (line 328-332)
- **Exception**: ScanRef dicts are allowed (line 328)
- Uses `_navigate_to_parent()` to find/create parent dict and set value directly

### A3) The Exact Error: "Path component X is not a dict"

**File**: `src/qmatsuite/core/yamldoc.py:108-149`

```python
def _navigate_to_parent(self, path: PathType, *, create: bool = False) -> tuple[dict, str]:
    """Navigate to parent dict of the final path component."""
    current = self._data
    for i, key in enumerate(path[:-1]):
        if key not in current:
            if create:
                current[key] = {}
            else:
                raise PathNotFoundError(...)
        
        next_val = current[key]
        if not isinstance(next_val, dict):
            raise YamlDocError(
                f"Path component '{key}' is not a dict at {'.'.join(path[:i+1])}"
            )
        current = next_val
    
    return current, path[-1]
```

**Error Condition**:
- When `apply_patch()` recurses into a dict value (line 401-403 in `_apply_patch_recursive`)
- But the existing value at that path is **not a dict** (e.g., a scalar like `320`)
- `_navigate_to_parent()` tries to access `current[key]` and finds a scalar
- Raises: `YamlDocError: Path component 'ecutrho' is not a dict at parameters.SYSTEM.ecutrho`

**Root Cause**:
The patch structure `{"parameters": {"SYSTEM": {"ecutrho": {"scan_ref": "scan001"}}}}` causes `apply_patch()` to:
1. Recurse into `{"SYSTEM": {"ecutrho": {...}}}` (line 401-403)
2. Try to recurse into `{"ecutrho": {"scan_ref": "scan001"}}`
3. But `ecutrho` is currently a scalar (`320`), not a dict
4. `_navigate_to_parent(["parameters", "SYSTEM", "ecutrho"])` fails at `SYSTEM` level because `ecutrho` is not a dict

**Note**: The current fix (line 397-400) catches ScanRef dicts **before** recursion, but this is fragile and breaks the clean separation of concerns.

### A4) How `update_step_params()` Uses Patches

**File**: `src/qmatsuite/api.py:4540-4601`

```python
def update_step_params(...):
    step_doc = StepDoc.load(step.absolute_path)
    
    param_patch = {}
    for namelist, params in parameters.items():
        namelist_upper = namelist.upper()
        param_patch[namelist_upper] = {}
        
        for key, value in params.items():
            if value is None:
                param_patch[namelist_upper][key] = None  # Delete
            elif isinstance(value, dict) and "scan_ref" in value:
                # ScanRef dict: store as-is (no validation/parsing)
                param_patch[namelist_upper][key] = value
            else:
                # Validate and parse typed value
                param_patch[namelist_upper][key] = typed_value
    
    # Apply parameter patch
    if param_patch:
        step_doc.apply_patch({"parameters": param_patch})
    
    # Update parameter_scan if provided
    if parameter_scan is not None:
        step_doc.apply_patch({"parameter_scan": parameter_scan})
```

**Patch Structure from GUI**:
```python
{
    "parameters": {
        "SYSTEM": {
            "ecutrho": {"scan_ref": "scan001"}  # Dict leaf!
        }
    },
    "parameter_scan": {
        "scan001": {"values": [320, 330, 340]}
    }
}
```

**Problem**: The nested structure `{"SYSTEM": {"ecutrho": {...}}}` causes `apply_patch()` to recurse, but `ecutrho` is a scalar, not a dict.

**What Would Be Required for Safe Leaf Replacement**:
1. **Option A**: Use `set()` directly for ScanRef values (bypass `apply_patch()`)
   - Requires detecting ScanRef in `update_step_params()` and calling `step_doc.set(["parameters", "SYSTEM", "ecutrho"], {"scan_ref": "scan001"})`
   - **Problem**: Breaks the unified patch API; requires special-casing

2. **Option B**: Delete old value first, then set new value
   - `step_doc.delete(["parameters", "SYSTEM", "ecutrho"])`
   - `step_doc.set(["parameters", "SYSTEM", "ecutrho"], {"scan_ref": "scan001"})`
   - **Problem**: Not atomic; intermediate state exists

3. **Option C**: Use string representation (recommended)
   - `param_patch[namelist_upper][key] = "@scan:scan001"` (string, not dict)
   - `apply_patch()` treats it as a scalar leaf → calls `set()` directly
   - **Advantage**: No special-casing, preserves invariants

---

## B) Existing "Complex Parameter" Precedent: K_POINTS Editing

### B1) How K_POINTS is Represented

**File**: `src/qmatsuite/api.py:4760-4768`

```python
def set_common_card(...):
    # Convert view model to raw text
    raw = format_k_points(kp_vm)
    
    # Convert raw text to card data dict
    card_data = k_points_to_card_data(raw)
    # Returns: {"option": "automatic", "data": [[8, 8, 8, 0, 0, 0]]}
    
    # Update via StepDoc
    step_doc = StepDoc.load(step.absolute_path)
    step_doc.set(["cards", "K_POINTS"], card_data)  # Direct set(), not apply_patch()
    save_step_doc(step_doc, step.absolute_path)
```

**Storage in step.yaml**:
```yaml
cards:
  K_POINTS:
    option: "automatic"
    data: [[8, 8, 8, 0, 0, 0]]
```

### B2) How K_POINTS is Updated

**Key Finding**: K_POINTS uses **`set()` directly**, not `apply_patch()`.

**File**: `src/qmatsuite/api.py:4767`
```python
step_doc.set(["cards", "K_POINTS"], card_data)
```

**Why This Works**:
- `card_data` is a **dict** (`{"option": "...", "data": [...]}`)
- But `cards.K_POINTS` is **expected to be a dict** (card structure)
- `set()` allows setting a dict at a path where the parent (`cards`) is a dict
- The **entire card** is replaced atomically

**Difference from Parameter Scan**:
- K_POINTS: Replacing a dict with a dict (same type)
- ScanRef: Replacing a scalar with a dict (type mismatch)

### B3) Lesson: Allowed Leaf Shapes

**Current Stable Patterns**:
1. **Scalar leaf**: `parameters.SYSTEM.ecutwfc = 40` (number/string/bool)
2. **Simple list leaf**: `parameters.SYSTEM.kpoints = [4, 4, 4]` (list of scalars)
3. **Dict leaf (cards only)**: `cards.K_POINTS = {"option": "...", "data": [...]}` (entire card replaced)

**Unstable Pattern**:
- **Dict leaf in parameters**: `parameters.SYSTEM.ecutrho = {"scan_ref": "scan001"}` (breaks invariants)

**Conclusion**: StepDoc/YamlDoc design assumes **parameters are always scalar or simple list**. Cards are a special case where the entire card is a dict structure, but parameters are not.

---

## C) ScanRef Representation Options

### Option 1: Token String (RECOMMENDED)

**Representation**:
```yaml
parameters:
  SYSTEM:
    ecutrho: "@scan:scan001"  # String, not dict
parameter_scan:
  scan001:
    values: [320, 330, 340]
```

**Pros**:
- ✅ Preserves StepDoc invariant: leaf values are scalar/list, not dict
- ✅ No special-casing in `apply_patch()` or `set()`
- ✅ Works with existing type validation (string is valid for any parameter)
- ✅ Single source of truth: param value is the token, scan def is separate
- ✅ Easy to detect: `value.startswith("@scan:")`
- ✅ Easy to extract: `value.split(":", 2)[1]` → `"scan001"`

**Cons**:
- ⚠️ Requires string parsing (but simple: `@scan:` prefix)
- ⚠️ UI must handle token string display (show as "Scan: scan001" or similar)
- ⚠️ Type metadata may show "string" instead of actual type (minor UX issue)

**Preset Inference**:
- Token string `"@scan:scan001"` will not match any preset pattern → naturally returns `None` (custom)
- No special logic needed

**Runner Scan Expansion**:
- Collect scan dims: find all params where `value.startswith("@scan:")`
- Extract scan_id: `value.split(":", 2)[1]`
- Look up `parameter_scan[scan_id].values`
- **No change needed** to existing scan expansion logic

**Single-Representation Invariant**:
- ✅ Param value is **only** the token string (no concrete value stored)
- ✅ Scan def is **only** in `parameter_scan` section
- ✅ No stale concrete value possible

### Option 2: Separate Mapping (Top-Level `scan_refs`)

**Representation**:
```yaml
parameters:
  SYSTEM:
    ecutrho: null  # Unset, or could be first value
scan_refs:
  "parameters.SYSTEM.ecutrho": "scan001"  # Path -> scan_id mapping
parameter_scan:
  scan001:
    values: [320, 330, 340]
```

**Pros**:
- ✅ Parameters remain scalar/list only
- ✅ Clear separation: scan mapping is explicit

**Cons**:
- ❌ **Double-truth risk**: `ecutrho` could be `null` or first value, but `scan_refs` says it's scanned
- ❌ Path string format must be canonical (e.g., `"parameters.SYSTEM.ecutrho"`)
- ❌ More complex: need to maintain `scan_refs` dict in sync with parameters
- ❌ UI must query two sources: `parameters` and `scan_refs`
- ❌ Runner must merge `parameters` + `scan_refs` to build effective params

**Preset Inference**:
- Parameters look normal (scalar/null), but `scan_refs` indicates scanning
- Would need to check `scan_refs` during inference → more complex

**Runner Scan Expansion**:
- Must merge `parameters` + `scan_refs` to identify scanned params
- More complex: iterate `scan_refs`, resolve paths, look up values

**Single-Representation Invariant**:
- ⚠️ **Risk**: `ecutrho` could be `null` (unset) or first value (stale), while `scan_refs` says scanned
- Requires validation to ensure consistency

### Option 3: YAML Tag / Typed Scalar

**Representation**:
```yaml
parameters:
  SYSTEM:
    ecutrho: !!scan_ref scan001  # YAML tag
parameter_scan:
  scan001:
    values: [320, 330, 340]
```

**Pros**:
- ✅ Preserves scalar type (string)
- ✅ Type information embedded in YAML

**Cons**:
- ❌ **Parser support**: Most YAML parsers (including PyYAML) require custom tag handlers
- ❌ **Round-trip risk**: YAML dumps may not preserve tags (depends on dumper settings)
- ❌ **Complexity**: Need to register `!!scan_ref` constructor in PyYAML
- ❌ **Portability**: Other tools reading YAML may not understand the tag

**Preset Inference**:
- Tagged scalar will not match preset patterns → naturally returns `None` (custom)
- But need to handle tag during parsing

**Runner Scan Expansion**:
- Must detect tagged scalars during traversal
- More complex: need to check `isinstance(value, yaml.ScalarNode)` and check tag

**Single-Representation Invariant**:
- ✅ Param value is only the tagged scalar (no concrete value)
- ✅ Scan def is separate

---

## D) UI Persistence Bug: Why Only First Value is Saved

### D1) Scan Editor Input Flow

**File**: `gui/src/components/step_parameters/ScanValuesEditor.tsx:38-86`

```typescript
const handleChange = useCallback((newInput: string) => {
    setInputValue(newInput);
    setError(null);
    
    if (!newInput.trim()) {
        onChange([]);
        return;
    }
    
    try {
        const parsed = JSON.parse(newInput);
        
        if (!Array.isArray(parsed)) {
            // Single value: wrap in array
            if (parsed === null || typeof parsed === 'string' || ...) {
                onChange([parsed]);
            }
        } else {
            // Validate and call onChange
            onChange(parsed);  // ✅ This should work
        }
    } catch (e) {
        setError('Invalid JSON');
    }
}, [onChange]);
```

**Finding**: `ScanValuesEditor` correctly calls `onChange(parsed)` with the full array when user enters `[320, 330, 340]`.

### D2) How Values Flow to Backend

**File**: `gui/src/components/panels/StepDetailPanel.tsx:919-927`

```typescript
const handleScanValuesChange = useCallback((scanId: string, values: unknown[]) => {
    setEditedParameterScan(prev => {
        const updated = JSON.parse(JSON.stringify(prev));
        updated[scanId] = { values };  // ✅ Should store full array
        return updated;
    });
    setHasChanges(true);
}, []);
```

**Finding**: `handleScanValuesChange` correctly stores the full array in `editedParameterScan[scanId].values`.

### D3) What Gets Sent to Backend

**File**: `gui/src/components/panels/StepDetailPanel.tsx:755-761`

```typescript
const response = await window.qms.request<StepDetail>('update_step_params', {
    project_root: normalizedProjectRoot,
    calculation: calculationSelector,
    step: stepSelector,
    parameters: paramUpdates,
    parameter_scan: Object.keys(editedParameterScan).length > 0 ? editedParameterScan : undefined,
});
```

**Finding**: `editedParameterScan` is sent correctly to backend.

### D4) Backend Processing

**File**: `src/qmatsuite/api.py:4599-4601`

```python
# Update parameter_scan if provided
if parameter_scan is not None:
    step_doc.apply_patch({"parameter_scan": parameter_scan})
```

**Finding**: Backend applies `parameter_scan` patch correctly.

### D5) Hypothesis: Initial Value Initialization Bug

**File**: `gui/src/components/panels/StepDetailPanel.tsx:830-870`

```typescript
const handleScanToggle = useCallback((namelist: string, paramName: string, enable: boolean) => {
    if (enable) {
        // ... generate scan_id ...
        
        // Get current parameter value
        const currentValue = editedParams[namelist]?.[paramName];
        
        // Set parameter to scan_ref
        setEditedParams(prev => {
            const updated = JSON.parse(JSON.stringify(prev));
            if (!updated[namelist]) {
                updated[namelist] = {};
            }
            updated[namelist][paramName] = { scan_ref: scanId };
            return updated;
        });
        
        // Initialize parameter_scan values
        setEditedParameterScan(prev => {
            const updated = JSON.parse(JSON.stringify(prev));
            if (!updated[scanId]) {
                updated[scanId] = { values: [] };
            }
            // ✅ Initialize with current value if scalar/simple list
            if (currentValue !== null && currentValue !== undefined) {
                // Check if it's a leaf value (scalar or simple list)
                const isLeaf = currentValue === null ||
                    typeof currentValue === 'string' ||
                    typeof currentValue === 'number' ||
                    typeof currentValue === 'boolean' ||
                    (Array.isArray(currentValue) && currentValue.every(item =>
                        item === null || typeof item === 'string' ||
                        typeof item === 'number' || typeof item === 'boolean'
                    ));
                
                if (isLeaf) {
                    updated[scanId].values = [currentValue];  // ⚠️ Only first value!
                }
            }
            return updated;
        });
    }
    // ...
}, [editedParams, editedParameterScan, stepDetail]);
```

**Root Cause Identified**:
- When enabling scan, `handleScanToggle` initializes `values: [currentValue]` (line 862)
- This is correct for initialization
- **But**: If user edits the values in `ScanValuesEditor`, `handleScanValuesChange` should update `editedParameterScan[scanId].values`
- **However**: The initial value `[currentValue]` might be overwriting user edits if `handleScanToggle` is called again, or if state is reset

**Additional Hypothesis**: State Reset on Save

**File**: `gui/src/components/panels/StepDetailPanel.tsx:763-768`

```typescript
if (response.ok && response.data) {
    setStepDetail(response.data);
    // Initialize edited params from current values
    setEditedParams(JSON.parse(JSON.stringify(response.data.parameters)));
    // Initialize edited parameter_scan
    setEditedParameterScan(JSON.parse(JSON.stringify(response.data.parameter_scan || {})));
    // ...
}
```

**Potential Issue**: After save, `editedParameterScan` is reset from `response.data.parameter_scan`. If backend only saved `[320]` (first value), then UI will show `[320]` after reload.

**Likely Root Cause**: The backend `apply_patch({"parameter_scan": parameter_scan})` might be merging instead of replacing, or the initial value `[currentValue]` is being persisted instead of user-entered values.

**Recommendation**: Add logging to trace:
1. What `editedParameterScan` contains before save
2. What `parameter_scan` payload is sent to backend
3. What `step_doc.parameter_scan` contains after `apply_patch()`
4. What `response.data.parameter_scan` contains after save

---

## Recommendation

**Adopt Option 1: Token String Representation**

**Rationale**:
1. **Preserves StepDoc Invariants**: No dict leaves in parameters
2. **No Special-Casing**: Works with existing `apply_patch()` and `set()` logic
3. **Single Source of Truth**: Param value is token, scan def is separate
4. **Simple Detection**: `value.startswith("@scan:")` is trivial
5. **Minimal Changes**: Only need to:
   - Change UI to send `"@scan:scan001"` instead of `{scan_ref: "scan001"}`
   - Update scan expansion to parse token string
   - Update preset inference to treat token strings as custom (already works)

**Migration Path**:
1. Update `update_step_params()` to accept token strings (or convert `{scan_ref: "id"}` → `"@scan:id"`)
2. Update scan expansion to parse token strings
3. Update UI to display token strings as "Scan: scan001" instead of raw string
4. Remove `_is_scanref_leaf_dict()` workaround from YamlDoc

**Alternative Token Formats** (if `@scan:` conflicts):
- `"#scan:scan001"` (comment-like)
- `"scan_ref:scan001"` (explicit)
- `"__scan__scan001"` (double underscore prefix)

---

## Appendix: Code References

### Key Files
- `src/qmatsuite/core/yamldoc.py`: YamlDoc core mutation logic
- `src/qmatsuite/api.py:4540-4601`: `update_step_params()` implementation
- `gui/src/components/panels/StepDetailPanel.tsx:830-927`: Scan toggle and values change handlers
- `gui/src/components/step_parameters/ScanValuesEditor.tsx`: Scan values editor component
- `src/qmatsuite/api.py:4760-4768`: K_POINTS card update (precedent)

### Key Functions
- `YamlDoc.apply_patch()`: Main patch application entry point
- `YamlDoc._apply_patch_recursive()`: Recursive patch application
- `YamlDoc.set()`: Leaf value replacement
- `YamlDoc._navigate_to_parent()`: Path navigation (raises "not a dict" error)
- `YamlDoc._is_scanref_leaf_dict()`: Current workaround for ScanRef dicts
- `QMSService.update_step_params()`: Backend parameter update handler
- `StepDetailPanel.handleScanToggle()`: UI scan enable/disable handler
- `StepDetailPanel.handleScanValuesChange()`: UI scan values update handler

