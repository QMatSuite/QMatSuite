# Repository Code Review Report: Multi-Frontend Refactor

**Version**: 1.0
**Date**: 2026-01-21
**Status**: COMPLIANCE AUDIT
**Target**: MULTI_FRONTEND_ARCHITECTURE_SPEC.md

---

## Executive Summary

This report audits the current QMatSuite repository against the target "single core, multi-frontends" architecture. The codebase is **approximately 70% aligned** with the target architecture but has significant layer violations that must be addressed.

**Key Findings**:
- ✅ Core modules correctly avoid frontend imports (good dependency direction)
- ✅ Daemon consistently uses QVService for most operations
- ❌ CLI imports directly from 15+ core modules instead of using api layer
- ❌ No structured error model (exceptions are stringly-typed)
- ❌ `tools/` directory contains maintenance scripts (naming conflict)
- ❌ No notebook frontend exists yet

**Overall Difficulty**: MEDIUM - Mostly refactoring, no fundamental architecture changes needed.

---

## 1. Current Repo Map

### 1.1 Module Summary

| Module | Files | LOC (est.) | Purpose |
|--------|-------|------------|---------|
| `src/quantumvitas/core/` | 59 | ~15,000 | Kernel: models, resolution, locking, resources |
| `src/quantumvitas/drivers/` | 53 | ~12,000 | Engine drivers (QE, VASP, LAMMPS, etc.) |
| `src/quantumvitas/calculation/` | 27 | ~8,000 | Calculation orchestration, runner |
| `src/quantumvitas/engine/` | 18 | ~4,000 | Engine interfaces |
| `src/quantumvitas/io/` | 14 | ~4,000 | Structure I/O, format conversion |
| `src/quantumvitas/analysis/` | 13 | ~3,500 | Output parsing, plotting |
| `src/quantumvitas/daemon/` | 3 | ~10,000 | JSON-RPC daemon for GUI |
| `src/quantumvitas/cli/` | 3 | ~6,500 | Typer CLI |
| `src/quantumvitas/api.py` | 1 | ~12,000 | QVService (current API layer) |
| `src/quantumvitas/data/` | 2 | ~500 | Static JSON metadata |
| Other | ~80 | ~15,000 | Presets, workflow, history, IR, project |
| **Total** | ~270 | ~90,000 | |

### 1.2 Current Dependency Graph

```
                        ┌─────────────────────┐
                        │   gui/ (Electron)   │
                        └──────────┬──────────┘
                                   │ JSON-RPC
                                   ▼
┌─────────────┐           ┌─────────────────┐
│    cli/     │           │     daemon/     │
│  main.py    │           │    server.py    │
└──────┬──────┘           └────────┬────────┘
       │                           │
       │ MIXED                     │ MOSTLY CLEAN
       │ (imports core + api)      │ (imports api)
       ▼                           ▼
┌──────────────────────────────────────────────┐
│                   api.py                      │
│                 (QVService)                   │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────┐
│  core/  calculation/  drivers/  io/  etc.   │
│              (Kernel)                        │
└──────────────────────────────────────────────┘
```

---

## 2. Current Dependency Directions

### 2.1 Core → Frontend (CORRECT: No Violations)

**Verification Command**:
```bash
rg "from quantumvitas\.(cli|daemon)" src/quantumvitas/core/
rg "from quantumvitas\.(cli|daemon)" src/quantumvitas/calculation/
rg "from quantumvitas\.(cli|daemon)" src/quantumvitas/drivers/
rg "from quantumvitas\.(cli|daemon)" src/quantumvitas/io/
```

**Result**: ✅ **ZERO MATCHES** - Core modules correctly do not import from frontends.

### 2.2 Daemon → API (MOSTLY CORRECT)

**Evidence** (`src/quantumvitas/daemon/server.py:31`):
```python
from quantumvitas.api import QVService, QVServiceError
```

**Observations**:
- Daemon imports `QVService` and calls it for most operations ✅
- Daemon also imports from `core.resolution`, `core.project_utils` directly ⚠️
- These should be routed through API layer

**Direct Core Imports in Daemon** (lines 33-52):
```python
from quantumvitas.core.exceptions import LegacyProjectError
from quantumvitas.core.resolution import (
    ResourceNotFoundError, RegistryOutOfSyncError, SelectorNotFoundError,
    build_resource_index, resolve_calculation, resolve_step, ResourceIndex,
)
from quantumvitas.core.project_utils import load_project_config
```

**Verdict**: ⚠️ PARTIAL VIOLATION - 6 direct core imports should be routed through API.

### 2.3 CLI → API (SIGNIFICANT VIOLATIONS)

**Evidence** (`src/quantumvitas/cli/main.py` lines 1-100):

```python
# Direct core imports (VIOLATIONS):
from quantumvitas.core.resources import (...)           # 8 imports
from quantumvitas.core.context import (...)             # 2 imports
from quantumvitas.core.exceptions import (...)          # 1 import
from quantumvitas.core.resolution import (...)          # 7 imports
from quantumvitas.core.selectors import (...)           # 6 imports
from quantumvitas.core.project_utils import (...)       # 19 imports
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe_installation import get_qe_home

# Other direct imports:
from quantumvitas.analysis import bands, dos, energy
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.types import StepMode, StepStatus
from quantumvitas.calculation.input_runner import (...)
```

**API Usage in CLI** (sparse):
```python
# Only 4 occurrences of QVService import:
# Line 1610, 3943, 4060, 4134
from quantumvitas.api import QVService
```

**Verdict**: ❌ MAJOR VIOLATION - CLI bypasses API layer for most operations. Imports from 15+ core modules directly.

---

## 3. Evidence-Based Findings

### 3.1 Layer Violations Summary

| Frontend | Direct Core Imports | API Imports | Violation Level |
|----------|---------------------|-------------|-----------------|
| CLI (`cli/main.py`) | 50+ symbols from 10+ modules | 4 occurrences | ❌ MAJOR |
| Daemon (`daemon/server.py`) | 10+ symbols from 4 modules | Primary pattern | ⚠️ PARTIAL |

### 3.2 Where SSOT Writes Happen

**YAML Write Centralization**:

| Write Operation | Location | Locking |
|-----------------|----------|---------|
| `save_yaml_doc()` | `core/yamldoc.py` | Acquires `calc_edit_lock` ✅ |
| `save_project_config()` | `core/project_utils.py` | No lock ⚠️ |
| `save_calculation()` | `core/models.py` | Via `save_yaml_doc` ✅ |

**Finding**: Most YAML writes are centralized through `save_yaml_doc()` which acquires `calc_edit_lock`. However, project config writes (`project.qv.yml`) do not acquire locks.

**Recommendation**: Add project-level edit lock or ensure project config writes go through a locked path.

### 3.3 Error Surfacing Analysis

**Current Exception Classes** (`core/` grep):

| Exception | Location | Structured? |
|-----------|----------|-------------|
| `YamlDocError` | `core/yamldoc.py:38` | ❌ String message |
| `CalculationLockError` | `core/locking.py:25` | ❌ String message |
| `ValidationError` | `core/param_validation.py:11` | ❌ String message |
| `LegacyProjectError` | `core/exceptions.py:11` | ⚠️ Has `project_root` attr |
| `MissingArtifactError` | `core/exceptions.py:35` | ❌ String message |
| `UnsupportedStepError` | `core/exceptions.py:45` | ❌ String message |
| `ResourceNotFoundError` | `core/resolution.py:54` | ❌ String message |
| `RegistryOutOfSyncError` | `core/resolution.py:103` | ❌ String message |
| `DriverError` | `core/driver_exceptions.py:6` | ❌ String message |

**API-Level Error** (`api.py`):
```python
class QVServiceError(Exception):
    """Base exception for QVService operations."""
    pass
```

**Finding**: ❌ **No structured error model**. All exceptions use string messages. Frontends must parse strings to understand errors.

### 3.4 Naming Conflicts

**Current `tools/` Directory** (repo-level):
```
tools/
├── extract_qe_parameters_v0.py
├── extract_qe_parameters_v1.py
├── extract_qe_parameters_v2.py
├── extract_qe_parameters_v3.py
├── generate_demo_snapshots.py
├── generate_pyscf_demo.py
├── qv_migrate_legacy_project.py
├── verify_demos.py
└── ... (25 total scripts)
```

**Finding**: The repo-level `tools/` contains maintenance/development scripts. This conflicts with the desired `quantumvitas/tools/` module for agent-ready primitives.

**Recommendation**: Rename repo-level `tools/` to `scripts/`.

---

## 4. Risk and Difficulty Assessment

### 4.1 Complexity Buckets

| Task | Difficulty | LOC Change | Risk |
|------|------------|------------|------|
| Rename `tools/` → `scripts/` | EASY | ~50 (CI/docs) | LOW |
| Create `frontends/` directory structure | EASY | ~200 | LOW |
| Move CLI to `frontends/cli/` | MEDIUM | ~100 | MEDIUM |
| Move Daemon to `frontends/daemon/` | MEDIUM | ~100 | MEDIUM |
| Refactor CLI to use API only | HARD | ~2000 | MEDIUM |
| Add ErrorSpec structured errors | MEDIUM | ~500 | LOW |
| Create `tools/` surface | MEDIUM | ~800 | LOW |
| Create `frontends/notebook/` | EASY | ~200 | LOW |
| Update all imports repo-wide | MEDIUM | ~300 | MEDIUM |
| Compatibility shims | EASY | ~50 | LOW |

### 4.2 Top Unknowns / Hidden Coupling Hotspots

1. **CLI `main.py` Complexity**: At 189KB, this is the largest file. Refactoring to use only API layer requires understanding 4000+ lines of command handlers. Some handlers may need new API methods.

2. **Daemon Caching**: `DaemonState` maintains `ResourceIndex` cache per project. This cache logic may need API-level abstraction.

3. **Context Detection**: CLI uses `find_path_context_from_pwd()` and other context helpers. These should remain in CLI (thin layer) but some logic may need API support.

4. **Parameter Override Parsing**: CLI has custom parameter override parsing (`--SYSTEM.ecutwfc=50`). This parsing logic is CLI-specific but validation should use API.

5. **Test Imports**: Tests import from many modules. Will need import path updates but should not change test logic.

### 4.3 Migration Hazards

| Hazard | Mitigation |
|--------|------------|
| Breaking `qv` CLI entrypoint | Add re-export shim at old location |
| Breaking daemon startup for GUI | Add re-export shim at old location |
| CI workflow references `tools/` | Update to `scripts/` in one commit |
| Third-party imports from `quantumvitas.cli` | Deprecation warning + shim |

---

## 5. Recommendations: Staged Refactor

### Phase 1: Non-Breaking Preparation (EASY)

1. **Rename `tools/` → `scripts/`**
   - Update CI references
   - Update documentation
   - Single commit, low risk

2. **Create directory structure skeleton**
   ```
   src/quantumvitas/
   ├── api/           # Create, move api.py → api/service.py
   ├── tools/         # Create empty, add __init__.py
   └── frontends/     # Create with cli/, daemon/, notebook/, agent/
   ```

3. **Add ErrorSpec infrastructure**
   - Create `api/errors.py` with `ErrorSpec` class
   - Update `QVServiceError` to carry `ErrorSpec`
   - Do not yet wrap all exceptions (gradual rollout)

### Phase 2: API Layer Consolidation (MEDIUM)

4. **Move api.py to api/ package**
   - `api.py` → `api/service.py`
   - Re-export from `api/__init__.py`
   - Add compatibility shim at old location

5. **Create missing API methods for CLI**
   - Audit CLI handlers that bypass API
   - Add corresponding methods to `QVService`
   - Example: `list_qe_parameter_metadata()` → `QVService.list_param_metadata()`

6. **Wrap core exceptions in ErrorSpec**
   - `QVService` catches core exceptions
   - Wraps in `ErrorSpec` with code, category, evidence
   - Returns `QVServiceError(error_spec)`

### Phase 3: Frontend Relocation (MEDIUM)

7. **Move Daemon to frontends/daemon/**
   - `daemon/server.py` → `frontends/daemon/server.py`
   - `daemon/jobs.py` → `frontends/daemon/jobs.py`
   - Add re-export shim at old location
   - Update Electron spawn path (or use shim)

8. **Move CLI to frontends/cli/**
   - `cli/main.py` → `frontends/cli/app.py`
   - Add re-export shim at old location
   - Update `pyproject.toml` entrypoint

### Phase 4: CLI Refactor (HARD, Incremental)

9. **Refactor CLI to use API layer**
   - Command by command, replace direct core imports
   - Move parameter adaptation logic to command handlers
   - Business logic moves to `QVService` methods
   - This is the most effort-intensive phase

10. **Remove direct core imports from CLI**
    - Target: zero `from quantumvitas.core` in `frontends/cli/`
    - Verify with `rg "from quantumvitas.core" src/quantumvitas/frontends/cli/`

### Phase 5: Tool Surface and Notebook (MEDIUM)

11. **Implement tools/ surface**
    - Create `tools/schema.py`, `tools/calc.py`, `tools/params.py`, `tools/run.py`, `tools/results.py`
    - Each function calls `QVService` internally
    - Add structured input validation
    - Return structured dicts (not dataclasses)

12. **Create notebook frontend**
    - `frontends/notebook/__init__.py` with convenience exports
    - `frontends/notebook/display.py` with IPython display helpers
    - Test in Jupyter environment

### Phase 6: Cleanup (EASY)

13. **Remove compatibility shims** (after deprecation period)
    - Remove re-exports at old locations
    - Update any remaining external references

14. **Final verification**
    - Run import audit commands
    - Ensure all tests pass
    - Verify Jupyter usage works

---

## 6. Validation Commands

### 6.1 Layer Violation Detection

```bash
# Frontends should not import from core (after refactor)
rg "from quantumvitas\.core" src/quantumvitas/frontends/
# Expected: 0 matches

# Frontends should not import from calculation (after refactor)
rg "from quantumvitas\.calculation" src/quantumvitas/frontends/
# Expected: 0 matches

# Frontends should not import from drivers (after refactor)
rg "from quantumvitas\.drivers" src/quantumvitas/frontends/
# Expected: 0 matches
```

### 6.2 API Usage Verification

```bash
# Frontends should import from api or tools
rg "from quantumvitas\.(api|tools)" src/quantumvitas/frontends/
# Expected: Many matches

# API should not import from frontends
rg "from quantumvitas\.frontends" src/quantumvitas/api/
# Expected: 0 matches
```

### 6.3 Tools Surface Verification

```bash
# Tools should only import from api
rg "from quantumvitas\." src/quantumvitas/tools/ | grep -v "from quantumvitas.api"
# Expected: 0 matches (tools only use api)
```

### 6.4 Naming Conflict Check

```bash
# Old tools/ should be renamed
ls tools/
# Expected: Directory not found (renamed to scripts/)

ls scripts/
# Expected: Maintenance scripts present
```

---

## 7. Current State vs Target State

| Aspect | Current | Target | Gap |
|--------|---------|--------|-----|
| CLI imports from core | Yes (50+ symbols) | No | LARGE |
| Daemon imports from core | Yes (10+ symbols) | No | SMALL |
| ErrorSpec structured errors | No | Yes | MEDIUM |
| `tools/` agent surface | No | Yes | NEW |
| `frontends/` organization | No | Yes | RESTRUCTURE |
| Notebook support | No | Yes | NEW |
| `scripts/` for dev tools | `tools/` | `scripts/` | RENAME |
| API layer exists | Yes (`api.py`) | Yes (`api/`) | MINIMAL |

---

## Appendix A: Files to Move

| Current Location | New Location |
|------------------|--------------|
| `src/quantumvitas/api.py` | `src/quantumvitas/api/service.py` |
| `src/quantumvitas/cli/main.py` | `src/quantumvitas/frontends/cli/app.py` |
| `src/quantumvitas/cli/__init__.py` | `src/quantumvitas/frontends/cli/__init__.py` |
| `src/quantumvitas/cli/__main__.py` | `src/quantumvitas/frontends/cli/__main__.py` |
| `src/quantumvitas/daemon/server.py` | `src/quantumvitas/frontends/daemon/server.py` |
| `src/quantumvitas/daemon/jobs.py` | `src/quantumvitas/frontends/daemon/jobs.py` |
| `src/quantumvitas/daemon/__init__.py` | `src/quantumvitas/frontends/daemon/__init__.py` |
| `tools/*` (repo level) | `scripts/*` (repo level) |

---

## Appendix B: New Files to Create

| File | Purpose |
|------|---------|
| `src/quantumvitas/api/__init__.py` | API package exports |
| `src/quantumvitas/api/errors.py` | ErrorSpec definition |
| `src/quantumvitas/api/types.py` | Public return types |
| `src/quantumvitas/tools/__init__.py` | Tools surface exports |
| `src/quantumvitas/tools/schema.py` | `discover()` |
| `src/quantumvitas/tools/calc.py` | `get_summary()`, `get_digest()` |
| `src/quantumvitas/tools/params.py` | `validate_patch()`, `apply_patch()` |
| `src/quantumvitas/tools/run.py` | `run_step()`, `run_calc()` |
| `src/quantumvitas/tools/results.py` | `extract()` |
| `src/quantumvitas/frontends/__init__.py` | Frontends package |
| `src/quantumvitas/frontends/cli/__init__.py` | CLI frontend |
| `src/quantumvitas/frontends/daemon/__init__.py` | Daemon frontend |
| `src/quantumvitas/frontends/notebook/__init__.py` | Notebook frontend |
| `src/quantumvitas/frontends/notebook/display.py` | Notebook display helpers |
| `src/quantumvitas/frontends/agent/__init__.py` | Reserved for MCP |

---

## Appendix C: Compatibility Shims

```python
# src/quantumvitas/cli/__init__.py (TEMPORARY SHIM)
"""Backward compatibility shim. Use quantumvitas.frontends.cli instead."""
import warnings
warnings.warn(
    "quantumvitas.cli is deprecated. Use quantumvitas.frontends.cli instead.",
    DeprecationWarning,
    stacklevel=2,
)
from quantumvitas.frontends.cli import app

# src/quantumvitas/daemon/__init__.py (TEMPORARY SHIM)
"""Backward compatibility shim. Use quantumvitas.frontends.daemon instead."""
import warnings
warnings.warn(
    "quantumvitas.daemon is deprecated. Use quantumvitas.frontends.daemon instead.",
    DeprecationWarning,
    stacklevel=2,
)
from quantumvitas.frontends.daemon import QVDaemon
```

---

*End of report.*
