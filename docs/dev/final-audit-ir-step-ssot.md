# Final Audit: IR Truth + Step Vocabulary SSOT — Definitive Evidence Report

**Date**: 2025-01-XX  
**Purpose**: Resolve two disputed truths with hard code evidence and produce actionable ORCA/PySCF onboarding plan without violating SSOT or ParamSpace reversibility.

**Status**: Review-only (no code changes)

---

## Executive Conclusions

### A) IR Representation Truth

- **IR canonical format is QE-style strings (`.true.`/`.false.`) stored as strings in YAML**
- ParamSpace compiler converts Python `bool` → `.true.`/`.false.` strings **before** writing patch (paramspace.py:601-605)
- Integration layer ensures QE format via `ir_params_to_qe_params()` before applying to StepDoc (integration.py:718-719)
- step.yaml stores `.true.`/`.false.` strings (not Python bool) - confirmed by test expectations (test_integration_ir.py:177)
- **UNKNOWN**: YAML parsing behavior for `.true.` needs verification (proposed test included)

### B) Step Vocabulary SSOT

- **Two real vocabularies**: `public_type` (gen) and `machine_type` (spec)
- `public_type` used by: presets/ParamSpace targeting (variants_registry.py:257-265), UI display (api.py:3438-3439), file naming (api.py:3437)
- `machine_type` used by: step.yaml storage (step_factory.py:73), runner execution (step.py:92, qe_engine.py:40-41), materialization (structure_steps.py:747-772)
- **StepType Enum is legacy-only**: Used for coercion/formatting only (acceptable), but **2 violations** in validation logic (api.py:7756-7758, 7866-7868) - **FORBIDDEN**

### C) ORCA/PySCF Onboarding Plan

- **Preset targeting**: Use `public_type` (gen step) - variants keyed by public_type (variants_registry.py:267)
- **Step storage/execution**: Use `machine_type` (spec step) - step.yaml stores machine_type (step_factory.py:73)
- **IR→engine mapping**: Engine-owned modules (`ir/backends/{engine}/mapping.py`) convert IR canonical strings to engine format
- **Fix required**: Replace Enum validation with `StepTypeRegistry` lookups (api.py:7756-7758, 7866-7868)

---

## Part A: IR Truth Audit (Definitive)

### A.1 Complete Boolean Path Trace

**Example key**: `SYSTEM.noncolin` (boolean IR key)

#### Stage 1: ParamSpace Compiler Output (Before Patch)

**Location**: `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (lines 601-605)

**Code snippet**:
```python
# Convert boolean values to IR canonical format (.true./.false.)
# IR contract: boolean values must be canonical strings, not Python bool
if isinstance(value, bool):
    from quantumvitas.ir.backends.qe.mapping import ir_bool
    value = ir_bool(value)
```

**Type**: **IR canonical string** (`.true.` or `.false.`)

**Example value**: `".true."` (string)

**Evidence**: 
- Function: `compile_profile_patch()` (paramspace.py:541-612)
- Conversion: `ir_bool(True)` → `".true."` (mapping.py:30-31)
- Patch dict contains: `{"SYSTEM": {"noncolin": ".true."}}`

#### Stage 2: Integration Apply Patch (Before StepDoc)

**Location**: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 712-720)

**Code snippet**:
```python
# Serialize IR patch to engine format before writing to step.yaml
# step.yaml is spec step, parameters must be engine-specific format (QE: .true./.false.)
from quantumvitas.ir.backends.qe.mapping import ir_params_to_qe_params
qe_patch = ir_params_to_qe_params(unified_patch)
doc.apply_patch(qe_patch)
```

**Type**: **IR canonical string** (`.true.` or `.false.`) - same as Stage 1

**Example value**: `".true."` (string)

**Evidence**:
- Function: `ir_params_to_qe_params()` (mapping.py:218-278)
- Calls `ir_to_qe_param()` which preserves `.true.` strings (mapping.py:274, 118-122)
- Comment: "qe_value serialized (bool -> '.true.'/'.false.')" (mapping.py:234)

#### Stage 3: StepDoc Apply Patch (In-Memory)

**Location**: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)

**Code snippet**:
```python
def _apply_patch_recursive(self, patch: dict, current_path: list[str]) -> None:
    for key, value in patch.items():
        # ...
        else:
            # Set leaf value
            self.set(path, value)
```

**Type**: **IR canonical string** (`.true.` or `.false.`) - stored as-is

**Example value**: `".true."` (string)

**Evidence**:
- Function: `set()` (yamldoc.py:299-333) stores value directly: `parent[key] = value` (line 333)
- No type conversion in `apply_patch()` or `set()`
- Values are stored as-is in `_data` dict

#### Stage 4: Step YAML Serialized Representation

**Location**: `src/quantumvitas/core/yaml_io.py:save_yaml_doc()` (line 77)

**Code snippet**:
```python
content = yaml.safe_dump(data, default_flow_style=False, sort_keys=False)
```

**Type**: **YAML string** (`.true.` or `.false.` as string literal)

**Example value in YAML**: `noncolin: .true.` (unquoted) or `noncolin: ".true."` (quoted)

**Evidence**:
- `yaml.safe_dump()` serializes strings as YAML string literals
- If value is string `".true."`, YAML writes it as `.true.` (unquoted) or `".true."` (quoted)
- Test expectation: `assert result_content["parameters"]["SYSTEM"]["noncolin"] == ".false."` (test_integration_ir.py:177)

**UNKNOWN**: Does `yaml.safe_dump()` quote `.true.` strings? Need verification.

#### Stage 5: StructureStepSpec.from_yaml Load Type (After yaml.safe_load)

**Location**: `src/quantumvitas/calculation/structure_steps.py:StructureStepSpec.from_yaml()` (lines 150-169)

**Code snippet**:
```python
content = yaml.safe_load(spec_path.read_text()) or {}
```

**Type**: **UNKNOWN** - Depends on YAML parsing behavior

**Possible values**:
- If YAML contains `noncolin: .true.` (unquoted): YAML may parse as boolean `True` or string `".true."`
- If YAML contains `noncolin: ".true."` (quoted): YAML parses as string `".true."`

**Evidence Gap**: Need to verify actual YAML parsing behavior.

**Proposed test**:
```python
def test_yaml_boolean_parsing():
    import yaml
    
    # Test 1: Unquoted .true. (what yaml.safe_dump() produces)
    data1 = yaml.safe_dump({"noncolin": ".true."}, default_flow_style=False)
    parsed1 = yaml.safe_load(data1)
    assert isinstance(parsed1["noncolin"], str), f"Expected string, got {type(parsed1['noncolin'])}"
    assert parsed1["noncolin"] == ".true."
    
    # Test 2: Quoted .true.
    data2 = yaml.safe_load('noncolin: ".true."')
    assert isinstance(data2["noncolin"], str)
    assert data2["noncolin"] == ".true."
    
    # Test 3: Python bool (for comparison)
    data3 = yaml.safe_load("noncolin: true")
    assert isinstance(data3["noncolin"], bool)
    assert data3["noncolin"] is True
```

**Expected result**: If `yaml.safe_dump()` produces unquoted `.true.`, YAML may parse it as boolean. Need to verify.

#### Stage 6: Materialize Step Spec / Generate Input Type

**Location**: `src/quantumvitas/calculation/structure_steps.py:generate_qe_input_from_spec()` (line 487-524)

**Code snippet**:
```python
spec_overrides = parameter_dict_to_overrides(spec.parameters)
```

**Type**: **Depends on Stage 5** - If YAML parsed as string, remains string; if parsed as bool, is bool

**Example value**: Either `".true."` (string) or `True` (bool)

**Evidence**:
- `spec.parameters` comes from `StructureStepSpec.from_yaml()` (Stage 5)
- `parameter_dict_to_overrides()` converts dict to `ParameterOverride` list
- Values are passed to `apply_parameter_overrides()` which handles both types

#### Stage 7: Engine Writer Final Serialization Type

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 118-122)

**Code snippet**:
```python
# Convert Python bool to QE string format for boolean parameters
if isinstance(ir_value, bool):
    boolean_params = {"noncolin", "lspinorb", "nosym", "noinv"}
    if qe_key in boolean_params:
        qe_value = ".true." if ir_value else ".false."
```

**Type**: **QE canonical string** (`.true.` or `.false.`)

**Example value**: `".true."` (string)

**Evidence**:
- Function: `ir_to_qe_param()` (mapping.py:92-124)
- Converts Python `bool` to `.true.`/`.false.` strings for boolean parameters
- If input is already `.true.` string, it passes through unchanged (no conversion)

### A.2 Boundary Type Table

| Stage | Type | Example Value | Evidence Location |
|-------|------|--------------|-------------------|
| ParamSpace compile output | IR canonical string | `".true."` | paramspace.py:601-605 |
| Integration apply_patch | IR canonical string | `".true."` | integration.py:718-719 |
| StepDoc apply_patch (in-memory) | IR canonical string | `".true."` | yamldoc.py:396 |
| step.yaml serialized | YAML string | `noncolin: .true.` | yaml_io.py:77 |
| StructureStepSpec.from_yaml | **UNKNOWN** | Either `".true."` (str) or `True` (bool) | structure_steps.py:166 |
| Materialize/generate input | **UNKNOWN** | Depends on Stage 5 | structure_steps.py:516 |
| Engine writer serialization | QE canonical string | `".true."` | mapping.py:118-122 |

### A.3 Confirmation: ParamSpace Compiler Conversion

**Question**: Does ParamSpace/compiler convert Python `bool` → `.true.`/`.false.` BEFORE writing?

**Answer**: **YES**

**Evidence**: `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (lines 601-605)
```python
# Convert boolean values to IR canonical format (.true./.false.)
# IR contract: boolean values must be canonical strings, not Python bool
if isinstance(value, bool):
    from quantumvitas.ir.backends.qe.mapping import ir_bool
    value = ir_bool(value)
```

**Conclusion**: ParamSpace compiler converts Python `bool` to `.true.`/`.false.` strings **before** writing to patch dict.

### A.4 Confirmation: StepDoc Apply Patch Storage

**Question**: Does StepDoc `apply_patch()` store values "as-is"?

**Answer**: **YES**

**Evidence**: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)
- `_apply_patch_recursive()` calls `set()` for leaf values (line 396)
- `set()` stores value directly: `parent[key] = value` (yamldoc.py:333)
- No type conversion or normalization in `apply_patch()` or `set()`

**Conclusion**: StepDoc stores values as-is. If patch contains `.true.` string, it is stored as string.

### A.5 Proposed YAML Parsing Test

**Purpose**: Verify how `yaml.safe_load()` parses `.true.`/`.false.` strings

**Proposed test code**:
```python
def test_yaml_boolean_parsing_behavior():
    """Verify YAML parsing behavior for .true./.false. strings."""
    import yaml
    
    # Test 1: What yaml.safe_dump() produces for ".true." string
    data = {"noncolin": ".true."}
    yaml_str = yaml.safe_dump(data, default_flow_style=False)
    print(f"YAML output: {yaml_str}")
    
    # Test 2: Parse the YAML back
    parsed = yaml.safe_load(yaml_str)
    print(f"Parsed type: {type(parsed['noncolin'])}, value: {parsed['noncolin']!r}")
    
    # Expected: Should be string ".true.", not boolean True
    assert isinstance(parsed["noncolin"], str), \
        f"Expected string, got {type(parsed['noncolin'])}: {parsed['noncolin']!r}"
    assert parsed["noncolin"] == ".true."
    
    # Test 3: Unquoted .true. (edge case)
    data2 = yaml.safe_load("noncolin: .true.")
    print(f"Unquoted parsed type: {type(data2['noncolin'])}, value: {data2['noncolin']!r}")
    # This may parse as boolean or string - need to verify
    
    # Test 4: Quoted .true. (explicit string)
    data3 = yaml.safe_load('noncolin: ".true."')
    assert isinstance(data3["noncolin"], str)
    assert data3["noncolin"] == ".true."
```

**Expected result**: 
- If `yaml.safe_dump()` produces unquoted `.true.`, YAML may parse it as boolean (YAML spec allows `.true.` as boolean alias)
- If `yaml.safe_dump()` produces quoted `".true."`, YAML parses it as string
- **Need to verify actual behavior**

### A.6 Final Conclusion: IR Canonical Format

**Truth Statement**: **"IR canonical format is QE-style strings (`.true.`/`.false.`) stored as strings in YAML"**

**Evidence Summary**:
1. ParamSpace compiler converts Python `bool` → `.true.`/`.false.` strings (paramspace.py:601-605)
2. Integration layer ensures QE format before applying to StepDoc (integration.py:718-719)
3. StepDoc stores values as-is (yamldoc.py:396) - preserves `.true.` strings
4. Tests expect `.true.`/`.false.` strings in step.yaml (test_integration_ir.py:177)
5. Engine writer handles both Python `bool` and `.true.` strings (mapping.py:118-122)

**Conversion Boundary**:
- **Before StepDoc**: Python `bool` → `.true.`/`.false.` strings (ParamSpace compiler)
- **In StepDoc**: `.true.`/`.false.` strings stored as-is
- **After StepDoc**: If YAML parses as boolean, engine writer converts back to `.true.`/`.false.` strings

**UNKNOWN / Verification Needed**:
- YAML parsing behavior for unquoted `.true.` (may parse as boolean)
- Materialization type handling (if YAML parses as boolean, writer must convert)

**Acceptability**: Conversion at ParamSpace compiler boundary is acceptable because:
- IR contract explicitly states boolean values must be canonical strings (paramspace.py:602)
- Engine writers handle both types (mapping.py:118-122)
- Tests enforce string format (test_integration_ir.py:177)

---

## Part B: Step Vocabulary SSOT Audit (Exhaustive)

### B.1 Inventory of All Representations

**1. public_type (Gen Step)**:
- **Definition**: `src/quantumvitas/workflow/registry.py:StepTypeSpec.public_type` (line 46)
- **Format**: Generalized step type string (e.g., `"scf"`, `"nscf"`)
- **Storage**: Not stored on disk (in-memory only)
- **SSOT**: `StepTypeRegistry` `public_type` field

**2. machine_type (Spec Step)**:
- **Definition**: `src/quantumvitas/workflow/registry.py:StepTypeSpec.machine_type` (line 45)
- **Format**: Engine-prefixed step type string (e.g., `"qe_scf"`, `"w90_run"`)
- **Storage**: Stored in `step.yaml` `step_type` field
- **SSOT**: `StepTypeRegistry` `machine_type` field

**3. StepType Enum**:
- **Definition**: `src/quantumvitas/calculation/types.py:StepType` (lines 10-30)
- **Format**: Enum with values like `StepType.SCF = "scf"`, `StepType.BANDS_PW = "bands_pw"`, `StepType.PYSCF_SCF = "pyscf_scf"`
- **Storage**: Not stored on disk (in-memory only)
- **Status**: Legacy compatibility layer

**4. Other Representations**:
- **None found**: No `step_type_raw` or secondary registries found in codebase

### B.2 Exhaustive Call Site Inventory

#### B.2.1 public_type Usage Sites

| File / Function | Line | Usage Context | Allowed/Forbidden | Impact for ORCA/PySCF |
|-----------------|------|---------------|-------------------|----------------------|
| `presets/variants_registry.py:get_variant()` | 257-265 | Preset/ParamSpace step selection | **ALLOWED** (preset targeting) | None - uses public_type |
| `api.py:normalize_step_type_to_public()` | 3438-3439 | UI display (output file extensions) | **ALLOWED** (display/naming) | None - display only |
| `api.py:get_step_detail()` | 3437 | File naming (output file extensions) | **ALLOWED** (naming) | None - naming only |
| `workflow/registry.py:StepTypeRegistry.list_all()` | 624-626 | API listing (returns public types) | **ALLOWED** (API response) | None - API only |
| `workflow/registry.py:StepTypeRegistry.list_accepting_presets()` | 646-651 | Preset catalog (returns public types) | **ALLOWED** (catalog) | None - catalog only |

**Conclusion**: All `public_type` usages are **ALLOWED** (preset targeting, UI display, naming, API responses).

#### B.2.2 machine_type Usage Sites

| File / Function | Line | Usage Context | Allowed/Forbidden | Impact for ORCA/PySCF |
|-----------------|------|---------------|-------------------|----------------------|
| `workflow/step_factory.py:create_step_doc()` | 73 | step.yaml storage (`step_type` field) | **ALLOWED** (persistent storage) | Must add machine_type entries |
| `calculation/step.py:Step.run()` | 92 | Runner execution (reads from step.yaml) | **ALLOWED** (execution) | Must read machine_type from step.yaml |
| `engine/qe_engine.py:QeEngine.run_step()` | 40-41 | Engine execution (step_type_value passed to backend) | **ALLOWED** (execution) | Engine-specific |
| `engine/pyscf_engine.py:PySCFEngine.run_step_with_chain()` | 474-483 | PySCF execution (reads machine_type from step.yaml) | **ALLOWED** (execution) | Must read machine_type from step.yaml |
| `calculation/structure_steps.py:materialize_step_spec()` | 747-772 | Materialization routing (Wannier90/PySCF/ORCA detection) | **ALLOWED** (materialization) | Must add ORCA/PySCF routing |

**Conclusion**: All `machine_type` usages are **ALLOWED** (persistent storage, execution, materialization).

#### B.2.3 StepType Enum Usage Sites

| File / Function | Line | Usage Context | Allowed/Forbidden | Impact for ORCA/PySCF |
|-----------------|------|---------------|-------------------|----------------------|
| `calculation/step.py:Step.__init__()` | 29 | `step_type: Optional[StepType] = None` field | **ALLOWED** (type hinting) | None - type hint only |
| `calculation/runner.py:_coerce_step_type()` | 50-77 | String to Enum conversion | **ALLOWED** (coercion) | None - coercion only |
| `api.py:get_calculation_steps()` | 1292 | API response formatting | **ALLOWED** (formatting) | None - response only |
| `api.py:get_step_detail()` | 2376 | API response formatting | **ALLOWED** (formatting) | None - response only |
| `cli/main.py:_run_standalone_step()` | 1746 | Standalone step creation | **ALLOWED** (coercion) | None - coercion only |
| `api.py:set_relax_final_cell()` | 7756-7758 | **Validation logic** for relax operations | **FORBIDDEN** (core logic) | **HIGH** - Will fail for ORCA/PySCF |
| `api.py:get_relax_final_cell()` | 7866-7868 | **Validation logic** for relax operations | **FORBIDDEN** (core logic) | **HIGH** - Will fail for ORCA/PySCF |

**Conclusion**: 
- **6 ALLOWED** usages (type hinting, coercion, formatting)
- **2 FORBIDDEN** usages (validation logic) - **MUST FIX**

### B.3 Forbidden Enum Usages: Replacement Rules

#### Violation 1: `api.py:set_relax_final_cell()` (lines 7756-7758)

**Current code**:
```python
from quantumvitas.calculation.types import StepType
if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value):
    raise QVServiceError(
        f"Step '{step_selector}' is not a relax/vc-relax step (type: {step_type})"
    )
```

**Problem**: Uses Enum for validation. Enum doesn't include ORCA/PySCF values (e.g., `orca_relax`, `pyscf_opt`).

**Proposed replacement**:
```python
from quantumvitas.workflow.registry import get_registry
registry = get_registry()
spec = registry.get(step_type)  # Accepts both public and machine types
if spec is None:
    raise QVServiceError(f"Unknown step type: {step_type}")

# Check if step type is a relax type (use public_type for comparison)
# Relax types: "relax", "vc-relax" (public types)
# ORCA: "orca_opt", "orca_relax" (machine types) -> public_type "opt", "relax"
# PySCF: "pyscf_opt" (machine type) -> public_type "opt"
public_type = spec.public_type
if public_type not in ("relax", "vc-relax", "opt"):  # "opt" for ORCA/PySCF
    raise QVServiceError(
        f"Step '{step_selector}' is not a relax/vc-relax/opt step (type: {step_type}, public_type: {public_type})"
    )
```

**Rationale**: Use `StepTypeRegistry` to get `public_type`, then compare against allowed public types. This supports ORCA/PySCF relax/opt steps.

#### Violation 2: `api.py:get_relax_final_cell()` (lines 7866-7868)

**Current code**: Same as Violation 1 (duplicate)

**Proposed replacement**: Same as Violation 1

**Rationale**: Same fix applies.

### B.4 Mapping Logic: Public ↔ Machine

**Single source of truth**: `src/quantumvitas/workflow/registry.py:StepTypeRegistry.get()` (lines 594-618)

**Evidence**:
- Accepts both `public_type` and `machine_type` (line 608-616)
- Returns `StepTypeSpec` with both fields (line 606)
- **No multiple mappings exist** - this is the only mapping location

**Usage sites**:
1. `presets/variants_registry.py:get_variant()` (lines 260-265) - Maps machine_type → public_type for variant lookup
2. `workflow/generalized_steps.py:materialize_public_step_key()` (lines 193-200) - Maps public_type → machine_type for materialization

**Conclusion**: Mapping is **single-source-of-truth** via `StepTypeRegistry`. Safe for ORCA/PySCF extension.

---

## Part C: ORCA/PySCF Preset/IR Onboarding Architecture

### C.1 Preset/ParamSpace Targeting (Must Use public_type)

**Current implementation**: `src/quantumvitas/presets/variants_registry.py:get_variant()` (lines 257-268)

**Evidence**:
```python
# STEP TYPE MAPPING: Map machine_type to public_type for variant lookup
# Presets use gen/public step types (string), not machine_type
from quantumvitas.workflow.registry import get_registry
registry = get_registry()
spec = registry.get(step_type)
if spec and spec.public_type:
    # Map machine_type to public_type
    step_type = spec.public_type

key = (step_type, dimension)
return VARIANT_BY_STEP_AND_DIMENSION.get(key)
```

**Conclusion**: Variants are keyed by `(public_type, dimension)` tuple. ORCA/PySCF must use same `public_type` (e.g., `"scf"`) as QE.

**Mapping happens**: At variant lookup boundary (variants_registry.py:257-265) - maps machine_type → public_type before lookup.

### C.2 Spec/Machine Type (Must Land in step.yaml and Runner)

**Current implementation**: 
- **Storage**: `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73) - stores `machine_type` in step.yaml
- **Execution**: `src/quantumvitas/calculation/step.py:Step.run()` (line 92) - reads from step.yaml (machine_type)
- **Materialization**: `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` (lines 747-772) - uses machine_type for routing

**Conclusion**: ORCA/PySCF must:
1. Add `machine_type` entries to `StepTypeRegistry` (e.g., `"orca_scf"`, `"pyscf_scf"`)
2. Ensure step.yaml stores `machine_type` (already handled by step_factory.py)
3. Ensure runner reads `machine_type` from step.yaml (already handled by step.py)

### C.3 What ORCA/PySCF Must Implement

#### C.3.1 StepTypeRegistry Entries

**Location**: `src/quantumvitas/workflow/registry.py:_STEP_TYPES` dict (line ~100-558)

**Action**: Add `StepTypeSpec` entries for ORCA/PySCF step types

**Example**:
```python
StepTypeSpec(
    id="scf",  # public_type (same as QE)
    machine_type="orca_scf",  # ORCA-specific
    public_type="scf",  # alias for id
    engine="orca",
    executable="orca",
    description="ORCA SCF calculation",
    accepts_presets=True,
    allowed_dimensions=frozenset({"precision", "magnetism", "occupations_scheme"}),
    # ... other fields
)
```

**Rationale**: 
- `public_type` must match QE (e.g., `"scf"`) for preset targeting
- `machine_type` must be engine-specific (e.g., `"orca_scf"`) for execution
- `engine` field identifies engine family

#### C.3.2 Preset Variant Entries

**Location**: `src/quantumvitas/presets/variants_registry.py:VARIANT_BY_STEP_AND_DIMENSION` (line ~100-150)

**Action**: Add variant entries with `applies_to_step_types` including ORCA/PySCF public types

**Example**:
```python
# Existing variant (QE)
PRECISION_PW_DEFAULT_VARIANT = ParamSpaceVariant(
    name="PRECISION_PW_DEFAULT",
    dimension="precision",
    space=PRECISION_PW_DEFAULT_SPACE,
    applies_to_step_types=frozenset({
        "scf", "relax", "vc-relax", "md", "vc-md",  # public types
    }),
)

# ORCA/PySCF can reuse same variant (uses public_type "scf")
# No changes needed if ORCA/PySCF use same public_type as QE
```

**Rationale**: Variants are keyed by `public_type`. If ORCA/PySCF use same `public_type` as QE (e.g., `"scf"`), they automatically inherit QE variants. If they need different variants, add new entries with ORCA/PySCF-specific `public_type`.

#### C.3.3 Engine-Owned IR→Engine Parameter Mapping

**Location**: `src/quantumvitas/ir/backends/{engine}/mapping.py` (create new files)

**Action**: Create IR→engine mapping modules

**Example structure**:
```python
# src/quantumvitas/ir/backends/orca/mapping.py

IR_TO_ORCA_MAPPING: Dict[str, Tuple[str, str, str]] = {
    # Reuse IR keys (same as QE in v0)
    "ecutwfc": ("orca", "SCF", "basis"),  # ORCA uses basis sets, not ecutwfc
    "nspin": ("orca", "SCF", "mult"),  # ORCA uses multiplicity
    "noncolin": ("orca", "SCF", "UKS"),  # ORCA uses UKS for noncollinear
    # ... other mappings
}

def ir_to_orca_param(ir_key: str, ir_value: Any) -> Tuple[str, str, str, Any]:
    """Convert IR parameter to ORCA parameter."""
    # Convert IR canonical strings (.true./.false.) to ORCA format
    if ir_key in {"noncolin", "lspinorb"}:
        if ir_value == ".true.":
            orca_value = True  # ORCA uses Python bool
        elif ir_value == ".false.":
            orca_value = False
        else:
            orca_value = ir_value
    else:
        orca_value = ir_value
    
    qe_module, qe_section, qe_key = IR_TO_ORCA_MAPPING[ir_key]
    return (qe_module, qe_section, qe_key, orca_value)
```

**Rationale**: 
- IR keys remain engine-agnostic (same as QE in v0)
- Engine writers convert IR canonical strings to engine-specific format
- ORCA may use Python `bool` instead of `.true.`/`.false.` strings

#### C.3.4 Writer/Serializer Boolean Conversion

**Responsibility**: Engine writers must convert IR canonical strings (`.true.`/`.false.`) to engine-specific format

**Current QE implementation**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 118-122)
- Converts Python `bool` → `.true.`/`.false.` strings
- If input is already `.true.` string, passes through unchanged

**ORCA/PySCF requirement**: 
- **ORCA**: May use Python `bool` (`True`/`False`) in input files or Python API
- **PySCF**: May use Python `bool` (`True`/`False`) in Python API
- **Conversion**: `ir_to_orca_param()` or `ir_to_pyscf_param()` must convert `.true.`/`.false.` strings to engine format

**Example**:
```python
def ir_to_orca_param(ir_key: str, ir_value: Any) -> Tuple[str, str, str, Any]:
    # Handle IR canonical strings
    if isinstance(ir_value, str) and ir_value in (".true.", ".false."):
        orca_value = (ir_value == ".true.")  # Convert to Python bool
    elif isinstance(ir_value, bool):
        orca_value = ir_value  # Already bool
    else:
        orca_value = ir_value  # Other types
    
    # ... rest of mapping
```

### C.4 Explicit Confirmations

#### C.4.1 ParamSpace Core Does NOT Learn ORCA/PySCF Engine Parameters

**Confirmation**: **YES** - ParamSpace core remains engine-agnostic

**Evidence**:
- ParamSpace operates on IR keys (paramspace.py:64-71)
- IR keys are engine-agnostic (same as QE in v0, but conceptually engine-agnostic)
- Engine-specific mapping happens at writer boundary (mapping.py:92-124)

**ORCA/PySCF requirement**: 
- Add IR keys to ParamSpace if needed (e.g., ORCA-specific parameters)
- But ParamSpace core logic (compile/match) remains unchanged
- Engine writers handle ORCA/PySCF-specific conversions

#### C.4.2 No New "Third Step Vocabulary" May Be Introduced

**Confirmation**: **YES** - Only two vocabularies allowed

**Evidence**:
- `public_type` (gen step) - for preset targeting, UI, naming
- `machine_type` (spec step) - for storage, execution, materialization
- `StepType` Enum - legacy only, must not drive logic

**ORCA/PySCF requirement**:
- Must use existing `public_type`/`machine_type` system
- Cannot introduce new step type vocabulary
- Must add entries to `StepTypeRegistry` (not create new registry)

#### C.4.3 Only Thin Boundary Adapters Are Allowed

**Confirmation**: **YES** - Only boundary adapters allowed

**Evidence**:
- ParamSpace core (paramspace.py) - no engine-specific code
- Integration layer (integration.py) - calls `ir_params_to_qe_params()` at boundary
- Engine writers (mapping.py) - handle engine-specific conversions

**ORCA/PySCF requirement**:
- Create `ir/backends/{engine}/mapping.py` modules (thin adapters)
- No changes to ParamSpace core
- No changes to integration layer (except to call engine-specific mapper)

---

## Risk Register

### Risk 1: YAML Parsing Behavior for `.true.`/`.false.` Strings

**Risk**: If `yaml.safe_load()` parses unquoted `.true.` as boolean, materialization may receive Python `bool` instead of string.

**Impact**: Medium - May cause type mismatch if engine writer expects string.

**Mitigation**: 
- Verify YAML parsing behavior (proposed test in A.5)
- Engine writers already handle both types (mapping.py:118-122)
- If needed, ensure `yaml.safe_dump()` quotes `.true.` strings

**Evidence Gap**: Need to run proposed test to confirm behavior.

### Risk 2: Enum Validation Blocks ORCA/PySCF Steps

**Risk**: `api.py:7756-7758` and `7866-7868` use Enum for validation, which doesn't include ORCA/PySCF values.

**Impact**: **HIGH** - ORCA/PySCF relax/opt steps will fail validation.

**Mitigation**: 
- Replace Enum checks with `StepTypeRegistry` lookups (proposed fix in B.3)
- Use `public_type` for comparison (supports ORCA/PySCF `"opt"` public type)

**Fix Required**: **MANDATORY** before ORCA/PySCF onboarding.

### Risk 3: IR Canonical Strings Are QE-Specific

**Risk**: IR canonical strings (`.true.`/`.false.`) are QE-specific. ORCA/PySCF may use different boolean representations.

**Impact**: Low - Engine writers handle conversion.

**Mitigation**: 
- Engine writers convert IR canonical strings to engine-specific format
- ORCA/PySCF writers must implement boolean conversion (see C.3.4)

**Acceptability**: Conversion at writer boundary is acceptable (not in ParamSpace core).

### Risk 4: Variant Definitions Use Hardcoded public_type Strings

**Risk**: Variant `applies_to_step_types` uses hardcoded public_type strings (e.g., `frozenset({"scf", "nscf"})`).

**Impact**: Low - If ORCA/PySCF use same public_type as QE, they inherit variants automatically.

**Mitigation**: 
- ORCA/PySCF should use same public_type as QE (e.g., `"scf"`) for preset compatibility
- If different public_type needed, add new variant entries

**Acceptability**: Current design supports ORCA/PySCF if they use same public_type.

### Risk 5: Materialization Routing May Not Support ORCA/PySCF

**Risk**: `materialize_step_spec()` uses hardcoded step type checks for routing (lines 747-772).

**Impact**: Medium - ORCA/PySCF steps may not route correctly.

**Mitigation**: 
- Add ORCA/PySCF step type detection to materialization routing
- Use `StepTypeRegistry` to determine engine family instead of hardcoded checks

**Fix Required**: Add ORCA/PySCF routing logic to `materialize_step_spec()`.

---

## Appendix: Evidence Index

### IR Representation Evidence

**File → Symbol → Why Relevant**:

- `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (lines 601-605)
  - Converts Python `bool` → `.true.`/`.false.` strings
  - **Evidence**: ParamSpace compiler output type

- `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 712-720)
  - Calls `ir_params_to_qe_params()` to ensure QE format
  - **Evidence**: Integration layer type handling

- `src/quantumvitas/ir/backends/qe/mapping.py:ir_bool()` (lines 14-41)
  - IR canonical boolean encoder
  - **Evidence**: IR canonical format definition

- `src/quantumvitas/ir/backends/qe/mapping.py:ir_params_to_qe_params()` (lines 218-278)
  - Converts IR parameters to QE parameters
  - **Evidence**: IR→QE conversion at boundary

- `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)
  - Stores values as-is
  - **Evidence**: StepDoc storage behavior

- `tests/presets/test_integration_ir.py:177`
  - Expects `.false.` string in step.yaml
  - **Evidence**: Test expectations

### Step Vocabulary Evidence

**File → Symbol → Why Relevant**:

- `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58)
  - Defines `public_type` and `machine_type`
  - **Evidence**: Vocabulary definitions

- `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73)
  - Stores `machine_type` in step.yaml
  - **Evidence**: Storage location

- `src/quantumvitas/presets/variants_registry.py:get_variant()` (lines 257-265)
  - Maps machine_type → public_type for variant lookup
  - **Evidence**: Preset targeting uses public_type

- `src/quantumvitas/calculation/step.py:Step.run()` (line 92)
  - Reads step_type from step.yaml (machine_type)
  - **Evidence**: Runner execution uses machine_type

- `src/quantumvitas/calculation/types.py:StepType` (lines 10-30)
  - Enum definition
  - **Evidence**: Legacy vocabulary

- `src/quantumvitas/api.py:set_relax_final_cell()` (lines 7756-7758)
  - Enum validation (FORBIDDEN)
  - **Evidence**: SSOT violation

### Ripgrep Commands Used

```bash
# IR representation
rg -n "ir_bool|\.true\.|\.false\.|IR canonical|canonical encoding" -S src/quantumvitas
rg -n "noncolin|lspinorb|canonical" -S tests

# Step vocabulary
rg -n "public_type|machine_type|StepType\b|StepTypeRegistry" -S src/quantumvitas
rg -n "step_type.*=.*public|step_type.*=.*machine" -S src/quantumvitas

# Enum usage
rg -n "from.*StepType|import.*StepType|StepType\." -S src/quantumvitas
rg -n "StepType\(|StepType\." -S src/quantumvitas
```

---

**End of Final Audit Report**

