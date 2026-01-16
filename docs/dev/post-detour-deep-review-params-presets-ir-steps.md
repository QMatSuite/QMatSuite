# Post-Detour Deep Code Review: ParamSpace + Presets/IR + QE Parameters + Materialization + Execution Modes + Gen/Spec Step Usage

**Date**: 2025-01-XX  
**Purpose**: Comprehensive review of the system state after detour work, focusing on ParamSpace restore, IR SSOT, species_map SSOT, execution modes, and step type vocabularies. This review must guide ORCA/PySCF onboarding without breaking reversibility or SSOT.

**Status**: Review-only (no code changes)

---

## FINAL AUDIT ADDENDUM: IR Truth + Step Vocabulary SSOT

**Date**: 2025-01-XX  
**Purpose**: Resolve two disputed points with hard evidence: (A) IR representation truth (`.true.` strings vs Python bool), (B) Step vocabulary SSOT (gen/public vs spec/machine vs Enum).

---

### Part 1 — IR Representation Truth (Definitive)

#### 1.1 What the Code Calls "IR"

**IR Definition**: `src/quantumvitas/presets/paramspace.py:ParamKey` docstring (lines 64-71)
- "ParamSpace operates on IR keys (IR is SSOT). In v0, IR keys == QE keys due to 1:1 mapping"
- IR sections: `"SYSTEM"`, `"ELECTRONS"`, `"cards"` (same as QE sections in v0)
- IR keys: Parameter names (e.g., `"ecutwfc"`, `"nspin"`, `"noncolin"`) that match QE keys in v0

**IR Canonical Encoder**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_bool()` (lines 14-41)
- Converts Python `bool` or IR canonical string to IR canonical boolean string
- Returns: `".true."` or `".false."` (IR canonical format)
- Docstring: "This is part of IR contract (not engine serialization)"

**IR Mapping**: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
- Maps IR keys to `(qe_module, qe_section, qe_key)` tuples
- In v0, mapping is 1:1 (IR key == QE key for most parameters)

#### 1.2 Storage Type at Each Boundary

**(a) ParamSpace Compiler Output (Patch Dicts)**:

**Evidence**: `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (lines 601-605)
```python
# Convert boolean values to IR canonical format (.true./.false.)
# IR contract: boolean values must be canonical strings, not Python bool
if isinstance(value, bool):
    from quantumvitas.ir.backends.qe.mapping import ir_bool
    value = ir_bool(value)
```

**Conclusion**: ParamSpace compiler output contains **IR canonical strings** (`.true.`/`.false.`), not Python `bool`.

**(b) Step YAML Storage (step.yaml)**:

**Evidence**: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 712-720)
```python
# Serialize IR patch to engine format before writing to step.yaml
# step.yaml is spec step, parameters must be engine-specific format (QE: .true./.false.)
from quantumvitas.ir.backends.qe.mapping import ir_params_to_qe_params
qe_patch = ir_params_to_qe_params(unified_patch)
doc.apply_patch(qe_patch)
```

**Evidence**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_params_to_qe_params()` (lines 218-278)
- Calls `ir_to_qe_param()` (line 274) which converts boolean values to `.true.`/`.false.` strings (lines 118-122)
- Comment: "qe_value serialized (bool -> '.true.'/'.false.')" (line 234)

**Evidence**: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)
- Stores values as-is via `set()` (line 396)
- If patch contains `.true.` string, it is stored as string (not converted to Python bool)

**Test Evidence**: `tests/presets/test_integration_ir.py:177`
```python
# Compiler output uses QE string format for booleans (per Fix #1: canonical encoding)
# step.yaml stores QE strings, not Python bools
assert result_content["parameters"]["SYSTEM"]["noncolin"] == ".false."
```

**Conclusion**: step.yaml stores **IR canonical strings** (`.true.`/`.false.`), not Python `bool`. YAML serialization preserves strings.

**(c) Materialization Input (StructureStepSpec / materialize_step_spec)**:

**Evidence**: `src/quantumvitas/calculation/structure_steps.py:StructureStepSpec.from_yaml()` (lines 150-169)
- Uses `yaml.safe_load()` (line 166) to read step.yaml
- YAML parser: If step.yaml contains `noncolin: .true.` (unquoted), YAML may parse it as string or boolean depending on context
- **UNKNOWN**: Need to verify actual parsing behavior. If YAML parses `.true.` as boolean, there may be a mismatch.

**Evidence**: `src/quantumvitas/calculation/structure_steps.py:generate_qe_input_from_spec()` (line 487-524)
- Reads `spec.parameters` (line 516) which comes from `StructureStepSpec.from_yaml()`
- Values are passed to `apply_parameter_overrides()` which expects QE format

**Conclusion**: Materialization reads values from step.yaml. If YAML parses `.true.` as boolean, there may be a type mismatch. **VERIFY**: Check if `yaml.safe_load()` parses `.true.` as string or boolean.

**(d) QE Input Writer (generate_qe_input_from_spec / QE mapping)**:

**Evidence**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 92-124)
- Converts IR parameter to QE parameter
- For boolean parameters: Converts Python `bool` to `.true.`/`.false.` strings (lines 118-122)
- But if input is already `.true.` string, it passes through unchanged

**Evidence**: `src/quantumvitas/io/generator.py:QEInputGenerator.write_file()`
- Writes QE input file from `QEInput` object
- Boolean values in `QEInput.namelists[].parameters` are written as `.true.`/`.false.` strings

**Conclusion**: QE writer expects `.true.`/`.false.` strings (or converts Python `bool` to strings). If materialization reads Python `bool` from step.yaml, writer must convert.

#### 1.3 Test Evidence

**Tests Expecting `.true.`/`.false.` Strings**:

1. **`tests/presets/test_integration_ir.py:177`**: Expects `.false.` string in step.yaml after applying presets
2. **`tests/unit/test_preset_integration.py:328-329`**: Expects `.true.` strings in system params
3. **`tests/unit/test_detector_b.py:51-52`**: Detector expects `.true.` string format for matching

**Tests Expecting Python Bool**:

- **NONE FOUND**: No tests explicitly expect Python `True`/`False` in step.yaml or patches.

**Conclusion**: All tests expect **IR canonical strings** (`.true.`/`.false.`) in step.yaml and patches.

#### 1.4 Final Conclusion: Truth Statement

**Truth A: "IR is QE-canonical and stored as strings in YAML; `.true.`/`.false.` appear before the writer."**

**Evidence Summary**:
1. ParamSpace compiler converts Python `bool` to `.true.`/`.false.` strings using `ir_bool()` (paramspace.py:601-605)
2. Integration layer ensures QE format before applying to StepDoc (integration.py:718-719)
3. `ir_params_to_qe_params()` converts IR to QE format, serializing booleans to strings (mapping.py:218-278)
4. Tests expect `.true.`/`.false.` strings in step.yaml (test_integration_ir.py:177)
5. StepDoc `apply_patch()` stores values as-is (yamldoc.py:396), preserving strings

**UNKNOWN / Verification Needed**:
- **YAML parsing behavior**: Does `yaml.safe_load()` parse `noncolin: .true.` as string or boolean? If boolean, there may be a type mismatch that needs handling.
- **Materialization type handling**: Does `StructureStepSpec.from_yaml()` receive Python `bool` or string? If bool, QE writer must convert.

**Recommendation**: Add a targeted test to verify YAML parsing behavior:
```python
def test_yaml_boolean_parsing():
    import yaml
    # Test 1: Unquoted .true.
    data1 = yaml.safe_load("noncolin: .true.")
    assert isinstance(data1["noncolin"], str)  # Should be string
    
    # Test 2: Quoted .true.
    data2 = yaml.safe_load('noncolin: ".true."')
    assert isinstance(data2["noncolin"], str)  # Should be string
    
    # Test 3: Python bool
    data3 = yaml.safe_load("noncolin: true")
    assert isinstance(data3["noncolin"], bool)  # Should be bool
```

---

### Part 2 — Step Vocabulary SSOT Audit (Gen vs Spec vs Enum)

#### 2.1 Inventory of All Vocabularies

**Gen/Public Step Identifiers**:

**Where defined**: `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58)
- `public_type` field: Generalized step type string (e.g., `"scf"`, `"nscf"`)
- `id` field: Alias for `public_type` (for backward compatibility)

**How stored**: Not stored on disk. Used in memory for:
- Preset/ParamSpace lookups (via `get_variant()`)
- UI display (via `normalize_step_type_to_public()`)
- File naming (output file extensions)

**Spec/Machine Step Identifiers**:

**Where defined**: `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58)
- `machine_type` field: Engine-prefixed step type string (e.g., `"qe_scf"`, `"w90_run"`)

**How stored**: Stored in `step.yaml` `step_type` field
- Evidence: `src/quantumvitas/workflow/step_factory.py:73` - `"step_type": machine_step_type`

**StepType Enum**:

**Where defined**: `src/quantumvitas/calculation/types.py:StepType` (lines 10-30)
- Values: `SCF = "scf"`, `NSCF = "nscf"`, `DOS = "dos"`, `BANDS_PW = "bands_pw"`, `BANDS = "bands"`, `PH = "ph"`, `Q2R = "q2r"`, `MATDYN = "matdyn"`, `DYNMAT = "dynmat"`, `PP = "pp"`, `PROJWFC = "projwfc"`, `RELAX = "relax"`, `VC_RELAX = "vc-relax"`, `W90_PREPROC = "w90_preproc"`, `PW2WANNIER90 = "pw2wannier90"`, `W90_RUN = "w90_run"`, `PYSCF_SCF = "pyscf_scf"`, `CUSTOM = "custom"`

**How used**: Legacy compatibility layer
- Used in `Step` dataclass: `step_type: Optional[StepType] = None` (step.py:29)
- Used for coercion: `_coerce_step_type()` (runner.py:50-77)
- Used for validation: `if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value)` (api.py:7756-7758)

#### 2.2 Where Gen/Public Is Used (Call Sites)

| File / Function | Uses Gen/Public For | Affects Execution Semantics? |
|---|---|---|
| `src/quantumvitas/presets/variants_registry.py:get_variant()` (lines 257-265) | Preset/ParamSpace step selection | **YES** - Determines which variants apply to step |
| `src/quantumvitas/api.py:normalize_step_type_to_public()` (line 3438-3439) | UI display (output file extensions) | **NO** - Display/naming only |
| `src/quantumvitas/api.py:get_step_detail()` (line 3437) | File naming (output file extensions) | **NO** - File naming only |
| `src/quantumvitas/workflow/registry.py:StepTypeRegistry.list_all()` (line 624-626) | API listing (returns public types) | **NO** - API response only |
| `src/quantumvitas/workflow/registry.py:StepTypeRegistry.list_accepting_presets()` (line 646-651) | Preset catalog (returns public types) | **NO** - Catalog only |

**Conclusion**: Gen/public types are used for **preset targeting** (affects execution) and **UI/API display** (does not affect execution).

#### 2.3 Where Spec/Machine Is Used (Call Sites)

| File / Function | Uses Spec/Machine For | Affects Execution Semantics? |
|---|---|---|
| `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73) | step.yaml storage (`step_type` field) | **YES** - Persistent storage |
| `src/quantumvitas/calculation/step.py:Step.run()` (line 92) | Runner execution (reads from step.yaml) | **YES** - Determines executable/binary |
| `src/quantumvitas/engine/qe_engine.py:QeEngine.run_step()` (lines 40-41) | Engine execution (step_type_value passed to backend) | **YES** - Determines QE executable |
| `src/quantumvitas/engine/pyscf_engine.py:PySCFEngine.run_step_with_chain()` (lines 474-483) | PySCF execution (reads machine_type from step.yaml) | **YES** - Determines PySCF step type |
| `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` (lines 747-772) | Materialization routing (Wannier90/PySCF/ORCA detection) | **YES** - Determines input generator |

**Conclusion**: Spec/machine types are used for **persistent storage** and **execution** (affects execution semantics).

#### 2.4 Where Enum Is Used (Exhaustive)

**All Enum Usages**:

1. **`src/quantumvitas/calculation/step.py:29`** - `step_type: Optional[StepType] = None`
   - **Classification**: Legacy coercion only (acceptable)
   - **Logic influence**: Used for type hinting and coercion, but execution reads from step.yaml (line 92)

2. **`src/quantumvitas/calculation/runner.py:50-77`** - `_coerce_step_type()`
   - **Classification**: Legacy coercion only (acceptable)
   - **Logic influence**: Converts string to Enum for backward compatibility, but execution uses string from step.yaml

3. **`src/quantumvitas/api.py:7756-7758`** - Validation: `if step_type not in (StepType.RELAX.value, StepType.VC_RELAX.value)`
   - **Classification**: **Core logic usage (NOT acceptable; SSOT violation)**
   - **Logic influence**: **Preset application** - Validates step type for relax-specific operations
   - **Severity for ORCA/PySCF**: **HIGH** - Enum doesn't include ORCA/PySCF values, will fail validation

4. **`src/quantumvitas/api.py:7866-7868`** - Same as above (duplicate validation)
   - **Classification**: **Core logic usage (NOT acceptable; SSOT violation)**
   - **Logic influence**: Same as above

5. **`src/quantumvitas/api.py:1292`** - API response: `"step_type": s.step_type.value if hasattr(s.step_type, 'value') else str(s.step_type)`
   - **Classification**: Legacy coercion only (acceptable)
   - **Logic influence**: API response formatting only

6. **`src/quantumvitas/api.py:2376`** - API response: Same as above
   - **Classification**: Legacy coercion only (acceptable)
   - **Logic influence**: API response formatting only

7. **`src/quantumvitas/cli/main.py:1746`** - Standalone step creation: `step_type=StepType.from_string(spec.step_type)`
   - **Classification**: Legacy coercion only (acceptable)
   - **Logic influence**: Creates Step object with Enum, but execution reads from step.yaml

**Core Logic Violations**:

- **`src/quantumvitas/api.py:7756-7758`** and **`7866-7868`**: Enum used for **validation logic** in preset application. This is a **SSOT violation** because:
  - Enum doesn't include all step types (e.g., ORCA/PySCF values missing)
  - Should use `StepTypeRegistry` instead
  - Blocks ORCA/PySCF onboarding

**Severity for ORCA/PySCF**: **HIGH** - These validation checks will fail for ORCA/PySCF steps because Enum doesn't include their values.

#### 2.5 Mapping Logic: Public ↔ Machine

**Where mapping is performed**:

1. **`src/quantumvitas/workflow/registry.py:StepTypeRegistry.get()`** (lines 594-618)
   - Accepts both `public_type` and `machine_type`
   - Returns `StepTypeSpec` with both fields
   - **Single source of truth**: Yes, this is the only mapping location

2. **`src/quantumvitas/presets/variants_registry.py:get_variant()`** (lines 257-265)
   - Maps `machine_type` to `public_type` via `StepTypeRegistry.get()`
   - Uses `public_type` for variant lookup
   - **Single source of truth**: Yes, uses registry

3. **`src/quantumvitas/workflow/generalized_steps.py:materialize_public_step_key()`** (lines 161-212)
   - Maps `public_type` to `machine_type` via `StepTypeRegistry.get()`
   - **Single source of truth**: Yes, uses registry

**Is mapping one-to-one? conditional? family-based?**:

- **One-to-one per engine**: Each `public_type` maps to exactly one `machine_type` per engine (e.g., `"scf"` → `"qe_scf"` for QE, `"pyscf_scf"` for PySCF)
- **Family-based**: Different engines may have different `machine_type` for same `public_type`

**How unsupported steps are handled**:

- `StepTypeRegistry.get()` returns `None` if step type not found (line 618)
- Code should handle `None` case (e.g., fallback to `CUSTOM` or raise error)

**Conclusion**: Mapping is **single-source-of-truth** via `StepTypeRegistry`. No multiple mappings exist.

---

### Part 3 — ORCA/PySCF Onboarding Implications

#### 3.1 What Must Be Implemented for ORCA/PySCF Minimal Onboarding

**Where to declare supported gen steps (registry)**:
- **Location**: `src/quantumvitas/workflow/registry.py:_STEP_TYPES` dict (line ~100-558)
- **Action**: Add `StepTypeSpec` entries for ORCA/PySCF step types
- **Example**: `StepTypeSpec(id="scf", machine_type="orca_scf", public_type="scf", engine="orca", ...)`

**Where to declare supported presets/IR keys**:
- **Location**: `src/quantumvitas/presets/variants_registry.py:VARIANT_BY_STEP_AND_DIMENSION` (line ~100-150)
- **Action**: Add variant entries with `applies_to_step_types` including ORCA/PySCF public types
- **Note**: Variants use `public_type` strings (e.g., `"scf"`), not `machine_type` (e.g., `"orca_scf"`)

**Where to implement IR→engine params mapping**:
- **Location**: `src/quantumvitas/ir/backends/{engine}/mapping.py` (create new files)
- **Action**: Create `IR_TO_ORCA_MAPPING` or `IR_TO_PYSCF_MAPPING` dicts
- **Action**: Implement `ir_to_orca_param()` or `ir_to_pyscf_param()` functions
- **Action**: Implement `ir_params_to_orca_params()` or `ir_params_to_pyscf_params()` functions (similar to `ir_params_to_qe_params()`)

**How to preserve reversibility and SSOT**:
- **Reversibility**: Use same `match_profile()` / `compile_profile_patch()` logic (no changes needed)
- **SSOT**: IR keys remain engine-agnostic; engine-specific mapping happens at writer boundary
- **Type formatting**: IR canonical strings (`.true.`/`.false.`) must be converted to engine-specific format in writer

#### 3.2 What Must Remain Stable

- **ParamSpace semantics**: Key ownership, compile phases, oracle constraints (no changes)
- **species_map SSOT**: Calculation-level `species_map` remains authoritative (no changes)
- **Execution mode boundaries**: Project/standalone/compat boundaries unchanged (no changes)
- **Type formatting boundary**: ParamSpace writes IR canonical strings; engine writers convert to engine format (no changes)

#### 3.3 Risks if IR is QE-Canonical Strings (Confirmed)

**Since IR == QE-canonical strings (`.true.`/`.false.`)**:

**Risk**: ORCA/PySCF may use different boolean representations (e.g., `True`/`False` in Python, `1`/`0` in input files).

**Solution**: Engine writers must convert IR canonical strings to engine-specific format:
- **ORCA**: May use `True`/`False` in Python input, or `1`/`0` in input file
- **PySCF**: May use `True`/`False` in Python input
- **Writer responsibility**: `ir_to_orca_param()` or `ir_to_pyscf_param()` must handle boolean conversion

**Practical consequence**: IR canonical strings (`.true.`/`.false.`) are QE-specific. For ORCA/PySCF, engine writers must convert to engine-specific format. This is acceptable because conversion happens at writer boundary (not in ParamSpace core).

**Recommendation**: Keep IR canonical strings as QE format for now. When IR diverges for ORCA/PySCF, either:
- Option A: Keep IR canonical strings QE-specific, convert in engine writers
- Option B: Introduce engine-agnostic IR canonical format (e.g., `"true"`/`"false"` strings), convert to engine format in writers

**Current implementation supports Option A** (IR == QE-canonical, conversion in writers).

---

### Part 4 — Final Q&A

**Q1: Does step.yaml store booleans as `.true.` strings or Python bool today?**

**Answer**: **`.true.` strings** (IR canonical format)

**Evidence**:
- `src/quantumvitas/presets/paramspace.py:601-605` converts Python `bool` to `.true.`/`.false.` strings
- `src/quantumvitas/presets/integration.py:718-719` ensures QE format before applying to StepDoc
- `tests/presets/test_integration_ir.py:177` expects `.false.` string in step.yaml

**Q2: Where exactly does `.true.` get introduced, if at all?**

**Answer**: **In ParamSpace compiler** (`compile_profile_patch()`)

**Evidence**:
- `src/quantumvitas/presets/paramspace.py:601-605` calls `ir_bool()` to convert Python `bool` to `.true.`/`.false.` strings
- This happens **before** patch is written to StepDoc
- Integration layer (`ir_params_to_qe_params()`) ensures QE format, but values are already strings

**Q3: Is runner execution ever driven by gen/public step types beyond file naming?**

**Answer**: **NO** - Runner execution uses spec/machine types only

**Evidence**:
- `src/quantumvitas/calculation/step.py:Step.run()` reads `step_type_value = self.step_type.value` (line 92), but this is from `Step.step_type` Enum (legacy)
- **Actual execution**: `engine.backend.run_step()` receives `step_type_value` (line 113), but engine reads from step.yaml directly
- `src/quantumvitas/engine/pyscf_engine.py:474-483` explicitly reads `machine_type` from step.yaml (not from `Step.step_type` Enum)
- `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` uses `machine_type` for routing (lines 747-772)

**Conclusion**: Runner execution is driven by **spec/machine types** from step.yaml, not gen/public types.

**Q4: How many step vocabularies are effectively "real" today?**

**Answer**: **Two real vocabularies** (gen/public and spec/machine). Enum is legacy-only.

**Evidence**:
- **Gen/public**: Used by presets, UI, file naming (real vocabulary)
- **Spec/machine**: Used by step.yaml storage, runner execution, materialization (real vocabulary)
- **Enum**: Used only for coercion/validation, not execution (legacy compatibility layer)

**Q5: Where does StepType Enum still affect behavior (if any)?**

**Answer**: **Two locations** affect core logic (SSOT violations):

1. **`src/quantumvitas/api.py:7756-7758`** - Validation for relax operations
   - **Impact**: Blocks ORCA/PySCF steps from using relax operations
   - **Fix**: Replace with `StepTypeRegistry` lookup

2. **`src/quantumvitas/api.py:7866-7868`** - Same validation (duplicate)
   - **Impact**: Same as above
   - **Fix**: Replace with `StepTypeRegistry` lookup

**All other Enum usages**: Legacy coercion only (acceptable).

**Q6: What is the cleanest ORCA/PySCF path given the current IR truth?**

**Answer**: **Path A (Recommended)**:

1. **Add step types to registry**: `_STEP_TYPES` dict in `workflow/registry.py`
2. **Add variants for presets**: `VARIANT_BY_STEP_AND_DIMENSION` in `variants_registry.py` (use public types)
3. **Create IR→engine mapping**: `ir/backends/{engine}/mapping.py` with `IR_TO_{ENGINE}_MAPPING`
4. **Implement engine writers**: Convert IR canonical strings (`.true.`/`.false.`) to engine-specific format
5. **Fix Enum validation**: Replace `StepType` Enum checks with `StepTypeRegistry` lookups

**Path B (Alternative - if IR diverges)**:

- Introduce engine-agnostic IR canonical format (e.g., `"true"`/`"false"` strings)
- Convert to engine-specific format in writers
- **Risk**: Requires changing ParamSpace compiler to use new canonical format

**Recommendation**: **Use Path A** (keep IR == QE-canonical, convert in writers). This requires minimal changes and preserves existing contracts.

---

## 1. Executive Summary

### What is stable and correct

- **ParamSpace core semantics restored (baac796-era)**: Key ownership enforcement, reversibility contract, multi-phase compilation, and oracle mechanism are implemented and guarded by tests.
- **species_map SSOT for project runs**: Calculation-level `species_map` is authoritative; step-level `species_overrides` are ignored with warnings.
- **Execution mode boundaries**: Project run (YAML SSOT, clean rewrite), standalone (debug/test), and compat playback (tutorial) are clearly separated.
- **Type formatting boundary**: ParamSpace/IR operate in IR-native types; engine writers convert to engine-specific canonical strings (e.g., `.true.`/`.false.`).
- **Step type mapping**: `StepTypeRegistry` provides public_type ↔ machine_type mapping; preset lookups use public_type via `get_variant()`.

### What is still risky / inconsistent

- **StepType Enum still exists**: `src/quantumvitas/calculation/types.py:StepType` (Enum) coexists with `StepTypeRegistry` (string-based). Some code paths may still use Enum.
- **IR mapping is 1:1 with QE**: Current IR keys are QE-equivalent. When IR diverges (ORCA/PySCF), mapping layer must be extended.
- **QE parameter catalog JSON**: Used for UI/validation but not for preset compilation (presets use hardcoded variants). Risk: catalog and presets can drift.
- **Runtime-managed keys**: `prefix`, `outdir`, `pseudo_dir` are injected during materialization. Contract is clear but implementation scattered.

### Top 5 invariants the code currently enforces

1. **Key ownership uniqueness**: Each `(section, key)` belongs to exactly one ParamSpace. Enforced by `register_paramspace()` and `check_key_access()` (`src/quantumvitas/presets/paramspace.py:168-254`).
2. **Reversibility**: `match_profile()` → `compile_profile_patch()` → `match_profile()` must be idempotent. Guarded by `tests/unit/test_paramspace_contract.py`.
3. **species_map SSOT**: Project runs require `calculation.yaml` `species_map`; step-level `species_overrides` are ignored. Enforced by `src/quantumvitas/calculation/structure_steps.py:1134-1187`.
4. **Compile phase ordering**: Prerequisite dimensions (occupations_scheme, magnetism) compile before dependent ones (precision). Enforced by `src/quantumvitas/presets/integration.py:414-576`.
5. **Type formatting boundary**: ParamSpace writes IR-native types; `ir_bool()` converts to canonical strings. Enforced by `src/quantumvitas/presets/paramspace.py:601-605` and `src/quantumvitas/ir/backends/qe/mapping.py:14-41`.

---

## 2. Current Non-Negotiable Contracts (as Implemented)

### 2.1 ParamSpace Restored Semantics (baac796-era)

**Evidence**:
- **Key ownership registry**: `src/quantumvitas/presets/paramspace.py:162-205`
  - Global registry: `_KEY_OWNERSHIP: Dict[Tuple[str, str], str]` maps `(section, key)` → `paramspace_name`
  - Registration: `register_paramspace()` (line 168-205) enforces uniqueness
  - Enforcement: `check_key_access()` (line 207-254) raises `KeyAccessError` on violations
- **Reversibility**: `src/quantumvitas/presets/paramspace.py:461-534` (match), `541-612` (compile)
  - Match: `match_profile()` compares effective values against profile cells
  - Compile: `compile_profile_patch()` writes VALUE cells, deletes NOT_APPLICABLE cells
  - Guardian test: `tests/unit/test_paramspace_contract.py`
- **Multi-phase compilation**: `src/quantumvitas/presets/integration.py:414-576`
  - Phase 1 (prerequisite): `occupations_scheme`, `magnetism` (lines 437-472)
  - Phase 2 (dependent): `precision`, `convergence` (lines 490-575)
  - Oracle created at line 622, passed to `apply_invariants()` at line 629

**Contract**: ParamSpace core semantics MUST NOT be changed; only thin adapters allowed at boundaries.

### 2.2 Reversibility (match vs custom)

**Evidence**:
- **Match logic**: `src/quantumvitas/presets/paramspace.py:461-534`
  - Returns profile name if all owned keys match, `None` (custom) otherwise
  - Uses `get_yaml_value()` with key-access enforcement (line 501)
  - Compares effective values (canonicalized) against profile cells
- **Custom detection**: `src/quantumvitas/presets/variants_registry.py:499-502`
  - If `match_profile()` returns `None`, dimension is `CUSTOM`
  - Custom dimensions are not compiled (preserves user values)
- **Guardian test**: `tests/unit/test_paramspace_contract.py` enforces idempotency

**Contract**: Match → compile → match must be idempotent. If a preset is detected, compiling it must produce no changes.

### 2.3 species_map SSOT (project runs)

**Evidence**:
- **Detection**: `src/quantumvitas/calculation/structure_steps.py:1134`
  - `is_project_run = (calculation_dir and project_root and calc_model is not None)`
- **Enforcement**: Lines 1147-1187
  - Missing `species_map` → `ValueError` (lines 1152-1158)
  - Incomplete `species_map` (missing element or placeholder) → `ValueError` (lines 1180-1187)
  - Step-level `species_overrides` warning (lines 1139-1143)
- **Shared API**: `src/quantumvitas/calculation/species_config.py:configure_species_map()` (line 22-124)
  - Used by CLI (`src/quantumvitas/cli/main.py:3159`) and QVService (`src/quantumvitas/api.py:8016`)

**Contract**: For project runs, ONLY `calculation.yaml: species_map` is authoritative. Step-level `species_overrides` are ignored (warning emitted).

### 2.4 Execution Mode Split (project/standalone/compat)

**Evidence**:
- **Project run**: `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` (line 671-1797)
  - SSOT: `step.yaml` → generates `.in` clean rewrite
  - Runtime overrides: `prefix`, `outdir`, `pseudo_dir` set during materialization (lines 1188-1200)
- **Standalone**: `src/quantumvitas/cli/main.py:_run_standalone_step()` (line ~1700+)
  - Import `.in` → temporary `step.yaml` → run using production pipeline (roundtrip)
- **Compat playback**: `src/quantumvitas/calculation/compat_executor.py:run_qe_step_from_existing_input_compat()` (line 22-285)
  - Opt-in via `compat_input_playback=True` flag
  - Patches only 3 CONTROL keys: `prefix`, `outdir`, `pseudo_dir`
  - Pseudopotential filenames from `.in` `ATOMIC_SPECIES` (not `step.yaml`)

**Contract**: Production run never parses `.in` files during execution. Standalone is import→YAML→run roundtrip. Compat playback is test-only.

### 2.5 Runtime-Managed QE Keys (prefix/outdir/pseudo_dir)

**Evidence**:
- **Materialization**: `src/quantumvitas/calculation/structure_steps.py:1188-1200`
  - `set_outdir_to_temp()` and `set_pseudo_dir_in_input()` called during `materialize_step_spec()`
- **Pseudo staging**: `src/quantumvitas/core/pseudo.py:ensure_qe_pseudos()` (line 171-301)
  - Copies required UPFs from `system_pseudo_dir` to `project_pseudo_dir`
  - Raises `ValueError` if placeholders found (line 293-300)

**Contract**: Runtime-managed keys are injected during materialization, not during preset compilation. They override YAML values.

### 2.6 Type Formatting Boundary (IR-native vs QE canonical strings)

**Evidence**:
- **ParamSpace compile**: `src/quantumvitas/presets/paramspace.py:601-605`
  - Converts Python `bool` to IR canonical string using `ir_bool()` before writing patch
- **IR canonical encoder**: `src/quantumvitas/ir/backends/qe/mapping.py:14-41`
  - `ir_bool()` converts `True`/`False` → `.true.`/`.false.`
- **QE writer**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (line 92-124)
  - Converts IR values to QE format (boolean strings for specific keys)

**Contract**: ParamSpace/IR operate in IR-native types (Python `bool`/`float`/`int`/`str`). Engine writers convert to engine-specific canonical strings.

---

## 3. Terminology Grounded in Code

### 3.1 ParamSpace, Dimension, Variant, Key, Ownership Registry

**ParamSpace**: `src/quantumvitas/presets/paramspace.py:298-372`
- Dataclass with `name`, `keys` (list of `ParamKey`), `profiles` (dict of profile_name → cells)
- Example: `get_magnetism_paramspace()` returns ParamSpace for magnetism dimension

**Dimension**: String identifier (e.g., `"precision"`, `"magnetism"`). Defined in `src/quantumvitas/presets/dimensions.py`.

**Variant**: `src/quantumvitas/presets/space_variant.py:ParamSpaceVariant` (line 16-51)
- Wraps a ParamSpace with `applies_to_step_types` (frozenset of public step types)
- Example: `PRECISION_PW_DEFAULT_VARIANT` applies to `{"scf", "relax", "vc-relax", "md", "vc-md"}`

**Key**: `src/quantumvitas/presets/paramspace.py:ParamKey` (line 59-121)
- Represents `(section, key)` tuple with parser, canonicalizer, tolerance, aliases, default
- Example: `ParamKey(section="SYSTEM", key="ecutwfc", parser=parse_float, ...)`

**Ownership Registry**: `src/quantumvitas/presets/paramspace.py:162-205`
- `_KEY_OWNERSHIP: Dict[Tuple[str, str], str]` maps `(section, key)` → `paramspace_name`
- `register_paramspace()` enforces uniqueness (raises `RuntimeError` on conflict)

### 3.2 Preset, Profile, ParamSpace Compiler Phase, Oracle

**Preset**: User-facing option (e.g., `"high"`, `"medium"`, `"low"` for precision). Mapped to profile name via `ENUM_TO_PROFILE` (`src/quantumvitas/presets/variants_registry.py:233-238`).

**Profile**: Named set of cells in a ParamSpace (e.g., `"LOW"`, `"MED"`, `"HIGH"`). Defined in `paramspace.profiles` dict.

**ParamSpace Compiler Phase**: `src/quantumvitas/presets/integration.py:414-576`
- Phase 1 (prerequisite): `occupations_scheme`, `magnetism` (lines 437-472)
- Phase 2 (dependent): `precision`, `convergence` (lines 490-575)
- Ordering is hardcoded in `apply_presets_to_step()`

**Oracle**: `src/quantumvitas/presets/oracle.py:Oracle` (line 18-60)
- Read-only semantic prerequisite queries
- Example: `oracle.degauss_applicability()` returns `True` iff `SYSTEM.occupations == "smearing"`
- Created at `src/quantumvitas/presets/integration.py:622`, passed to `apply_invariants()` at line 629

### 3.3 IR (What Counts as IR in Code Today)

**IR Definition**: `src/quantumvitas/presets/paramspace.py:ParamKey` docstring (lines 64-71)
- "ParamSpace operates on IR keys (IR is SSOT). In v0, IR keys == QE keys due to 1:1 mapping"
- IR sections: `"SYSTEM"`, `"ELECTRONS"`, `"cards"` (same as QE sections in v0)
- IR keys: Parameter names (e.g., `"ecutwfc"`, `"nspin"`) that match QE keys in v0

**IR Mapping**: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
- Maps IR keys to `(qe_module, qe_section, qe_key)` tuples
- In v0, mapping is 1:1 (IR key == QE key for most parameters)

**IR YAML Structure**: `step.yaml` `parameters` section is IR-compatible
- Format: `parameters: {SYSTEM: {ecutwfc: 60.0}, ELECTRONS: {conv_thr: 1e-6}}`
- Cards: `cards: {K_POINTS: {option: "automatic", data: [...]}}`

### 3.4 Engine Parameter (QE Sections/Keys)

**QE Sections**: Namelists (e.g., `&SYSTEM`, `&ELECTRONS`) and cards (e.g., `K_POINTS`, `ATOMIC_SPECIES`).

**QE Keys**: Parameter names within namelists (e.g., `ecutwfc`, `nspin`) or card names.

**QE Parameter Catalog**: `src/quantumvitas/data/qe_module_parameters.json`
- Schema v3: `modules → parameters` map
- Each parameter has: `namelist`, `name`, `type`, `default`, `enum`, `description`
- Used by UI (`src/quantumvitas/api.py:list_qe_ui_parameters`) and validation

### 3.5 Gen Step vs Spec Step vs StepType Enum

**Gen Step (public_type)**: Generalized step type string (e.g., `"scf"`, `"nscf"`). Used in APIs/UI and preset lookups.

**Spec Step (machine_type)**: Engine-prefixed step type string (e.g., `"qe_scf"`, `"w90_run"`). Stored in `step.yaml` `step_type` field.

**StepType Enum**: `src/quantumvitas/calculation/types.py:StepType` (line 10-30)
- Legacy Enum with values like `StepType.SCF = "scf"`
- Still used in some code paths (e.g., `src/quantumvitas/calculation/step.py:29`)

**StepTypeRegistry**: `src/quantumvitas/workflow/registry.py:StepTypeRegistry` (line 566-640)
- Provides `get()` method that accepts both `public_type` and `machine_type`
- Returns `StepTypeSpec` with both `public_type` and `machine_type` fields

---

## 4. ParamSpace Deep Dive (CORE)

### 4.1 Data Model: Dimension / Variant / Key and Relationships

**Where defined**:
- **Dimension**: String constant in `src/quantumvitas/presets/dimensions.py` (e.g., `DIMENSION_PRECISION = "precision"`)
- **Variant**: `src/quantumvitas/presets/space_variant.py:ParamSpaceVariant` (line 16-51)
- **Key**: `src/quantumvitas/presets/paramspace.py:ParamKey` (line 59-121)
- **ParamSpace**: `src/quantumvitas/presets/paramspace.py:ParamSpace` (line 298-372)

**How variant selection works**:
- `src/quantumvitas/presets/variants_registry.py:get_variant()` (line 245-268)
  - Maps `machine_type` to `public_type` via `StepTypeRegistry.get()` (lines 260-265)
  - Looks up variant by `(step_type, dimension)` key in `VARIANT_BY_STEP_AND_DIMENSION` (line 267-268)

**How dimensions map to keys**:
- Each ParamSpace declares owned keys via `keys` list (line 305)
- `owned_keys()` method returns `Set[Tuple[str, str]]` of `(section, key)` tuples (line 308-317)
- Example: Precision ParamSpace owns `("SYSTEM", "ecutwfc")`, `("SYSTEM", "ecutrho")`, `("ELECTRONS", "conv_thr")`

**How key ownership is registered and enforced**:
- Registration: `register_paramspace()` (line 168-205) adds entries to `_KEY_OWNERSHIP` dict
- Enforcement: `check_key_access()` (line 207-254) raises `KeyAccessError` if current ParamSpace doesn't own the key
- Context: `ParamSpaceContext` (line 257-296) sets current ParamSpace via context variable

### 4.2 Compile Pipeline + Oracle

**Where compile phases are defined and executed**:
- `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328-997)
  - Phase 1 (prerequisite): Lines 437-472
  - Phase 2 (dependent): Lines 490-575

**How ordering is expressed in code**:
- Hardcoded lists: `prerequisite_dimensions` (lines 417-420) and `dependent_dimensions` (lines 421-424)
- Phase 1 patches are applied to `step_yaml` before Phase 2 (lines 474-488) so oracle can read latest state

**Oracle: what interface is provided, what information it can access, who calls it**:
- Interface: `src/quantumvitas/presets/oracle.py:Oracle` (line 18-60)
  - Methods: `degauss_applicability()` returns `True` iff `SYSTEM.occupations == "smearing"`
- Information access: Oracle reads `yaml_state` dict (IR YAML structure) passed to constructor
- Who calls it: `apply_invariants()` methods (e.g., `precision_space.apply_invariants()` at line 629)

**Evidence of "pre/post" behavior**:
- Phase 1 patches are merged into `step_yaml` (lines 474-488) before Phase 2 compilation
- Oracle is created with updated `current_yaml_state` (line 622) that includes Phase 1 patches
- Precision `apply_invariants()` uses oracle to check `degauss_applicability()` (line 975)

### 4.3 Apply Path (preset → ParamSpace → patches → YAML)

**Entrypoint(s)**:
- CLI: `src/quantumvitas/cli/main.py:configure_presets_command()` (calls `apply_presets_to_step()`)
- QVService: `src/quantumvitas/api.py:QVService.apply_presets_to_step()` (calls `apply_presets_to_step()`)
- Direct: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328)

**Where patches are computed**:
- `src/quantumvitas/presets/variants_registry.py:compile_dimension_patch_for_step()` (line 271-335)
  - Calls `compile_profile_patch()` (line 330) within `ParamSpaceContext` (line 329)
- `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (line 541-612)
  - Iterates over profile cells, writes VALUE cells, marks NOT_APPLICABLE for deletion

**Where patches are written**:
- `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328-997)
  - Unified patch is built (lines 427-575), then applied to `StepDoc` via `doc.apply_patch()` (line 680-690)

**Confirm patch value types at each boundary**:
- ParamSpace compile: Writes IR-native types (Python `bool`/`float`/`int`/`str`), but converts `bool` to IR canonical string via `ir_bool()` (line 601-605)
- Integration layer: Receives IR patch, applies to `StepDoc` (IR YAML structure)
- StepDoc: Stores IR YAML (in v0, IR == QE, so values are QE-compatible)

### 4.4 Reverse Inference Path (YAML → inferred preset/profile/custom)

**What "match" means**:
- `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534)
  - Compares all owned keys against profile cells
  - VALUE cells: effective value must match expected value (after canonicalization)
  - NOT_APPLICABLE cells: key must be absent
  - WILDCARD cells: ignored
  - Returns profile name if all keys match, `None` otherwise

**What triggers "custom"**:
- `src/quantumvitas/presets/variants_registry.py:detect_dimension_for_step()` (line 485-520)
  - If `match_profile()` returns `None`, dimension is `CUSTOM` (line 501-502)
  - Custom dimensions are not compiled (user values preserved)

**How unknown parameters are handled in inference**:
- Unknown parameters (not owned by any ParamSpace) are ignored during matching
- They remain in YAML unchanged (not touched by preset system)

**List guardian tests**:
- `tests/unit/test_paramspace_contract.py`: Reversibility (match → compile → match idempotency)
- `tests/unit/test_key_access_enforcement.py`: Key ownership enforcement
- `tests/unit/test_paramspace_invariants.py`: `apply_invariants()` behavior and compile ordering
- `tests/unit/test_preset_integration.py`: Two-phase compilation and oracle usage

### 4.5 Thin Adapter Layer (QE↔IR) — What It Is TODAY

**Is ParamSpace bridging preset↔QE parameters directly, with an adapter to IR?**
- **No**. ParamSpace operates on IR keys (IR is SSOT). In v0, IR keys == QE keys due to 1:1 mapping, but conceptually ParamSpace only knows about IR keys.

**Or is ParamSpace actually bridging preset↔IR and QE is a backend?**
- **Yes**. ParamSpace bridges preset↔IR. QE writer converts IR to QE input format.

**Where is the mapping defined**:
- `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
  - Maps IR keys to `(qe_module, qe_section, qe_key)` tuples
- `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (line 92-124)
  - Converts IR parameter to QE parameter (handles boolean string conversion)

**Is it truly 1:1 string match today**:
- **Yes, for most parameters**. IR keys match QE keys (e.g., `"ecutwfc"` → `("pw", "SYSTEM", "ecutwfc")`).
- **Exception**: Cards like `K_POINTS` map to `("pw", "cards", "K_POINTS")` (section is `"cards"`, not a namelist).

---

## 5. QE Parameter System and UI Contract

**How QE parameter catalog JSON is produced and consumed**:
- **Production**: `tools/extract_qe_parameters_v2.py` scrapes QE HTML docs, generates `src/quantumvitas/data/qe_module_parameters.json` (schema v3)
- **Consumption**: `src/quantumvitas/data/qe_metadata.py` loads JSON, provides `get_module_param_sections()` API
- **UI**: `src/quantumvitas/api.py:list_qe_ui_parameters()` (line 692-709) returns parameters for UI display

**How active/common/advanced/freeform are represented**:
- **Data model**: Not explicitly in JSON schema. UI may categorize parameters, but catalog doesn't define categories.
- **UNKNOWN**: Need to verify if UI uses separate categorization logic or if "active/common/advanced" are UI-only concepts.

**How "unknown parameter" creation works and how it round-trips**:
- **UNKNOWN**: Need to trace UI code path for creating freeform parameters. Likely stored in `step.yaml` `parameters` section, but validation may reject if not in catalog.

**How values are typed and stored in step.yaml**:
- **Storage**: `step.yaml` `parameters` section stores values as YAML primitives (string, number, boolean)
- **Type inference**: QE catalog provides `type` field (`CHARACTER`, `INTEGER`, `REAL`, `LOGICAL`), but YAML doesn't enforce types
- **Boolean handling**: IR canonical format (`.true.`/`.false.`) stored as strings in YAML

**Any normalization/canonicalization steps**:
- **ParamSpace canonicalization**: `ParamKey.canonicalize()` (line 86-100) applies aliases and canonicalizer
- **Boolean canonicalization**: `ir_bool()` converts to `.true.`/`.false.` during compile (line 601-605)
- **QE writer**: `ir_to_qe_param()` converts boolean values to QE string format (line 118-122)

---

## 6. Materialization & Runner Pipeline Fidelity (Project Mode)

**Trace end-to-end**:
1. **step.yaml + calculation.yaml + project resources**:
   - `step.yaml` loaded via `StructureStepSpec.from_yaml()` (`src/quantumvitas/calculation/structure_steps.py:487-665`)
   - `calculation.yaml` `species_map` loaded via `Calculation.species_map` property
2. **materialized spec**:
   - `materialize_step_spec()` (line 671-1797) generates `QEInput` from spec
   - Runtime overrides applied: `set_outdir_to_temp()`, `set_pseudo_dir_in_input()` (lines 1188-1200)
3. **generated .in**:
   - `QEInputGenerator.write_file()` writes `.in` file (clean rewrite, no read-append)
4. **run command**:
   - `Step.run()` (line 63-135) calls `engine.backend.run_step()` directly (no re-parsing)

**Confirm .in generation is clean rewrite**:
- **Evidence**: `src/quantumvitas/io/generator.py:QEInputGenerator.write_file()` writes fresh `.in` file from `QEInput` object. No parsing of existing `.in` files during production run.

**Confirm runtime-managed keys override behavior**:
- **Evidence**: `src/quantumvitas/calculation/structure_steps.py:1188-1200`
  - `set_outdir_to_temp()` sets `CONTROL.outdir` to `"./outdir"`
  - `set_pseudo_dir_in_input()` sets `CONTROL.pseudo_dir` to `project_root/pseudo` (relative or absolute)

**Confirm pseudo staging**:
- **Only required UPFs staged**: `src/quantumvitas/core/pseudo.py:ensure_qe_pseudos()` (line 171-301)
  - Copies files from `system_pseudo_dir` to `project_pseudo_dir` based on `species_map` entries
- **pseudo_dir points to project/pseudo**: `src/quantumvitas/calculation/structure_steps.py:1188-1200`
  - `set_pseudo_dir_in_input()` sets `CONTROL.pseudo_dir` to `project_root/pseudo`
- **calc species_map authoritative**: `src/quantumvitas/calculation/structure_steps.py:1134-1187`
  - Project run detection requires `species_map`; step-level `species_overrides` are ignored (warning emitted)

**step-level species_overrides warning path**:
- **Evidence**: `src/quantumvitas/calculation/structure_steps.py:1139-1143`
  - Warning emitted if `spec.species_overrides` is present in project run
  - Warning message: "Step-level species_overrides detected in step.yaml. Project runs ignore step species_overrides and use calculation.yaml species_map instead."

---

## 7. Execution Modes Inventory and Boundaries

### 7.1 Project Run (Production)

**SSOT**: `step.yaml` (spec truth)

**Files read/written**:
- Read: `step.yaml`, `calculation.yaml`, structure files
- Write: Generated `.in` file (versioned, e.g., `scf-1.in`)

**Warnings/errors expected**:
- Warning: Step-level `species_overrides` detected (if present)
- Error: Missing or incomplete `species_map` in `calculation.yaml`

**Mode leakage risks**:
- Risk: If `existing_input_file` is passed, it may be parsed and merged (but code explicitly ignores it in production run - line 666-680 in `calculation.py`)

### 7.2 Standalone Step Mode (Debug/Test)

**SSOT**: Temporary `step.yaml` created from imported `.in` file

**Files read/written**:
- Read: Standalone `.in` file (imported)
- Write: Temporary `step.yaml`, then generated `.in` file

**Warnings/errors expected**:
- No warnings (standalone mode allows `species_overrides`)

**Mode leakage risks**:
- Risk: Standalone mode may be used for normal project steps (should be prevented by API contract)

### 7.3 Compat Input Playback (Tutorial/Tests)

**SSOT**: Existing `.in` input files (referenced in `calculation.yaml` `steps[].input`)

**Files read/written**:
- Read: Existing `.in` file (from `calculation.yaml` `steps[].input`)
- Write: Patched `.in` file (only 3 CONTROL keys patched: `prefix`, `outdir`, `pseudo_dir`)

**Warnings/errors expected**:
- No warnings (compat mode is test-only)

**Mode leakage risks**:
- Risk: Compat mode may be triggered in production if `compat_input_playback=True` flag is set (should be test-only)

---

## 8. Gen Step vs Spec Step Audit (NEW — Go Deep)

### 8.1 Vocabulary Inventory

**StepType Enum values**:
- `src/quantumvitas/calculation/types.py:StepType` (line 10-30)
  - Values: `SCF = "scf"`, `NSCF = "nscf"`, `DOS = "dos"`, `BANDS_PW = "bands_pw"`, `BANDS = "bands"`, `PH = "ph"`, `Q2R = "q2r"`, `MATDYN = "matdyn"`, `DYNMAT = "dynmat"`, `PP = "pp"`, `PROJWFC = "projwfc"`, `RELAX = "relax"`, `VC_RELAX = "vc-relax"`, `W90_PREPROC = "w90_preproc"`, `PW2WANNIER90 = "pw2wannier90"`, `W90_RUN = "w90_run"`, `PYSCF_SCF = "pyscf_scf"`, `CUSTOM = "custom"`

**public_type / gen step strings**:
- Defined in `src/quantumvitas/workflow/registry.py:StepTypeSpec` (line 23-58)
  - `public_type` field (alias for `id`) stores generalized step type (e.g., `"scf"`, `"nscf"`)
  - Used in APIs/UI and preset lookups

**machine_type / spec step strings**:
- Defined in `src/quantumvitas/workflow/registry.py:StepTypeSpec` (line 23-58)
  - `machine_type` field stores engine-prefixed step type (e.g., `"qe_scf"`, `"w90_run"`)
  - Stored in `step.yaml` `step_type` field

**Legacy names**:
- Some code may still use lowercase strings without engine prefix (e.g., `"scf"` instead of `"qe_scf"`)
- `StepTypeRegistry.get()` accepts both `public_type` and `machine_type` for backward compatibility

### 8.2 Where Gen Steps Are Used (Actual Call Sites)

**In YAML/meta or runtime models**:
- `calculation.yaml` `steps[].type` field stores public_type (normalized from machine_type in `CalculationStepEntry.from_dict()` - line 188-197 in `core/models.py`)
- `step.yaml` `step_type` field stores machine_type (but preset lookups map to public_type)

**In UI**:
- `src/quantumvitas/api.py:list_workflow_templates()` (line ~3437) uses `normalize_step_type_to_public()` to convert machine_type to public_type for display

**In preset/ParamSpace compilation targeting steps**:
- `src/quantumvitas/presets/variants_registry.py:get_variant()` (line 245-268)
  - Maps `machine_type` to `public_type` via `StepTypeRegistry.get()` (lines 260-265)
  - Variant lookup uses `public_type` (line 267)

### 8.3 Where Spec Steps Are Used (Actual Call Sites)

**Where machine_type is stored**:
- `step.yaml` `step_type` field stores machine_type (e.g., `"qe_scf"`)

**Where it determines engine writer behavior**:
- `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` (line 671-1797)
  - Checks `step_type_lower` to determine if step is Wannier90, PySCF, or ORCA (lines 747-772)
  - Routes to appropriate input generator based on engine family

**Where it determines runner execution (binary selection)**:
- `src/quantumvitas/engine/qe_engine.py:QeEngine.run_step()` uses `step_type` to select executable (e.g., `pw.x` for `qe_scf`, `bands.x` for `qe_bands`)

### 8.4 Mapping Logic: Gen/Public ↔ Machine/Spec

**What module performs mapping**:
- `src/quantumvitas/workflow/registry.py:StepTypeRegistry` (line 566-640)
  - `get()` method (line 594-618) accepts both `public_type` and `machine_type`, returns `StepTypeSpec`

**Is the mapping one-to-one? conditional? family-based?**:
- **One-to-one**: Each `public_type` maps to exactly one `machine_type` per engine (e.g., `"scf"` → `"qe_scf"` for QE engine)
- **Family-based**: Different engines may have different `machine_type` for same `public_type` (e.g., `"scf"` → `"qe_scf"` for QE, `"pyscf_scf"` for PySCF)

**How unsupported steps are handled**:
- `StepTypeRegistry.get()` returns `None` if step type not found (line 618)
- Code should handle `None` case (e.g., fallback to `CUSTOM` or raise error)

### 8.5 SSOT Risk Assessment

**Are there more than two step-type "truth sources"?**
- **Yes, three sources**:
  1. `StepTypeRegistry` (string-based, `public_type` ↔ `machine_type` mapping)
  2. `StepType` Enum (legacy, used in some code paths)
  3. Hardcoded strings in variant definitions (e.g., `applies_to_step_types=frozenset({"scf", "nscf"})`)

**Where does StepType Enum still leak into places it shouldn't?**
- `src/quantumvitas/calculation/step.py:29` - `step_type: Optional[StepType] = None`
- `src/quantumvitas/calculation/runner.py:50-77` - `_coerce_step_type()` converts string to Enum

**What are the top 3 risks for ORCA/PySCF extension?**
1. **Variant definitions use hardcoded public_type strings**: `applies_to_step_types` in variants must be updated for new engines
2. **StepType Enum doesn't include ORCA/PySCF values**: Enum may need extension or deprecation
3. **IR mapping is QE-specific**: `IR_TO_QE_MAPPING` must be extended or replaced with engine-agnostic mapping

---

## 9. Risk Register (Post-Detour)

1. **StepType Enum coexistence with StepTypeRegistry**
   - **Risk**: Code paths may use Enum instead of Registry, causing inconsistencies
   - **Evidence**: `src/quantumvitas/calculation/step.py:29`, `src/quantumvitas/calculation/runner.py:50-77`
   - **Impact**: Medium - may cause step type resolution failures
   - **Suggested follow-up**: Audit all Enum usages, migrate to Registry

2. **IR mapping is QE-specific (1:1 today)**
   - **Risk**: When IR diverges for ORCA/PySCF, mapping layer must be extended
   - **Evidence**: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
   - **Impact**: High - blocks ORCA/PySCF onboarding
   - **Suggested follow-up**: Design engine-agnostic IR mapping or extend mapping for each engine

3. **QE parameter catalog and presets can drift**
   - **Risk**: Catalog (JSON) and presets (hardcoded variants) are separate; may become inconsistent
   - **Evidence**: Catalog in `src/quantumvitas/data/qe_module_parameters.json`, presets in `src/quantumvitas/presets/variants_registry.py`
   - **Impact**: Medium - UI may show parameters not in presets, or presets may use parameters not in catalog
   - **Suggested follow-up**: Verify catalog coverage of preset-owned keys

4. **Variant definitions use hardcoded public_type strings**
   - **Risk**: New engines require manual updates to variant `applies_to_step_types`
   - **Evidence**: `src/quantumvitas/presets/variants_registry.py:48-100` (variant definitions)
   - **Impact**: Medium - slows down engine onboarding
   - **Suggested follow-up**: Consider engine-family-based variant selection

5. **Runtime-managed keys scattered across codebase**
   - **Risk**: `prefix`, `outdir`, `pseudo_dir` injection logic may be inconsistent
   - **Evidence**: `src/quantumvitas/calculation/structure_steps.py:1188-1200`, `src/quantumvitas/core/pseudo.py:ensure_qe_pseudos()`
   - **Impact**: Low - contract is clear, but implementation could be centralized
   - **Suggested follow-up**: Centralize runtime key injection in single function

6. **Unknown parameter creation round-trip unclear**
   - **Risk**: UI may allow creating parameters not in catalog, but validation may reject them
   - **Evidence**: UNKNOWN - need to trace UI code path
   - **Impact**: Low - affects UX, not core functionality
   - **Suggested follow-up**: Trace UI freeform parameter creation and validation path

7. **Compat playback mode may leak into production**
   - **Risk**: `compat_input_playback=True` flag may be set in production code paths
   - **Evidence**: `src/quantumvitas/calculation/runner.py:140` (flag definition), `src/quantumvitas/execution/handlers.py:190-200` (flag check)
   - **Impact**: Low - flag is explicit opt-in, but should be test-only
   - **Suggested follow-up**: Add guard to prevent compat mode in production

8. **Step-level species_overrides warning may be ignored**
   - **Risk**: Users may not notice warning, continue using step-level overrides
   - **Evidence**: `src/quantumvitas/calculation/structure_steps.py:1139-1143` (warning only, not error)
   - **Impact**: Low - warning is sufficient, but migration path unclear
   - **Suggested follow-up**: Document migration path from step-level to calc-level species_map

9. **Oracle interface is minimal (only degauss_applicability)**
   - **Risk**: Future cross-space dependencies may require more oracle methods
   - **Evidence**: `src/quantumvitas/presets/oracle.py:Oracle` (line 18-60) - only one method
   - **Impact**: Low - current design is sufficient, but may need extension
   - **Suggested follow-up**: Monitor for new cross-space dependencies

10. **Type formatting boundary may be violated**
    - **Risk**: Code may write Python `bool` directly to YAML instead of using `ir_bool()`
    - **Evidence**: `src/quantumvitas/presets/paramspace.py:601-605` (converts bool to string), but other code paths may bypass
    - **Impact**: Medium - may cause `.true.` vs `True` mismatches
    - **Suggested follow-up**: Add linter check to enforce `ir_bool()` usage for boolean values

11. **Materialization path for non-QE engines unclear**
    - **Risk**: Wannier90, PySCF, ORCA steps may bypass QE input generation, but materialization contract may assume QE
    - **Evidence**: `src/quantumvitas/calculation/structure_steps.py:777-850` (Wannier90 path), `767-772` (PySCF/ORCA detection)
    - **Impact**: Medium - may cause issues when adding new engines
    - **Suggested follow-up**: Document materialization contract for non-QE engines

12. **StepTypeRegistry lookup may fail silently**
    - **Risk**: If `StepTypeRegistry.get()` returns `None`, code may not handle gracefully
    - **Evidence**: `src/quantumvitas/presets/variants_registry.py:262-265` (returns `None` if spec not found)
    - **Impact**: Low - code checks for `None`, but error messages may be unclear
    - **Suggested follow-up**: Add clear error messages for unsupported step types

---

## 10. Implications for ORCA/PySCF Onboarding (Bounded)

### What to Implement at Engine Boundary

- **IR→engine params mapping responsibility**: Create `src/quantumvitas/ir/backends/orca/mapping.py` (or `pyscf/mapping.py`) with `IR_TO_ORCA_MAPPING` (or `IR_TO_PYSCF_MAPPING`) dict
- **Engine-specific input writer**: Implement `generate_orca_input_from_spec()` (or `generate_pyscf_input_from_spec()`) that converts IR YAML to engine input format
- **StepTypeRegistry entries**: Add ORCA/PySCF step types to `_STEP_TYPES` dict in `src/quantumvitas/workflow/registry.py`

### What Must Remain Stable

- **ParamSpace core**: Key ownership, reversibility, compile phases, oracle mechanism
- **Reversibility tests**: `tests/unit/test_paramspace_contract.py` must remain green
- **Warning semantics**: Step-level `species_overrides` warning must remain unchanged
- **Type formatting boundary**: ParamSpace writes IR-native types; engine writers convert to engine-specific format

### Where a New Engine Should Hook In

- **Registries**: `src/quantumvitas/workflow/registry.py:StepTypeRegistry` - add step type specs
- **Resolvers**: `src/quantumvitas/workflow/generalized_steps.py:materialize_public_step_key()` - add engine family mapping
- **Materializers**: `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` - add engine-specific input generation path (similar to Wannier90 path at lines 777-850)
- **IR mapping**: `src/quantumvitas/ir/backends/{engine}/mapping.py` - create engine-specific mapping module

---

## 11. Appendix: Evidence Index

### File → Symbols → Why Relevant

**src/quantumvitas/presets/paramspace.py**:
- `ParamSpace` (line 298-372): Core ParamSpace dataclass
- `ParamKey` (line 59-121): Parameter key definition
- `register_paramspace()` (line 168-205): Key ownership registration
- `check_key_access()` (line 207-254): Key access enforcement
- `match_profile()` (line 461-534): Reverse inference
- `compile_profile_patch()` (line 541-612): Forward compilation
- `ir_bool()` usage (line 601-605): Type formatting boundary

**src/quantumvitas/presets/integration.py**:
- `apply_presets_to_step()` (line 328-997): Main apply entrypoint
- Phase 1/2 ordering (lines 414-576): Compile phase contract
- Oracle creation (line 622): Oracle interface
- `apply_invariants()` call (line 629): Invariant enforcement

**src/quantumvitas/presets/variants_registry.py**:
- `get_variant()` (line 245-268): Variant lookup with step type mapping
- `compile_dimension_patch_for_step()` (line 271-335): Patch compilation
- Variant definitions (lines 42-100): Hardcoded step type lists

**src/quantumvitas/calculation/structure_steps.py**:
- `materialize_step_spec()` (line 671-1797): Materialization pipeline
- Project run detection (line 1134): `is_project_run` logic
- species_map enforcement (lines 1147-1187): SSOT contract
- Runtime key injection (lines 1188-1200): `prefix`, `outdir`, `pseudo_dir`

**src/quantumvitas/workflow/registry.py**:
- `StepTypeSpec` (line 23-58): Step type specification
- `StepTypeRegistry` (line 566-640): Step type lookup
- `_STEP_TYPES` dict (line ~100-558): Step type definitions

**src/quantumvitas/ir/backends/qe/mapping.py**:
- `IR_TO_QE_MAPPING` (line 46-74): IR→QE mapping
- `ir_bool()` (line 14-41): IR canonical boolean encoder
- `ir_to_qe_param()` (line 92-124): IR→QE parameter conversion

**src/quantumvitas/calculation/types.py**:
- `StepType` Enum (line 10-30): Legacy step type enum

**src/quantumvitas/core/pseudo.py**:
- `ensure_qe_pseudos()` (line 171-301): Pseudopotential staging

**src/quantumvitas/calculation/species_config.py**:
- `configure_species_map()` (line 22-124): Shared species_map API

### Ripgrep Commands Used

```bash
rg -n "class Dimension|class Variant|owned_keys|KeyAccess|KeyAccessError|oracle|apply_invariants|compile_" -S src/quantumvitas/presets
rg -n "public_type|machine_type|StepType|step_type_raw|resolve_.*step|StepTypeRegistry" -S src/quantumvitas
rg -n "species_map|species_overrides|configure_species_map|pseudo_dir|ensure_qe_pseudos" -S src/quantumvitas
rg -n "qe_parameter.*json|active|common|advanced|freeform" -S src/quantumvitas
rg -n "ParamSpace|revers|oracle|compile_order|species_map|species_overrides|pseudo_dir|public_type|machine_type" -S tests
```

### Guardian Tests

- `tests/unit/test_key_access_enforcement.py`: Key ownership enforcement
- `tests/unit/test_paramspace_invariants.py`: `apply_invariants()` and compile ordering
- `tests/unit/test_paramspace_contract.py`: Reversibility (match/compile idempotency)
- `tests/unit/test_preset_integration.py`: Two-phase compilation and oracle usage

---

**End of Review**

