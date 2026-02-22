# YAML→Spec→Input(.in)→Runner Information Fidelity & Overrides Audit

**Date**: 2025-01-XX  
**Purpose**: Deep code review of the entire pipeline from step.yaml to generated QE input and runner execution, focusing on information fidelity and override propagation correctness.

**Status**: Review only - no code changes

---

## Executive Summary

This audit examines the complete data flow from step.yaml persistence through in-memory spec objects, QE input generation, and runner execution. Key findings:

**Critical Paths**:
- **Path A (Generate from spec)**: step.yaml → `StructureStepSpec` → `generate_qe_input_from_spec()` → `.in` file → `Step.run()` → `prepare_input_step()` → runner
- **Path B (Reuse existing)**: step.yaml + existing_input_file → extract/merge → `materialize_step_spec()` → `.in` file → runner

**Key Findings**:
1. **Data Model**: `StructureStepSpec` is the primary in-memory SSOT; `StepDoc` is used for YAML persistence with normalization
2. **Override Channels**: parameters, cards, species_overrides, runtime CONTROL (prefix/outdir/pseudo_dir)
3. **Recent Fix**: `Step.run()` now forwards `card_overrides` from step.yaml (fixed in previous commit)
4. **Gap**: `species_overrides` not explicitly forwarded in `Step.run()` but applied via `generate_qe_input_from_spec()` → `materialize_step_spec()` → `prepare_input_step()`
5. **Validation**: Pseudopotential placeholder detection raises "configuration error" and triggers skip in tests

**Risk Areas Identified**: 10+ concrete risks documented in Risk Register section.

---

## Data Model Inventory

### step.yaml Schema (Persisted)

**Location**: `src/qmatsuite/calculation/structure_steps.py:171-202` (`StructureStepSpec.to_dict()`)

**Required Fields**:
- `meta`: Resource metadata (id, name, slug, path, kind)
- `step_type`: Machine type (e.g., "qe_scf", "qe_bands") - SPEC type, not GEN

**Optional Fields** (only written if non-empty):
- `parameters`: Dict[str, Dict[str, Any]] - Namelist sections (CONTROL, SYSTEM, ELECTRONS, etc.)
- `cards`: Dict[str, Dict[str, Any]] - QE cards (K_POINTS, ATOMIC_SPECIES, etc.)
- `species_overrides`: Dict[str, Dict[str, Any]] - Element-specific overrides (pseudopot, mass)
- `input_name`: Optional[str] - Explicit input filename override
- `kpath_metadata`: Optional[Dict[str, Any]] - K-path visualization metadata

**Explicitly Excluded** (DAG invariant):
- `structure_id`: Inherits from calculation (not duplicated)
- `parent_calculation_id`: Implicit from file location
- `structure`: Legacy selector (not written)

**Evidence**:
```python
# src/qmatsuite/calculation/structure_steps.py:171-202
def to_dict(self) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "meta": self.meta.to_dict(),
        "step_type": self.step_type,
    }
    if self.parameters:
        data["parameters"] = self.parameters
    if self.input_name:
        data["input_name"] = self.input_name
    if self.cards:
        data["cards"] = self.cards
    if self.species_overrides:
        data["species_overrides"] = self.species_overrides
    if self.kpath_metadata:
        data["kpath_metadata"] = self.kpath_metadata
    # Do NOT write structure_id, parent_calculation_id, structure
```

### In-Memory Objects

#### StructureStepSpec (Primary SSOT)

**Location**: `src/qmatsuite/calculation/structure_steps.py:34-53`

**Fields**:
- `meta: ResourceMeta`
- `structure: str` (legacy selector, backwards compat)
- `structure_id: Optional[str]` (canonical ULID reference)
- `step_type: str` (machine type)
- `parameters: Dict[str, Dict[str, Any]]`
- `input_name: Optional[str]`
- `cards: Dict[str, Dict[str, Any]]`
- `species_overrides: Dict[str, Dict[str, Any]]`
- `parent_calculation_id: Optional[str]`
- `kpath_metadata: Optional[Dict[str, Any]]`

**Creation**:
- `StructureStepSpec.from_yaml(path)` → `from_dict(yaml.safe_load(path.read_text()))`
- Used in: `_build_step_from_spec()`, `generate_qe_input_from_spec()`, `materialize_step_spec()`

#### StepDoc (YAML Document Wrapper)

**Location**: `src/qmatsuite/core/yamldoc.py:454-505`

**Purpose**: YAML persistence with QE-specific normalization (section names uppercase, parameter aliases)

**Key Facts**:
- Inherits from `YamlDoc` (no `id` or `meta.id` attribute accessor)
- Access pattern: `doc.get(["meta", "id"])` or `doc.export_copy()["meta"]["id"]`
- Used in: `create_step_doc()`, `save_step_doc()`, preset integration (`apply_presets_to_step()`)

**Normalization**:
- Section names → uppercase (CONTROL, SYSTEM, etc.)
- Parameter aliases (gauss → gaussian)
- Access control ownership (compiler/detector/user)

#### QEInput (Runtime Input Model)

**Location**: `src/qmatsuite/io/model.py` (QEInput class)

**Purpose**: In-memory representation of QE input file (namelists, cards, structure)

**Used in**: 
- `generate_qe_input_from_spec()` output
- `prepare_input_step()` input/output
- `apply_card_overrides_to_qe_input()`, `apply_species_overrides_to_qe_input()`

#### Step (Execution Wrapper)

**Location**: `src/qmatsuite/calculation/step.py:19-32`

**Fields**:
- `meta: ResourceMeta`
- `input_file: Path`
- `engine: str`
- `step_type: Optional[StepType]`
- `options: Dict[str, object]`
- `mode: StepMode`
- `reference_output: Optional[Path]`
- `structure: Optional[StructureRef]`

**Note**: `Step` does NOT store cards/species_overrides directly. These are loaded from step.yaml in `Step.run()`.

---

## Pipeline Call Chains

### Path A: Generate Input from Spec

```
step.yaml (YAML file)
  ↓ yaml.safe_load()
  ↓ StructureStepSpec.from_dict() / StructureStepSpec.from_yaml()
spec = StructureStepSpec (in-memory)
  ↓ _build_step_from_spec() (calculation.py:558-726)
  ↓ materialize_step_spec() (materialize.py)
  ↓ generate_qe_input_from_spec(structure, spec) (structure_steps.py:487)
  ↓ generate_qe_input_from_structure() (structure_steps.py:212)
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards) (structure_steps.py:571)
  ↓ apply_species_overrides_to_qe_input(qe_input, spec.species_overrides) (structure_steps.py:576)
qe_input = QEInput (in-memory)
  ↓ QEInputGenerator.write_file(qe_input, output_path) (generator/qe_generator.py)
output .in file (filesystem)
  ↓ Step.run() (step.py:62)
  ↓ run_input_step(input_file, ..., card_overrides=spec.cards) (step.py:115, input_runner.py:458)
  ↓ prepare_input_step(input_file, ..., card_overrides, species_overrides) (input_runner.py:199)
  ↓ QEInputParser.parse_file(input_file) → qe_input (parser/qe_parser.py)
  ↓ apply_card_overrides_to_qe_input(qe_input, card_overrides) (input_runner.py:375, input_runner.py:726)
  ↓ apply_species_overrides_to_qe_input(qe_input, species_overrides) (input_runner.py:376, input_runner.py:682)
  ↓ set_outdir_to_temp() (input_runner.py:377)
  ↓ set_pseudo_dir_in_input() (input_runner.py:379)
  ↓ QEInputGenerator.write_file(qe_input, working_dir_input) (input_runner.py:380)
final .in file in working_dir (filesystem)
  ↓ run_prepared_step() (input_runner.py:403)
  ↓ engine.run_step() (qe_engine.py)
runner execution
```

**Key Functions**:
- `StructureStepSpec.from_yaml()`: `structure_steps.py:151-169`
- `generate_qe_input_from_spec()`: `structure_steps.py:487-578`
- `materialize_step_spec()`: `materialize.py` (imported)
- `Step.run()`: `step.py:62-127`
- `prepare_input_step()`: `input_runner.py:199-400`

### Path B: Reuse/Import Existing Input File

```
step.yaml + existing_input_file (from calculation.yaml step entry)
  ↓ StructureStepSpec.from_yaml(step.yaml)
spec_preview = StructureStepSpec (in-memory)
  ↓ _build_step_from_spec(..., existing_input_file=...) (calculation.py:558)
  ↓ QEInputParser.parse_file(existing_input_file) → existing_qe_input (calculation.py:601)
  ↓ _build_step_spec_from_qe_input_data(existing_qe_input, apply_defaults=False) (calculation.py:646, importers.py:49)
  ↓ extracted_params, extracted_cards = (dict, dict)
  ↓ spec_preview.parameters[section].update(extracted_params[section]) (calculation.py:657-660)
  ↓ spec_preview.cards.update(extracted_cards) (calculation.py:663-666)  ⚠️ RISK: shallow merge
  ↓ Extract ATOMIC_SPECIES → extracted_overrides (calculation.py:668-683)
  ↓ spec_preview.species_overrides.update(extracted_overrides) (calculation.py:685-689)
merged spec_preview (extracted data takes precedence)
  ↓ materialize_step_spec(spec_preview, ...) (calculation.py:726)
  ↓ generate_qe_input_from_spec() → .in file
  ↓ Step.run() → runner
```

**Key Functions**:
- `_build_step_from_spec()`: `calculation.py:558-726`
- `_build_step_spec_from_qe_input_data()`: `importers.py:49-92`
- Merge logic: `calculation.py:652-689`

**Merge Precedence**: existing_input_file data takes precedence over step.yaml (explicit comment: "existing input takes precedence")

---

## Overrides Taxonomy & Ownership

### 1. Parameters Overrides (Namelists)

**Source**: `step.yaml["parameters"]` or extracted from existing_input_file

**Structure**: `Dict[str, Dict[str, Any]]` where key = namelist section (CONTROL, SYSTEM, etc.)

**Application Points**:
1. `generate_qe_input_from_spec()` → `parameter_dict_to_overrides()` → `generate_qe_input_from_structure()`
2. `prepare_input_step()` → `_apply_parameter_overrides()`

**Merge Logic**: Section-level merge in `calculation.py:657-660`:
```python
for section, params in extracted_params.items():
    if section not in spec_preview.parameters:
        spec_preview.parameters[section] = {}
    spec_preview.parameters[section].update(params)  # Existing input wins
```

**Risk**: Shallow merge - nested dict keys overwritten entirely (not merged recursively)

### 2. Cards Overrides

**Source**: `step.yaml["cards"]` or extracted from existing_input_file

**Structure**: `Dict[str, Dict[str, Any]]` where key = card type (K_POINTS, ATOMIC_SPECIES, etc.)

**Application Points**:
1. `generate_qe_input_from_spec()` → `apply_card_overrides_to_qe_input(qe_input, spec.cards)`
2. `Step.run()` → loads cards from step.yaml → `run_input_step(..., card_overrides=cards)` → `prepare_input_step()` → `apply_card_overrides_to_qe_input()`

**Merge Logic**: Top-level dict update in `calculation.py:666`:
```python
spec_preview.cards.update(extracted_cards)  # ⚠️ RISK: shallow merge loses nested keys
```

**Validation**: `apply_card_overrides_to_qe_input()` validates K_POINTS k-path formats require `data` (input_runner.py:748-766)

**Recent Fix**: `Step.run()` now forwards `card_overrides` from step.yaml (step.py:100-123)

### 3. Species Overrides (Pseudopotentials/Masses)

**Source**: `step.yaml["species_overrides"]` or extracted from existing_input_file ATOMIC_SPECIES card

**Structure**: `Dict[str, Dict[str, Any]]` where key = element symbol, value = `{"pseudopot": "...", "mass": ...}`

**Application Points**:
1. `generate_qe_input_from_spec()` → `apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)` where `effective_species_overrides = species_map if species_map else spec.species_overrides`
2. `prepare_input_step()` → `apply_species_overrides_to_qe_input(qe_input, species_overrides)`

**Note**: `Step.run()` does NOT explicitly forward `species_overrides`. They are applied during materialization (`generate_qe_input_from_spec()`) before `.in` file is written.

**Merge Logic**: Top-level dict update in `calculation.py:689`:
```python
spec_preview.species_overrides.update(extracted_overrides)  # ⚠️ RISK: shallow merge
```

**Placeholder Detection**: `is_missing_pseudo_placeholder()` checks for `<filename>` pattern (pseudo.py)

**Validation**: `ensure_qe_pseudos()` raises "configuration error" if placeholder detected (pseudo.py, triggers test skip)

### 4. Runtime CONTROL Overrides

**Source**: Runtime enforcement (not from step.yaml)

**Keys**: `prefix`, `outdir`, `pseudo_dir`

**Application Points**:
1. `set_outdir_to_temp()`: Forces `outdir = "./outdir"` (input_runner.py:377)
2. `set_pseudo_dir_in_input()`: Forces `pseudo_dir = "../pseudo"` relative to working_dir (input_runner.py:379)

**Precedence**: Runtime overrides ALWAYS win (applied after all other overrides)

**Evidence**:
```python
# input_runner.py:371-380
qe_input = QEInputParser.parse_file(input_file)
if parameter_overrides:
    _apply_parameter_overrides(qe_input, parameter_overrides)
apply_card_overrides_to_qe_input(qe_input, card_overrides)
apply_species_overrides_to_qe_input(qe_input, species_overrides)
set_outdir_to_temp(qe_input)  # Runtime override
set_pseudo_dir_in_input(qe_input, project_pseudo_dir, working_dir)  # Runtime override
QEInputGenerator.write_file(qe_input, working_dir_input)
```

### 5. Default Templates

**Source**: `step_defaults.py` (DEFAULT_STEP_PARAMS dict)

**Injection Points**:
1. `get_default_step_params(step_type)` → `QMSService.init_step()` → `create_step_doc(overrides={"cards": defaults.get("cards", {})})`
2. `_build_step_spec_from_qe_input_data(..., apply_defaults=True)` merges defaults

**Recent Fix**: Removed invalid `K_POINTS: {option: "crystal_b"}` from "bands" defaults (step_defaults.py:83-86)

**Risk**: Defaults can inject partial/invalid structures (e.g., K_POINTS without data)

### 6. Implicit Overrides (Presets/ParamSpace)

**Source**: Preset detection/compilation pipeline

**Application**: `apply_presets_to_step()` → writes to StepDoc → step.yaml updated → next materialization picks up changes

**Note**: Presets operate on IR, not directly on QEInput. IR→QE conversion happens during materialization.

---

## Where Data Can Be Lost

### Risk Register

#### R-01: Cards Shallow Merge Loses Nested Keys (K_POINTS.data)

**Severity**: High  
**Symptom**: `K_POINTS option 'crystal_b' requires 'data'` error when existing_input_file has incomplete K_POINTS  
**Root Cause**: `spec_preview.cards.update(extracted_cards)` in `calculation.py:666` performs shallow merge. If `extracted_cards["K_POINTS"] = {"option": "crystal_b"}` (no data) and `spec_preview.cards["K_POINTS"] = {"option": "crystal_b", "data": [...]}`, the entire dict is replaced, losing `data`.  
**Affected Channels**: cards  
**Code Location**: `calculation.py:662-666`  
**Current Coverage**: Fail-fast validation in `apply_card_overrides_to_qe_input()` (input_runner.py:755-759)  
**Proposed Safeguard**: Deep merge for cards dict, or preserve step.yaml data for k-path formats when extracted lacks data

#### R-02: Parameters Shallow Merge Loses Nested Keys

**Severity**: Medium  
**Symptom**: Nested namelist parameters overwritten instead of merged  
**Root Cause**: `spec_preview.parameters[section].update(params)` in `calculation.py:659` merges at section level, but if `extracted_params["CONTROL"]` has keys that overwrite important step.yaml values, they're lost.  
**Affected Channels**: parameters  
**Code Location**: `calculation.py:657-660`  
**Current Coverage**: None (no validation)  
**Proposed Safeguard**: Document merge precedence clearly, or use deep merge utility

#### R-03: Species Overrides Shallow Merge

**Severity**: Medium  
**Symptom**: Mass/pseudopot overrides from step.yaml lost when existing_input_file extracted  
**Root Cause**: `spec_preview.species_overrides.update(extracted_overrides)` in `calculation.py:689` replaces entire element dict.  
**Affected Channels**: species_overrides  
**Code Location**: `calculation.py:685-689`  
**Current Coverage**: None  
**Proposed Safeguard**: Merge at element level (preserve mass if only pseudopot updated)

#### R-04: Default Templates Inject Invalid Partial Cards

**Severity**: High (fixed)  
**Symptom**: `bands` step type default had `K_POINTS: {option: "crystal_b"}` without data  
**Root Cause**: `step_defaults.py` injected incomplete card structure  
**Affected Channels**: cards (defaults)  
**Code Location**: `step_defaults.py:69-88` (fixed in recent commit)  
**Current Coverage**: Manual review (no static check)  
**Proposed Safeguard**: Static check or unit test preventing defaults from containing invalid partial cards

#### R-05: Step.run() Missing species_overrides Forwarding

**Severity**: Low  
**Symptom**: If `.in` file is modified after materialization, species_overrides from step.yaml won't re-apply  
**Root Cause**: `Step.run()` forwards `card_overrides` but not `species_overrides`. They're applied during materialization, but if `prepare_input_step()` re-parses `.in` file, species changes are lost.  
**Affected Channels**: species_overrides  
**Code Location**: `step.py:100-123` (card_overrides forwarded, species_overrides not)  
**Current Coverage**: Works if `.in` file generated correctly during materialization  
**Proposed Safeguard**: Forward `species_overrides` in `Step.run()` similar to `card_overrides`

#### R-06: Runtime CONTROL Overrides Always Win (No User Override Possible)

**Severity**: Low  
**Symptom**: User cannot override `outdir` or `pseudo_dir` in step.yaml (runtime always sets them)  
**Root Cause**: `set_outdir_to_temp()` and `set_pseudo_dir_in_input()` run after all user overrides  
**Affected Channels**: parameters (CONTROL section)  
**Code Location**: `input_runner.py:377, 379`  
**Current Coverage**: Documented behavior (by design)  
**Proposed Safeguard**: Document clearly that runtime CONTROL keys cannot be overridden

#### R-07: Existing Input File Extraction Loses Cards Data If Input Incomplete

**Severity**: High  
**Symptom**: If existing_input_file has K_POINTS with only option (no data), step.yaml data is lost  
**Root Cause**: `_extract_cards()` extracts what's in file. If file incomplete, extracted_cards incomplete. Shallow merge replaces step.yaml cards.  
**Affected Channels**: cards  
**Code Location**: `calculation.py:646-666`, `importers.py:68-69`  
**Current Coverage**: Fail-fast validation in `apply_card_overrides_to_qe_input()`  
**Proposed Safeguard**: Validate extracted cards completeness before merge, or preserve step.yaml data for required fields

#### R-08: StepDoc vs StructureStepSpec Schema Mismatch

**Severity**: Medium  
**Symptom**: Preset integration writes to StepDoc, but execution reads via StructureStepSpec. If schemas diverge, data lost.  
**Root Cause**: `apply_presets_to_step()` uses `StepDoc`, but `_build_step_from_spec()` uses `StructureStepSpec.from_yaml()`. Both read same file but different parsers.  
**Affected Channels**: All (if schema diverges)  
**Code Location**: `presets/integration.py` (StepDoc), `calculation.py:587` (StructureStepSpec)  
**Current Coverage**: Both use same YAML file (should be consistent)  
**Proposed Safeguard**: Ensure StepDoc and StructureStepSpec have identical read/write semantics

#### R-09: Structure Resolution at Execution Time (Not in step.yaml)

**Severity**: Low  
**Symptom**: If calculation.structure_id changes, step.yaml doesn't reflect it (by design, DAG model)  
**Root Cause**: Structure resolved from calculation.structure_id at execution, not stored in step.yaml  
**Affected Channels**: structure  
**Code Location**: `structure_steps.py:97-100` (DAG invariant documentation)  
**Current Coverage**: By design (DAG model)  
**Proposed Safeguard**: Document clearly that structure_id is calculation-level, not step-level

#### R-10: Pseudopotential Placeholder Causes Skip (Not Hard Error)

**Severity**: Medium  
**Symptom**: Tests skip with "configuration error" message instead of failing fast  
**Root Cause**: `is_missing_pseudo_placeholder()` detects `<filename>` pattern, `ensure_qe_pseudos()` raises but test framework converts to skip  
**Affected Channels**: species_overrides  
**Code Location**: `pseudo.py` (placeholder detection), test framework (skip conversion)  
**Current Coverage**: Error raised correctly, but test behavior may mask issues  
**Proposed Safeguard**: Document that placeholder = configuration error (not runtime error). Tests should configure pseudos properly.

#### R-11: Parameters Dict Conditional Write (Empty Dicts Not Persisted)

**Severity**: Low  
**Symptom**: Empty `parameters: {}` not written to step.yaml (conditional: `if self.parameters`)  
**Root Cause**: `to_dict()` only writes if dict non-empty. This is intentional (cleaner YAML) but means empty dicts are lost on round-trip.  
**Affected Channels**: parameters  
**Code Location**: `structure_steps.py:189`  
**Current Coverage**: By design  
**Proposed Safeguard**: Document that empty collections are not persisted (round-trip loss expected)

#### R-12: Input Name vs Input File Path Confusion

**Severity**: Low  
**Symptom**: `input_name` in step.yaml vs `input_file` in Step object vs `existing_input_file` parameter - three different concepts  
**Root Cause**: Legacy naming - `input_name` is output filename hint, `input_file` is execution path, `existing_input_file` is import source  
**Affected Channels**: input file resolution  
**Code Location**: Multiple (calculation.py, step.py, structure_steps.py)  
**Current Coverage**: Code works but terminology confusing  
**Proposed Safeguard**: Document terminology clearly: `input_name` = output filename, `input_file` = execution path, `existing_input_file` = import source

---

## Existing Safeguards

### 1. K_POINTS Validation (Fail-Fast)

**Location**: `input_runner.py:748-766`

**Check**: If `K_POINTS.option` is k-path format (`crystal_b`, `crystal_c`, `tpiba_b`, `tpiba_c`) and `data` is missing, raise `ValueError` immediately.

**Evidence**:
```python
if new_option and new_option.lower() in kpath_formats:
    if "data" not in payload:
        raise ValueError(
            f"K_POINTS option '{new_option}' requires 'data' to be provided. "
            "K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data."
        )
```

**Coverage**: Catches incomplete K_POINTS at apply time (R-01, R-07)

### 2. Pseudopotential Placeholder Detection

**Location**: `pseudo.py` (`is_missing_pseudo_placeholder()`)

**Check**: Detects `<filename>` pattern in pseudopotential names.

**Coverage**: Prevents runtime errors from missing pseudos (R-10)

### 3. Type Validation in StructureStepSpec.from_dict()

**Location**: `structure_steps.py:107-118`

**Checks**:
- `parameters` must be dict
- `cards` must be dict (if provided)
- `species_overrides` must be dict (if provided)

**Coverage**: Prevents schema violations at parse time

### 4. Step.run() Card Overrides Forwarding (Recent Fix)

**Location**: `step.py:100-123`

**Implementation**: Loads cards from step.yaml and forwards to `run_input_step(card_overrides=...)`

**Coverage**: Ensures step.yaml cards apply at runtime (R-05 partially addressed)

### 5. Runtime CONTROL Override Documentation

**Location**: Code comments in `input_runner.py:377-379`

**Coverage**: Documents that runtime always sets outdir/pseudo_dir (R-06)

---

## Gaps & Proposed Minimal Safeguards

### Gap 1: Cards Deep Merge Not Implemented

**Issue**: Shallow merge in `calculation.py:666` can lose nested keys (R-01, R-07)

**Proposed Safeguard**: 
- Add deep merge utility for cards dict, or
- Preserve step.yaml `data` for k-path formats when extracted_cards lacks it
- Location: `calculation.py:662-666`

**Priority**: High (already causes test failures)

### Gap 2: No Validation of Extracted Cards Completeness

**Issue**: `_extract_cards()` can return incomplete cards, merge loses step.yaml data

**Proposed Safeguard**:
- Validate extracted cards before merge (e.g., K_POINTS k-path requires data)
- Location: `calculation.py:646` (before merge)

**Priority**: High

### Gap 3: Default Template Validation Missing

**Issue**: No static check preventing invalid partial cards in defaults (R-04 fixed manually but could recur)

**Proposed Safeguard**:
- Unit test that validates all defaults don't contain invalid partial cards
- Location: `tests/unit/test_step_defaults.py` (new)

**Priority**: Medium

### Gap 4: species_overrides Not Forwarded in Step.run()

**Issue**: If `.in` file regenerated, species_overrides from step.yaml may not re-apply (R-05)

**Proposed Safeguard**:
- Forward `species_overrides` in `Step.run()` similar to `card_overrides`
- Location: `step.py:100-123`

**Priority**: Low (works currently via materialization path)

### Gap 5: No Documentation of Merge Precedence

**Issue**: Unclear which data source wins in various merge scenarios

**Proposed Safeguard**:
- Document merge precedence clearly: existing_input_file > step.yaml > defaults
- Location: `calculation.py:652` (comment block)

**Priority**: Low (documentation)

---

## Suggested Targeted Tests

### Test 1: Cards Deep Merge Preserves Nested Keys

**Purpose**: Verify that merge preserves step.yaml `K_POINTS.data` when existing_input_file has incomplete K_POINTS

**Setup**:
- step.yaml: `cards: {K_POINTS: {option: "crystal_b", data: [[...]]}}`
- existing_input_file: K_POINTS with only `option: "crystal_b"` (no data)
- Call `_build_step_from_spec()` with existing_input_file

**Assert**: Merged spec.cards["K_POINTS"] has both `option` and `data`

**Location**: `tests/unit/test_calculation_merge.py` (new)

### Test 2: Default Templates Don't Contain Invalid Cards

**Purpose**: Ensure all defaults are valid (no partial K_POINTS, etc.)

**Setup**: Iterate over all step types in `DEFAULT_STEP_PARAMS`

**Assert**: 
- If `cards.K_POINTS.option` is k-path format, `data` must exist
- All cards have required fields

**Location**: `tests/unit/test_step_defaults.py` (new)

### Test 3: Step.run() Forwards card_overrides Correctly

**Purpose**: Verify cards from step.yaml are applied at runtime

**Setup**:
- step.yaml with `cards: {K_POINTS: {option: "automatic", data: [[8,8,8,0,0,0]]}}`
- Mock `run_input_step()` and verify `card_overrides` parameter matches step.yaml cards

**Assert**: `run_input_step()` called with correct `card_overrides`

**Location**: `tests/unit/test_step_run.py` (new)

### Test 4: Round-Trip Cards Preservation

**Purpose**: Verify cards survive round-trip: YAML → spec → input → extraction → merge

**Setup**:
- Create step.yaml with complex cards (K_POINTS with data, ATOMIC_POSITIONS, etc.)
- Generate input, extract, merge, regenerate input

**Assert**: Final input matches original cards

**Location**: `tests/integration/test_cards_roundtrip.py` (new)

### Test 5: Species Overrides Applied During Materialization

**Purpose**: Verify species_overrides from step.yaml are applied even if not forwarded in Step.run()

**Setup**:
- step.yaml with `species_overrides: {Si: {pseudopot: "Si.UPF"}}`
- Materialize step, check generated `.in` file

**Assert**: ATOMIC_SPECIES card contains correct pseudopotential

**Location**: `tests/integration/test_species_overrides.py` (new)

---

## Appendix: Evidence Snippets

### Q1: step.yaml Fields

**File**: `src/qmatsuite/calculation/structure_steps.py:171-202`
```python
def to_dict(self) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "meta": self.meta.to_dict(),
        "step_type": self.step_type,
    }
    if self.parameters:
        data["parameters"] = self.parameters
    if self.input_name:
        data["input_name"] = self.input_name
    if self.cards:
        data["cards"] = self.cards
    if self.species_overrides:
        data["species_overrides"] = self.species_overrides
    if self.kpath_metadata:
        data["kpath_metadata"] = self.kpath_metadata
```

### Q2: In-Memory SSOT

**File**: `src/qmatsuite/calculation/structure_steps.py:34-53` (StructureStepSpec definition)
**File**: `src/qmatsuite/core/yamldoc.py:454-505` (StepDoc definition)

### Q3: Override Channels

- Parameters: `structure_steps.py:514-522`, `input_runner.py:373-374`
- Cards: `structure_steps.py:571`, `input_runner.py:375`, `step.py:100-123`
- Species: `structure_steps.py:575-576`, `input_runner.py:376`, `input_runner.py:682-724`
- Runtime CONTROL: `input_runner.py:377, 379`

### Q4: Override Tracing

**Cards**:
- Read: `structure_steps.py:112` (`cards = data.get("cards") or {}`)
- Apply (materialization): `structure_steps.py:571` (`apply_card_overrides_to_qe_input(qe_input, spec.cards)`)
- Apply (runtime): `input_runner.py:375` (`apply_card_overrides_to_qe_input(qe_input, card_overrides)`)
- Validate: `input_runner.py:748-766` (K_POINTS k-path validation)

**Species**:
- Read: `structure_steps.py:116` (`species_overrides = data.get("species_overrides") or {}`)
- Apply (materialization): `structure_steps.py:575-576` (`apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)`)
- Apply (runtime): `input_runner.py:376` (`apply_species_overrides_to_qe_input(qe_input, species_overrides)`)
- Validate: `pseudo.py` (`ensure_qe_pseudos()`, placeholder detection)

### Q5: Data Loss Locations

**Shallow Merges**:
- `calculation.py:659` (parameters section merge)
- `calculation.py:666` (cards merge)
- `calculation.py:689` (species_overrides merge)

**Conditional Writes**:
- `structure_steps.py:189-198` (only write if non-empty)

### Q6: Step.run() card_overrides Forwarding

**File**: `src/qmatsuite/calculation/step.py:100-123`
```python
# Load cards from step.yaml if available
card_overrides = None
if self.meta.path:
    try:
        from qmatsuite.calculation.structure_steps import StructureStepSpec
        step_yaml_path = (project_root / self.meta.path).resolve()
        if step_yaml_path.exists():
            spec = StructureStepSpec.from_yaml(step_yaml_path)
            if spec.cards:
                card_overrides = copy.deepcopy(spec.cards)
    except Exception as e:
        logger.debug(f"[Step.run] Could not load cards: {e}")

result, _ = run_input_step(
    ...
    card_overrides=card_overrides,  # ✅ Forwarded
)
```

**species_overrides**: NOT explicitly forwarded. Applied during materialization via `generate_qe_input_from_spec()`.

### Q7: Configuration Error Location

**File**: `src/qmatsuite/core/pseudo.py` (placeholder detection)
**File**: Test framework (skip conversion)

**Check**: `is_missing_pseudo_placeholder(filename)` detects `<filename>` pattern
**Action**: `ensure_qe_pseudos()` raises error if placeholder detected
**Test Behavior**: Error converted to skip with message "configuration error, not missing file"

---

## Conclusion

The pipeline has multiple safeguards but several gaps remain, particularly around shallow merge behavior for cards and parameters. The recent fix to forward `card_overrides` in `Step.run()` addresses one gap, but `species_overrides` forwarding and deep merge for nested dicts are still needed.

**Priority Actions**:
1. Implement deep merge for cards (R-01, R-07)
2. Add validation for extracted cards completeness (R-07)
3. Add unit test for default template validation (R-04)
4. Document merge precedence clearly (documentation)

**Low Priority**:
- Forward species_overrides in Step.run() (R-05)
- Deep merge for parameters/species (R-02, R-03)

