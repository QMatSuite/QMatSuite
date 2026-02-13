# IR, Step, and Engine Generalization v0 Implementation Plan

**Version**: 0.1  
**Status**: Implementation Plan (Ready to Start)  
**Date**: 2025-01-XX  
**Purpose**: Detailed, checkbox-driven implementation plan for v0 IR/Step/Engine generalization

**Final Clarifications**:
- ✅ IR landing MUST be fully implemented in v0 (not scaffolding)
- ✅ Step generalization: Conceptual only (enums/mappings/docs; NO execution changes)
- ✅ Engine generalization: QE adapter MUST be implemented; NO central registry; NO engine_id in step.yaml
- ✅ QE/Wannier execution paths MUST NOT break (no refactoring)
- ✅ System must be usable exactly as before from user perspective

---

## Context & Invariants

### Non-Negotiable Principles (from Charter)

1. **step.yaml is the ONLY on-disk SSOT** ("machine code") for execution
   - Execution consumes step.yaml only
   - Preset/IR must NOT be written into step.yaml
   - Any provenance about preset/IR belongs to history/journal only (not step files)

2. **ParamSpace logic MUST NOT change**
   - Only allowed change: replace dimension-2 keys from QE-parameter keys to IR-parameter keys (via explicit mapping table)
   - Do NOT rewrite matching/compilation logic, cell semantics, or applicability semantics
   - Must NOT assume ir_key == qe_key even if v0 chooses identical names

3. **v0 IR is QE-equivalent rename/indirection ONLY**
   - IR is internal-only in v0; do not migrate user-facing parameter editing or API/Jupyter to IR
   - IR keys in v0 should mostly reuse QE names (ecutwfc, nspin, conv_thr, etc.)
   - IR base units: Energy=Ry, Length=Bohr (no conversion in v0)

4. **Separation of concerns**
   - IR definitions must NOT include qe_key (belongs to IR↔QE adapter)
   - Execution policy flags are NOT IR (restart_mode, tstress, tprnfor, outdir, prefix, etc.)

5. **Step / Engine generalization must be planned in parallel**
   - v0 may implement only "foundational scaffolding" if that's what the repo supports now

---

## Repo Reality Check

### Files Inspected (Presets & ParamSpace)

**ParamSpace Core**:
- `src/quantumvitas/presets/paramspace.py`: `ParamSpace`, `ParamKey`, `Cell`, `match_profile()`, `compile_profile_patch()`
  - **Key Finding**: `ParamKey.key` is currently QE parameter name (e.g., "nspin", "ecutwfc")
  - **Key Finding**: `match_profile()` uses `key.section` and `key.key` to read from YAML
  - **Key Finding**: `compile_profile_patch()` uses `key.section` and `key.key` to write to YAML

**Preset Dimensions**:
- `src/quantumvitas/presets/paramspace.py:545-634`: `build_magnetism_paramspace()` - defines `nspin`, `noncolin`, `lspinorb` keys
- `src/quantumvitas/presets/paramspace.py:460-526`: `build_occupations_scheme_paramspace()` - defines `occupations`, `smearing`, `degauss` keys
- `src/quantumvitas/presets/paramspace.py:652-727`: `build_precision_paramspace()` - defines `ecutwfc`, `ecutrho`, `conv_thr`, `K_POINTS` keys
- `src/quantumvitas/presets/paramspace.py:829-936`: `build_convergence_paramspace()` - defines `mixing_beta`, `electron_maxstep`, `mixing_mode`, `mixing_ndim`, `diagonalization` keys

**Preset Registry**:
- `src/quantumvitas/presets/spaces_registry.py`: `detect_dimension()`, `compile_dimension_patch()` - public APIs
- `src/quantumvitas/presets/variants_registry.py`: `get_variant()`, `compile_dimension_patch_for_step()` - step-type-aware variants

**Compiler/Detector**:
- `src/quantumvitas/presets/compiler.py`: `compile_magnetism()`, `compile_occupations_scheme()`, `compile_presets()` - high-level compilation
- `src/quantumvitas/presets/detector.py`: `detect_magnetism()`, `detect_occupations_scheme()`, `detect_all_presets()` - high-level detection

**Integration Layer**:
- `src/quantumvitas/presets/integration.py:327-550`: `apply_presets_to_step()` - mutates step.yaml via StepDoc
  - **Key Finding**: Uses `StepDoc` to load/mutate step.yaml, then saves via `save_yaml_doc()`
  - **Key Finding**: Compilation produces QE parameters which are written to `step.yaml["parameters"]`

### Files Inspected (Step YAML Mutation)

**Step Structure**:
- `src/quantumvitas/calculation/structure_steps.py:34-54`: `StructureStepSpec` - has `parameters: Dict[str, Dict[str, Any]]` field (engine-specific)
  - **Key Finding**: No `engine_id` field currently exists
  - **Key Finding**: `parameters` field contains QE namelist parameters (e.g., `{"SYSTEM": {"nspin": 2}}`)

**StepDoc Abstraction**:
- `src/quantumvitas/core/yamldoc.py:75-655`: `YamlDoc`, `StepDoc` - mutation containment
  - **Key Finding**: `StepDoc` provides `get()`, `set()`, `apply_patch()`, `export_copy()` methods
  - **Key Finding**: All mutations go through StepDoc; no direct dict mutation

**YAML I/O & Journal**:
- `src/quantumvitas/core/yaml_io.py:117-124`: `save_yaml_doc()` - save hook with journal integration
  - **Key Finding**: Journal hook records before/after snapshots automatically
  - **Key Finding**: Journal entries stored in `~/.quantumvitas/journal/journal.jsonl`

### Files Inspected (QE Input Generation)

**Input Generator**:
- `src/quantumvitas/io/generator/qe_generator.py`: `QEInputGenerator` - generates `*.in` files from step.yaml
  - **Key Finding**: Reads `step.yaml["parameters"]` to generate QE namelists and cards
  - **Key Finding**: `step.yaml` → `*.in` is the authoritative path for execution

### Files Inspected (Execution & Runner)

**QE Engine**:
- `src/quantumvitas/core/engines/qe.py:22-618`: `QuantumEspressoEngine` - QE-specific engine
  - **Key Finding**: `EXECUTABLE_MAP` maps step types to QE executables (e.g., `"scf": "pw.x"`)
  - **Key Finding**: No `engine_id` field in step.yaml currently

**PySCF Runner**:
- `src/quantumvitas/engines/pyscf/runner.py:1-359`: PySCF subprocess runner
  - **Key Finding**: Reads `job.json`, writes `results.json` (file-based, restartable)
  - **Key Finding**: No long-lived worker yet; invoked per step

**Step Completion**:
- `src/quantumvitas/calculation/step_done.py:86-141`: `is_step_done()` - determines if step is complete
  - **Key Finding**: QE steps: checks for "JOB DONE" in primary `.out` file
  - **Key Finding**: Wannier90 steps: checks for `.wout` file existence

### Files Inspected (Workflow & Step Types)

**Step Types**:
- `src/quantumvitas/calculation/types.py:10-30`: `StepType` enum - defines step types
  - **Key Finding**: Step types: SCF, NSCF, DOS, BANDS_PW, BANDS, PH, Q2R, MATDYN, DYNMAT, PP, PROJWFC, RELAX, VC_RELAX, W90_PREPROC, PW2WANNIER90, W90_RUN, PYSCF_SCF, CUSTOM

**Workflow Templates**:
- `src/quantumvitas/workflow/templates.py:76-113`: `WorkflowTemplate` - defines workflow sequences
  - **Key Finding**: Workflow templates group step types (e.g., DOS = SCF → NSCF → DOS)

---

## Phase 1: Parameter IR Landing (QE-Only Behavioral Preservation)

**Status**: ✅ FULL IMPLEMENTATION REQUIRED (not scaffolding)

**Architecture**: Parameter pipeline flow
- Preset (physical intent) → IR parameters (physical quantities, engine-agnostic) → Engine-specific parameters (step.yaml, SSOT)
- ParamSpace operates ONLY on IR keys
- IR→QE translation happens in QE engine adapter/compiler layer, NOT inside ParamSpace

**Deliverables**: 
- IR parameter registry (fully implemented)
- ParamSpace dimension-2 migration to IR keys (fully implemented)
- Explicit IR↔QE adapter layer (fully implemented)
- All existing behavior preserved
- Tests added and passing

### A1) IR Parameter Inventory (v0)

**Task**: Enumerate all IR parameters required by existing presets

- [ ] **A1.1**: Inspect `src/quantumvitas/presets/paramspace.py:545-634` (magnetism ParamSpace)
  - **Why**: Need to identify all QE keys used in magnetism dimension
  - **Expected IR Keys**: `nspin`, `noncolin`, `lspinorb` (QE-equivalent)
  - **Tests Impacted**: None (documentation only)

- [ ] **A1.2**: Inspect `src/quantumvitas/presets/paramspace.py:460-526` (occupations_scheme ParamSpace)
  - **Why**: Need to identify all QE keys used in occupations_scheme dimension
  - **Expected IR Keys**: `occupations`, `smearing`, `degauss` (QE-equivalent)
  - **Tests Impacted**: None (documentation only)

- [ ] **A1.3**: Inspect `src/quantumvitas/presets/paramspace.py:652-727` (precision ParamSpace)
  - **Why**: Need to identify all QE keys used in precision dimension
  - **Expected IR Keys**: `ecutwfc`, `ecutrho`, `conv_thr`, `K_POINTS` (QE-equivalent; K_POINTS is a card)
  - **Note**: Confirm `K_POINTS` is treated as a card in `key.section == "cards"`
  - **Tests Impacted**: None (documentation only)

- [ ] **A1.4**: Inspect `src/quantumvitas/presets/paramspace.py:829-936` (convergence ParamSpace)
  - **Why**: Need to identify all QE keys used in convergence dimension
  - **Expected IR Keys**: `mixing_beta`, `electron_maxstep`, `mixing_mode`, `mixing_ndim`, `diagonalization` (QE-equivalent)
  - **Tests Impacted**: None (documentation only)

- [ ] **A1.5**: Document low-hanging additions
  - **IR Keys**: `nbnd`, `nosym`, `noinv` (QE-equivalent)
  - **Rationale**: Commonly user-edited physical knobs not currently in presets
  - **Tests Impacted**: None (documentation only)

**Deliverable**: Complete list of 18 IR parameters (15 from presets + 3 low-hanging)

---

### A2) IR Registry

**Task**: Create minimal IR parameter registry (IR definitions only; no QE references)

- [ ] **A2.1**: Create `src/quantumvitas/ir/parameters.py`
  - **Why**: Central registry for IR parameter definitions (engine-agnostic)
  - **Exact Edit**: New file with IR parameter dataclass and registry
  - **Structure**:
    ```python
    @dataclass(frozen=True)
    class IRParameter:
        ir_key: str  # e.g., "ecutwfc", "nspin", "conv_thr"
        physical_meaning: str
        dimension: str  # "Energy", "Length", "Dimensionless", "Bool", "Enum", "Integer", "Struct"
        ir_base_unit: Optional[str]  # "Ry", "Bohr", None
        type: str  # "float", "int", "bool", "str", "dict"
        comment: str
        # MUST NOT include qe_key or qe_section (belongs to adapter)
    
    IR_REGISTRY: Dict[str, IRParameter] = {
        "ecutwfc": IRParameter(...),
        "nspin": IRParameter(...),
        # ... 16 more
    }
    ```
  - **Tests Impacted**: New unit tests for IR registry

- [ ] **A2.2**: Populate IR registry with 18 parameters
  - **Why**: Complete IR parameter definitions for v0
  - **Exact Edit**: Add all 18 `IRParameter` instances to `IR_REGISTRY`
  - **Source**: QE metadata from `src/quantumvitas/data/qe_module_parameters.json`
  - **Note**: Physical meaning and comments can be copied from QE metadata but are IR-owned
  - **Tests Impacted**: Registry validation tests

- [ ] **A2.3**: Add IR registry validation function
  - **Why**: Ensure all IR parameters have valid definitions
  - **Exact Edit**: `validate_ir_registry()` function
  - **Tests Impacted**: Registry validation tests

**Deliverable**: `src/quantumvitas/ir/parameters.py` with 18 IR parameter definitions

---

### A3) IR↔QE Adapter (Explicit Mapping Table)

**Task**: Create mechanical mapping layer between IR and QE parameter names

**Architecture Constraint**: IR→QE mapping MUST live in a QE-specific adapter/compiler layer, NOT inside ParamSpace. ParamSpace operates ONLY on IR keys and does NOT perform engine translation.

- [ ] **A3.1**: Create IR↔QE adapter module
  - **Why**: Explicit mapping table for IR ↔ QE conversion (engine-specific, separate from ParamSpace)
  - **Location Options**:
    - Option A: `src/quantumvitas/ir/backends/qe/mapping.py` (IR module, QE backend)
    - Option B: `src/quantumvitas/core/engines/qe/adapter.py` (QE engine module, IR adapter)
  - **Decision**: Choose location based on whether this is IR's QE backend or QE's IR adapter
  - **Exact Edit**: New file with mapping dictionaries
  - **Structure**:
    ```python
    # IR → QE Mapping (for compilation)
    IR_TO_QE_MAPPING: Dict[str, Tuple[str, str, str]] = {
        "ecutwfc": ("pw", "SYSTEM", "ecutwfc"),
        "nspin": ("pw", "SYSTEM", "nspin"),
        # ... all 18 IR keys
    }
    
    # QE → IR Mapping (for detection)
    QE_TO_IR_MAPPING: Dict[Tuple[str, str, str], str] = {
        ("pw", "SYSTEM", "ecutwfc"): "ecutwfc",
        ("pw", "SYSTEM", "nspin"): "nspin",
        # ... reverse mapping
    }
    
    # Unit mapping (v0: identity, but explicit boundary)
    IR_UNIT_TO_QE_UNIT: Dict[str, str] = {
        "Ry": "Ry",  # Energy: IR=Ry, QE=Ry (no conversion)
        "Bohr": "Bohr",  # Length: IR=Bohr, QE=Bohr (no conversion)
    }
    ```
  - **Tests Impacted**: New unit tests for mapping functions

- [ ] **A3.2**: Add IR→QE conversion function
  - **Why**: Convert IR key/value to QE section/key/value for compilation
  - **Exact Edit**: `ir_to_qe_param(ir_key: str, ir_value: Any) -> Tuple[str, str, Any]`
  - **Tests Impacted**: Mapping function tests

- [ ] **A3.3**: Add QE→IR conversion function
  - **Why**: Convert QE section/key/value to IR key/value for detection
  - **Exact Edit**: `qe_to_ir_param(qe_module: str, qe_section: str, qe_key: str, qe_value: Any) -> Tuple[str, Any]`
  - **Tests Impacted**: Mapping function tests

- [ ] **A3.4**: Handle K_POINTS card mapping
  - **Why**: K_POINTS is a card (not namelist), needs special handling
  - **Exact Edit**: Special case in mapping functions for `ir_key == "K_POINTS"` and `qe_section == "cards"`
  - **Note**: Confirm v0 canonicalization: 4 modes (gamma/automatic/crystal/crystal_b)
  - **Tests Impacted**: Card mapping tests

- [ ] **A3.5**: Add mapping validation function
  - **Why**: Ensure IR↔QE mapping is complete and reversible
  - **Exact Edit**: `validate_ir_qe_mapping()` function
  - **Tests Impacted**: Mapping validation tests

**Deliverable**: `src/quantumvitas/ir/backends/qe/mapping.py` with explicit mapping table and conversion functions

---

### A4) ParamSpace Migration (Dimension-2 QE → IR)

**Task**: Replace QE parameter keys with IR keys in ParamSpace (surgical change only)

- [ ] **A4.1**: Inspect all ParamSpace builders
  - **Why**: Identify every `ParamKey` instance that needs IR key substitution
  - **Files**: `src/quantumvitas/presets/paramspace.py:545-936`
  - **Tests Impacted**: None (documentation only)

- [ ] **A4.2**: Update `ParamKey` usage in `build_magnetism_paramspace()`
  - **Why**: Replace QE keys with IR keys
  - **Exact Edit**: Change `ParamKey(key="nspin", ...)` to `ParamKey(key="nspin", ...)` (no change in v0, but use IR registry)
  - **Note**: In v0, ir_key == qe_key for most params, but still use IR registry for consistency
  - **Location**: `src/quantumvitas/presets/paramspace.py:565-589`
  - **Tests Impacted**: ParamSpace reversibility tests

- [ ] **A4.3**: Update `ParamKey` usage in `build_occupations_scheme_paramspace()`
  - **Why**: Replace QE keys with IR keys
  - **Exact Edit**: Change `ParamKey(key="occupations", ...)` to use IR registry
  - **Location**: `src/quantumvitas/presets/paramspace.py:460-526`
  - **Tests Impacted**: ParamSpace reversibility tests

- [ ] **A4.4**: Update `ParamKey` usage in `build_precision_paramspace()`
  - **Why**: Replace QE keys with IR keys
  - **Exact Edit**: Change `ParamKey(key="ecutwfc", ...)` to use IR registry
  - **Note**: Handle `K_POINTS` card mapping (section="cards", key="K_POINTS")
  - **Location**: `src/quantumvitas/presets/paramspace.py:652-727`
  - **Tests Impacted**: ParamSpace reversibility tests

- [ ] **A4.5**: Update `ParamKey` usage in `build_convergence_paramspace()`
  - **Why**: Replace QE keys with IR keys
  - **Exact Edit**: Change `ParamKey(key="mixing_beta", ...)` to use IR registry
  - **Location**: `src/quantumvitas/presets/paramspace.py:829-936`
  - **Tests Impacted**: ParamSpace reversibility tests

- [ ] **A4.6**: Update `match_profile()` to work with IR keys (read YAML via adapter)
  - **Why**: ParamSpace operates on IR keys only; need to read QE YAML and convert to IR for matching
  - **Architecture**: ParamSpace does NOT perform engine translation; adapter converts QE→IR before ParamSpace matching
  - **Exact Edit**: In `src/quantumvitas/presets/paramspace.py:238-306`, ParamSpace matches against IR keys
  - **Integration**: IR→QE adapter layer (outside ParamSpace) converts QE YAML to IR YAML before calling `match_profile()`
  - **Logic**:
    ```python
    # ParamSpace operates on IR keys only
    # Before calling match_profile(), adapter converts QE YAML → IR YAML
    # match_profile() receives IR YAML and matches against IR keys in ParamSpace
    ```
  - **Tests Impacted**: ParamSpace matching tests

- [ ] **A4.7**: Update `compile_profile_patch()` to work with IR keys (write YAML via adapter)
  - **Why**: ParamSpace operates on IR keys only; need to compile IR patch then convert to QE for YAML
  - **Architecture**: ParamSpace produces IR patch; adapter converts IR→QE before writing to YAML
  - **Exact Edit**: In `src/quantumvitas/presets/paramspace.py:313-374`, ParamSpace compiles IR patch
  - **Integration**: IR→QE adapter layer (outside ParamSpace) converts IR patch to QE patch before writing to step.yaml
  - **Logic**:
    ```python
    # ParamSpace produces IR patch (IR keys)
    # After compile_profile_patch(), adapter converts IR patch → QE patch
    # QE patch is written to step.yaml
    ```
  - **Tests Impacted**: ParamSpace compilation tests

**Deliverable**: ParamSpace uses IR keys internally; IR→QE translation happens in adapter layer (outside ParamSpace)

---

### A5) Preset Compiler + Detector Updates

**Task**: Update compiler/detector to route through IR→QE adapter (outside ParamSpace)

- [ ] **A5.1**: Update `compile_dimension_patch()` to use IR→QE adapter
  - **Why**: Compilation flow: ParamSpace (IR keys) → IR patch → IR→QE adapter → QE patch → step.yaml
  - **File**: `src/quantumvitas/presets/spaces_registry.py:compile_dimension_patch()`
  - **Exact Edit**: After ParamSpace produces IR patch, call IR→QE adapter to convert IR patch to QE patch
  - **Architecture**: ParamSpace does NOT perform engine translation; adapter layer (outside ParamSpace) does
  - **Tests Impacted**: Compilation integration tests

- [ ] **A5.2**: Update `detect_dimension()` to use QE→IR adapter
  - **Why**: Detection flow: step.yaml (QE params) → QE→IR adapter → IR params → ParamSpace matching → preset enum
  - **File**: `src/quantumvitas/presets/spaces_registry.py:detect_dimension()`
  - **Exact Edit**: Before ParamSpace matching, call QE→IR adapter to convert QE YAML to IR YAML
  - **Architecture**: ParamSpace operates on IR keys only; adapter layer (outside ParamSpace) converts QE→IR
  - **Tests Impacted**: Detection integration tests

- [ ] **A5.3**: Update `compile_magnetism()` if needed
  - **Why**: Ensure high-level compiler functions still work with IR keys
  - **File**: `src/quantumvitas/presets/compiler.py:39-64`
  - **Expected**: No changes needed (thin wrapper around registry)
  - **Tests Impacted**: Compiler function tests

- [ ] **A5.4**: Update `detect_magnetism()` if needed
  - **Why**: Ensure high-level detector functions still work with IR keys
  - **File**: `src/quantumvitas/presets/detector.py`
  - **Expected**: No changes needed (thin wrapper around registry)
  - **Tests Impacted**: Detector function tests

**Deliverable**: Compiler/detector work with IR keys transparently (via ParamSpace adapter layer)

---

### A6) Integration Layer Updates

**Task**: Ensure preset application mutates step.yaml correctly (still QE params)

- [ ] **A6.1**: Verify `apply_presets_to_step()` behavior
  - **Why**: Ensure preset application writes QE params to step.yaml (not IR params)
  - **File**: `src/quantumvitas/presets/integration.py:327-550`
  - **Expected**: No changes needed (compilation already produces QE params via adapter)
  - **Tests Impacted**: Integration tests for preset application

- [ ] **A6.2**: Verify StepDoc mutation flow
  - **Why**: Ensure StepDoc correctly mutates `step.yaml["parameters"]` with QE params
  - **File**: `src/quantumvitas/core/yamldoc.py:StepDoc`
  - **Expected**: No changes needed (StepDoc already handles QE parameter structure)
  - **Tests Impacted**: StepDoc mutation tests

- [ ] **A6.3**: Verify journal recording (if IR/preset provenance needed)
  - **Why**: Charter says IR/preset provenance belongs to journal/history only
  - **File**: `src/quantumvitas/core/journal.py:Journal`
  - **Note**: Journal already records before/after snapshots; IR/preset can be derived from journal if needed
  - **Tests Impacted**: Journal recording tests (if provenance recording is added)

- [ ] **A6.4**: Verify no IR/preset persistence in step.yaml
  - **Why**: Charter explicitly forbids IR/preset in step.yaml
  - **File**: `src/quantumvitas/presets/integration.py:apply_presets_to_step()`
  - **Expected**: Ensure `apply_presets_to_step()` never writes IR params to step.yaml
  - **Tests Impacted**: Integration tests to verify step.yaml never contains IR keys

**Deliverable**: Integration layer preserves SSOT rule (step.yaml contains QE params only)

---

### A7) Test Plan (Mandatory)

**Task**: Add/adjust tests to prove behavioral preservation

- [ ] **A7.1**: ParamSpace reversibility tests
  - **Why**: Prove ParamSpace logic unchanged (same semantics, only key-space renamed)
  - **Test**: `test_paramspace_reversibility_ir_keys()` in `tests/presets/test_paramspace_ir.py`
  - **Logic**: Match profile → compile patch → match profile again (should return same profile)
  - **Tests Impacted**: New test file

- [ ] **A7.2**: Preset compile/detect round-trip tests
  - **Why**: Prove preset → IR → QE → IR → preset round-trip works
  - **Test**: `test_preset_roundtrip_ir_keys()` in `tests/presets/test_preset_ir.py`
  - **Logic**: Compile preset → detect preset (should return same preset)
  - **Tests Impacted**: New test file

- [ ] **A7.3**: QE step.yaml SSOT enforcement tests
  - **Why**: Prove execution path never reads IR/preset
  - **Test**: `test_step_yaml_ssot_enforcement()` in `tests/presets/test_integration_ir.py`
  - **Logic**: Verify `step.yaml["parameters"]` contains QE params only; verify execution reads from `step.yaml["parameters"]` only
  - **Tests Impacted**: New test file

- [ ] **A7.4**: IR→QE adapter mapping tests
  - **Why**: Prove IR↔QE mapping is complete and reversible
  - **Test**: `test_ir_qe_mapping_completeness()` in `tests/ir/test_mapping.py`
  - **Logic**: Verify all IR keys have QE mappings; verify reverse mapping works
  - **Tests Impacted**: New test file

- [ ] **A7.5**: ParamSpace key substitution tests
  - **Why**: Prove ParamSpace uses IR keys internally but YAML I/O uses QE keys
  - **Test**: `test_paramspace_ir_key_internal_qe_key_external()` in `tests/presets/test_paramspace_ir.py`
  - **Logic**: Verify ParamSpace matches against IR keys, but reads/writes QE keys from/to YAML
  - **Tests Impacted**: New test file

- [ ] **A7.6**: Backward compatibility tests
  - **Why**: Prove existing step.yaml files continue to work (QE params only)
  - **Test**: `test_backward_compatibility_qe_params_only()` in `tests/presets/test_integration_ir.py`
  - **Logic**: Load old step.yaml with QE params; verify detection/compilation still works
  - **Tests Impacted**: New test file

**Deliverable**: Test suite proving behavioral preservation and SSOT enforcement

---

## Phase 2: Step Generalization (Conceptual Only in v0)

**Status**: ⚠️ CONCEPTUAL ONLY (enums/mappings/documentation; NO execution changes)

**Architecture**: Workflow pipeline flow (conceptual only in v0)
- Workflow (physical intent) → Generalized Steps (physical operations, engine-agnostic) → Engine-specific Steps (step.yaml, executable, SSOT)
- Only engine-specific steps are written to disk and executed

**v0 Constraints**:
- Generalized steps are conceptual ONLY (enums/mappings/documentation)
- Generalized steps are NOT written to disk
- Generalized steps do NOT have executables
- Existing step types remain UNCHANGED
- Execution logic stays EXACTLY the same
- step.yaml schema stays EXACTLY the same
- Runners stay EXACTLY the same
- NO new execution pipeline
- NO engine registries
- NO engine_id in step.yaml

**Allowed in v0**:
- Rename or annotate existing step types internally as engine-specific
- Add thin generalized-step abstraction that maps to existing step types (conceptual only)

### B1) Generalized Step vs Engine-Specific Step Separation

**Task**: Define minimal physical step taxonomy (conceptual only; no execution changes)

**Architecture**: TWO distinct step layers (conceptual only):
- **Generalized Step**: Physical operation (SCF, NSCF, Wannierization, etc.), engine-agnostic, conceptual only (not written to disk, no executables)
- **Engine-Specific Step**: Existing step types (qe_scf, qe_nscf, w90_run, pyscf_xxx, etc.), execution unchanged, written to step.yaml and executed

- [ ] **B1.1**: Inspect current step type definitions
  - **Why**: Understand existing step types and their groupings
  - **File**: `src/quantumvitas/calculation/types.py:StepType`
  - **Findings**: 17 step types (SCF, NSCF, DOS, BANDS_PW, BANDS, PH, Q2R, MATDYN, DYNMAT, PP, PROJWFC, RELAX, VC_RELAX, W90_PREPROC, PW2WANNIER90, W90_RUN, PYSCF_SCF)
  - **Tests Impacted**: None (documentation only)

- [ ] **B1.2**: Create minimal generalized step taxonomy (conceptual only - enums/mappings)
  - **Why**: Conceptual abstraction only; execution logic unchanged
  - **Exact Edit**: New file `src/quantumvitas/workflow/generalized_steps.py` (conceptual enum only)
  - **Structure**:
    ```python
    from enum import Enum
    
    class GeneralizedStep(str, Enum):
        """Generalized step types (conceptual only, not written to disk)."""
        SCF = "scf"
        RELAX = "relax"
        VC_RELAX = "vc_relax"
        NSCF = "nscf"
        BANDS = "bands"
        DOS = "dos"
        WANNIER = "wannier"
        # Future: PHONON, etc.
    
    # Mapping: Engine-specific StepType → GeneralizedStep (conceptual only)
    ENGINE_STEP_TO_GENERALIZED: Dict[StepType, GeneralizedStep] = {
        StepType.SCF: GeneralizedStep.SCF,
        StepType.RELAX: GeneralizedStep.RELAX,
        StepType.VC_RELAX: GeneralizedStep.VC_RELAX,
        StepType.NSCF: GeneralizedStep.NSCF,
        StepType.BANDS_PW: GeneralizedStep.BANDS,
        StepType.BANDS: GeneralizedStep.BANDS,
        StepType.DOS: GeneralizedStep.DOS,
        StepType.W90_PREPROC: GeneralizedStep.WANNIER,
        StepType.PW2WANNIER90: GeneralizedStep.WANNIER,
        StepType.W90_RUN: GeneralizedStep.WANNIER,
        StepType.PYSCF_SCF: GeneralizedStep.SCF,
        # ... other mappings
    }
    ```
  - **Constraint**: This is CONCEPTUAL ONLY; execution logic unchanged
  - **Tests Impacted**: Minimal unit tests for mapping (no execution tests)

- [ ] **B1.3**: Document generalized step vs engine-specific step separation
  - **Why**: Clarify architecture; execution unchanged
  - **Documentation**: Add to `docs/design/workflow_pipeline.md` (new file)
  - **Content**:
    - Generalized steps: Physical operations (SCF, NSCF, Wannierization), engine-agnostic, conceptual only (NOT written to disk, NO executables)
    - Engine-specific steps: Existing step types (qe_scf, qe_nscf, w90_run, pyscf_xxx), execution UNCHANGED, written to step.yaml, executed
    - Workflow: Ordered list of generalized steps (conceptual only in v0)
    - Materialization: Workflow → engine-specific steps mapping (future work)
  - **Tests Impacted**: None (documentation only)

**Deliverable**: Conceptual generalized step taxonomy (enums/mappings only; NO execution changes)

---

### B2) Workflow Materialization (Design-Level)

**Task**: Document workflow materialization concept (design-level only)

- [ ] **B2.1**: Document workflow materialization architecture
  - **Why**: Design-level scaffolding only; clarify how workflows materialize to engine-specific steps
  - **Documentation**: Add to `docs/design/workflow_pipeline.md`
  - **Content**:
    - Workflow: Ordered list of generalized steps
    - Materialization mapping: Workflow declares valid materialization mappings (e.g., generalized workflow → qe + wannier90)
    - Materialization produces: Ordered list of engine-specific steps (written to step.yaml, executed)
  - **Tests Impacted**: None (documentation only)

- [ ] **B2.2**: Defer workflow materialization implementation
  - **Why**: v0 focuses on IR landing; workflow materialization is future work
  - **Note**: Implementation deferred to future phase
  - **Tests Impacted**: None (deferred)

**Deliverable**: Documentation of workflow materialization concept (implementation deferred)

---

## Phase 3: Engine Layer (QE Adapter Implementation)

**Status**: ✅ QE ADAPTER MUST BE IMPLEMENTED (IR↔QE mapping); ⚠️ NO central registry, NO engine_id in step.yaml

**Architecture**: Engines are responsible for:
1. Translating IR parameters → engine-specific parameters (QE adapter MUST be implemented)
2. Executing engine-specific steps (unchanged in v0)

**v0 Constraints**:
- QE adapter MUST be implemented (IR↔QE mapping)
- QE execution path MUST NOT be refactored (runners, generators, done-detection unchanged)
- Wannier execution path MUST NOT be refactored
- NO central engine registry
- NO engine_id in step.yaml in v0
- PySCF may be refactored internally if needed (must not affect QE/Wannier, must remain restartable)

### C1) Engine ID and Registry (EXPLICITLY DEFERRED)

**Task**: Document that engine_id/registry is NOT implemented in v0

- [ ] **C1.1**: Document engine_id/registry deferral
  - **Why**: v0 MUST NOT introduce engine_id in step.yaml or central engine registry
  - **Documentation**: Add note in plan that engine_id/registry is explicitly deferred
  - **Note**: Existing execution paths work without engine_id (QE/Wannier use implicit engine selection)
  - **Tests Impacted**: None (documentation only)

**Deliverable**: Documentation that engine_id/registry is explicitly deferred (not v0)

**Note**: QE/Wannier execution works without engine_id (implicit engine selection via step_type)

---

### C2) IR → Engine-Specific Parameter Translation (QE Adapter - MUST IMPLEMENT)

**Task**: Implement IR→QE translation in QE engine adapter (not ParamSpace)

- [ ] **C2.1**: Implement IR→QE translation in QE adapter/compiler layer
  - **Why**: Engines are responsible for translating IR → engine-specific parameters; QE adapter MUST be implemented
  - **Location**: QE engine adapter/compiler (e.g., `src/quantumvitas/core/engines/qe/adapter.py` or IR backend `src/quantumvitas/ir/backends/qe/mapping.py`)
  - **Exact Edit**: Translation function: `ir_patch_to_qe_patch(ir_patch: Dict) -> Dict` (converts IR keys to QE section/key)
  - **Architecture**: IR→QE translation happens in QE engine layer, NOT in ParamSpace
  - **Constraint**: Must NOT refactor QE execution paths (runners, generators, done-detection unchanged)
  - **Tests Impacted**: IR→QE translation tests (new), integration tests (update)

- [ ] **C2.2**: Implement QE→IR translation in QE adapter/compiler layer
  - **Why**: Detection needs QE→IR conversion before ParamSpace matching
  - **Location**: QE engine adapter/compiler
  - **Exact Edit**: Translation function: `qe_yaml_to_ir_yaml(qe_yaml: Dict) -> Dict` (converts QE section/key to IR keys)
  - **Architecture**: QE→IR translation happens in QE engine layer, NOT in ParamSpace
  - **Constraint**: Must NOT refactor QE execution paths
  - **Tests Impacted**: QE→IR translation tests (new), detection integration tests (update)

**Deliverable**: ✅ FULLY IMPLEMENTED IR↔QE translation in QE engine adapter/compiler layer (separate from ParamSpace)

### C3) Session-Restartable Artifacts (Documentation)

**Task**: Document current PySCF runner artifacts and restartability

- [ ] **C3.1**: Inspect PySCF runner artifact persistence
  - **Why**: Understand what artifacts PySCF persists per step
  - **File**: `src/quantumvitas/engines/pyscf/runner.py:117-359`
  - **Finding**: Runner writes `results.json` after each step (restartable)
  - **Tests Impacted**: None (documentation only)

- [ ] **C3.2**: Document PySCF session-restartable requirements
  - **Why**: Charter requires session-restartable semantics
  - **Documentation**: Add to `docs/design/engine_contract.md` (new file)
  - **Content**: Document PySCF artifacts (`results.json`, logs) and restart requirements
  - **Tests Impacted**: None (documentation only)

- [ ] **C3.3**: Document QE session-restartable requirements
  - **Why**: Charter requires session-restartable semantics for all engines
  - **Documentation**: Add to `docs/design/engine_contract.md`
  - **Content**: Document QE artifacts (`.out`, `.wfc`, `.charge-density`) and restart requirements
  - **Tests Impacted**: None (documentation only)

**Deliverable**: Documentation of session-restartable requirements for QE and PySCF

---

### C4) Engine "Done" Detection (Documentation)

**Task**: Document current engine-specific "done" detection

- [ ] **C4.1**: Inspect QE "done" detection
  - **Why**: Understand how QE determines step completion
  - **File**: `src/quantumvitas/calculation/step_done.py:86-141`
  - **Finding**: QE checks for "JOB DONE" in primary `.out` file
  - **Tests Impacted**: None (documentation only)

- [ ] **C4.2**: Document engine-specific "done" detection
  - **Why**: Charter says "done" detection remains engine-specific in v0
  - **Documentation**: Add to `docs/design/engine_contract.md`
  - **Content**: Document QE (file + "JOB DONE") and PySCF (`results.json` existence) detection methods
  - **Tests Impacted**: None (documentation only)

**Deliverable**: Documentation of engine-specific "done" detection (no generalization in v0)

---

## Testing Matrix

### Unit Tests (New)

- [ ] `tests/ir/test_parameters.py`: IR parameter registry tests
- [ ] `tests/ir/test_mapping.py`: IR↔QE adapter mapping tests
- [ ] `tests/presets/test_paramspace_ir.py`: ParamSpace with IR keys tests
- [ ] `tests/presets/test_preset_ir.py`: Preset compile/detect with IR keys tests
- [ ] `tests/engines/test_qe_adapter.py`: QE engine adapter IR↔QE translation tests

### Integration Tests (New)

- [ ] `tests/presets/test_integration_ir.py`: Preset application with IR keys integration tests
- [ ] `tests/presets/test_ssot_enforcement.py`: step.yaml SSOT enforcement tests

### Regression Tests (Update)

- [ ] Update `tests/presets/test_paramspace.py`: ParamSpace reversibility tests (verify IR keys work)
- [ ] Update `tests/presets/test_compiler.py`: Compiler tests (verify IR keys work)
- [ ] Update `tests/presets/test_detector.py`: Detector tests (verify IR keys work)

---

## Migration / Backward Compatibility

### Old step.yaml Compatibility

- [ ] **BC1**: Verify old step.yaml files (QE params only) still work
  - **Why**: Backward compatibility requirement
  - **Expected**: Old step.yaml files should continue to work (no IR keys, only QE params)
  - **Tests**: `test_backward_compatibility_qe_params_only()`

### Missing Fields Handling

- [ ] **BC2**: No engine_id field handling needed (deferred)
  - **Why**: Engine_id introduction deferred to future phase
  - **Expected**: No engine_id field in v0; existing step.yaml files work as-is

---

## Risks & Non-Goals Reaffirmed

### What We Will NOT Do in v0

1. **No user-facing IR editing**: IR is internal-only; no Jupyter/API migration to IR
2. **No Ry↔eV conversion**: IR base units align with QE (Ry, Bohr); no unit conversion
3. **No semantic refactoring of ParamSpace**: Keep nspin/noncolin/lspinorb as-is (no spin_mode/soc normalization)
4. **No IR/preset persistence in step.yaml**: step.yaml contains QE params only
5. **No perfect generalized requires/produces**: File-based engines share outdir; granularity limited
6. **No full long-lived Python worker**: Session-fast optimization deferred
7. **No full multi-engine support**: QE primary; PySCF skeleton only

---

## Questions / Unknowns Resolved by Code Inspection

### Q1: Where does ParamSpace currently store QE parameter names?

**Answer**: `ParamKey.key` field in `src/quantumvitas/presets/paramspace.py:117-160`.  
**Evidence**: `ParamKey` dataclass has `key: str` field which currently contains QE parameter names (e.g., "nspin", "ecutwfc").  
**Resolution**: Replace `key` field usage with IR keys; use IR→QE adapter for YAML I/O.

---

### Q2: How does ParamSpace read/write YAML currently?

**Answer**: `match_profile()` and `compile_profile_patch()` in `src/quantumvitas/presets/paramspace.py:238-374`.  
**Evidence**: 
- `match_profile()` uses `yaml_tree[key.section].get(key.key)` to read values
- `compile_profile_patch()` uses `patch[key.section][key.key] = value` to write values
**Resolution**: Convert IR keys to QE section/key via adapter before YAML I/O.

---

### Q3: Does step.yaml currently have engine_id field?

**Answer**: No.  
**Evidence**: `StructureStepSpec` in `src/quantumvitas/calculation/structure_steps.py:34-54` has no `engine_id` field.  
**Resolution**: Engine_id introduction deferred to future phase (v0 MUST NOT break existing QE/Wannier behavior).

---

### Q4: Where does preset application mutate step.yaml?

**Answer**: `apply_presets_to_step()` in `src/quantumvitas/presets/integration.py:327-550`.  
**Evidence**: Uses `StepDoc` to load/mutate step.yaml, then saves via `save_yaml_doc()`.  
**Resolution**: No changes needed; compilation already produces QE params via adapter.

---

### Q5: How does journal record changes?

**Answer**: `save_yaml_doc()` in `src/quantumvitas/core/yaml_io.py:117-124` records before/after snapshots.  
**Evidence**: Journal hook in `save_yaml_doc()` automatically records changes.  
**Resolution**: IR/preset provenance can be derived from journal if needed (not stored in step.yaml).

---

### Q6: How does QE determine step completion?

**Answer**: `is_step_done()` in `src/quantumvitas/calculation/step_done.py:86-141` checks for "JOB DONE" in primary `.out` file.  
**Evidence**: Function checks file existence and "JOB DONE" marker.  
**Resolution**: Document engine-specific "done" detection (no generalization in v0).

---

### Q7: Is K_POINTS treated as a card or namelist parameter?

**Answer**: Card (not namelist).  
**Evidence**: In `build_precision_paramspace()`, `ParamKey(section="cards", key="K_POINTS", ...)` indicates card structure.  
**Resolution**: Handle K_POINTS card mapping specially in IR→QE adapter (section="cards").

---

## Conclusion

This plan provides a detailed, checkbox-driven implementation path for v0 IR/Step/Engine generalization while preserving all existing behavior and respecting the non-negotiable principles from the charter.

**Key Points**:
- **Two Parallel Pipelines**: Parameter pipeline (Preset → IR → Engine-specific) and Workflow pipeline (Workflow → Generalized Steps → Engine-specific Steps)
- **IR Layer (FULLY IMPLEMENTED)**: ParamSpace operates ONLY on IR keys; IR→QE translation in QE engine adapter (NOT in ParamSpace)
- **step.yaml remains SSOT**: Engine-specific parameters only (QE params in v0); no IR/preset persistence
- **Step Layer (CONCEPTUAL ONLY)**: Generalized steps (enums/mappings/documentation only, NOT written to disk, NO execution changes) vs Engine-specific steps (unchanged, written to step.yaml, executed)
- **Engine Layer (QE ADAPTER IMPLEMENTED)**: QE adapter translates IR → engine-specific params; v0 MUST NOT refactor QE/Wannier execution paths; NO central registry; NO engine_id in step.yaml
- **v0 Scope**: IR landing is FULLY IMPLEMENTED (primary deliverable); Step generalization is conceptual only (enums/mappings); Engine generalization is QE adapter only (no registry/engine_id)

**End State Requirement**:
- System must be usable exactly as before from user perspective
- Workflow UI may show generalized names, but behavior must be unchanged
- QE + Wannier workflows must still run end-to-end

**Next Steps**: 
1. ✅ Plan updated with final clarifications
2. ⏭️ **IMMEDIATELY START IMPLEMENTATION** following this plan
3. Implement IR landing first (Phase 1: A1-A7)
4. Add tests as you go
5. Run targeted tests frequently
6. Run full test suite at major milestones
7. Do NOT wait for further approval unless encountering genuine ambiguity

**Implementation Notes**:
- If you change anything for test stability or compatibility, WRITE IT DOWN
- If you encounter a real ambiguity that blocks progress, stop and ask
- Otherwise, proceed with implementation
- Do not over-engineer
- Do not refactor execution

---

**End of Implementation Plan**

