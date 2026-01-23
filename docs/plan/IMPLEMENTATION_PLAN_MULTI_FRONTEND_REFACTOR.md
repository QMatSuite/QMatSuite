# Implementation Plan: Multi-Frontend Refactor v2

**Version**: 2.0
**Date**: 2026-01-21
**Status**: REVISED IMPLEMENTATION PLAN
**Reference**: `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md` v2.0

---

## CRITICAL LESSONS FROM v1 FAILURE

The v1 plan caused catastrophic failures:

1. **Gate test false-positives**: Pattern `resolve_calculation(` matched legitimate `svc.resolve_calculation(...)` calls, forcing ugly API renames and mass replacements that broke indentation.

2. **Wrong sequence**: "Remove imports first, add API later" caused immediate NameError/import breakage.

3. **No importability smoke test**: Gates passed but code was un-importable.

4. **Dangerous cleanup**: `git clean -xfd` deleted `.qmatsuite/` (local QE engines), breaking integration tests.

5. **CLI too large for mass replace**: 4000+ line file cannot survive sed/rg replacements without indentation disasters.

This v2 plan fixes all of these.

---

## SAFETY RULES (NON-NEGOTIABLE)

### Rule 1: Never Delete .qmatsuite/

The `.qmatsuite/` directory contains local QE engine installations. Deleting it breaks all integration tests.

**FORBIDDEN**:
```bash
git clean -xfd  # NEVER USE THIS
rm -rf .qmatsuite  # NEVER
```

**SAFE ALTERNATIVES**:
```bash
# Clean build artifacts only
git clean -xfd -e .qmatsuite/ -e .venv/

# Or better: targeted cleanup
rm -rf build/ dist/ *.egg-info/ __pycache__/ .pytest_cache/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
```

### Rule 2: Every Batch Must End Importable

After EVERY PR or batch, the following must pass:

```bash
# 1. Compile check
python -m py_compile src/quantumvitas/cli/main.py
python -m py_compile src/quantumvitas/daemon/server.py
python -m py_compile src/quantumvitas/api.py

# 2. Import check
python -c "from quantumvitas.cli.main import app; print('CLI OK')"
python -c "from quantumvitas.daemon.server import QVDaemon; print('Daemon OK')"
python -c "from quantumvitas.api import QVService; print('API OK')"

# 3. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Rule 3: No Mass Search/Replace in CLI

The CLI file (`cli/main.py`) is 4000+ lines. Mass replacements cause:
- Indentation damage
- String literal corruption
- Comment breakage

**FORBIDDEN**:
```bash
sed -i 's/resolve_calculation/svc.resolve_calculation/g' ...  # NO
rg -l ... | xargs sed ...  # NO
```

**REQUIRED**: Edit one function at a time, verify compile after each edit.

---

## BATCH STRUCTURE OVERVIEW

| Batch | Name | Purpose | Risk |
|-------|------|---------|------|
| 0 | Safety & Gates | Fix broken gates, add importability smoke, doc safety | LOW |
| 1 | API Facade | Build complete API methods (no migration yet) | LOW |
| 2 | Daemon Migration | Convert daemon to use API (10 files max) | MEDIUM |
| 3 | CLI Preparation | Identify CLI modules, add API stubs, compile loop | MEDIUM |
| 4 | CLI Migration | Convert CLI in 10-function chunks | HIGH |
| 5 | Directory Moves | Move files to frontends/ after all behavior stable | LOW |
| 6 | Cleanup | Remove shims, final audit | LOW |

Each batch ends with a **STOP POINT** where repo is fully green.

---

## Architecture Gates Policy

**Default Behavior**: Architecture gate tests are **enforced by default** (blocking mode). Violations cause test failures.

**Opt-Out for Local Development**: Set `QMATSUITE_RELAX_ARCH_GATES=1` to enable report-only mode (non-blocking). This allows local development while still seeing violation reports.

**Importability Smoke Tests**: Always enforced (never optional). These catch "gates green but code broken" scenarios.

**Notebook/Tools Behavior**:
- If notebook frontend does not exist → test is skipped (healthy)
- If tools directory does not exist → test is skipped (healthy)
- If they exist → enforce normally

**Usage**:
```bash
# Default: enforced (blocking)
python -m pytest tests/gates/test_import_rules.py -v -rs

# Relax mode: report-only (non-blocking)
QMATSUITE_RELAX_ARCH_GATES=1 python -m pytest tests/gates/test_import_rules.py -v -rs
```

---

## BATCH 0: SAFETY & GATES

**Goal**: Fix broken gate tests, add importability smoke tests, document safety rules.

**Risk**: LOW (no functional changes)

### PR 0.1: Fix Gate Test False-Positives

**Problem**: Current gate pattern `resolve_calculation(` also matches `svc.resolve_calculation(...)`.

**Solution**: Detect forbidden **imports**, not method calls.

**File**: `tests/gates/test_import_rules.py`

**Replace the entire file with**:

```python
"""
Gate tests for import rule enforcement.

These tests verify the architecture's import rules are not violated.
They detect IMPORTS, not method calls.

CRITICAL: These must NOT false-positive on legitimate method calls like:
    svc.resolve_calculation(...)  # OK - method call
    QVService().resolve_calculation(...)  # OK - method call

They SHOULD catch:
    from quantumvitas.core.resolution import resolve_calculation  # FORBIDDEN
    import quantumvitas.core.resolution  # FORBIDDEN
    from quantumvitas.core import resolution  # FORBIDDEN
"""

import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _find_forbidden_imports(source_dir: str, forbidden_modules: list[str]) -> list[str]:
    """
    Find forbidden imports using ripgrep.

    Detects:
    - from quantumvitas.X import ...
    - from quantumvitas.X.Y import ...
    - import quantumvitas.X
    - import quantumvitas.X.Y

    Does NOT detect method calls like svc.resolve_calculation().
    """
    source_path = PROJECT_ROOT / source_dir
    if not source_path.exists():
        return []

    violations = []
    for module in forbidden_modules:
        # Pattern 1: from quantumvitas.module import ...
        # Pattern 2: from quantumvitas.module.submodule import ...
        # Pattern 3: import quantumvitas.module
        patterns = [
            f"^from quantumvitas\\.{module}(\\.|\\s)",
            f"^import quantumvitas\\.{module}(\\.|\\s|$)",
        ]

        for pattern in patterns:
            result = subprocess.run(
                ["rg", "-n", "--pcre2", pattern, str(source_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    # Skip comments
                    if not line.strip().startswith("#"):
                        violations.append(line)

    return violations


class TestFrontendImportRules:
    """Frontends must not import from kernel modules."""

    KERNEL_MODULES = ["core", "calculation", "drivers", "analysis", "io", "engine", "workflow", "presets"]

    def test_cli_no_kernel_imports(self):
        """cli/* must not import from kernel modules."""
        # Check both old and new locations
        for source_dir in ["src/quantumvitas/cli", "src/quantumvitas/frontends/cli"]:
            violations = _find_forbidden_imports(source_dir, self.KERNEL_MODULES)
            # Filter out any in-progress migration markers
            violations = [v for v in violations if "# MIGRATION:" not in v]
            assert violations == [], (
                f"Forbidden kernel imports in CLI:\n" + "\n".join(violations)
            )

    def test_daemon_no_kernel_imports(self):
        """daemon/* must not import from kernel modules."""
        for source_dir in ["src/quantumvitas/daemon", "src/quantumvitas/frontends/daemon"]:
            violations = _find_forbidden_imports(source_dir, self.KERNEL_MODULES)
            violations = [v for v in violations if "# MIGRATION:" not in v]
            assert violations == [], (
                f"Forbidden kernel imports in daemon:\n" + "\n".join(violations)
            )

    def test_notebook_no_kernel_imports(self):
        """notebook/* must not import from kernel modules."""
        violations = _find_forbidden_imports(
            "src/quantumvitas/frontends/notebook",
            self.KERNEL_MODULES
        )
        assert violations == [], (
            f"Forbidden kernel imports in notebook:\n" + "\n".join(violations)
        )


class TestToolsImportRules:
    """Tools must only import from api."""

    KERNEL_MODULES = ["core", "calculation", "drivers", "analysis", "io", "engine"]

    def test_tools_no_kernel_imports(self):
        """tools/* must not import from kernel modules."""
        violations = _find_forbidden_imports(
            "src/quantumvitas/tools",
            self.KERNEL_MODULES
        )
        assert violations == [], (
            f"Forbidden kernel imports in tools:\n" + "\n".join(violations)
        )


class TestAPIImportRules:
    """API must not import from frontends or tools."""

    def test_api_no_frontend_imports(self):
        """api/* must not import from frontends/*."""
        violations = _find_forbidden_imports(
            "src/quantumvitas/api",
            ["frontends", "cli", "daemon"]
        )
        assert violations == [], (
            f"Forbidden frontend imports in api:\n" + "\n".join(violations)
        )


class TestImportabilitySmoke:
    """
    Smoke tests that verify key modules are importable.

    CRITICAL: These catch the "gates green but code broken" scenario.
    """

    def test_cli_importable(self):
        """CLI must be importable."""
        result = subprocess.run(
            ["python", "-c", "from quantumvitas.cli.main import app; print('OK')"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"CLI import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_daemon_importable(self):
        """Daemon must be importable."""
        result = subprocess.run(
            ["python", "-c", "from quantumvitas.daemon.server import QVDaemon; print('OK')"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"Daemon import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_api_importable(self):
        """API must be importable."""
        result = subprocess.run(
            ["python", "-c", "from quantumvitas.api import QVService; print('OK')"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"API import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_package_importable(self):
        """Main package must be importable."""
        result = subprocess.run(
            ["python", "-c", "import quantumvitas; print('OK')"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"Package import failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
```

### PR 0.2: Add Safety Documentation

**File**: `docs/dev/SAFETY_RULES.md` (create)

```markdown
# Development Safety Rules

## Never Delete .qmatsuite/

The `.qmatsuite/` directory contains:
- Local QE engine installations
- Cached binaries
- Engine configuration

Deleting it breaks ALL integration tests.

### Safe Cleanup Commands

```bash
# Clean build artifacts (SAFE)
git clean -xfd -e .qmatsuite/ -e .venv/

# Targeted cleanup (SAFER)
rm -rf build/ dist/ *.egg-info/
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# If .qmatsuite was accidentally deleted
# Re-run: qv engines install qe  (may take 10+ minutes)
```

## Verification Commands

After any refactor, run:

```bash
# Quick smoke
python -c "from quantumvitas.cli.main import app"
python -c "from quantumvitas.daemon.server import QVDaemon"
python -c "from quantumvitas.api import QVService"

# Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
```

### Acceptance Criteria (Batch 0)

```bash
# 1. Gates pass
python -m pytest tests/gates/test_import_rules.py -v

# 2. Importability smoke passes
python -c "from quantumvitas.cli.main import app; print('CLI OK')"
python -c "from quantumvitas.daemon.server import QVDaemon; print('Daemon OK')"
python -c "from quantumvitas.api import QVService; print('API OK')"

# 3. Full suite passes
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 0: Gates fixed, smoke tests added
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 1: API FACADE (API-FIRST)

**Goal**: Build complete API methods that CLI/daemon will call. NO migration yet.

**Risk**: LOW (additive changes only)

**Principle**: We add all needed API methods BEFORE removing any imports from frontends.

### PR 1.1: Audit Current API and Plan Additions

**Task**: Review `api.py` and identify missing methods needed by CLI/daemon.

**Output**: A checklist in this PR description of methods to add.

**Current QVService methods to verify**:
- `run_calculation(calc_selector)`
- `run_step(calc_selector, step_selector)`
- `list_calculations()`
- `list_steps(calc_selector)`
- `get_calculation(selector)`
- `import_structure(path)`
- `list_structures()`

**Methods to ADD** (based on CLI usage):
- `resolve_calculation_ref(selector) -> CalculationRef` - returns ref object
- `resolve_step_ref(calc_selector, step_selector) -> StepRef` - returns ref object
- `resolve_structure_ref(selector) -> StructureRef` - returns ref object
- `load_project_config() -> dict` - loads project.qv.yml
- `get_context_from_cwd(cwd: Path) -> dict` - context detection
- `get_engine_registry() -> EngineRegistry` - engine access
- `validate_step_params(step_selector, params) -> ValidationResult`
- `configure_step(step_selector, params) -> None`

### PR 1.2: Add Resolution Methods to API

**File**: `src/quantumvitas/api.py`

**Add these methods to QVService class** (do NOT remove existing code):

```python
# Add after existing methods in QVService class

def resolve_calculation_ref(self, selector: str) -> "CalculationRef":
    """
    Resolve calculation selector to CalculationRef.

    This is the API method that CLI/daemon should call instead of
    importing resolve_calculation from core.resolution.

    Args:
        selector: Calculation name, slug, ULID, or path

    Returns:
        CalculationRef object

    Raises:
        QVServiceError: If calculation not found
    """
    from quantumvitas.core.resolution import resolve_calculation
    from quantumvitas.core.project_utils import load_project_config

    config = load_project_config(self.project_root)
    try:
        return resolve_calculation(self.project_root, selector, config=config)
    except Exception as e:
        raise QVServiceError(f"Failed to resolve calculation '{selector}': {e}") from e

def resolve_step_ref(self, calc_selector: str, step_selector: str) -> "StepRef":
    """
    Resolve step selector to StepRef.

    Args:
        calc_selector: Calculation selector
        step_selector: Step selector (name, ULID, or index)

    Returns:
        StepRef object
    """
    from quantumvitas.core.resolution import resolve_step
    from quantumvitas.core.project_utils import load_project_config

    config = load_project_config(self.project_root)
    try:
        return resolve_step(self.project_root, calc_selector, step_selector, config=config)
    except Exception as e:
        raise QVServiceError(f"Failed to resolve step '{calc_selector}/{step_selector}': {e}") from e

def resolve_structure_ref(self, selector: str) -> "StructureRef":
    """
    Resolve structure selector to StructureRef.

    Args:
        selector: Structure name, slug, ULID, or path

    Returns:
        StructureRef object
    """
    from quantumvitas.core.resolution import resolve_structure
    from quantumvitas.core.project_utils import load_project_config

    config = load_project_config(self.project_root)
    try:
        return resolve_structure(self.project_root, selector, config=config)
    except Exception as e:
        raise QVServiceError(f"Failed to resolve structure '{selector}': {e}") from e

def load_project_config(self) -> dict:
    """
    Load project.qv.yml configuration.

    Returns:
        Project configuration dict
    """
    from quantumvitas.core.project_utils import load_project_config as _load_config
    return _load_config(self.project_root)

def get_context_from_cwd(self, cwd: Path = None) -> dict:
    """
    Detect project/calculation context from working directory.

    Args:
        cwd: Working directory (defaults to current)

    Returns:
        Context dict with keys: project_root, calculation, step, etc.
    """
    from quantumvitas.core.context import find_path_context_from_pwd
    if cwd is None:
        cwd = Path.cwd()
    return find_path_context_from_pwd(cwd)

def get_engine_registry(self) -> "EngineRegistry":
    """
    Get engine registry for this project.

    Returns:
        EngineRegistry instance
    """
    from quantumvitas.engine.registry import create_default_registry
    return create_default_registry()

def configure_step(
    self,
    calc_selector: str,
    step_selector: str,
    params: dict,
    *,
    dry_run: bool = False,
) -> dict:
    """
    Configure step parameters.

    Args:
        calc_selector: Calculation selector
        step_selector: Step selector
        params: Parameters to set
        dry_run: If True, validate only without saving

    Returns:
        Result dict with 'success', 'changes', 'warnings'
    """
    # Implementation delegates to existing configure logic
    step_ref = self.resolve_step_ref(calc_selector, step_selector)

    if dry_run:
        # Validation only
        return {"success": True, "changes": params, "warnings": []}

    # Apply changes
    from quantumvitas.core.yamldoc import StepDoc
    from quantumvitas.core.yaml_io import load_yaml_doc, save_yaml_doc

    step_path = step_ref.absolute_path
    doc = load_yaml_doc(StepDoc, step_path)

    # Merge params into step
    if "parameters" not in doc.data:
        doc.data["parameters"] = {}
    doc.data["parameters"].update(params)

    save_yaml_doc(doc, step_path)
    return {"success": True, "changes": params, "warnings": []}
```

### PR 1.3: Add API Tests

**File**: `tests/unit/test_api_facade.py` (create)

```python
"""Tests for API facade methods."""

import pytest
from pathlib import Path

# These tests verify API methods work, NOT that frontends use them
# (That's the gate tests' job)


class TestAPIResolutionMethods:
    """Test that API resolution methods work correctly."""

    @pytest.fixture
    def demo_project(self, tmp_path):
        """Create a minimal demo project."""
        # Use existing demo or create minimal fixture
        from quantumvitas.api import QVService

        project_root = tmp_path / "test_project"
        project_root.mkdir()

        # Create minimal project.qv.yml
        (project_root / "project.qv.yml").write_text("""
project:
  name: test_project
structures: []
calculations: []
""")
        return project_root

    def test_load_project_config(self, demo_project):
        """API can load project config."""
        from quantumvitas.api import QVService

        svc = QVService(demo_project)
        config = svc.load_project_config()
        assert "project" in config

    def test_get_context_from_cwd(self, demo_project):
        """API can detect context from cwd."""
        from quantumvitas.api import QVService
        import os

        svc = QVService(demo_project)

        # Change to project dir
        old_cwd = os.getcwd()
        try:
            os.chdir(demo_project)
            ctx = svc.get_context_from_cwd()
            # Should detect project root at minimum
            assert ctx is not None
        finally:
            os.chdir(old_cwd)
```

### Acceptance Criteria (Batch 1)

```bash
# 1. API is importable with new methods
python -c "
from quantumvitas.api import QVService
svc = QVService.__new__(QVService)
# Check methods exist
assert hasattr(svc, 'resolve_calculation_ref')
assert hasattr(svc, 'resolve_step_ref')
assert hasattr(svc, 'resolve_structure_ref')
assert hasattr(svc, 'load_project_config')
assert hasattr(svc, 'get_context_from_cwd')
print('API methods OK')
"

# 2. Importability smoke
python -c "from quantumvitas.cli.main import app; print('CLI OK')"
python -c "from quantumvitas.daemon.server import QVDaemon; print('Daemon OK')"

# 3. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 1: API facade complete
### All needed API methods exist
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 2: DAEMON MIGRATION

**Goal**: Convert daemon to use API methods instead of direct core imports.

**Risk**: MEDIUM (daemon is smaller than CLI, ~1000 lines)

### PR 2.1: Identify Daemon Imports to Migrate

**Task**: List all forbidden imports in daemon.

**Command**:
```bash
rg "^from quantumvitas\.(core|calculation|drivers|analysis|io)" src/quantumvitas/daemon/
rg "^import quantumvitas\.(core|calculation|drivers|analysis|io)" src/quantumvitas/daemon/
```

**Expected findings** (from earlier audit):
- `from quantumvitas.core.exceptions import LegacyProjectError`
- `from quantumvitas.core.resolution import resolve_calculation, ...`
- `from quantumvitas.core.project_utils import load_project_config`

### PR 2.2: Migrate Daemon Resolution Calls

**File**: `src/quantumvitas/daemon/server.py`

**Strategy**: ONE FUNCTION AT A TIME with compile check.

**Step 1**: Add API import at top (keep existing imports for now):
```python
from quantumvitas.api import QVService, QVServiceError
```

**Step 2**: For EACH function that calls resolution:

Example - `_handle_get_calculation`:
```python
# BEFORE:
def _handle_get_calculation(self, params):
    calc = resolve_calculation(self.project_root, params["selector"], self.config)
    return calc.to_dict()

# AFTER:
def _handle_get_calculation(self, params):
    svc = QVService(self.project_root)
    calc_ref = svc.resolve_calculation_ref(params["selector"])
    return calc_ref.to_dict()
```

**After EACH function edit**:
```bash
python -m py_compile src/quantumvitas/daemon/server.py
python -c "from quantumvitas.daemon.server import QVDaemon; print('OK')"
```

**Step 3**: After ALL functions migrated, remove unused imports:
```python
# REMOVE these lines:
from quantumvitas.core.resolution import resolve_calculation, resolve_step, ...
from quantumvitas.core.project_utils import load_project_config
```

### PR 2.3: Migrate Daemon Exception Handling

**Current**:
```python
from quantumvitas.core.exceptions import LegacyProjectError
```

**Options**:
1. Re-export `LegacyProjectError` from `api.py`
2. Catch generic `QVServiceError` instead

**Preferred**: Re-export from API:

**File**: `src/quantumvitas/api.py`
```python
# Add to imports section
from quantumvitas.core.exceptions import LegacyProjectError

# Add to __all__ if exists
```

**Then in daemon**:
```python
from quantumvitas.api import QVService, QVServiceError, LegacyProjectError
```

### Acceptance Criteria (Batch 2)

```bash
# 1. No forbidden imports in daemon
rg "^from quantumvitas\.(core|calculation|drivers)" src/quantumvitas/daemon/
# Expected: 0 matches (or only re-exports via api)

# 2. Daemon importable
python -c "from quantumvitas.daemon.server import QVDaemon; print('Daemon OK')"

# 3. Gates pass
python -m pytest tests/gates/test_import_rules.py -v

# 4. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 2: Daemon migrated
### Daemon uses API only
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 3: CLI PREPARATION

**Goal**: Prepare for CLI migration without breaking anything.

**Risk**: MEDIUM

### CLI Deep Review

**File**: `src/quantumvitas/cli/main.py` (~4000 lines, ~189KB)

**Current forbidden imports** (from audit):
```python
from quantumvitas.core.resources import (...)           # ~8 imports
from quantumvitas.core.context import (...)             # ~2 imports
from quantumvitas.core.exceptions import (...)          # ~1 import
from quantumvitas.core.resolution import (...)          # ~7 imports
from quantumvitas.core.selectors import (...)           # ~6 imports
from quantumvitas.core.project_utils import (...)       # ~19 imports
from quantumvitas.analysis import bands, dos, energy
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.calculation.calculation import Calculation
```

**High-risk areas** (most uses of forbidden imports):
1. Project/context resolution at command start
2. Calculation/step resolution in run commands
3. Step parameter configuration
4. Analysis display (bands/dos/energy)

### Migration Order (safest first)

| Phase | Functions | Complexity |
|-------|-----------|------------|
| 3A | Project context detection | LOW |
| 3B | list_* commands | LOW |
| 3C | show_* commands | MEDIUM |
| 3D | run_* commands | MEDIUM |
| 3E | config_* commands | MEDIUM |
| 3F | Analysis display | HIGH |
| 3G | Remaining functions | VARIES |

### PR 3.1: Create CLI Migration Marker

**Purpose**: Mark imports that are being migrated to prevent accidental removal.

**File**: `src/quantumvitas/cli/main.py`

**Add comment markers to imports**:
```python
# === MIGRATION ZONE START ===
# These imports will be migrated to use API in Batch 4.
# Do NOT remove until migration complete.
from quantumvitas.core.resolution import (  # MIGRATION: PR 4.x
    resolve_calculation,
    resolve_step,
    ...
)
# === MIGRATION ZONE END ===
```

### PR 3.2: Add CLI Compile Gate

**File**: `tests/gates/test_import_rules.py`

**Add to TestImportabilitySmoke**:
```python
def test_cli_compiles(self):
    """CLI must compile without syntax errors."""
    result = subprocess.run(
        ["python", "-m", "py_compile", "src/quantumvitas/cli/main.py"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"CLI compilation failed:\n{result.stderr}"
    )
```

### Acceptance Criteria (Batch 3)

```bash
# 1. Migration markers added
rg "MIGRATION:" src/quantumvitas/cli/main.py | head -5
# Expected: Shows migration markers

# 2. CLI compiles
python -m py_compile src/quantumvitas/cli/main.py

# 3. CLI importable
python -c "from quantumvitas.cli.main import app; print('CLI OK')"

# 4. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 3: CLI prepared
### Migration markers in place
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 4: CLI MIGRATION

**Goal**: Convert CLI to use API, in small increments.

**Risk**: HIGH (largest file, most changes)

### CRITICAL RULES FOR CLI MIGRATION

1. **ONE function at a time**
2. **Compile check after EVERY edit**
3. **NO mass search/replace**
4. **Keep old import until ALL uses removed**
5. **Test frequently**

### PR 4.1: Migrate Context Detection

**Functions to migrate**:
- `_get_project_root()`
- Any function using `find_path_context_from_pwd`

**Pattern**:
```python
# BEFORE:
from quantumvitas.core.context import find_path_context_from_pwd
def _get_project_root():
    ctx = find_path_context_from_pwd(Path.cwd())
    return ctx.get("project_root")

# AFTER:
def _get_project_root():
    # Note: We need project_root to create QVService, but we're detecting it.
    # This is a bootstrap case - keep the import for now or use a standalone helper.
    from quantumvitas.core.context import find_path_context_from_pwd
    ctx = find_path_context_from_pwd(Path.cwd())
    return ctx.get("project_root")
```

**Decision**: Context detection is a **bootstrap** operation - it MUST run before we have a project_root. This import may need to stay or be moved to a `frontends/_shared/context.py` helper.

### PR 4.2: Migrate list_* Commands

**Functions**:
- `list_calculations()`
- `list_structures()`
- `list_steps()`

**Pattern**:
```python
# BEFORE:
@app.command()
def list_calculations():
    config = load_project_config(project_root)
    for calc in config.get("calculations", []):
        print(calc["name"])

# AFTER:
@app.command()
def list_calculations():
    svc = QVService(project_root)
    for calc in svc.list_calculations():
        print(calc.name)
```

**After EACH function**:
```bash
python -m py_compile src/quantumvitas/cli/main.py
python -c "from quantumvitas.cli.main import app; print('OK')"
```

### PR 4.3: Migrate show_* Commands

Similar pattern to list_* commands.

### PR 4.4: Migrate run_* Commands

**Functions**:
- `run_calculation()`
- `run_step()`

**These are critical** - test thoroughly.

### PR 4.5: Migrate config_* Commands

### PR 4.6: Migrate Remaining Functions

### PR 4.7: Remove Migrated Imports

**ONLY after ALL functions migrated**:

```python
# REMOVE these lines (verify no uses first):
# from quantumvitas.core.resolution import ...
# from quantumvitas.core.project_utils import ...
# etc.
```

**Verify no uses**:
```bash
# For each symbol being removed:
rg "resolve_calculation" src/quantumvitas/cli/main.py
# Should show only the import line (which we're removing)
# or svc.resolve_calculation_ref() calls (which are fine)
```

### Failure Recovery

**If you get NameError after removing import**:
1. DO NOT add a new import back
2. Find the function that still uses the old symbol
3. Edit that function to use API
4. Compile check
5. Try again

**If you get IndentationError**:
1. STOP immediately
2. `git diff src/quantumvitas/cli/main.py` to see damage
3. If damage is extensive: `git checkout src/quantumvitas/cli/main.py`
4. Start over with smaller edits

### Acceptance Criteria (Batch 4)

```bash
# 1. No forbidden imports (except bootstrap context detection)
rg "^from quantumvitas\.(core|calculation|drivers)" src/quantumvitas/cli/main.py | grep -v "BOOTSTRAP"
# Expected: 0 matches

# 2. CLI compiles
python -m py_compile src/quantumvitas/cli/main.py

# 3. CLI importable
python -c "from quantumvitas.cli.main import app; print('CLI OK')"

# 4. CLI works
qv --help
qv list --help

# 5. Gates pass
python -m pytest tests/gates/test_import_rules.py -v

# 6. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 4: CLI migrated
### CLI uses API only
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 5: DIRECTORY MOVES

**Goal**: Move files to `frontends/` directory structure.

**Risk**: LOW (behavior already migrated, just moving files)

**PREREQUISITE**: Batches 0-4 complete and green.

### PR 5.1: Create frontends/ Structure

```bash
mkdir -p src/quantumvitas/frontends/_shared
mkdir -p src/quantumvitas/frontends/cli
mkdir -p src/quantumvitas/frontends/daemon
mkdir -p src/quantumvitas/frontends/notebook
mkdir -p src/quantumvitas/frontends/agent

echo '"""Frontend layers for QMatSuite."""' > src/quantumvitas/frontends/__init__.py
```

### PR 5.2: Move Daemon

```bash
git mv src/quantumvitas/daemon/server.py src/quantumvitas/frontends/daemon/server.py
git mv src/quantumvitas/daemon/jobs.py src/quantumvitas/frontends/daemon/jobs.py
# Update imports in moved files
# Create shim at old location
```

### PR 5.3: Move CLI

```bash
git mv src/quantumvitas/cli/main.py src/quantumvitas/frontends/cli/app.py
git mv src/quantumvitas/cli/__main__.py src/quantumvitas/frontends/cli/__main__.py
# Update imports in moved files
# Create shim at old location
# Update pyproject.toml entry point
```

### PR 5.4: Create Notebook Frontend

Create `src/quantumvitas/frontends/notebook/` with display helpers.

### Acceptance Criteria (Batch 5)

```bash
# 1. New locations importable
python -c "from quantumvitas.frontends.cli import app; print('OK')"
python -c "from quantumvitas.frontends.daemon import QVDaemon; print('OK')"

# 2. Old locations still work (shims)
python -c "from quantumvitas.cli import app; print('OK')"
python -c "from quantumvitas.daemon import QVDaemon; print('OK')"

# 3. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### ═══════════════════════════════════════════════════════
### STOP POINT 5: Directory structure complete
### Files moved to frontends/
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## BATCH 6: CLEANUP & FINALIZE

**Goal**: Remove shims, final audit.

**Risk**: LOW

### PR 6.1: Rename tools/ to scripts/

```bash
git mv tools scripts
# Update any CI/docs references
```

### PR 6.2: Create tools/ Surface (Python Package)

Create `src/quantumvitas/tools/` with agent-ready primitives.

### PR 6.3: Remove Compatibility Shims (Optional)

After deprecation period, remove shims at old locations.

### Final Verification

```bash
# === Complete Audit ===

# 1. No forbidden imports in frontends
rg "^from quantumvitas\.(core|calculation|drivers|analysis|io)" src/quantumvitas/frontends/
# Expected: 0 matches

# 2. No forbidden imports in tools
rg "^from quantumvitas\.(core|calculation|drivers)" src/quantumvitas/tools/
# Expected: 0 matches

# 3. All importability checks
python -c "from quantumvitas.frontends.cli import app; print('CLI OK')"
python -c "from quantumvitas.frontends.daemon import QVDaemon; print('Daemon OK')"
python -c "from quantumvitas.frontends.notebook import display_bands; print('Notebook OK')"
python -c "from quantumvitas.tools import discover, run_calc; print('Tools OK')"
python -c "from quantumvitas.api import QVService; print('API OK')"

# 4. CLI works
qv --help
qv list calcs --help

# 5. Full suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# 6. scripts/ exists
ls scripts/
# Expected: Maintenance scripts

# 7. No old tools/ at repo level
ls tools/ 2>&1 | grep -i "no such"
# Expected: No such file or directory

echo "=== REFACTOR COMPLETE ==="
```

### ═══════════════════════════════════════════════════════
### STOP POINT 6: REFACTOR COMPLETE
### All batches done
### Repo is GREEN and IMPORTABLE
### ═══════════════════════════════════════════════════════

---

## APPENDIX A: Gate Test Patterns

### What Gates SHOULD Detect

```python
# FORBIDDEN - direct imports from kernel
from quantumvitas.core.resolution import resolve_calculation  # CATCH THIS
from quantumvitas.core import resolution  # CATCH THIS
import quantumvitas.core.resolution  # CATCH THIS
from quantumvitas.calculation.runner import CalculationRunner  # CATCH THIS
```

### What Gates Should NOT Detect

```python
# ALLOWED - method calls on API objects
svc.resolve_calculation_ref(...)  # DO NOT CATCH
result = QVService(root).resolve_calculation_ref(...)  # DO NOT CATCH

# ALLOWED - re-exports from API
from quantumvitas.api import LegacyProjectError  # DO NOT CATCH (re-exported)
```

### Gate Pattern Implementation

Use **import-based detection**, not method-name detection:

```python
# CORRECT gate pattern
r"^from quantumvitas\.core"  # Matches import statements only
r"^import quantumvitas\.core"  # Matches import statements only

# WRONG gate pattern (v1 mistake)
r"resolve_calculation\("  # Matches method calls too - FALSE POSITIVE
```

---

## APPENDIX B: Safe Rollback Commands

### Undo a single file
```bash
git checkout HEAD -- src/quantumvitas/cli/main.py
```

### Undo all uncommitted changes
```bash
git checkout HEAD -- .
```

### Undo last commit (keep changes)
```bash
git reset --soft HEAD~1
```

### Clean up (SAFE)
```bash
# ALWAYS exclude .qmatsuite and .venv
git clean -xfd -e .qmatsuite/ -e .venv/ -e .env
```

---

## APPENDIX C: CLI Migration Checklist

Use this checklist when migrating each CLI function:

```
[ ] Identify function to migrate
[ ] Identify which core imports it uses
[ ] Check API has equivalent method
[ ] Edit function (ONE function only)
[ ] Run: python -m py_compile src/quantumvitas/cli/main.py
[ ] Run: python -c "from quantumvitas.cli.main import app"
[ ] Run: python -m pytest tests/gates/test_import_rules.py -v
[ ] Commit changes
[ ] Repeat for next function
```

---

## APPENDIX D: Bootstrap Imports Exception

Some imports MUST stay in frontends because they're needed BEFORE we have a project_root:

1. **Context detection**: `find_path_context_from_pwd` - needed to find project_root
2. **Exception types**: May need to catch specific types

**Solution**: Create `frontends/_shared/bootstrap.py`:
```python
"""
Bootstrap utilities that frontends may import.

These are the ONLY kernel imports allowed in frontends.
They are needed before QVService can be instantiated.
"""

from quantumvitas.core.context import find_path_context_from_pwd
from quantumvitas.core.exceptions import LegacyProjectError

__all__ = ["find_path_context_from_pwd", "LegacyProjectError"]
```

Then frontends import from `_shared`:
```python
from quantumvitas.frontends._shared.bootstrap import find_path_context_from_pwd
```

Gate tests exclude `_shared/bootstrap.py` from forbidden import checks.

---

*End of implementation plan v2.*
