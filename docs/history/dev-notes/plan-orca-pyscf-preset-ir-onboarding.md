# ORCA/PySCF Preset/IR Onboarding Implementation Plan

**Date**: 2025-01-XX  
**Status**: Ready for Execution  
**Purpose**: Concrete, PR-by-PR execution plan for onboarding ORCA/PySCF preset/IR while keeping existing QE/PW behavior stable.

---

## 0. Executive Intent

**What we ARE implementing:**
- Introduce `ir.pw` and `ir.qc` dialect namespaces as conceptual organization (minimal code changes)
- Add QC precision preset for ORCA/PySCF using ParamSpace's existing math structure
- Define `ir.qc` keys with PySCF-like names: `scf.conv_tol`, `scf.max_cycle`, `dft.grid_level`
- Define ORCA engine-specific path: `engine.orca.scf.macro` (string, lower-case)
- Implement "specific supersedes general" dual-path materialization
- Enable `accepts_presets=True` for `pyscf_scf` and `orca_scf` step types

**What we are NOT touching:**
- Existing QE/PW `.true.`/`.false.` YAML roundtrip (keep v0 PW chain stable)
- ParamSpace core semantics (compile order, oracle, reversibility)
- Gen/public step names or spec/machine step mapping
- StepType Enum (leave as legacy compat-only; not fixing the 2 api.py violations in this milestone)
- Persisted state boundaries (SSOT remains `calculation.yaml` + `step.yaml`)

---

## 1. Discrepancy Log

| # | Item | Spec Says | Code Reality | File/Location | Impact |
|---|------|-----------|--------------|---------------|--------|
| D1 | IR bool type | IR uses Python `True/False`; `.true.` only in `.in` files | `ir_bool()` converts Python bool → `.true.`/`.false.` strings BEFORE writing to step.yaml | `src/quantumvitas/presets/paramspace.py:601-605`, `ir/backends/qe/mapping.py:14-41` | **Keep v0 as-is for PW.** QC dialect SHOULD use Python bool for new keys (no legacy compat burden). |
| D2 | `supported_presets` per engine | Spec requires `supported_presets: [...]` engine declaration | Current code uses `accepts_presets` (bool) + `allowed_dimensions` (frozenset) per step type, not per engine | `src/quantumvitas/workflow/registry.py:StepTypeSpec` (lines 35-51) | **Tolerable for v0.** Step-level control is sufficient. Engine-level gating can be deferred. |
| D3 | StepType Enum violations | Enum MUST NOT be used for core logic | Still used in 2 validation paths: `api.py:7757`, `api.py:7867` | `src/quantumvitas/api.py` | **Out of scope.** Fix deferred; does not affect ORCA/PySCF preset work. |
| D4 | Dialect namespace structure | Spec says `ir.pw` / `ir.qc` | Current code uses flat namespace; no dialect concept in IR layer | `src/quantumvitas/ir/` | **Will implement.** Introduce dialect as directory structure + docstrings; no runtime registry yet. |

---

## 2. Implementation Plan (PR-by-PR)

### PR0: Docs-only — Clarify Discrepancy D1 (bool representation)

**Title**: `Docs: clarify PW vs QC bool representation in IR dialect contract`

**Scope**: `docs/dev/spec-preset-paramspace-ir-engine-contract.md`

**Tasks**:
- [x] Add explicit note in section 3.3 that `ir.pw` dialect uses `.true.`/`.false.` strings for backward compatibility (v0 freeze)
- [x] Add explicit note that `ir.qc` dialect uses Python native `True/False` (fresh start, no legacy)
- [x] Clarify this is a transitional state; future migration may unify to Python bool

**Do NOT do**:
- Do not change code
- Do not promise future migration timeline

**Tests**: None (docs only)

**Verification**: `git diff docs/dev/spec-preset-paramspace-ir-engine-contract.md`

**Expected outcome**: Spec aligned with current QE/PW behavior; QC path clearly documented.

**Status**: ✅ COMPLETE

---

### PR1: IR Dialect Directory Structure (Scaffolding)

**Title**: `IR: introduce dialect directory structure (ir.pw, ir.qc)`

**Scope**: `src/quantumvitas/ir/`

**Tasks**:
- [ ] Create directory structure:
  - `src/quantumvitas/ir/dialects/__init__.py`
  - `src/quantumvitas/ir/dialects/pw/__init__.py` (docstring only; re-export from `backends/qe`)
  - `src/quantumvitas/ir/dialects/qc/__init__.py` (new, empty initially)
- [ ] Add docstrings explaining dialect paradigm (PW = PBC + plane-wave; QC = mol + AO)
- [ ] Create `src/quantumvitas/ir/dialects/qc/parameters.py` with `QC_IR_PARAMETERS` dict (empty initially)
- [ ] Update `src/quantumvitas/ir/__init__.py` to expose dialects

**Do NOT do**:
- Do not touch `ir/backends/qe/mapping.py`
- Do not change any existing QE/PW code paths
- Do not rename anything

**Tests**:
- [ ] `tests/unit/test_ir_dialect_structure.py` (new) — verify imports work, dialect modules exist

**Verification**:
```bash
pytest tests/unit/test_ir_dialect_structure.py -v
python -c "from quantumvitas.ir.dialects import pw, qc; print('OK')"
```

**Expected outcome**: Dialect directory structure exists; imports work; QE/PW unchanged.

---

### PR2: QC Precision ParamSpace Definition

**Title**: `Presets: define QC precision ParamSpace with ir.qc keys`

**Scope**: 
- `src/quantumvitas/ir/dialects/qc/parameters.py`
- `src/quantumvitas/presets/qc_precision.py` (new)
- `src/quantumvitas/presets/spaces_registry.py`
- `src/quantumvitas/presets/dimensions.py`

**Tasks**:
- [ ] Define `ir.qc` keys in `QC_IR_PARAMETERS`:
  - `scf.conv_tol` (float): SCF convergence tolerance
  - `scf.max_cycle` (int): Maximum SCF iterations
  - `dft.grid_level` (int, optional): DFT grid level
- [ ] Create `src/quantumvitas/presets/qc_precision.py` with:
  - `QC_PRECISION_PARAMSPACE` defining profiles `LOW`, `MED`, `HIGH`
  - Profile values (PySCF-compatible defaults)
  - Key ownership registered
- [ ] Add `DIMENSION_QC_PRECISION = "qc_precision"` to dimensions.py
- [ ] Add engine-specific cell placeholder: `engine.orca.scf.macro` (string key)
- [ ] Register in `spaces_registry.py`

**Do NOT do**:
- Do not touch PW precision ParamSpace
- Do not modify existing occupations_scheme/magnetism
- Do not call `ir_bool()` for QC keys (use Python native types)

**Tests**:
- [ ] `tests/unit/test_qc_precision_paramspace.py` (new):
  - Test profile definitions exist
  - Test key ownership is registered
  - Test compile_profile_patch produces expected keys
  - Test match_profile returns correct profile

**Verification**:
```bash
pytest tests/unit/test_qc_precision_paramspace.py -v
```

**Expected outcome**: QC precision ParamSpace defined; roundtrip tests pass; PW tests unchanged.

---

### PR3: Dual-Path Materialization (Specific Supersedes General)

**Title**: `Presets: implement specific-supersedes-general materialization for QC`

**Scope**:
- `src/quantumvitas/presets/variants_registry.py`
- `src/quantumvitas/presets/integration.py`
- `src/quantumvitas/ir/dialects/qc/mapping.py` (new)

**Tasks**:
- [ ] Create `ir/dialects/qc/mapping.py` with:
  - `QC_IR_TO_PYSCF_MAPPING`: dict mapping `ir.qc` keys → PySCF params
  - `QC_IR_TO_ORCA_MAPPING`: dict mapping `ir.qc` keys → ORCA params
- [ ] Add `QcPrecisionVariant` to variants_registry for step types: `{"scf"}` (gen step)
- [ ] Modify `compile_dimension_patch_for_step()` to:
  - Check if engine-specific patch exists (`engine.<engine>.*`)
  - If exists: return ONLY engine-specific patch (suppress general IR patch)
  - If multiple engine-specific patches: raise `PresetCompilationError` (hard error)
- [ ] Add logic in integration.py to detect engine from step_type and route accordingly

**Do NOT do**:
- Do not change PW dimension compilation
- Do not change compile ordering (prerequisite/dependent)
- Do not modify oracle behavior

**Tests**:
- [ ] `tests/unit/test_dual_path_materialization.py` (new):
  - Test general IR patch used when no engine-specific
  - Test engine-specific patch used when present
  - Test hard error when multiple engine-specific patches

**Verification**:
```bash
pytest tests/unit/test_dual_path_materialization.py -v
pytest tests/unit/test_paramspace_contract.py -v  # Ensure PW unchanged
```

**Expected outcome**: Dual-path works; PW presets unchanged; hard error on ambiguity.

---

### PR4: Enable QC Presets for ORCA/PySCF Step Types

**Title**: `Workflow: enable accepts_presets for orca_scf/pyscf_scf step types`

**Scope**:
- `src/quantumvitas/workflow/registry.py`

**Tasks**:
- [ ] Set `accepts_presets=True` for:
  - `pyscf_scf` step type
  - `orca_scf` step type
- [ ] Set `allowed_dimensions=frozenset({"qc_precision"})` for these step types
- [ ] Add public_type mapping for preset targeting (gen step `"scf"`)

**Do NOT do**:
- Do not enable presets for post-processing steps (TD, MP2)
- Do not change PW step types

**Tests**:
- [ ] `tests/unit/test_qc_step_preset_acceptance.py` (new):
  - Test `orca_scf` accepts `qc_precision` dimension
  - Test `pyscf_scf` accepts `qc_precision` dimension
  - Test other QC steps (TD, MP2) do NOT accept presets

**Verification**:
```bash
pytest tests/unit/test_qc_step_preset_acceptance.py -v
pytest tests/unit/test_paramspace_contract.py -v
```

**Expected outcome**: ORCA/PySCF SCF steps accept presets; other steps unchanged.

---

### PR5: Engine-Specific Macro Materialization (ORCA)

**Title**: `ORCA: materialize engine.orca.scf.macro to input file`

**Scope**:
- `src/quantumvitas/engines/orca/input_compiler.py`
- `src/quantumvitas/engine/orca_engine.py`

**Tasks**:
- [ ] Read `engine.orca.scf.macro` from step spec if present
- [ ] Map macro values to ORCA keywords:
  - `"tightscf"` → `! TightSCF`
  - `"normal"` → (default, no extra keyword)
  - `"loose"` → `! LooseSCF`
- [ ] Insert into ORCA input file generation
- [ ] Validate macro value is canonical lower-case

**Do NOT do**:
- Do not change PySCF input generation (PySCF uses IR keys directly)
- Do not add new macro types without spec approval

**Tests**:
- [ ] `tests/unit/test_orca_macro_materialization.py` (new):
  - Test `"tightscf"` produces `! TightSCF` in input
  - Test `"normal"` produces no extra keyword
  - Test invalid macro raises error

**Verification**:
```bash
pytest tests/unit/test_orca_macro_materialization.py -v
pytest tests/engines/orca/ -v  # Existing ORCA tests still pass
```

**Expected outcome**: ORCA macro materialization works; existing ORCA tests pass.

---

## 3. Risk Register

| # | Risk | Trigger | Detection | Mitigation |
|---|------|---------|-----------|------------|
| R1 | **SSOT break** | Preset/IR state accidentally persisted | Test assertion that step.yaml contains only engine params, not preset names | Add explicit test checking step.yaml schema |
| R2 | **PW reversibility break** | Change to ParamSpace core affects match/compile idempotency | `test_paramspace_contract.py` fails | Run full test suite after each PR; keep PW code frozen |
| R3 | **Dialect confusion** | Developer mixes `ir.pw` and `ir.qc` keys in same ParamSpace | Key ownership violation at runtime; tests fail | Add docstring warnings; key ownership registry catches |
| R4 | **StepType Enum usage creep** | New code uses Enum for routing/validation | Code review; grep for `StepType.` | Document enum as legacy-only; prefer registry lookup |
| R5 | **Bool type mismatch** | QC code accidentally calls `ir_bool()` | Type error or string in QC step.yaml where bool expected | Add test asserting QC step.yaml contains Python bool |
| R6 | **Compile ordering regression** | QC dimension added to wrong phase | Wrong oracle state during compile | Keep QC dimension in dependent phase; test ordering |
| R7 | **Dual-path hard error false positive** | Multiple engine patches exist by accident | User sees cryptic error on apply | Clear error message; test with intentional violation |
| R8 | **ORCA macro typo** | Invalid macro string slips through | ORCA fails at runtime | Validate macro against known list; test with invalid input |

---

## 4. Open Questions

| # | Question | Recommendation | Rationale |
|---|----------|----------------|-----------|
| Q1 | Should QC precision profiles (LOW/MED/HIGH) have same names as PW? | **Yes, same names.** | User mental model stays consistent; differentiation is by dimension name (`precision` vs `qc_precision`). |
| Q2 | Should `engine.orca.scf.macro` be required or optional for ORCA SCF? | **Optional.** Default to engine default (TightSCF). | Allows minimal presets; advanced users can override. |
| Q3 | Should we enable presets for `pyscf_mp2` / `orca_td` now? | **No.** Only `scf` gen step for v0. | Keep scope minimal; expand in next milestone. |
| Q4 | Should we add `qc_precision` to existing PW step types? | **No.** Dialects are disjoint. | PW steps use `precision`; QC steps use `qc_precision`. |
| Q5 | How should we handle the `.true.` migration for PW? | **Defer to separate milestone.** | High risk; needs careful roundtrip testing. Out of scope. |
| Q6 | Should `supported_presets` per engine be added now? | **Defer.** Step-level `allowed_dimensions` is sufficient. | Reduces scope; engine-level gating is nice-to-have. |

---

## 5. Ready-to-Execute Prompts for AUTO (Implementation Worker)

### AUTO Prompt: PR0

```
You are implementing PR0 (docs only).

TARGET FILE: docs/dev/spec-preset-paramspace-ir-engine-contract.md

TASK: Update section 3.3 (IR Dialects) to clarify:
1. `ir.pw` dialect uses `.true.`/`.false.` strings for backward compatibility (v0 freeze)
2. `ir.qc` dialect uses Python native `True/False` (fresh start, no legacy burden)
3. Add a note: "This is a transitional state; `ir.pw` may migrate to Python bool in a future milestone."

DO NOT:
- Change any code
- Modify other sections unless necessary for consistency

TESTS: None (docs only)

VERIFICATION: git diff docs/dev/spec-preset-paramspace-ir-engine-contract.md

STOP IF: Any confusion about spec intent; write log and stop.
```

**Status**: ✅ COMPLETE

---

### AUTO Prompt: PR1

```
You are implementing PR1 (IR dialect directory structure).

TARGET FILES:
- src/quantumvitas/ir/dialects/__init__.py (new)
- src/quantumvitas/ir/dialects/pw/__init__.py (new)
- src/quantumvitas/ir/dialects/qc/__init__.py (new)
- src/quantumvitas/ir/dialects/qc/parameters.py (new)
- src/quantumvitas/ir/__init__.py (update)

TASK:
1. Create directories: ir/dialects/, ir/dialects/pw/, ir/dialects/qc/
2. Add __init__.py files with docstrings explaining dialect paradigm
3. pw/__init__.py should re-export from backends/qe (comment: "v0 alias")
4. qc/parameters.py should define empty QC_IR_PARAMETERS dict
5. Update ir/__init__.py to expose dialects

PRESERVE:
- All existing ir/backends/qe/* code unchanged
- All existing ir/parameters.py unchanged

TESTS: Create tests/unit/test_ir_dialect_structure.py with import tests

VERIFICATION:
pytest tests/unit/test_ir_dialect_structure.py -v
python -c "from quantumvitas.ir.dialects import pw, qc; print('OK')"

STOP IF: Any import error or test failure; log and stop.
```

---

### AUTO Prompt: PR2

```
You are implementing PR2 (QC precision ParamSpace).

TARGET FILES:
- src/quantumvitas/ir/dialects/qc/parameters.py (update)
- src/quantumvitas/presets/qc_precision.py (new)
- src/quantumvitas/presets/spaces_registry.py (update)
- src/quantumvitas/presets/dimensions.py (update)

TASK:
1. Define QC_IR_PARAMETERS with keys: scf.conv_tol, scf.max_cycle, dft.grid_level
2. Create qc_precision.py with QC_PRECISION_PARAMSPACE:
   - Profiles: LOW, MED, HIGH
   - Use ParamSpace class from paramspace.py
   - Use Python native types (NOT ir_bool())
   - Add engine.orca.scf.macro as engine-specific key
3. Add DIMENSION_QC_PRECISION = "qc_precision" to dimensions.py
4. Register in spaces_registry.py

PRESERVE:
- All PW precision code unchanged
- All existing ParamSpace registrations unchanged

TESTS: Create tests/unit/test_qc_precision_paramspace.py with roundtrip tests

VERIFICATION:
pytest tests/unit/test_qc_precision_paramspace.py -v
pytest tests/unit/test_paramspace_contract.py -v

STOP IF: Any PW test regression; log and stop.
```

---

### AUTO Prompt: PR3

```
You are implementing PR3 (dual-path materialization).

TARGET FILES:
- src/quantumvitas/ir/dialects/qc/mapping.py (new)
- src/quantumvitas/presets/variants_registry.py (update)
- src/quantumvitas/presets/integration.py (update)

TASK:
1. Create qc/mapping.py with QC_IR_TO_PYSCF_MAPPING and QC_IR_TO_ORCA_MAPPING
2. Add QcPrecisionVariant to variants_registry for gen step "scf"
3. Modify compile_dimension_patch_for_step() to:
   - Check for engine-specific patch (engine.<engine>.*)
   - If present: return ONLY engine-specific patch
   - If multiple engine-specific patches: raise PresetCompilationError

PRESERVE:
- All PW dimension compilation unchanged
- Compile ordering (prerequisite/dependent) unchanged
- Oracle behavior unchanged

TESTS: Create tests/unit/test_dual_path_materialization.py

VERIFICATION:
pytest tests/unit/test_dual_path_materialization.py -v
pytest tests/unit/test_paramspace_contract.py -v

STOP IF: Any PW test regression or compile ordering change; log and stop.
```

---

### AUTO Prompt: PR4

```
You are implementing PR4 (enable QC presets for step types).

TARGET FILE: src/quantumvitas/workflow/registry.py

TASK:
1. Find StepTypeSpec for "pyscf_scf" (line ~440)
2. Change accepts_presets=False to accepts_presets=True
3. Change allowed_dimensions=frozenset() to allowed_dimensions=frozenset({"qc_precision"})
4. Repeat for "orca_scf" (line ~495)

PRESERVE:
- All PW step types unchanged
- All other QC step types (pyscf_mp2, orca_td, etc.) unchanged

TESTS: Create tests/unit/test_qc_step_preset_acceptance.py

VERIFICATION:
pytest tests/unit/test_qc_step_preset_acceptance.py -v
pytest tests/unit/test_paramspace_contract.py -v

STOP IF: Any PW step type changed; log and stop.
```

---

### AUTO Prompt: PR5

```
You are implementing PR5 (ORCA macro materialization).

TARGET FILES:
- src/quantumvitas/engines/orca/input_compiler.py (update)
- src/quantumvitas/engine/orca_engine.py (update if needed)

TASK:
1. Read engine.orca.scf.macro from step spec in ORCA input compilation
2. Map values to ORCA keywords:
   - "tightscf" → "! TightSCF"
   - "normal" → (no extra keyword)
   - "loose" → "! LooseSCF"
3. Insert keyword into ORCA input file generation
4. Validate macro is lower-case

PRESERVE:
- All existing ORCA input generation logic
- All PySCF code unchanged

TESTS: Create tests/unit/test_orca_macro_materialization.py

VERIFICATION:
pytest tests/unit/test_orca_macro_materialization.py -v
pytest tests/engines/orca/ -v

STOP IF: Existing ORCA tests fail; log and stop.
```

---

## Appendix: Verification Commands Summary

### After Each PR

```bash
# Run new tests
pytest tests/unit/test_<new_test_file>.py -v

# Ensure PW tests still pass
pytest tests/unit/test_paramspace_contract.py -v
pytest tests/unit/test_preset_integration.py -v

# Check for regressions
pytest tests/presets/ -v
```

### Final Verification (After All PRs)

```bash
# Full preset test suite
pytest tests/unit/test_paramspace*.py -v
pytest tests/presets/ -v

# QC-specific tests
pytest tests/unit/test_qc_*.py -v

# ORCA/PySCF engine tests
pytest tests/engines/orca/ -v
pytest tests/engines/pyscf/ -v
```

---

**End of Implementation Plan**

