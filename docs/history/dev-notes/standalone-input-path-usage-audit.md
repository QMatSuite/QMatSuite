# Standalone Input / Existing Input File / prepare_input_step(overrides) Path Usage Audit

**Date**: 2025-01-XX  
**Purpose**: Enumerate all entry points and call-sites that use the "parse existing .in + apply overrides" path (Path S) vs "YAML SSOT clean rewrite" path (Path P).

**Status**: Review only - no code changes

---

## Executive Summary

This audit identifies all code paths that either use standalone QE input execution or parse/reuse existing `.in` files with overrides, distinguishing them from the production YAML SSOT path.

**Key Findings**:
1. **Path P (Production YAML SSOT)**: Used by GUI workflows, daemon `run_calculation`/`run_step`, and production CLI
2. **Path S (Standalone/Existing-input)**: Used by CLI standalone mode, calculation.yaml `existing_input_file` entries, GUI import (non-execution), and some tests
3. **GUI Status**: GUI does NOT use Path S for execution. It only uses `import_step_from_qe_input` to create step.yaml (no run)
4. **Risk**: `calculation.yaml` step entries with `input:` field can trigger Path S merge logic, potentially violating SSOT

**Critical Entry Points**:
- **CLI**: `qms run step --standalone --input` (Path S - standalone only)
- **calculation.yaml**: Step entry with `input:` or `file:` field (Path S - rare in production)
- **GUI**: `import_step_from_qe_input` (Path S - but only for import, not execution)
- **Tests**: Various uses of `prepare_input_step`/`run_input_step` directly

---

## Definitions: "Production YAML SSOT path" vs "Standalone/Existing-input path"

### Path P (Production YAML SSOT)

**Flow**:
```
step.yaml (spec truth)
  ↓ StructureStepSpec.from_yaml()
  ↓ generate_qe_input_from_spec(structure, spec)
  ↓ generate_qe_input_from_structure() (creates fresh QEInput)
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
  ↓ apply_species_overrides_to_qe_input(qe_input, spec.species_overrides)
  ↓ QEInputGenerator.write_file(qe_input, output_path)  (clean rewrite)
output .in file (versioned, generated from YAML)
  ↓ Step.run()
  ↓ run_input_step(..., card_overrides=spec.cards)  (re-applies if needed)
  ↓ prepare_input_step(input_file, ..., card_overrides, species_overrides)
  ↓ QEInputParser.parse_file(input_file)  (reads what we just wrote)
  ↓ apply_card_overrides_to_qe_input(qe_input, card_overrides)  (re-validates)
  ↓ apply_species_overrides_to_qe_input(qe_input, species_overrides)
  ↓ QEInputGenerator.write_file(qe_input, working_dir_input)  (final version)
runner execution
```

**Characteristics**:
- step.yaml is the single source of truth
- `.in` file is generated from YAML/spec (clean rewrite)
- No parsing of pre-existing `.in` files during materialization
- Overrides in `prepare_input_step()` are re-validation/application from step.yaml, not merge from external source

**Evidence**: `structure_steps.py:487-578` (`generate_qe_input_from_spec()`)

### Path S (Standalone/Existing-input)

**Flow (Standalone mode)**:
```
existing .in file (user-provided)
  ↓ QEInputParser.parse_file(existing_input_file)
existing_qe_input (in-memory)
  ↓ [Optional: apply overrides]
  ↓ QEInputGenerator.write_file(qe_input, generated_input)  (normalized)
generated .in file (parsed → normalized → written)
  ↓ run_input_step(...)
  ↓ prepare_input_step(input_file, ..., card_overrides=None, species_overrides=None)
  ↓ QEInputParser.parse_file(input_file)
  ↓ [Runtime overrides applied: outdir, pseudo_dir]
  ↓ QEInputGenerator.write_file(qe_input, working_dir_input)
runner execution
```

**Flow (Existing input file from calculation.yaml)**:
```
calculation.yaml step entry with input: "path/to/file.in"
  ↓ _build_step() → existing_input_file = resolve(input_path)
  ↓ _build_step_from_spec(..., existing_input_file=...)
  ↓ QEInputParser.parse_file(existing_input_file)  (parse existing .in)
  ↓ _build_step_spec_from_qe_input_data(existing_qe_input, apply_defaults=False)
  ↓ extracted_params, extracted_cards = (dict, dict)
  ↓ spec_preview.parameters[section].update(extracted_params[section])  (merge)
  ↓ spec_preview.cards.update(extracted_cards)  (merge, existing wins)
  ↓ Extract ATOMIC_SPECIES → extracted_overrides
  ↓ spec_preview.species_overrides.update(extracted_overrides)  (merge)
merged spec_preview (existing input takes precedence over step.yaml)
  ↓ materialize_step_spec(spec_preview, ...)
  ↓ generate_qe_input_from_spec() → .in file (from merged spec)
  ↓ Step.run() → runner
```

**Characteristics**:
- Existing `.in` file is parsed and used as data source
- Extracted content is merged with step.yaml (existing input takes precedence)
- Overrides in `prepare_input_step()` may come from parsed input, not step.yaml
- SSOT can be violated if existing input data conflicts with step.yaml

**Evidence**: 
- Standalone: `standalone.py:44-152` (`run_standalone_step()`)
- Existing input: `calculation.py:336-666` (`_build_step()` → `_build_step_from_spec()`)

---

## Inventory of Building Blocks

### 1. prepare_input_step()

**File**: `src/qmatsuite/calculation/input_runner.py:199-400`

**Signature**:
```python
def prepare_input_step(
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
    output_name: Optional[str] = None,
    step_type: Optional[str] = None,
) -> PreparedInputStep
```

**Purpose**: Parse existing `.in` file, apply overrides, write normalized version to working_dir

**Key Behavior**:
- Always parses `input_file` using `QEInputParser.parse_file()`
- Applies `parameter_overrides`, `card_overrides`, `species_overrides` (if provided)
- Forces runtime CONTROL keys (outdir, pseudo_dir)
- Writes final `.in` to working_dir

**Callers**:
- `run_input_step()` (input_runner.py:497)
- `run_standalone_step()` (standalone.py:143 - via `run_input_step()`)
- Tests (various)

### 2. run_input_step()

**File**: `src/qmatsuite/calculation/input_runner.py:458-514`

**Signature**:
```python
def run_input_step(
    engine: QuantumEspressoEngine,
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    step_type: Optional[str] = None,
    timeout: Optional[float] = None,
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    keep_original: bool = True,
    output_name: Optional[str] = None,
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[StepResult, PreparedInputStep]
```

**Purpose**: Convenience function combining `prepare_input_step()` + `run_prepared_step()`

**Callers**:
- `Step.run()` (step.py:115)
- CLI commands (various)
- `run_standalone_step()` (standalone.py:143)

### 3. QEInputParser.parse_file()

**File**: `src/qmatsuite/io/parser/qe_parser.py`

**Purpose**: Parse QE input file (`.in`) into `QEInput` object

**Used in Path S**:
- `prepare_input_step()` always parses input_file (input_runner.py:372)
- `_build_step_from_spec()` parses existing_input_file if provided (calculation.py:601)
- `run_standalone_step()` parses original input (standalone.py:89)

**Used in Path P**:
- `prepare_input_step()` parses generated `.in` file (re-validation, not source)

### 4. generate_qe_input_from_spec()

**File**: `src/qmatsuite/calculation/structure_steps.py:487-578`

**Signature**:
```python
def generate_qe_input_from_spec(
    structure: PMGStructure | PMGMolecule,
    spec: StructureStepSpec,
    extra_overrides: Sequence[ParameterOverride] | None = None,
    *,
    species_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[QEInput, list[ParameterOverride]]
```

**Purpose**: Build QEInput from structure + StructureStepSpec (Path P core function)

**Behavior**:
- Creates fresh `QEInput` from structure (no parsing)
- Applies `spec.parameters`, `spec.cards`, `spec.species_overrides`
- Returns in-memory `QEInput` (caller writes to file)

**Callers**:
- `materialize_step_spec()` (structure_steps.py:1112)
- CLI `_execute_step_spec()` (cli/main.py:4605)

### 5. materialize_step_spec()

**File**: `src/qmatsuite/calculation/structure_steps.py:648-1190`

**Purpose**: Generate `.in` file from StructureStepSpec (Path P materialization)

**Behavior**:
- Calls `generate_qe_input_from_spec()` to create `QEInput`
- Writes `.in` file via `QEInputGenerator.write_file()`
- Handles pseudopotential resolution

**Callers**:
- `_build_step_from_spec()` (calculation.py:726)

### 6. _build_step_from_spec()

**File**: `src/qmatsuite/calculation/calculation.py:558-765`

**Purpose**: Build `Step` from step spec file, optionally merging existing input file

**Key Behavior (Path S trigger)**:
```python
# calculation.py:592-666
if existing_input_file and existing_input_file.exists():
    existing_qe_input = QEInputParser.parse_file(existing_input_file)  # Parse
    extracted_params, extracted_cards = _build_step_spec_from_qe_input_data(...)  # Extract
    spec_preview.parameters[section].update(extracted_params[section])  # Merge
    spec_preview.cards.update(extracted_cards)  # Merge (existing wins)
    # ... extract species_overrides ...
    spec_preview.species_overrides.update(extracted_overrides)  # Merge
# Then materialize merged spec
generated_input, spec = materialize_step_spec(spec_preview, ...)
```

**Callers**:
- `_build_step()` (calculation.py:378) - passes `existing_input_file` if calculation.yaml step entry has `input:` field

### 7. _build_step_spec_from_qe_input_data()

**File**: `src/qmatsuite/calculation/importers.py:49-92`

**Purpose**: Extract parameters and cards from parsed QEInput

**Behavior**:
- Extracts namelist sections → parameters dict
- Extracts cards (K_POINTS, ATOMIC_SPECIES, etc.) → cards dict
- Optionally merges with defaults (`apply_defaults` parameter)

**Used in Path S**:
- `_build_step_from_spec()` when `existing_input_file` exists (calculation.py:646)

### 8. run_standalone_step()

**File**: `src/qmatsuite/calculation/standalone.py:44-152`

**Purpose**: Run QE step without project context (standalone mode)

**Behavior**:
- Parses existing `.in` file
- Normalizes (sets outdir, pseudo_dir)
- Writes normalized version
- Calls `run_input_step()` with generated file

**Callers**:
- CLI `_run_standalone_step()` (cli/main.py:1636)

### 9. Step.run()

**File**: `src/qmatsuite/calculation/step.py:62-127`

**Purpose**: Execute step using engine

**Behavior**:
- Resolves `input_file` path
- Loads cards from step.yaml (if available)
- Calls `run_input_step(..., card_overrides=cards)`

**Note**: In Path P, `Step.input_file` points to generated `.in` file. In Path S (if existing_input_file was used), it points to generated file from merged spec.

**Callers**:
- JobRunner handler (execution/handlers.py:112)
- Tests

### 10. resolve_input_path() / existing_input_file resolution

**File**: `src/qmatsuite/calculation/calculation.py:336-357`

**Purpose**: Resolve `input:` field from calculation.yaml step entry to file path

**Behavior**:
```python
input_path_value = step_data.get("input") or step_data.get("file")
if input_path_value:
    # Resolve path relative to working_dir or calculation_dir
    existing_input_file = (working_dir / input_path).resolve()
    if not existing_input_file.exists():
        existing_input_file = (calculation_dir / input_path).resolve()
```

**Used in**: `_build_step()` (calculation.py:336-357)

---

## Entry Points & Call Graph

### Entry Point 1: CLI `qms run step --standalone --input`

**Command**: `qms run step --standalone --input <file.in>`

**File**: `src/qmatsuite/cli/main.py:1423-1500`

**Call Chain (Path S)**:
```
run_step_command(standalone=True, input=Path)
  ↓ _run_standalone_step(input_file, ...)
  ↓ StandaloneStepContext(input_file=...)
  ↓ run_standalone_step(ctx)  (standalone.py:44)
  ↓ QEInputParser.parse_file(original_input)  (parse existing .in)
  ↓ Normalize (set outdir, pseudo_dir)
  ↓ QEInputGenerator.write_file(qe_input, generated_input)  (write normalized)
  ↓ run_input_step(engine, input_file=generated_input, ...)  (standalone.py:143)
  ↓ prepare_input_step(input_file, ..., card_overrides=None, species_overrides=None)  (input_runner.py:497)
  ↓ QEInputParser.parse_file(input_file)  (re-parse)
  ↓ apply_card_overrides_to_qe_input(qe_input, card_overrides=None)  (no-op)
  ↓ apply_species_overrides_to_qe_input(qe_input, species_overrides=None)  (no-op)
  ↓ set_outdir_to_temp(), set_pseudo_dir_in_input()  (runtime overrides)
  ↓ QEInputGenerator.write_file(qe_input, working_dir_input)
  ↓ run_prepared_step()
  ↓ engine.run_step()
runner execution
```

**Classification**: CLI-only, standalone mode, user-facing, NOT production GUI

**Evidence**: `cli/main.py:1476-1499`

### Entry Point 2: CLI `qms run structure`

**Command**: `qms run structure <structure_id> [--type <step_type>]`

**File**: `src/qmatsuite/cli/main.py:1704-1778`

**Call Chain (Path P)**:
```
run_structure_command(structure, step_type, ...)
  ↓ generate_qe_input_from_structure(structure, step_type, parameter_overrides)  (generate from spec)
  ↓ apply_card_overrides_to_qe_input(qe_input, bundle.card_overrides)  (apply CLI overrides)
  ↓ apply_species_overrides_to_qe_input(qe_input, bundle.species_overrides)  (apply CLI overrides)
  ↓ QEInputGenerator.write_file(qe_input, generated_input)  (write fresh .in)
  ↓ run_input_step(engine, input_file=generated_input, ..., card_overrides=None, species_overrides=None)  (cli/main.py:1763)
  ↓ prepare_input_step(input_file, ..., card_overrides=None, species_overrides=None)  (input_runner.py:497)
  ↓ QEInputParser.parse_file(input_file)  (parse what we just wrote - re-validation)
  ↓ Runtime overrides (outdir, pseudo_dir)
  ↓ run_prepared_step()
runner execution
```

**Classification**: CLI-only, user-facing, Path P (generates from structure, not from existing file)

**Evidence**: `cli/main.py:1751-1772`

### Entry Point 3: CLI `qms run step` (Project mode)

**Command**: `qms run step --calculation <calc> --step <step>`

**File**: `src/qmatsuite/cli/main.py:1427-1599`

**Call Chain (Path P)**:
```
run_step_command(calculation=..., step=..., standalone=False)
  ↓ ProjectContext.load()
  ↓ resolve_step_for_cli()
  ↓ QMSService.run_step(project_root, calculation_selector, step_selector)
  ↓ Calculation.from_yaml() → materialize_steps=True
  ↓ _build_step(step_data, ...)  (calculation.py:247)
  ↓ _build_step_from_spec(..., existing_input_file=None)  (calculation.py:378)  # No existing_input_file
  ↓ materialize_step_spec(spec_preview, ...)  (generate from spec)
  ↓ generate_qe_input_from_spec(structure, spec)  (Path P core)
  ↓ write .in file
  ↓ Step.run()
  ↓ run_input_step(..., card_overrides=spec.cards)  (step.py:115)
  ↓ prepare_input_step(..., card_overrides, species_overrides=None)  (re-apply from step.yaml)
runner execution
```

**Classification**: CLI, production path, Path P (unless calculation.yaml has `input:` field)

**Evidence**: `cli/main.py:1506-1599`, `api.py` (QMSService.run_step)

### Entry Point 4: Calculation.yaml step entry with `input:` field

**Location**: `calculation.yaml` step entry

**Example**:
```yaml
steps:
- step_id: 01...
  type: scf
  input: "raw/scf.in"  # ← Triggers Path S
```

**Call Chain (Path S)**:
```
Calculation.from_yaml(materialize_steps=True)  (calculation.py:144)
  ↓ _build_step(step_data, ...)  (calculation.py:247)
  ↓ existing_input_file = resolve(step_data.get("input"))  (calculation.py:336-357)
  ↓ _build_step_from_spec(..., existing_input_file=...)  (calculation.py:378)
  ↓ QEInputParser.parse_file(existing_input_file)  (calculation.py:601)  # Parse existing .in
  ↓ _build_step_spec_from_qe_input_data(existing_qe_input, apply_defaults=False)  (calculation.py:646)
  ↓ spec_preview.parameters[section].update(extracted_params[section])  (merge, existing wins)
  ↓ spec_preview.cards.update(extracted_cards)  (merge, existing wins)  ⚠️ SSOT violation risk
  ↓ spec_preview.species_overrides.update(extracted_overrides)  (merge, existing wins)
merged spec_preview (existing input data overwrites step.yaml)
  ↓ materialize_step_spec(spec_preview, ...)  (generate from merged spec)
  ↓ generate_qe_input_from_spec() → .in file
  ↓ Step.run() → runner
```

**Classification**: Internal (calculation.yaml), Path S, SSOT violation risk

**Evidence**: `calculation.py:336-666`

**Current Usage**: Rare in production (likely only for legacy/imported calculations)

### Entry Point 5: GUI `import_step_from_qe_input`

**IPC Endpoint**: `import_step_from_qe_input`

**File**: 
- GUI: `gui/src/components/panels/CalculationListPanel.tsx:667-693`
- Daemon: `src/qmatsuite/daemon/server.py:4228-4268`
- API: `src/qmatsuite/api.py:5550-5648`

**Call Chain (Path S - Import only, no execution)**:
```
GUI: handleImportStep()
  ↓ window.qms.request('import_step_from_qe_input', {input_file: ...})
  ↓ Daemon: _handle_import_step_from_qe_input()
  ↓ QMSService.import_step_from_qe_input(project_root, calculation_ulid, input_file, ...)
  ↓ build_step_spec_from_qe_input(input_file, ..., apply_defaults=False)  (importers.py:95)
  ↓ QEInputParser.parse_file(input_file)  (parse existing .in)
  ↓ _build_step_spec_from_qe_input_data(qe_input, step_type, apply_defaults=False)  (importers.py:49)
  ↓ Extract parameters, cards, species_overrides
  ↓ Create StructureStepSpec from extracted data
  ↓ Save step.yaml (via StepDoc)
  ↓ Return step detail
NO EXECUTION - just creates step.yaml from .in file
```

**Classification**: GUI, import-only (not execution), Path S (for import), production

**Evidence**: 
- GUI: `gui/src/components/panels/CalculationListPanel.tsx:688`
- Daemon: `daemon/server.py:4228`
- API: `api.py:5550`

**Note**: This does NOT trigger Path S execution. It only imports `.in` file into step.yaml format.

### Entry Point 6: GUI `run_calculation`

**IPC Endpoint**: `run_calculation`

**File**:
- GUI: `gui/src/App.tsx:1748`
- Daemon: `src/qmatsuite/daemon/server.py:5356-5419`
- API: `src/qmatsuite/api.py` (QMSService.run_calculation)

**Call Chain (Path P)**:
```
GUI: handleRunCalculation()
  ↓ window.qms.call('run_calculation', {calculation: ...})
  ↓ Daemon: _handle_run_calculation()
  ↓ QMSService.run_calculation(project_root, calculation_selector, ...)
  ↓ Calculation.from_yaml() → materialize_steps=True
  ↓ _build_step() → _build_step_from_spec(..., existing_input_file=None)  # No existing_input_file
  ↓ materialize_step_spec() → generate_qe_input_from_spec()  (Path P)
  ↓ JobRunner handler → Step.run()
  ↓ run_input_step(..., card_overrides=spec.cards)
runner execution
```

**Classification**: GUI, production, Path P

**Evidence**: 
- GUI: `gui/src/App.tsx:1748`
- Daemon: `daemon/server.py:5356`

### Entry Point 7: GUI `run_step`

**IPC Endpoint**: `run_step`

**File**:
- GUI: `gui/src/components/panels/StepDetailPanel.tsx:590`
- Daemon: `src/qmatsuite/daemon/server.py:5450-5508`

**Call Chain (Path P)**:
```
GUI: handleRunStep()
  ↓ window.qms.request('run_step', {calculation: ..., step: ...})
  ↓ Daemon: _handle_run_step()
  ↓ QMSService.run_step(project_root, calculation_selector, step_selector, ...)
  ↓ Calculation.from_yaml() → materialize_steps=True
  ↓ _build_step() → _build_step_from_spec(..., existing_input_file=None)  # Path P
  ↓ JobRunner → Step.run()
runner execution
```

**Classification**: GUI, production, Path P

**Evidence**: 
- GUI: `gui/src/components/panels/StepDetailPanel.tsx:590`
- Daemon: `daemon/server.py:5450`

### Entry Point 8: Tests

**Files**:
- `tests/unit/test_project_and_cli.py`
- `tests/examples/test_cli_usage_examples.py`
- `tests/core/qe_step_runner.py`
- `tests/unit/test_calculation_importers.py`

**Usage Patterns**:
1. Direct `prepare_input_step()` calls with existing `.in` files
2. Direct `run_input_step()` calls
3. Mocked paths for testing

**Classification**: Tests, internal, Path S (for testing purposes)

**Evidence**: Multiple test files (see grep results)

---

## Usage Classification Matrix

| Entry Point | Path | Requires Project? | Accepts Overrides? | Audience | Recommendation |
|------------|------|-------------------|-------------------|----------|----------------|
| CLI `qms run step --standalone --input` | S | No | No (standalone only) | User (CLI) | CLI-only, keep but document as non-production |
| CLI `qms run structure` | P | Yes (optional) | Yes (parameters/cards/species) | User (CLI) | CLI-only, production |
| CLI `qms run step` (project mode) | P* | Yes | Via step.yaml | User (CLI) | Production (Path S only if calculation.yaml has `input:`) |
| calculation.yaml `input:` field | S | Yes | Via merge | Internal | **Risk**: SSOT violation. Should be deprecated/removed |
| GUI `import_step_from_qe_input` | S (import only) | Yes | No | User (GUI) | Production (import only, no execution) |
| GUI `run_calculation` | P | Yes | Via step.yaml | User (GUI) | Production |
| GUI `run_step` | P | Yes | Via step.yaml | User (GUI) | Production |
| Tests | S/P | Mixed | Mixed | Internal | Test-only, acceptable |

**Legend**:
- **Path P***: Normally Path P, but becomes Path S if calculation.yaml step entry has `input:` field
- **Overrides**: Refers to runtime overrides in `prepare_input_step()` parameters

**Key Findings**:
- ✅ **GUI does NOT use Path S for execution** (only for import)
- ⚠️ **calculation.yaml `input:` field triggers Path S** (potential SSOT violation)
- ⚠️ **CLI standalone is Path S** (intended, but non-production)

---

## Runtime Behavior Differences

### 1. SSOT Violations

**Path P**: step.yaml is authoritative. All `.in` content comes from YAML/spec.

**Path S**: Existing `.in` file content takes precedence over step.yaml during merge.

**Example**:
```python
# calculation.py:663-666
spec_preview.cards.update(extracted_cards)  # Existing input wins
```

If step.yaml has `K_POINTS: {option: "crystal_b", data: [...]}` but existing `.in` has only `K_POINTS automatic`, the merge loses `data`.

**Risk**: `calculation.py:662-666` - shallow merge can lose nested keys.

**Evidence**: `calculation.py:652-689` (merge logic)

### 2. Merge Precedence Risks

**Path P**: No merge conflicts. YAML → spec → QEInput is one-way.

**Path S**: Merge precedence is "existing input wins", but implementation is shallow merge:
- `spec.parameters[section].update(extracted_params[section])` - section-level merge
- `spec.cards.update(extracted_cards)` - top-level dict replace (loses nested keys)
- `spec.species_overrides.update(extracted_overrides)` - top-level dict replace

**Risk**: Shallow merge loses nested keys (e.g., K_POINTS.data).

**Evidence**: `calculation.py:657-689`

### 3. Reproducibility Risks

**Path P**: Fully reproducible. step.yaml → `.in` is deterministic.

**Path S**: Depends on existing `.in` file content. If file changes or is incomplete, results vary.

**Risk**: Non-deterministic if existing `.in` is modified or incomplete.

**Evidence**: `calculation.py:594-666` (conditional merge based on file existence)

### 4. Debugging Complexity

**Path P**: Clear data flow: YAML → spec → `.in` → runner

**Path S**: Confusing data flow: YAML + existing `.in` → merge → spec → `.in` → runner. Hard to trace which values came from where.

**Risk**: Difficult to debug when values don't match expectations.

**Evidence**: Merge logic in `calculation.py:652-689` mixes sources

### 5. Validation Timing

**Path P**: Validation happens during materialization (fail-fast if invalid).

**Path S**: Validation happens in `apply_card_overrides_to_qe_input()` after merge. If existing input is invalid, merge may create invalid merged spec.

**Risk**: Invalid existing input may create invalid merged spec, only caught later.

**Evidence**: `input_runner.py:755-759` (K_POINTS validation)

---

## Risk Assessment

### Risk 1: calculation.yaml `input:` Field Triggers Path S (High Severity)

**Location**: `calculation.py:336-388`

**Symptom**: If calculation.yaml step entry has `input:` field, `existing_input_file` is set, triggering merge logic that violates SSOT.

**Evidence**:
```python
# calculation.py:336-357
input_path_value = step_data.get("input") or step_data.get("file")
if input_path_value:
    existing_input_file = (working_dir / input_path).resolve()
    # ...
    _build_step_from_spec(..., existing_input_file=existing_input_file)  # Triggers Path S
```

**Current Usage**: Unknown (rare in production, likely only legacy)

**Recommendation**: Deprecate `input:` field in calculation.yaml. If needed, use import workflow instead.

### Risk 2: Shallow Merge Loses Nested Keys (High Severity)

**Location**: `calculation.py:662-666`

**Symptom**: `spec.cards.update(extracted_cards)` replaces entire dict, losing nested keys (e.g., K_POINTS.data).

**Evidence**: See R-01 in `yaml-to-runner-fidelity-audit.md`

**Recommendation**: Deep merge or preserve step.yaml data for required fields (K_POINTS.data for k-path formats).

### Risk 3: GUI May Indirectly Trigger Path S via calculation.yaml (Medium Severity)

**Location**: GUI → daemon → Calculation.from_yaml() → _build_step()

**Symptom**: If calculation.yaml has `input:` field (from import or manual edit), GUI `run_calculation` would trigger Path S.

**Evidence**: GUI uses `QMSService.run_calculation()` → `Calculation.from_yaml()` → `_build_step()` which checks for `input:` field.

**Current Usage**: GUI does not set `input:` field, but it could be set manually or via import.

**Recommendation**: Validate that GUI workflows never set `input:` field. Document that `input:` field is deprecated.

### Risk 4: Standalone CLI Usage in Production (Low Severity)

**Location**: `cli/main.py:1476-1499`

**Symptom**: Users may use `qms run step --standalone --input` in production workflows, bypassing YAML SSOT.

**Recommendation**: Document that standalone mode is for one-off testing, not production workflows.

---

## Recommendations (Policy-Level Only)

### Recommendation 1: Deprecate calculation.yaml `input:` Field

**Policy**: Mark `input:` and `file:` fields in calculation.yaml step entries as deprecated.

**Rationale**: These fields trigger Path S merge logic, violating SSOT principle.

**Action** (no code changes):
- Document that `input:` field should not be used in new calculations
- Add warning if `input:` field is detected (future enhancement)
- Recommend using `import_step_from_qe_input` workflow instead

### Recommendation 2: Document Path S as Non-Production

**Policy**: Clearly document that Path S (standalone/existing input) is for:
- One-off testing/debugging (CLI standalone)
- Import workflows (creating step.yaml from .in)
- NOT for production GUI workflows

**Action**:
- Add docstring note to `_build_step_from_spec()` that `existing_input_file` is legacy
- Document CLI standalone mode as non-production
- Add note to architecture docs that production is YAML SSOT only

### Recommendation 3: Validate GUI Never Sets `input:` Field

**Policy**: Ensure GUI workflows never create or modify calculation.yaml step entries with `input:` field.

**Action** (no code changes, documentation):
- Document that `QMSService` methods should not set `input:` field
- Add static check (future) preventing `input:` field in new calculations

### Recommendation 4: Rename for Clarity (Optional)

**Policy**: Consider renaming to make distinction obvious:
- `existing_input_file` → `legacy_input_file` or `import_source_file`
- `_build_step_from_spec(existing_input_file=...)` → document as "legacy import path"

**Action**: Documentation only (no code changes)

### Recommendation 5: Minimal Doc Note

**Policy**: Add clear policy statement:
> "Production workflows use YAML SSOT with clean rewrite of `.in` files from step.yaml. Standalone/existing input parsing is for one-off testing and import workflows only, not production execution."

**Action**: Add to architecture documentation

---

## Appendix: Evidence Snippets

### Snippet 1: CLI Standalone Entry Point

**File**: `src/qmatsuite/cli/main.py:1476-1499`

```python
if standalone:
    if not input:
        raise typer.BadParameter(
            "--input is required in standalone mode. "
            "Example: qms run step --standalone --input pw.in"
        )
    _run_standalone_step(
        input_file=input,
        workdir=working_dir,
        engine_name=engine,
    )
    return
```

### Snippet 2: Standalone Step Execution

**File**: `src/qmatsuite/calculation/standalone.py:88-152`

```python
# Parse original input and generate normalized version
qe_input = QEInputParser.parse_file(original_input)  # ← Parse existing .in

# Set outdir in the QE input (relative to workdir) if not already set
# ... normalize ...

# Generate normalized input file
generated_input = workdir / f"{original_input.stem}.in"
QEInputGenerator.write_file(qe_input, generated_input)

# Use generated input for the run
result, prepared = run_input_step(
    engine=ctx.engine,
    input_file=input_for_run,
    working_dir=workdir,
    project_root=None,  # Standalone mode: no project
    step_type=None,  # Auto-detect from input
    keep_original=False,
)
```

### Snippet 3: Existing Input File Resolution

**File**: `src/qmatsuite/calculation/calculation.py:336-357`

```python
input_path_value = step_data.get("input") or step_data.get("file")
input_path: Optional[Path] = None
existing_input_file: Optional[Path] = None
if input_path_value:
    input_path = Path(input_path_value)
    # ... resolve path ...
    if input_path:
        existing_input_file = (working_dir / input_path).resolve()
        if not existing_input_file.exists():
            existing_input_file = (calculation_dir / input_path).resolve()
            if not existing_input_file.exists():
                existing_input_file = None
```

### Snippet 4: Merge Logic (Path S)

**File**: `src/qmatsuite/calculation/calculation.py:644-666`

```python
# Extract all parameters and cards from the existing input file
extracted_params, extracted_cards = _build_step_spec_from_qe_input_data(
    existing_qe_input,
    spec_preview.step_type or "scf",
    apply_defaults=False,
)

# Merge extracted parameters into step spec (existing input takes precedence)
if extracted_params:
    if not spec_preview.parameters:
        spec_preview.parameters = {}
    for section, params in extracted_params.items():
        if section not in spec_preview.parameters:
            spec_preview.parameters[section] = {}
        spec_preview.parameters[section].update(params)  # Section-level merge

# Merge extracted cards into step spec (existing input takes precedence)
if extracted_cards:
    if not spec_preview.cards:
        spec_preview.cards = {}
    spec_preview.cards.update(extracted_cards)  # ← Top-level replace (loses nested keys)
```

### Snippet 5: GUI Import (Non-Execution)

**File**: `src/qmatsuite/api.py:5550-5648`

```python
def import_step_from_qe_input(
    project_root: Path,
    calculation_ulid: str,
    input_file: Path,
    step_name: Optional[str] = None,
    ...
) -> Dict[str, Any]:
    """Import a QE input file as a step in a calculation (preserves original parameters)."""
    # ...
    result = build_step_spec_from_qe_input(
        input_file=input_file,
        destination_dir=step_dir,
        ...
        apply_defaults=False,  # Preserve original parameters
    )
    # Creates step.yaml from .in file
    # NO EXECUTION - just import
```

### Snippet 6: GUI Run Calculation (Path P)

**File**: `src/qmatsuite/daemon/server.py:5356-5419`

```python
def _handle_run_calculation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Submit a calculation run job."""
    project_root = self._require_path(payload, "project_root")
    calculation_selector = self._require_str(payload, "calculation")
    
    result = QMSService.run_calculation(
        project_root=project_root,
        calculation_selector=calculation_selector,
        ...
    )
    # → Calculation.from_yaml() → _build_step() → Path P (no existing_input_file)
```

### Snippet 7: Step.run() Card Overrides Forwarding

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
    card_overrides=card_overrides,  # Forward from step.yaml
)
```

### Snippet 8: prepare_input_step() Always Parses

**File**: `src/qmatsuite/calculation/input_runner.py:371-380`

```python
try:
    qe_input = QEInputParser.parse_file(input_file)  # ← Always parses
    if parameter_overrides:
        _apply_parameter_overrides(qe_input, parameter_overrides)
    apply_card_overrides_to_qe_input(qe_input, card_overrides)  # Apply overrides
    apply_species_overrides_to_qe_input(qe_input, species_overrides)
    set_outdir_to_temp(qe_input)  # Runtime override
    set_pseudo_dir_in_input(qe_input, project_pseudo_dir, working_dir)
    QEInputGenerator.write_file(qe_input, working_dir_input)
```

### Snippet 9: Path P Materialization

**File**: `src/qmatsuite/calculation/structure_steps.py:487-578`

```python
def generate_qe_input_from_spec(...) -> tuple[QEInput, list[ParameterOverride]]:
    """Build a QE input from a structure step specification."""
    # ...
    qe_input = generate_qe_input_from_structure(  # ← Creates fresh QEInput
        structure=structure,
        step_type=spec.step_type,
        parameter_overrides=combined_overrides,
    )
    # ...
    apply_card_overrides_to_qe_input(qe_input, spec.cards)  # Apply from spec
    apply_species_overrides_to_qe_input(qe_input, effective_species_overrides)
    return qe_input, combined_overrides  # Returns in-memory QEInput (caller writes)
```

### Snippet 10: Branch Condition for Path S

**File**: `src/qmatsuite/calculation/calculation.py:592-594`

```python
# If there's an existing input file, extract structure, parameters, cards, and pseudopotentials from it
# and merge them into the step spec (existing input takes precedence over step spec defaults)
if existing_input_file and existing_input_file.exists():  # ← Branch condition
    # Path S logic: parse, extract, merge
```

### Snippet 11: GUI Import Handler

**File**: `src/qmatsuite/daemon/server.py:4228-4268`

```python
def _handle_import_step_from_qe_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Import a QE input file as a step (preserves original parameters, no defaults)."""
    # ...
    result = QMSService.import_step_from_qe_input(
        project_root=project_root,
        calculation_ulid=calculation_ulid,
        input_file=input_file,
        step_name=step_name,
        index=cache.index,
        config=cache.config,
    )
    # Returns step detail - NO EXECUTION
```

### Snippet 12: Path P in Calculation.from_yaml()

**File**: `src/qmatsuite/calculation/calculation.py:213-217`

```python
# Execution mode: fully materialize steps (calls materialize_step_spec, requires pseudos)
step, _ = _build_step(
    step_data, calculation_dir, working_dir, project, step_type_counts=step_type_counts
)
# → _build_step() → _build_step_from_spec(..., existing_input_file=...) 
# existing_input_file is None unless calculation.yaml has "input:" field
```

---

## Conclusion

**Summary**:
- ✅ **GUI does NOT use Path S for execution** - confirmed via code review
- ⚠️ **calculation.yaml `input:` field can trigger Path S** - potential SSOT violation
- ✅ **CLI standalone is Path S** - intended, but non-production
- ✅ **GUI import is Path S** - but only for import, not execution

**Critical Finding**: Production GUI workflows (`run_calculation`, `run_step`) use Path P exclusively, UNLESS calculation.yaml has `input:` field (which GUI does not set).

**Recommendation**: Deprecate `input:` field in calculation.yaml to ensure GUI always uses Path P.

