# QE Array Parameter Refactoring Summary

**Date**: After refactoring to store array parameters as base names with indexing metadata

## Summary

Successfully refactored `tools/extract_qe_parameters_v2.py` to store "family" array parameters (like `celldm(i), i=1,6`) exactly like v1, as a single base name (e.g., "celldm") with `indexing` metadata indicating the array structure.

## Key Changes

### 1. Created Shared Normalization Module

**File**: `tools/qe_parameter_normalization.py`

Provides shared functions for parameter name normalization:
- `normalize_param_name()`: Normalizes parameter names to match v1 style
- `extract_array_indexing_info()`: Detects and extracts indexing metadata for array parameters
- `get_base_param_name()`: Extracts base name from array notation

This ensures v2 uses the same parameter names as v1.

### 2. Updated Extractor Logic

**File**: `tools/extract_qe_parameters_v2.py`

**Changes**:
- Removed `expand_array_parameter()` function (no longer expands arrays into individual entries)
- Added `split_grouped_parameters()` function (still splits grouped params like "A,B,C")
- Updated `extract_parameter_metadata_from_table()` to:
  - Detect array parameters and store as base name with `indexing` metadata
  - Split grouped parameters (like "A,B,C,cosAB,cosAC,cosBC") into individual entries
  - Keep regular parameters unchanged
- Updated ToC parameter initialization to use base names
- Updated metadata extraction to preserve `indexing` field

### 3. Indexing Metadata Structure

For array parameters, the `indexing` field is added with the following structure:

```json
{
  "index_name": "i",
  "kind": "bounded" | "unbounded",
  "start": 1,
  "end": 6,  // null for unbounded
  "keyword_pattern": "celldm({i})"
}
```

**Bounded arrays** (e.g., `celldm(i), i=1,6`):
- `kind`: "bounded"
- `start`: 1
- `end`: 6
- `keyword_pattern`: "celldm({i})"

**Unbounded arrays** (e.g., `alpha_mix(niter)`):
- `kind`: "unbounded"
- `start`: 1
- `end`: null
- `keyword_pattern`: "alpha_mix({i})"

### 4. Updated Tests

**File**: `tests/unit/test_extract_qe_parameters_v2.py`

Added tests:
- `test_celldm_indexing_metadata()`: Verifies celldm has correct indexing metadata
- `test_parameter_names_match_v1()`: Verifies parameter names match v1 style (base names, not expanded)

## Results

### Parameter Name Matching

- **PW module**: 100% parameter name match (289/289 parameters)
- **All modules**: Parameter names match v1 style (base names, not expanded)
- **Comparison script**: Reports 0 parameter name differences (section name differences are expected due to normalization)

### Indexing Metadata

- **Total parameters with indexing**: 12
- **Bounded arrays**: 12
- **Unbounded arrays**: 0 (none detected yet, but detection logic is in place)

### Examples

**Bounded Array (celldm)**:
```json
{
  "&SYSTEM.celldm": {
    "namelist": "&SYSTEM",
    "name": "celldm",
    "type": "REAL",
    "default": null,
    "enum": null,
    "description": "Crystallographic constants - see the ibrav variable...",
    "indexing": {
      "index_name": "i",
      "kind": "bounded",
      "start": 1,
      "end": 6,
      "keyword_pattern": "celldm({i})"
    }
  }
}
```

**Grouped Parameters (A,B,C,cosAB,cosAC,cosBC)**:
Stored as 6 separate parameters:
- `&SYSTEM.A`
- `&SYSTEM.B`
- `&SYSTEM.C`
- `&SYSTEM.cosAB`
- `&SYSTEM.cosAC`
- `&SYSTEM.cosBC`

Each has full metadata (type, description, etc.) but no `indexing` field (not array parameters).

## All Parameters with Indexing

1. `bands.&BANDS.lsigma`: bounded (1 to 3)
2. `cp.&SYSTEM.celldm`: bounded (1 to 6)
3. `pp.&INPUTPP.kband`: bounded (1 to 2)
4. `pp.&INPUTPP.kpoint`: bounded (1 to 2)
5. `pp.&INPUTPP.spin_component`: bounded (1 to 2)
6. `pp.&PLOT.e1`: bounded (1 to 3)
7. `pp.&PLOT.x0`: bounded (1 to 3)
8. `pprism.&PLOT.e1`: bounded (1 to 3)
9. `pprism.&PLOT.x0`: bounded (1 to 3)
10. `pw.&ELECTRONS.efield_cart`: bounded (1 to 3)
11. `pw.&SYSTEM.celldm`: bounded (1 to 6)
12. `pw.&SYSTEM.fixed_magnetization`: bounded (1 to 3)

## Verification

- ✅ Parameter names match v1 style (base names, not expanded)
- ✅ `tools/compare_qe_parameter_maps.py` reports 0 parameter name differences
- ✅ Tests pass (including new indexing metadata tests)
- ✅ `qe_metadata.iter_params()` and `get_module_param_sections()` remain compatible
- ✅ Schema v2 structure preserved (existing fields unchanged for non-array parameters)

## Notes

- Unbounded array detection is implemented but conservative (requires strong evidence from description or index name pattern)
- Section name differences in comparison script are expected (normalized names like `&ALLELECTRONCARDS` vs `&A__E_______C`)
- Parameter names themselves match exactly between v1 and v2
