# LAMMPS restart/chain CI Fix: Implementation Plan

**Date**: 2026-01-19  
**Author**: Review Agent  
**For**: Auto to implement  
**Prerequisites**: Read `lammps_restart_ci_review.md` first

---

## Overview

This plan addresses the Ubuntu CI regression where `test_workflow_d_restart` and `test_chain_workflow` fail with "No restart artifact found". The fix is split into 2 PRs for minimal blast radius.

---

## PR1: Add Output Artifact Verification (Core Fix)

### Goal
Ensure LAMMPS handler verifies expected output artifacts exist before declaring success.

### Files to Modify

#### 1. `src/qmatsuite/execution/handlers.py`

**Location**: `lammps_step_handler()` function, after line 532

**Current Code** (line 530-540):
```python
success = result.success if hasattr(result, "success") else False
error_msg = result.error if hasattr(result, "error") and not success else None

# Build step result with capability-based relax artifact spec
step_result_data = {
    "success": success,
    ...
}
```

**Required Change**: Add output verification BEFORE building step_result_data

**New Code** (insert after line 532, before line 534):
```python
success = result.success if hasattr(result, "success") else False
error_msg = result.error if hasattr(result, "error") and not success else None

# Verify expected output artifacts exist (fixes Ubuntu CI race condition)
if success:
    public_type = job.metadata.get("public_type")
    
    # Relax steps must produce final.data
    if public_type == "relax":
        final_data_path = working_dir / "final.data"
        if not final_data_path.exists():
            success = False
            error_msg = (
                f"Relax step completed but final.data not found in {working_dir}. "
                f"Contents: {list(working_dir.iterdir()) if working_dir.exists() else 'dir missing'}"
            )
            logger.error(f"[LAMMPS_HANDLER] {error_msg}")
    
    # MD steps should produce restart.bin (or restart.*.bin)
    elif public_type == "md":
        restart_patterns = list(working_dir.glob("restart*.bin"))
        log_file = working_dir / "log.lammps"
        # Only fail if no restart file AND log indicates completion
        if not restart_patterns and log_file.exists():
            # Check if LAMMPS completed normally (log should have timing info)
            log_content = log_file.read_text()
            if "Total wall time" in log_content or "Loop time" in log_content:
                # LAMMPS completed but no restart file - this is OK for short runs
                # but log it for debugging
                logger.warning(
                    f"[LAMMPS_HANDLER] MD step completed but no restart.bin found in {working_dir}. "
                    f"This may affect downstream restart_from steps."
                )

# Build step result with capability-based relax artifact spec
step_result_data = {
    ...
```

**Rationale**: 
- For `relax` steps, `final.data` is required for downstream `restart_from`
- For `md` steps, `restart.bin` is optional (depends on LAMMPS config) but warn if missing

### 2. `src/qmatsuite/calculation/step_done.py`

**Add LAMMPS step type handling** to `is_step_done()` function.

**Location**: After line 158 (after VASP handling), before line 160

**Add Code**:
```python
    # LAMMPS steps: check for log.lammps and step-specific outputs
    LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md", "lammps_restart"}
    if step_kind_lower in LAMMPS_STEP_TYPES:
        # LAMMPS uses isolated workdirs: calc_raw_dir / step_ulid / log.lammps
        step_ulid = None
        if step_doc:
            meta = step_doc.get("meta", {})
            step_ulid = meta.get("id") or step_doc.get("step_id")
        
        if step_ulid:
            step_workdir = calc_raw_dir / step_ulid
            log_path = step_workdir / "log.lammps"
        else:
            # Fallback: look in calc_raw_dir root
            log_path = calc_raw_dir / "log.lammps"
            step_workdir = calc_raw_dir
        
        if not log_path.exists():
            logger.debug(f"Step {step_kind}: LAMMPS log file not found at {log_path}")
            return False
        
        # Check log for completion markers
        try:
            log_content = log_path.read_text()
            # LAMMPS prints timing info at end of successful run
            if "Total wall time" in log_content or "Loop time" in log_content:
                # For relax, also check final.data exists
                if step_kind_lower == "lammps_relax":
                    final_data = step_workdir / "final.data"
                    if not final_data.exists():
                        logger.debug(f"Step {step_kind}: final.data not found")
                        return False
                logger.debug(f"Step {step_kind}: LAMMPS completed successfully")
                return True
            else:
                logger.debug(f"Step {step_kind}: LAMMPS log incomplete (no timing info)")
                return False
        except Exception as e:
            logger.warning(f"Step {step_kind}: Error reading log: {e}")
            return False
```

### Verification Commands

```bash
# Run specific failing tests
source .venv/bin/activate
python -m pytest tests/integration/test_lammps_chain.py::test_chain_workflow -v --tb=short

python -m pytest tests/integration/test_lammps_long_smoke.py::test_workflow_d_restart -v --tb=short

# Run all LAMMPS tests
python -m pytest tests/integration/test_lammps*.py -v --tb=short

# Full regression test
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Expected Outcome
- Tests should pass on both Mac and Ubuntu
- If LAMMPS fails to produce artifacts, error message clearly indicates what's missing
- Debug logging helps identify filesystem timing issues

---

## PR2: Add restart_from Explicit Dependency Edges (Hardening)

### Goal
Make `restart_from` an explicit edge in JobGraph so future parallelization won't break.

### Files to Modify

#### 1. `src/qmatsuite/execution/recipes.py`

**Location**: `LAMMPSRecipe.materialize()` function, modify dependency logic

**Current Code** (lines 410-414):
```python
# Fingerprint
step_sha = self._get_step_sha(step, step_shas)
fingerprint = step_sha if step_sha else None

# Dependencies: linear (each step depends on previous)
deps = []
if len(jobs) > 0:
    deps = [jobs[-1].id]
```

**New Code** (replace):
```python
# Fingerprint
step_sha = self._get_step_sha(step, step_shas)
fingerprint = step_sha if step_sha else None

# Dependencies: include restart_from if present
deps = []

# Linear dependency on previous job (conservative)
if len(jobs) > 0:
    deps = [jobs[-1].id]

# Explicit restart_from dependency (artifact-based)
# This ensures downstream step waits for upstream artifact
step_params = step.parameters if hasattr(step, "parameters") else {}
if not step_params:
    # Try to load from step spec
    from qmatsuite.calculation.structure_steps import StructureStepSpec
    from qmatsuite.core.resolution import require_step
    try:
        step_ulid = step.meta.id
        # Get step file path
        # Note: This is a temporary workaround; proper fix would pass params through
        pass
    except Exception:
        pass

restart_from = step_params.get("restart_from") if step_params else None
if restart_from:
    # Find the job that contains the restart_from step
    for existing_job in jobs:
        if restart_from in existing_job.step_ids:
            if existing_job.id not in deps:
                deps.append(existing_job.id)
            break
    else:
        # restart_from references a step not yet in jobs list
        # This is unusual but could happen with non-linear topologies
        # Log for debugging
        import logging
        logging.getLogger(__name__).warning(
            f"restart_from={restart_from} references step not in current jobs"
        )
```

**Note**: This is a best-effort enhancement. The step parameters may not be available at recipe time (they're loaded later in handler). If this proves too complex, focus on PR1 which is the actual fix.

#### 2. Add Integration Test for Parallel Safety

**New File**: `tests/integration/test_lammps_restart_parallel.py`

```python
"""
Test LAMMPS restart/chain workflows are parallel-safe.

These tests verify that restart_from dependencies work correctly
even under pytest-xdist parallel execution.
"""

import json
import pytest
import shutil
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.calculation.calculation import Calculation
from qmatsuite.calculation.runner import CalculationRunner
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.project.model import Project
from qmatsuite.core.yaml_io import save_yaml_doc
from qmatsuite.core.yamldoc import CalcDoc
from qmatsuite.core.models import load_calculation
from qmatsuite.core.pseudo_provenance import compute_sha256_file


def get_lammps_binary():
    """Check LAMMPS availability."""
    from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin
    try:
        return resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS binary not found")


@pytest.mark.parametrize("execution_number", range(3))
def test_restart_chain_parallel_safe(tmp_path: Path, execution_number: int):
    """
    Test restart chain is deterministic across parallel executions.
    
    This test is parameterized to run 3 times in parallel with pytest-xdist.
    Each execution should produce identical results.
    """
    lammps_bin = get_lammps_binary()
    
    # Use unique subdir for each execution
    project_dir = tmp_path / f"parallel_test_{execution_number}"
    
    # Create project
    project_root = QMSService.init_project(
        target_dir=project_dir,
        name=f"Parallel Test {execution_number}"
    )
    
    # Create minimal Cu structure
    from pymatgen.core import Structure, Lattice
    lattice = Lattice.cubic(3.6)
    structure = Structure(
        lattice,
        ["Cu"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    struct_file = project_dir / "cu_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QMSService.import_structure(project_root, struct_file, name="Cu FCC")
    structure_id = struct_result.meta.id
    
    # Copy potential file
    repo_root = Path(__file__).parent.parent.parent
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    potential_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QMSService.init_calculation(
        project_root=project_root,
        name="parallel_test",
        structure_selector=structure_id,
    )
    calc_id = calc_result.meta.id
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    calc_model.species_map = {}
    calc_model.potential_map = {
        "eam_cu": {
            "style": "eam",
            "file": "potentials/Cu_u3.eam",
            "elements": ["Cu"],
            "sha256": potential_sha,
        }
    }
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create relax step
    relax_step = QMSService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="relax",
    )
    relax_step_id = relax_step.meta.id
    
    QMSService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=relax_step_id,
        parameters={
            "potential": "eam_cu",
            "units": "metal",
            "atom_style": "atomic",
            "energy_tolerance": 1e-4,
            "force_tolerance": 1e-6,
            "thermo_frequency": 100,
            "dump_frequency": 500,
            "dump_trajectory": True,
        },
    )
    
    # Create MD step with restart_from
    md_step = QMSService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="md",
    )
    md_step_id = md_step.meta.id
    
    QMSService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": relax_step_id,  # KEY: This creates artifact dependency
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 50,
            "thermo_frequency": 10,
            "dump_frequency": 25,
            "dump_trajectory": True,
        },
    )
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Assertions
    assert result.status.value == "success", (
        f"Calculation failed (execution {execution_number}): "
        f"{result.steps[-1].message if result.steps else 'Unknown error'}"
    )
    
    # Verify relax produced final.data BEFORE asserting MD success
    raw_dir = calculation.raw_dir
    relax_dir = raw_dir / relax_step_id
    final_data = relax_dir / "final.data"
    assert final_data.exists(), (
        f"Relax step did not produce final.data. "
        f"Contents of {relax_dir}: {list(relax_dir.iterdir()) if relax_dir.exists() else 'dir missing'}"
    )
    
    # Verify MD step used restart correctly
    md_dir = raw_dir / md_step_id
    md_in_lammps = md_dir / "in.lammps"
    assert md_in_lammps.exists(), "MD in.lammps should exist"
    md_content = md_in_lammps.read_text()
    assert "read_restart" in md_content or "read_data" in md_content, (
        "MD should use restart artifact from relax step"
    )
    
    # Verify no ERROR in logs
    relax_log = (relax_dir / "log.lammps").read_text()
    md_log = (md_dir / "log.lammps").read_text()
    assert "ERROR" not in relax_log.upper(), "Relax log should not contain ERROR"
    assert "ERROR" not in md_log.upper(), "MD log should not contain ERROR"
```

### Verification Commands

```bash
# Run parallel safety test with xdist
source .venv/bin/activate
python -m pytest tests/integration/test_lammps_restart_parallel.py -v -n 3 --dist=loadfile

# Full regression test
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Expected Outcome
- All 3 parameterized executions pass consistently
- No race conditions in artifact resolution
- Clear error messages if artifacts missing

---

## Stop Conditions

**If you encounter any of the following, STOP and report back**:

1. **JobGraph Cannot Express restart_from Edges**
   - If `Job.deps` is not actually used by executor
   - If modifying deps doesn't change execution order
   - Report: Show executor code that ignores deps

2. **Handler Cannot Access Step Parameters**
   - If `step_params` is empty when checking for outputs
   - Report: Show what data is available in handler context

3. **Changes > 150 Lines**
   - If the fix grows beyond the scope described here
   - Report: Explain why and propose alternatives

4. **Tests Still Fail After PR1**
   - If output verification fix doesn't resolve the issue
   - Report: Collect debug logs and directory listings

---

## Final Verification

After both PRs, run full test suite:

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected**: All tests pass (2238+ tests), no regressions.

**Specifically verify**:
- `tests/integration/test_lammps_chain.py::test_chain_workflow` - PASS
- `tests/integration/test_lammps_long_smoke.py::test_workflow_d_restart` - PASS
- `tests/integration/test_lammps_restart_parallel.py::test_restart_chain_parallel_safe` - PASS (all 3 variants)

---

## PR Description Template

### PR1: Add LAMMPS Output Artifact Verification

**What**: Add verification that LAMMPS steps produce expected output artifacts before declaring success.

**Why**: Ubuntu CI fails because LAMMPS may return success but artifacts aren't visible yet due to filesystem timing differences.

**Changes**:
- `handlers.py`: Verify `final.data` exists for relax steps before returning success
- `step_done.py`: Add LAMMPS step completion detection

**Testing**:
- All LAMMPS integration tests pass
- Full pytest suite passes with 2238+ tests

### PR2: Add restart_from Explicit Dependencies

**What**: Make `restart_from` an explicit edge in JobGraph dependency list.

**Why**: Future-proofing for parallel job execution. Currently jobs run sequentially, but this makes the dependency explicit.

**Changes**:
- `recipes.py`: Parse `restart_from` and add to Job.deps
- New test file: `test_lammps_restart_parallel.py`

**Testing**:
- Parallel parameterized test passes with `-n 3`
- No regression in existing tests

