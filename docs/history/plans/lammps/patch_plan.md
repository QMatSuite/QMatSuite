# LAMMPS Integration Patch Plan

## Overview

This document provides a detailed, executable patch plan to fix the 5 failing tests and align Auto's implementation with the final specification.

**Failing Tests:**
1. `test_all_keys_are_spec_step_types` - `lammps_minimize` not in allowed prefixes
2. `test_spec_type_preserved_in_registry` - `lammps_md` not in allowed prefixes
3. `test_lammps_lj_minimize.py` - `Project.from_directory()` doesn't exist
4. `test_lammps_eam_md.py` - `Project.from_directory()` doesn't exist
5. `test_lammps_chain.py` - `Project.from_directory()` doesn't exist

---

## Key Questions Answered

### Q1: Should `lammps_minimize` be renamed to `lammps_relax`, or kept as legacy alias?

**Answer: RENAME to `lammps_relax`**

Rationale:
- The final specification explicitly states: "Machine/SPEC step types: `lammps_relax` and `lammps_md`"
- `minimize` is LAMMPS-internal terminology; QMatSuite uses engine-agnostic GEN types
- Other engines use `qe_relax`, `orca_relax`, `pyscf_relax` - consistency requires `lammps_relax`
- No backward compatibility needed (LAMMPS integration is new, no deployed users)

If legacy alias is needed later:
```python
# NOT RECOMMENDED for initial release
"lammps_minimize": StepTypeSpec(
    id="relax",
    machine_type="lammps_minimize",
    public_type="relax",
    engine="lammps",
    deprecated=True,  # Add deprecation flag
    canonical="lammps_relax",  # Point to canonical
)
```

**For this patch: Delete `lammps_minimize` entirely, replace with `lammps_relax`.**

---

### Q2: How should SPEC prefix validation be updated?

**Answer: Extend the allowed prefix list to include `lammps_`**

Two approaches considered:

**Option A: Extend hardcoded list (CHOSEN - minimal change)**
```python
valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_", "lammps_")
```

**Option B: Derive from registry (better long-term)**
```python
from quantumvitas.workflow.registry import get_registry
valid_prefixes = tuple(f"{e}_" for e in get_registry().list_engines())
```

**For this patch: Use Option A (minimal change). Create a follow-up issue for Option B.**

---

### Q3: What is the correct integration test API pattern?

**Answer: Use `QVService` API, not manual directory construction**

**Correct Pattern (from `test_vasp_project_e2e.py`):**
```python
from quantumvitas.api import QVService
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation

# 1. Create project
project_root = QVService.init_project(target_dir=tmp_path / "project", name="LAMMPS Test")

# 2. Create structure file (pymatgen Structure/Molecule)
from pymatgen.core import Structure, Lattice
struct = Structure(Lattice.cubic(3.6), ["Cu"] * 4, [[0,0,0], [0.5,0.5,0], [0.5,0,0.5], [0,0.5,0.5]])
structures_dir = project_root / "structures"
structures_dir.mkdir(exist_ok=True)
struct_file = structures_dir / "cu_fcc.json"
struct_file.write_text(json.dumps(struct.as_dict()))

# 3. Import structure (or register manually)
struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC")
structure_id = struct_result.meta.id

# 4. Create calculation
calc_resolved = QVService.init_calculation(
    project_root=project_root,
    name="test_calc",
    structure_selector=structure_id,
)
calc_id = calc_resolved.meta.id
calc_dir = calc_resolved.absolute_path

# 5. Configure engine_family
calc_data_path = calc_dir / "calculation.yaml"
calc_model = load_calculation(calc_data_path, project_root=project_root)
calc_model.engine_family = "lammps"
calc_doc = CalcDoc(calc_model.to_dict())
save_yaml_doc(calc_doc, calc_data_path)

# 6. Create step
step_resolved = QVService.init_step(
    project_root=project_root,
    calculation_selector=calc_id,
    step_type="relax",  # or "md"
)
step_id = step_resolved.meta.id

# 7. Configure step parameters
QVService.configure_step(
    project_root=project_root,
    calculation_selector=calc_id,
    step_selector=step_id,
    parameters={...},
)

# 8. Run
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.calculation.runner import CalculationRunner

registry = create_default_registry(include_lammps=True)
runner = CalculationRunner(engine_registry=registry)

# Load calculation from disk (as runner expects)
from quantumvitas.calculation.calculation import Calculation
calculation = Calculation.from_yaml(calc_data_path, project=project_root)
result = runner.run(calculation)
```

**Key API Entry Points:**
| API | Purpose | Location |
|-----|---------|----------|
| `QVService.init_project()` | Create project | `src/quantumvitas/api.py` |
| `QVService.import_structure()` | Import structure file | `src/quantumvitas/api.py` |
| `QVService.init_calculation()` | Create calculation | `src/quantumvitas/api.py` |
| `QVService.init_step()` | Add step to calculation | `src/quantumvitas/api.py` |
| `QVService.configure_step()` | Set step parameters | `src/quantumvitas/api.py` |
| `CalculationRunner.run()` | Execute calculation | `src/quantumvitas/calculation/runner.py` |

---

### Q4: Should `lammps_restart` be deleted?

**Answer: YES, delete it**

Rationale:
- The specification states: "`restart_from` is an upstream artifact reference, not a public step type"
- `restart_from` should be a **parameter** on `lammps_md`, not a separate step type
- Other engines (QE, VASP) use `restart_from` parameter pattern, not separate step types

**Implementation:**
- Delete `lammps_restart` from `_STEP_TYPES`
- The `restart_from` parameter is already handled in `lammps_engine.py` materialize logic
- Update tests that reference `lammps_restart`

---

## Patch Plan (2 PRs)

### PR 1: Fix Step Type Registry and SPEC Prefix Validation

**Goal:** Make unit tests pass

**Files to Change:**

#### 1.1 `src/quantumvitas/workflow/registry.py`

```diff
# Lines 545-556: Rename lammps_minimize → lammps_relax
- "lammps_minimize": StepTypeSpec(
+ "lammps_relax": StepTypeSpec(
      id="relax",
-     machine_type="lammps_minimize",
+     machine_type="lammps_relax",
      public_type="relax",
      engine="lammps",
      ...
  ),

# Lines 568-578: DELETE lammps_restart entirely
- "lammps_restart": StepTypeSpec(
-     id="restart_md",
-     machine_type="lammps_restart",
-     public_type="restart_md",
-     engine="lammps",
-     ...
- ),
```

#### 1.2 `tests/unit/test_step_type_mapping.py`

```diff
# Line 23
- valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_")
+ valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_", "lammps_")

# Line 128
- valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_")
+ valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_", "lammps_")
```

#### 1.3 `src/quantumvitas/engine/lammps_writer.py`

```diff
# Line 61: Update docstring
- step_type: Machine step type (e.g., "lammps_minimize", "lammps_md")
+ step_type: Machine step type (e.g., "lammps_relax", "lammps_md")

# Line 66: Update condition
- if step_type == "lammps_minimize":
+ if step_type == "lammps_relax":
```

#### 1.4 `src/quantumvitas/execution/lammps_relax_handler.py`

```diff
# Line 31: Update docstring
- step_type: Machine step type (e.g., "lammps_minimize")
+ step_type: Machine step type (e.g., "lammps_relax")
```

#### 1.5 `tests/unit/test_lammps_engine.py`

```diff
# Lines 72-80: Rename test and update assertions
- def test_lammps_minimize_registered(self):
-     """Test lammps_minimize step type is registered."""
-     spec = registry.get("lammps_minimize")
-     assert spec.machine_type == "lammps_minimize"
+ def test_lammps_relax_registered(self):
+     """Test lammps_relax step type is registered."""
+     spec = registry.get("lammps_relax")
+     assert spec.machine_type == "lammps_relax"

# Lines 91-98: DELETE entire test_lammps_restart_registered method
- def test_lammps_restart_registered(self):
-     """Test lammps_restart step type is registered."""
-     ...

# Lines 103-107: Update list test
- assert "lammps_minimize" in lammps_types
- assert "lammps_restart" in lammps_types
+ assert "lammps_relax" in lammps_types
+ # lammps_restart should NOT be in list (it's deleted)
```

#### 1.6 `tests/unit/test_lammps_writer.py`

```diff
# Line 19: Update step type in test data
- "step_type": "lammps_minimize",
+ "step_type": "lammps_relax",

# Line 65: Update assertion
- assert get_template_for_step_type("lammps_minimize") == "minimize.in.j2"
+ assert get_template_for_step_type("lammps_relax") == "minimize.in.j2"

# Line 67: DELETE or update lammps_restart assertion
- assert get_template_for_step_type("lammps_restart") == "md_nvt.in.j2"
```

**Verification Command:**
```bash
pytest tests/unit/test_step_type_mapping.py tests/unit/test_lammps_*.py -v --tb=short
```

**Rollback Point:** Git commit before PR 1

---

### PR 2: Fix Integration Tests to Use Service API

**Goal:** Make integration tests pass

**Files to Change:**

#### 2.1 `tests/integration/test_lammps_lj_minimize.py`

Complete rewrite using Service API pattern:

```python
"""
Integration test for LAMMPS LJ minimize workflow.
"""
import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation


@pytest.fixture
def lj_project(tmp_path: Path):
    """Create a LAMMPS project using Service API."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    
    try:
        resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS not installed")
    
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "lj_project",
        name="LJ Minimize Test"
    )
    
    # Create LJ structure (simple cubic or FCC)
    from pymatgen.core import Structure, Lattice
    lattice = Lattice.cubic(5.0)
    structure = Structure(
        lattice,
        ["Ar"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    structures_dir = project_root / "structures"
    structures_dir.mkdir(exist_ok=True)
    struct_file = structures_dir / "ar_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    struct_result = QVService.import_structure(project_root, struct_file, name="Ar FCC")
    structure_id = struct_result.meta.id
    
    # Create calculation
    calc_resolved = QVService.init_calculation(
        project_root=project_root,
        name="lj_minimize",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.id
    calc_dir = calc_resolved.absolute_path
    
    # Configure as LAMMPS
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create relax step
    step_resolved = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="relax",
    )
    
    # Configure step parameters
    QVService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=step_resolved.meta.id,
        parameters={
            "units": "lj",
            "atom_style": "atomic",
            "potential": {
                "style": "lj/cut",
                "cutoff": 2.5,
                "params": {"1 1": "1.0 1.0"},
            },
            "energy_tolerance": 1e-6,
            "force_tolerance": 1e-8,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_path": calc_path,
    }


@pytest.mark.requires_lammps
def test_lj_minimize_workflow(lj_project):
    """Test LJ minimize workflow end-to-end."""
    project_root = lj_project["project_root"]
    calc_path = lj_project["calc_path"]
    
    # Load and run
    from quantumvitas.project.model import Project
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_path, project)
    
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Failed: {result}"
    print("✓ LJ minimize workflow completed")
```

#### 2.2 `tests/integration/test_lammps_eam_md.py`

Similar rewrite using Service API pattern (with EAM potential staging).

#### 2.3 `tests/integration/test_lammps_chain.py`

Similar rewrite using Service API pattern (with multiple steps).

**Key Changes:**
- Replace `Project.from_directory()` with `Project.open()` (exists)
- Use `QVService.init_project()` to create proper project structure
- Use `QVService.init_calculation()` and `QVService.init_step()` to create resources
- Use `QVService.configure_step()` to set parameters
- Load calculation properly before running

**Verification Command:**
```bash
pytest tests/integration/test_lammps_*.py -v --tb=short -m requires_lammps
```

**Rollback Point:** Git commit before PR 2

---

## Verification Matrix

| PR | Test Command | Expected Result |
|----|--------------|-----------------|
| PR 1 | `pytest tests/unit/test_step_type_mapping.py -v` | All pass |
| PR 1 | `pytest tests/unit/test_lammps_*.py -v` | All pass |
| PR 2 | `pytest tests/integration/test_lammps_*.py -v` | All pass (with LAMMPS) |
| Both | `pytest tests/ -v --tb=short -n auto` | No regressions |

---

## Documentation Updates

After both PRs, update:

1. `docs/engines/lammps/integration_design.md` - Replace `lammps_minimize` with `lammps_relax`, remove `lammps_restart`
2. `docs/engines/lammps/workflows.md` - Update step type references
3. `docs/engines/lammps/codebase_review_notes.md` - Update step type references
4. `docs/plan/lammps/implementation_plan.md` - Mark patches as complete

**Specific doc changes:**
```bash
# Find and replace in docs
grep -r "lammps_minimize" docs/engines/lammps/ | wc -l  # Should become 0
grep -r "lammps_restart" docs/engines/lammps/ | wc -l   # Should become 0
```

---

## Summary

| Change | Files | Risk |
|--------|-------|------|
| Rename `lammps_minimize` → `lammps_relax` | 6 files | Low |
| Delete `lammps_restart` | 2 files | Low |
| Add `lammps_` prefix to validation | 1 file | Low |
| Rewrite integration tests | 3 files | Medium |

**Total Estimated Effort:** 1-2 hours

