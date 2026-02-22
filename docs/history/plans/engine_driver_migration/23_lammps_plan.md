# LAMMPS Driver Migration Plan

**PR Title**: `feat(drivers): Migrate LAMMPS to driver bundle architecture`

**Priority**: Fourth engine migration (has restart logic)

**Complexity**: MEDIUM

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract all LAMMPS-specific code from kernel files into a self-contained driver bundle at `src/qmatsuite/drivers/lammps/`. After this migration:

1. All LAMMPS code lives in `drivers/lammps/`
2. LAMMPS is registered via DriverRegistry
3. Kernel files have no LAMMPS-specific logic
4. Restart/continuation logic preserved
5. Gate 3 (engine isolation) passes for LAMMPS

---

## 2. Code Inventory

### 2.1 Handler Code

**Source**: `src/qmatsuite/execution/handlers.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `lammps_step_handler` | 459-755 | LAMMPS step handler (~296 lines) |
| Restart handling | (within handler) | Checkpoint/restart logic |

### 2.2 Recipe Code

**Source**: `src/qmatsuite/execution/recipes.py`

| Class | Lines | Description |
|-------|-------|-------------|
| `LAMMPSRecipe` | 336-469 | Input staging recipe (~133 lines) |

### 2.3 Step Types

```
lammps_minimize, lammps_md, lammps_npt, lammps_nvt, lammps_nve,
lammps_relax, lammps_equilibrate, lammps_deform
```

### 2.4 Materialization Map

```python
("lammps", "GEN_MINIMIZE"): "lammps_minimize"
("lammps", "GEN_MD"): "lammps_md"
("lammps", "GEN_RELAX"): "lammps_relax"
```

### 2.5 Additional LAMMPS Logic

**Locations**:
- `src/qmatsuite/calculation/step_done.py` - LAMMPS_STEP_TYPES, done detection
- `src/qmatsuite/calculation/structure_steps.py` - LAMMPS_STEP_TYPES

### 2.6 Special Considerations

**LAMMPS-specific behavior**:
1. **Restart files**: LAMMPS writes checkpoint files that can restart simulations
2. **Accumulation mode**: Workdir accumulates files across steps
3. **Data file handling**: LAMMPS uses data files for structure input
4. **Force field files**: Potential files need staging

---

## 3. Target Structure

```
src/qmatsuite/drivers/lammps/
├── __init__.py          # Registration (15 lines)
├── driver.py            # LAMMPSDriver class (90 lines)
├── handler.py           # lammps_step_handler (296 lines, moved)
├── recipe.py            # LAMMPSRecipe (133 lines, moved)
├── restart.py           # Restart/checkpoint handling (60 lines)
└── data_file.py         # Data file utilities (40 lines)
```

**Total**: ~634 lines (mostly moved, not new)

---

## 4. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/qmatsuite/drivers/lammps
touch src/qmatsuite/drivers/lammps/__init__.py
touch src/qmatsuite/drivers/lammps/driver.py
touch src/qmatsuite/drivers/lammps/handler.py
touch src/qmatsuite/drivers/lammps/recipe.py
touch src/qmatsuite/drivers/lammps/restart.py
touch src/qmatsuite/drivers/lammps/data_file.py
```

### Step 2: Create driver.py

**Create file**: `src/qmatsuite/drivers/lammps/driver.py`

```python
"""LAMMPS engine driver.

This driver handles all LAMMPS molecular dynamics simulations including:
- Energy minimization
- NVE, NVT, NPT ensembles
- Structure relaxation
- Deformation studies

LAMMPS has special restart/checkpoint capabilities that are
handled by this driver.
"""

from pathlib import Path
from typing import Any

from qmatsuite.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class LAMMPSDriver(BaseEngineDriver):
    """LAMMPS driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "lammps"

    @property
    def display_name(self) -> str:
        return "LAMMPS"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return LAMMPS step type specifications."""
        return [
            StepTypeSpec(
                id="lammps_minimize",
                engine="lammps",
                executable="lmp",
                description="LAMMPS energy minimization",
                category="calculation",
            ),
            StepTypeSpec(
                id="lammps_md",
                engine="lammps",
                executable="lmp",
                description="LAMMPS molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="lammps_nve",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NVE ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="lammps_nvt",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NVT ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="lammps_npt",
                engine="lammps",
                executable="lmp",
                description="LAMMPS NPT ensemble MD",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="lammps_relax",
                engine="lammps",
                executable="lmp",
                description="LAMMPS structure relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="lammps_equilibrate",
                engine="lammps",
                executable="lmp",
                description="LAMMPS equilibration run",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="lammps_deform",
                engine="lammps",
                executable="lmp",
                description="LAMMPS deformation study",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return LAMMPS step handler."""
        from .handler import lammps_step_handler
        return lammps_step_handler

    def get_recipe_class(self):
        """Return LAMMPS recipe class."""
        from .recipe import LAMMPSRecipe
        return LAMMPSRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return LAMMPS GEN→SPEC mappings."""
        return {
            "GEN_MINIMIZE": "lammps_minimize",
            "GEN_MD": "lammps_md",
            "GEN_RELAX": "lammps_relax",
            "GEN_NVT": "lammps_nvt",
            "GEN_NPT": "lammps_npt",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where LAMMPS differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """LAMMPS uses isolated workdir with accumulation."""
        # LAMMPS accumulates trajectory files, restart files
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """LAMMPS capabilities."""
        return {
            "minimize", "md", "nve", "nvt", "npt",
            "relax", "deform",
            "periodic", "molecular", "mpi",
            "restart",  # Supports restart from checkpoint
            "trajectory",  # Produces trajectory files
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """MD steps should not be skipped (continuation matters)."""
        md_steps = {"lammps_md", "lammps_nve", "lammps_nvt", "lammps_npt", "lammps_equilibrate"}
        if step_type in md_steps:
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """LAMMPS preflight requirements (restart files, potentials)."""
        requirements = []

        step_config = getattr(step, "config", {}) or {}

        # Check for restart continuation
        if step_config.get("restart", False):
            requirements.append(PreflightRequirement(
                artifact_type="restart",
                source_step=step_config.get("restart_source"),
                required=True,
                description="LAMMPS restart file for continuation",
            ))

        # Check for potential files
        if step_config.get("potential_file"):
            requirements.append(PreflightRequirement(
                artifact_type="potential",
                source_step=None,  # Potential files are typically external
                required=True,
                description="Force field potential file",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify LAMMPS errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "lost atoms" in stderr_lower:
            return ErrorClass.CONVERGENCE  # Simulation instability
        if "out of memory" in stderr_lower or "malloc" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "cannot open" in stderr_lower or "file not found" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "illegal" in stderr_lower or "unknown" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "lmp" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """LAMMPS artifact patterns for discovery."""
        return {
            "restart": "*.restart*",
            "data": "*.data",
            "trajectory": "*.lammpstrj",
            "log": "log.lammps",
            "dump": "dump.*",
            "thermo": "thermo.dat",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find latest LAMMPS artifact (especially restart files)."""
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = sorted(
            workdir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return matches[0] if matches else None
```

### Step 3: Move Handler to handler.py

**Create file**: `src/qmatsuite/drivers/lammps/handler.py`

**Copy** the `lammps_step_handler` function from `handlers.py` (lines 459-755).

```python
"""LAMMPS step handler.

This module contains the main handler for LAMMPS step execution.
LAMMPS has special handling for:
- Restart/checkpoint files
- Trajectory accumulation
- Data file input format
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from qmatsuite.core.job import Job
from qmatsuite.core.step_context import StepContext
from qmatsuite.core.job_result import JobResult

from .restart import find_restart_file, stage_restart_file

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def lammps_step_handler(job: Job, context: StepContext) -> JobResult:
    """Handle LAMMPS step execution.

    This handler manages:
    - Input script staging
    - Data file preparation
    - Restart file handling (read from previous, write for next)
    - LAMMPS execution
    - Output/trajectory collection

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    # [COPY EXISTING FUNCTION BODY FROM handlers.py lines 459-755]
    # The function body remains EXACTLY the same
    # Only update imports to use local modules (.restart, .data_file)
    pass  # Placeholder - copy actual code
```

### Step 4: Move Recipe to recipe.py

**Create file**: `src/qmatsuite/drivers/lammps/recipe.py`

**Copy** the `LAMMPSRecipe` class from `recipes.py` (lines 336-469).

```python
"""LAMMPS recipe for input staging.

This module handles the preparation of LAMMPS input files.
"""

import logging
from pathlib import Path
from typing import Any

from qmatsuite.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class LAMMPSRecipe(BaseRecipe):
    """Recipe for staging LAMMPS inputs.

    Handles:
    - Input script generation
    - Data file creation from structure
    - Potential file linking
    - Restart file staging
    """

    # [COPY EXISTING CLASS BODY FROM recipes.py lines 336-469]
    # The class body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

### Step 5: Create restart.py

**Create file**: `src/qmatsuite/drivers/lammps/restart.py`

**Extract** restart handling logic from handler if applicable.

```python
"""LAMMPS restart file handling.

This module manages LAMMPS restart/checkpoint files for
simulation continuation.
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.step_context import StepContext

logger = logging.getLogger(__name__)


def find_restart_file(
    workdir: Path,
    pattern: str = "*.restart*",
) -> Optional[Path]:
    """Find the latest restart file in workdir.

    LAMMPS can write numbered restart files (e.g., restart.100000).
    This function finds the most recent one.

    Args:
        workdir: Directory to search
        pattern: Glob pattern for restart files

    Returns:
        Path to latest restart file, or None if not found
    """
    matches = list(workdir.glob(pattern))
    if not matches:
        return None

    # Sort by modification time, get most recent
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def stage_restart_file(
    source: Path,
    target_dir: Path,
    target_name: str = "restart.read",
) -> Path:
    """Stage restart file for reading.

    LAMMPS expects restart files with specific names for reading.

    Args:
        source: Source restart file path
        target_dir: Target directory
        target_name: Name for the staged file

    Returns:
        Path to staged restart file
    """
    import shutil

    target = target_dir / target_name
    shutil.copy2(source, target)
    logger.info(f"Staged restart file: {source} -> {target}")
    return target


def resolve_restart_source(
    context: "StepContext",
    explicit_source: Optional[str] = None,
) -> Optional[Path]:
    """Resolve source step for restart file.

    Args:
        context: Step context with calculation info
        explicit_source: Explicitly specified source step

    Returns:
        Path to restart file, or None if not found
    """
    if explicit_source:
        step_dir = context.get_step_dir(explicit_source)
        if step_dir:
            restart = find_restart_file(step_dir)
            if restart:
                return restart
        logger.warning(f"No restart file in explicit source '{explicit_source}'")

    # Auto-resolve: find previous step with restart file
    for prev_step in reversed(context.completed_steps):
        step_dir = context.get_step_dir(prev_step)
        if step_dir:
            restart = find_restart_file(step_dir)
            if restart:
                logger.debug(f"Auto-resolved restart from {prev_step}")
                return restart

    return None
```

### Step 6: Create data_file.py

**Create file**: `src/qmatsuite/drivers/lammps/data_file.py`

```python
"""LAMMPS data file utilities.

This module handles LAMMPS data file creation and manipulation.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.structure import Structure

logger = logging.getLogger(__name__)


def write_data_file(
    structure: "Structure",
    output_path: Path,
    atom_style: str = "full",
) -> None:
    """Write LAMMPS data file from structure.

    Args:
        structure: Input structure
        output_path: Path to write data file
        atom_style: LAMMPS atom style (atomic, charge, full, etc.)
    """
    # Implementation would convert structure to LAMMPS data format
    # This is a placeholder - actual implementation depends on
    # existing structure conversion code
    pass
```

### Step 7: Create __init__.py

**Create file**: `src/qmatsuite/drivers/lammps/__init__.py`

```python
"""LAMMPS driver bundle.

This package provides the LAMMPS engine driver for QMatSuite.
It handles all LAMMPS molecular dynamics simulations including
energy minimization, various ensembles, and restart handling.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import LAMMPSDriver

# Register driver at import time
DriverRegistry.register(LAMMPSDriver())

__all__ = ["LAMMPSDriver"]
```

### Step 8: Update drivers/__init__.py

**File**: `src/qmatsuite/drivers/__init__.py`

**Add** LAMMPS import:

```python
from qmatsuite.drivers import qe_shim
from qmatsuite.drivers import vasp
from qmatsuite.drivers import orca
from qmatsuite.drivers import pyscf
from qmatsuite.drivers import lammps  # ADD THIS LINE
```

### Step 9: Remove LAMMPS from Kernel Files

**handlers.py**: Remove `lammps_step_handler` (lines 459-755)

**recipes.py**: Remove `LAMMPSRecipe` (lines 336-469)

**step_done.py**: Verify LAMMPS_STEP_TYPES uses registry

**structure_steps.py**: Verify LAMMPS_STEP_TYPES uses registry

### Step 10: Create LAMMPS-Specific Tests

**Create file**: `tests/drivers/lammps/test_lammps_driver.py`

```python
"""Tests for LAMMPS driver bundle."""

import pytest
from qmatsuite.drivers.lammps import LAMMPSDriver
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_protocol import WorkdirPolicy


class TestLAMMPSDriver:
    """Test LAMMPSDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = LAMMPSDriver()
        assert driver.engine_family == "lammps"
        assert driver.display_name == "LAMMPS"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = LAMMPSDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "lammps_minimize" in spec_ids
        assert "lammps_md" in spec_ids
        assert "lammps_npt" in spec_ids

        for spec in specs:
            assert spec.engine == "lammps"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = LAMMPSDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = LAMMPSDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = LAMMPSDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_MD"] == "lammps_md"
        assert mat_map["GEN_MINIMIZE"] == "lammps_minimize"

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = LAMMPSDriver()
        assert driver.supports_incremental_skip("lammps_minimize") is True
        assert driver.supports_incremental_skip("lammps_md") is False
        assert driver.supports_incremental_skip("lammps_npt") is False

    def test_restart_capability(self):
        """LAMMPS should have restart capability."""
        driver = LAMMPSDriver()
        assert "restart" in driver.get_capabilities()


class TestLAMMPSRegistration:
    """Test LAMMPS driver registration."""

    def test_lammps_registered(self):
        """LAMMPS should be registered in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_engine_registered("lammps")
        driver = DriverRegistry.get_driver("lammps")
        assert driver.engine_family == "lammps"

    def test_lammps_step_types_registered(self):
        """LAMMPS step types should be in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("lammps_minimize")
        assert DriverRegistry.is_step_type_registered("lammps_md")


class TestLAMMPSIsolation:
    """Gate 3 tests: LAMMPS isolation from kernel."""

    def test_handlers_no_lammps_handler(self):
        """handlers.py should not contain lammps_step_handler."""
        from pathlib import Path
        source = Path("src/qmatsuite/execution/handlers.py").read_text()

        assert "def lammps_step_handler" not in source

    def test_recipes_no_lammps_recipe(self):
        """recipes.py should not contain LAMMPSRecipe."""
        from pathlib import Path
        source = Path("src/qmatsuite/execution/recipes.py").read_text()

        assert "class LAMMPSRecipe" not in source


class TestLAMMPSRestart:
    """Tests for LAMMPS restart handling."""

    def test_find_restart_file(self, tmp_path):
        """Test finding latest restart file."""
        from qmatsuite.drivers.lammps.restart import find_restart_file
        import time

        # Create mock restart files
        (tmp_path / "restart.1000").touch()
        time.sleep(0.01)
        (tmp_path / "restart.2000").touch()

        latest = find_restart_file(tmp_path)
        assert latest is not None
        assert latest.name == "restart.2000"

    def test_find_restart_file_none(self, tmp_path):
        """Test no restart file found."""
        from qmatsuite.drivers.lammps.restart import find_restart_file

        result = find_restart_file(tmp_path)
        assert result is None
```

### Step 11: Run Tests

```bash
pytest tests/drivers/lammps/ -v
pytest tests/gates/ -v -k "lammps"
pytest tests/ -v
```

---

## 5. Semantic Preservation Checklist

| Semantic | Verification |
|----------|--------------|
| LAMMPS handler behavior | Test step execution |
| LAMMPS recipe staging | Test input script generation |
| Restart file handling | Test continuation from checkpoint |
| Data file creation | Test structure → data conversion |
| MD accumulation | Test trajectory file handling |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Restart logic broken | Medium | High | Dedicated restart tests |
| Data file handling | Low | Medium | Test with real structures |
| Trajectory handling | Low | Medium | Test MD output collection |

---

## 7. PR Checklist

- [ ] `drivers/lammps/` directory created
- [ ] `driver.py` with LAMMPSDriver class
- [ ] `handler.py` with moved lammps_step_handler
- [ ] `recipe.py` with moved LAMMPSRecipe
- [ ] `restart.py` with restart handling
- [ ] `__init__.py` with registration
- [ ] LAMMPS removed from handlers.py
- [ ] LAMMPS removed from recipes.py
- [ ] LAMMPS driver tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes

---

## 8. Definition of Done

1. All LAMMPS code in `drivers/lammps/`
2. No LAMMPS-specific code in kernel files
3. LAMMPS registered via DriverRegistry
4. Restart/continuation works correctly
5. All existing LAMMPS tests pass
6. Gate 3 (isolation) tests pass
7. CI green
