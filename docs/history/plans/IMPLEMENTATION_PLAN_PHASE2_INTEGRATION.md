# Implementation Plan: Phase 2 - Preset Integration Layer

**Status**: In Progress  
**Last Updated**: 2025-12-30  
**Prerequisite**: Phase 1 (Presets Detector B + Compiler) - COMPLETE  
**Constitution Reference**: Chapter 10

---

## Overview

This phase integrates the completed preset detection and compilation system into
the QMatSuite calculation infrastructure. The goal is to make presets *usable*
from the daemon API and calculation layer while maintaining Constitution compliance.

### Key Constraints (unchanged)

1. `step.yml` remains the sole executable truth (§10.1.1)
2. Presets/workflows are runtime-only, never persisted (§10.2.1)
3. Detector B is the sole legitimate state source for UI (§10.4.1)
4. No step topology assumptions

### What's Already Done

- ✅ `quantumvitas.presets.detector` - Tolerant detection from step params
- ✅ `quantumvitas.presets.compiler` - Canonical encoding, strict
- ✅ Mathematical equivalence verified by tests
- ✅ 70 unit tests passing

---

## Phase 2 Goals

1. **Daemon API exposure** - Expose preset detection via daemon for GUI
2. **Calculation-level detection** - Aggregate presets from calculation's steps
3. **Step creation with presets** - Allow preset options when creating steps
4. **Preset application** - Apply preset to existing step (overwrite)

---

## Implementation Plan

### Phase 2.1: Daemon API for Preset Detection ✅ COMPLETE

**Goal**: Expose `detect_all_presets` via daemon so GUI can derive preset state.

- [x] **2.1.1** Add daemon handler for preset detection
  - File: `src/quantumvitas/daemon/server.py`
  - Method: `_handle_detect_presets(calculation_id)`
  - Returns: `{spin: "collinear", soc: "no_soc", material: "metal"}` or `"Custom"`
  
- [x] **2.1.2** Load step parameters from calculation
  - `src/quantumvitas/presets/integration.py` - `_load_step_parameters()`
  - Read all step.yaml files for calculation
  - Extract parameters dict from each
  - Pass to `detect_all_presets(steps)`

- [x] **2.1.3** Add integration test
  - File: `tests/unit/test_preset_integration.py`
  - 26 tests covering step loading, preset detection, workflow detection
  - Tests with synthetic calculations and tmp_path fixtures

### Phase 2.2: Apply Presets to Step ✅ COMPLETE

**Goal**: Allow applying preset options to an existing step (overwrite params).

- [x] **2.2.1** Create apply_presets_to_step function
  - File: `src/quantumvitas/presets/integration.py`
  - Function: `apply_presets_to_step(step_path, options, validate_physics=True)`
  - Reads step.yaml, applies compiled params, writes back
  - Per §10.3.3: OVERWRITE, not merge

- [x] **2.2.2** Handle parameter merging correctly
  - Compiled params go into SYSTEM section
  - Existing SYSTEM params NOT in preset dimensions are preserved
  - Preset dimension params are replaced

- [x] **2.2.3** Add integration test
  - Tests for roundtrip detection
  - Tests for physics validation
  - Tests for parameter preservation

### Phase 2.3: Create Step with Presets

**Goal**: Support preset options in step creation flow.

- [ ] **2.3.1** Add preset options to step creation
  - When creating step via CLI or API
  - Accept optional preset options dict
  - Compile and merge with default step params

- [ ] **2.3.2** Daemon handler for create_step_with_presets
  - Method: `handle_create_step(calc_id, step_type, preset_options)`
  - Returns: created step info

- [ ] **2.3.3** Add daemon test for step creation with presets

### Phase 2.4: Workflow Detection (Runtime-Only) ✅ COMPLETE

**Goal**: Detect workflow type from step sequence (informational only).

- [x] **2.4.1** Define workflow detection logic
  - File: `src/quantumvitas/presets/integration.py` (combined with integration)
  - Analyze step_types in calculation
  - Return detected workflow: DOS, BandStructure, Relaxation, etc.

- [x] **2.4.2** Workflow detection rules
  - SCF only → "SCF"
  - SCF + NSCF + DOS → "DOS"
  - SCF + BANDS_PW + BANDS → "BandStructure"
  - RELAX or VC_RELAX → "Relaxation"
  - PH → "Phonon"
  - MD or VC-MD → "MD"

- [x] **2.4.3** Add to daemon API
  - Method: `_handle_detect_workflow(calculation_id)`
  - Returns: detected workflow name

- [x] **2.4.4** Add unit tests for workflow detection
  - 9 tests in TestDetectWorkflowType

### Phase 2.5: Validation Layer

**Goal**: Non-fatal physics warnings for preset combinations.

- [ ] **2.5.1** Create validation module
  - File: `src/quantumvitas/presets/validation.py`
  - Function: `validate_preset_combination(options) -> List[Warning]`

- [ ] **2.5.2** Define warning rules
  - SOC without noncollinear → Error (already in compiler)
  - noncollinear without FR pseudopotential → Warning
  - metal without k-point sampling → Warning

- [ ] **2.5.3** Integrate with apply_presets
  - Return warnings alongside success

---

## Test Strategy

### New Test Files

| File | Purpose |
|------|---------|
| `tests/daemon/test_preset_detection.py` | Daemon API preset detection |
| `tests/unit/test_preset_integration.py` | Apply/create step with presets |
| `tests/unit/test_workflow_detection.py` | Workflow type detection |
| `tests/unit/test_preset_validation.py` | Physics warnings |

### Test Data Requirements

Use existing `tests/data/` fixtures:
- DOS workflow: `4_Si_DOS/`
- Band structure: `7_Si_bandStructure/`
- Relaxation: `3_Si_vc_relax/`
- Spin polarized: `8_Fe_DOS/`

---

## Verification Commands

```bash
# Run all new tests
python -m pytest tests/unit/test_preset_integration.py tests/unit/test_workflow_detection.py -v

# Run daemon tests
python -m pytest tests/daemon/test_preset_detection.py -v

# Full test suite
python -m pytest tests/ -v --tb=short
```

---

## Milestone Definitions

### Milestone 2.1 (First Stop Point) ✅ COMPLETE
- [x] Daemon can detect presets from calculation
- [x] 26 integration tests passing
- [x] No regressions (96 total tests passing)

### Milestone 2.2 ✅ COMPLETE
- [x] Can apply presets to existing step
- [x] Integration tests passing

### Milestone 2.3
- [ ] Step creation accepts preset options
- [ ] Daemon handler working

### Milestone 2.4 ✅ COMPLETE
- [x] Workflow detection logic complete
- [x] Detection tests for SCF, DOS, Bands, Relaxation, Phonon, MD workflows

### Milestone 2.5
- [ ] Validation layer with warnings
- [ ] Integration complete

---

## Design Decisions

### Apply Presets Strategy

Per Constitution §10.3.3, preset apply must OVERWRITE:

```python
# Correct: Replace entire SYSTEM section's preset-related params
existing_params = {"SYSTEM": {"ecutwfc": 50, "nspin": 1, "occupations": "'fixed'"}}
compiled = {"SYSTEM": {"nspin": 2, "occupations": "'smearing'", "smearing": "'gaussian'", "degauss": 0.01}}

# Result: ecutwfc preserved, nspin/occupations replaced
result = {"SYSTEM": {"ecutwfc": 50, "nspin": 2, "occupations": "'smearing'", "smearing": "'gaussian'", "degauss": 0.01}}
```

### Workflow Detection is Informational

- Workflow detection is for display/hints only
- Does NOT affect step execution
- Does NOT affect preset detection
- A calculation can have "unknown" workflow

---

## Handoff Notes

If resuming this phase:

1. Presets module is complete at `src/quantumvitas/presets/`
2. Daemon server is at `src/quantumvitas/daemon/server.py`
3. Step specs are at `src/quantumvitas/calculation/structure_steps.py`
4. Start with Phase 2.1.1 (daemon handler)

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-30 | Initial plan created | AI |
| 2025-12-30 | Milestone 2.1, 2.2, 2.4 completed | AI |
| 2025-12-30 | 96 tests passing (70 detector + 26 integration) | AI |

