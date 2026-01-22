# Implementation Plan: Multi-Frontend Refactor

**Version**: 1.0
**Date**: 2026-01-21
**Status**: IMPLEMENTATION PLAN (Cursor Auto Executable)
**Reference**: `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md` v2.0

---

## Overview

This plan provides a PR-by-PR sequence to implement the multi-frontend architecture refactor. Each PR is self-contained, testable, and can be merged independently.

**Total PRs**: 12
**Estimated LOC Changed**: ~5,000
**Test Coverage Requirement**: All existing tests must pass after each PR

---

## Pre-Flight Checklist

Before starting, verify:

```bash
# 1. All tests pass
pytest tests/ -v --tb=short

# 2. No uncommitted changes
git status

# 3. On correct branch
git checkout -b refactor/multi-frontend-architecture
```

---

## PR 1: Rename `tools/` to `scripts/`

### Goal
Rename repo-level `tools/` directory to `scripts/` to free the namespace for `quantumvitas/tools/`.

### Files Changed

| Action | Path |
|--------|------|
| RENAME | `tools/` → `scripts/` |
| MODIFY | `.github/workflows/*.yml` (if any references) |
| MODIFY | `README.md` (if references tools/) |
| MODIFY | `docs/**/*.md` (if references tools/) |

### Exact Commands

```bash
# 1. Rename directory
git mv tools scripts

# 2. Find and update references
rg -l "tools/" . --glob "*.md" --glob "*.yml" --glob "*.yaml" | head -20
# For each file found, update "tools/" to "scripts/"

# 3. Update any imports in scripts themselves (if they reference each other)
rg -l "from tools" scripts/
# Update if found
```

### Acceptance Criteria

```bash
# Directory renamed
ls tools/
# Expected: ls: tools/: No such file or directory

ls scripts/
# Expected: List of maintenance scripts

# No broken references
rg "tools/" --glob "*.md" --glob "*.yml" --glob "*.yaml" | grep -v "quantumvitas/tools" | grep -v "node_modules"
# Expected: 0 matches (or only external references)

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- LOW: Simple rename, no code changes

### Rollback
```bash
git mv scripts tools
```

---

## PR 2: Create Directory Structure Skeleton

### Goal
Create the target directory structure with empty `__init__.py` files.

### Files Created

| Path | Content |
|------|---------|
| `src/quantumvitas/frontends/__init__.py` | `"""Frontend layers for QMatSuite."""` |
| `src/quantumvitas/frontends/_shared/__init__.py` | `"""Shared frontend utilities."""` |
| `src/quantumvitas/frontends/cli/__init__.py` | Empty (placeholder) |
| `src/quantumvitas/frontends/daemon/__init__.py` | Empty (placeholder) |
| `src/quantumvitas/frontends/notebook/__init__.py` | Empty (placeholder) |
| `src/quantumvitas/frontends/agent/__init__.py` | `"""Reserved for MCP adapter."""` |
| `src/quantumvitas/frontends/agent/README.md` | MCP reservation doc |
| `src/quantumvitas/tools/__init__.py` | Tool surface exports (empty for now) |
| `src/quantumvitas/api/__init__.py` | Empty (placeholder) |

### Exact Commands

```bash
# Create directories
mkdir -p src/quantumvitas/frontends/_shared
mkdir -p src/quantumvitas/frontends/cli
mkdir -p src/quantumvitas/frontends/daemon
mkdir -p src/quantumvitas/frontends/notebook
mkdir -p src/quantumvitas/frontends/agent
mkdir -p src/quantumvitas/tools
mkdir -p src/quantumvitas/api

# Create __init__.py files
echo '"""Frontend layers for QMatSuite."""' > src/quantumvitas/frontends/__init__.py
echo '"""Shared frontend utilities."""' > src/quantumvitas/frontends/_shared/__init__.py
touch src/quantumvitas/frontends/cli/__init__.py
touch src/quantumvitas/frontends/daemon/__init__.py
touch src/quantumvitas/frontends/notebook/__init__.py
echo '"""Reserved for MCP adapter. See README.md."""' > src/quantumvitas/frontends/agent/__init__.py
touch src/quantumvitas/tools/__init__.py
touch src/quantumvitas/api/__init__.py
```

### Create Agent README

```bash
cat > src/quantumvitas/frontends/agent/README.md << 'EOF'
# Agent Adapter (Reserved)

This directory is reserved for the future MCP (Model Context Protocol) adapter.

## Purpose

When implemented, this adapter will:
1. Expose `quantumvitas.tools.*` functions as MCP tools
2. Handle MCP server lifecycle
3. Translate MCP requests to tool calls

## Implementation Notes

- The adapter MUST only import from `quantumvitas.tools.*`
- It MUST NOT import from `api/*`, `core/*`, or other kernel modules
- All operations go through the structured tool surface

## Status

**NOT YET IMPLEMENTED** - Placeholder only.
EOF
```

### Acceptance Criteria

```bash
# Directories exist
ls src/quantumvitas/frontends/
# Expected: __init__.py _shared/ agent/ cli/ daemon/ notebook/

ls src/quantumvitas/tools/
# Expected: __init__.py

ls src/quantumvitas/api/
# Expected: __init__.py

# Package is importable
python -c "import quantumvitas.frontends; print('OK')"
python -c "import quantumvitas.tools; print('OK')"
# Expected: OK (no errors)

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- LOW: Only creates empty files

---

## PR 3: Create ErrorSpec and API Package Structure

### Goal
Create `api/` package with `ErrorSpec`, `QVServiceError`, and `Result` types.

### Files Created/Modified

| Action | Path |
|--------|------|
| CREATE | `src/quantumvitas/api/errors.py` |
| CREATE | `src/quantumvitas/api/types.py` |
| MODIFY | `src/quantumvitas/api/__init__.py` |

### File: `src/quantumvitas/api/errors.py`

```python
"""Structured error model for API and tool surface."""

from dataclasses import dataclass, field
from typing import Any, Literal

ErrorCategory = Literal[
    "validation",
    "resource",
    "lock",
    "engine",
    "io",
    "schema",
    "internal",
]

@dataclass
class ErrorSpec:
    """
    Structured error for API and tool surface.

    All errors raised/returned from api/ and tools/ use this structure.
    Frontends MUST NOT parse exception message strings.
    """
    code: str
    category: ErrorCategory
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_actions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "evidence": self.evidence,
            "suggested_actions": self.suggested_actions,
            "details": self.details,
        }


class QVServiceError(Exception):
    """API-level exception carrying structured error."""

    def __init__(self, error_spec: ErrorSpec):
        self.error_spec = error_spec
        super().__init__(error_spec.message)

    def to_dict(self) -> dict[str, Any]:
        return self.error_spec.to_dict()


# Error code constants
class ErrorCodes:
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    CALC_NOT_FOUND = "CALC_NOT_FOUND"
    STEP_NOT_FOUND = "STEP_NOT_FOUND"
    STRUCTURE_NOT_FOUND = "STRUCTURE_NOT_FOUND"
    SELECTOR_AMBIGUOUS = "SELECTOR_AMBIGUOUS"
    LOCK_BUSY = "LOCK_BUSY"
    PARAM_INVALID = "PARAM_INVALID"
    PARAM_READONLY = "PARAM_READONLY"
    PATCH_NOT_VALIDATED = "PATCH_NOT_VALIDATED"
    ENGINE_EXEC_FAILED = "ENGINE_EXEC_FAILED"
    ENGINE_NOT_FOUND = "ENGINE_NOT_FOUND"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    YAML_PARSE_ERROR = "YAML_PARSE_ERROR"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

### File: `src/quantumvitas/api/types.py`

```python
"""Public return types for API and tool surface."""

from dataclasses import dataclass, asdict
from typing import Any, Generic, TypeVar

from .errors import ErrorSpec

T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    Structured return for tools/ surface.

    Tools never raise exceptions - they return Result with error.
    """
    success: bool
    data: T | None = None
    error: ErrorSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"success": self.success}
        if self.data is not None:
            if isinstance(self.data, dict):
                result["data"] = self.data
            elif hasattr(self.data, "to_dict"):
                result["data"] = self.data.to_dict()
            else:
                try:
                    result["data"] = asdict(self.data)
                except TypeError:
                    result["data"] = str(self.data)
        if self.error is not None:
            result["error"] = self.error.to_dict()
        return result

    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: ErrorSpec) -> "Result[T]":
        """Create a failed result."""
        return cls(success=False, error=error)
```

### File: `src/quantumvitas/api/__init__.py`

```python
"""
QMatSuite Public API.

This package is the SINGLE GATEWAY to kernel functionality.
All frontends (CLI, daemon, notebook) must use this API.
"""

from .errors import ErrorSpec, QVServiceError, ErrorCodes, ErrorCategory
from .types import Result

# Re-export QVService from legacy location (temporary)
# Will be moved to api/service.py in later PR
from quantumvitas.api_legacy import QVService

__all__ = [
    "QVService",
    "QVServiceError",
    "ErrorSpec",
    "ErrorCodes",
    "ErrorCategory",
    "Result",
]
```

### Temporary: Rename api.py

```bash
# Rename existing api.py to avoid conflict
git mv src/quantumvitas/api.py src/quantumvitas/api_legacy.py

# Update imports in api_legacy.py if needed (keep QVServiceError there for now)
```

### Acceptance Criteria

```bash
# Package imports work
python -c "from quantumvitas.api import QVService, ErrorSpec, Result; print('OK')"
# Expected: OK

# ErrorSpec is usable
python -c "
from quantumvitas.api import ErrorSpec, ErrorCodes
e = ErrorSpec(code=ErrorCodes.CALC_NOT_FOUND, category='resource', message='Not found')
print(e.to_dict())
"
# Expected: {'code': 'CALC_NOT_FOUND', 'category': 'resource', ...}

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- MEDIUM: Renaming api.py may break imports temporarily

### Rollback
```bash
git mv src/quantumvitas/api_legacy.py src/quantumvitas/api.py
rm -rf src/quantumvitas/api/
```

---

## PR 4: Add Project Edit Lock

### Goal
Add `project_edit_lock` for `project.qv.yml` writes.

### Files Modified

| Action | Path |
|--------|------|
| MODIFY | `src/quantumvitas/core/locking.py` |
| MODIFY | `src/quantumvitas/core/project_utils.py` |

### Changes to `core/locking.py`

Add after existing lock definitions:

```python
@contextmanager
def project_edit_lock(project_root: Path, timeout: float = 10.0):
    """
    Acquire exclusive lock for project.qv.yml writes.

    This prevents concurrent modifications to project-level config
    from CLI, daemon, and notebook.

    Args:
        project_root: Path to project root
        timeout: Lock acquisition timeout in seconds

    Raises:
        ProjectLockError: If lock cannot be acquired
    """
    lock_file = project_root / ".qv_project.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with portalocker.Lock(
            lock_file,
            timeout=timeout,
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
        ):
            yield
    except portalocker.LockException as e:
        raise ProjectLockError(
            f"Could not acquire project edit lock for {project_root}. "
            f"Another process may be modifying project.qv.yml."
        ) from e


class ProjectLockError(Exception):
    """Raised when project lock cannot be acquired."""
    pass
```

### Changes to `core/project_utils.py`

Find `save_project_config` function and wrap with lock:

```python
from quantumvitas.core.locking import project_edit_lock

def save_project_config(project_root: Path, config: dict) -> None:
    """Save project.qv.yml with exclusive lock."""
    with project_edit_lock(project_root):
        # ... existing save logic ...
```

### Acceptance Criteria

```bash
# Lock is importable
python -c "from quantumvitas.core.locking import project_edit_lock; print('OK')"
# Expected: OK

# Tests pass
pytest tests/ -v --tb=short -x

# Manual test: concurrent access (optional)
# Run two terminals trying to save project config simultaneously
```

### Risks
- LOW: Additive change

---

## PR 5: Create Tools Surface Skeleton

### Goal
Create `tools/` module with stub implementations that call API.

### Files Created

| Path | Purpose |
|------|---------|
| `src/quantumvitas/tools/__init__.py` | Exports all tools |
| `src/quantumvitas/tools/schema.py` | `discover()` |
| `src/quantumvitas/tools/calc.py` | `get_summary()`, `get_digest()` |
| `src/quantumvitas/tools/params.py` | `validate_patch()`, `apply_patch()` |
| `src/quantumvitas/tools/run.py` | `run_step()`, `run_calc()` |
| `src/quantumvitas/tools/results.py` | `extract()` |

### File: `src/quantumvitas/tools/__init__.py`

```python
"""
Agent-ready tool surface for QMatSuite.

These functions provide structured, machine-friendly access to QMatSuite operations.
They are designed for use by MCP adapters and programmatic access.

IMPORTANT: These modules MUST only import from quantumvitas.api.
Direct imports from core/, calculation/, drivers/ are FORBIDDEN.
"""

from .schema import discover
from .calc import get_summary, get_digest
from .params import validate_patch, apply_patch
from .run import run_step, run_calc
from .results import extract

__all__ = [
    "discover",
    "get_summary",
    "get_digest",
    "validate_patch",
    "apply_patch",
    "run_step",
    "run_calc",
    "extract",
]
```

### File: `src/quantumvitas/tools/schema.py`

```python
"""Schema discovery tool."""

from typing import Any, Literal

from quantumvitas.api import QVService, ErrorSpec, ErrorCodes
from quantumvitas.api.types import Result


def discover(
    *,
    project_root: str | None = None,
    scope: Literal["step_types", "params", "all"] = "all",
    engine: str | None = None,
    step_type: str | None = None,
) -> Result[dict[str, Any]]:
    """
    Discover available step types, parameter schemas, and ownership.

    Args:
        project_root: Optional project context (for project-specific schemas)
        scope: What to discover ("step_types", "params", "all")
        engine: Filter by engine family
        step_type: Filter by specific step type

    Returns:
        Result with discovery data or error
    """
    try:
        # Use QVService for discovery
        # Note: Some discovery may not need a project
        if project_root:
            svc = QVService(project_root)
            # TODO: Implement svc.discover_schema() method
            data = {"step_types": [], "param_schemas": {}}
        else:
            # Project-independent discovery
            data = {"step_types": [], "param_schemas": {}}

        return Result.ok(data)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
        ))
```

### File: `src/quantumvitas/tools/calc.py`

```python
"""Calculation summary and digest tools."""

from typing import Any

from quantumvitas.api import QVService, QVServiceError, ErrorSpec, ErrorCodes
from quantumvitas.api.types import Result


def get_summary(
    project_root: str,
    calc_selector: str,
) -> Result[dict[str, Any]]:
    """
    Get calculation summary (structure, steps, status).

    Args:
        project_root: Path to project root
        calc_selector: Calculation selector (name, slug, or ULID)

    Returns:
        Result with CalcSummary dict or error
    """
    try:
        svc = QVService(project_root)
        # TODO: Implement svc.get_calculation_summary() that returns structured data
        calc = svc.get_calculation(calc_selector)

        summary = {
            "id": calc.id if hasattr(calc, 'id') else str(calc),
            "name": getattr(calc, 'name', 'unknown'),
            "steps": [],
            "status": "unknown",
        }
        return Result.ok(summary)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
            evidence={"calc_selector": calc_selector},
        ))


def get_digest(
    project_root: str,
    run_id: str,
) -> Result[dict[str, Any]]:
    """
    Get digest of a completed run.

    Args:
        project_root: Path to project root
        run_id: Run identifier

    Returns:
        Result with RunDigest dict or error
    """
    try:
        svc = QVService(project_root)
        # TODO: Implement svc.get_run_digest()
        digest = {
            "run_id": run_id,
            "status": "unknown",
            "steps": [],
        }
        return Result.ok(digest)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
        ))
```

### File: `src/quantumvitas/tools/params.py`

```python
"""Parameter patch tools."""

from typing import Any

from quantumvitas.api import QVService, QVServiceError, ErrorSpec, ErrorCodes
from quantumvitas.api.types import Result


def validate_patch(
    project_root: str,
    step_selector: str,
    patch: dict[str, Any],
) -> Result[dict[str, Any]]:
    """
    Validate a parameter patch WITHOUT applying.

    Args:
        project_root: Path to project root
        step_selector: Step selector (calc/step format)
        patch: Parameter patch to validate

    Returns:
        Result with validation result (valid, normalized_patch, diff_preview, warnings, errors)
    """
    try:
        svc = QVService(project_root)
        # TODO: Implement svc.validate_step_patch()

        validation_result = {
            "valid": True,
            "normalized_patch": patch,
            "diff_preview": {},
            "warnings": [],
            "errors": [],
        }
        return Result.ok(validation_result)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
        ))


def apply_patch(
    project_root: str,
    step_selector: str,
    validated_patch: dict[str, Any],
) -> Result[dict[str, Any]]:
    """
    Apply a PREVIOUSLY VALIDATED patch.

    REQUIRES: Patch must have been validated via validate_patch first.
    ACQUIRES: calc_edit_lock

    Args:
        project_root: Path to project root
        step_selector: Step selector
        validated_patch: Previously validated patch

    Returns:
        Result with apply result (success, new_state)
    """
    try:
        svc = QVService(project_root)
        # TODO: Implement svc.apply_step_patch()

        apply_result = {
            "applied": True,
            "new_state": {},
        }
        return Result.ok(apply_result)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
        ))
```

### File: `src/quantumvitas/tools/run.py`

```python
"""Run execution tools."""

from typing import Any, Literal

from quantumvitas.api import QVService, QVServiceError, ErrorSpec, ErrorCodes
from quantumvitas.api.types import Result


def run_step(
    project_root: str,
    step_selector: str,
    *,
    mode: Literal["normal", "force"] = "normal",
) -> Result[dict[str, Any]]:
    """
    Run a single step.

    ACQUIRES: calc_run_lock

    Args:
        project_root: Path to project root
        step_selector: Step selector (calc/step format)
        mode: Run mode ("normal" or "force")

    Returns:
        Result with run result (status, timing, artifacts)
    """
    try:
        svc = QVService(project_root)
        # Parse step selector (calc/step format)
        if "/" in step_selector:
            calc_sel, step_sel = step_selector.rsplit("/", 1)
        else:
            raise ValueError(f"Invalid step selector format: {step_selector}. Expected 'calc/step'.")

        result = svc.run_step(calc_sel, step_sel, force=(mode == "force"))

        run_result = {
            "status": "completed" if result else "failed",
            "step_selector": step_selector,
        }
        return Result.ok(run_result)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
            evidence={"step_selector": step_selector},
        ))


def run_calc(
    project_root: str,
    calc_selector: str,
    *,
    mode: Literal["normal", "force", "continue"] = "normal",
) -> Result[dict[str, Any]]:
    """
    Run entire calculation.

    ACQUIRES: calc_run_lock

    Args:
        project_root: Path to project root
        calc_selector: Calculation selector
        mode: Run mode

    Returns:
        Result with run result (per-step status, timing, artifacts)
    """
    try:
        svc = QVService(project_root)
        result = svc.run_calculation(calc_selector, force=(mode == "force"))

        run_result = {
            "status": "completed" if result else "failed",
            "calc_selector": calc_selector,
            "steps": [],
        }
        return Result.ok(run_result)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
            evidence={"calc_selector": calc_selector},
        ))
```

### File: `src/quantumvitas/tools/results.py`

```python
"""Result extraction tools."""

from typing import Any, Literal

from quantumvitas.api import QVService, QVServiceError, ErrorSpec, ErrorCodes
from quantumvitas.api.types import Result


def extract(
    project_root: str,
    step_selector: str,
    artifact_type: Literal["energy", "bands", "dos", "structure", "all"],
) -> Result[dict[str, Any]]:
    """
    Extract canonical analysis result from completed step.

    Args:
        project_root: Path to project root
        step_selector: Step selector (calc/step format)
        artifact_type: Type of artifact to extract

    Returns:
        Result with extracted data (no file paths, structured data only)
    """
    try:
        svc = QVService(project_root)

        # Parse step selector
        if "/" in step_selector:
            calc_sel, step_sel = step_selector.rsplit("/", 1)
        else:
            raise ValueError(f"Invalid step selector format: {step_selector}")

        # TODO: Implement svc.extract_artifact()
        extract_result = {
            "artifact_type": artifact_type,
            "data": None,
            "meta": {
                "step_selector": step_selector,
            },
        }
        return Result.ok(extract_result)
    except QVServiceError as e:
        return Result.fail(e.error_spec)
    except Exception as e:
        return Result.fail(ErrorSpec(
            code=ErrorCodes.INTERNAL_ERROR,
            category="internal",
            message=str(e),
        ))
```

### Acceptance Criteria

```bash
# Tools are importable
python -c "
from quantumvitas.tools import (
    discover, get_summary, get_digest,
    validate_patch, apply_patch,
    run_step, run_calc, extract
)
print('OK')
"
# Expected: OK

# Tools do NOT import from core (CRITICAL CHECK)
rg "from quantumvitas\.core" src/quantumvitas/tools/
# Expected: 0 matches

rg "from quantumvitas\.calculation" src/quantumvitas/tools/
# Expected: 0 matches

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- LOW: Stub implementations

---

## PR 6: Create Import Rule Gate Tests

### Goal
Add tests that enforce import rules and will fail if violations are introduced.

### Files Created

| Path | Purpose |
|------|---------|
| `tests/gates/test_import_rules.py` | Import rule enforcement |

### File: `tests/gates/test_import_rules.py`

```python
"""
Gate tests for import rule enforcement.

These tests verify the architecture's import rules are not violated.
They should fail immediately if forbidden imports are added.
"""

import subprocess
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestFrontendImportRules:
    """Frontends must not import from kernel modules."""

    def _check_no_imports(self, source_dir: str, forbidden_pattern: str) -> list[str]:
        """Run ripgrep to find forbidden imports."""
        source_path = PROJECT_ROOT / source_dir
        if not source_path.exists():
            pytest.skip(f"Directory {source_dir} does not exist yet")

        result = subprocess.run(
            ["rg", "-l", forbidden_pattern, str(source_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
        return []

    def test_frontends_no_core_imports(self):
        """frontends/* must not import from core/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/frontends",
            r"from quantumvitas\.core"
        )
        assert violations == [], f"Forbidden core imports in frontends: {violations}"

    def test_frontends_no_calculation_imports(self):
        """frontends/* must not import from calculation/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/frontends",
            r"from quantumvitas\.calculation"
        )
        assert violations == [], f"Forbidden calculation imports in frontends: {violations}"

    def test_frontends_no_drivers_imports(self):
        """frontends/* must not import from drivers/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/frontends",
            r"from quantumvitas\.drivers"
        )
        assert violations == [], f"Forbidden drivers imports in frontends: {violations}"

    def test_frontends_no_analysis_imports(self):
        """frontends/* must not import from analysis/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/frontends",
            r"from quantumvitas\.analysis"
        )
        assert violations == [], f"Forbidden analysis imports in frontends: {violations}"

    def test_frontends_no_io_imports(self):
        """frontends/* must not import from io/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/frontends",
            r"from quantumvitas\.io"
        )
        assert violations == [], f"Forbidden io imports in frontends: {violations}"


class TestToolsImportRules:
    """Tools must only import from api."""

    def _check_no_imports(self, source_dir: str, forbidden_pattern: str) -> list[str]:
        source_path = PROJECT_ROOT / source_dir
        if not source_path.exists():
            pytest.skip(f"Directory {source_dir} does not exist yet")

        result = subprocess.run(
            ["rg", "-l", forbidden_pattern, str(source_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
        return []

    def test_tools_no_core_imports(self):
        """tools/* must not import from core/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/tools",
            r"from quantumvitas\.core"
        )
        assert violations == [], f"Forbidden core imports in tools: {violations}"

    def test_tools_no_calculation_imports(self):
        """tools/* must not import from calculation/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/tools",
            r"from quantumvitas\.calculation"
        )
        assert violations == [], f"Forbidden calculation imports in tools: {violations}"

    def test_tools_no_frontends_imports(self):
        """tools/* must not import from frontends/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/tools",
            r"from quantumvitas\.frontends"
        )
        assert violations == [], f"Forbidden frontends imports in tools: {violations}"


class TestAPIImportRules:
    """API must not import from frontends or tools."""

    def _check_no_imports(self, source_dir: str, forbidden_pattern: str) -> list[str]:
        source_path = PROJECT_ROOT / source_dir
        if not source_path.exists():
            pytest.skip(f"Directory {source_dir} does not exist yet")

        result = subprocess.run(
            ["rg", "-l", forbidden_pattern, str(source_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
        return []

    def test_api_no_frontends_imports(self):
        """api/* must not import from frontends/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/api",
            r"from quantumvitas\.frontends"
        )
        assert violations == [], f"Forbidden frontends imports in api: {violations}"

    def test_api_no_tools_imports(self):
        """api/* must not import from tools/*."""
        violations = self._check_no_imports(
            "src/quantumvitas/api",
            r"from quantumvitas\.tools"
        )
        assert violations == [], f"Forbidden tools imports in api: {violations}"


class TestCLIThinRules:
    """CLI must be thin - no selector resolution."""

    def _check_no_pattern(self, source_dir: str, pattern: str) -> list[str]:
        source_path = PROJECT_ROOT / source_dir
        if not source_path.exists():
            pytest.skip(f"Directory {source_dir} does not exist yet")

        result = subprocess.run(
            ["rg", "-l", pattern, str(source_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")
        return []

    def test_cli_no_resolve_functions(self):
        """CLI must not call resolve_* functions directly."""
        patterns = [
            r"resolve_calculation\(",
            r"resolve_step\(",
            r"resolve_structure\(",
        ]
        for pattern in patterns:
            violations = self._check_no_pattern(
                "src/quantumvitas/frontends/cli",
                pattern
            )
            assert violations == [], f"Forbidden resolve call in CLI: {violations}"
```

### Acceptance Criteria

```bash
# Gate tests run (may skip if dirs don't exist yet)
pytest tests/gates/test_import_rules.py -v

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- LOW: Test-only changes

---

## PR 7: Move Daemon to frontends/daemon/

### Goal
Move daemon code to `frontends/daemon/` and add compatibility shim.

### Files Changed

| Action | Path |
|--------|------|
| MOVE | `src/quantumvitas/daemon/server.py` → `src/quantumvitas/frontends/daemon/server.py` |
| MOVE | `src/quantumvitas/daemon/jobs.py` → `src/quantumvitas/frontends/daemon/jobs.py` |
| MODIFY | `src/quantumvitas/frontends/daemon/__init__.py` |
| MODIFY | `src/quantumvitas/daemon/__init__.py` (compatibility shim) |
| MODIFY | `gui/` references (if any) |

### Exact Commands

```bash
# 1. Move files
git mv src/quantumvitas/daemon/server.py src/quantumvitas/frontends/daemon/server.py
git mv src/quantumvitas/daemon/jobs.py src/quantumvitas/frontends/daemon/jobs.py

# 2. Copy any other files in daemon/
cp src/quantumvitas/daemon/*.py src/quantumvitas/frontends/daemon/ 2>/dev/null || true
```

### File: `src/quantumvitas/frontends/daemon/__init__.py`

```python
"""
GUI Daemon frontend for QMatSuite.

Provides JSON-RPC interface for the Electron GUI.
"""

from .server import QVDaemon, main

__all__ = ["QVDaemon", "main"]
```

### File: `src/quantumvitas/daemon/__init__.py` (Compatibility Shim)

```python
"""
DEPRECATED: Use quantumvitas.frontends.daemon instead.

This module is a compatibility shim that will be removed in a future version.
"""
import warnings

warnings.warn(
    "quantumvitas.daemon is deprecated. Use quantumvitas.frontends.daemon instead.",
    DeprecationWarning,
    stacklevel=2,
)

from quantumvitas.frontends.daemon import QVDaemon, main

__all__ = ["QVDaemon", "main"]
```

### Update Internal Imports in Moved Files

In `src/quantumvitas/frontends/daemon/server.py`, update relative imports:

```bash
# Find internal imports
rg "from quantumvitas.daemon" src/quantumvitas/frontends/daemon/

# Update to use frontends.daemon or absolute imports
```

### Acceptance Criteria

```bash
# Old import still works (with warning)
python -c "from quantumvitas.daemon import QVDaemon" 2>&1 | grep -i deprecat
# Expected: DeprecationWarning shown

# New import works
python -c "from quantumvitas.frontends.daemon import QVDaemon; print('OK')"
# Expected: OK

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- MEDIUM: GUI may reference old path

### Rollback
```bash
git mv src/quantumvitas/frontends/daemon/*.py src/quantumvitas/daemon/
```

---

## PR 8: Move CLI to frontends/cli/

### Goal
Move CLI code to `frontends/cli/` and add compatibility shim.

### Files Changed

| Action | Path |
|--------|------|
| MOVE | `src/quantumvitas/cli/main.py` → `src/quantumvitas/frontends/cli/app.py` |
| MOVE | `src/quantumvitas/cli/__main__.py` → `src/quantumvitas/frontends/cli/__main__.py` |
| MODIFY | `src/quantumvitas/frontends/cli/__init__.py` |
| MODIFY | `src/quantumvitas/cli/__init__.py` (compatibility shim) |
| MODIFY | `pyproject.toml` (entry point) |

### Exact Commands

```bash
# 1. Move files
git mv src/quantumvitas/cli/main.py src/quantumvitas/frontends/cli/app.py
git mv src/quantumvitas/cli/__main__.py src/quantumvitas/frontends/cli/__main__.py
```

### File: `src/quantumvitas/frontends/cli/__init__.py`

```python
"""
CLI frontend for QMatSuite.

Provides the `qv` command-line interface.
"""

from .app import app

__all__ = ["app"]
```

### File: `src/quantumvitas/frontends/cli/__main__.py`

```python
"""Entry point for python -m quantumvitas.frontends.cli"""
from .app import app

if __name__ == "__main__":
    app()
```

### File: `src/quantumvitas/cli/__init__.py` (Compatibility Shim)

```python
"""
DEPRECATED: Use quantumvitas.frontends.cli instead.

This module is a compatibility shim that will be removed in a future version.
"""
import warnings

warnings.warn(
    "quantumvitas.cli is deprecated. Use quantumvitas.frontends.cli instead.",
    DeprecationWarning,
    stacklevel=2,
)

from quantumvitas.frontends.cli import app

__all__ = ["app"]
```

### Update pyproject.toml

```toml
[project.scripts]
qv = "quantumvitas.frontends.cli:app"
```

### Acceptance Criteria

```bash
# Old import still works (with warning)
python -c "from quantumvitas.cli import app" 2>&1 | grep -i deprecat
# Expected: DeprecationWarning shown

# New import works
python -c "from quantumvitas.frontends.cli import app; print('OK')"
# Expected: OK

# CLI works
qv --help
# Expected: Help output

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- MEDIUM: Entry point change

### Rollback
```bash
git mv src/quantumvitas/frontends/cli/app.py src/quantumvitas/cli/main.py
# Revert pyproject.toml entry point
```

---

## PR 9: Create Notebook Frontend

### Goal
Create `frontends/notebook/` with convenience exports and display helpers.

### Files Created

| Path | Purpose |
|------|---------|
| `src/quantumvitas/frontends/notebook/__init__.py` | Convenience exports |
| `src/quantumvitas/frontends/notebook/display.py` | IPython display helpers |

### File: `src/quantumvitas/frontends/notebook/__init__.py`

```python
"""
Notebook frontend for QMatSuite.

Provides convenience imports and display helpers for Jupyter notebooks.

Usage:
    from quantumvitas import QVService
    from quantumvitas.frontends.notebook import display_bands, display_structure

    svc = QVService(project_root="/path/to/project")
    result = svc.run_calculation("my_calc")
    display_bands(result)
"""

# Re-export QVService for convenience
from quantumvitas.api import QVService, QVServiceError, ErrorSpec

# Display helpers
from .display import (
    display_structure,
    display_bands,
    display_dos,
    display_energy,
    display_calculation_summary,
)

__all__ = [
    # API
    "QVService",
    "QVServiceError",
    "ErrorSpec",
    # Display
    "display_structure",
    "display_bands",
    "display_dos",
    "display_energy",
    "display_calculation_summary",
]
```

### File: `src/quantumvitas/frontends/notebook/display.py`

```python
"""Display helpers for Jupyter notebooks."""

from typing import Any, Optional


def _get_ipython_display():
    """Get IPython display function if available."""
    try:
        from IPython.display import display, HTML
        return display, HTML
    except ImportError:
        return None, None


def display_structure(
    structure: Any,
    *,
    style: str = "ball_stick",
    size: tuple[int, int] = (600, 400),
) -> None:
    """
    Display structure visualization in notebook.

    Args:
        structure: Structure object or dict
        style: Visualization style
        size: Figure size (width, height)
    """
    display, HTML = _get_ipython_display()
    if display is None:
        print(f"Structure: {structure}")
        return

    # TODO: Integrate with 3D visualization library
    display(HTML(f"<p>Structure visualization (style={style})</p>"))


def display_bands(
    bands_data: Any,
    *,
    figsize: tuple[int, int] = (10, 6),
    title: Optional[str] = None,
) -> None:
    """
    Display band structure plot in notebook.

    Args:
        bands_data: Band structure data (dict or artifact)
        figsize: Figure size
        title: Optional plot title
    """
    display, HTML = _get_ipython_display()
    if display is None:
        print(f"Bands data: {bands_data}")
        return

    # TODO: Integrate with matplotlib plotting
    display(HTML(f"<p>Band structure plot</p>"))


def display_dos(
    dos_data: Any,
    *,
    figsize: tuple[int, int] = (10, 6),
    title: Optional[str] = None,
) -> None:
    """
    Display DOS plot in notebook.

    Args:
        dos_data: DOS data (dict or artifact)
        figsize: Figure size
        title: Optional plot title
    """
    display, HTML = _get_ipython_display()
    if display is None:
        print(f"DOS data: {dos_data}")
        return

    display(HTML(f"<p>DOS plot</p>"))


def display_energy(
    energy_data: Any,
    *,
    unit: str = "eV",
) -> None:
    """
    Display energy information.

    Args:
        energy_data: Energy data (dict or float)
        unit: Energy unit for display
    """
    display, HTML = _get_ipython_display()
    if display is None:
        print(f"Energy: {energy_data} {unit}")
        return

    if isinstance(energy_data, (int, float)):
        display(HTML(f"<p><strong>Energy:</strong> {energy_data:.6f} {unit}</p>"))
    else:
        display(HTML(f"<p><strong>Energy data:</strong> {energy_data}</p>"))


def display_calculation_summary(
    calc: Any,
) -> None:
    """
    Display calculation summary in notebook.

    Args:
        calc: Calculation object or summary dict
    """
    display, HTML = _get_ipython_display()
    if display is None:
        print(f"Calculation: {calc}")
        return

    # Build HTML summary
    html_parts = ["<div style='border: 1px solid #ddd; padding: 10px;'>"]
    html_parts.append("<h3>Calculation Summary</h3>")

    if hasattr(calc, 'id'):
        html_parts.append(f"<p><strong>ID:</strong> {calc.id}</p>")
    if hasattr(calc, 'name'):
        html_parts.append(f"<p><strong>Name:</strong> {calc.name}</p>")

    html_parts.append("</div>")
    display(HTML("".join(html_parts)))
```

### Acceptance Criteria

```bash
# Notebook imports work
python -c "
from quantumvitas.frontends.notebook import QVService, display_bands
print('OK')
"
# Expected: OK

# No daemon required
python -c "
from quantumvitas.frontends.notebook import QVService
# This should work without starting daemon
print('Direct import OK')
"
# Expected: Direct import OK

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- LOW: New module, no breaking changes

---

## PR 10: Refactor Daemon to Remove Core Imports

### Goal
Update daemon to use only `api/` - remove direct core imports.

### Changes Required

In `src/quantumvitas/frontends/daemon/server.py`:

1. **Remove direct core imports**:
```python
# REMOVE these lines:
from quantumvitas.core.exceptions import LegacyProjectError
from quantumvitas.core.resolution import (...)
from quantumvitas.core.project_utils import load_project_config
```

2. **Add API imports**:
```python
from quantumvitas.api import QVService, QVServiceError, ErrorSpec
```

3. **Update resolution calls to use QVService**:
```python
# BEFORE:
calc = resolve_calculation(project_root, selector, config)

# AFTER:
svc = QVService(project_root)
calc = svc.resolve_calculation(selector)
```

### Verification Commands

```bash
# After changes, this must return 0 matches:
rg "from quantumvitas\.core" src/quantumvitas/frontends/daemon/
# Expected: 0 matches

# Gate tests pass
pytest tests/gates/test_import_rules.py -v
```

### Acceptance Criteria

```bash
# No core imports in daemon
rg "from quantumvitas\.core" src/quantumvitas/frontends/daemon/
# Expected: 0 matches

# Daemon still works
python -c "from quantumvitas.frontends.daemon import QVDaemon; print('OK')"
# Expected: OK

# Tests pass
pytest tests/ -v --tb=short -x
```

### Risks
- MEDIUM: Daemon functionality depends on resolution working through API

---

## PR 11: Refactor CLI to Remove Core Imports (Incremental)

### Goal
Begin refactoring CLI to use only `api/`. This is the largest PR and may need to be split further.

### Strategy

1. **Phase A**: Add missing API methods to `QVService`
2. **Phase B**: Update CLI commands one by one
3. **Phase C**: Remove core imports

### Phase A: Add Missing API Methods

Add to `api/service.py` (or `api_legacy.py`):

```python
class QVService:
    # ... existing methods ...

    def resolve_calculation(self, selector: str):
        """Resolve calculation selector to Calculation object."""
        from quantumvitas.core.resolution import resolve_calculation
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(self.project_root)
        return resolve_calculation(self.project_root, selector, config)

    def resolve_step(self, calc_selector: str, step_selector: str):
        """Resolve step selector to Step object."""
        from quantumvitas.core.resolution import resolve_step
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(self.project_root)
        return resolve_step(self.project_root, calc_selector, step_selector, config)

    def detect_context(self, cwd: str) -> dict:
        """Detect project/calculation context from working directory."""
        from quantumvitas.core.context import find_path_context_from_pwd
        return find_path_context_from_pwd(Path(cwd))
```

### Phase B: Update CLI Commands

For each command in `frontends/cli/app.py`:

```python
# BEFORE:
from quantumvitas.core.resolution import resolve_calculation
@app.command()
def show(calc: str):
    calc_obj = resolve_calculation(project_root, calc, config)

# AFTER:
from quantumvitas.api import QVService
@app.command()
def show(calc: str):
    svc = QVService(project_root)
    calc_obj = svc.resolve_calculation(calc)
```

### Verification Commands

```bash
# Track progress:
rg "from quantumvitas\.core" src/quantumvitas/frontends/cli/ | wc -l
# Goal: Reduce to 0

# After each batch of changes:
pytest tests/ -v --tb=short -x
```

### Acceptance Criteria

```bash
# No core imports in CLI
rg "from quantumvitas\.core" src/quantumvitas/frontends/cli/
# Expected: 0 matches

# No resolution functions called directly
rg "resolve_calculation\(|resolve_step\(" src/quantumvitas/frontends/cli/
# Expected: 0 matches

# CLI works
qv list calcs --help
qv run --help

# Tests pass
pytest tests/ -v --tb=short -x

# Gate tests pass
pytest tests/gates/test_import_rules.py -v
```

### Risks
- HIGH: Large refactor, may break CLI functionality

### Rollback
- Revert individual command changes if tests fail

---

## PR 12: Cleanup and Final Verification

### Goal
Remove compatibility shims (optional), final verification, documentation update.

### Tasks

1. **Run full test suite**
2. **Run all gate tests**
3. **Run repo audit commands**
4. **Update documentation**

### Final Verification Commands

```bash
# === Import Rule Verification ===

# 1. Frontends have no kernel imports
rg "from quantumvitas\.core" src/quantumvitas/frontends/
rg "from quantumvitas\.calculation" src/quantumvitas/frontends/
rg "from quantumvitas\.drivers" src/quantumvitas/frontends/
rg "from quantumvitas\.analysis" src/quantumvitas/frontends/
rg "from quantumvitas\.io" src/quantumvitas/frontends/
# Expected: All return 0 matches

# 2. Tools have no kernel imports
rg "from quantumvitas\.core" src/quantumvitas/tools/
rg "from quantumvitas\.calculation" src/quantumvitas/tools/
# Expected: All return 0 matches

# 3. API has no frontend/tools imports
rg "from quantumvitas\.frontends" src/quantumvitas/api/
rg "from quantumvitas\.tools" src/quantumvitas/api/
# Expected: All return 0 matches

# 4. CLI is thin (no resolve functions)
rg "resolve_calculation\(|resolve_step\(|resolve_structure\(" src/quantumvitas/frontends/cli/
# Expected: 0 matches

# === Functional Tests ===

# 5. All tests pass
pytest tests/ -v

# 6. Gate tests pass
pytest tests/gates/ -v

# 7. CLI works
qv --help
qv list --help

# 8. Jupyter import works
python -c "
from quantumvitas import QVService
from quantumvitas.frontends.notebook import display_bands
print('Jupyter import OK')
"

# 9. Tools import works
python -c "
from quantumvitas.tools import discover, run_calc, validate_patch
print('Tools import OK')
"

# === Directory Structure ===

# 10. scripts/ exists (not tools/)
ls scripts/
# Expected: Maintenance scripts

ls tools/ 2>&1 | grep -i "no such"
# Expected: No such file or directory
```

### Update README.md

Add section about new module structure:

```markdown
## Module Structure

- `quantumvitas.api` - Public API (use this)
- `quantumvitas.tools` - Agent-ready tool surface
- `quantumvitas.frontends.cli` - CLI frontend
- `quantumvitas.frontends.daemon` - GUI daemon
- `quantumvitas.frontends.notebook` - Jupyter helpers
```

### Acceptance Criteria

All verification commands pass with expected output.

---

## Test Strategy Summary

### Required Test Suites

| Suite | When to Run | Purpose |
|-------|-------------|---------|
| `pytest tests/` | Every PR | Full test coverage |
| `pytest tests/gates/` | Every PR | Import rule enforcement |
| `pytest tests/gates/test_import_rules.py` | After any frontend/api/tools change | Verify architecture |

### New Tests Added

| Test | PR | Purpose |
|------|-----|---------|
| `test_import_rules.py` | PR 6 | Enforce import rules |
| `test_jupyter_smoke.py` | PR 9 | Verify Jupyter works without daemon |

### Repo Audit Script

Create `scripts/audit_imports.sh`:

```bash
#!/bin/bash
# Audit import rules for multi-frontend architecture

echo "=== Frontend Import Audit ==="
echo "Checking frontends/ for forbidden imports..."

VIOLATIONS=0

for pattern in "quantumvitas\.core" "quantumvitas\.calculation" "quantumvitas\.drivers" "quantumvitas\.analysis" "quantumvitas\.io"; do
    count=$(rg -c "from $pattern" src/quantumvitas/frontends/ 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
    if [ "$count" -gt 0 ]; then
        echo "  VIOLATION: $count imports matching 'from $pattern' in frontends/"
        VIOLATIONS=$((VIOLATIONS + count))
    fi
done

echo ""
echo "=== Tools Import Audit ==="
echo "Checking tools/ for forbidden imports..."

for pattern in "quantumvitas\.core" "quantumvitas\.calculation"; do
    count=$(rg -c "from $pattern" src/quantumvitas/tools/ 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
    if [ "$count" -gt 0 ]; then
        echo "  VIOLATION: $count imports matching 'from $pattern' in tools/"
        VIOLATIONS=$((VIOLATIONS + count))
    fi
done

echo ""
echo "=== API Import Audit ==="
for pattern in "quantumvitas\.frontends" "quantumvitas\.tools"; do
    count=$(rg -c "from $pattern" src/quantumvitas/api/ 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
    if [ "$count" -gt 0 ]; then
        echo "  VIOLATION: $count imports matching 'from $pattern' in api/"
        VIOLATIONS=$((VIOLATIONS + count))
    fi
done

echo ""
if [ "$VIOLATIONS" -gt 0 ]; then
    echo "FAILED: $VIOLATIONS total violations found"
    exit 1
else
    echo "PASSED: No import violations found"
    exit 0
fi
```

---

## Risk Summary

| PR | Risk Level | Main Risk |
|----|------------|-----------|
| PR 1 | LOW | Broken CI references |
| PR 2 | LOW | None |
| PR 3 | MEDIUM | Breaking api.py rename |
| PR 4 | LOW | None |
| PR 5 | LOW | None |
| PR 6 | LOW | None |
| PR 7 | MEDIUM | GUI spawn path |
| PR 8 | MEDIUM | Entry point change |
| PR 9 | LOW | None |
| PR 10 | MEDIUM | Daemon functionality |
| PR 11 | HIGH | CLI functionality |
| PR 12 | LOW | None |

---

## Rollback Strategy

Each PR can be reverted independently:

```bash
git revert <commit-hash>
```

For multi-commit PRs, use:

```bash
git revert --no-commit <first-commit>..<last-commit>
git commit -m "Revert: <PR description>"
```

---

## Timeline

**No time estimates provided** - PRs should be merged when ready and tests pass.

Recommended order:
1. PR 1-2: Foundation (can be done quickly)
2. PR 3-6: API/Tools setup
3. PR 7-9: Frontend relocation
4. PR 10-11: Refactoring (most effort)
5. PR 12: Cleanup

---

*End of implementation plan.*
