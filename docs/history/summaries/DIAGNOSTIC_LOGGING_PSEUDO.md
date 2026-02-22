# Diagnostic Logging for Pseudo Issues

This document describes the diagnostic logging added to help debug pseudo-related issues, particularly for Wannier90 demos.

## Log Locations

### 1. `ensure_qe_pseudos` (src/qmatsuite/core/pseudo.py)

**When**: Before raising `ValueError` for "Pseudopotential not configured for element(s)"

**Log Tag**: `[PSEUDO_CONFIG_ERROR]`

**Information logged**:
- `qe_input_file`: Path to QE input file
- `project_pseudo_dir`: Project pseudo directory
- `system_pseudo_dir`: System pseudo directory
- `required_pps`: List of required pseudopotential filenames
- `required_elements`: List of element symbols extracted from ATOMIC_SPECIES
- `missing_placeholders`: Elements with missing/empty pseudos
- `project_pseudo_dir.exists()`: Whether project pseudo dir exists
- `calculation_path`: Path to calculation.yaml (if resolvable from qe_input_file path)
- `structure_path`: Path to structure file (if resolvable)
- `species_map_keys`: Keys from calculation's species_map
- `element_pseudopot_values`: Dict mapping element to pseudopot filename from species_map

**Example log**:
```
ERROR [qmatsuite.core.pseudo] [PSEUDO_CONFIG_ERROR] Pseudopotential not configured for element(s): Si
  qe_input_file=/path/to/project/calculations/calc/raw/scf.in
  project_pseudo_dir=/path/to/project/pseudo
  system_pseudo_dir=/path/to/repo/resources/pseudo
  required_pps=[]
  required_elements=['Si']
  missing_placeholders=['Si']
  project_pseudo_dir.exists()=True
  calculation_path=/path/to/project/calculations/calc/calculation.yaml
  structure_path=/path/to/project/structures/silicon.json
  species_map_keys=['Si']
  element_pseudopot_values={'Si': 'Si.pbe-n-van.UPF'}
```

### 2. `get_calculation_pseudo_mapping` (src/qmatsuite/api.py)

**When**: Entry and exit of function

**Log Tags**: `[GET_CALCULATION_PSEUDO_MAPPING] ENTRY` and `[GET_CALCULATION_PSEUDO_MAPPING] EXIT`

**Entry information**:
- `calculation_ulid`: Calculation ULID
- `project_root`: Project root path

**Exit information**:
- `final_pseudo_mapping`: Dict mapping element to pseudopot filename
- `mapping_missing`: List of elements with unresolved pseudos
- `warnings`: List of warnings

**During execution**:
- `resolved calculation path`: Path to calculation.yaml
- `structure_path`: Path to structure file
- `required_elements`: Elements from structure
- `species_map keys`: Keys from species_map
- `element_pseudopot_values`: Dict mapping element to pseudopot value
- `project_pseudo_dir`: Path to project pseudo directory
- `project_pseudo_dir.exists()`: Whether directory exists
- `available_pseudos`: List of pseudo files in project/pseudo

**Example log**:
```
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] ENTRY calculation_ulid=01KE052JT5S9DMATPNNJ8ZCTK3 project_root=/path/to/project
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] resolved calculation path=/path/to/project/calculations/silicon-mlwfs/calculation.yaml
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] structure_path=/path/to/project/structures/silicon.json required_elements=['Si']
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] species_map keys=['Si'] element_pseudopot_values={'Si': 'Si.pbe-n-van.UPF'}
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] project_pseudo_dir=/path/to/project/pseudo project_pseudo_dir.exists()=True available_pseudos=['Si.pbe-n-van.UPF']
INFO [qmatsuite.api] [GET_CALCULATION_PSEUDO_MAPPING] EXIT final_pseudo_mapping={'Si': 'Si.pbe-n-van.UPF'} mapping_missing=[] warnings=[]
```

### 3. `_handle_get_calculation_pseudo_mapping` (src/qmatsuite/daemon/server.py)

**When**: Entry and exit of handler

**Log Tags**: `[HANDLER_GET_CALCULATION_PSEUDO_MAPPING] ENTRY` and `[HANDLER_GET_CALCULATION_PSEUDO_MAPPING] EXIT`

**Entry information**:
- `payload_keys`: Keys in the request payload
- `calculation_selector`: Calculation selector (slug/name/ULID)

**Exit information**:
- `calculation_ulid`: Resolved calculation ULID
- `resolved_ulid`: Same as calculation_ulid
- `mapping_keys`: Keys in the returned mapping
- `warnings`: List of warnings

**Example log**:
```
INFO [qmatsuite.daemon.server] [HANDLER_GET_CALCULATION_PSEUDO_MAPPING] ENTRY payload_keys=['project_root', 'calculation'] calculation_selector=silicon-mlwfs
INFO [qmatsuite.daemon.server] [HANDLER_GET_CALCULATION_PSEUDO_MAPPING] EXIT calculation_ulid=01KE052JT5S9DMATPNNJ8ZCTK3 resolved_ulid=01KE052JT5S9DMATPNNJ8ZCTK3 mapping_keys=['Si'] warnings=[]
```

### 4. `_handle_get_pseudo_options_for_calculation` (src/qmatsuite/daemon/server.py)

**When**: Entry of handler

**Log Tag**: `[GET_PSEUDO_OPTIONS_FOR_CALCULATION] ENTRY`

**Information logged**:
- `payload_keys`: Keys in the request payload
- `calculation`: Calculation selector
- `inspect.signature(get_calculation_detail)`: Parameter names from function signature
- Actual call parameters passed to `get_calculation_detail`

**Example log**:
```
INFO [qmatsuite.daemon.server] [GET_PSEUDO_OPTIONS_FOR_CALCULATION] ENTRY payload_keys=['project_root', 'calculation'] calculation=silicon-mlwfs
INFO [qmatsuite.daemon.server] [GET_PSEUDO_OPTIONS_FOR_CALCULATION] inspect.signature(get_calculation_detail)=['project_root', 'calculation_selector', 'index', 'config', ...]
INFO [qmatsuite.daemon.server] [GET_PSEUDO_OPTIONS_FOR_CALCULATION] calling get_calculation_detail with calculation_selector=silicon-mlwfs (index and config from cache)
```

### 5. `Calculation.from_yaml` materialization (src/qmatsuite/calculation/calculation.py)

**When**: Entry of step materialization (when `materialize_steps=True`)

**Log Tag**: `[MATERIALIZE_STEPS] ENTRY`

**Information logged**:
- `calculation_dir`: Path to calculation directory
- `raw_dir`: Path to raw/ working directory
- `steps_to_materialize`: List of step IDs to be materialized
- `n_steps`: Number of steps

**Example log**:
```
INFO [qmatsuite.calculation.calculation] [MATERIALIZE_STEPS] ENTRY calculation_dir=/path/to/project/calculations/silicon-mlwfs raw_dir=/path/to/project/calculations/silicon-mlwfs/raw steps_to_materialize=['01KE052JT5380NNREG30HFRQRM', ...] n_steps=5
```

### 6. `materialize_step_spec` (src/qmatsuite/calculation/structure_steps.py)

**When**: Before calling `ensure_qe_pseudos`

**Log Tag**: `[MATERIALIZE_STEP_SPEC] before ensure_qe_pseudos`

**Information logged**:
- `calculation_dir`: Calculation directory
- `project_pseudo_dir`: Project pseudo directory
- `calculation_context`: Dict with:
  - `calculation_path`: Path to calculation.yaml
  - `species_map`: Full species_map from calculation
  - `structure_path`: Path to structure file

**Example log**:
```
INFO [qmatsuite.calculation.structure_steps] [MATERIALIZE_STEP_SPEC] before ensure_qe_pseudos calculation_dir=/path/to/project/calculations/silicon-mlwfs project_pseudo_dir=/path/to/project/pseudo calculation_context={'calculation_path': '/path/to/...', 'species_map': {...}, 'structure_path': '/path/to/...'}
```

## How to View Logs

### Through UI/Daemon

When running the UI, daemon logs are typically output to:
- Console where the daemon is running
- Log files (location depends on how daemon is started)

To see logs:
1. Open the silicon-wannier90 demo in the UI
2. Try to run the calculation
3. Check daemon console/logs for diagnostic messages

### Filtering Logs

To filter for diagnostic messages:

```bash
# All pseudo-related diagnostics
grep -E "\[(GET_CALCULATION_PSEUDO_MAPPING|HANDLER_GET_CALCULATION_PSEUDO_MAPPING|MATERIALIZE_STEPS|MATERIALIZE_STEP_SPEC|PSEUDO_CONFIG_ERROR|GET_PSEUDO_OPTIONS_FOR_CALCULATION)\]" daemon.log

# Specific calculation path resolution
grep "calculation_path\|structure_path" daemon.log

# Mapping information
grep "final_pseudo_mapping\|mapping_missing\|species_map_keys" daemon.log
```

## Expected Log Flow for silicon-wannier90 Demo

1. **UI opens demo**:
   - `[HANDLER_GET_CALCULATION_PSEUDO_MAPPING] ENTRY` with `calculation_selector=silicon-mlwfs`
   - `[GET_CALCULATION_PSEUDO_MAPPING] ENTRY`
   - Resolved calculation path
   - Structure path, required elements, species_map keys
   - Project pseudo dir check
   - `[GET_CALCULATION_PSEUDO_MAPPING] EXIT` with mapping and mapping_missing

2. **UI runs calculation**:
   - `[MATERIALIZE_STEPS] ENTRY` with raw_dir and steps list
   - For each step: `[MATERIALIZE_STEP_SPEC] before ensure_qe_pseudos`
   - If error: `[PSEUDO_CONFIG_ERROR]` with full diagnostic context

## Key Diagnostic Fields

When debugging, look for:
- **`calculation_path`**: Confirms calculation.yaml was found
- **`structure_path`**: Confirms structure file was found  
- **`required_elements`**: Elements needed from structure
- **`species_map_keys`**: Elements in species_map
- **`element_pseudopot_values`**: What pseudopot is configured for each element
- **`project_pseudo_dir.exists()`**: Whether project/pseudo exists
- **`final_pseudo_mapping`**: The resolved mapping
- **`mapping_missing`**: Elements that couldn't be resolved

