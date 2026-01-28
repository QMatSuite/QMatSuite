# Step-Type Mapping SSOT Audit

**Date**: 2026-01-28
**Status**: ✅ IMPLEMENTED
**Solution**: Option B - DriverRegistry as SSOT

---

## Implementation Summary

**COMPLETED**: The static `MATERIALIZATION_MAP` has been removed. Each driver now defines
its own `get_materialization_map()` method as the single source of truth (SSOT).

### Changes Made:
1. **Removed** static `MATERIALIZATION_MAP` from `generalized_steps.py`
2. **Expanded** driver materialization maps (QE, VASP, PySCF, ORCA, CP2K, W90, LAMMPS)
3. **Updated** `materialize_step()` to only use DriverRegistry
4. **Updated** helper functions (`_is_zero_mapping`, `get_supported_generalized_steps`, etc.)
5. **Added** `vasp_nscf` step type to VASP driver
6. **Added** `GEN_WANNIER` mapping to W90 driver
7. **Created** test gate at `tests/workflow/test_materialization_ssot.py`

### Test Results:
- 63 workflow tests passing
- 45 SSOT tests passing
- Round-trip consistency verified for all engines

---

## Original Analysis

The codebase previously had **two sources** for step-type mappings (GEN→SPEC):
1. Static `MATERIALIZATION_MAP` in `generalized_steps.py`
2. Dynamic driver `get_materialization_map()` registered in `DriverRegistry`

**Finding**: Significant drift existed between these sources. The static map was used as a **fallback** but contained mappings not present in drivers, and vice versa.

**Solution**: Consolidated to DriverRegistry as SSOT, deleted static map.

---

## Current Architecture

### Source 1: Static MATERIALIZATION_MAP

**Location**: `src/quantumvitas/workflow/generalized_steps.py:64-116`

```python
MATERIALIZATION_MAP: Dict[Tuple[str, str], Optional[str]] = {
    ("qe", "SCF"): "qe_scf",
    ("qe", "NSCF"): "qe_nscf",
    ("qe", "RELAX"): "qe_relax",
    ("qe", "VC_RELAX"): "qe_relax",  # Maps to same step type
    ...
    ("vasp", "SCF"): "vasp_scf",
    ...
}
```

**Key Format**: `(engine_family: str, gen_step: str)` → `machine_step_type: str | None`
- Uses UPPERCASE step names (e.g., "SCF", "RELAX")
- Does NOT use "GEN_" prefix

### Source 2: Driver get_materialization_map()

**Location**: Each driver in `src/quantumvitas/drivers/*/driver.py`

Example from VASP driver (`driver.py:136-148`):
```python
def get_materialization_map(self) -> dict[str, str]:
    return {
        "GEN_SCF": "vasp_scf",
        "GEN_RELAX": "vasp_relax",
        "GEN_VC_RELAX": "vasp_vc_relax",
        "GEN_MD": "vasp_md",
        "GEN_BANDS": "vasp_bands",
    }
```

**Key Format**: `gen_type: str` → `machine_step_type: str`
- Uses "GEN_" prefix (e.g., "GEN_SCF", "GEN_RELAX")
- Registered at import time via `DriverRegistry.register()`

### Consumer: materialize_step()

**Location**: `src/quantumvitas/workflow/generalized_steps.py:119-167`

**Flow**:
```
1. If input has "GEN_" prefix → try DriverRegistry.materialize_step_type()
2. If input lacks "GEN_" prefix → add "GEN_" prefix, try DriverRegistry
3. FALLBACK → use static MATERIALIZATION_MAP
```

This means the static map is a **fallback for backward compatibility**, not the primary source.

---

## Drift Analysis

### Mappings in Static Map but NOT in Drivers

| Engine | Gen Step | Machine Type | Driver Has? |
|--------|----------|--------------|-------------|
| qe | NSCF | qe_nscf | NO |
| qe | VC_RELAX | qe_relax | NO |
| qe | BANDS_POST | qe_bands | NO |
| qe | WANNIER_CONVERT | qe_pw2wannier90 | NO |
| qe | WANNIER | w90_run | NO |
| qe | PHONON | qe_ph | NO |
| qe | MD | qe_md | NO |
| qe | VC_MD | qe_vc_md | NO |
| qe | CUSTOM | qe_custom | NO |
| pyscf | TD | pyscf_td | NO |
| orca | HF | orca_hf | NO |
| orca | TD | orca_td | NO |
| vasp | NSCF | vasp_nscf | NO |
| cp2k | VC_RELAX | cp2k_relax | NO |
| cp2k | VC_MD | cp2k_md | NO |

### Mappings in Drivers but NOT in Static Map

| Engine | Gen Type | Machine Type | Static Has? |
|--------|----------|--------------|-------------|
| vasp | GEN_VC_RELAX | vasp_vc_relax | NO |
| lammps | GEN_NVT | lammps_nvt | NO |
| lammps | GEN_NPT | lammps_npt | NO |
| lammps | GEN_MINIMIZE | lammps_minimize | NO |
| cp2k | GEN_OPT | cp2k_geo_opt | NO |
| cp2k | GEN_CELL_OPT | cp2k_cell_opt | NO |
| pyscf | GEN_DFT | pyscf_dft | NO |
| pyscf | GEN_OPT | pyscf_opt | NO |
| pyscf | GEN_FREQ | pyscf_freq | NO |

### Key Format Inconsistency

Static map: `("qe", "SCF")` - tuple key, no prefix
Driver map: `"GEN_SCF"` - string key with prefix

This makes it impossible to directly compare or validate consistency.

---

## Third Registry: StepTypeRegistry

**Location**: `src/quantumvitas/workflow/registry.py`

Contains `_STEP_TYPES` dict with `StepTypeSpec` definitions. This is a **separate concern** (step metadata, not GEN→SPEC mapping), but introduces a third place where step types are defined.

**Observation**: StepTypeRegistry defines step type **semantics** (consumes_state, produces_state, is_structure_transform), while MATERIALIZATION_MAP/DriverRegistry defines **mappings**.

---

## Recommendation: Option B - DriverRegistry as SSOT

### Rationale

1. **Driver-local Knowledge**: Each driver knows its own step types and mappings
2. **Dynamic Registration**: DriverRegistry already handles registration at import time
3. **Single Source**: Eliminates drift by having one authoritative source
4. **Testable**: Can validate mappings at registration time

### Implementation Plan

#### Phase 1: Enhance Driver Materialization Maps

For each driver, add all missing mappings:

```python
# QE driver.py
def get_materialization_map(self) -> dict[str, str]:
    return {
        "GEN_SCF": "qe_scf",
        "GEN_NSCF": "qe_nscf",
        "GEN_RELAX": "qe_relax",
        "GEN_VC_RELAX": "qe_relax",  # Maps to same
        "GEN_BANDS": "qe_bands_pw",
        "GEN_BANDS_POST": "qe_bands",
        "GEN_DOS": "qe_dos",
        "GEN_WANNIER_CONVERT": "qe_pw2wannier90",
        "GEN_WANNIER": "w90_run",
        "GEN_PHONON": "qe_ph",
        "GEN_MD": "qe_md",
        "GEN_VC_MD": "qe_vc_md",
        "GEN_CUSTOM": "qe_custom",
    }
```

#### Phase 2: Update materialize_step()

Remove fallback to static map:

```python
def materialize_step(
    generalized_step: str,
    engine_family: str,
) -> Optional[str]:
    """Materialize a generalized step to an engine-specific step type."""
    import quantumvitas.drivers

    # Normalize to GEN_ format
    gen_type = generalized_step.upper()
    if not gen_type.startswith("GEN_"):
        gen_type = f"GEN_{gen_type}"

    try:
        return DriverRegistry.materialize_step_type(engine_family, gen_type)
    except (UnknownMaterializationError, UnknownEngineError):
        return None
```

#### Phase 3: Delete Static MATERIALIZATION_MAP

Remove lines 64-116 from `generalized_steps.py`.

#### Phase 4: Add Test Gate

Create test that validates all mappings at import time:

```python
# tests/workflow/test_materialization_ssot.py
def test_driver_materialization_completeness():
    """Ensure all expected GEN types are mapped by drivers."""
    expected_gen_types = {
        "qe": ["GEN_SCF", "GEN_NSCF", "GEN_RELAX", ...],
        "vasp": ["GEN_SCF", "GEN_RELAX", "GEN_BANDS", ...],
        ...
    }

    for engine, gen_types in expected_gen_types.items():
        driver = DriverRegistry.get_driver(engine)
        mat_map = driver.get_materialization_map()
        for gen_type in gen_types:
            assert gen_type in mat_map, f"{engine} missing {gen_type}"

def test_no_orphan_mappings():
    """Ensure all mapped step types are registered."""
    for engine in DriverRegistry.get_all_engines():
        driver = DriverRegistry.get_driver(engine)
        mat_map = driver.get_materialization_map()
        for gen_type, machine_type in mat_map.items():
            assert DriverRegistry.is_step_type_registered(machine_type), \
                f"Orphan mapping: {gen_type} -> {machine_type} (not registered)"
```

---

## Alternative: Option A - Static Map as SSOT

### Approach
Keep static MATERIALIZATION_MAP, delete driver `get_materialization_map()`.

### Drawbacks
1. Drivers don't control their own mappings
2. Adding new engine requires modifying central file
3. Goes against "driver encapsulation" principle

**NOT RECOMMENDED**

---

## Alternative: Option C - Validation-Only

### Approach
Keep both sources, add test that validates they match.

### Drawbacks
1. Maintains redundancy
2. Still requires manual sync
3. Doesn't solve the root cause

**NOT RECOMMENDED** (only if migration is too risky)

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/quantumvitas/drivers/qe/driver.py` | Expand `get_materialization_map()` |
| `src/quantumvitas/drivers/vasp/driver.py` | Add NSCF mapping |
| `src/quantumvitas/drivers/pyscf/driver.py` | Add TD mapping |
| `src/quantumvitas/drivers/orca/driver.py` | Add HF, TD mappings |
| `src/quantumvitas/drivers/lammps/driver.py` | Already complete |
| `src/quantumvitas/drivers/cp2k/driver.py` | Add VC_RELAX, VC_MD mappings |
| `src/quantumvitas/workflow/generalized_steps.py` | Remove static map, update `materialize_step()` |
| `tests/workflow/test_materialization_ssot.py` | New test file |

---

## Cursor Auto Implementation Steps

```markdown
## Step 1: Update QE Driver Materialization Map
File: src/quantumvitas/drivers/qe/driver.py
Task: Expand get_materialization_map() to include all QE step types

## Step 2: Update VASP Driver Materialization Map
File: src/quantumvitas/drivers/vasp/driver.py
Task: Add GEN_NSCF mapping

## Step 3: Update PySCF Driver Materialization Map
File: src/quantumvitas/drivers/pyscf/driver.py
Task: Add GEN_TD, GEN_RELAX mappings

## Step 4: Update ORCA Driver Materialization Map
File: src/quantumvitas/drivers/orca/driver.py
Task: Add GEN_HF, GEN_TD, GEN_RELAX mappings

## Step 5: Update CP2K Driver Materialization Map
File: src/quantumvitas/drivers/cp2k/driver.py
Task: Add GEN_VC_RELAX, GEN_VC_MD mappings (map to cp2k_relax, cp2k_md)

## Step 6: Update materialize_step() Function
File: src/quantumvitas/workflow/generalized_steps.py
Task: Remove fallback to static MATERIALIZATION_MAP

## Step 7: Delete Static MATERIALIZATION_MAP
File: src/quantumvitas/workflow/generalized_steps.py
Task: Remove lines 64-116 (the static dict)

## Step 8: Update Helper Functions
File: src/quantumvitas/workflow/generalized_steps.py
Task: Update _is_zero_mapping(), get_supported_generalized_steps(),
      get_engine_families_for_step() to query DriverRegistry instead

## Step 9: Add SSOT Test Gate
File: tests/workflow/test_materialization_ssot.py (new)
Task: Create test that validates driver mappings completeness

## Step 10: Run Test Suite
Command: pytest tests/workflow/ -v
Task: Verify all tests pass
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missing mapping causes runtime error | Medium | High | Test gate catches at import |
| Backward compatibility break | Low | Medium | All existing mappings preserved in drivers |
| Third-party drivers affected | Low | Low | Protocol unchanged, just consolidation |

---

## Appendix: Current Driver Materialization Maps

### QE (needs expansion)
```python
"GEN_SCF": "qe_scf",
"GEN_RELAX": "qe_relax",
"GEN_BANDS": "qe_bands_pw",
"GEN_DOS": "qe_dos",
```

### VASP (needs NSCF)
```python
"GEN_SCF": "vasp_scf",
"GEN_RELAX": "vasp_relax",
"GEN_VC_RELAX": "vasp_vc_relax",
"GEN_MD": "vasp_md",
"GEN_BANDS": "vasp_bands",
```

### PySCF (needs TD, RELAX)
```python
"GEN_SCF": "pyscf_scf",
"GEN_DFT": "pyscf_dft",
"GEN_OPT": "pyscf_opt",
"GEN_FREQ": "pyscf_freq",
"GEN_MP2": "pyscf_mp2",
```

### ORCA (needs HF, TD, RELAX, TDDFT, MP2, CCSD, CASSCF, NEVPT2)
```python
# Current (incomplete):
"GEN_SCF": "orca_scf",
"GEN_OPT": "orca_opt",
"GEN_FREQ": "orca_freq",
"GEN_SP": "orca_sp",

# Missing (step types exist but no GEN mapping):
# "GEN_HF": "orca_hf",
# "GEN_TD": "orca_td",
# "GEN_RELAX": "orca_relax",
# "GEN_TDDFT": "orca_tddft",
# "GEN_MP2": "orca_mp2",
# "GEN_CCSD": "orca_ccsd",
# "GEN_CASSCF": "orca_casscf",
# "GEN_NEVPT2": "orca_nevpt2",
```

### LAMMPS (complete)
```python
"GEN_MINIMIZE": "lammps_minimize",
"GEN_MD": "lammps_md",
"GEN_RELAX": "lammps_relax",
"GEN_NVT": "lammps_nvt",
"GEN_NPT": "lammps_npt",
```

### CP2K (needs VC_RELAX, VC_MD)
```python
"GEN_SCF": "cp2k_scf",
"GEN_RELAX": "cp2k_relax",
"GEN_OPT": "cp2k_geo_opt",
"GEN_CELL_OPT": "cp2k_cell_opt",
"GEN_MD": "cp2k_md",
"GEN_BANDS": "cp2k_bands",
"GEN_DOS": "cp2k_dos",
```
