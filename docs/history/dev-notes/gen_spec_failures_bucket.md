# GEN/SPEC Test Failures Bucket Analysis

## Overview

250 test failures after Phase 3-5 completion. Categorized into 3 buckets with unified fix strategies.

## Bucket A: Function Parameter Name Mismatches (120 failures)

**Pattern**: Tests call functions with wrong parameter names.

### A1: `step_type_gen=` → `step_type_spec=` (Execution Layer)

**Issue**: Execution layer functions expect `step_type_spec`, but tests pass `step_type_gen`.

**Affected Functions**:
- `handle_pyscf_relax_output(step_type_gen=...)` → `step_type_spec=...`
- `handle_orca_relax_output(step_type_gen=...)` → `step_type_spec=...`
- `QuantumEspressoEngine.run_step(step_type_gen=...)` → `step_type_spec=...`
- `QECalculationRunner.run_step(step_type_gen=...)` → `step_type_spec=...`
- `Engine.run_step(step_type_gen=...)` → `step_type_spec=...`

**Fix Strategy**:
1. Find all calls to execution layer functions with `step_type_gen=`
2. Replace with `step_type_spec=`
3. If test has GEN type, convert to SPEC: `step_type_spec=spec_from(engine_prefix, step_type_gen)`

**Files to Fix**:
- `tests/unit/execution/test_pyscf_relax_handler.py`
- `tests/unit/execution/test_orca_relax_parser.py`
- `tests/unit/test_output_file_overwrite.py`
- `tests/integration/test_pw_step_specs.py`
- `tests/integration/test_pw_scf_ibrav_step_specs.py`

### A2: `spec_from(engine_prefix=...)` → `spec_from(prefix=...)`

**Issue**: `spec_from()` function signature is `spec_from(prefix: str, gen: str)`, but code calls with `engine_prefix=`.

**Fix Strategy**:
1. Find all calls to `spec_from(engine_prefix=...)`
2. Replace with `spec_from(prefix=...)`

**Files to Fix**:
- `src/quantumvitas/engine/lammps_writer.py:68`
- Any other files using `spec_from(engine_prefix=...)`

### A3: Other Parameter Name Mismatches

**Pattern**: Various other parameter name mismatches in function calls.

**Fix Strategy**: Fix case-by-case based on function signatures.

---

## Bucket B: Wrong Step Type Namespace (53 failures)

**Pattern**: Tests use SPEC types where GEN types are expected, or vice versa.

### B1: SPEC Type Used as GEN Type

**Issue**: Tests pass SPEC types (e.g., `"qe_scf"`, `"vasp_scf"`) where GEN types are expected.

**Examples**:
- `step_type_gen="qe_scf"` → should be `step_type_gen="scf"`
- `step_type_gen="qe_relax"` → should be `step_type_gen="relax"`
- `step_type_gen="vasp_scf"` → should be `step_type_gen="scf"`
- `step_type_gen="orca_scf"` → should be `step_type_gen="scf"`
- `step_type_gen="pyscf_relax"` → should be `step_type_gen="relax"`

**Fix Strategy**:
1. Identify all test code using SPEC types as GEN types
2. Extract GEN type using `gen_from(spec_type)` or manual conversion
3. Update test to use GEN type

**Files to Fix**:
- `tests/contract_crawler/recipes/*.py` - Many uses of `step_type_gen="qe_scf"` etc.
- `tests/integration/vasp/test_vasp_project_e2e.py`
- `tests/integration/orca/test_orca_project_level.py`
- `tests/unit/execution/test_relax_artifacts.py`
- `tests/integration/test_relax_e2e.py`
- `tests/daemon/test_promote_relax_structure.py`

### B2: "Unknown step type" Errors

**Issue**: API/registry functions receive SPEC types but expect GEN types (or vice versa).

**Examples**:
- `ValidationError: Unknown step type: qe_scf` - API expects GEN type but receives SPEC
- Registry lookups fail because wrong namespace used

**Fix Strategy**:
1. Identify where SPEC types are passed to functions expecting GEN types
2. Convert using `gen_from(spec_type)` before passing
3. Or identify where GEN types are passed to functions expecting SPEC types
4. Convert using `spec_from(prefix, gen_type)` before passing

**Files to Fix**:
- `tests/contract_crawler/test_golden_contracts.py` - All 30+ failures
- Various API test files

---

## Bucket C: Undefined Variables and Bare step_type (77 failures)

**Pattern**: Tests use undefined `step_type` variable or bare `step_type` field.

### C1: Undefined `step_type` Variable

**Issue**: Test code references `step_type` variable that doesn't exist.

**Examples**:
- `step_type_gen=step_type` where `step_type` is undefined
- Should be `step_type_gen=...` or `step_type_spec=...` with explicit value

**Fix Strategy**:
1. Find all undefined `step_type` references
2. Replace with explicit `step_type_gen=` or `step_type_spec=` based on context
3. If value comes from step object, use `step.step_type_gen` or `step.step_type_spec`

**Files to Fix**:
- `tests/unit/execution/test_pyscf_relax_handler.py:45` - `step_type_gen=step_type` where `step_type` undefined
- `tests/unit/execution/test_orca_relax_parser.py` - Similar issues

### C2: Bare `step_type` Field Usage

**Issue**: Tests access `step.step_type` or `step["step_type"]` which no longer exists.

**Fix Strategy**:
1. Replace `step.step_type` with `step.step_type_spec` or `step.step_type_gen` based on context
2. Replace `step.get("step_type")` with `step.get("step_type_spec")` or `step.get("step_type_gen")`
3. If both needed, access both explicitly

**Files to Fix**:
- Various test files accessing step objects

---

## Fix Order

1. **Bucket A** - Function parameter names (mechanical, high impact)
2. **Bucket B** - Step type namespace errors (requires understanding context)
3. **Bucket C** - Undefined variables (mechanical, but may need context)

## Rules

- **NO bare `step_type` compatibility shims** - Always use explicit `step_type_gen` or `step_type_spec`
- **Cross-layer conversion MUST be explicit** - Use `gen_from()` or `spec_from()` functions
- **Execution layer = SPEC only** - All execution/runner functions use `step_type_spec`
- **Preset/UI layer = GEN only** - All preset/workflow functions use `step_type_gen`

