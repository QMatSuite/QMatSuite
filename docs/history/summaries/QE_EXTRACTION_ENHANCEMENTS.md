# QE Parameter Extraction Enhancements

This document summarizes the enhancements made to extract richer metadata from QE HTML documentation.

**Date**: After implementing array parameter expansion and card metadata extraction

## Enhancements Implemented

### 1. Array Parameter Expansion

**Problem**: Parameters like `celldm(i), i=1,6` and grouped parameters like `A,B,C,cosAB,cosAC,cosBC` were documented as single entries but represent multiple parameters.

**Solution**: Added `expand_array_parameter()` function that:
- Expands array notation: `celldm(i), i=1,6` → `celldm(1)`, `celldm(2)`, ..., `celldm(6)`
- Splits grouped parameters: `A,B,C,cosAB,cosAC,cosBC` → `A`, `B`, `C`, `cosAB`, `cosAC`, `cosBC`
- Handles comma-separated lists: `nr1,nr2,nr3` → `nr1`, `nr2`, `nr3`

**Results**:
- All 6 `celldm` parameters now extracted individually with full metadata
- All 6 crystallographic constants (`A`, `B`, `C`, `cosAB`, `cosAC`, `cosBC`) now extracted individually
- Other grouped parameters (like `nr1,nr2,nr3`) properly split

### 2. Card-Level Metadata Extraction

**Problem**: Card sections like `K_POINTS` have metadata (options, default, description) that wasn't being extracted.

**Solution**: Added `extract_card_metadata()` function that:
- Finds "Card: NAME { option1 | option2 | ... }" patterns
- Extracts available options/enum values
- Extracts default value from "Default:" patterns
- Extracts description from following text

**Results**:
- `K_POINTS`: Found 8 options (tpiba, automatic, crystal, gamma, tpiba_b, crystal_b, tpiba_c, crystal_c)
- `ADDITIONAL_K_POINTS`: Found 6 options
- `CELL_PARAMETERS`: Found 3 options
- `ATOMIC_VELOCITIES`: Found 1 option
- `SOLVENTS`: Found 3 options

### 3. Card Parameter Metadata Extraction

**Problem**: Parameters within cards (like `nks` in `K_POINTS`) have metadata that wasn't being extracted.

**Solution**: Added `extract_card_parameter_metadata()` function that:
- Searches for parameter names within card sections
- Extracts metadata from tables or definition lists
- Provides type, description for card parameters

**Results**:
- Card parameters now have metadata where available
- Improved coverage for parameters like `nks`, `nq`, etc. within cards

## Statistics

After regeneration with enhancements:

- **Total parameters**: Increased from 1069 to 1154 (across all 22 modules) - **+85 parameters**
- **Parameters with metadata**: 85% coverage (988/1154) - **up from 73%**
- **Expanded array parameters**: 56 parameters now properly expanded across all modules
  - PW: celldm(1-6), efield_cart(1-3), fixed_magnetization(1-3), A/B/C/cosAB/cosAC/cosBC
  - Other modules: alpha_mix(niter), kpoint(1-2), kband(1-2), spin_component(1-2), lsigma(1-3), q(1-3), etc.
- **Cards with metadata**: 8 cards across modules now have full metadata
  - PW: K_POINTS (8 options), ADDITIONAL_K_POINTS (6 options), CELL_PARAMETERS (3 options), ATOMIC_VELOCITIES (1 option), SOLVENTS (3 options)
  - Other modules: K_POINTS (band_interpolation), CELL_PARAMETERS (cp), REF_CELL_PARAMETERS (cp)
- **Card parameters with metadata**: 45+ card parameters now have metadata (up from 0)
  - Before: 0 card parameters had metadata
  - After: 45 card parameters have type and description (16 in K_POINTS alone)

## Examples of Extracted Metadata

### Array Parameters

**Before**: Single entry `celldm(i), i=1,6`
**After**: 6 separate parameters:
- `&SYSTEM.celldm(1)`: REAL, description about lattice parameter "a"
- `&SYSTEM.celldm(2)`: REAL, description about b/a ratio
- `&SYSTEM.celldm(3)`: REAL, description about c/a ratio
- `&SYSTEM.celldm(4)`: REAL, description about cos(gamma)
- `&SYSTEM.celldm(5)`: REAL, description about cos(beta)
- `&SYSTEM.celldm(6)`: REAL, description about cos(alpha)

**Before**: Single entry `A,B,C,cosAB,cosAC,cosBC`
**After**: 6 separate parameters:
- `&SYSTEM.A`: REAL, description about lattice parameter "a" in Angstrom
- `&SYSTEM.B`: REAL, description about lattice parameter "b" in Angstrom
- `&SYSTEM.C`: REAL, description about lattice parameter "c" in Angstrom
- `&SYSTEM.cosAB`: REAL, description about cosine of angle between a and b
- `&SYSTEM.cosAC`: REAL, description about cosine of angle between a and c
- `&SYSTEM.cosBC`: REAL, description about cosine of angle between b and c

### Card Metadata

**K_POINTS card**:
- **Type**: CHARACTER
- **Default**: "tpiba"
- **Enum**: ["tpiba", "automatic", "crystal", "gamma", "tpiba_b", "crystal_b", "tpiba_c", "crystal_c"]
- **Description**: Detailed explanation of each option

**ADDITIONAL_K_POINTS card**:
- **Type**: CHARACTER
- **Enum**: [6 options found]
- **Description**: [extracted]

## Technical Details

### Parameter Name Handling

- Array parameters are stored with parentheses: `celldm(1)`, `celldm(2)`, etc.
- JSON keys use safe format: `celldm_1`, `celldm_2` (parentheses replaced with underscores)
- Original parameter name preserved in `name` field

### Card Metadata Storage

Card metadata is stored in a separate `card_metadata` field in the module data:
```json
{
  "modules": {
    "pw": {
      "parameters": {...},
      "card_metadata": {
        "K_POINTS": {
          "name": "K_POINTS",
          "type": "CHARACTER",
          "default": "tpiba",
          "enum": ["tpiba", "automatic", ...],
          "description": "..."
        }
      }
    }
  }
}
```

## Future Enhancements

1. **Better card parameter extraction**: Improve detection of parameters within card sections
2. **Array parameter handling for variable-size arrays**: Handle cases like `angle1(i), i=1,ntyp` where size depends on another parameter
3. **Cross-references**: Extract "See:" references and link related parameters
4. **Deprecation markers**: Detect and mark deprecated parameters
