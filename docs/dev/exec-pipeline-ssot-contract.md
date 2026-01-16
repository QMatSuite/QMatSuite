# Execution Pipeline SSOT Contract

**Date**: 2025-01-XX  
**Purpose**: Define the contract for execution pipeline: production run uses YAML SSOT with clean rewrite, never parsing .in files during run.

**Status**: Enforced in code

---

## Executive Summary

**Production run must never parse any .in file during execution.**  
**It must always generate a fresh versioned .in by reading step.yaml (spec SSOT) and writing input cleanly (no append, no reuse).**

`prepare_input_step()` becomes **IMPORT-ONLY**.  
It may parse/extract from an existing QE input .in only for import flows.

"Standalone run" is not a separate execution pipeline. It must be implemented as:  
**(a) import .in to YAML → (b) run YAML using the normal production run pipeline (roundtrip).**

**Absolutely no "parse .in → apply overrides → run" in production run.**

---

## Contract Definitions

### Production Run (Path P)

**Flow**:
```
step.yaml (spec SSOT)
  ↓ StructureStepSpec.from_yaml()
  ↓ materialize_step_spec()
  ↓ generate_qe_input_from_spec(structure, spec)
  ↓ generate_qe_input_from_structure() (creates fresh QEInput)
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
  ↓ apply_species_overrides_to_qe_input(qe_input, spec.species_overrides)
  ↓ set_outdir_to_temp(qe_input)  (runtime override)
  ↓ set_pseudo_dir_in_input(qe_input, project_pseudo_dir, working_dir)  (runtime override)
  ↓ QEInputGenerator.write_file(qe_input, output_path)  (clean rewrite)
output .in file (versioned, generated from YAML)
  ↓ Step.run()
  ↓ engine.backend.run_step(input_file=input_path, ...)  (direct call, no parsing)
runner execution
```

**Key Characteristics**:
- **Never calls `prepare_input_step()`** during production run
- **Never parses .in file** during production run
- **Always generates .in from step.yaml** (YAML SSOT)
- **Runtime overrides (outdir, pseudo_dir)** applied during materialization, not during run
- **Cards/parameters/species** all come from step.yaml

**Entry Points**:
- GUI `run_calculation` / `run_step`
- Daemon `run_calculation` / `run_step`
- CLI `qv run step` (project mode)
- CLI `qv run structure`

**Evidence**:
- `Step.run()` calls `engine.backend.run_step()` directly (step.py:114)
- `_build_step_from_spec()` ignores `existing_input_file` in production run (calculation.py:388)
- `materialize_step_spec()` applies runtime overrides during materialization (structure_steps.py:1138, 1188)

### Import Flow (Path I)

**Flow**:
```
existing .in file (user-provided)
  ↓ QEInputParser.parse_file(existing_input_file)
  ↓ _build_step_spec_from_qe_input_data(qe_input, apply_defaults=False)
  ↓ Extract parameters, cards, species_overrides
  ↓ Create StructureStepSpec from extracted data
  ↓ Write step.yaml (via StepDoc)
output step.yaml (created from .in file)
NO EXECUTION - just creates YAML from .in
```

**Key Characteristics**:
- **Uses `prepare_input_step()` for parsing only** (if needed for import workflows)
- **Never runs execution** (only creates step.yaml)
- **Preserves original parameters** (`apply_defaults=False`)

**Entry Points**:
- GUI `import_step_from_qe_input`
- Daemon `import_step_from_qe_input`
- CLI import commands

**Evidence**:
- `build_step_spec_from_qe_input()` creates step.yaml from .in (importers.py:95)
- `QVService.import_step_from_qe_input()` only creates step.yaml, no execution (api.py:5550)

### Standalone Run (Path S)

**Flow**:
```
existing .in file (user-provided)
  ↓ build_step_spec_from_qe_input()  (Step 1: import .in to YAML)
  ↓ Write step.yaml (temporary)
  ↓ materialize_step_spec()  (Step 2: generate .in from YAML)
  ↓ generate_qe_input_from_spec() → write .in
  ↓ Step.run()  (Step 3: run from YAML using production pipeline)
  ↓ engine.backend.run_step()  (direct call, no parsing)
runner execution
```

**Key Characteristics**:
- **Roundtrip**: import→YAML→run
- **Uses production run pipeline** (Step.run() → engine directly)
- **Never calls `prepare_input_step()`** during run
- **Temporary project structure** created for import, cleaned up after

**Entry Points**:
- CLI `qv run step --standalone --input <file.in>`

**Evidence**:
- `_run_standalone_step()` imports to YAML first, then runs (cli/main.py:1698-1750)
- Uses same `Step.run()` → `engine.backend.run_step()` path as production

---

## Function Roles

### prepare_input_step() — IMPORT-ONLY

**File**: `src/quantumvitas/calculation/input_runner.py:199-400`

**Purpose**: Parse existing .in file and apply overrides (for import workflows only).

**Usage**:
- ✅ Import flows (e.g., `build_step_spec_from_qe_input` parsing .in)
- ✅ Tests that validate import behavior
- ❌ **NOT used in production run** (production generates from YAML)

**Contract**: May parse .in files for import, but never during production execution.

### run_input_step() — DEPRECATED FOR PRODUCTION

**File**: `src/quantumvitas/calculation/input_runner.py:458-514`

**Purpose**: Convenience function combining `prepare_input_step()` + `run_prepared_step()`.

**Usage**:
- ✅ Tests (legacy)
- ❌ **NOT used in production run** (production uses `Step.run()` → engine directly)

**Contract**: Still exists for backwards compatibility in tests, but production run bypasses it.

### Step.run() — PRODUCTION EXECUTION

**File**: `src/quantumvitas/calculation/step.py:63-125`

**Purpose**: Execute step using engine directly (no parsing).

**Contract**:
- **Never calls `prepare_input_step()`**
- **Never parses .in file**
- **Always calls `engine.backend.run_step()` directly**
- Input file is generated from step.yaml by `materialize_step_spec()` with all overrides applied

**Evidence**: `step.py:114` - direct call to `engine.backend.run_step()`

### materialize_step_spec() — GENERATES .IN FROM YAML

**File**: `src/quantumvitas/calculation/structure_steps.py:648-1193`

**Purpose**: Generate .in file from step.yaml (YAML SSOT → clean rewrite).

**Contract**:
- Reads step.yaml (StructureStepSpec)
- Generates fresh QEInput from structure + spec
- Applies cards, parameters, species_overrides from spec
- Applies runtime overrides (outdir, pseudo_dir) during materialization
- Writes versioned .in file (no parsing, clean rewrite)

**Evidence**: `structure_steps.py:1188` - applies runtime overrides, then writes

---

## Runtime Overrides

Runtime overrides (outdir, pseudo_dir) are applied **during materialization**, not during run:

**Location**: `structure_steps.py:1138, 1188`

```python
# During materialize_step_spec():
set_outdir_to_temp(qe_input)  # Force outdir = "./outdir"
set_pseudo_dir_in_input(qe_input, project_pseudo_dir, working_dir)  # Force pseudo_dir = "../pseudo"
QEInputGenerator.write_file(qe_input, generated_input)  # Write with overrides applied
```

**Contract**: Runtime overrides are baked into the generated .in file, so `Step.run()` doesn't need to re-parse or modify it.

---

## existing_input_file — IMPORT-ONLY

**File**: `src/quantumvitas/calculation/calculation.py:336-388`

**Purpose**: Legacy field from calculation.yaml step entry (`input:` or `file:` field).

**Contract**:
- **Ignored in production run** (always None)
- **Used only for import workflows** (e.g., `build_step_spec_from_qe_input`)
- **Never triggers Path S merge logic** in production execution

**Evidence**: `calculation.py:388` - `existing_input_file=None` forced in production run

**Deprecation**: The `input:` field in calculation.yaml is deprecated. Production run always uses YAML SSOT (step.yaml → generate .in).

---

## Standalone Implementation

**File**: `src/quantumvitas/cli/main.py:1636-1762`

**Implementation**:
1. **Import phase**: `build_step_spec_from_qe_input()` creates temporary step.yaml from .in
2. **Materialization phase**: `materialize_step_spec()` generates .in from step.yaml (production path)
3. **Execution phase**: `Step.run()` → `engine.backend.run_step()` (production path)

**Contract**: Standalone is **NOT a separate execution pipeline**. It's a roundtrip: import→YAML→run (uses production pipeline).

**Evidence**: `cli/main.py:1698-1750` - import first, then materialize, then run

---

## Validation & Enforcement

### Code Enforcement

1. **`Step.run()` never calls `prepare_input_step()`**
   - Evidence: `step.py:114` - direct `engine.backend.run_step()` call

2. **`_build_step_from_spec()` ignores `existing_input_file` in production run**
   - Evidence: `calculation.py:388` - `existing_input_file=None` forced

3. **`materialize_step_spec()` applies runtime overrides during materialization**
   - Evidence: `structure_steps.py:1138, 1188` - overrides applied before write

### Test Enforcement

Tests should validate:
- Production run never calls `prepare_input_step()` (monkeypatch/mock check)
- Standalone performs import→run, not parse+patch
- Generated .in files come from step.yaml, not parsed from existing .in

---

## Migration Notes

### From Old Contract (Path S merge logic)

**Old behavior** (deprecated):
- Production run could parse existing .in and merge with step.yaml
- `prepare_input_step()` called during production run
- `existing_input_file` triggered merge logic in production run

**New behavior** (enforced):
- Production run **never** parses .in files
- Production run **always** generates .in from step.yaml
- `prepare_input_step()` is import-only
- `existing_input_file` is ignored in production run

### Backwards Compatibility

- Legacy calculation.yaml with `input:` field will be ignored (no merge)
- Old tests that relied on `prepare_input_step()` during run may need updates
- Standalone mode changed from parse+patch to import→run (same result, different path)

---

## Summary

**Production Run Contract**:
- ✅ YAML SSOT → clean rewrite .in → run (no parsing .in)
- ✅ Runtime overrides applied during materialization
- ✅ `Step.run()` calls engine directly, no `prepare_input_step()`

**Import Contract**:
- ✅ Uses `prepare_input_step()` for parsing .in to YAML
- ✅ No execution during import

**Standalone Contract**:
- ✅ Roundtrip: import .in to YAML → run YAML (uses production pipeline)
- ✅ Not a separate execution path

**existing_input_file Contract**:
- ✅ Import-only (not used in production run)

