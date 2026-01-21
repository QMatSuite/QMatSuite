# VASP Driver Migration Plan

**PR Title**: `feat(drivers): Migrate VASP to driver bundle architecture`

**Priority**: First engine migration (after prereq PRs)

**Complexity**: MEDIUM

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract all VASP-specific code from kernel files into a self-contained driver bundle at `src/quantumvitas/drivers/vasp/`. After this migration:

1. All VASP code lives in `drivers/vasp/`
2. VASP is registered via DriverRegistry
3. Kernel files have no VASP-specific logic
4. All existing VASP functionality preserved
5. Gate 3 (engine isolation) passes for VASP

---

## 2. Code Inventory

### 2.1 Handler Code

**Source**: `src/quantumvitas/execution/handlers.py`

| Function | Lines | Description |
|----------|-------|-------------|
| `vasp_step_handler` | 294-456 | Main VASP step handler (~162 lines) |
| VASP imports | 12-25 | VASP-specific imports |

### 2.2 Recipe Code

**Source**: `src/quantumvitas/execution/recipes.py`

| Class | Lines | Description |
|-------|-------|-------------|
| `VASPRecipe` | 236-334 | Input staging recipe (~98 lines) |
| VASP staging helpers | 800-890 | CHGCAR/WAVECAR staging |

### 2.3 Step Types

**Source**: `src/quantumvitas/workflow/registry.py` (conceptual) and `step_done.py`

```
vasp_scf, vasp_relax, vasp_vc_relax, vasp_md, vasp_bands, vasp_dos,
vasp_static, vasp_neb, vasp_phonon, vasp_elastic, vasp_dielectric
```

### 2.4 Materialization Map

**Source**: `src/quantumvitas/workflow/generalized_steps.py`

```python
("vasp", "GEN_SCF"): "vasp_scf"
("vasp", "GEN_RELAX"): "vasp_relax"
("vasp", "GEN_MD"): "vasp_md"
("vasp", "GEN_BANDS"): "vasp_bands"
("vasp", "GEN_DOS"): "vasp_dos"
```

### 2.5 Additional VASP Logic

**Locations to check**:
- `src/quantumvitas/io/generator/` - VASP input generators (POSCAR, INCAR, KPOINTS, POTCAR)
- `src/quantumvitas/io/parser/` - VASP output parsers (OUTCAR, vasprun.xml)
- `src/quantumvitas/calculation/step_done.py` - VASP done detection

---

## 3. Target Structure

```
src/quantumvitas/drivers/vasp/
├── __init__.py          # Registration (15 lines)
├── driver.py            # VASPDriver class (80 lines)
├── handler.py           # vasp_step_handler (162 lines, moved)
├── recipe.py            # VASPRecipe (98 lines, moved)
├── staging.py           # CHGCAR/WAVECAR staging (90 lines, moved)
└── reference.py         # Reference file resolution (50 lines)
```

**Total**: ~495 lines (mostly moved, not new)

---

## 4. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/quantumvitas/drivers/vasp
touch src/quantumvitas/drivers/vasp/__init__.py
touch src/quantumvitas/drivers/vasp/driver.py
touch src/quantumvitas/drivers/vasp/handler.py
touch src/quantumvitas/drivers/vasp/recipe.py
touch src/quantumvitas/drivers/vasp/staging.py
```

### Step 2: Create driver.py

**Create file**: `src/quantumvitas/drivers/vasp/driver.py`

```python
"""VASP engine driver.

This driver handles all VASP calculations including:
- SCF, relaxation, MD simulations
- Band structure, DOS calculations
- Phonon, elastic, dielectric calculations
- NEB transition state searches
"""

from quantumvitas.core.driver_protocol import (
    BaseEngineDriver,
    StepTypeSpec,
    WorkdirPolicy,
    PreflightRequirement,
    ErrorClass,
)


class VASPDriver(BaseEngineDriver):
    """VASP driver bundle implementing the EngineDriver protocol."""

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "vasp"

    @property
    def display_name(self) -> str:
        return "VASP"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return VASP step type specifications."""
        return [
            StepTypeSpec(
                id="vasp_scf",
                engine="vasp",
                executable="vasp_std",
                description="VASP SCF calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP ionic relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_vc_relax",
                engine="vasp",
                executable="vasp_std",
                description="VASP variable-cell relaxation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_md",
                engine="vasp",
                executable="vasp_std",
                description="VASP molecular dynamics",
                category="calculation",
                supports_restart=True,
            ),
            StepTypeSpec(
                id="vasp_bands",
                engine="vasp",
                executable="vasp_std",
                description="VASP band structure calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_dos",
                engine="vasp",
                executable="vasp_std",
                description="VASP density of states",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_static",
                engine="vasp",
                executable="vasp_std",
                description="VASP static calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_neb",
                engine="vasp",
                executable="vasp_std",
                description="VASP NEB transition state search",
                category="calculation",
                mpi_aware=True,
            ),
            StepTypeSpec(
                id="vasp_phonon",
                engine="vasp",
                executable="vasp_std",
                description="VASP phonon calculation",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_elastic",
                engine="vasp",
                executable="vasp_std",
                description="VASP elastic constants",
                category="calculation",
            ),
            StepTypeSpec(
                id="vasp_dielectric",
                engine="vasp",
                executable="vasp_std",
                description="VASP dielectric properties",
                category="calculation",
            ),
        ]

    def get_handler(self):
        """Return VASP step handler."""
        from .handler import vasp_step_handler
        return vasp_step_handler

    def get_recipe_class(self):
        """Return VASP recipe class."""
        from .recipe import VASPRecipe
        return VASPRecipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return VASP GEN→SPEC mappings."""
        return {
            "GEN_SCF": "vasp_scf",
            "GEN_RELAX": "vasp_relax",
            "GEN_VC_RELAX": "vasp_vc_relax",
            "GEN_MD": "vasp_md",
            "GEN_BANDS": "vasp_bands",
            "GEN_DOS": "vasp_dos",
        }

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where VASP differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """VASP uses cleanup policy (fresh workdir each step)."""
        return WorkdirPolicy.CLEANUP

    def get_capabilities(self) -> set[str]:
        """VASP capabilities."""
        return {
            "scf", "relax", "md", "bands", "dos",
            "phonon", "elastic", "dielectric", "neb",
            "periodic", "mpi", "gpu",
            "charge_continuation", "wfn_continuation",
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """MD steps should not be skipped."""
        if step_type == "vasp_md":
            return False
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """VASP preflight requirements (CHGCAR, WAVECAR)."""
        requirements = []

        # Check step configuration for continuation
        step_config = getattr(step, "config", {}) or {}

        if step_config.get("use_chgcar", False):
            requirements.append(PreflightRequirement(
                artifact_type="CHGCAR",
                source_step=step_config.get("chgcar_source"),
                required=True,
                description="Charge density for continuation",
            ))

        if step_config.get("use_wavecar", False):
            requirements.append(PreflightRequirement(
                artifact_type="WAVECAR",
                source_step=step_config.get("wavecar_source"),
                required=False,  # WAVECAR is optional optimization
                description="Wavefunction for continuation",
            ))

        return requirements

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify VASP errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "scf convergence" in stderr_lower or "electronic convergence" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "out of memory" in stderr_lower or "malloc" in stderr_lower:
            return ErrorClass.MEMORY
        if "timeout" in stderr_lower or exit_code == 124:
            return ErrorClass.TIMEOUT
        if "potcar" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "incar" in stderr_lower and "error" in stderr_lower:
            return ErrorClass.INPUT_ERROR

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """VASP artifact patterns for discovery."""
        return {
            "CHGCAR": "CHGCAR*",
            "WAVECAR": "WAVECAR",
            "OUTCAR": "OUTCAR",
            "vasprun": "vasprun.xml",
            "CONTCAR": "CONTCAR",
            "OSZICAR": "OSZICAR",
            "DOSCAR": "DOSCAR",
            "EIGENVAL": "EIGENVAL",
            "PROCAR": "PROCAR",
        }

    def find_latest_artifact(self, workdir, artifact_type: str):
        """Find latest artifact in workdir."""
        from pathlib import Path
        import glob

        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = sorted(
            Path(workdir).glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return matches[0] if matches else None
```

### Step 3: Move Handler to handler.py

**Create file**: `src/quantumvitas/drivers/vasp/handler.py`

**Copy** the `vasp_step_handler` function from `handlers.py` (lines 294-456).

**Update imports** at top of file:

```python
"""VASP step handler.

This module contains the main handler for VASP step execution.
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

# Keep existing imports from the handler code
from quantumvitas.core.job import Job
from quantumvitas.core.step_context import StepContext
from quantumvitas.core.job_result import JobResult

# Import staging utilities
from .staging import stage_chgcar, stage_wavecar, stage_potcar
from .reference import resolve_reference_step

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def vasp_step_handler(job: Job, context: StepContext) -> JobResult:
    """Handle VASP step execution.

    This is the main entry point for all VASP calculations.
    It handles:
    - Input staging (POSCAR, INCAR, KPOINTS, POTCAR)
    - Reference file copying (CHGCAR, WAVECAR)
    - VASP execution
    - Output collection

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    # [COPY EXISTING FUNCTION BODY FROM handlers.py lines 294-456]
    # The function body remains EXACTLY the same
    # Only update imports to use local modules (.staging, .reference)
    pass  # Placeholder - copy actual code
```

**CRITICAL**: Copy the EXACT function body. Do not modify logic.

### Step 4: Move Recipe to recipe.py

**Create file**: `src/quantumvitas/drivers/vasp/recipe.py`

**Copy** the `VASPRecipe` class from `recipes.py` (lines 236-334).

```python
"""VASP recipe for input staging.

This module handles the preparation of VASP input files.
"""

import logging
from pathlib import Path
from typing import Any

from quantumvitas.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class VASPRecipe(BaseRecipe):
    """Recipe for staging VASP inputs.

    Handles:
    - POSCAR generation from structure
    - INCAR generation from parameters
    - KPOINTS generation
    - POTCAR linking/copying
    - Reference file staging (CHGCAR, WAVECAR)
    """

    # [COPY EXISTING CLASS BODY FROM recipes.py lines 236-334]
    # The class body remains EXACTLY the same
    pass  # Placeholder - copy actual code
```

**CRITICAL**: Copy the EXACT class body. Do not modify logic.

### Step 5: Create staging.py

**Create file**: `src/quantumvitas/drivers/vasp/staging.py`

**Extract** CHGCAR/WAVECAR staging functions from `recipes.py` (lines 800-890).

```python
"""VASP file staging utilities.

This module handles staging of continuation files:
- CHGCAR (charge density)
- WAVECAR (wavefunctions)
- POTCAR (pseudopotentials)
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def stage_chgcar(
    source_dir: Path,
    target_dir: Path,
    source_step: Optional[str] = None,
) -> bool:
    """Stage CHGCAR from source to target directory.

    Args:
        source_dir: Directory containing source CHGCAR
        target_dir: Directory to copy CHGCAR to
        source_step: Optional step name for logging

    Returns:
        True if CHGCAR was staged, False otherwise
    """
    # [COPY/EXTRACT FROM recipes.py]
    chgcar_path = source_dir / "CHGCAR"
    if not chgcar_path.exists():
        logger.warning(f"CHGCAR not found in {source_dir}")
        return False

    target_path = target_dir / "CHGCAR"
    shutil.copy2(chgcar_path, target_path)
    logger.info(f"Staged CHGCAR from {source_dir} to {target_dir}")
    return True


def stage_wavecar(
    source_dir: Path,
    target_dir: Path,
    source_step: Optional[str] = None,
) -> bool:
    """Stage WAVECAR from source to target directory.

    Args:
        source_dir: Directory containing source WAVECAR
        target_dir: Directory to copy WAVECAR to
        source_step: Optional step name for logging

    Returns:
        True if WAVECAR was staged, False otherwise
    """
    # [COPY/EXTRACT FROM recipes.py]
    wavecar_path = source_dir / "WAVECAR"
    if not wavecar_path.exists():
        logger.debug(f"WAVECAR not found in {source_dir} (optional)")
        return False

    target_path = target_dir / "WAVECAR"
    shutil.copy2(wavecar_path, target_path)
    logger.info(f"Staged WAVECAR from {source_dir} to {target_dir}")
    return True


def stage_potcar(
    elements: list[str],
    target_dir: Path,
    potcar_dir: Optional[Path] = None,
) -> bool:
    """Stage POTCAR for given elements.

    Args:
        elements: List of element symbols
        target_dir: Directory to write POTCAR
        potcar_dir: Directory containing POTCAR files

    Returns:
        True if POTCAR was staged, False otherwise
    """
    # [COPY/EXTRACT FROM recipes.py or handlers.py]
    # Implementation depends on existing POTCAR handling
    pass
```

### Step 6: Create reference.py

**Create file**: `src/quantumvitas/drivers/vasp/reference.py`

```python
"""VASP reference step resolution.

This module handles finding reference steps for continuation.
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from quantumvitas.core.step_context import StepContext

logger = logging.getLogger(__name__)


def resolve_reference_step(
    context: "StepContext",
    artifact_type: str,
    explicit_source: Optional[str] = None,
) -> Optional[Path]:
    """Resolve reference step directory for artifact.

    Args:
        context: Step context with calculation info
        artifact_type: Type of artifact (CHGCAR, WAVECAR)
        explicit_source: Explicitly specified source step

    Returns:
        Path to source directory, or None if not found
    """
    # If explicit source specified, use it
    if explicit_source:
        step_dir = context.get_step_dir(explicit_source)
        if step_dir and step_dir.exists():
            return step_dir
        logger.warning(f"Explicit source step '{explicit_source}' not found")

    # Auto-resolve: find previous step with artifact
    for prev_step in reversed(context.completed_steps):
        step_dir = context.get_step_dir(prev_step)
        if step_dir:
            artifact_path = step_dir / artifact_type
            if artifact_path.exists():
                logger.debug(f"Auto-resolved {artifact_type} from {prev_step}")
                return step_dir

    return None
```

### Step 7: Create __init__.py

**Create file**: `src/quantumvitas/drivers/vasp/__init__.py`

```python
"""VASP driver bundle.

This package provides the VASP engine driver for QuantumVitas.
It handles all VASP calculations including SCF, relaxation, MD,
band structure, DOS, and various property calculations.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import VASPDriver

# Register driver at import time
DriverRegistry.register(VASPDriver())

__all__ = ["VASPDriver"]
```

### Step 8: Update drivers/__init__.py

**File**: `src/quantumvitas/drivers/__init__.py`

**Add** VASP import:

```python
# Import all driver packages to trigger registration
from quantumvitas.drivers import qe_shim
from quantumvitas.drivers import vasp  # ADD THIS LINE
```

### Step 9: Remove VASP from handlers.py

**File**: `src/quantumvitas/execution/handlers.py`

**Remove**:
1. VASP-specific imports (if any become unused)
2. `vasp_step_handler` function (lines 294-456)
3. Any VASP helper functions only used by `vasp_step_handler`

**Keep**:
- The registry-based dispatch (from PR 2)
- Any utility functions used by multiple engines

### Step 10: Remove VASP from recipes.py

**File**: `src/quantumvitas/execution/recipes.py`

**Remove**:
1. `VASPRecipe` class (lines 236-334)
2. VASP staging helpers (lines 800-890)
3. VASP-specific imports (if unused)

**Keep**:
- `BaseRecipe` class
- Registry-based dispatch (from PR 2)
- Utility functions used by multiple recipes

### Step 11: Clean up step_done.py

**File**: `src/quantumvitas/calculation/step_done.py`

**Verify** that VASP_STEP_TYPES is now provided by registry (from PR 2).

**Remove** any remaining VASP-specific hardcoding.

### Step 12: Create VASP-Specific Tests

**Create file**: `tests/drivers/vasp/test_vasp_driver.py`

```python
"""Tests for VASP driver bundle."""

import pytest
from quantumvitas.drivers.vasp import VASPDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestVASPDriver:
    """Test VASPDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = VASPDriver()
        assert driver.engine_family == "vasp"
        assert driver.display_name == "VASP"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = VASPDriver()
        specs = driver.get_step_type_specs()

        # Check required step types exist
        spec_ids = {s.id for s in specs}
        assert "vasp_scf" in spec_ids
        assert "vasp_relax" in spec_ids
        assert "vasp_md" in spec_ids
        assert "vasp_bands" in spec_ids

        # Check all specs have correct engine
        for spec in specs:
            assert spec.engine == "vasp"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = VASPDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = VASPDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None
        assert hasattr(recipe_class, "stage")

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = VASPDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "vasp_scf"
        assert mat_map["GEN_RELAX"] == "vasp_relax"
        assert mat_map["GEN_MD"] == "vasp_md"

    def test_workdir_policy_cleanup(self):
        """VASP should use CLEANUP policy."""
        driver = VASPDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.CLEANUP

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = VASPDriver()
        assert driver.supports_incremental_skip("vasp_scf") is True
        assert driver.supports_incremental_skip("vasp_md") is False


class TestVASPRegistration:
    """Test VASP driver registration."""

    def test_vasp_registered(self):
        """VASP should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("vasp")
        driver = DriverRegistry.get_driver("vasp")
        assert driver.engine_family == "vasp"

    def test_vasp_step_types_registered(self):
        """VASP step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("vasp_scf")
        assert DriverRegistry.is_step_type_registered("vasp_relax")
        assert DriverRegistry.is_step_type_registered("vasp_md")

    def test_vasp_handler_via_registry(self):
        """Should get VASP handler via registry."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("vasp_scf")
        assert callable(handler)

    def test_vasp_recipe_via_registry(self):
        """Should get VASP recipe via registry."""
        import quantumvitas.drivers

        recipe_class = DriverRegistry.get_recipe_class("vasp")
        assert recipe_class is not None


class TestVASPIsolation:
    """Gate 3 tests: VASP isolation from kernel."""

    def test_handlers_no_vasp_handler(self):
        """handlers.py should not contain vasp_step_handler."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/handlers.py").read_text()

        assert "def vasp_step_handler" not in source, (
            "vasp_step_handler should be moved to drivers/vasp/handler.py"
        )

    def test_recipes_no_vasp_recipe(self):
        """recipes.py should not contain VASPRecipe."""
        from pathlib import Path
        source = Path("src/quantumvitas/execution/recipes.py").read_text()

        assert "class VASPRecipe" not in source, (
            "VASPRecipe should be moved to drivers/vasp/recipe.py"
        )

    def test_no_vasp_hardcoding_in_kernel(self):
        """Kernel files should not have VASP-specific logic."""
        from pathlib import Path

        kernel_files = [
            "src/quantumvitas/core/calc_identity.py",
            "src/quantumvitas/calculation/step_done.py",
            "src/quantumvitas/calculation/structure_steps.py",
        ]

        for filepath in kernel_files:
            source = Path(filepath).read_text()
            # Should not have hardcoded VASP step types
            assert "VASP_STEP_TYPES" not in source or "get_step_types" in source, (
                f"{filepath} should not have hardcoded VASP_STEP_TYPES"
            )
```

### Step 13: Run Tests

```bash
# VASP driver tests
pytest tests/drivers/vasp/ -v

# Gate 3 isolation tests
pytest tests/gates/ -v -k "vasp"

# Full test suite
pytest tests/ -v
```

**Expected**: All tests pass

---

## 5. Semantic Preservation Checklist

| Semantic | Verification |
|----------|--------------|
| VASP handler behavior unchanged | Compare handler output before/after |
| VASP recipe staging unchanged | Test POSCAR, INCAR, KPOINTS, POTCAR |
| CHGCAR continuation works | Test with use_chgcar=True |
| WAVECAR continuation works | Test with use_wavecar=True |
| MD execution unchanged | Test vasp_md step |
| NEB execution unchanged | Test vasp_neb step |
| Done detection unchanged | Test step completion detection |

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Handler logic broken | Low | High | Copy exactly, extensive testing |
| Import paths wrong | Medium | Medium | Careful import updates |
| POTCAR staging broken | Medium | High | Test with real POTCAR directory |
| Reference resolution broken | Low | High | Test CHGCAR/WAVECAR staging |

---

## 7. PR Checklist

- [ ] `drivers/vasp/` directory created
- [ ] `driver.py` with VASPDriver class
- [ ] `handler.py` with moved vasp_step_handler
- [ ] `recipe.py` with moved VASPRecipe
- [ ] `staging.py` with CHGCAR/WAVECAR staging
- [ ] `reference.py` with reference resolution
- [ ] `__init__.py` with registration
- [ ] VASP removed from handlers.py
- [ ] VASP removed from recipes.py
- [ ] VASP driver tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes
- [ ] CI green

---

## 8. Definition of Done

1. All VASP code in `drivers/vasp/`
2. No VASP-specific code in kernel files
3. VASP registered via DriverRegistry
4. All VASP step types work correctly
5. CHGCAR/WAVECAR continuation works
6. All existing VASP tests pass
7. Gate 3 (isolation) tests pass
8. CI green
