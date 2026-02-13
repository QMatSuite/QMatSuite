# Multi-Frontend Refactor Milestone

**Status**: COMPLETE  
**Date**: 2026-01-21  
**Reference**: `docs/plan/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md`

---

## Contract

**Frontends import only `quantumvitas.api`** (QVService wrappers + re-exports). No direct kernel imports.

**Kernel modules** (forbidden in frontends):
- `quantumvitas.core`
- `quantumvitas.calculation`
- `quantumvitas.drivers`
- `quantumvitas.analysis`
- `quantumvitas.io`
- `quantumvitas.engine`
- `quantumvitas.workflow`
- `quantumvitas.presets`

**Frontends** (must use API only):
- `src/quantumvitas/cli/*`
- `src/quantumvitas/daemon/*`
- `src/quantumvitas/frontends/*/*`

**API facade pattern**:
- Functions → `QVService.<wrapper>()` static methods (pass-through, no behavior change)
- Types/Enums/Exceptions → re-exported from `quantumvitas.api` (same object identity)
- Wrappers convert generic exceptions to `QVServiceError` when appropriate

---

## Gates Policy

**Default behavior**: Architecture gate tests are **enforced by default** (blocking mode). Violations cause test failures.

**Opt-out for local development**: Set `QMATSUITE_RELAX_ARCH_GATES=1` to enable report-only mode (non-blocking). This allows local development while still seeing violation reports.

**Importability smoke tests**: Always enforced (never optional). These catch "gates green but code broken" scenarios.

**Usage**:
```bash
# Default: enforced (blocking)
python -m pytest tests/gates/test_import_rules.py -v -rs

# Relax mode: report-only (non-blocking)
QMATSUITE_RELAX_ARCH_GATES=1 python -m pytest tests/gates/test_import_rules.py -v -rs
```

---

## Testing Philosophy for API Facade

**Wrapper validation**: Wrappers are validated via monkeypatching underlying functions. Tests avoid heavy real filesystem/engine execution.

**Test pattern**:
```python
def test_wrapper(monkeypatch):
    # Mock underlying function
    called = {}
    def fake_underlying(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        return "fake_result"
    
    monkeypatch.setattr(module, "underlying_function", fake_underlying)
    
    # Call wrapper
    result = QVService.wrapper_method(...)
    
    # Verify pass-through
    assert result == "fake_result"
    assert called["args"] == (...)
```

**Re-export validation**: Verify identity (same object):
```python
from quantumvitas.api import SomeType
from quantumvitas.original.module import SomeType as OriginalType
assert SomeType is OriginalType
```

---

## How to Verify

### 1. Gates Test (Default Enforced)
```bash
python -m pytest tests/gates/test_import_rules.py -v -rs
```
**Expected**: All tests pass (10 passed, 2 skipped)

### 2. Full Test Suite (Parallel)
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
**Expected**: All tests pass (2458+ passed, 2 skipped)

### 3. Audit Scripts (Deterministic Outputs)
```bash
# CLI audit
python scripts/audit_cli_kernel_imports.py
# Output: ./.audit/cli_kernel_deps.json

# Daemon audit
python scripts/audit_daemon_kernel_imports.py
# Output: ./.audit/daemon_kernel_deps.json

# Verify outputs exist
ls -la .audit/
```

**Expected**: Both JSON files exist with `total_violations: 0`

### 4. Manual Verification
```bash
# Check for forbidden imports
rg -n "^from quantumvitas\.(core|calculation|drivers|analysis|io|engine|workflow|presets)\b" src/quantumvitas/cli
rg -n "^from quantumvitas\.(core|calculation|drivers|analysis|io|engine|workflow|presets)\b" src/quantumvitas/daemon

# Expected: 0 matches
```

### 5. Importability Checks
```bash
python -c "from quantumvitas.cli.main import app; print('CLI OK')"
python -c "from quantumvitas.daemon.server import QVDaemon; print('Daemon OK')"
python -c "from quantumvitas.api import QVService; print('API OK')"
```

---

## Milestone Commits

### Batch 0: Gates + Smoke Baseline
- Gate tests fixed (no false-positives on method calls)
- Importability smoke tests added
- Safety documentation added

### Batch 1: API Facade Instance Methods
- QVService instance methods added
- Re-exports for types/exceptions added
- Unit tests for API facade

### Batch 2: Daemon Migration (0 Violations)
- All daemon presets imports migrated to API
- All daemon workflow imports migrated to API
- Commit: `52a0122` - refactor(daemon): migrate workflow.templates imports to API facade

### Batch 3: CLI Prep + Map
- CLI migration markers added
- CLI compile gate added

### CLI Migration Completion (0 Violations)
- All CLI kernel imports migrated to API
- Multiple commits (A2-A15, B1-B2, C1):
  - `efbb129` - C1: eliminate remaining CLI violations via quantumvitas.api/QVService
  - `a895cd4` - B2: remove remaining CLI quantumvitas.analysis.* deps via QVService/api
  - `5bb76b4` - B1: remove remaining CLI quantumvitas.calculation.* deps via QVService/api
  - Plus A2-A15 series for incremental migration

### D1: Default Enforcement Change
- Commit: `03da778` - D1: enforce architecture gates by default (relax via env var)
- Gates now enforced by default (no opt-in required)
- Opt-out via `QMATSUITE_RELAX_ARCH_GATES=1`

### D2: Presets Migration Completion
- All daemon presets imports removed
- API wrappers added for presets functions
- Unit tests added

### D3: Workflow Templates Migration Completion
- Commit: `52a0122` - refactor(daemon): migrate workflow.templates imports to API facade
- All daemon workflow imports removed
- API wrapper added for `get_workflow_service()`
- Unit test added

### D4: Finalize Refactor (This Milestone)
- Milestone documentation
- Deterministic audit outputs
- Improved gate diagnostics
- Plan marked COMPLETE/Archived

---

## Final State

- **CLI**: 0 violations ✅
- **Daemon**: 0 violations ✅
- **Gates**: Enforced by default ✅
- **Full suite**: All tests pass ✅
- **Audit scripts**: Deterministic outputs ✅

---

## Next Steps (Future Work)

- Move files to `frontends/` directory structure (Batch 5)
- Remove compatibility shims (Batch 6)
- Create notebook frontend
- Create tools/ surface (Python package)

