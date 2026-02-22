# Implementation Plan: Presets (Detector B + Compiler)

**Status**: ✅ COMPLETE  
**Last Updated**: 2025-12-30  
**Constitution Reference**: Chapter 10 (Calculation Model & Preset/Workflow Constitution)  
**Design Document**: `docs/WORKFLOW_PRESET_DESIGN_V0.md`

---

## Overview

This document tracks the implementation of the preset detection and compilation system for QMatSuite. Per Constitution Chapter 10:

- **Detector B** (§10.4-10.5): Reverse-detects preset values from step parameters (tolerant, supports implicit defaults)
- **Compiler** (§10.3): Forward-generates step parameters from preset options (strict, canonical encoding)
- **Equivalence Axiom** (§10.6): `detect(compile_one(step_type, options)) == options`

### Key Invariants

1. `step.yml` is the sole executable truth for parameters (§10.1.1)
2. Presets/workflows are runtime-only, never persisted (§10.2.1)
3. Detector B is the sole legitimate state source for UI (§10.4.1)
4. No "Unknown" state; either single detected value or CUSTOM (§10.5.1)
5. Compiler must use canonical encoding - explicit all key parameters (§10.3.4)
6. Compiler is overwrite-only, not merge/append (§10.3.3)

---

## V0 Preset Dimensions

| Dimension | Options | QE Parameters | Notes |
|-----------|---------|---------------|-------|
| **Spin** | `nonspin`, `collinear`, `noncollinear` | `nspin`, `noncolin` | Default: nonspin |
| **SOC** | `no_soc`, `with_soc` | `lspinorb`, `noncolin` | Requires noncollinear for with_soc |
| **Material** | `insulator`, `metal` | `occupations`, `smearing`, `degauss` | Affects Fermi level handling |

---

## Completed Tasks

### Phase 1: Detector B Core Logic ✅

- [x] **1.1** Create preset/detector module structure
  - Files: `src/qmatsuite/presets/__init__.py`, `dimensions.py`, `detector.py`
  - Completed: 2025-12-30

- [x] **1.2** Define preset dimension enums
  - `SpinOption`: NONSPIN, COLLINEAR, NONCOLLINEAR
  - `SOCOption`: NO_SOC, WITH_SOC
  - `MaterialOption`: INSULATOR, METAL
  - `CUSTOM` singleton for heterogeneous detection

- [x] **1.3** Implement single-step detection functions
  - `detect_spin(params)` - handles nspin, noncolin, implicit defaults
  - `detect_soc(params)` - handles lspinorb, implicit defaults
  - `detect_material(params)` - handles occupations variants

- [x] **1.4** Implement multi-step aggregation
  - `detect_dimension_from_steps(steps, dimension)` - single value or CUSTOM
  - Per §10.5.1: |unique values| == 1 → value, else CUSTOM

- [x] **1.5** Implement detect_all_presets
  - `detect_all_presets(steps)` - returns all v0 dimensions

- [x] **1.6** Add unit tests with tests/data tutorial cases
  - 40 tests covering all detection scenarios
  - Real QE inputs: Si SCF, Fe collinear/noncollinear, Al DOS

- [x] **1.7** Add compiler-detector equivalence test placeholders
  - 7 skipped tests awaiting Compiler implementation

---

## Completed Tasks (Phase 2-5)

### Phase 2: Compiler Implementation ✅

- [x] **2.1** Create compiler module
  - File: `src/qmatsuite/presets/compiler.py`
  - Pure functions mapping options → canonical parameters
  - Completed: 2025-12-30

- [x] **2.2** Implement compile_spin
  - `compile_spin(option: SpinOption) -> Dict[str, Any]`
  - Explicitly writes: nspin=1 (nonspin), nspin=2 (collinear), noncolin=.true. (noncollinear)
  - Canonical encoding: no reliance on defaults

- [x] **2.3** Implement compile_soc
  - `compile_soc(option: SOCOption, spin: SpinOption) -> Dict[str, Any]`
  - Explicitly writes: lspinorb=.false. (no_soc), lspinorb=.true. (with_soc)
  - Physics validation: raises PresetCompilationError if with_soc without noncollinear

- [x] **2.4** Implement compile_material
  - `compile_material(option: MaterialOption) -> Dict[str, Any]`
  - INSULATOR: occupations='fixed' (explicit)
  - METAL: occupations='smearing', smearing='gaussian', degauss=0.01

- [x] **2.5** Implement compile_presets
  - `compile_presets(options: Dict) -> Dict[str, Dict[str, Any]]`
  - Combines all dimensions into SYSTEM namelist parameters
  - Handles dimension interactions (SOC requires noncollinear)
  - Optional validate_physics flag for strict/lenient compilation

- [x] **2.6** Export compiler functions in __init__.py

### Phase 3: Equivalence Tests ✅

- [x] **3.1** Implement spin roundtrip tests
  - `test_spin_roundtrip_nonspin` - PASSED
  - `test_spin_roundtrip_collinear` - PASSED
  - `test_spin_roundtrip_noncollinear` - PASSED

- [x] **3.2** Implement SOC roundtrip tests
  - `test_soc_roundtrip_no_soc` - PASSED
  - `test_soc_roundtrip_with_soc` - PASSED

- [x] **3.3** Implement material roundtrip tests
  - `test_material_roundtrip_insulator` - PASSED
  - `test_material_roundtrip_metal` - PASSED

- [x] **3.4** Add combined preset roundtrip tests
  - `test_full_preset_roundtrip_defaults` - PASSED
  - `test_full_preset_roundtrip_collinear_metal` - PASSED
  - `test_full_preset_roundtrip_noncollinear_soc` - PASSED
  - `test_homogeneous_compiled_steps_detect_single_value` - PASSED
  - `test_heterogeneous_compiled_steps_detect_custom` - PASSED

### Phase 4: Edge Cases and Robustness ✅

- [x] **4.1** Tests for physics constraint validation
  - `test_soc_with_nonspin_raises_error` - PASSED
  - `test_soc_with_collinear_raises_error` - PASSED
  - `test_compile_presets_soc_nonspin_raises` - PASSED
  - `test_compile_presets_skip_physics_validation` - PASSED

- [x] **4.2** Tests for step_type applicability
  - `test_compile_presets_for_dos_step` - PASSED (returns empty for post-processing)
  - `test_compile_presets_for_bands_step` - PASSED
  - `test_compile_presets_for_scf_step` - PASSED

- [x] **4.3** Tests for string option normalization
  - `test_compile_presets_string_spin` - PASSED
  - `test_compile_presets_string_noncollinear` - PASSED

### Phase 5: Documentation and Cleanup ✅

- [x] **5.1** Update this implementation plan with final status
- [x] **5.2** Add docstrings with Constitution references
  - All functions have detailed docstrings referencing Constitution sections
- [x] **5.3** Verify all tests pass
  - 70 preset tests passing
  - 568 total unit tests passing

---

## Verification Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install in dev mode
pip install -e '.[dev]'

# Run preset tests only
python -m pytest tests/unit/test_detector_b.py -v

# Run all unit tests
python -m pytest tests/unit/ -v --tb=short

# Run full test suite
python -m pytest tests/ -v --tb=short
```

---

## Design Decisions

### Compiler Canonical Encoding Strategy

Per Constitution §10.3.4, Compiler must explicitly write all key parameters:

| Dimension | Option | Explicit Parameters |
|-----------|--------|---------------------|
| Spin | nonspin | `nspin=1` |
| Spin | collinear | `nspin=2` |
| Spin | noncollinear | `noncolin=.true.` (nspin not written, QE sets internally) |
| SOC | no_soc | `lspinorb=.false.` |
| SOC | with_soc | `lspinorb=.true.` |
| Material | insulator | `occupations='fixed'` |
| Material | metal | `occupations='smearing'`, `smearing='gaussian'`, `degauss=0.01` |

### Dimension Interactions

1. **SOC requires noncollinear**: If `with_soc` is requested but spin is `nonspin` or `collinear`, Compiler should:
   - Option A: Raise error (strict)
   - Option B: Implicitly upgrade to noncollinear (convenient but implicit)
   - **Decision**: Option A - be explicit about physics constraints

2. **Material and smearing parameters**: For metals, we provide sensible defaults but users can override via step params.

### Post-Processing Steps

Steps like `dos`, `bands`, `projwfc` don't have a SYSTEM namelist. Detection should:
- Return dimension defaults for missing SYSTEM
- This is consistent with "implicit default" semantics

---

## Handoff Notes

**Implementation is COMPLETE.** All phases have been implemented and tested.

### Files Created/Modified

| File | Purpose |
|------|---------|
| `src/qmatsuite/presets/__init__.py` | Public API exports |
| `src/qmatsuite/presets/dimensions.py` | Enum definitions (SpinOption, SOCOption, MaterialOption, CUSTOM) |
| `src/qmatsuite/presets/detector.py` | Detector B implementation (tolerant, implicit defaults) |
| `src/qmatsuite/presets/compiler.py` | Compiler implementation (strict, canonical encoding) |
| `tests/unit/test_detector_b.py` | 70 comprehensive tests |
| `docs/IMPLEMENTATION_PLAN_PRESETS.md` | This plan document |

### Test Coverage

```
tests/unit/test_detector_b.py - 70 tests
├── TestSpinDetection (10 tests)
├── TestSOCDetection (5 tests)
├── TestMaterialDetection (8 tests)
├── TestMultiStepAggregation (5 tests)
├── TestDetectAllPresets (3 tests)
├── TestRealQEInputs (5 tests)
├── TestCustomSingleton (4 tests)
├── TestCompilerDetectorEquivalence (10 tests)
├── TestCompilerCanonicalEncoding (8 tests)
├── TestCompilerPhysicsConstraints (5 tests)
├── TestCompilerStringOptions (2 tests)
├── TestCompilerPostProcessing (3 tests)
└── TestMultiStepCompilerDetectorEquivalence (2 tests)
```

### Possible Future Enhancements

1. **Additional preset dimensions** (per WORKFLOW_PRESET_DESIGN_V0.md):
   - Accuracy (low/medium/high) - affects ecutwfc, conv_thr, k-point density
   - DFT+U (no_hubbard/with_hubbard)
   - XC Functional (pbe/lda/etc.)
   - vdW Correction

2. **Workflow-aware compilation**:
   - Step-type specific parameter variations
   - K-point handling for DOS vs bands workflows

3. **Integration with UI**:
   - Expose detect_all_presets via daemon API
   - Preset selector components that use Compiler

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-30 | Initial plan, Detector B complete | AI |
| 2025-12-30 | Compiler implementation complete | AI |
| 2025-12-30 | All equivalence tests passing | AI |
| 2025-12-30 | Phase 4 edge case tests complete | AI |
| 2025-12-30 | **IMPLEMENTATION COMPLETE** - 70 preset tests, 568 total tests passing | AI |

