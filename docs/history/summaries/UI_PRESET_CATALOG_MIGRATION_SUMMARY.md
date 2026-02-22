# UI Preset Catalog Migration Summary

## Overview

Successfully migrated QMatSuite UI Presets Panel from hardcoded dimensions/options to a backend-driven catalog system. UI now derives all preset information from the backend variants registry, eliminating duplicate truth sources.

## Changes Made

### Part A — Backend RPC: `get_preset_catalog`

**File**: `src/qmatsuite/presets/catalog.py` (NEW)
- Created `get_preset_catalog()` function that generates catalog from variants registry
- Catalog includes:
  - Dimensions with labels, descriptions, order
  - Options with values and labels
  - Default values
  - Scope information (variant step types or variant details)

**File**: `src/qmatsuite/daemon/server.py`
- Added `_handle_get_preset_catalog()` RPC handler
- Updated `_handle_detect_presets()` to return `dimension_states` instead of `presets`
- Updated `_handle_apply_presets_to_calculation()` to return `dimension_states` instead of `presets`
- Updated `_handle_apply_presets_to_step()` to return `dimension_states` instead of `presets`

### Part B — UI: Catalog-Driven Rendering

**File**: `gui/src/hooks/usePresetCatalog.ts` (NEW)
- Created hook for fetching preset catalog from backend
- Handles loading, error states, and compatibility checks
- Shows clear error message if daemon is outdated (no fallback to hardcoded values)

**File**: `gui/src/components/presets/PresetSection.tsx` (REWRITTEN)
- Removed all hardcoded dimensions (Spin, SOC, Occupations, Precision)
- Removed all hardcoded options and labels
- Now renders dimensions from catalog (sorted by order)
- Each dimension row shows:
  - Label from catalog
  - Dropdown with options from catalog
  - Scope information ("Applies to: scf, nscf, ...")
- Generic `handleDimensionChange` replaces specific handlers
- Updated footer text: "Applies to applicable steps (preset variant scope)"

**File**: `gui/src/hooks/usePresets.ts`
- Updated `PresetState` to be generic `Record<string, string | 'Custom'>`
- Updated `applyPreset` to accept any dimension string
- Updated to use `dimension_states` from backend responses

**File**: `gui/src/types/qms.ts`
- Added `get_preset_catalog` RPC type definition
- Updated `PresetDetectionResult` to return `dimension_states`
- Updated `ApplyPresetsToCalcResult` to return `dimension_states`
- Updated `apply_presets_to_calculation` payload to accept `Record<string, string>`
- Marked legacy constants (`SPIN_OPTIONS`, `SOC_OPTIONS`, etc.) as `@deprecated`

## Key Features

### 1. Single Source of Truth
- All preset information comes from backend variants registry
- UI has zero hardcoded dimensions, options, or labels
- Catalog is generated automatically from variants (no manual sync needed)

### 2. Scope Information
- Each dimension shows which step types it applies to
- For precision (multiple variants), shows variant details
- Example: "Applies to: scf, nscf, relax" or "Applies to: scf, relax (not bands_pw)"

### 3. Backward Compatibility
- Old daemon detection: Shows clear error "Daemon is outdated: preset catalog not available"
- No fallback to hardcoded values (prevents duplicate truth)
- Legacy constants marked as deprecated but kept for compatibility

### 4. Generic Dimension Handling
- UI can handle any dimension without code changes
- Adding new dimensions (e.g., kpath) requires only backend changes
- UI automatically renders new dimensions from catalog

## Catalog Structure

```json
{
  "dimensions": [
    {
      "dimension": "magnetism",
      "label": "Magnetism",
      "description": "Spin/SOC settings",
      "order": 10,
      "options": [
        {"value": "nonmagnetic", "label": "Non-magnetic"},
        {"value": "collinear_lsda", "label": "Collinear (LSDA)"},
        {"value": "noncollinear", "label": "Noncollinear"},
        {"value": "noncollinear_soc", "label": "Noncollinear + SOC"}
      ],
      "default": "nonmagnetic",
      "scope": {
        "type": "variant_step_types",
        "step_types": ["scf", "nscf", "bands_pw", "relax", "vc-relax", "md", "vc-md"]
      }
    },
    {
      "dimension": "occupations_scheme",
      "label": "Occupations",
      "order": 20,
      "options": [...],
      "scope": {...}
    },
    {
      "dimension": "precision",
      "label": "Precision",
      "order": 30,
      "options": [...],
      "scope": {
        "type": "variants",
        "variants": [
          {"name": "PRECISION_PW_DEFAULT", "step_types": ["scf", "relax", ...], "notes": "mesh K_POINTS"},
          {"name": "PRECISION_PW_NSCF", "step_types": ["nscf"], "notes": "denser mesh"},
          {"name": "PRECISION_PW_BANDS_PW", "step_types": ["bands_pw"], "notes": "no K_POINTS (kpath preserved)"}
        ]
      }
    }
  ],
  "schema_version": 1
}
```

## Verification

### ✅ No Hardcoded Dimensions
- Removed all references to "spin", "soc" as dimension keys in UI code
- All dimensions come from catalog

### ✅ No Hardcoded Options
- Removed all hardcoded option lists
- All options come from catalog

### ✅ Scope Display
- Each dimension shows applicable step types
- Precision shows variant details

### ✅ Generic Apply
- UI sends `{dimension: option_value}` to backend
- Backend handles variant scope and step filtering

### ✅ Error Handling
- Catalog unavailable: Shows error (no fallback)
- Old daemon: Shows "Daemon is outdated" message
- Preset detection failure: Shows error

## Files Modified

### Backend
1. `src/qmatsuite/presets/catalog.py` (NEW)
2. `src/qmatsuite/daemon/server.py`

### Frontend
1. `gui/src/hooks/usePresetCatalog.ts` (NEW)
2. `gui/src/components/presets/PresetSection.tsx` (REWRITTEN)
3. `gui/src/hooks/usePresets.ts`
4. `gui/src/types/qms.ts`

## RPC Protocol Changes

### New RPC: `get_preset_catalog`
```typescript
payload: {}
result: {
  dimensions: Array<{
    dimension: string;
    label: string;
    description: string;
    order: number;
    options: Array<{value: string; label: string}>;
    default: string;
    scope: {...};
  }>;
  schema_version: number;
}
```

### Updated RPC: `detect_presets`
```typescript
// Before
result: { presets: { spin: ..., soc: ..., ... } }

// After
result: { dimension_states: { magnetism: ..., occupations_scheme: ..., precision: ... } }
```

### Updated RPC: `apply_presets_to_calculation`
```typescript
// Before
payload: { presets: { spin?: ..., soc?: ..., ... } }
result: { presets: {...} }

// After
payload: { presets: Record<string, string> }  // dimension -> option_value
result: { dimension_states: {...} }
```

## Testing Checklist

- [x] Catalog generation from variants registry
- [x] RPC handler for `get_preset_catalog`
- [x] UI fetches catalog on mount
- [x] UI renders dimensions from catalog
- [x] UI shows scope information
- [x] Apply works with generic dimension+option
- [x] Error handling for outdated daemon
- [x] No hardcoded dimensions/options in UI
- [x] Legacy constants marked as deprecated

## Future Work

1. Remove deprecated constants (`SPIN_OPTIONS`, `SOC_OPTIONS`, etc.) in next major version
2. Add UI tests for catalog-driven rendering
3. Consider adding dimension descriptions in tooltips
4. Add visual indicators for variant-specific behavior (e.g., precision variants)

