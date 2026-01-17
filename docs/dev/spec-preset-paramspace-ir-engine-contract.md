# Preset/ParamSpace/IR/Engine Contract Specification

**Version**: 1.0  
**Date**: 2025-01-XX  
**Status**: Authoritative System Design Spec  
**Purpose**: Define the complete contract between Preset, ParamSpace, IR, and Engine layers to enable ORCA/PySCF onboarding and prevent "double truth" violations.

---

## 1. Purpose and Design Principles

### 1.1 Purpose

This specification defines the complete system contract for:
- **Preset** (user intent, non-persisted)
- **ParamSpace** (declarative matrix, profiles/variants, ownership, compile ordering)
- **IR Dialects** (logical patch, non-persisted)
- **Engine Parameters** (step.yaml persisted spec)

The contract ensures:
- **Reversibility**: Preset detection must be reversible with compilation (match → compile → match idempotent)
- **SSOT**: Only `calculation.yaml` + `step.yaml` are persisted; all other layers are runtime-only
- **Engine Independence**: ParamSpace core remains engine-agnostic; engine-specific logic isolated to boundary adapters
- **Extensibility**: ORCA/PySCF onboarding requires only thin boundary adapters, no core changes

### 1.2 Design Principles

1. **Single Source of Truth (SSOT)**: Only persisted files (`calculation.yaml`, `step.yaml`) are SSOT. Preset/IR/Workflow/ParamSpace output is not persisted.
2. **Reversibility**: Preset detection and compilation must be idempotent. If a preset is detected, compiling it must produce no changes.
3. **Key Ownership**: Each parameter key (section.key) belongs to exactly one ParamSpace. Cross-space access requires explicit oracle queries.
4. **Engine Isolation**: ParamSpace operates on IR keys (engine-agnostic). Engine-specific mapping happens at writer boundary only.
5. **Robustness**: ParamSpace performs lightweight normalization for matching robustness, but does not redefine engine canonicalization.

**Evidence**:
- SSOT principle: `docs/dev/post-detour-deep-review-params-presets-ir-steps.md` (section 2.1)
- Reversibility: `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534), `compile_profile_patch()` (line 541-612)
- Key ownership: `src/quantumvitas/presets/paramspace.py:register_paramspace()` (line 168-205), `check_key_access()` (line 207-254)
- Engine isolation: `src/quantumvitas/presets/paramspace.py:ParamKey` docstring (lines 64-71)

---

## 2. Terminology and SSOT Boundaries

### 2.1 Core Terms

**Preset**: User-facing option (e.g., `"high"`, `"medium"`, `"low"` for precision). Mapped to profile name via `ENUM_TO_PROFILE`. Never persisted.

**ParamSpace**: Declarative data structure with keys, profiles, and compile/match algorithms. Operates on IR keys (IR is SSOT).

**Dimension**: String identifier for a physical concept (e.g., `"precision"`, `"magnetism"`). Defined in `src/quantumvitas/presets/dimensions.py`.

**Variant**: `ParamSpaceVariant` instance that binds a `ParamSpace` to specific `step_type`s via `applies_to_step_types` (frozenset of public step types).

**Profile**: Named set of cells in a ParamSpace (e.g., `"LOW"`, `"MED"`, `"HIGH"`). Defined in `paramspace.profiles` dict.

**IR Dialect**: Namespace for IR keys/values. Currently two dialects: `ir.pw` (PW implies PBC; no mol) and `ir.qc` (Quantum chemistry; AO/MOL world). Dialects are disjoint namespaces. **Note**: Dialect names are NOT engine names; they represent computational paradigms (PW vs QC).

**Engine Parameters**: Engine-specific parameter keys stored in `step.yaml` (e.g., QE namelist keys). SSOT for execution.

**Gen/Public Step Type**: Generalized step type string (e.g., `"scf"`, `"nscf"`). Used for UI + ParamSpace scope.

**Spec/Machine Step Type**: Engine-prefixed step type string (e.g., `"qe_scf"`, `"orca_scf"`). Used for persisted execution + engine dispatch.

**Evidence**:
- Preset definition: `src/quantumvitas/presets/variants_registry.py:ENUM_TO_PROFILE` (line 233-238)
- ParamSpace: `src/quantumvitas/presets/paramspace.py:ParamSpace` (line 298-372)
- Variant: `src/quantumvitas/presets/space_variant.py:ParamSpaceVariant` (line 16-51)
- Gen/Spec step: `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58)

### 2.2 SSOT Boundaries

**MUST**: Only `calculation.yaml` + `step.yaml` are SSOT. Preset/IR/Workflow/ParamSpace output is not persisted.

**MUST**: `step.yaml` stores spec/machine step_type and engine-specific parameters.

**MUST NOT**: Preset/IR/Workflow/ParamSpace output be persisted to disk (runtime-only).

**Evidence**:
- SSOT principle: `docs/dev/post-detour-deep-review-params-presets-ir-steps.md` (section 2.1)
- step.yaml storage: `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73)
- Preset non-persistence: `docs/dev/post-detour-deep-review-params-presets-ir-steps.md` (section 3.1)

---

## 3. Data Model Overview

### 3.1 Preset (intent, non-persisted)

**Definition**: User-facing option (e.g., `"high"`, `"medium"`, `"low"` for precision). Mapped to profile name via `ENUM_TO_PROFILE`.

**Storage**: Never persisted. Computed from step.yaml via detection or compiled into step.yaml when applied.

**Lifecycle**:
1. User selects preset (e.g., `"high"` precision)
2. Preset mapped to profile name (e.g., `"HIGH"`)
3. Profile compiled to IR patch via `compile_profile_patch()`
4. IR patch materialized to engine params and written to `step.yaml`
5. On reload, preset detected from `step.yaml` via `match_profile()`

**Evidence**:
- Preset mapping: `src/quantumvitas/presets/variants_registry.py:ENUM_TO_PROFILE` (line 233-238)
- Detection: `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534)
- Compilation: `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (line 541-612)

### 3.2 ParamSpace (matrix, profiles/variants, ownership, compile ordering)

**Definition**: Declarative data structure with:
- `name`: ParamSpace identifier (e.g., `"precision"`)
- `keys`: List of `ParamKey` instances (owned keys)
- `profiles`: Dict mapping profile name → cells (e.g., `{"HIGH": {("SYSTEM", "ecutwfc"): Cell.VALUE(80.0)}}`)

**Key Ownership**:
- Each key (section.key) belongs to exactly one ParamSpace
- Ownership registered via `register_paramspace()` and enforced via `check_key_access()`
- Violations raise `KeyAccessError`

**Compile Ordering**:
- Multi-phase compilation: prerequisite dimensions (e.g., `occupations_scheme`, `magnetism`) compile before dependent ones (e.g., `precision`)
- Phase ordering enforced by `apply_presets_to_step()` (lines 414-576 in `integration.py`)

**Evidence**:
- ParamSpace definition: `src/quantumvitas/presets/paramspace.py:ParamSpace` (line 298-372)
- Key ownership: `src/quantumvitas/presets/paramspace.py:register_paramspace()` (line 168-205)
- Compile ordering: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 414-576)

### 3.3 IR Dialects (logical patch, non-persisted)

**Definition**: IR is NOT a single flattened vocabulary. We use exactly TWO IR dialect namespaces initially:
- `ir.pw` (PW implies PBC; no mol; canonical keys/values modeled after QE/PW semantics)
- `ir.qc` (Quantum chemistry; AO/MOL world; canonical keys/values modeled after PySCF-like names for QC atomic knobs)

**MUST**: Dialects are disjoint namespaces; do not mix `ir.pw` and `ir.qc` IR keys.

**MUST**: Dialect names are NOT engine names. They represent computational paradigms (PW vs QC), not specific engines (QE vs ORCA vs PySCF).

**MUST**: IR uses Python native types:
- Bool MUST be Python `True/False` (NOT `.true.` strings in IR)
- IR canonical string values MUST be lowercase (e.g., `gauss`, not `Gauss`)

**MUST**: Key naming uses shallow namespacing: at most one dot (one level), e.g., `scf.conv_tol`, `scf.max_cycle`, `dft.grid_level`. Avoid deep paths like `ir.qc.scf.conv_tol`.

**Storage**: IR patches are runtime-only (not persisted). Only engine params in `step.yaml` are persisted.

**Future 2x2 generalization** (PBC/MOL × PW/AO) is out of scope; this spec documents only the chosen `ir.pw`/`ir.qc` dialect split.

**Evidence**:
- IR parameter registry: `src/quantumvitas/ir/parameters.py:IRParameter` (lines 14-27)
- IR→QE mapping: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
- Note: IR dialect split (`ir.pw`/`ir.qc`) is a future design decision; current code uses single IR namespace

### 3.4 Engine params (step.yaml persisted spec)

**Definition**: Engine-specific parameter keys stored in `step.yaml` `parameters` section. SSOT for execution.

**Format**: `parameters: {SYSTEM: {ecutwfc: 60.0}, ELECTRONS: {conv_thr: 1e-6}}`

**Storage**: Persisted in `step.yaml` via `StepDoc.apply_patch()`. Values stored as-is (no type conversion).

**Materialization**: Engine writers convert IR patches to engine-specific format (e.g., QE `.true.`/`.false.` strings) during materialization.

**Evidence**:
- step.yaml storage: `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73)
- StepDoc apply_patch: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)
- Materialization: `src/quantumvitas/calculation/structure_steps.py:materialize_step_spec()` (line 671-1797)

### 3.5 Gen/public step vs spec/machine step vs legacy enum

**Gen/Public Step Type**:
- Format: Generalized step type string (e.g., `"scf"`, `"nscf"`)
- Used by: Presets/ParamSpace targeting, UI display, file naming
- Storage: Not stored on disk (in-memory only)
- SSOT: `StepTypeRegistry` `public_type` field

**Spec/Machine Step Type**:
- Format: Engine-prefixed step type string (e.g., `"qe_scf"`, `"orca_scf"`)
- Used by: step.yaml storage, runner execution, materialization
- Storage: Stored in `step.yaml` `step_type` field
- SSOT: `StepTypeRegistry` `machine_type` field

**StepType Enum**:
- Format: Enum with values like `StepType.SCF = "scf"`
- Status: Legacy compatibility layer
- **MUST NOT**: Be used for core logic decisions (validation, routing, etc.)
- **MAY**: Be used for coercion/formatting only (type hinting, API responses)

**Evidence**:
- Gen/Spec step: `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58)
- Enum definition: `src/quantumvitas/calculation/types.py:StepType` (lines 10-30)
- Enum violations: `src/quantumvitas/api.py:set_relax_final_cell()` (lines 7756-7758), `get_relax_final_cell()` (lines 7866-7868)

---

## 4. Engine Declaration: supported_presets

**MUST**: Engine backend SSOT declaration is ONLY `supported_presets: [...]`.

**MUST**: UI must show only presets declared in `supported_presets`.

**MUST**: Detection must only attempt matching within `supported_presets`.

**MUST**: Apply may only be invoked for presets in `supported_presets`; otherwise fail.

**Rationale**: Prevents UI from showing presets that cannot be materialized by the target engine. Ensures detection only matches presets that the engine can actually apply.

**Evidence**:
- Note: `supported_presets` is a future design requirement; current code does not implement this yet

---

## 5. Apply Preset Pipeline (compile + materialize + write YAML)

### 5.1 Pipeline Overview

```
User selects preset
  ↓
Map preset → profile name (ENUM_TO_PROFILE)
  ↓
Get variant for (step_type, dimension) → ParamSpaceVariant
  ↓
Compile profile → IR patch (compile_profile_patch)
  ↓
Apply compile ordering (prerequisite → dependent)
  ↓
Materialize IR patch → engine params (ir_params_to_engine_params)
  ↓
Write to step.yaml (StepDoc.apply_patch)
```

### 5.2 Compile Phase

**Entrypoint**: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328)

**Phase 1 (Prerequisite)**:
- Dimensions: `occupations_scheme`, `magnetism`
- Compiles patches and applies to `step_yaml` (lines 437-472)
- Patches merged before Phase 2 so oracle can read latest state

**Phase 2 (Dependent)**:
- Dimensions: `precision`, `convergence`
- Oracle created with updated `current_yaml_state` (line 622)
- Oracle passed to `apply_invariants()` (line 629)

**Evidence**:
- Compile phases: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 414-576)
- Oracle creation: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 622)

### 5.3 Materialization

**IR Patch → Engine Params**:
- Function: `ir_params_to_engine_params()` (engine-specific)
- QE example: `src/quantumvitas/ir/backends/qe/mapping.py:ir_params_to_qe_params()` (lines 218-278)
- Converts IR canonical values to engine-specific format (e.g., Python `bool` → `.true.`/`.false.` strings for QE)

**Write to step.yaml**:
- Function: `StepDoc.apply_patch()` (lines 358-396 in `yamldoc.py`)
- Stores values as-is (no type conversion)

**Evidence**:
- IR→QE conversion: `src/quantumvitas/ir/backends/qe/mapping.py:ir_params_to_qe_params()` (lines 218-278)
- StepDoc apply_patch: `src/quantumvitas/core/yamldoc.py:apply_patch()` (lines 358-396)

### 5.4 Apply Semantics

**MUST**: Apply preset MUST be immediate YAML write (after user confirmation if overwriting custom).

**MUST**: Apply MUST be atomic: if backend cannot fully materialize required keys, apply MUST fail and MUST NOT write partial YAML.

**Evidence**:
- Apply entrypoint: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328)

---

## 6. Detect Preset Pipeline (reverse inference)

### 6.1 Pipeline Overview

```
Read step.yaml (StepDoc)
  ↓
For each dimension:
  Get variant for (step_type, dimension) → ParamSpaceVariant
  ↓
Match profile (match_profile) → profile name or None
  ↓
If match: return preset (ENUM_TO_PROFILE reverse lookup)
  If None: return CUSTOM
```

### 6.2 Match Logic

**Function**: `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534)

**Algorithm**:
1. For each owned key, get effective value from YAML (after canonicalization)
2. Compare effective value against profile cell:
   - `VALUE` cell: effective value must match expected value (after canonicalization)
   - `NOT_APPLICABLE` cell: key must be absent
   - `WILDCARD` cell: ignored
3. If all keys match: return profile name
4. If any mismatch: return `None` (custom)

**Custom Rule**: Reverse inference is full-pattern match; any mismatch => custom; custom is not auto-overwritten without explicit user action.

**Evidence**:
- Match logic: `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534)
- Custom detection: `src/quantumvitas/presets/variants_registry.py:detect_dimension_for_step()` (line 485-520)

---

## 7. Specific Supersedes General (dual-path rules)

**MUST**: ParamSpace may define both:
- General IR patch (`ir.<dialect>.*`, e.g., `ir.pw.*` or `ir.qc.*`)
- Engine-specific patch (`engine.<engine>.*`, e.g., `engine.orca.*`)

for the same preset/profile + gen_step.

**MUST**: If engine-specific patch is non-empty for the target engine, backend MUST materialize ONLY the engine-specific patch. General IR patch MUST NOT be materialized to YAML in that case.

**MUST**: Engine-specific patch for a given preset/profile+gen_step MUST be unique:
- A preset/profile MUST NOT yield more than one engine-specific patch target (e.g., not both `engine.orca.*` and `engine.pyscf.*` in the same compilation). If it does, that is a **HARD ERROR** (no tie-breakers).

**Rationale**: Allows presets to have engine-specific overrides while maintaining a general fallback. Prevents ambiguity when multiple engine-specific patches exist.

**Evidence**:
- Note: Dual-path rules are a future design requirement; current code does not implement this yet

---

## 8. Canonicalization and Robustness Contract

### 8.1 ParamSpace Robustness Normalization (Match Robustness Only)

**MUST**: ParamSpace MUST perform lightweight, lossless normalization for matching robustness on **strings**:
- `strip()` leading/trailing whitespace before comparison (applied to both reference and observed values)
- `lower()` before comparison (applied to both reference and observed values)
- Best-effort parse legacy bool strings ONLY (e.g., `.true.`/`.false.` and common variants) into Python bool, for backwards compatibility only

**MUST NOT**: ParamSpace MUST NOT implement domain synonym mapping (e.g., `gaussian` vs `gauss`) beyond the lowercase/trim normalization.

**Scope**: This normalization is ONLY for match/detect robustness; it does not redefine engine canonicalization.

**Evidence**:
- String canonicalization: `src/quantumvitas/presets/paramspace.py:canonicalize_string()` (lines 671-676)
- Bool canonicalization: `src/quantumvitas/presets/paramspace.py:canonicalize_bool()` (lines 679-681)
- ParamKey canonicalize: `src/quantumvitas/presets/paramspace.py:ParamKey.canonicalize()` (lines 86-100)

### 8.2 Engine Canonicalization SSOT

**MUST**: Engine MUST own synonym + textual variation canonicalization and MUST define canonical forms.

**MUST**: Engine MUST provide a single canonicalization entry point (one module/function per engine) used anywhere canonicalization is needed.

**MUST**: Engine canonicalization is SSOT for:
- Synonyms (e.g., `gauss`/`gaussian`)
- Case variants
- `.in` text forms (QE `.true.`/`.false.` etc.)

**MUST**: `.true.`/`.false.` textual forms SHOULD only exist in final `.in` files (text IO layer). YAML/IR should stay logical (Python `True`/`False`).

**MUST**: Import `.in -> YAML` MUST canonicalize textual forms and synonyms into canonical IR values (bools, lowercase strings).

**MUST**: YAML read before materialize/detect MAY re-canonicalize in engine (idempotent).

**Evidence**:
- QE canonicalization: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 92-124)
- IR bool encoder: `src/quantumvitas/ir/backends/qe/mapping.py:ir_bool()` (lines 14-41)
- Note: `.in -> YAML` canonicalization is a future requirement; current code may not fully implement this

### 8.3 Canonicalization Boundary

**ParamSpace Normalization** (match robustness):
- Location: `ParamKey.canonicalize()` (lines 86-100)
- Scope: Match/detect only
- Operations: trim, lowercase, legacy bool string parse

**Engine Canonicalization** (SSOT):
- Location: Engine-specific mapping modules (e.g., `ir/backends/{engine}/mapping.py`)
- Scope: All canonicalization needs (import, materialization, detection)
- Operations: synonym mapping, text form conversion, unit conversion

**Evidence**:
- ParamSpace normalization: `src/quantumvitas/presets/paramspace.py:ParamKey.canonicalize()` (lines 86-100)
- Engine canonicalization: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 92-124)

---

## 9. Profiles and UI Presentation

**MUST**: Per-engine profile lists are allowed to differ (count + names).

**MUST**: ParamSpace provides `display_name` per profile; UI must show `display_name`, not internal machine keys.

**MUST**: Profiles not applicable for an engine must be hidden (not disabled).

**Rationale**: Different engines may support different preset profiles. UI must reflect engine capabilities accurately.

**Evidence**:
- Profile display: `src/quantumvitas/presets/catalog.py:get_preset_catalog()` (line 90)
- Note: Per-engine profile lists are a future design requirement; current code may not fully implement this

---

## 9.1 QC Precision Preset Contract (v0)

**MUST**: QC precision preset applies only to **gen step `scf`**. Other gen steps are not applicable and yield empty patch.

**IR Keys** (belong to `ir.qc` dialect library):
- `scf.conv_tol` (float): SCF convergence tolerance
- `scf.max_cycle` (int): Maximum SCF iterations
- `dft.grid_level` (int, optional): DFT grid level (DFT only)

**MUST NOT**: Do NOT include `conv_tol_grad` (use engine default).

**Key Naming**: Uses shallow namespacing (one dot level): `scf.conv_tol`, `scf.max_cycle`, `dft.grid_level`.

**Engine-Specific Macro Path** (ORCA example):
- `engine.orca.scf.macro` (string, canonical lower-case): ORCA-specific SCF macro (e.g., `"tightscf"`, `"normal"`)
- Profiles for this macro are ORCA-specific and independent from IR profiles (no implied mapping)
- ParamSpace produces this path; engine writer converts to ORCA input format

**Evidence**:
- Note: QC precision preset contract is a future design requirement; current code does not implement this yet

---

## 9.2 Minimal Touch to Existing QE/PW

**MUST NOT**: Do not rename existing PW IR keys or existing ParamSpace semantics.

**MUST**: Only document the dialect split and bool canonicalization; leave PW naming as-is.

**Rationale**: Maintains backward compatibility with existing QE/PW code. Only minimal changes required to introduce dialect split and clarify bool canonicalization.

**Evidence**:
- Current PW IR keys: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
- Note: Minimal-change principle ensures existing QE/PW code remains stable

---

## 10. Invariants and Failure Modes

### 10.1 SSOT Invariants

1. **Only calculation.yaml + step.yaml are SSOT**: Preset/IR/Workflow/ParamSpace output is not persisted.
   - **Evidence**: `docs/dev/post-detour-deep-review-params-presets-ir-steps.md` (section 2.1)
   - **Test**: Verify no preset/IR state is written to disk

2. **step.yaml stores spec/machine step_type**: `step.yaml` `step_type` field stores `machine_type`, not `public_type`.
   - **Evidence**: `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73)
   - **Test**: Verify `step.yaml` contains `machine_type` (e.g., `"qe_scf"`)

### 10.2 Step Vocabulary Invariants

3. **Gen/public step type is stable string**: Used for UI + ParamSpace scope, not persisted.
   - **Evidence**: `src/quantumvitas/workflow/registry.py:StepTypeSpec.public_type` (line 46)
   - **Test**: Verify preset targeting uses `public_type`

4. **Spec/machine step_type used for persisted execution**: `step.yaml` stores `machine_type`; runner reads `machine_type`.
   - **Evidence**: `src/quantumvitas/calculation/step.py:Step.run()` (line 92)
   - **Test**: Verify runner execution uses `machine_type` from `step.yaml`

5. **StepType Enum is legacy-only**: MUST NOT be used for core logic decisions.
   - **Evidence**: `src/quantumvitas/api.py:set_relax_final_cell()` (lines 7756-7758) - **VIOLATION**
   - **Test**: Verify no Enum usage in validation/routing logic

### 10.3 Engine Declaration Invariants

6. **Only supported_presets are detected/shown/applied**: UI shows only presets in `supported_presets`; detection only matches within `supported_presets`; apply fails if preset not in `supported_presets`.
   - **Evidence**: Note: `supported_presets` is a future requirement
   - **Test**: Verify UI filtering, detection gating, apply validation

### 10.4 IR Value Type Invariants

7. **IR bool is True/False**: IR uses Python native types; bool MUST be `True`/`False`, not `.true.` strings.
   - **Evidence**: Note: Current code uses `.true.`/`.false.` strings in IR; this is a future requirement
   - **Test**: Verify IR patches contain Python `bool`, not strings

8. **IR strings lowercase**: IR canonical string values MUST be lowercase (e.g., `gauss`, not `Gauss`).
   - **Evidence**: Note: This is a future requirement
   - **Test**: Verify IR string values are lowercase

### 10.5 ParamSpace Robustness Invariants

9. **ParamSpace string normalization (trim+lower) before compare**: ParamSpace MUST trim whitespace and lowercase strings before matching.
   - **Evidence**: `src/quantumvitas/presets/paramspace.py:canonicalize_string()` (lines 671-676)
   - **Test**: Verify `match_profile()` handles `"  GAUSS  "` as `"gauss"`

10. **ParamSpace does not synonym-map gaussian↔gauss**: ParamSpace MUST NOT implement domain synonym mapping beyond lowercase/trim.
   - **Evidence**: `src/quantumvitas/presets/paramspace.py:canonicalize_string()` (lines 671-676)
   - **Test**: Verify `match_profile()` does NOT map `"gaussian"` to `"gauss"`

### 10.6 Engine Canonicalization Invariants

11. **Engine canonicalization is single entry point**: Engine MUST provide one canonicalization function/module used everywhere.
   - **Evidence**: `src/quantumvitas/ir/backends/qe/mapping.py:ir_to_qe_param()` (lines 92-124)
   - **Test**: Verify all canonicalization goes through engine mapping module

12. **Engine defines canonical forms**: Engine MUST define canonical forms for all parameters (synonyms, text forms, units).
   - **Evidence**: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74)
   - **Test**: Verify engine mapping defines canonical forms

13. **`.true.` appears only in `.in`**: `.true.`/`.false.` textual forms MUST only appear in engine input files, not in IR or YAML.
   - **Evidence**: Note: Current code stores `.true.`/`.false.` in `step.yaml`; this is a future requirement
   - **Test**: Verify `.in` files contain `.true.`/`.false.`, but `step.yaml` contains Python `bool`

### 10.7 Specific Supersedes General Invariants

14. **Specific patch non-empty => IR patch not materialized**: If engine-specific patch exists, general IR patch MUST NOT be materialized.
   - **Evidence**: Note: Dual-path rules are a future requirement
   - **Test**: Verify materialization uses engine-specific patch when available

15. **Engine-specific patch uniqueness per preset/profile+gen_step**: A preset/profile MUST NOT yield more than one engine-specific patch target (hard error if violated).
   - **Evidence**: Note: Dual-path rules are a future requirement
   - **Test**: Verify compilation fails if multiple engine-specific patches exist

### 10.8 Apply/Detect Invariants

16. **Apply is atomic**: If backend cannot fully materialize required keys, apply MUST fail and MUST NOT write partial YAML.
   - **Evidence**: `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328)
   - **Test**: Verify apply fails fast if materialization fails

17. **Detect is full-pattern match or custom**: Reverse inference is full-pattern match; any mismatch => custom.
   - **Evidence**: `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534)
   - **Test**: Verify `match_profile()` returns `None` on any mismatch

### 10.9 Reversibility Invariants

18. **Match → compile → match idempotent**: If a preset is detected, compiling it must produce no changes.
   - **Evidence**: `tests/unit/test_paramspace_contract.py`
   - **Test**: Verify `match_profile(compile_profile_patch(profile)) == profile`

---

## 11. Test Strategy

### 11.1 Apply→Detect Roundtrip (Reversibility)

**Test**: Apply preset → detect preset → verify match
- Apply preset `"high"` precision to step
- Detect preset from step
- Verify detected preset is `"high"`

**Evidence**: `tests/unit/test_paramspace_contract.py`

### 11.2 Custom Mismatch Behavior

**Test**: Verify custom detection on mismatch
- Set step parameter to non-profile value (e.g., `ecutwfc=70` when profile expects `60`)
- Detect preset
- Verify detected preset is `CUSTOM`

**Evidence**: `src/quantumvitas/presets/variants_registry.py:detect_dimension_for_step()` (line 485-520)

### 11.3 `.in` Import Canonicalization Tests

**Test**: Verify `.in` import canonicalizes bool text + synonyms to canonical lowercase forms
- Import `.in` file with `noncolin: .true.`
- Verify `step.yaml` contains `noncolin: true` (Python bool)
- Import `.in` file with `occupations: "GAUSS"`
- Verify `step.yaml` contains `occupations: "gauss"` (lowercase)

**Evidence**: Note: `.in` import canonicalization is a future requirement

### 11.4 Enforcement of Specific>General Materialization

**Test**: Verify engine-specific patch takes precedence over general IR patch
- Define preset with both `ir.pw.*` and `engine.qe.*` patches
- Materialize for QE engine
- Verify only `engine.qe.*` patch is materialized

**Evidence**: Note: Dual-path rules are a future requirement

### 11.5 Enforcement of "No Multiple Engine-Specific Patches" Hard Error

**Test**: Verify compilation fails if preset yields multiple engine-specific patches
- Define preset with both `engine.orca.*` and `engine.pyscf.*` patches
- Attempt compilation
- Verify hard error (no tie-breakers)

**Evidence**: Note: Dual-path rules are a future requirement

### 11.6 supported_presets Gating Tests

**Test**: Verify UI filtering, detection gating, apply validation
- Set engine `supported_presets = ["high", "medium"]`
- Verify UI shows only `"high"` and `"medium"`
- Verify detection only matches `"high"` and `"medium"`
- Verify apply fails for `"low"` (not in `supported_presets`)

**Evidence**: Note: `supported_presets` is a future requirement

### 11.7 Guardian Tests

**Key tests that enforce the contract**:
- `tests/unit/test_key_access_enforcement.py`: Enforces key ownership rules
- `tests/unit/test_paramspace_invariants.py`: Enforces `apply_invariants()` behavior and compile ordering
- `tests/unit/test_paramspace_contract.py`: Enforces reversibility (match/compile idempotency)
- `tests/unit/test_preset_integration.py`: Enforces two-phase compilation and oracle usage

**Evidence**:
- Key ownership: `tests/unit/test_key_access_enforcement.py`
- Invariants: `tests/unit/test_paramspace_invariants.py`
- Reversibility: `tests/unit/test_paramspace_contract.py`
- Integration: `tests/unit/test_preset_integration.py`

---

## 12. Open Questions (minimal)

### Q1: IR Value Type Discrepancy

**Question**: Current code stores `.true.`/`.false.` strings in `step.yaml` (per `final-audit-ir-step-ssot.md`), but this spec requires IR bool to be Python `True/False` and `.true.` to appear only in `.in` files. Which is correct?

**Evidence**:
- Current behavior: `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (lines 601-605) converts Python `bool` → `.true.`/`.false.` strings
- Spec requirement: IR bool MUST be Python `True/False`; `.true.` only in `.in` files

**Impact**: Affects IR value type contract and materialization boundary.

### Q2: IR Dialect Namespace Implementation

**Question**: Current code uses single IR namespace (QE-equivalent). Spec requires `ir.pw` and `ir.qc` dialects. When will dialect split be implemented?

**Evidence**:
- Current: `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (single namespace)
- Spec requirement: Two dialects (`ir.pw`, `ir.qc`)

**Impact**: Affects ORCA/PySCF onboarding strategy.

### Q3: supported_presets Implementation

**Question**: `supported_presets` is not implemented yet. When will engine declaration be added?

**Evidence**:
- Current: No `supported_presets` declaration found in codebase
- Spec requirement: Engine MUST declare `supported_presets`

**Impact**: Affects UI filtering and detection gating.

### Q4: Dual-Path Rules Implementation

**Question**: Dual-path rules (general IR patch vs engine-specific patch) are not implemented yet. When will this be added?

**Evidence**:
- Current: No dual-path patch compilation found in codebase
- Spec requirement: ParamSpace may define both general and engine-specific patches

**Impact**: Affects preset compilation and materialization strategy.

### Q5: `.in` Import Canonicalization

**Question**: `.in` import canonicalization (bool text + synonyms to canonical forms) is not fully implemented. When will this be added?

**Evidence**:
- Current: `.in` import may not canonicalize all forms
- Spec requirement: Import `.in -> YAML` MUST canonicalize textual forms and synonyms

**Impact**: Affects import roundtrip and detection accuracy.

---

## Appendix: Evidence Index

### ParamSpace Core

- `src/quantumvitas/presets/paramspace.py:ParamSpace` (line 298-372) - ParamSpace definition
- `src/quantumvitas/presets/paramspace.py:ParamKey` (line 59-121) - ParamKey definition
- `src/quantumvitas/presets/paramspace.py:register_paramspace()` (line 168-205) - Key ownership registration
- `src/quantumvitas/presets/paramspace.py:check_key_access()` (line 207-254) - Key access enforcement
- `src/quantumvitas/presets/paramspace.py:match_profile()` (line 461-534) - Reverse inference
- `src/quantumvitas/presets/paramspace.py:compile_profile_patch()` (line 541-612) - Forward compilation

### Integration Layer

- `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (line 328) - Main apply entrypoint
- `src/quantumvitas/presets/integration.py:apply_presets_to_step()` (lines 414-576) - Compile phase ordering
- `src/quantumvitas/presets/oracle.py:Oracle` (line 18-60) - Oracle interface

### IR Layer

- `src/quantumvitas/ir/parameters.py:IRParameter` (lines 14-27) - IR parameter definition
- `src/quantumvitas/ir/backends/qe/mapping.py:IR_TO_QE_MAPPING` (line 46-74) - IR→QE mapping
- `src/quantumvitas/ir/backends/qe/mapping.py:ir_bool()` (lines 14-41) - IR bool encoder
- `src/quantumvitas/ir/backends/qe/mapping.py:ir_params_to_qe_params()` (lines 218-278) - IR→QE conversion

### Step Vocabulary

- `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 23-58) - Gen/Spec step definition
- `src/quantumvitas/workflow/step_factory.py:create_step_doc()` (line 73) - step.yaml storage
- `src/quantumvitas/calculation/types.py:StepType` (lines 10-30) - Enum definition

### Tests

- `tests/unit/test_key_access_enforcement.py` - Key ownership enforcement
- `tests/unit/test_paramspace_invariants.py` - Invariant enforcement
- `tests/unit/test_paramspace_contract.py` - Reversibility tests
- `tests/unit/test_preset_integration.py` - Integration tests

---

## Appendix: Contract Summary

### SSOT vs Non-SSOT

- **SSOT (persisted)**: `calculation.yaml` + `step.yaml` only
- **Non-SSOT (runtime-only)**: Preset, IR, ParamSpace, Workflow output

### Dialect Naming

- **Dialects**: `ir.pw` (PW/PBC) and `ir.qc` (QC/AO/MOL)
- **NOT engines**: Dialect names represent computational paradigms, not specific engines
- **Disjoint**: Do not mix `ir.pw` and `ir.qc` keys

### Robust Match Rules

- **ParamSpace normalization** (match robustness only):
  - `strip()` and `lower()` strings before comparison
  - Best-effort parse legacy bool strings (`.true.`/`.false.`) to Python bool
  - NO domain synonym mapping (e.g., `gaussian` vs `gauss`)
- **Engine canonicalization** (SSOT):
  - Synonyms, case variants, `.in` text forms
  - Single entry point per engine

### Specific>General Rule

- Preset MAY define both general IR patch (`ir.<dialect>.*`) and engine-specific patch (`engine.<engine>.*`)
- If engine-specific patch exists, MUST use it (general IR patch NOT materialized)
- Multiple engine-specific patches = HARD ERROR (no tie-breakers)

### Shallow Key Namespace Rule for QC

- **MUST**: Use at most one dot (one level), e.g., `scf.conv_tol`, `scf.max_cycle`, `dft.grid_level`
- **MUST NOT**: Avoid deep paths like `ir.qc.scf.conv_tol`

### IR Value Types

- **Bool**: Python `True/False` (NOT `.true.` strings in IR)
- **Strings**: Lowercase canonical values
- **`.true.`/`.false.`**: SHOULD only appear in final `.in` files (text IO layer)

### Gen Step Scope

- **QC precision preset**: Applies only to gen step `scf`; other gen steps yield empty patch

### Minimal-Change Principle

- **MUST NOT**: Rename existing PW IR keys or ParamSpace semantics
- **MUST**: Only document dialect split and bool canonicalization

---

**End of Specification**

