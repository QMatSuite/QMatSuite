# Multi-Frontend Architecture Specification

**Version**: 2.0
**Date**: 2026-01-21
**Status**: DESIGN SPECIFICATION (HARDENED)
**Supersedes**: Version 1.0
**Authors**: Architecture Team

---

## Executive Summary

This document specifies the target architecture for QMatSuite's "single core, multi-frontends" refactor with **strict, non-negotiable boundaries**. This version hardens all rules to eliminate loopholes and technical debt.

**Core Principles (Non-Negotiable)**:

1. **Frontends MUST NOT import kernel modules** - `frontends/*` and `tools/*` can ONLY call `api/*`
2. **CLI must be thin** - No selector resolution, no business logic, no caching inside CLI
3. **Daemon cache is derived** - Caches are discardable, not semantic truth
4. **Jupyter needs no daemon** - Direct import path via `api/`
5. **`tools/` calls `api/` only** - No escape hatch for "tools importing core primitives"
6. **ErrorSpec is mandatory** - All errors surfaced to frontends use structured `ErrorSpec`

This refactor does NOT redesign the SSOT philosophy, history system, or introduce a database.

---

## 1. Target Module Layout

### 1.1 Python Package Structure

```
src/qmatsuite/
├── __init__.py              # Public exports: QMSService, ErrorSpec, key models
│
├── api/                     # PUBLIC API LAYER (single entry point to kernel)
│   ├── __init__.py          # Exports QMSService, ErrorSpec, all public operations
│   ├── service.py           # QMSService class implementation
│   ├── errors.py            # ErrorSpec, QMSServiceError, error codes
│   ├── types.py             # Public return types (Result wrappers, digests)
│   └── resolution.py        # Selector resolution (moved FROM cli)
│
├── tools/                   # AGENT-READY TOOL SURFACE (stable primitives)
│   ├── __init__.py          # Exports all tool functions
│   ├── schema.py            # schema.discover
│   ├── calc.py              # calc.get_summary, run.get_digest
│   ├── params.py            # params.validate_patch, params.apply_patch
│   ├── run.py               # run.step, run.calc
│   └── results.py           # results.extract
│
├── frontends/               # THIN FRONTEND LAYERS (no business logic)
│   ├── __init__.py
│   ├── _shared/             # Optional shared frontend utilities (display, formatting)
│   │   ├── __init__.py
│   │   └── display.py       # Shared formatting helpers
│   │
│   ├── cli/                 # CLI frontend (thin Typer wrapper)
│   │   ├── __init__.py
│   │   ├── app.py           # Typer app definition
│   │   ├── __main__.py      # Entry point
│   │   └── commands/        # Command handlers (parameter adaptation ONLY)
│   │
│   ├── daemon/              # GUI daemon (JSON-RPC transport)
│   │   ├── __init__.py
│   │   ├── server.py        # JSON-RPC server
│   │   ├── jobs.py          # Job queue (transport-level only)
│   │   ├── cache.py         # Derived caches (discardable)
│   │   └── handlers/        # RPC handlers (adapt → call api → format response)
│   │
│   ├── notebook/            # Jupyter integration
│   │   ├── __init__.py      # Convenience exports for notebooks
│   │   └── display.py       # IPython display helpers
│   │
│   └── agent/               # Reserved MCP adapter (placeholder)
│       ├── __init__.py      # Placeholder with README
│       ├── README.md        # Documents future MCP integration
│       └── adapter.py       # Reserved: MCP → tools/ translation
│
├── core/                    # KERNEL: Engine-agnostic business logic
│   ├── __init__.py
│   ├── models.py            # Calculation, Step, Project dataclasses
│   ├── resolution.py        # Internal selector resolution (used by api)
│   ├── locking.py           # calc_run_lock, calc_edit_lock, project_edit_lock
│   ├── resources.py         # ResourceMeta, ID generation
│   ├── project_utils.py     # Project config operations
│   ├── context.py           # Path context helpers
│   ├── settings.py          # Global settings
│   ├── param_validation.py  # Parameter validation
│   ├── yamldoc.py           # YAML document operations
│   ├── exceptions.py        # Core exceptions (internal, not surfaced)
│   └── ...                  # Other kernel modules
│
├── drivers/                 # ENGINE DRIVERS (per-engine bundles)
│   ├── __init__.py
│   ├── qe/                  # Quantum ESPRESSO driver
│   ├── vasp/                # VASP driver
│   ├── lammps/              # LAMMPS driver
│   ├── orca/                # ORCA driver
│   ├── pyscf/               # PySCF driver
│   ├── cp2k/                # CP2K driver
│   └── w90/                 # Wannier90 driver
│
├── calculation/             # CALCULATION ORCHESTRATION
│   └── ...
│
├── analysis/                # POST-PROCESSING
│   └── ...
│
├── io/                      # STRUCTURE/FORMAT I/O
│   └── ...
│
└── ...                      # Other kernel modules
```

### 1.2 Repo-Level Layout

```
QMatSuite/
├── src/qmatsuite/        # Python package (as above)
├── gui/                     # Electron GUI (calls daemon)
├── tests/                   # pytest test suite
│   ├── gates/               # Architecture enforcement tests
│   │   └── test_import_rules.py  # Forbidden import detection
│   └── ...
├── scripts/                 # Maintenance/dev scripts (RENAMED from tools/)
│   ├── extract_qe_parameters_v3.py
│   ├── generate_demo_snapshots.py
│   └── ...
├── resources/               # Templates, demos, pseudo libraries
├── docs/                    # Documentation
│   ├── specs/               # Architecture specs (this doc)
│   └── ...
└── pyproject.toml           # Package configuration
```

**CRITICAL**: The repo-level `tools/` directory MUST be renamed to `scripts/` to avoid conflict with the Python-package `qmatsuite/tools/` module.

---

## 2. Dependency Rules (Constitution)

### 2.1 Import Rule Matrix (STRICTLY ENFORCED)

| From | May Import | MUST NOT Import |
|------|------------|-----------------|
| `frontends/cli/*` | `api/*`, `frontends/_shared/*` | `core/*`, `calculation/*`, `drivers/*`, `analysis/*`, `io/*`, `tools/*`† |
| `frontends/daemon/*` | `api/*`, `frontends/_shared/*` | `core/*`, `calculation/*`, `drivers/*`, `analysis/*`, `io/*`, `cli/*` |
| `frontends/notebook/*` | `api/*`, `frontends/_shared/*` | `core/*`, `calculation/*`, `drivers/*`, `analysis/*`, `io/*`, `daemon/*` |
| `frontends/agent/*` | `tools/*` | `api/*`‡, `core/*`, `calculation/*`, `drivers/*` |
| `frontends/_shared/*` | `api/*` (types only) | `core/*`, `calculation/*`, `drivers/*` |
| `tools/*` | `api/*` | `core/*`, `calculation/*`, `drivers/*`, `frontends/*` |
| `api/*` | `core/*`, `calculation/*`, `drivers/*`, `analysis/*`, `io/*` | `frontends/*`, `tools/*` |
| `core/*` | `io/*`, `data/*` | `frontends/*`, `api/*`, `tools/*`, `calculation/*`§ |
| `calculation/*` | `core/*`, `drivers/*`, `io/*` | `frontends/*`, `api/*`, `tools/*` |
| `drivers/*` | `core/*`, `io/*` | `frontends/*`, `api/*`, `tools/*`, other `drivers/*` |

**Notes**:
- † CLI may import `tools/*` for result type definitions but NOT for calling tool functions (use api)
- ‡ Agent adapter imports `tools/*` only (structured surface); api is for interactive frontends
- § Some calculation modules may be imported by core; minimize this coupling

### 2.2 Explicit Prohibitions (No Exceptions)

**PROHIBITION 1: Frontends cannot import kernel modules**
```python
# FORBIDDEN in frontends/*
from qmatsuite.core.resolution import resolve_calculation  # NO
from qmatsuite.calculation.runner import CalculationRunner  # NO
from qmatsuite.drivers.qe import QEDriver  # NO
from qmatsuite.analysis.parsers import parse_bands  # NO
```

**PROHIBITION 2: CLI cannot do selector resolution**
```python
# FORBIDDEN in frontends/cli/*
from qmatsuite.core.resolution import resolve_calculation  # NO
calc = resolve_calculation(project_root, selector)  # NO

# REQUIRED: Use api layer
from qmatsuite.api import QMSService
svc = QMSService(project_root)
calc = svc.resolve_calculation(selector)  # YES
```

**PROHIBITION 3: tools/* cannot import core directly**
```python
# FORBIDDEN in tools/*
from qmatsuite.core.models import Calculation  # NO
from qmatsuite.core.locking import calc_run_lock  # NO

# REQUIRED: Use api layer
from qmatsuite.api import QMSService
svc = QMSService(project_root)
result = svc.run_step(selector)  # YES
```

**PROHIBITION 4: Daemon cannot implement business logic**
```python
# FORBIDDEN in frontends/daemon/*
# Daemon must NOT validate parameters itself
if ecutwfc < 10:  # NO - business logic
    raise ValueError("ecutwfc too low")

# REQUIRED: Call api which does validation
result = svc.configure_step(selector, params)  # api validates
```

### 2.3 Dependency Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTENDS                                   │
│   ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐               │
│   │   CLI   │   │ Daemon  │   │ Notebook │   │  Agent  │               │
│   │ (thin)  │   │ (cache) │   │ (direct) │   │  (MCP)  │               │
│   └────┬────┘   └────┬────┘   └────┬─────┘   └────┬────┘               │
│        │             │             │              │                     │
│        │             │             │              │ tools/ only         │
│        └─────────────┴──────┬──────┴──────────────┤                     │
│                             │                     │                     │
│                             ▼                     ▼                     │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    api/ + tools/                                 │  │
│   │           (Public API Surface - SINGLE GATEWAY)                  │  │
│   │   • api/: QMSService, ErrorSpec, selector resolution              │  │
│   │   • tools/: Structured primitives for agents                     │  │
│   └──────────────────────────┬──────────────────────────────────────┘  │
│                              │                                          │
│                              │ ONLY api/ crosses this line              │
│                              ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │        core/ + calculation/ + drivers/ + analysis/ + io/         │  │
│   │                    (KERNEL - Protected)                          │  │
│   └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CLI Must Be Thin (No Selector Resolution)

### 3.1 What CLI Does (Allowed)

1. **Parse command-line arguments** (Typer handles this)
2. **Adapt parameters** (CLI flags → Python dict/kwargs)
3. **Call `api.QMSService` methods** (all business operations)
4. **Format output** (print, table, JSON, etc.)
5. **Handle user interaction** (prompts, confirmations)
6. **Detect path context** (find project root from cwd) - BUT context detection only, not resolution

### 3.2 What CLI Must NOT Do (Prohibited)

1. **Selector resolution** - Must use `svc.resolve_*()` methods
2. **Parameter validation** - Must use `svc.validate_*()` or let api validate
3. **Business logic decisions** - No "if step done, skip" - api decides
4. **Direct YAML read/write** - Must use api methods
5. **Direct file path construction** - Api returns paths
6. **Caching** - CLI is one-shot, no state between invocations

### 3.3 Example: Before and After

**BEFORE (Violation)**:
```python
# cli/main.py - WRONG
from qmatsuite.core.resolution import resolve_calculation, resolve_step
from qmatsuite.core.project_utils import load_project_config
from qmatsuite.calculation.runner import CalculationRunner

@app.command()
def run(calc_selector: str):
    config = load_project_config(project_root)  # Direct core import
    calc = resolve_calculation(project_root, calc_selector, config)  # Resolution in CLI
    runner = CalculationRunner(calc)  # Direct calculation import
    runner.run()  # Business logic in CLI
```

**AFTER (Compliant)**:
```python
# frontends/cli/app.py - CORRECT
from qmatsuite.api import QMSService, QMSServiceError

@app.command()
def run(calc_selector: str):
    svc = QMSService(project_root)
    try:
        result = svc.run_calculation(calc_selector)  # Api handles everything
        display_run_result(result)  # CLI only formats output
    except QMSServiceError as e:
        display_error(e.error_spec)  # Structured error handling
```

### 3.4 API Methods Required for CLI

The following methods must exist in `QMSService` to support CLI operations:

| CLI Command | Required API Method |
|-------------|---------------------|
| `qms run <calc>` | `svc.run_calculation(selector)` |
| `qms run <calc>/<step>` | `svc.run_step(selector)` |
| `qms list calcs` | `svc.list_calculations()` |
| `qms list steps <calc>` | `svc.list_steps(calc_selector)` |
| `qms show <calc>` | `svc.get_calculation(selector)` |
| `qms config <step> --set ...` | `svc.configure_step(selector, params)` |
| `qms import <file>` | `svc.import_structure(path)` |
| `qms resolve <selector>` | `svc.resolve_selector(selector)` |
| Context detection | `svc.detect_context(cwd)` → returns dict |

---

## 4. Daemon: Cache Is Derived, Not Truth

### 4.1 What Daemon Cache May Contain

The daemon is the only long-lived process (for GUI). It may cache:

1. **ResourceIndex** - Mapping of IDs/selectors to paths (derived from YAML)
2. **Project metadata** - Name, structure count, etc. (derived from project.qms.yml)
3. **Step status** - Done/pending/running (derived from step.done.yaml)
4. **File watchers** - Track changes to invalidate cache

### 4.2 Cache Invariants (Non-Negotiable)

| Rule | Description |
|------|-------------|
| **INVARIANT 1** | Cache is always discardable - daemon restart rebuilds from YAML |
| **INVARIANT 2** | Cache never defines truth - YAML files are SSOT |
| **INVARIANT 3** | Cache invalidation on YAML change - watcher or explicit reload |
| **INVARIANT 4** | All mutations go through api - daemon never writes YAML directly |
| **INVARIANT 5** | No business rules in cache logic - only indexing and lookup |

### 4.3 What Daemon Must NOT Do

```python
# FORBIDDEN in frontends/daemon/*

# 1. Direct YAML writes
yaml.safe_dump(data, file)  # NO - use svc.save_*()

# 2. Parameter validation
if params['ecutwfc'] < 10:  # NO - api validates
    raise ValueError()

# 3. Step execution decisions
if step.is_done():  # NO - api decides
    return

# 4. Selector resolution logic
if '/' in selector:  # NO - api resolves
    calc, step = selector.split('/')
```

### 4.4 What Daemon Does (Allowed)

1. **Transport** - JSON-RPC request/response handling
2. **Cache management** - Derived indices, invalidation
3. **Job queue** - Track running jobs (transport-level)
4. **Log streaming** - Pipe subprocess output to GUI
5. **Subscriptions** - Notify GUI of state changes
6. **Call api for ALL semantic operations**

---

## 5. Jupyter Shape: No Daemon Required

### 5.1 Direct Import Pattern

```python
# In Jupyter notebook - NO DAEMON NEEDED
from qmatsuite import QMSService

# Initialize with explicit project path
svc = QMSService(project_root="/home/user/my_project")

# All operations through api
structures = svc.list_structures()
result = svc.run_calculation("si_dos")

# Display helpers (optional)
from qmatsuite.frontends.notebook import display_bands
display_bands(result.artifacts['bands'])
```

### 5.2 Locking Model

| Lock | Scope | Acquired By |
|------|-------|-------------|
| `calc_run_lock` | Per-calculation | `svc.run_calculation()`, `svc.run_step()` |
| `calc_edit_lock` | Per-calculation | `svc.configure_step()`, `svc.save_*()` |
| `project_edit_lock` | Per-project | `svc.save_project_config()` (NEW) |

**Lock Implementation**:
- All locks are file-based (portalocker)
- Locks prevent conflicts between CLI/daemon/notebook
- Notebook user sees lock error if calculation is running from GUI

### 5.3 Project-Level Lock (NEW)

The current codebase lacks locking for `project.qms.yml` writes. This must be added:

```python
# core/locking.py (NEW)
@contextmanager
def project_edit_lock(project_root: Path):
    """Acquire exclusive lock for project.qms.yml writes."""
    lock_file = project_root / ".qms_project.lock"
    with portalocker.Lock(lock_file, timeout=5):
        yield
```

---

## 6. Agent-Ready Tool Surface

### 6.1 Location and Rules

All agent-callable primitives live in `qmatsuite/tools/`. These modules:

- **MUST** import only from `api/*`
- **MUST** return structured dicts (JSON-serializable)
- **MUST** use `ErrorSpec` for all errors (never raise string exceptions)
- **MUST** have stable function signatures

### 6.2 Reserved Primitives

#### `schema.discover`

```python
# qmatsuite/tools/schema.py

from qmatsuite.api import QMSService
from qmatsuite.api.types import Result

def discover(
    *,
    project_root: str | None = None,
    scope: Literal["step_types", "params", "all"] = "all",
    engine: str | None = None,
    step_type: str | None = None,
) -> Result[DiscoverResult]:
    """
    Discover available step types, parameter schemas, and ownership.

    Returns Result with:
    - success: True/False
    - data: DiscoverResult dict
    - error: ErrorSpec if failed
    """
```

#### `calc.get_summary`

```python
# qmatsuite/tools/calc.py

def get_summary(
    project_root: str,
    calc_selector: str,
) -> Result[CalcSummary]:
    """
    Get calculation summary (structure, steps, status).

    Returns Result with structured overview, no file paths.
    """
```

#### `params.validate_patch` / `params.apply_patch`

```python
# qmatsuite/tools/params.py

def validate_patch(
    project_root: str,
    step_selector: str,
    patch: dict[str, Any],
) -> Result[PatchValidationResult]:
    """
    Validate a parameter patch WITHOUT applying.

    Returns Result with:
    - valid: bool
    - normalized_patch: Patch with defaults
    - diff_preview: Before/after comparison
    - warnings: Non-fatal issues
    - errors: List[ErrorSpec] if invalid
    """

def apply_patch(
    project_root: str,
    step_selector: str,
    validated_patch: dict[str, Any],
) -> Result[PatchApplyResult]:
    """
    Apply a PREVIOUSLY VALIDATED patch.

    REQUIRES: Patch must have been validated first
    ACQUIRES: calc_edit_lock
    RECORDS: Edit event in history
    """
```

#### `run.step` / `run.calc`

```python
# qmatsuite/tools/run.py

def run_step(
    project_root: str,
    step_selector: str,
    *,
    mode: Literal["normal", "force"] = "normal",
) -> Result[RunResult]:
    """
    Run a single step.

    ACQUIRES: calc_run_lock
    """

def run_calc(
    project_root: str,
    calc_selector: str,
    *,
    mode: Literal["normal", "force", "continue"] = "normal",
) -> Result[RunResult]:
    """
    Run entire calculation.

    ACQUIRES: calc_run_lock
    """
```

#### `results.extract`

```python
# qmatsuite/tools/results.py

def extract(
    project_root: str,
    step_selector: str,
    artifact_type: Literal["energy", "bands", "dos", "structure", "all"],
) -> Result[ExtractResult]:
    """
    Extract canonical analysis result from completed step.

    Returns structured data directly - no path guessing.
    """
```

### 6.3 Future MCP Adapter Pattern

```python
# qmatsuite/frontends/agent/adapter.py (reserved)

# When implementing MCP, the adapter translates MCP requests to tools/ calls:
#
# MCP Request: {"tool": "qmatsuite.params.validate_patch", "params": {...}}
#     ↓
# from qmatsuite.tools.params import validate_patch
# result = validate_patch(**params)
#     ↓
# MCP Response: {"result": result.to_dict()}
```

---

## 7. Structured Error Model: ErrorSpec

### 7.1 ErrorSpec Definition

```python
# qmatsuite/api/errors.py

from dataclasses import dataclass, field
from typing import Any, Literal

ErrorCategory = Literal[
    "validation",      # Input validation failed
    "resource",        # Resource not found / selector error
    "lock",            # Lock acquisition failed
    "engine",          # Engine execution error
    "io",              # File I/O error
    "schema",          # Schema/format error
    "internal",        # Unexpected internal error
]

@dataclass
class ErrorSpec:
    """
    Structured error for API and tool surface.

    All errors raised/returned from api/ and tools/ use this structure.
    Frontends MUST NOT parse exception message strings.
    """
    code: str                          # Machine-readable (e.g., "CALC_NOT_FOUND")
    category: ErrorCategory            # Error category
    message: str                       # Human-readable message
    evidence: dict[str, Any] = field(default_factory=dict)  # Context data
    suggested_actions: list[str] = field(default_factory=list)  # What to do
    details: dict[str, Any] = field(default_factory=dict)  # Additional info

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "message": self.message,
            "evidence": self.evidence,
            "suggested_actions": self.suggested_actions,
            "details": self.details,
        }
```

### 7.2 QMSServiceError

```python
class QMSServiceError(Exception):
    """API-level exception carrying structured error."""

    def __init__(self, error_spec: ErrorSpec):
        self.error_spec = error_spec
        super().__init__(error_spec.message)

    def to_dict(self) -> dict[str, Any]:
        return self.error_spec.to_dict()
```

### 7.3 Result Wrapper for tools/

```python
# qmatsuite/api/types.py

from dataclasses import dataclass
from typing import Generic, TypeVar

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
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data if isinstance(self.data, dict) else asdict(self.data)
        if self.error is not None:
            result["error"] = self.error.to_dict()
        return result
```

### 7.4 Error Codes (Initial Set)

| Code | Category | Description |
|------|----------|-------------|
| `PROJECT_NOT_FOUND` | resource | Project root does not exist |
| `CALC_NOT_FOUND` | resource | Calculation selector did not match |
| `STEP_NOT_FOUND` | resource | Step selector did not match |
| `STRUCTURE_NOT_FOUND` | resource | Structure selector did not match |
| `SELECTOR_AMBIGUOUS` | resource | Selector matched multiple resources |
| `LOCK_BUSY` | lock | Resource is locked |
| `PARAM_INVALID` | validation | Parameter value is invalid |
| `PARAM_READONLY` | validation | Attempted to modify managed parameter |
| `PATCH_NOT_VALIDATED` | validation | apply_patch called without validate_patch |
| `ENGINE_EXEC_FAILED` | engine | Engine subprocess returned error |
| `ENGINE_NOT_FOUND` | engine | Required binary not found |
| `ARTIFACT_NOT_FOUND` | io | Required file does not exist |
| `YAML_PARSE_ERROR` | schema | YAML parse failed |
| `SCHEMA_MISMATCH` | schema | Data does not match expected schema |
| `INTERNAL_ERROR` | internal | Unexpected internal error |

---

## 8. Success Criteria

This refactor is complete when ALL of the following are true:

### 8.1 Import Rules (Verified by Tests)

```bash
# MUST return 0 matches
rg "from qmatsuite\.core" src/qmatsuite/frontends/
rg "from qmatsuite\.calculation" src/qmatsuite/frontends/
rg "from qmatsuite\.drivers" src/qmatsuite/frontends/
rg "from qmatsuite\.analysis" src/qmatsuite/frontends/
rg "from qmatsuite\.io" src/qmatsuite/frontends/

# MUST return 0 matches
rg "from qmatsuite\.core" src/qmatsuite/tools/
rg "from qmatsuite\.calculation" src/qmatsuite/tools/

# MUST return 0 matches (api cannot import frontends)
rg "from qmatsuite\.frontends" src/qmatsuite/api/
```

### 8.2 CLI Thin Check

```bash
# MUST return 0 matches (CLI does not resolve selectors)
rg "resolve_calculation|resolve_step|resolve_structure" src/qmatsuite/frontends/cli/

# MUST return 0 matches (CLI does not use core exceptions directly)
rg "except.*Error.*from qmatsuite\.core" src/qmatsuite/frontends/cli/
```

### 8.3 Functional Tests

1. ✅ All existing tests pass
2. ✅ Jupyter can `import qmatsuite; svc = QMSService(...)` without daemon
3. ✅ CLI commands work via api layer
4. ✅ Daemon serves GUI via api layer
5. ✅ `scripts/` contains maintenance utilities (renamed from `tools/`)

### 8.4 Error Model

1. ✅ All errors surfaced to frontends are `ErrorSpec` instances
2. ✅ No frontend code parses exception message strings

---

## 9. Explicit Out of Scope

The following are NOT part of this refactor:

1. **SSOT Philosophy** - YAML-as-truth model unchanged
2. **History System** - Existing provenance tracking unchanged
3. **Engine Internals** - Driver implementations unchanged
4. **MCP Server Implementation** - Reserved boundaries only
5. **GUI React/Electron Code** - Unchanged (calls daemon correctly)
6. **Database** - Not introduced

---

## Appendix A: Compatibility Shims

During migration, provide temporary re-exports:

```python
# src/qmatsuite/cli/__init__.py (TEMPORARY - remove after deprecation)
"""DEPRECATED: Use qmatsuite.frontends.cli instead."""
import warnings
warnings.warn(
    "qmatsuite.cli is deprecated. Use qmatsuite.frontends.cli.",
    DeprecationWarning, stacklevel=2
)
from qmatsuite.frontends.cli import app

# src/qmatsuite/daemon/__init__.py (TEMPORARY - remove after deprecation)
"""DEPRECATED: Use qmatsuite.frontends.daemon instead."""
import warnings
warnings.warn(
    "qmatsuite.daemon is deprecated. Use qmatsuite.frontends.daemon.",
    DeprecationWarning, stacklevel=2
)
from qmatsuite.frontends.daemon import QMSDaemon
```

---

## Appendix B: Import Path Changes

| Old Path | New Path |
|----------|----------|
| `qmatsuite.cli` | `qmatsuite.frontends.cli` |
| `qmatsuite.cli.main` | `qmatsuite.frontends.cli.app` |
| `qmatsuite.daemon` | `qmatsuite.frontends.daemon` |
| `qmatsuite.api` (file) | `qmatsuite.api` (package) |
| `tools/*` (repo level) | `scripts/*` (repo level) |
| (new) | `qmatsuite.tools` |
| (new) | `qmatsuite.frontends.notebook` |

---

## Appendix C: Entry Point Updates

```toml
# pyproject.toml
[project.scripts]
qms = "qmatsuite.frontends.cli:app"
qms-daemon = "qmatsuite.frontends.daemon:main"
```

---

*End of specification.*
