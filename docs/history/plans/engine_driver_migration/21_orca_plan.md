# ORCA Driver Migration Plan

**PR Title**: `feat(drivers): Migrate ORCA to driver bundle architecture`

**Priority**: Second engine migration (validates chain handler pattern)

**Complexity**: LOW

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract all ORCA-specific code from kernel files into a self-contained driver bundle at `src/quantumvitas/drivers/orca/`. After this migration:

1. All ORCA code lives in `drivers/orca/`
2. ORCA is registered via DriverRegistry
3. Kernel files have no ORCA-specific logic
4. Chain handler pattern validated
5. Gate 3 (engine isolation) passes for ORCA

---

## 2. Code Inventory

### 2.1 Handler Code

**Source**: `src/quantumvitas/execution/handlers.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `orca_chain_handler` | 887-1095 | ORCA chain handler (~208 lines) |
| `_run_orca_step` | (internal) | Single step execution |

### 2.2 Recipe Code

**Source**: `src/quantumvitas/execution/recipes.py`

| Class | Lines | Description |
|-------|-------|-------------|
| `ORCARecipe` | 471-580 | Input staging recipe (~109 lines) |

### 2.3 Step Types

```
orca_scf, orca_opt, orca_freq, orca_sp, orca_tddft,
orca_mp2, orca_ccsd, orca_casscf, orca_nevpt2
```

### 2.4 Materialization Map

```python
("orca", "GEN_SCF"): "orca_scf"
("orca", "GEN_OPT"): "orca_opt"
("orca", "GEN_FREQ"): "orca_freq"
```

### 2.5 Additional ORCA Logic

**Locations**:
- `src/quantumvitas/io/generator/` - ORCA input generator
- `src/quantumvitas/io/parser/` - ORCA output parser
- `src/quantumvitas/calculation/structure_steps.py` - ORCA_STEP_TYPES

---

## 3. Target Structure

```
src/quantumvitas/drivers/orca/
├── __init__.py          # Registration (15 lines)
├── driver.py            # ORCADriver class (60 lines)
├── handler.py           # orca_chain_handler (208 lines, moved)
└── recipe.py            # ORCARecipe (109 lines, moved)
```

**Total**: ~392 lines (mostly moved, not new)

---

## 4. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/quantumvitas/drivers/orca
touch src/quantumvitas/drivers/orca/__init__.py
touch src/quantumvitas/drivers/orca/driver.py
touch src/quantumvitas/drivers/orca/handler.py
touch src/quantumvitas/drivers/orca/recipe.py
```

### Step 2: Create driver.py

**Create file**: `src/quantumvitas/drivers/orca/driver.py`

```python
"""ORCA engine driver.

This driver handles all ORCA quantum chemistry calculations including:
- SCF, geometry optimization, frequency calculations
- MP2, CCSD, CASSCF, NEVPT2 methods
- TD-DFT excited state calculations
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class ORCADriver(BaseEngineDriver):
    """ORCA driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "orca"

    @property
    def display_name(self) -> str:
        return "ORCA"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return ORCA step type specifications."""
        return [
            StepTypeSpec(
                id="orca_scf",
                engine="orca",
                executable="orca",
                description="ORCA SCF single-point calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_opt",
                engine="orca",
                executable="orca",
                description="ORCA geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_freq",
                engine="orca",
                executable="orca",
                description="ORCA frequency/vibrational calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_sp",
                engine="orca",
                executable="orca",
                description="ORCA single-point energy",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_tddft",
                engine="orca",
                executable="orca",
                description="ORCA TD-DFT excited states",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_mp2",
                engine="orca",
                executable="orca",
                description="ORCA MP2 calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_ccsd",
                engine="orca",
                executable="orca",
                description="ORCA CCSD calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_casscf",
                engine="orca",
                executable="orca",
                description="ORCA CASSCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="orca_nevpt2",
                engine="orca",
                executable="orca",
                description="ORCA NEVPT2 calculation",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return ORCA chain handler."""
        from .handler import orca_chain_handler
        return orca_chain_handler

    def get_recipe_class(self):
        """Return ORCA recipe class."""
        from .recipe import ORCARecipe
        return ORCARecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return ORCA GEN→SPEC mappings."""
        return {
            "GEN_SCF": "orca_scf",
            "GEN_OPT": "orca_opt",
            "GEN_FREQ": "orca_freq",
            "GEN_SP": "orca_sp",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where ORCA differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """ORCA uses isolated workdir (default)."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """ORCA capabilities."""
        return {
            "scf", "opt", "freq", "sp",
            "tddft", "mp2", "ccsd", "casscf", "nevpt2",
            "molecular", "mpi",
            "chain",  # Supports chain execution
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """All ORCA steps can be skipped if done."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify ORCA errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower or "allocation" in stderr_lower:
            return ErrorClass.MEMORY
        if "input error" in stderr_lower or "unknown keyword" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "orca not found" in stderr_lower or exit_code == 127:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """ORCA artifact patterns for discovery."""
        return {
            "output": "*.out",
            "gbw": "*.gbw",
            "xyz": "*.xyz",
            "hess": "*.hess",
            "prop": "*.prop",
            "engrad": "*.engrad",
        }
```

### Step 3: Move Handler to handler.py

**Create file**: `src/quantumvitas/drivers/orca/handler.py`

**Copy** the `orca_chain_handler` function from `handlers.py` (lines 887-1095).

```python
"""ORCA chain handler.

This module contains the chain handler for ORCA calculations.
ORCA uses a chain pattern where multiple related calculations
can be grouped and executed with shared context.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from quantumvitas.core.job import Job
from quantumvitas.core.step_context import StepContext
from quantumvitas.core.job_result import JobResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def orca_chain_handler(job: Job, context: StepContext) -> JobResult:
    """Handle ORCA chain execution.

    ORCA calculations can be chained, where the output of one
    calculation feeds into the next. This handler manages:
    - Input file generation
    - ORCA execution
    - Output parsing
    - Chain state management

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    # [COPY EXISTING FUNCTION BODY FROM handlers.py lines 887-1095]
    # The function body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

**CRITICAL**: Copy the EXACT function body. Do not modify logic.

### Step 4: Move Recipe to recipe.py

**Create file**: `src/quantumvitas/drivers/orca/recipe.py`

**Copy** the `ORCARecipe` class from `recipes.py` (lines 471-580).

```python
"""ORCA recipe for input staging.

This module handles the preparation of ORCA input files.
"""

import logging
from pathlib import Path
from typing import Any

from quantumvitas.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class ORCARecipe(BaseRecipe):
    """Recipe for staging ORCA inputs.

    Handles:
    - Input file generation from template
    - Coordinate block insertion
    - Method/basis specification
    - Parallelization settings
    """

    # [COPY EXISTING CLASS BODY FROM recipes.py lines 471-580]
    # The class body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

**CRITICAL**: Copy the EXACT class body. Do not modify logic.

### Step 5: Create __init__.py

**Create file**: `src/quantumvitas/drivers/orca/__init__.py`

```python
"""ORCA driver bundle.

This package provides the ORCA engine driver for QuantumVitas.
It handles all ORCA quantum chemistry calculations including
SCF, optimization, frequencies, and correlated methods.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import ORCADriver

# Register driver at import time
DriverRegistry.register(ORCADriver())

__all__ = ["ORCADriver"]
```

### Step 6: Update drivers/__init__.py

**File**: `src/quantumvitas/drivers/__init__.py`

**Add** ORCA import:

```python
# Import all driver packages to trigger registration
from quantumvitas.drivers import qe_shim
from quantumvitas.drivers import vasp
from quantumvitas.drivers import orca  # ADD THIS LINE
```

### Step 7: Remove ORCA from handlers.py

**File**: `src/quantumvitas/execution/handlers.py`

**Remove**:
1. `orca_chain_handler` function (lines 887-1095)
2. Any ORCA-specific helper functions
3. ORCA-specific imports (if unused)

### Step 8: Remove ORCA from recipes.py

**File**: `src/quantumvitas/execution/recipes.py`

**Remove**:
1. `ORCARecipe` class (lines 471-580)
2. ORCA-specific imports (if unused)

### Step 9: Clean up structure_steps.py

**File**: `src/quantumvitas/calculation/structure_steps.py`

**Verify** that ORCA_STEP_TYPES is now provided by registry (from PR 2).

### Step 10: Create ORCA-Specific Tests

**Create file**: `tests/drivers/orca/test_orca_driver.py`

```python
"""Tests for ORCA driver bundle."""

import pytest
from quantumvitas.drivers.orca import ORCADriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestORCADriver:
    """Test ORCADriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = ORCADriver()
        assert driver.engine_family == "orca"
        assert driver.display_name == "ORCA"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = ORCADriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "orca_scf" in spec_ids
        assert "orca_opt" in spec_ids
        assert "orca_freq" in spec_ids

        for spec in specs:
            assert spec.engine == "orca"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = ORCADriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = ORCADriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = ORCADriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "orca_scf"
        assert mat_map["GEN_OPT"] == "orca_opt"

    def test_workdir_policy_isolated(self):
        """ORCA should use ISOLATED policy (default)."""
        driver = ORCADriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_chain_capability(self):
        """ORCA should have chain capability."""
        driver = ORCADriver()
        assert "chain" in driver.get_capabilities()


class TestORCARegistration:
    """Test ORCA driver registration."""

    def test_orca_registered(self):
        """ORCA should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("orca")
        driver = DriverRegistry.get_driver("orca")
        assert driver.engine_family == "orca"

    def test_orca_step_types_registered(self):
        """ORCA step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("orca_scf")
        assert DriverRegistry.is_step_type_registered("orca_opt")

    def test_orca_handler_via_registry(self):
        """Should get ORCA handler via registry."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("orca_scf")
        assert callable(handler)


class TestORCAIsolation:
    """Gate 3 tests: ORCA isolation from kernel."""

    def test_handlers_no_orca_handler(self):
        """handlers.py should not contain orca_chain_handler."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/handlers.py").read_text()

        assert "def orca_chain_handler" not in source, (
            "orca_chain_handler should be moved to drivers/orca/handler.py"
        )

    def test_recipes_no_orca_recipe(self):
        """recipes.py should not contain ORCARecipe."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/recipes.py").read_text()

        assert "class ORCARecipe" not in source, (
            "ORCARecipe should be moved to drivers/orca/recipe.py"
        )
```

### Step 11: Run Tests

```bash
# ORCA driver tests
pytest tests/drivers/orca/ -v

# Gate 3 isolation tests for ORCA
pytest tests/gates/ -v -k "orca"

# Full test suite
pytest tests/ -v
```

---

## 5. Semantic Preservation Checklist

| Semantic | Verification |
|----------|--------------|
| ORCA chain handler behavior | Test multi-step chain execution |
| ORCA recipe staging | Test input file generation |
| SCF calculation works | Test orca_scf step |
| Optimization works | Test orca_opt step |
| Frequency works | Test orca_freq step |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Chain logic broken | Low | High | Copy exactly, test chains |
| Import paths wrong | Medium | Low | Verify imports |

---

## 7. PR Checklist

- [ ] `drivers/orca/` directory created
- [ ] `driver.py` with ORCADriver class
- [ ] `handler.py` with moved orca_chain_handler
- [ ] `recipe.py` with moved ORCARecipe
- [ ] `__init__.py` with registration
- [ ] ORCA removed from handlers.py
- [ ] ORCA removed from recipes.py
- [ ] ORCA driver tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes

---

## 8. Definition of Done

1. All ORCA code in `drivers/orca/`
2. No ORCA-specific code in kernel files
3. ORCA registered via DriverRegistry
4. Chain execution works correctly
5. All existing ORCA tests pass
6. Gate 3 (isolation) tests pass
7. CI green
