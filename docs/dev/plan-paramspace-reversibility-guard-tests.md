# ParamSpace Reversibility Guard Tests Implementation Plan

**Version**: 1.0  
**Date**: 2025-01-17  
**Purpose**: Define constitution-grade regression tests that permanently lock reversibility/uniqueness invariants across engines.

---

## 1. Code Review Summary: Existing Test Coverage

### 1.1 Existing Reversibility Tests

| Test File | Coverage | Dimensions | Engines |
|-----------|----------|------------|---------|
| `tests/unit/test_paramspace_contract.py` | Roundtrip apply→detect | occupations_scheme, precision | QE (implicit) |
| `tests/unit/test_magnetism_paramspace_contract.py` | Roundtrip, explicit false, contradictions | magnetism | QE (implicit) |
| `tests/unit/test_paramspace_invariants.py` | Invariant enforcement, oracle, compile order | occupations_scheme + precision | QE |
| `tests/integration/test_precision_roundtrip.py` | Multi-step precision roundtrip | precision | QE |
| `tests/unit/test_key_access_enforcement.py` | Key ownership enforcement | occupations_scheme, precision, magnetism | QE |
| `tests/unit/test_qc_precision_paramspace.py` | QC precision roundtrip | qc_precision | PySCF/ORCA |

### 1.2 Existing Capability/Guard Tests

| Test File | Coverage |
|-----------|----------|
| `tests/unit/test_preset_capability_contract.py` | Capability resolver contract |
| `tests/unit/test_no_deprecated_preset_fields.py` | Guard: no accepts_presets/allowed_dimensions |
| `tests/unit/test_no_capability_bypass.py` | Guard: no capability bypass |
| `tests/unit/test_no_steptype_enum.py` | Guard: no StepType enum in production |
| `tests/unit/test_engine_supported_presets.py` | Engine.supported_presets property |

### 1.3 Gaps Identified

1. **No systematic negative invariant tests**: No tests that mutate a single key and verify CUSTOM detection
2. **No convergence dimension tests**: `convergence` dimension has no roundtrip tests
3. **No cross-engine roundtrip tests**: QC engines (PySCF, ORCA) lack full roundtrip coverage
4. **No explicit test for "multiple engine-specific patches = hard error"**
5. **No test verifying ORCA binary-optional behavior** for capability tests

---

## 2. Test Matrix

### 2.1 Dimensions and Representative Profiles

| Dimension | Profile | Representative Gen Steps | Engines |
|-----------|---------|--------------------------|---------|
| magnetism | NM (NONMAGNETIC) | scf | QE |
| magnetism | COL (COLLINEAR_LSDA) | scf, relax | QE |
| magnetism | NC_CANONICAL (NONCOLLINEAR) | scf | QE |
| occupations_scheme | FIXED | scf, relax | QE |
| occupations_scheme | SMEARING_GAUSSIAN | scf | QE |
| precision | LOW | scf | QE |
| precision | MED | scf, nscf | QE |
| precision | HIGH | scf | QE |
| convergence | NORMAL | scf | QE |
| convergence | ROBUST | scf | QE |
| qc_precision | LOW | scf | PySCF, ORCA* |
| qc_precision | MED | scf | PySCF, ORCA* |
| qc_precision | HIGH | scf | PySCF, ORCA* |

*ORCA tests must skip if binary unavailable

### 2.2 Keys to Mutate for Negative Tests

| Dimension | Key to Mutate | Profile | Expected Result |
|-----------|---------------|---------|-----------------|
| magnetism | `SYSTEM.nspin` | COL (expects 2) → 3 | CUSTOM |
| magnetism | `SYSTEM.noncolin` | NC_CANONICAL (expects True) → False | CUSTOM |
| occupations_scheme | `SYSTEM.occupations` | FIXED (expects "fixed") → "smearing" | CUSTOM |
| occupations_scheme | `SYSTEM.smearing` | SMEARING_GAUSSIAN → "mp" | CUSTOM |
| precision | `SYSTEM.ecutwfc` | MED → +1 | CUSTOM |
| precision | `ELECTRONS.conv_thr` | MED → 1e-5 | CUSTOM |
| convergence | `ELECTRONS.mixing_beta` | NORMAL (expects 0.4) → 0.5 | CUSTOM |
| qc_precision | `scf.conv_tol` | MED → different value | CUSTOM |

---

## 3. New Test Classes

### 3.1 Round-Trip Invariant Tests

**File**: `tests/unit/test_paramspace_roundtrip_invariants.py`

**Purpose**: Systematic roundtrip tests for ALL dimensions with explicit engine coverage.

**Structure**:
```python
class TestRoundtripInvariants:
    """
    Constitution-grade roundtrip tests.
    
    Invariant: apply(preset) → detect() == preset
    """
    
    # --- Magnetism ---
    def test_roundtrip_magnetism_nm(self): ...
    def test_roundtrip_magnetism_col(self): ...
    def test_roundtrip_magnetism_nc(self): ...
    def test_roundtrip_magnetism_soc(self): ...
    
    # --- OccupationsScheme ---
    def test_roundtrip_occupations_fixed(self): ...
    def test_roundtrip_occupations_smearing(self): ...
    def test_roundtrip_occupations_tetrahedra(self): ...
    
    # --- Precision (QE) ---
    def test_roundtrip_precision_low_scf(self): ...
    def test_roundtrip_precision_med_scf(self): ...
    def test_roundtrip_precision_high_scf(self): ...
    def test_roundtrip_precision_med_nscf(self): ...
    
    # --- Convergence ---
    def test_roundtrip_convergence_fast(self): ...
    def test_roundtrip_convergence_normal(self): ...
    def test_roundtrip_convergence_robust(self): ...
    def test_roundtrip_convergence_very_robust(self): ...
    
    # --- QC Precision (PySCF) ---
    @pytest.mark.skipif(not is_pyscf_available(), reason="PySCF not installed")
    def test_roundtrip_qc_precision_low_pyscf(self): ...
    def test_roundtrip_qc_precision_med_pyscf(self): ...
    def test_roundtrip_qc_precision_high_pyscf(self): ...
    
    # --- QC Precision (ORCA) - skip if binary not available ---
    @pytest.mark.skipif(not is_orca_available(), reason="ORCA not installed")
    def test_roundtrip_qc_precision_low_orca(self): ...
    def test_roundtrip_qc_precision_med_orca(self): ...
    def test_roundtrip_qc_precision_high_orca(self): ...
```

### 3.2 Negative Invariant Tests

**File**: `tests/unit/test_paramspace_negative_invariants.py`

**Purpose**: Verify that ANY mutation of an owned key causes CUSTOM detection.

**Structure**:
```python
class TestNegativeInvariants:
    """
    Constitution-grade negative tests.
    
    Invariant: mutate ANY owned key → detect() == CUSTOM
    """
    
    # --- Magnetism ---
    def test_negative_magnetism_mutate_nspin(self): ...
    def test_negative_magnetism_mutate_noncolin(self): ...
    def test_negative_magnetism_mutate_lspinorb(self): ...
    
    # --- OccupationsScheme ---
    def test_negative_occupations_mutate_occupations(self): ...
    def test_negative_occupations_mutate_smearing(self): ...
    
    # --- Precision ---
    def test_negative_precision_mutate_ecutwfc(self): ...
    def test_negative_precision_mutate_ecutrho(self): ...
    def test_negative_precision_mutate_conv_thr(self): ...
    def test_negative_precision_mutate_kpoints(self): ...
    
    # --- Convergence ---
    def test_negative_convergence_mutate_mixing_beta(self): ...
    def test_negative_convergence_mutate_electron_maxstep(self): ...
    def test_negative_convergence_mutate_mixing_mode(self): ...
    
    # --- QC Precision ---
    def test_negative_qc_precision_mutate_conv_tol(self): ...
    def test_negative_qc_precision_mutate_max_cycle(self): ...
```

### 3.3 Key Ownership Uniqueness Tests

**File**: `tests/unit/test_key_ownership_uniqueness.py` (enhance existing)

**Purpose**: Verify no duplicate key ownership across all registered ParamSpaces.

**Structure**:
```python
class TestKeyOwnershipUniqueness:
    """Verify key ownership is unique across all ParamSpaces."""
    
    def test_no_key_overlap_precision_occupations(self): ...
    def test_no_key_overlap_precision_magnetism(self): ...
    def test_no_key_overlap_precision_convergence(self): ...
    def test_no_key_overlap_all_dimensions(self): ...
    def test_degauss_owned_by_precision_not_occupations(self): ...
```

### 3.4 Capability Resolver Invariant Tests

**File**: `tests/unit/test_capability_resolver_invariants.py`

**Purpose**: Verify capability resolver SSOT and edge cases.

**Structure**:
```python
class TestCapabilityResolverInvariants:
    """Constitution-grade capability tests."""
    
    def test_engine_not_in_registry_raises_keyerror(self): ...
    def test_preset_not_in_supported_returns_empty(self): ...
    def test_preset_in_supported_but_not_applicable_returns_empty(self): ...
    def test_intersection_logic_correct(self): ...
    
    # ORCA binary-optional tests
    def test_orca_in_registry_without_binary(self): ...
    def test_orca_supported_presets_without_binary(self): ...
```

---

## 4. PR Checklist for Cursor Auto

### PR0: Create test infrastructure and helpers

**Scope**: Create shared fixtures and helpers for reversibility tests

**Files to Create/Modify**:
- `tests/unit/conftest.py` - Add shared fixtures for preset testing
- `tests/utils/preset_helpers.py` - Add helper functions

**Tasks**:
- [ ] Create `is_pyscf_available()` helper
- [ ] Create `is_orca_available()` helper (uses registry, not binary check)
- [ ] Create `build_test_step_yaml()` fixture factory
- [ ] Create `apply_and_detect_roundtrip()` helper function

**Tests to Run**:
```bash
pytest tests/unit/conftest.py -v  # Verify no import errors
```

**DONE**: [ ]

---

### PR1: Add roundtrip invariant tests for QE dimensions

**Scope**: Systematic roundtrip tests for magnetism, occupations_scheme, precision, convergence

**Files to Create**:
- `tests/unit/test_paramspace_roundtrip_invariants.py`

**Tasks**:
- [ ] Create TestRoundtripInvariants class
- [ ] Add magnetism roundtrip tests (NM, COL, NC, SOC)
- [ ] Add occupations_scheme roundtrip tests (FIXED, SMEARING, TETRAHEDRA)
- [ ] Add precision roundtrip tests (LOW, MED, HIGH) for scf and nscf
- [ ] Add convergence roundtrip tests (FAST, NORMAL, ROBUST, VERY_ROBUST)

**Tests to Run**:
```bash
pytest tests/unit/test_paramspace_roundtrip_invariants.py -v
```

**DONE**: [ ]

---

### PR2: Add negative invariant tests for QE dimensions

**Scope**: Tests that mutate one key and verify CUSTOM detection

**Files to Create**:
- `tests/unit/test_paramspace_negative_invariants.py`

**Tasks**:
- [ ] Create TestNegativeInvariants class
- [ ] Add magnetism negative tests (mutate nspin, noncolin, lspinorb)
- [ ] Add occupations_scheme negative tests (mutate occupations, smearing)
- [ ] Add precision negative tests (mutate ecutwfc, ecutrho, conv_thr, K_POINTS)
- [ ] Add convergence negative tests (mutate mixing_beta, electron_maxstep, mixing_mode)

**Tests to Run**:
```bash
pytest tests/unit/test_paramspace_negative_invariants.py -v
```

**DONE**: [ ]

---

### PR3: Add QC precision roundtrip and negative tests

**Scope**: Tests for qc_precision dimension (PySCF, ORCA)

**Files to Modify**:
- `tests/unit/test_paramspace_roundtrip_invariants.py` - Add QC tests
- `tests/unit/test_paramspace_negative_invariants.py` - Add QC tests

**Tasks**:
- [ ] Add qc_precision roundtrip tests for PySCF (LOW, MED, HIGH)
- [ ] Add qc_precision roundtrip tests for ORCA (skip if binary unavailable)
- [ ] Add qc_precision negative tests (mutate conv_tol, max_cycle)
- [ ] Verify ORCA tests skip cleanly without binary

**Tests to Run**:
```bash
pytest tests/unit/test_paramspace_roundtrip_invariants.py::*qc* -v
pytest tests/unit/test_paramspace_negative_invariants.py::*qc* -v
```

**DONE**: [ ]

---

### PR4: Add key ownership uniqueness tests

**Scope**: Verify no key overlap between ParamSpaces

**Files to Create/Modify**:
- `tests/unit/test_key_ownership_uniqueness.py`

**Tasks**:
- [ ] Create TestKeyOwnershipUniqueness class
- [ ] Test no overlap between all dimension pairs
- [ ] Test degauss owned by precision (not occupations)
- [ ] Test all canonical ParamSpaces registered successfully

**Tests to Run**:
```bash
pytest tests/unit/test_key_ownership_uniqueness.py -v
```

**DONE**: [ ]

---

### PR5: Add capability resolver invariant tests

**Scope**: Verify capability resolver edge cases and ORCA binary-optional

**Files to Create/Modify**:
- `tests/unit/test_capability_resolver_invariants.py`

**Tasks**:
- [ ] Create TestCapabilityResolverInvariants class
- [ ] Test engine not in registry → KeyError
- [ ] Test preset not in supported_presets → not in result
- [ ] Test preset in supported but not applicable → not in result
- [ ] Test ORCA in registry without binary
- [ ] Test ORCA supported_presets query without binary

**Tests to Run**:
```bash
pytest tests/unit/test_capability_resolver_invariants.py -v
```

**DONE**: [ ]

---

### PR6: Final verification and documentation update

**Scope**: Run full test suite and update spec

**Tasks**:
- [ ] Run full unit test suite: `pytest tests/unit/ -v`
- [ ] Verify no regressions
- [ ] Update `docs/dev/spec-dimension-variant-ownership-oracle.md` with new test references
- [ ] Add test file references to Evidence Pointers table

**Tests to Run**:
```bash
pytest tests/unit/ -v
pytest tests/integration/test_precision_roundtrip.py -v
```

**DONE**: [ ]

---

## 5. Stop Conditions for Auto

If any of the following occur, STOP and produce a forensic note:

1. **Import failure**: Module cannot be imported → investigate missing dependency
2. **Existing test breaks**: A test that was passing now fails → investigate cause
3. **Ownership conflict detected**: `RuntimeError` during ParamSpace registration → investigate key overlap
4. **More than 2 test failures in same PR**: Multiple unrelated failures → step back and analyze
5. **ORCA binary required unexpectedly**: Test should skip but crashes → investigate binary check

Do NOT try multiple speculative fixes. Document the failure and stop.

---

## 6. Acceptance Criteria

All of the following MUST pass:

- [ ] `pytest tests/unit/test_paramspace_roundtrip_invariants.py -v` - 100% pass
- [ ] `pytest tests/unit/test_paramspace_negative_invariants.py -v` - 100% pass
- [ ] `pytest tests/unit/test_key_ownership_uniqueness.py -v` - 100% pass
- [ ] `pytest tests/unit/test_capability_resolver_invariants.py -v` - 100% pass
- [ ] `pytest tests/unit/ -v` - No regressions
- [ ] ORCA tests skip cleanly when binary unavailable

---

**End of Plan**

