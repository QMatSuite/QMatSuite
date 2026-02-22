# QE CONTROL.{prefix,outdir,pseudo_dir} Audit Report

**Date**: 2024  
**Scope**: Audit how QE runtime-only keys (prefix, outdir, pseudo_dir) are handled across CLI import/show, step persistence, and runner/materialization paths.

---

## Section 1: CLI Import/Show Behavior (Preservation)

**Status**: ✅ **PASS** (with caveat)

### Evidence

**CLI show-command** (`src/qmatsuite/cli/main.py:3108-3197`):
- **Parsing**: `QEInputParser.parse_file(input_file)` (line 3121) → `QEInput` object
- **Parameter extraction**: `_qe_input_to_parameter_dict(qe_input)` (line 3122)
  - **Location**: `src/qmatsuite/cli/main.py:4299-4308`
  - **Behavior**: Extracts ALL parameters from ALL namelists, including `prefix`, `outdir`, `pseudo_dir`
  - **No filtering**: Only strips structural SYSTEM params (ibrav, nat, ntyp, celldm) via `_strip_structural_system_params()` (line 4307)
- **CLI args generation**: `_parameter_dict_to_cli_args(parameter_dict)` (line 3123)
  - **Location**: `src/qmatsuite/cli/main.py:4342-4350`
  - **Behavior**: Converts all parameters to `--SECTION.key=value` format, including prefix/outdir/pseudo_dir
- **Output**: Generated command includes `--CONTROL.prefix=...`, `--CONTROL.outdir=...`, `--CONTROL.pseudo_dir=...` if present in original .in

**Call Graph**:
```
show_command(input_file)
  └─> QEInputParser.parse_file(input_file)  [io/parser/qe_parser.py]
  └─> _qe_input_to_parameter_dict(qe_input)  [cli/main.py:4299]
       └─> Iterates all namelists, extracts all parameters
       └─> _strip_structural_system_params()  [cli/main.py:4311]
            └─> Only strips ibrav, nat, ntyp, celldm, lattice params
  └─> _parameter_dict_to_cli_args(parameter_dict)  [cli/main.py:4342]
       └─> Formats as --SECTION.key=value for ALL params
```

**CLI import paths**:
- **API import**: `QMSService.import_step_from_qe_input()` (`src/qmatsuite/api.py:5538-5602`)
  - Uses `build_step_spec_from_qe_input()` with `apply_defaults=False` (line 5601)
  - **Location**: `src/qmatsuite/calculation/importers.py:95-196`
  - **Parameter extraction**: `_extract_parameters(qe_input)` (line 68)
    - **Location**: `src/qmatsuite/calculation/importers.py:444-453`
    - **Behavior**: Extracts ALL parameters from ALL namelists, no filtering of prefix/outdir/pseudo_dir
    - Only strips structural params via `_remove_structure_parameters()` (line 452)

**Conclusion**: CLI import/show **DOES preserve** prefix/outdir/pseudo_dir from external .in files. ✅

**Caveat**: The test `test_cli_show_command_import_preserves_original_parameters` (`tests/unit/test_project_and_cli.py:1003-1016`) strips runtime-only keys in the **comparison logic** (not in persistence), which masks the issue that these keys may leak into step.yaml.

---

## Section 2: Step Persistence Boundary

**Status**: ❌ **FAIL** (runtime-only keys are NOT stripped before persistence)

### Evidence

**Step creation paths**:

1. **CLI init step** (`src/qmatsuite/cli/main.py:920-1217`):
   - **Parameter collection**: Lines 1171-1189 merge defaults with user overrides
   - **No stripping**: No code removes prefix/outdir/pseudo_dir from `params` dict
   - **Step spec creation**: `StructureStepSpec(parameters=params, ...)` (line 1211)
   - **Persistence**: `_write_step_spec(spec_path, spec, ...)` (line 1217)
     - **Location**: `src/qmatsuite/cli/main.py:4199-4209`
     - **Behavior**: Calls `spec.to_dict()` and writes directly to YAML (line 4209)
     - **No filtering**: `to_dict()` does NOT strip prefix/outdir/pseudo_dir

2. **API add_step_to_calculation** (`src/qmatsuite/api.py:6155-6350`):
   - **Parameter source**: Uses `get_default_step_params(step_type)` (line 6221)
   - **No stripping**: Default params may include prefix/outdir (if in defaults), no filtering
   - **Step spec creation**: `StructureStepSpec(parameters=default_params, ...)` (line 6328)
   - **Persistence**: `StepDoc(step_spec.to_dict())` → `save_step_doc()` (lines 6349-6350)
     - **No filtering**: `to_dict()` does NOT strip prefix/outdir/pseudo_dir

3. **API import_step_from_qe_input** (`src/qmatsuite/api.py:5538-5602`):
   - **Parameter source**: `build_step_spec_from_qe_input(apply_defaults=False)` (line 5594)
   - **Extraction**: `_extract_parameters(qe_input)` includes ALL params (no filtering)
   - **Step spec creation**: `StructureStepSpec(parameters=parameters, ...)` (line 244 in importers.py)
   - **Persistence**: Via `save_step_doc()` (line 5769)
     - **No filtering**: `to_dict()` does NOT strip prefix/outdir/pseudo_dir

4. **StructureStepSpec.to_dict()** (`src/qmatsuite/calculation/structure_steps.py:171-200`):
   - **Location**: Lines 189-190: `if self.parameters: data["parameters"] = self.parameters`
   - **Behavior**: Writes ALL parameters as-is, no filtering
   - **No stripping**: No code removes prefix/outdir/pseudo_dir

**Exception (export only)**:
- **Snapshot export** (`src/qmatsuite/project/snapshot.py:375-381`):
  - **Location**: Lines 375-381 explicitly strip prefix/outdir from step parameters
  - **Scope**: Only for snapshot export, NOT for step.yaml persistence
  - **Not applicable**: This is a one-way export, not the persistence boundary

**Conclusion**: ❌ **FAIL** - prefix/outdir/pseudo_dir are **NOT stripped** before writing to step.yaml. If present in imported .in files or passed via CLI, they will be persisted, violating policy B.

---

## Section 3: Runner/Materialization Injection

**Status**: ✅ **PASS** (injection happens AFTER persistence, step-level values ignored)

### Evidence

**Injection sites**:

1. **Prefix injection** (`src/qmatsuite/calculation/structure_steps.py:306-407`):
   - **Function**: `_inject_calculation_prefix_outdir()`
   - **Location**: Called from `materialize_step_spec()` at line 1086
   - **Timing**: **AFTER** step.yaml is read (step.yaml is read earlier, injection happens during materialization)
   - **Behavior**: 
     - Overrides any existing prefix in QEInput (line 388: `namelist.parameters["prefix"] = calculation_prefix`)
     - Logs ignored step-level prefix (lines 362-367)
   - **Source**: `stable_short_calc_prefix(calc_model.meta.id)` (line 1035)

2. **Outdir injection** (`src/qmatsuite/calculation/structure_steps.py:394-407`):
   - **Function**: Same `_inject_calculation_prefix_outdir()`
   - **Location**: Lines 394-407
   - **Behavior**: 
     - Overrides any existing outdir (line 400: `namelist.parameters["outdir"] = calculation_outdir`)
     - Default: `"./outdir"` (line 1016)
   - **Additional**: `set_outdir_to_temp()` called at line 1108 (forces `"./outdir"`)

3. **Pseudo_dir injection** (`src/qmatsuite/calculation/structure_steps.py:1111-1158`):
   - **Function**: `set_pseudo_dir_in_input()`
   - **Location**: Called at line 1158
   - **Timing**: **AFTER** prefix/outdir injection (line 1108: outdir, line 1158: pseudo_dir)
   - **Behavior**: 
     - Overrides any existing pseudo_dir (line 155 in input_runner.py: `namelist.parameters["pseudo_dir"] = pseudo_dir_str`)
     - Value: `project_root / "pseudo"` (line 1115)

**Call Graph**:
```
materialize_step_spec()
  └─> Load step.yaml (via StructureStepSpec.from_yaml)
  └─> generate_qe_input_from_spec()  [line 1082]
  └─> _inject_calculation_prefix_outdir()  [line 1086]
       └─> Overrides prefix/outdir in QEInput (ignores step.yaml values)
  └─> set_outdir_to_temp()  [line 1108]
  └─> set_pseudo_dir_in_input()  [line 1158]
       └─> Overrides pseudo_dir in QEInput
```

**Conclusion**: ✅ **PASS** - Injection happens **AFTER** step.yaml is read, and step-level values are **ignored/overridden** by calculation defaults.

---

## Section 4: Other Entrypoints Besides CLI

**Status**: ⚠️ **PARTIAL** (API/daemon accept parameters, no config/env overrides)

### Evidence

**API Entrypoints**:
- `QMSService.add_step_to_calculation()` (`src/qmatsuite/api.py:6155-6350`)
  - Uses `get_default_step_params(step_type)` which includes `outdir` (see Risk 3)
- `QMSService.import_step_from_qe_input()` (`src/qmatsuite/api.py:5538-5602`)
  - Extracts from .in file via `_extract_parameters()` which includes ALL params (see Risk 1)
- `QMSService.update_step_params()` (`src/qmatsuite/api.py:4477-4555`)
  - Accepts `parameters: Dict[str, Dict[str, Any]]` and applies via `step_doc.apply_patch()` (line 4541)
  - **No filtering**: If user passes prefix/outdir/pseudo_dir, they will be written to step.yaml (see Risk 4)

**Daemon Entrypoints**:
- `_handle_add_step_to_calculation()` (`src/qmatsuite/daemon/server.py:4195-4226`)
  - Calls `QMSService.add_step_to_calculation()` (uses defaults with outdir)
- `_handle_import_step_from_qe_input()` (`src/qmatsuite/daemon/server.py:4228+`)
  - Calls `QMSService.import_step_from_qe_input()` (extracts all params)

**Config/Env Var Handling**:
- **Environment variables**: `QMS_PSEUDO_PATH` exists (`src/qmatsuite/core/pseudo.py:344`) but is for pseudo resolution, NOT for pseudo_dir in QE input
- **No config overrides**: No project config or env vars that override prefix/outdir/pseudo_dir in QE input

**Conclusion**: ⚠️ **PARTIAL** - No config/env var overrides for prefix/outdir/pseudo_dir. However, API/daemon entrypoints can accept these keys via parameters dict or defaults, which is a risk (covered in Section 5).

---

## Section 5: Risks (Where Runtime-Only Keys Might Leak)

### Risk 1: Import from .in file with prefix/outdir/pseudo_dir
**Location**: `src/qmatsuite/calculation/importers.py:444-453`
- **Issue**: `_extract_parameters()` extracts ALL parameters, including prefix/outdir/pseudo_dir
- **Impact**: If user imports a .in file that contains these keys, they will be written to step.yaml
- **Violation**: Policy B (step.yaml must NOT contain runtime-only keys)

### Risk 2: CLI init step with --CONTROL.prefix/outdir/pseudo_dir
**Location**: `src/qmatsuite/cli/main.py:1171-1211`
- **Issue**: User overrides are merged into params dict without filtering
- **Impact**: If user passes `--CONTROL.prefix=xyz`, it will be written to step.yaml
- **Violation**: Policy B (step.yaml must NOT contain runtime-only keys)

### Risk 3: API add_step_to_calculation with parameters
**Location**: `src/qmatsuite/api.py:6328`
- **Issue**: Default params include `outdir` in step_defaults.py
- **Evidence**: `src/qmatsuite/calculation/step_defaults.py:16,38,63,73,94,115,140,168`
  - All step types have `"outdir": "./outdir"` in CONTROL or DOS sections
- **Impact**: When steps are created with defaults (normal mode), `outdir` is written to step.yaml
- **Violation**: Policy B (step.yaml must NOT contain runtime-only keys)

### Risk 4: API configure_step / update_step_params
**Location**: `src/qmatsuite/api.py:4477-4555`, `4930-4982`
- **Issue**: `update_step_params()` accepts `parameters: Dict[str, Dict[str, Any]]` and applies via `step_doc.apply_patch()` (line 4541)
- **Evidence**: No filtering of runtime-only keys before applying patch
- **Impact**: If user updates prefix/outdir/pseudo_dir via API, they will be written to step.yaml
- **Violation**: Policy B

### Risk 5: Daemon add_step_to_calculation
**Location**: `src/qmatsuite/daemon/server.py:4195-4226`
- **Issue**: Calls `QMSService.add_step_to_calculation()` which uses defaults
- **Impact**: Same as Risk 3

**Current Mitigation**:
- Materialization **ignores** step-level prefix/outdir (logged but overridden)
- However, the keys still **exist in step.yaml**, which violates policy B

---

## Section 5: Minimal Fix Approach (No Code Changes)

### Fix Location 0: Remove outdir from step_defaults.py (Immediate)

**Location**: `src/qmatsuite/calculation/step_defaults.py:16,38,63,73,94,115,140,168`
- **Change**: Remove `"outdir": "./outdir"` from all step type defaults
- **Rationale**: outdir is runtime-only and injected during materialization; should not be in defaults
- **Impact**: Steps created with defaults will not have outdir in step.yaml
- **Note**: This is a breaking change for existing step.yaml files that may have outdir, but it's correct per policy B

### Fix Location 1: Step Persistence Boundary (Primary)

**Option A: Strip in StructureStepSpec.to_dict()** (Preferred)
- **Location**: `src/qmatsuite/calculation/structure_steps.py:171-200`
- **Change**: Before writing parameters to dict, remove prefix/outdir/pseudo_dir from all sections
- **Logic**:
  ```python
  # In to_dict(), before line 189:
  filtered_params = {}
  RUNTIME_ONLY_KEYS = {"prefix", "outdir", "pseudo_dir"}
  for section, section_params in self.parameters.items():
      if isinstance(section_params, dict):
          filtered_section = {k: v for k, v in section_params.items() 
                             if k.lower() not in RUNTIME_ONLY_KEYS}
          if filtered_section:
              filtered_params[section] = filtered_section
      else:
          filtered_params[section] = section_params
  data["parameters"] = filtered_params if filtered_params else None
  ```
- **Pros**: Single point of enforcement, applies to all persistence paths
- **Cons**: None

**Option B: Strip in _write_step_spec()**
- **Location**: `src/qmatsuite/cli/main.py:4199-4209`
- **Change**: Before calling `spec.to_dict()`, strip runtime-only keys from spec.parameters
- **Pros**: Centralized for CLI path
- **Cons**: Does not cover API paths (add_step_to_calculation, import_step_from_qe_input)

**Option C: Strip in StepDoc.save() or save_step_doc()**
- **Location**: `src/qmatsuite/workflow/step_factory.py:106-121`
- **Change**: Before saving, strip runtime-only keys from step_doc data
- **Pros**: Covers all StepDoc-based persistence
- **Cons**: Requires understanding StepDoc internals

**Recommendation**: **Option A** (strip in `to_dict()`) - single source of truth, applies to all paths.

### Fix Location 2: Import Path (Secondary)

**Location**: `src/qmatsuite/calculation/importers.py:444-453`
- **Change**: In `_extract_parameters()`, filter out prefix/outdir/pseudo_dir after extraction
- **Logic**: After line 451, remove runtime-only keys from parameters dict
- **Pros**: Prevents import from writing these keys
- **Cons**: Redundant if Option A is implemented (defense in depth)

### Fix Location 3: CLI Override Parsing (Tertiary)

**Location**: `src/qmatsuite/cli/main.py:1171-1211`
- **Change**: In `init_step_command()`, filter runtime-only keys from user overrides before merging
- **Logic**: After `_overrides_to_parameter_dict()`, remove prefix/outdir/pseudo_dir
- **Pros**: Prevents CLI from writing these keys
- **Cons**: Redundant if Option A is implemented

### Verification Points

After fix, verify:
1. Import .in file with prefix/outdir/pseudo_dir → step.yaml does NOT contain them
2. CLI `init step --CONTROL.prefix=xyz` → step.yaml does NOT contain prefix
3. API `add_step_to_calculation` → step.yaml does NOT contain prefix/outdir/pseudo_dir
4. Materialization still injects defaults correctly (ignores step-level values)

---

## Summary

| Section | Status | Key Finding |
|---------|--------|-------------|
| **1. CLI Import/Show** | ✅ PASS | Preserves prefix/outdir/pseudo_dir from .in files (correct) |
| **2. Step Persistence** | ❌ FAIL | **Runtime-only keys are NOT stripped** before writing to step.yaml |
| **3. Runner/Materialization** | ✅ PASS | Injection happens AFTER persistence, step-level values ignored |
| **4. Other Entrypoints** | ⚠️ PARTIAL | API/daemon accept parameters, no config/env overrides |
| **5. Risks** | ⚠️ HIGH | Multiple paths allow runtime-only keys to leak into step.yaml |

**Critical Issue**: Policy B is **violated** - step.yaml can contain prefix/outdir/pseudo_dir if:
- **Default mode**: `outdir` is in step_defaults.py and will be written to step.yaml (all step types)
- Imported from .in file that contains them
- Passed via CLI `--CONTROL.prefix/outdir/pseudo_dir`
- Updated via API `configure_step` / `update_step_params`

**Recommended Fix**: Strip runtime-only keys in `StructureStepSpec.to_dict()` (Option A) - single point of enforcement for all persistence paths.

---

**Report End**

