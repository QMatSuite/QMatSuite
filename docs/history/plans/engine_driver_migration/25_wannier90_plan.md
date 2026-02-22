# Wannier90 Driver Migration Plan

**PR Title**: `feat(drivers): Migrate Wannier90 to driver bundle architecture`

**Priority**: Last engine migration (cross-engine complexity)

**Complexity**: HIGH

**Dependencies**: PR 1 (Remove Fallbacks), PR 2 (Registry Scaffold)

---

## 1. Objective

Extract Wannier90-specific code from kernel files into a self-contained driver bundle at `src/qmatsuite/drivers/w90/`. After this migration:

1. Wannier90 code lives in `drivers/w90/`
2. Wannier90 is registered via DriverRegistry
3. Cross-engine artifact dependency handled via standardized interface
4. Gate 3 (engine isolation) passes for Wannier90

---

## 2. Special Considerations

### 2.1 Cross-Engine Dependency

Wannier90 is unique because it:
1. Requires output from a DFT calculation (typically QE, but can be VASP, etc.)
2. Has a preprocessing step (`w90_preproc`) that runs WITHIN the DFT engine
3. The main `wannier90.x` executable is separate from DFT engines

### 2.2 Current Step Types

```
w90_preproc  - Preprocessing (runs via QE's pw2wannier90.x or VASP)
w90_run      - Main Wannier90 execution (wannier90.x)
```

### 2.3 Artifact Dependencies

| Step | Requires From | Artifact |
|------|---------------|----------|
| w90_preproc | qe_nscf or vasp_bands | Band structure data |
| w90_run | w90_preproc | .amn, .mmn, .eig files |

### 2.4 Design Decision

**Approach**: Wannier90 driver handles `w90_run` only. The preprocessing step (`w90_preproc`) remains registered with the DFT engine that produces it (currently QE shim), because:

1. `w90_preproc` uses DFT engine's executable (`pw2wannier90.x` for QE)
2. It runs in the DFT calculation's context
3. Cross-engine artifact resolution is handled via the registry's artifact interface

---

## 3. Code Inventory

### 3.1 Handler Code

**Source**: `src/qmatsuite/execution/handlers.py`

There may not be a dedicated `w90_step_handler`. Check if Wannier90 is handled within QE handler or has separate handling.

**Search**: `rg "w90|wannier" src/qmatsuite/execution/handlers.py`

### 3.2 Recipe Code

**Source**: `src/qmatsuite/execution/recipes.py`

Check for W90Recipe or similar.

### 3.3 Step Types in QE Shim

The `w90_preproc` step is currently in QE shim (as of PR 2):
- `StepTypeSpec(id="w90_preproc", engine="qe", ...)`

### 3.4 Additional Logic

**Locations to check**:
- `src/qmatsuite/workflow/` - W90-specific workflow logic
- Input generators for `.win` files

---

## 4. Target Structure

```
src/qmatsuite/drivers/w90/
├── __init__.py          # Registration (15 lines)
├── driver.py            # W90Driver class (70 lines)
├── handler.py           # w90_run_handler (100 lines)
├── recipe.py            # W90Recipe (80 lines)
└── artifact_resolver.py # Cross-engine artifact resolution (60 lines)
```

**Total**: ~325 lines (some new for artifact resolution)

---

## 5. Step-by-Step Procedure

### Step 1: Create Directory Structure

```bash
mkdir -p src/qmatsuite/drivers/w90
touch src/qmatsuite/drivers/w90/__init__.py
touch src/qmatsuite/drivers/w90/driver.py
touch src/qmatsuite/drivers/w90/handler.py
touch src/qmatsuite/drivers/w90/recipe.py
touch src/qmatsuite/drivers/w90/artifact_resolver.py
```

### Step 2: Create driver.py

**Create file**: `src/qmatsuite/drivers/w90/driver.py`

```python
"""Wannier90 engine driver.

This driver handles Wannier90 calculations for constructing
maximally localized Wannier functions (MLWFs) from DFT output.

Note: The preprocessing step (w90_preproc) is registered with
the DFT engine (QE, VASP) that produces it. This driver handles
only the main Wannier90 execution (w90_run).
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


class W90Driver(BaseEngineDriver):
    """Wannier90 driver bundle implementing the EngineDriver protocol.

    This driver handles:
    - w90_run: Main Wannier90 execution using wannier90.x

    The w90_preproc step is handled by the DFT engine driver because
    it uses the DFT engine's executable (pw2wannier90.x for QE).
    """

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required properties
    # ─────────────────────────────────────────────────────────────────────

    @property
    def engine_family(self) -> str:
        return "w90"

    @property
    def display_name(self) -> str:
        return "Wannier90"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # MUST: Required methods
    # ─────────────────────────────────────────────────────────────────────

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        """Return Wannier90 step type specifications.

        Note: w90_preproc is NOT included here - it's registered
        with the DFT engine (QE) that executes it.
        """
        return [
            StepTypeSpec(
                id="w90_run",
                engine="w90",
                executable="wannier90.x",
                description="Wannier90 MLWF construction",
                category="postprocess",
                mpi_aware=False,  # wannier90.x is typically serial
            ),
        ]

    def get_handler(self):
        """Return Wannier90 step handler."""
        from .handler import w90_run_handler
        return w90_run_handler

    def get_recipe_class(self):
        """Return Wannier90 recipe class."""
        from .recipe import W90Recipe
        return W90Recipe

    def get_materialization_map(self) -> dict[str, str]:
        """Return W90 GEN→SPEC mappings.

        Wannier90 doesn't have standard generalized steps,
        so this map is empty.
        """
        return {}

    # ─────────────────────────────────────────────────────────────────────
    # SHOULD: Override defaults where W90 differs
    # ─────────────────────────────────────────────────────────────────────

    def get_workdir_policy(self) -> WorkdirPolicy:
        """W90 uses isolated workdir."""
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        """Wannier90 capabilities."""
        return {
            "wannier",
            "mlwf",  # Maximally localized Wannier functions
            "interpolation",  # Band interpolation
            "postprocess",
            "cross_engine",  # Requires DFT output
        }

    def supports_incremental_skip(self, step_type: str) -> bool:
        """All W90 steps can be skipped if done."""
        return True

    def get_preflight_requirements(self, step) -> list[PreflightRequirement]:
        """Wannier90 preflight requirements.

        w90_run requires output from w90_preproc step.
        """
        if step.step_type == "w90_run":
            return [
                PreflightRequirement(
                    artifact_type="w90_amn",
                    source_step=None,  # Auto-resolve from w90_preproc
                    required=True,
                    description="Wannier90 .amn file from preprocessing",
                ),
                PreflightRequirement(
                    artifact_type="w90_mmn",
                    source_step=None,
                    required=True,
                    description="Wannier90 .mmn file from preprocessing",
                ),
                PreflightRequirement(
                    artifact_type="w90_eig",
                    source_step=None,
                    required=True,
                    description="Wannier90 .eig file from preprocessing",
                ),
            ]
        return []

    def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
        """Classify Wannier90 errors from stderr/exit code."""
        stderr_lower = stderr.lower()

        if "kmesh" in stderr_lower and "error" in stderr_lower:
            return ErrorClass.INPUT_ERROR
        if "disentanglement not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "wannierisation not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "file not found" in stderr_lower or ".amn" in stderr_lower:
            return ErrorClass.MISSING_FILE
        if "wannier90" in stderr_lower and "not found" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND

        return ErrorClass.UNKNOWN

    # ─────────────────────────────────────────────────────────────────────
    # PLUGIN: Optional extension points
    # ─────────────────────────────────────────────────────────────────────

    def get_artifact_patterns(self) -> dict[str, str]:
        """Wannier90 artifact patterns for discovery."""
        return {
            "w90_amn": "*.amn",
            "w90_mmn": "*.mmn",
            "w90_eig": "*.eig",
            "w90_win": "*.win",
            "w90_wout": "*.wout",
            "w90_hr": "*_hr.dat",
            "w90_tb": "*_tb.dat",
            "w90_centres": "*_centres.xyz",
        }

    def find_latest_artifact(self, workdir: Path, artifact_type: str) -> Path | None:
        """Find Wannier90 artifact in workdir."""
        pattern = self.get_artifact_patterns().get(artifact_type)
        if not pattern:
            return None

        matches = list(workdir.glob(pattern))
        return matches[0] if matches else None
```

### Step 3: Create handler.py

**Create file**: `src/qmatsuite/drivers/w90/handler.py`

```python
"""Wannier90 step handler.

This module handles execution of the main Wannier90 calculation.
"""

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from qmatsuite.core.job import Job
from qmatsuite.core.step_context import StepContext
from qmatsuite.core.job_result import JobResult

from .artifact_resolver import resolve_w90_inputs

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def w90_run_handler(job: Job, context: StepContext) -> JobResult:
    """Handle Wannier90 execution.

    This handler:
    1. Resolves required input files (.amn, .mmn, .eig) from w90_preproc
    2. Stages the .win input file
    3. Runs wannier90.x
    4. Collects output files

    Args:
        job: Job instance with execution context
        context: Step context with configuration

    Returns:
        JobResult with execution outcome
    """
    step = context.step
    workdir = context.workdir
    workdir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting Wannier90 run: {step.name}")

    # Resolve input artifacts from preprocessing
    try:
        inputs = resolve_w90_inputs(context)
        if not inputs:
            return JobResult(
                success=False,
                error="Failed to resolve Wannier90 input files from preprocessing"
            )
    except Exception as e:
        logger.error(f"Failed to resolve W90 inputs: {e}")
        return JobResult(success=False, error=str(e))

    # Stage input files
    for artifact_type, source_path in inputs.items():
        target = workdir / source_path.name
        if not target.exists():
            shutil.copy2(source_path, target)
            logger.debug(f"Staged {artifact_type}: {source_path.name}")

    # Generate/stage .win file
    # [Implementation depends on existing W90 input generation]

    # Execute wannier90.x
    # [Implementation depends on existing execution infrastructure]

    # Collect results
    # [Implementation depends on existing output handling]

    return JobResult(success=True)
```

### Step 4: Create recipe.py

**Create file**: `src/qmatsuite/drivers/w90/recipe.py`

```python
"""Wannier90 recipe for input staging.

This module handles preparation of Wannier90 input files.
"""

import logging
from pathlib import Path
from typing import Any

from qmatsuite.execution.recipes import BaseRecipe

logger = logging.getLogger(__name__)


class W90Recipe(BaseRecipe):
    """Recipe for staging Wannier90 inputs.

    Handles:
    - .win file generation
    - Artifact staging from preprocessing
    - Projection definitions
    """

    def stage(self, workdir: Path, config: dict[str, Any]) -> None:
        """Stage Wannier90 inputs.

        Args:
            workdir: Working directory
            config: Step configuration
        """
        # Generate .win file
        win_content = self._generate_win_file(config)
        win_path = workdir / f"{config.get('seedname', 'wannier90')}.win"
        win_path.write_text(win_content)
        logger.info(f"Generated .win file: {win_path}")

    def _generate_win_file(self, config: dict[str, Any]) -> str:
        """Generate Wannier90 .win input file.

        Args:
            config: Step configuration with W90 parameters

        Returns:
            Content of .win file
        """
        lines = []

        # Basic parameters
        if "num_wann" in config:
            lines.append(f"num_wann = {config['num_wann']}")

        if "num_bands" in config:
            lines.append(f"num_bands = {config['num_bands']}")

        # Disentanglement window
        if "dis_win_min" in config:
            lines.append(f"dis_win_min = {config['dis_win_min']}")
        if "dis_win_max" in config:
            lines.append(f"dis_win_max = {config['dis_win_max']}")
        if "dis_froz_min" in config:
            lines.append(f"dis_froz_min = {config['dis_froz_min']}")
        if "dis_froz_max" in config:
            lines.append(f"dis_froz_max = {config['dis_froz_max']}")

        # k-point mesh
        if "mp_grid" in config:
            mp = config["mp_grid"]
            lines.append(f"mp_grid = {mp[0]} {mp[1]} {mp[2]}")

        # Projections
        if "projections" in config:
            lines.append("")
            lines.append("begin projections")
            for proj in config["projections"]:
                lines.append(f"  {proj}")
            lines.append("end projections")

        # Unit cell
        if "unit_cell" in config:
            lines.append("")
            lines.append("begin unit_cell_cart")
            for vec in config["unit_cell"]:
                lines.append(f"  {vec[0]:.10f} {vec[1]:.10f} {vec[2]:.10f}")
            lines.append("end unit_cell_cart")

        # Atoms
        if "atoms" in config:
            lines.append("")
            lines.append("begin atoms_frac")
            for atom in config["atoms"]:
                symbol = atom["symbol"]
                pos = atom["position"]
                lines.append(f"  {symbol} {pos[0]:.10f} {pos[1]:.10f} {pos[2]:.10f}")
            lines.append("end atoms_frac")

        # k-points (if explicit)
        if "kpoints" in config:
            lines.append("")
            lines.append("begin kpoints")
            for kpt in config["kpoints"]:
                lines.append(f"  {kpt[0]:.10f} {kpt[1]:.10f} {kpt[2]:.10f}")
            lines.append("end kpoints")

        return "\n".join(lines)
```

### Step 5: Create artifact_resolver.py

**Create file**: `src/qmatsuite/drivers/w90/artifact_resolver.py`

```python
"""Wannier90 artifact resolution.

This module handles resolution of W90 input artifacts from
preprocessing steps executed by DFT engines.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from qmatsuite.core.driver_registry import DriverRegistry

if TYPE_CHECKING:
    from qmatsuite.core.step_context import StepContext

logger = logging.getLogger(__name__)


def resolve_w90_inputs(
    context: "StepContext",
    explicit_source: Optional[str] = None,
) -> Dict[str, Path]:
    """Resolve Wannier90 input artifacts from preprocessing.

    Searches for .amn, .mmn, .eig files from w90_preproc step
    or any other step that produces them.

    Args:
        context: Step context with calculation info
        explicit_source: Explicitly specified source step

    Returns:
        Dict mapping artifact type to path

    Raises:
        FileNotFoundError: If required artifacts not found
    """
    required_artifacts = ["w90_amn", "w90_mmn", "w90_eig"]
    found = {}

    # Try explicit source first
    if explicit_source:
        step_dir = context.get_step_dir(explicit_source)
        if step_dir:
            found = _find_artifacts_in_dir(step_dir, required_artifacts)
            if len(found) == len(required_artifacts):
                return found
            logger.warning(
                f"Not all artifacts found in explicit source '{explicit_source}'"
            )

    # Search completed steps for w90_preproc or any step with artifacts
    for prev_step in reversed(context.completed_steps):
        step_dir = context.get_step_dir(prev_step)
        if not step_dir:
            continue

        # Check if this step has W90 artifacts
        step_artifacts = _find_artifacts_in_dir(step_dir, required_artifacts)
        if step_artifacts:
            for art_type, path in step_artifacts.items():
                if art_type not in found:
                    found[art_type] = path
                    logger.debug(f"Found {art_type} in {prev_step}")

        if len(found) == len(required_artifacts):
            break

    # Verify all required artifacts found
    missing = [a for a in required_artifacts if a not in found]
    if missing:
        raise FileNotFoundError(
            f"Missing Wannier90 artifacts: {', '.join(missing)}. "
            "Ensure w90_preproc step completed successfully."
        )

    return found


def _find_artifacts_in_dir(
    directory: Path,
    artifact_types: list[str],
) -> Dict[str, Path]:
    """Find artifacts in a directory.

    Args:
        directory: Directory to search
        artifact_types: List of artifact types to find

    Returns:
        Dict mapping found artifact types to paths
    """
    # Get patterns from W90 driver
    try:
        driver = DriverRegistry.get_driver("w90")
        patterns = driver.get_artifact_patterns()
    except Exception:
        # Fallback patterns if driver not available
        patterns = {
            "w90_amn": "*.amn",
            "w90_mmn": "*.mmn",
            "w90_eig": "*.eig",
        }

    found = {}
    for art_type in artifact_types:
        pattern = patterns.get(art_type)
        if not pattern:
            continue

        matches = list(directory.glob(pattern))
        if matches:
            found[art_type] = matches[0]

    return found
```

### Step 6: Create __init__.py

**Create file**: `src/qmatsuite/drivers/w90/__init__.py`

```python
"""Wannier90 driver bundle.

This package provides the Wannier90 engine driver for QMatSuite.
It handles Wannier90 calculations for constructing maximally
localized Wannier functions from DFT output.

Note: The w90_preproc step is registered with the DFT engine
(QE, VASP) that executes it, not with this driver.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import W90Driver

# Register driver at import time
DriverRegistry.register(W90Driver())

__all__ = ["W90Driver"]
```

### Step 7: Update drivers/__init__.py

**File**: `src/qmatsuite/drivers/__init__.py`

**Add** W90 import:

```python
from qmatsuite.drivers import qe_shim
from qmatsuite.drivers import vasp
from qmatsuite.drivers import orca
from qmatsuite.drivers import pyscf
from qmatsuite.drivers import lammps
from qmatsuite.drivers import cp2k
from qmatsuite.drivers import w90  # ADD THIS LINE
```

### Step 8: Verify w90_preproc in QE Shim

**File**: `src/qmatsuite/drivers/qe_shim/__init__.py`

**Verify** that `w90_preproc` is registered with QE shim (already done in PR 2):

```python
StepTypeSpec(id="w90_preproc", engine="qe", executable="pw.x",
            description="Wannier90 preprocessing"),
```

This is correct - w90_preproc runs via QE's pw2wannier90.x interface.

### Step 9: Create W90-Specific Tests

**Create file**: `tests/drivers/w90/test_w90_driver.py`

```python
"""Tests for Wannier90 driver bundle."""

import pytest
from pathlib import Path
from qmatsuite.drivers.w90 import W90Driver
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_protocol import WorkdirPolicy


class TestW90Driver:
    """Test W90Driver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = W90Driver()
        assert driver.engine_family == "w90"
        assert driver.display_name == "Wannier90"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = W90Driver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "w90_run" in spec_ids
        # w90_preproc is NOT in this driver
        assert "w90_preproc" not in spec_ids

        for spec in specs:
            assert spec.engine == "w90"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = W90Driver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = W90Driver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_cross_engine_capability(self):
        """W90 should have cross_engine capability."""
        driver = W90Driver()
        assert "cross_engine" in driver.get_capabilities()

    def test_materialization_map_empty(self):
        """W90 has no generalized step mappings."""
        driver = W90Driver()
        assert driver.get_materialization_map() == {}


class TestW90Registration:
    """Test W90 driver registration."""

    def test_w90_registered(self):
        """W90 should be registered in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_engine_registered("w90")
        driver = DriverRegistry.get_driver("w90")
        assert driver.engine_family == "w90"

    def test_w90_run_registered(self):
        """w90_run step type should be in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("w90_run")

    def test_w90_preproc_in_qe(self):
        """w90_preproc should be registered with QE."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("w90_preproc")
        engine = DriverRegistry.get_engine_for_step_type("w90_preproc")
        assert engine == "qe"  # Preprocessing runs via QE


class TestW90Isolation:
    """Gate 3 tests: W90 isolation from kernel."""

    def test_w90_driver_exists(self):
        """W90 driver package should exist."""
        from qmatsuite.drivers.w90 import W90Driver
        assert W90Driver is not None


class TestW90ArtifactResolver:
    """Tests for W90 artifact resolution."""

    def test_find_artifacts(self, tmp_path):
        """Test finding W90 artifacts in directory."""
        from qmatsuite.drivers.w90.artifact_resolver import _find_artifacts_in_dir

        # Create mock artifact files
        (tmp_path / "wannier90.amn").touch()
        (tmp_path / "wannier90.mmn").touch()
        (tmp_path / "wannier90.eig").touch()

        found = _find_artifacts_in_dir(
            tmp_path,
            ["w90_amn", "w90_mmn", "w90_eig"]
        )

        assert len(found) == 3
        assert "w90_amn" in found
        assert "w90_mmn" in found
        assert "w90_eig" in found

    def test_missing_artifacts(self, tmp_path):
        """Test partial artifacts found."""
        from qmatsuite.drivers.w90.artifact_resolver import _find_artifacts_in_dir

        # Only create one artifact
        (tmp_path / "wannier90.amn").touch()

        found = _find_artifacts_in_dir(
            tmp_path,
            ["w90_amn", "w90_mmn", "w90_eig"]
        )

        assert len(found) == 1
        assert "w90_amn" in found


class TestW90Recipe:
    """Tests for W90 recipe."""

    def test_win_file_generation(self, tmp_path):
        """Test .win file generation."""
        from qmatsuite.drivers.w90.recipe import W90Recipe

        recipe = W90Recipe()
        config = {
            "seedname": "test",
            "num_wann": 4,
            "num_bands": 8,
            "mp_grid": [4, 4, 4],
            "projections": ["Si:sp3"],
        }

        recipe.stage(tmp_path, config)

        win_path = tmp_path / "test.win"
        assert win_path.exists()

        content = win_path.read_text()
        assert "num_wann = 4" in content
        assert "num_bands = 8" in content
        assert "mp_grid = 4 4 4" in content
        assert "Si:sp3" in content
```

### Step 10: Run Tests

```bash
pytest tests/drivers/w90/ -v
pytest tests/gates/ -v -k "w90 or wannier"
pytest tests/ -v
```

---

## 6. Cross-Engine Artifact Resolution Design

### 6.1 How It Works

```
QE Calculation                    W90 Calculation
┌─────────────────┐               ┌─────────────────┐
│ qe_nscf         │               │ w90_run         │
│                 │               │                 │
│ produces:       │               │ requires:       │
│ - bands data    │               │ - .amn, .mmn    │
└────────┬────────┘               └────────┬────────┘
         │                                 │
         ▼                                 │
┌─────────────────┐                        │
│ w90_preproc     │                        │
│ (QE engine)     │                        │
│                 │                        │
│ produces:       │──────────────────────▶│
│ - .amn, .mmn    │    artifact resolution
│ - .eig          │
└─────────────────┘
```

### 6.2 Artifact Resolution Flow

1. `w90_run` handler calls `resolve_w90_inputs(context)`
2. Resolver searches completed steps for `.amn`, `.mmn`, `.eig`
3. Typically finds them in `w90_preproc` step directory
4. Files are staged to `w90_run` working directory
5. `wannier90.x` executed

### 6.3 Future Enhancement

When VASP is migrated, VASP can also produce W90 input files. The artifact resolution will find them regardless of source engine, because it searches by artifact pattern, not by engine.

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Artifact resolution fails | Medium | High | Extensive testing |
| w90_preproc engine mismatch | Low | Medium | Clear documentation |
| .win generation incomplete | Medium | Medium | Test with real configs |

---

## 8. PR Checklist

- [ ] `drivers/w90/` directory created
- [ ] `driver.py` with W90Driver class
- [ ] `handler.py` with w90_run_handler
- [ ] `recipe.py` with W90Recipe
- [ ] `artifact_resolver.py` with cross-engine resolution
- [ ] `__init__.py` with registration
- [ ] w90_preproc remains in QE shim (verified)
- [ ] W90 driver tests pass
- [ ] Artifact resolution tests pass
- [ ] Gate 3 isolation tests pass
- [ ] Full test suite passes

---

## 9. Definition of Done

1. Wannier90 driver in `drivers/w90/`
2. w90_run registered with W90 driver
3. w90_preproc remains with QE shim
4. Cross-engine artifact resolution works
5. All existing W90 tests pass
6. Gate 3 (isolation) tests pass
7. CI green

---

## 10. Future Considerations

When QE is properly migrated (separate effort):

1. Move `w90_preproc` to a cross-engine interface
2. Allow VASP/QE/other to produce W90 preprocessing
3. Standardize artifact handoff protocol

For now, the current design (w90_preproc in QE shim) works correctly and maintains backward compatibility.
