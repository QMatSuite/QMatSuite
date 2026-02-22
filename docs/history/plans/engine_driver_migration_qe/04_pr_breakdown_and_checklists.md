# QE Migration: PR Breakdown and Checklists

> This document provides step-by-step checklists for each PR in the QE migration.
> Designed for execution by automated agents (Cursor Auto) with minimal judgment required.

---

## PR 1: QE Driver Bundle Foundation

**Scope**: Create the `drivers/qe/` directory structure with minimal driver registration.
**Risk**: LOW - Only creates new files, no behavior change.

### Pre-flight Checks
- [ ] All tests pass before starting: `pytest tests/`
- [ ] No uncommitted changes: `git status`

### Implementation Checklist

#### Step 1.1: Create directory structure
- [ ] Create `src/qmatsuite/drivers/qe/`
- [ ] Create `src/qmatsuite/drivers/qe/__init__.py` (empty for now)
- [ ] Create `src/qmatsuite/drivers/qe/driver.py` (stub)
- [ ] Create `src/qmatsuite/drivers/qe/step_types.py` (empty list)

#### Step 1.2: Create minimal driver
```python
# File: src/qmatsuite/drivers/qe/driver.py
"""QE Driver (stub for migration)."""

from qmatsuite.core.driver_protocol import BaseEngineDriver, StepTypeSpec, WorkdirPolicy


class QEDriver(BaseEngineDriver):
    """QE driver stub - delegates to qe_shim during migration."""

    @property
    def engine_family(self) -> str:
        return "qe"

    @property
    def display_name(self) -> str:
        return "Quantum ESPRESSO"

    @property
    def driver_api_version(self) -> str:
        return "2.0.0-alpha"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        # Delegate to shim for now
        from qmatsuite.drivers.qe_shim import QELegacyDriver
        return QELegacyDriver().get_step_type_specs()

    def get_handler(self):
        from qmatsuite.drivers.qe_shim import QELegacyDriver
        return QELegacyDriver().get_handler()

    def get_recipe_class(self):
        from qmatsuite.drivers.qe_shim import QELegacyDriver
        return QELegacyDriver().get_recipe_class()

    def get_materialization_map(self) -> dict[str, str]:
        from qmatsuite.drivers.qe_shim import QELegacyDriver
        return QELegacyDriver().get_materialization_map()

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.SHARED
```

#### Step 1.3: Update `__init__.py` to NOT register yet
```python
# File: src/qmatsuite/drivers/qe/__init__.py
"""QE Driver Bundle (migration in progress)."""

from .driver import QEDriver

__all__ = ["QEDriver"]

# NOTE: Do NOT register here yet - still using qe_shim
# Registration will happen in PR 2 after step types are moved
```

### Validation
- [ ] Directory structure exists
- [ ] `from qmatsuite.drivers.qe import QEDriver` works
- [ ] All existing tests pass: `pytest tests/`

### Rollback
```bash
rm -rf src/qmatsuite/drivers/qe/
```

---

## PR 2: Move Step Type Specifications

**Scope**: Move QE step type specs from `qe_shim` and `workflow/registry.py` to `drivers/qe/step_types.py`.
**Risk**: MEDIUM - Changes step type source but maintains identical specs.

### Pre-flight Checks
- [ ] PR 1 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 2.1: Create step_types.py with all QE specs
- [ ] Copy step type specs from `drivers/qe_shim/__init__.py` (20 types)
- [ ] Add any additional specs from `workflow/registry.py` that are QE-specific
- [ ] Ensure all specs use `StepTypeSpec` from `driver_protocol`

```python
# File: src/qmatsuite/drivers/qe/step_types.py
"""QE step type specifications."""

from qmatsuite.core.driver_protocol import StepTypeSpec


QE_STEP_TYPE_SPECS: list[StepTypeSpec] = [
    StepTypeSpec(
        id="qe_scf",
        engine="qe",
        executable="pw.x",
        description="QE SCF calculation",
    ),
    # ... all 20+ step types
]
```

#### Step 2.2: Update QEDriver to use local step_types
```python
# In drivers/qe/driver.py
def get_step_type_specs(self) -> list[StepTypeSpec]:
    from .step_types import QE_STEP_TYPE_SPECS
    return QE_STEP_TYPE_SPECS
```

#### Step 2.3: Update qe_shim to import from qe driver
```python
# In drivers/qe_shim/__init__.py
def get_step_type_specs(self) -> list[StepTypeSpec]:
    # Delegate to new driver
    from qmatsuite.drivers.qe.step_types import QE_STEP_TYPE_SPECS
    return QE_STEP_TYPE_SPECS
```

### Validation
- [ ] `from qmatsuite.drivers.qe.step_types import QE_STEP_TYPE_SPECS` works
- [ ] `len(QE_STEP_TYPE_SPECS) >= 20`
- [ ] All step types have required fields (id, engine, executable)
- [ ] All existing tests pass: `pytest tests/`
- [ ] Specific test: `pytest tests/unit/test_driver_registry.py -v`

### Rollback
```bash
git checkout HEAD~1 -- src/qmatsuite/drivers/qe/step_types.py
git checkout HEAD~1 -- src/qmatsuite/drivers/qe/driver.py
git checkout HEAD~1 -- src/qmatsuite/drivers/qe_shim/__init__.py
```

---

## PR 3: Move QERecipe

**Scope**: Move `QERecipe` from `execution/recipes.py` to `drivers/qe/recipe.py`.
**Risk**: LOW - Well-isolated code with clear interface.

### Pre-flight Checks
- [ ] PR 2 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 3.1: Create recipe.py
- [ ] Copy `QERecipe` class from `execution/recipes.py`
- [ ] Copy related imports
- [ ] Ensure all dependencies are available

```python
# File: src/qmatsuite/drivers/qe/recipe.py
"""QE Recipe: Directory-state, step-run model."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from qmatsuite.execution.job_graph import Job, JobGraph
from qmatsuite.execution.recipes import BaseRecipe

if TYPE_CHECKING:
    from qmatsuite.calculation.step import Step


class QERecipe(BaseRecipe):
    """QE-Recipe: Directory-state, step-run model.

    Creates one job per step. Jobs share the same working directory
    and scratch directory (outdir/).
    """

    # ... implementation from execution/recipes.py
```

#### Step 3.2: Update driver to use local recipe
```python
# In drivers/qe/driver.py
def get_recipe_class(self):
    from .recipe import QERecipe
    return QERecipe
```

#### Step 3.3: Add re-export in execution/recipes.py
```python
# At end of execution/recipes.py
# Backward-compatibility re-export
def __getattr__(name: str):
    if name == "QERecipe":
        from qmatsuite.drivers.qe.recipe import QERecipe
        return QERecipe
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

### Validation
- [ ] `from qmatsuite.drivers.qe.recipe import QERecipe` works
- [ ] `from qmatsuite.execution.recipes import QERecipe` still works (backward compat)
- [ ] All existing tests pass: `pytest tests/`
- [ ] Specific test: `pytest tests/unit/execution/test_recipes.py -v`

### Rollback
```bash
rm src/qmatsuite/drivers/qe/recipe.py
git checkout HEAD~1 -- src/qmatsuite/drivers/qe/driver.py
git checkout HEAD~1 -- src/qmatsuite/execution/recipes.py
```

---

## PR 4: Move QE Handler

**Scope**: Move `qe_step_handler` from `execution/handlers.py` to `drivers/qe/handler.py`.
**Risk**: MEDIUM - Handler is central to execution path.

### Pre-flight Checks
- [ ] PR 3 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 4.1: Create handler.py
- [ ] Copy `qe_step_handler` function from `execution/handlers.py`
- [ ] Copy `handle_qe_relax_output` function
- [ ] Copy `_get_step_input_from_calculation_yaml` helper
- [ ] Copy related imports

```python
# File: src/qmatsuite/drivers/qe/handler.py
"""QE step handler."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from qmatsuite.execution.job_graph import Job
from qmatsuite.execution.executor import JobResult

if TYPE_CHECKING:
    from qmatsuite.calculation.calculation import Calculation
    from qmatsuite.engine.registry import EngineRegistry


def qe_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """Execute a single QE/Wannier step job."""
    # ... implementation from execution/handlers.py
```

#### Step 4.2: Update driver to use local handler
```python
# In drivers/qe/driver.py
def get_handler(self):
    from .handler import qe_step_handler
    return qe_step_handler
```

#### Step 4.3: Update execution/handlers.py
```python
# In execution/handlers.py - update import and fallback
def qe_step_handler(...):
    """DEPRECATED: Use qmatsuite.drivers.qe.handler.qe_step_handler"""
    from qmatsuite.drivers.qe.handler import qe_step_handler as _qe_handler
    return _qe_handler(...)
```

### Validation
- [ ] `from qmatsuite.drivers.qe.handler import qe_step_handler` works
- [ ] QE calculation runs successfully
- [ ] All existing tests pass: `pytest tests/`
- [ ] Specific test: `pytest tests/unit/execution/test_handlers.py -v`

### Rollback
```bash
rm src/qmatsuite/drivers/qe/handler.py
git checkout HEAD~1 -- src/qmatsuite/drivers/qe/driver.py
git checkout HEAD~1 -- src/qmatsuite/execution/handlers.py
```

---

## PR 5: Move QE Engine Files

**Scope**: Move all `core/engines/qe*.py` files to `drivers/qe/engine/`.
**Risk**: MEDIUM - Many files but well-isolated.

### Pre-flight Checks
- [ ] PR 4 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 5.1: Create engine/ subdirectory
- [ ] Create `src/qmatsuite/drivers/qe/engine/`
- [ ] Create `src/qmatsuite/drivers/qe/engine/__init__.py`

#### Step 5.2: Move engine files
- [ ] Move `core/engines/qe.py` → `drivers/qe/engine/qe_engine.py`
- [ ] Move `core/engines/qe_calculation.py` → `drivers/qe/engine/qe_calculation.py`
- [ ] Move `core/engines/qe_installation.py` → `drivers/qe/engine/qe_installation.py`
- [ ] Move `core/engines/qe_resolver.py` → `drivers/qe/engine/qe_resolver.py`
- [ ] Move `core/engines/qe_binary_locator.py` → `drivers/qe/engine/qe_binary_locator.py`
- [ ] Move `core/engines/qe_diagnostics.py` → `drivers/qe/engine/qe_diagnostics.py`
- [ ] Move `core/engines/qe_pseudopotentials.py` → `drivers/qe/engine/qe_pseudopotentials.py`

#### Step 5.3: Update internal imports in moved files
For each moved file, update relative imports:
```python
# Example: In qe_engine.py, change:
from .qe_installation import QEInstallation
# To:
from qmatsuite.drivers.qe.engine.qe_installation import QEInstallation
```

#### Step 5.4: Add re-exports in core/engines/
```python
# In core/engines/__init__.py - add backward compat exports
def __getattr__(name: str):
    if name in ("QuantumEspressoEngine", "QEInstallation", ...):
        from qmatsuite.drivers.qe.engine import ...
        return ...
    raise AttributeError(...)
```

### Validation
- [ ] All moved files import correctly
- [ ] `from qmatsuite.drivers.qe.engine import QuantumEspressoEngine` works
- [ ] `from qmatsuite.core.engines import QuantumEspressoEngine` still works
- [ ] All existing tests pass: `pytest tests/`
- [ ] QE execution works end-to-end

### Rollback
```bash
# Move files back
mv src/qmatsuite/drivers/qe/engine/qe_engine.py src/qmatsuite/core/engines/qe.py
# ... repeat for each file
rm -rf src/qmatsuite/drivers/qe/engine/
```

---

## PR 6: Move I/O Layer

**Scope**: Move QE I/O models, parser, and generator to `drivers/qe/io/`.
**Risk**: MEDIUM - Public API must be preserved via re-exports.

### Pre-flight Checks
- [ ] PR 5 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 6.1: Create io/ subdirectory
- [ ] Create `src/qmatsuite/drivers/qe/io/`
- [ ] Create `src/qmatsuite/drivers/qe/io/__init__.py`

#### Step 6.2: Move I/O files
- [ ] Move `io/model.py` → `drivers/qe/io/model.py`
- [ ] Move `io/parser/qe_parser.py` → `drivers/qe/io/parser.py`
- [ ] Move `io/generator/qe_generator.py` → `drivers/qe/io/generator.py`
- [ ] Copy QE parts of `io/structure_io.py` → `drivers/qe/io/structure_io.py`

#### Step 6.3: Update io/__init__.py with re-exports
```python
# In io/__init__.py
# Backward compatibility re-exports
from qmatsuite.drivers.qe.io.model import (
    QEModule, QECardType, QENamelist, QECard, QEInput
)
from qmatsuite.drivers.qe.io.parser import QEInputParser
from qmatsuite.drivers.qe.io.generator import QEInputGenerator
from qmatsuite.drivers.qe.io.structure_io import structure_from_qe_input

__all__ = [
    "QEModule", "QECardType", "QENamelist", "QECard", "QEInput",
    "QEInputParser", "QEInputGenerator",
    "structure_from_qe_input",
    # ... other non-QE exports
]
```

### Validation
- [ ] `from qmatsuite.io import QEModule, QEInput` works (backward compat)
- [ ] `from qmatsuite.drivers.qe.io import QEModule, QEInput` works
- [ ] All existing tests pass: `pytest tests/`
- [ ] Specific test: `pytest tests/unit/io/test_qe_*.py -v`

### Rollback
```bash
# Restore original io/ files from git
git checkout HEAD~1 -- src/qmatsuite/io/
rm -rf src/qmatsuite/drivers/qe/io/
```

---

## PR 7: Move IR Backend

**Scope**: Move `ir/backends/qe/` to `drivers/qe/ir/`.
**Risk**: LOW - Well-isolated module.

### Pre-flight Checks
- [ ] PR 6 merged
- [ ] All tests pass: `pytest tests/`

### Implementation Checklist

#### Step 7.1: Create ir/ subdirectory
- [ ] Create `src/qmatsuite/drivers/qe/ir/`
- [ ] Create `src/qmatsuite/drivers/qe/ir/__init__.py`

#### Step 7.2: Move IR files
- [ ] Move `ir/backends/qe/mapping.py` → `drivers/qe/ir/mapping.py`
- [ ] Move `ir/backends/qe/__init__.py` → `drivers/qe/ir/__init__.py`

#### Step 7.3: Update imports
```python
# In ir/backends/qe/__init__.py - redirect to new location
from qmatsuite.drivers.qe.ir.mapping import (
    ir_to_qe_param,
    qe_to_ir_param,
    ir_patch_to_qe_patch,
    qe_yaml_to_ir_yaml,
    # ... all exports
)
```

### Validation
- [ ] `from qmatsuite.ir.backends.qe import ir_to_qe_param` works
- [ ] `from qmatsuite.drivers.qe.ir import ir_to_qe_param` works
- [ ] IR compilation produces correct QE input
- [ ] All existing tests pass: `pytest tests/`

### Rollback
```bash
git checkout HEAD~1 -- src/qmatsuite/ir/backends/qe/
rm -rf src/qmatsuite/drivers/qe/ir/
```

---

## PR 8: Move Parsers and Data

**Scope**: Move `parsers/qe/` and `data/qe_metadata.py` to driver bundle.
**Risk**: LOW - Well-isolated modules.

### Implementation Checklist

#### Step 8.1: Create parsers/ and data/ subdirectories
- [ ] Create `src/qmatsuite/drivers/qe/parsers/`
- [ ] Create `src/qmatsuite/drivers/qe/data/`

#### Step 8.2: Move files
- [ ] Move `parsers/qe/trajectory.py` → `drivers/qe/parsers/trajectory.py`
- [ ] Move `data/qe_metadata.py` → `drivers/qe/data/qe_metadata.py`

#### Step 8.3: Update parser registration
```python
# In drivers/qe/parsers/trajectory.py
# Ensure @register_parser decorator still works
from qmatsuite.parsers.registry import register_parser

@register_parser("qe", "trajectory")
class QETrajectoryParser:
    ...
```

### Validation
- [ ] Parser registration works
- [ ] QE trajectory parsing works
- [ ] All existing tests pass: `pytest tests/`

---

## PR 9: Register QE Driver (Replace Shim)

**Scope**: Register QE driver properly, disable shim registration.
**Risk**: MEDIUM - Changes registration source.

### Implementation Checklist

#### Step 9.1: Update drivers/qe/__init__.py to register
```python
# In drivers/qe/__init__.py
from qmatsuite.core.driver_registry import DriverRegistry
from .driver import QEDriver

# Register on import
DriverRegistry.register(QEDriver())
```

#### Step 9.2: Disable shim registration
```python
# In drivers/qe_shim/__init__.py
# Comment out or remove:
# DriverRegistry.register(QELegacyDriver())
```

#### Step 9.3: Update drivers/__init__.py
```python
# Ensure qe is imported INSTEAD OF qe_shim
from qmatsuite.drivers import qe  # NOT qe_shim
```

### Validation
- [ ] `DriverRegistry.get_driver("qe")` returns QEDriver instance
- [ ] All QE operations work
- [ ] All existing tests pass: `pytest tests/`

---

## PR 10: Kernel Cleanup - Remove QE Defaults

**Scope**: Remove QE defaults and fallbacks from kernel code.
**Risk**: HIGH - Breaking change for legacy code without explicit engine.

### Implementation Checklist

#### Step 10.1: Remove default engine from step.py
```python
# In calculation/step.py, change:
engine: str = "qe"
# To:
engine: Optional[str] = None
```

#### Step 10.2: Add validation for engine field
```python
# In Step class
def __post_init__(self):
    if self.engine is None:
        raise ValueError("Step requires explicit 'engine' field")
```

#### Step 10.3: Remove runner fallbacks
```python
# In calculation/runner.py, remove:
if not engine_family:
    engine_family = "qe"  # Default

# Replace with:
if not engine_family:
    raise ValueError("Calculation requires explicit engine_family")
```

#### Step 10.4: Remove calc_identity W90 mapping
```python
# In core/calc_identity.py, remove:
if engine == "w90" or step_type in ("w90_run", "w90_preproc"):
    engine = "qe"
```

### Validation
- [ ] Creating Step without engine raises error
- [ ] Tests with explicit engine pass
- [ ] Legacy tests may need updating
- [ ] All updated tests pass: `pytest tests/`

### Rollback
```bash
git checkout HEAD~1 -- src/qmatsuite/calculation/step.py
git checkout HEAD~1 -- src/qmatsuite/calculation/runner.py
git checkout HEAD~1 -- src/qmatsuite/core/calc_identity.py
```

---

## PR 11: Final Cleanup

**Scope**: Delete shim, remove backward compat re-exports (optional), update docs.
**Risk**: LOW - Cleanup only.

### Implementation Checklist

#### Step 11.1: Delete qe_shim
- [ ] Remove `src/qmatsuite/drivers/qe_shim/` directory

#### Step 11.2: Delete legacy engine files (if re-exports work)
- [ ] Optionally remove files from `core/engines/` that are re-exports only

#### Step 11.3: Update documentation
- [ ] Update any docs referencing old file locations
- [ ] Add migration guide for users

### Validation
- [ ] No imports from deleted locations
- [ ] All tests pass: `pytest tests/`
- [ ] Documentation accurate

---

## Summary: PR Order and Dependencies

```
PR 1: Foundation ──────────────┐
                               │
PR 2: Step Types ──────────────┼──────┐
                               │      │
PR 3: Recipe ──────────────────┼──────┼──────┐
                               │      │      │
PR 4: Handler ─────────────────┼──────┼──────┼──────┐
                               │      │      │      │
PR 5: Engine Files ────────────┴──────┴──────┴──────┤
                                                    │
PR 6: I/O Layer ────────────────────────────────────┤
                                                    │
PR 7: IR Backend ───────────────────────────────────┤
                                                    │
PR 8: Parsers/Data ─────────────────────────────────┤
                                                    │
PR 9: Driver Registration ──────────────────────────┴──────┐
                                                           │
PR 10: Kernel Cleanup ─────────────────────────────────────┤
                                                           │
PR 11: Final Cleanup ──────────────────────────────────────┘
```
