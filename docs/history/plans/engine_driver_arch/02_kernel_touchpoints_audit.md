# Kernel Touchpoints Audit

**Document Version**: 1.0
**Date**: 2026-01-20

---

## 1. Overview

This document audits every location where QMatSuite's "kernel" (engine-agnostic core) contains engine-specific logic. These are the integration touchpoints that must be refactored for the driver architecture.

**Severity Levels**:
- **CRITICAL**: Causes silent failures or cross-engine execution
- **HIGH**: Tight coupling that blocks clean migration
- **MEDIUM**: Duplicated logic that should be centralized
- **LOW**: Cosmetic or minor coupling

---

## 2. Critical Touchpoints

### 2.1 Engine Family Detection (CRITICAL)

**File**: `src/qmatsuite/core/calc_identity.py`
**Lines**: 78-116
**Severity**: CRITICAL

**Current Implementation**:
```python
def determine_engine_family(machine_type: str) -> set[str]:
    families = set()
    if machine_type.startswith("qe_") or machine_type.startswith("pw_"):
        families.add("qe")
    elif machine_type.startswith("vasp_"):
        families.add("vasp")
    elif machine_type.startswith("orca_"):
        families.add("orca")
    elif machine_type.startswith("pyscf_"):
        families.add("pyscf")
    elif machine_type.startswith("lammps_"):
        families.add("lammps")
    elif machine_type.startswith("cp2k_"):
        families.add("cp2k")
    elif machine_type.startswith("w90_"):
        families.add("w90")
    else:
        # CRITICAL VULNERABILITY
        families.add("qe")  # Silent fallback to QE
    return families
```

**Problem**:
- Any unknown step type silently routes to QE
- Typos in step types cause cross-engine execution
- New engines require modifying kernel code

**Required Fix**:
```python
def determine_engine_family(machine_type: str) -> str:
    spec = STEP_TYPE_REGISTRY.get(machine_type)
    if spec is None:
        raise UnknownStepTypeError(
            f"Step type '{machine_type}' is not registered. "
            f"Known types: {list(STEP_TYPE_REGISTRY.keys())}"
        )
    return spec.engine
```

---

### 2.2 Handler Dispatch Map (HIGH)

**File**: `src/qmatsuite/execution/handlers.py`
**Lines**: 1335-1342
**Severity**: HIGH

**Current Implementation**:
```python
def build_handler_map():
    return {
        "qe": make_handler(qe_step_handler),
        "pyscf": make_handler(pyscf_chain_handler),
        "orca": make_handler(orca_chain_handler),
        "vasp": make_handler(vasp_step_handler),
        "lammps": make_handler(lammps_step_handler),
        "cp2k": make_handler(cp2k_step_handler),
    }
```

**Problem**:
- Adding a new engine requires modifying this kernel file
- All handlers live in one 1400+ line file
- No validation that handlers exist for all registered engines

**Required Fix**:
- Drivers register their handlers during initialization
- Kernel validates all engines have handlers at startup

---

### 2.3 Recipe Selection Map (HIGH)

**File**: `src/qmatsuite/execution/recipes.py`
**Lines**: 798-827
**Severity**: HIGH

**Current Implementation**:
```python
def get_recipe_class(engine_family: str) -> type[BaseRecipe]:
    recipe_map = {
        "qe": QERecipe,
        "orca": ORCARecipe,
        "pyscf": PySCFRecipe,
        "vasp": VASPRecipe,
        "lammps": LAMMPSRecipe,
        "cp2k": CP2KRecipe,
    }
    return recipe_map.get(engine_family, QERecipe)  # Another QE fallback!
```

**Problem**:
- Same pattern as calc_identity - silent QE fallback
- All recipe classes in one 900+ line file
- Adding engine requires modifying kernel

**Required Fix**:
- Drivers provide their recipe class
- Explicit error if no recipe registered

---

### 2.4 MATERIALIZATION_MAP (HIGH)

**File**: `src/qmatsuite/workflow/generalized_steps.py`
**Lines**: 364-389
**Severity**: HIGH

**Current Implementation**:
```python
MATERIALIZATION_MAP = {
    ("qe", "GEN_SCF"): "pw_scf",
    ("qe", "GEN_RELAX"): "pw_relax",
    ("qe", "GEN_MD"): "pw_md",
    ("vasp", "GEN_SCF"): "vasp_scf",
    ("vasp", "GEN_RELAX"): "vasp_relax",
    ("orca", "GEN_SCF"): "orca_scf",
    ("orca", "GEN_RELAX"): "orca_opt",
    ("pyscf", "GEN_SCF"): "pyscf_scf",
    ("lammps", "GEN_RELAX"): "lammps_relax",
    ("lammps", "GEN_MD"): "lammps_md",
    ("cp2k", "GEN_SCF"): "cp2k_scf",
    ("cp2k", "GEN_RELAX"): "cp2k_relax",
    ("cp2k", "GEN_MD"): "cp2k_md",
}
```

**Problem**:
- Centralized map requires kernel modification for new engines
- No validation that target step types exist
- Generalized step support not declared by drivers

**Required Fix**:
- Drivers declare their materialization mappings
- Kernel aggregates from all registered drivers

---

## 3. High Severity Touchpoints

### 3.1 Step Type Sets in structure_steps.py (HIGH)

**File**: `src/qmatsuite/calculation/structure_steps.py`
**Lines**: 758-792
**Severity**: HIGH

**Current Implementation**:
```python
# Hardcoded sets duplicating registry information
PYSCF_STEP_TYPES = {"pyscf_scf", "pyscf_mp2", "pyscf_td", "pyscf_analysis", "pyscf_freq"}
ORCA_STEP_TYPES = {"orca_scf", "orca_hf", "orca_td", "orca_mp2", "orca_opt", "orca_freq"}
LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}
CP2K_STEP_TYPES = {"cp2k_scf", "cp2k_relax", "cp2k_md"}

# Then used in conditionals
is_pyscf_step = step_type_lower in PYSCF_STEP_TYPES or calculation_engine_family == "pyscf"
is_orca_step = step_type_lower in ORCA_STEP_TYPES or calculation_engine_family == "orca"
```

**Problem**:
- Duplicate source of truth (registry exists)
- Can diverge from registry
- New step types require updating multiple files

**Required Fix**:
```python
# Query registry directly
def is_engine_step(step_type: str, engine: str) -> bool:
    spec = STEP_TYPE_REGISTRY.get(step_type)
    return spec is not None and spec.engine == engine
```

---

### 3.2 Step Type Sets in step_done.py (HIGH)

**File**: `src/qmatsuite/calculation/step_done.py`
**Lines**: 145-175
**Severity**: HIGH

**Current Implementation**:
```python
VASP_STEP_TYPES = {"vasp_scf", "vasp_relax", "vasp_bands", "vasp_dos", "vasp_md"}
LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}

def determine_done_policy(step) -> DonePolicy:
    step_type = step.step_type
    if step_type in VASP_STEP_TYPES:
        return VASPDonePolicy()
    elif step_type in LAMMPS_STEP_TYPES:
        return LAMMPSDonePolicy()
    # ... etc
```

**Problem**:
- Same duplication issue as structure_steps.py
- Done policy selection embedded in kernel

**Required Fix**:
- Drivers declare their done policy class
- Kernel queries driver for done policy

---

### 3.3 Reference Resolver (VASP-Specific in Kernel) (HIGH)

**File**: `src/qmatsuite/execution/reference_resolver.py`
**Lines**: all
**Severity**: HIGH

**Current Implementation**:
```python
def find_reference_scf(steps: list, current_idx: int) -> tuple[int, Step]:
    """Find reference SCF step for CHGCAR/WAVECAR staging."""
    # VASP-specific logic embedded in kernel
    for i in range(current_idx - 1, -1, -1):
        step = steps[i]
        if step.step_type in ("vasp_scf", "vasp_relax"):
            return (i, step)
    raise NoReferenceSCFError(...)
```

**Problem**:
- File name suggests generic but logic is VASP-specific
- CHGCAR/WAVECAR are VASP artifacts
- Other engines have different reference patterns

**Required Fix**:
- Move to VASP driver bundle
- Kernel should not have artifact-specific resolvers

---

## 4. Medium Severity Touchpoints

### 4.1 Workdir Cleanup Decisions (MEDIUM)

**File**: `src/qmatsuite/execution/handlers.py`
**Lines**: 350-355 (VASP), 519-521 (LAMMPS)
**Severity**: MEDIUM

**Current Implementation**:
```python
# VASP: cleans workdir
if working_dir.exists():
    shutil.rmtree(working_dir)
working_dir.mkdir(parents=True, exist_ok=True)

# LAMMPS: accumulates (no cleanup)
working_dir.mkdir(parents=True, exist_ok=True)
```

**Problem**:
- Cleanup policy hardcoded per-engine in kernel
- New engine must remember to set correct policy

**Required Fix**:
- Drivers declare cleanup policy
- Kernel applies policy based on driver declaration

---

### 4.2 Artifact Pattern Matching (MEDIUM)

**File**: `src/qmatsuite/execution/relax_artifacts.py`
**Lines**: various
**Severity**: MEDIUM

**Current Implementation**:
```python
def find_trajectory_file(workdir: Path, engine: str) -> Path:
    if engine == "vasp":
        return workdir / "XDATCAR"
    elif engine == "lammps":
        return workdir / "trajectory.dump"
    elif engine == "cp2k":
        candidates = list(workdir.glob("cp2k_calc-pos-*.xyz"))
        return max(candidates, key=lambda p: p.stat().st_mtime)
    # ...
```

**Problem**:
- Artifact patterns hardcoded in kernel
- Each engine has different naming conventions

**Required Fix**:
- Drivers declare artifact patterns
- Kernel uses driver-provided patterns

---

### 4.3 Preflight Check Logic (MEDIUM)

**File**: `src/qmatsuite/execution/vasp_staging.py`
**Lines**: 45-65
**Severity**: MEDIUM

**Current Implementation**:
```python
# VASP-specific preflight
if not chgcar_src.exists():
    if is_current_scf:
        return  # Optional for SCF
    else:
        raise MissingArtifactError(...)
```

**Problem**:
- Preflight logic embedded in VASP-specific file
- Pattern should be generalizable

**Required Fix**:
- Drivers declare preflight requirements
- General preflight checker in kernel

---

## 5. Low Severity Touchpoints

### 5.1 Executable Discovery (LOW)

**File**: `src/qmatsuite/core/engines/`
**Severity**: LOW

**Current State**:
- Each engine has resolver in `core/engines/`
- Already relatively isolated

**Required Fix**:
- Move resolvers into driver bundles
- Minor refactoring only

---

### 5.2 Mock Engine Patterns in Tests (LOW)

**File**: `tests/fixtures/mock_engines/`
**Severity**: LOW

**Current State**:
- Mock engines for testing without binaries
- Well-isolated in test fixtures

**Required Fix**:
- Update mocks to implement driver interface
- Straightforward adaptation

---

## 6. Touchpoint Summary Matrix

| Touchpoint | File | Severity | Engines Affected | Fix Complexity |
|------------|------|----------|------------------|----------------|
| Engine family detection | `calc_identity.py` | CRITICAL | ALL | Low |
| Handler dispatch | `handlers.py` | HIGH | ALL | Medium |
| Recipe selection | `recipes.py` | HIGH | ALL | Medium |
| MATERIALIZATION_MAP | `generalized_steps.py` | HIGH | ALL | Medium |
| Step type sets | `structure_steps.py` | HIGH | 4 | Low |
| Step type sets | `step_done.py` | HIGH | 2 | Low |
| Reference resolver | `reference_resolver.py` | HIGH | VASP | Medium |
| Workdir cleanup | `handlers.py` | MEDIUM | VASP, LAMMPS | Low |
| Artifact patterns | `relax_artifacts.py` | MEDIUM | ALL | Medium |
| Preflight checks | `vasp_staging.py` | MEDIUM | VASP | Low |
| Executable discovery | `core/engines/` | LOW | ALL | Low |
| Test mocks | `tests/fixtures/` | LOW | ALL | Low |

---

## 7. Dependency Graph

```
                    ┌─────────────────────────┐
                    │     User Request        │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  calc_identity.py       │ ◄── CRITICAL: Engine detection
                    │  determine_engine_family│
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
┌───────────▼───────┐ ┌────────▼────────┐ ┌───────▼─────────┐
│  registry.py      │ │ generalized_    │ │ structure_      │
│  StepTypeSpec     │ │ steps.py        │ │ steps.py        │
│  lookup           │ │ MATERIALIZATION │ │ step type sets  │
└───────────┬───────┘ └────────┬────────┘ └───────┬─────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │     recipes.py          │ ◄── HIGH: Recipe selection
                    │     get_recipe_class    │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │     handlers.py         │ ◄── HIGH: Handler dispatch
                    │     build_handler_map   │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
┌───────────▼───────┐ ┌────────▼────────┐ ┌───────▼─────────┐
│  Engine-specific  │ │ relax_          │ │ step_done.py    │
│  staging files    │ │ artifacts.py    │ │ done policy     │
└───────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 8. Recommended Fix Order

### Phase 1: Stop the Bleeding (CRITICAL fixes)

1. **calc_identity.py**: Replace fallback with explicit error
2. **recipes.py**: Replace fallback with explicit error

### Phase 2: Centralize (HIGH fixes)

3. **structure_steps.py**: Query registry instead of hardcoded sets
4. **step_done.py**: Query registry instead of hardcoded sets
5. **generalized_steps.py**: Make MATERIALIZATION_MAP driver-provided

### Phase 3: Extract to Drivers (MEDIUM fixes)

6. **handlers.py**: Move handlers to driver bundles
7. **recipes.py**: Move recipes to driver bundles
8. **reference_resolver.py**: Move to VASP driver
9. **relax_artifacts.py**: Move patterns to drivers

### Phase 4: Cleanup (LOW fixes)

10. **core/engines/**: Move resolvers to drivers
11. **tests/fixtures/**: Update mocks for driver interface
