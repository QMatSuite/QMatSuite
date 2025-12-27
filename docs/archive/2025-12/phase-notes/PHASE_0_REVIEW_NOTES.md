# Phase 0 Review Notes - Step Parameter Editor Architecture

## 1. RPC Endpoints

### `list_qe_parameter_metadata`
- **Location**: `src/quantumvitas/daemon/server.py` line 715
- **Handler**: `_handle_list_qe_parameter_metadata()`
- **Operations**: `list_modules`, `list_sections`, `list_parameters`, `search`
- **Used by**: Resources view (`QEParameterBrowserPanel.tsx`), StepDetailPanel (via `useQEParameterMetadata` hook)

### `update_step_params`
- **Location**: `src/quantumvitas/daemon/server.py` line 2145
- **Handler**: `_handle_update_step_params()`
- **Service**: `src/quantumvitas/api.py` line 3199, `QVService.update_step_params()`
- **Payload**: `{project_root, calculation, step, parameters: Dict[str, Dict[str, Any]], cards?: Dict}`
- **ISSUE**: Line 3250 has type coercion `value = float(value)` for numeric params - **VIOLATES STRING-ONLY RULE**

### `get_step_detail`
- **Location**: `src/quantumvitas/daemon/server.py` line 2099
- **Handler**: `_handle_get_step_detail()`
- **Service**: `src/quantumvitas/api.py`, `QVService.get_step_detail()`
- **Returns**: `StepDetail` with `parameters`, `cards`, `species_overrides` fields

## 2. Step YAML Structure

### File Format
- **Location**: `src/quantumvitas/calculation/structure_steps.py` line 35
- **Class**: `StructureStepSpec`
- **Fields**:
  - `parameters: Dict[str, Dict[str, Any]]` - Namelist parameters (e.g., `{"SYSTEM": {"ecutwfc": 30.0}}`)
  - `cards: Dict[str, Dict[str, Any]]` - Card data (e.g., `{"K_POINTS": {"option": "automatic", "data": [[4,4,4,0,0,0]]}}`)
  - `species_overrides: Dict[str, Dict[str, Any]]` - Element-specific overrides

### Reading from YAML
- **Method**: `StructureStepSpec.from_yaml()` (line 147)
- **Process**: `yaml.safe_load()` → `from_dict()` → creates `StructureStepSpec` object
- **Current behavior**: YAML values are loaded as Python types (int, float, bool, str) by PyYAML

### Writing to YAML
- **Method**: `StructureStepSpec.to_dict()` (line 167) → `yaml.safe_dump()`
- **Location**: `src/quantumvitas/api.py` line 3274: `step.absolute_path.write_text(yaml.safe_dump(spec.to_dict(), sort_keys=False))`
- **Current behavior**: Python types are serialized by PyYAML (numbers stay as numbers, strings as strings)

### String-Only Violation
- **Location**: `src/quantumvitas/api.py` line 3247-3252
- **Code**: 
  ```python
  if key in ('ecutwfc', 'ecutrho', 'degauss', 'conv_thr'):
      if value is not None:
          try:
              value = float(value)  # VIOLATION: Coerces to float
  ```
- **Impact**: Numeric parameters are stored as Python floats in YAML, not strings

## 3. Card Parameters (K_POINTS, ATOMIC_SPECIES, etc.)

### Current Storage Format
- **Location**: `src/quantumvitas/calculation/importers.py` line 491, `_extract_cards()`
- **Format**: `cards["K_POINTS"] = {"option": str, "data": list}`
  - Example: `{"option": "automatic", "data": [[4, 4, 4, 0, 0, 0]]}`
- **Applied to QE input**: `src/quantumvitas/calculation/input_runner.py` line 505, `apply_card_overrides_to_qe_input()`

### K_POINTS Formatting
- **Parser**: `src/quantumvitas/io/parser/qe_parser.py` line 259, `_parse_k_points()`
- **Generator**: `src/quantumvitas/io/generator/qe_generator.py` line 46, `generate_card()`
- **Output format**: 
  ```
  K_POINTS {automatic}
    4 4 4 0 0 0
  ```

### User Requirement
- **K_POINTS should be stored as single raw string in YAML**
- **Current**: `cards["K_POINTS"] = {"option": "automatic", "data": [[4,4,4,0,0,0]]}`
- **Required**: `cards["K_POINTS"] = "K_POINTS {automatic}\n  4 4 4 0 0 0"` (or similar raw string)

## 4. Pseudopotentials

### Current Storage
- **Location**: `src/quantumvitas/calculation/structure_steps.py` line 51, `species_overrides: Dict[str, Dict[str, Any]]`
- **Format**: `{"Si": {"mass": 28.085, "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}}`
- **Applied**: `src/quantumvitas/calculation/input_runner.py` line 461, `apply_species_overrides_to_qe_input()`

### ATOMIC_SPECIES Card
- **Location**: `src/quantumvitas/io/structure_io.py` line 155-169
- **Format**: List of `[symbol, mass, pseudo_file]` rows
- **Storage**: Part of `cards["ATOMIC_SPECIES"]` or `species_overrides`

## 5. Key Files and Functions

### Backend (Python)
- `src/quantumvitas/api.py`:
  - `QVService.update_step_params()` (line 3199) - **NEEDS FIX: Remove float coercion**
  - `QVService.get_step_detail()` - Returns StepDetail from YAML
- `src/quantumvitas/calculation/structure_steps.py`:
  - `StructureStepSpec.from_yaml()` (line 147) - Loads step.yaml
  - `StructureStepSpec.to_dict()` (line 167) - Serializes to YAML
- `src/quantumvitas/calculation/importers.py`:
  - `_extract_cards()` (line 491) - Extracts cards from QEInput
- `src/quantumvitas/io/generator/qe_generator.py`:
  - `generate_card()` (line 46) - Formats card to QE input string
- `src/quantumvitas/io/parser/qe_parser.py`:
  - `_parse_k_points()` (line 259) - Parses K_POINTS from QE input

### Frontend (TypeScript/React)
- `gui/src/components/panels/StepDetailPanel.tsx` - Main step detail component
- `gui/src/components/step_parameters/ActiveParametersPanel.tsx` - Active params display
- `gui/src/components/step_parameters/AddParameterPalette.tsx` - Parameter search/add
- `gui/src/components/step_parameters/ParameterValueEditor.tsx` - Value editor (NEEDS FIX: String-only)
- `gui/src/hooks/useQEParameterMetadata.ts` - Shared metadata hook

## 6. Constraints and Gotchas

1. **Type Coercion Issue**: `update_step_params` coerces numeric params to float (line 3250) - must be removed
2. **YAML Serialization**: PyYAML preserves Python types - need to ensure all values are strings before `to_dict()`
3. **K_POINTS Format**: Currently structured (`option` + `data`), user wants raw string
4. **Card Application**: `apply_card_overrides_to_qe_input()` expects structured format - may need changes for raw string
5. **No QE Grammar in UI**: All parsing/formatting must be in Python, not TypeScript

## 7. Implementation Plan

### Phase 1: Fix String-Only + UX
1. Remove type coercion in `update_step_params`
2. Ensure all parameter values are strings in YAML
3. Move "+ Add parameter" to always-visible position
4. Add raw string editing for LOGICAL/ENUM
5. Rename "Reset" to "Unset"

### Phase 2: K_POINTS Common Card
1. Add Python parsing/formatting functions for K_POINTS
2. Add RPC endpoints for parse/format
3. Create UI component with structured form + raw fallback
4. Store K_POINTS as raw string in YAML

### Phase 3: PSEUDO Common Card
1. Create UI for pseudo_dir and per-element pseudopotentials
2. Keep string-only storage

