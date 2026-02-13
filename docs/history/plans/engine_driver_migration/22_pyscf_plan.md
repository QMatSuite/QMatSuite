# PySCF Driver Migration Plan

**PR Title**: `feat(drivers): Migrate PySCF to driver bundle architecture`

**Priority**: Third engine migration (similar pattern to ORCA)

**Complexity**: LOW

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract all PySCF-specific code from kernel files into a self-contained driver bundle at `src/quantumvitas/drivers/pyscf/`. After this migration:

1. All PySCF code lives in `drivers/pyscf/`
2. PySCF is registered via DriverRegistry
3. Kernel files have no PySCF-specific logic
4. Gate 3 (engine isolation) passes for PySCF

---

## 2. Code Inventory

### 2.1 Handler Code

**Source**: `src/quantumvitas/execution/handlers.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `pyscf_chain_handler` | 757-885 | PySCF chain handler (~128 lines) |

### 2.2 Recipe Code

**Source**: `src/quantumvitas/execution/recipes.py`

| Class | Lines | Description |
|-------|-------|-------------|
| `PySCFRecipe` | 583-692 | Input staging recipe (~109 lines) |

### 2.3 Step Types

```
pyscf_scf, pyscf_opt, pyscf_freq, pyscf_mp2, pyscf_ccsd,
pyscf_casscf, pyscf_casci, pyscf_dft, pyscf_tddft
```

### 2.4 Materialization Map

```python
("pyscf", "GEN_SCF"): "pyscf_scf"
("pyscf", "GEN_OPT"): "pyscf_opt"
("pyscf", "GEN_FREQ"): "pyscf_freq"
```

### 2.5 Additional PySCF Logic

**Locations**:
- `src/quantumvitas/calculation/structure_steps.py` - PYSCF_STEP_TYPES
- `src/quantumvitas/workflow/generalized_steps.py` - pyscf startswith checks

---

## 3. Target Structure

```
src/quantumvitas/drivers/pyscf/
├── __init__.py          # Registration (15 lines)
├── driver.py            # PySCFDriver class (70 lines)
├── handler.py           # pyscf_chain_handler (128 lines, moved)
└── recipe.py            # PySCFRecipe (109 lines, moved)
```

**Total**: ~322 lines (mostly moved, not new)

---

## 4. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/quantumvitas/drivers/pyscf
touch src/quantumvitas/drivers/pyscf/__init__.py
touch src/quantumvitas/drivers/pyscf/driver.py
touch src/quantumvitas/drivers/pyscf/handler.py
touch src/quantumvitas/drivers/pyscf/recipe.py
```

### Step 2: Create driver.py

**Create file**: `src/quantumvitas/drivers/pyscf/driver.py`

```python
"""PySCF engine driver.

This driver handles all PySCF quantum chemistry calculations including:
- HF/DFT SCF calculations
- Geometry optimization, frequency calculations
- MP2, CCSD correlated methods
- CASSCF, CASCI multiconfigurational methods
- TD-DFT excited states
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    ErrorClass,
)


class PySCFDriver(BaseEngineDriver):
    """PySCF driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "pyscf"

    @property
    def display_name(self) -> str:
        return "PySCF"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return PySCF step type specifications."""
        return [
            StepTypeSpec(
                id="pyscf_scf",
                engine="pyscf",
                executable="python",  # PySCF is Python-based
                description="PySCF HF/DFT SCF calculation",
                category="calculation",
                mpi_aware=False,  # PySCF uses internal parallelization
            ),
            StepTypeSpec(
                id="pyscf_dft",
                engine="pyscf",
                executable="python",
                description="PySCF DFT calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_opt",
                engine="pyscf",
                executable="python",
                description="PySCF geometry optimization",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_freq",
                engine="pyscf",
                executable="python",
                description="PySCF frequency calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_mp2",
                engine="pyscf",
                executable="python",
                description="PySCF MP2 calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_ccsd",
                engine="pyscf",
                executable="python",
                description="PySCF CCSD calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_casscf",
                engine="pyscf",
                executable="python",
                description="PySCF CASSCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_casci",
                engine="pyscf",
                executable="python",
                description="PySCF CASCI calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="pyscf_tddft",
                engine="pyscf",
                executable="python",
                description="PySCF TD-DFT calculation",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return PySCF chain handler."""
        from .handler import pyscf_chain_handler
        return pyscf_chain_handler

    def get_recipe_class(self):
        """Return PySCF recipe class."""
        from .recipe import PySCFRecipe
        return PySCFRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return PySCF GEN→SPEC mappings."""
        return {
            "GEN_SCF": "pyscf_scf",
            "GEN_DFT": "pyscf_dft",
            "GEN_OPT": "pyscf_opt",
            "GEN_FREQ": "pyscf_freq",
            "GEN_MP2": "pyscf_mp2",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where PySCF differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """PySCF uses isolated workdir (default)."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """PySCF capabilities."""
        return {
            "scf", "dft", "opt", "freq",
            "mp2", "ccsd", "casscf", "casci", "tddft",
            "molecular",  # PySCF is primarily molecular
            "chain",  # Supports chain execution
            "python_native",  # Python-based, no external executable
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """All PySCF steps can be skipped if done."""
        return True

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify PySCF errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf not converged" in stderr_lower or "convergence" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower or "memoryerror" in stderr_lower:
            return ErrorClass.MEMORY
        if "import" in stderr_lower and "pyscf" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND
        if "keyerror" in stderr_lower or "valueerror" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """PySCF artifact patterns for discovery."""
        return {
            "chkfile": "*.chk",
            "output": "*.out",
            "molden": "*.molden",
            "cube": "*.cube",
        }
```

### Step 3: Move Handler to handler.py

**Create file**: `src/quantumvitas/drivers/pyscf/handler.py`

**Copy** the `pyscf_chain_handler` function from `handlers.py` (lines 757-885).

```python
"""PySCF chain handler.

This module contains the chain handler for PySCF calculations.
PySCF is Python-native, so the handler executes Python scripts
that call PySCF functions directly.
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


def pyscf_chain_handler(job: Job, context: StepContext) -> JobResult:
    """Handle PySCF chain execution.

    PySCF is a Python library, so calculations are executed
    by running Python scripts. This handler manages:
    - Script generation from templates
    - Python script execution
    - Output parsing
    - Chain state management

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    # [COPY EXISTING FUNCTION BODY FROM handlers.py lines 757-885]
    # The function body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

### Step 4: Move Recipe to recipe.py

**Create file**: `src/quantumvitas/drivers/pyscf/recipe.py`

**Copy** the `PySCFRecipe` class from `recipes.py` (lines 583-692).

```python
"""PySCF recipe for input staging.

This module handles the preparation of PySCF calculation scripts.
"""

import logging
from pathlib import Path
from typing import Any

from quantumvitas.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class PySCFRecipe(BaseRecipe):
    """Recipe for staging PySCF inputs.

    Handles:
    - Python script generation
    - Molecule definition from structure
    - Method/basis specification
    - Output file configuration
    """

    # [COPY EXISTING CLASS BODY FROM recipes.py lines 583-692]
    # The class body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

### Step 5: Create __init__.py

**Create file**: `src/quantumvitas/drivers/pyscf/__init__.py`

```python
"""PySCF driver bundle.

This package provides the PySCF engine driver for QuantumVitas.
It handles all PySCF quantum chemistry calculations including
HF, DFT, post-HF, and multiconfigurational methods.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import PySCFDriver

# Register driver at import time
DriverRegistry.register(PySCFDriver())

__all__ = ["PySCFDriver"]
```

### Step 6: Update drivers/__init__.py

**File**: `src/quantumvitas/drivers/__init__.py`

**Add** PySCF import:

```python
from quantumvitas.drivers import qe_shim
from quantumvitas.drivers import vasp
from quantumvitas.drivers import orca
from quantumvitas.drivers import pyscf  # ADD THIS LINE
```

### Step 7: Remove PySCF from Kernel Files

**handlers.py**: Remove `pyscf_chain_handler` (lines 757-885)

**recipes.py**: Remove `PySCFRecipe` (lines 583-692)

**structure_steps.py**: Verify PYSCF_STEP_TYPES uses registry

### Step 8: Create PySCF-Specific Tests

**Create file**: `tests/drivers/pyscf/test_pyscf_driver.py`

```python
"""Tests for PySCF driver bundle."""

import pytest
from quantumvitas.drivers.pyscf import PySCFDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestPySCFDriver:
    """Test PySCFDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = PySCFDriver()
        assert driver.engine_family == "pyscf"
        assert driver.display_name == "PySCF"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = PySCFDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "pyscf_scf" in spec_ids
        assert "pyscf_opt" in spec_ids
        assert "pyscf_mp2" in spec_ids

        for spec in specs:
            assert spec.engine == "pyscf"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = PySCFDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = PySCFDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = PySCFDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "pyscf_scf"
        assert mat_map["GEN_OPT"] == "pyscf_opt"

    def test_python_native_capability(self):
        """PySCF should have python_native capability."""
        driver = PySCFDriver()
        assert "python_native" in driver.get_capabilities()


class TestPySCFRegistration:
    """Test PySCF driver registration."""

    def test_pyscf_registered(self):
        """PySCF should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("pyscf")
        driver = DriverRegistry.get_driver("pyscf")
        assert driver.engine_family == "pyscf"

    def test_pyscf_step_types_registered(self):
        """PySCF step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("pyscf_scf")
        assert DriverRegistry.is_step_type_registered("pyscf_opt")


class TestPySCFIsolation:
    """Gate 3 tests: PySCF isolation from kernel."""

    def test_handlers_no_pyscf_handler(self):
        """handlers.py should not contain pyscf_chain_handler."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/handlers.py").read_text()

        assert "def pyscf_chain_handler" not in source

    def test_recipes_no_pyscf_recipe(self):
        """recipes.py should not contain PySCFRecipe."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/recipes.py").read_text()

        assert "class PySCFRecipe" not in source
```

### Step 9: Run Tests

```bash
pytest tests/drivers/pyscf/ -v
pytest tests/gates/ -v -k "pyscf"
pytest tests/ -v
```

---

## 5. PR Checklist

- [ ] `drivers/pyscf/` directory created
- [ ] `driver.py` with PySCFDriver class
- [ ] `handler.py` with moved pyscf_chain_handler
- [ ] `recipe.py` with moved PySCFRecipe
- [ ] `__init__.py` with registration
- [ ] PySCF removed from handlers.py
- [ ] PySCF removed from recipes.py
- [ ] PySCF driver tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes

---

## 6. Definition of Done

1. All PySCF code in `drivers/pyscf/`
2. No PySCF-specific code in kernel files
3. PySCF registered via DriverRegistry
4. Chain execution works correctly
5. All existing PySCF tests pass
6. Gate 3 (isolation) tests pass
7. CI green
