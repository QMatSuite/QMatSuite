# CP2K Driver Migration Plan

**PR Title**: `feat(drivers): Migrate CP2K to driver bundle architecture`

**Priority**: Fifth engine migration (follows LAMMPS pattern)

**Complexity**: MEDIUM

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract all CP2K-specific code from kernel files into a self-contained driver bundle at `src/qmatsuite/drivers/cp2k/`. After this migration:

1. All CP2K code lives in `drivers/cp2k/`
2. CP2K is registered via DriverRegistry
3. Kernel files have no CP2K-specific logic
4. Gate 3 (engine isolation) passes for CP2K

---

## 2. Code Inventory

### 2.1 Handler Code

**Source**: `src/qmatsuite/execution/handlers.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `cp2k_step_handler` | 1097-1310 | CP2K step handler (~213 lines) |

### 2.2 Recipe Code

**Source**: `src/qmatsuite/execution/recipes.py`

| Class | Lines | Description |
|-------|-------|-------------|
| `CP2KRecipe` | 694-798 | Input staging recipe (~104 lines) |

### 2.3 Step Types

```
cp2k_scf, cp2k_relax, cp2k_md, cp2k_bands, cp2k_dos,
cp2k_geo_opt, cp2k_cell_opt, cp2k_vibrational
```

### 2.4 Materialization Map

```python
("cp2k", "GEN_SCF"): "cp2k_scf"
("cp2k", "GEN_RELAX"): "cp2k_relax"
("cp2k", "GEN_MD"): "cp2k_md"
("cp2k", "GEN_BANDS"): "cp2k_bands"
```

### 2.5 Additional CP2K Logic

**Locations**:
- `src/qmatsuite/calculation/structure_steps.py` - CP2K_STEP_TYPES

### 2.6 Special Considerations

**CP2K-specific behavior**:
1. **Input format**: CP2K uses a hierarchical input format with sections
2. **Restart files**: CP2K writes RESTART.wfn and similar files
3. **Basis sets**: Needs BASIS_SET and POTENTIAL files
4. **XC functionals**: Uses libxc naming conventions

---

## 3. Target Structure

```
src/qmatsuite/drivers/cp2k/
├── __init__.py          # Registration (15 lines)
├── driver.py            # CP2KDriver class (80 lines)
├── handler.py           # cp2k_step_handler (213 lines, moved)
├── recipe.py            # CP2KRecipe (104 lines, moved)
└── input_writer.py      # CP2K input format utilities (50 lines)
```

**Total**: ~462 lines (mostly moved, not new)

---

## 4. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/qmatsuite/drivers/cp2k
touch src/qmatsuite/drivers/cp2k/__init__.py
touch src/qmatsuite/drivers/cp2k/driver.py
touch src/qmatsuite/drivers/cp2k/handler.py
touch src/qmatsuite/drivers/cp2k/recipe.py
touch src/qmatsuite/drivers/cp2k/input_writer.py
```

### Step 2: Create driver.py

**Create file**: `src/qmatsuite/drivers/cp2k/driver.py`

```python
"""CP2K engine driver.

This driver handles all CP2K calculations including:
- SCF calculations (DFT, HF, hybrid)
- Geometry and cell optimization
- Molecular dynamics
- Band structure and DOS calculations
"""

from pathlib import Path

from qmatsuite.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class CP2KDriver(BaseEngineDriver):
    """CP2K driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "cp2k"

    @property
    def display_name(self) -> str:
        return "CP2K"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return CP2K step type specifications."""
        return [
            StepTypeSpec(
                id="cp2k_scf",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K SCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_relax",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K geometry relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_geo_opt",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_cell_opt",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K cell optimization",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_md",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="cp2k_bands",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K band structure",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_dos",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K density of states",
                category="calculation",
            ),
            StepTypeSpec(
                id="cp2k_vibrational",
                engine="cp2k",
                executable="cp2k.psmp",
                description="CP2K vibrational analysis",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return CP2K step handler."""
        from .handler import cp2k_step_handler
        return cp2k_step_handler

    def get_recipe_class(self):
        """Return CP2K recipe class."""
        from .recipe import CP2KRecipe
        return CP2KRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return CP2K GEN→SPEC mappings."""
        return {
            "GEN_SCF": "cp2k_scf",
            "GEN_RELAX": "cp2k_relax",
            "GEN_OPT": "cp2k_geo_opt",
            "GEN_CELL_OPT": "cp2k_cell_opt",
            "GEN_MD": "cp2k_md",
            "GEN_BANDS": "cp2k_bands",
            "GEN_DOS": "cp2k_dos",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where CP2K differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """CP2K uses isolated workdir."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """CP2K capabilities."""
        return {
            "scf", "relax", "md", "bands", "dos",
            "geo_opt", "cell_opt", "vibrational",
            "periodic", "molecular", "mpi",
            "restart", "wfn_continuation",
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """MD steps should not be skipped."""
        if step_type == "cp2k_md":
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """CP2K preflight requirements (restart, basis sets)."""
        requirements = []

        step_config = getattr(step, "config", {}) or {}

        # Check for wavefunction restart
        if step_config.get("restart_wfn", False):
            requirements.append(PreflightRequirement(
                artifact_type="RESTART.wfn",
                source_step=step_config.get("restart_source"),
                required=True,
                description="CP2K wavefunction restart file",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify CP2K errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf run not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "file not found" in stderr_lower or "cannot open" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "input error" in stderr_lower or "unknown keyword" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "cp2k" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """CP2K artifact patterns for discovery."""
        return {
            "restart_wfn": "*RESTART.wfn*",
            "output": "*.out",
            "trajectory": "*-pos-*.xyz",
            "forces": "*-frc-*.xyz",
            "pdos": "*-k*.pdos",
            "cube": "*.cube",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find latest CP2K artifact."""
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

**Create file**: `src/qmatsuite/drivers/cp2k/handler.py`

**Copy** the `cp2k_step_handler` function from `handlers.py` (lines 1097-1310).

```python
"""CP2K step handler.

This module contains the main handler for CP2K step execution.
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from qmatsuite.core.job import Job
from qmatsuite.core.step_context import StepContext
from qmatsuite.core.job_result import JobResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def cp2k_step_handler(job: Job, context: StepContext) -> JobResult:
    """Handle CP2K step execution.

    This handler manages:
    - Input file generation (hierarchical CP2K format)
    - Basis set and potential file staging
    - CP2K execution
    - Output collection
    - Restart file handling

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    # [COPY EXISTING FUNCTION BODY FROM handlers.py lines 1097-1310]
    # The function body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

### Step 4: Move Recipe to recipe.py

**Create file**: `src/qmatsuite/drivers/cp2k/recipe.py`

**Copy** the `CP2KRecipe` class from `recipes.py` (lines 694-798).

```python
"""CP2K recipe for input staging.

This module handles the preparation of CP2K input files.
"""

import logging
from pathlib import Path
from typing import Any

from qmatsuite.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class CP2KRecipe(BaseRecipe):
    """Recipe for staging CP2K inputs.

    Handles:
    - Input file generation in CP2K hierarchical format
    - Coordinate specification
    - Basis set and potential references
    - Method and parameter configuration
    """

    # [COPY EXISTING CLASS BODY FROM recipes.py lines 694-798]
    # The class body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

### Step 5: Create input_writer.py (Optional)

**Create file**: `src/qmatsuite/drivers/cp2k/input_writer.py`

```python
"""CP2K input file writer utilities.

This module provides helpers for writing CP2K hierarchical input format.
"""

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def write_section(
    name: str,
    content: Dict[str, Any],
    indent: int = 0,
) -> str:
    """Write a CP2K input section.

    Args:
        name: Section name (e.g., "FORCE_EVAL")
        content: Section content as nested dict
        indent: Current indentation level

    Returns:
        Formatted section string
    """
    lines = []
    prefix = "  " * indent

    lines.append(f"{prefix}&{name}")

    for key, value in content.items():
        if isinstance(value, dict):
            # Nested section
            lines.append(write_section(key, value, indent + 1))
        elif isinstance(value, list):
            # Multiple values or repeated sections
            for item in value:
                if isinstance(item, dict):
                    lines.append(write_section(key, item, indent + 1))
                else:
                    lines.append(f"{prefix}  {key} {item}")
        else:
            lines.append(f"{prefix}  {key} {value}")

    lines.append(f"{prefix}&END {name}")

    return "\n".join(lines)
```

### Step 6: Create __init__.py

**Create file**: `src/qmatsuite/drivers/cp2k/__init__.py`

```python
"""CP2K driver bundle.

This package provides the CP2K engine driver for QMatSuite.
It handles all CP2K calculations including DFT, MD, and
property calculations.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import CP2KDriver

# Register driver at import time
DriverRegistry.register(CP2KDriver())

__all__ = ["CP2KDriver"]
```

### Step 7: Update drivers/__init__.py

**File**: `src/qmatsuite/drivers/__init__.py`

**Add** CP2K import:

```python
from qmatsuite.drivers import qe_shim
from qmatsuite.drivers import vasp
from qmatsuite.drivers import orca
from qmatsuite.drivers import pyscf
from qmatsuite.drivers import lammps
from qmatsuite.drivers import cp2k  # ADD THIS LINE
```

### Step 8: Remove CP2K from Kernel Files

**handlers.py**: Remove `cp2k_step_handler` (lines 1097-1310)

**recipes.py**: Remove `CP2KRecipe` (lines 694-798)

**structure_steps.py**: Verify CP2K_STEP_TYPES uses registry

### Step 9: Create CP2K-Specific Tests

**Create file**: `tests/drivers/cp2k/test_cp2k_driver.py`

```python
"""Tests for CP2K driver bundle."""

import pytest
from qmatsuite.drivers.cp2k import CP2KDriver
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_protocol import WorkdirPolicy


class TestCP2KDriver:
    """Test CP2KDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = CP2KDriver()
        assert driver.engine_family == "cp2k"
        assert driver.display_name == "CP2K"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = CP2KDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "cp2k_scf" in spec_ids
        assert "cp2k_relax" in spec_ids
        assert "cp2k_md" in spec_ids

        for spec in specs:
            assert spec.engine == "cp2k"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = CP2KDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = CP2KDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = CP2KDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "cp2k_scf"
        assert mat_map["GEN_MD"] == "cp2k_md"

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = CP2KDriver()
        assert driver.supports_incremental_skip("cp2k_scf") is True
        assert driver.supports_incremental_skip("cp2k_md") is False


class TestCP2KRegistration:
    """Test CP2K driver registration."""

    def test_cp2k_registered(self):
        """CP2K should be registered in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_engine_registered("cp2k")
        driver = DriverRegistry.get_driver("cp2k")
        assert driver.engine_family == "cp2k"

    def test_cp2k_step_types_registered(self):
        """CP2K step types should be in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("cp2k_scf")
        assert DriverRegistry.is_step_type_registered("cp2k_relax")


class TestCP2KIsolation:
    """Gate 3 tests: CP2K isolation from kernel."""

    def test_handlers_no_cp2k_handler(self):
        """handlers.py should not contain cp2k_step_handler."""
        from pathlib import Path
        source = Path("src/qmatsuite/execution/handlers.py").read_text()

        assert "def cp2k_step_handler" not in source

    def test_recipes_no_cp2k_recipe(self):
        """recipes.py should not contain CP2KRecipe."""
        from pathlib import Path
        source = Path("src/qmatsuite/execution/recipes.py").read_text()

        assert "class CP2KRecipe" not in source
```

### Step 10: Run Tests

```bash
pytest tests/drivers/cp2k/ -v
pytest tests/gates/ -v -k "cp2k"
pytest tests/ -v
```

---

## 5. PR Checklist

- [ ] `drivers/cp2k/` directory created
- [ ] `driver.py` with CP2KDriver class
- [ ] `handler.py` with moved cp2k_step_handler
- [ ] `recipe.py` with moved CP2KRecipe
- [ ] `__init__.py` with registration
- [ ] CP2K removed from handlers.py
- [ ] CP2K removed from recipes.py
- [ ] CP2K driver tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes

---

## 6. Definition of Done

1. All CP2K code in `drivers/cp2k/`
2. No CP2K-specific code in kernel files
3. CP2K registered via DriverRegistry
4. All existing CP2K tests pass
5. Gate 3 (isolation) tests pass
6. CI green
