# PR 5 Fixes Summary: Backward Compatibility Re-exports

## What I Changed

Fixed 3 backward compatibility issues that were causing test failures after PR 5 (Move QE Engine Files):

### 1. Added `home_qe_engines_dir` re-export to `core/engines/qe_resolver.py`
- **File**: `src/quantumvitas/core/engines/qe_resolver.py`
- **Change**: Added `home_qe_engines_dir` to the re-export module to support test monkeypatching
- **Reason**: Tests were trying to monkeypatch `qe_resolver.home_qe_engines_dir` but it didn't exist after migration
- **Fix**: Added compat re-export: `from quantumvitas.core.paths import home_qe_engines_dir` and included it in `__all__`

### 2. Made `drivers/qe/engine/qe_resolver.py` use re-export for monkeypatching support
- **File**: `src/quantumvitas/drivers/qe/engine/qe_resolver.py`
- **Change**: Modified `home_qe_engines_dir` usage to check re-export module first (allows test monkeypatching)
- **Reason**: The actual implementation imported directly from `core.paths`, so monkeypatching the re-export didn't work
- **Fix**: Added `_get_home_qe_engines_dir()` helper that checks re-export module first, then falls back to original

### 3. Created `core/engines/qe_diagnostics.py` re-export module
- **File**: `src/quantumvitas/core/engines/qe_diagnostics.py` (new file)
- **Change**: Created backward-compatibility re-export for `qe_diagnostics` functions
- **Reason**: Test was importing from `quantumvitas.core.engines.qe_diagnostics` but module was moved
- **Fix**: Created re-export module with all functions: `diagnose_qe_resolution`, `check_settings_for_external_engines`, `check_environment_variables`, `check_managed_engines`, `QEResolutionReport`

### 4. Created `core/engines/qe_binary_locator.py` re-export module
- **File**: `src/quantumvitas/core/engines/qe_binary_locator.py` (new file)
- **Change**: Created backward-compatibility re-export for `qe_binary_locator` functions
- **Reason**: Test was importing `locate_pw2wannier90` from `quantumvitas.core.engines.qe_binary_locator` but module was moved
- **Fix**: Created re-export module with: `locate_qe_executable`, `locate_pw2wannier90`

### 5. Fixed `EngineConfig` import in test
- **File**: `tests/unit/test_pw2wannier90_stderr_output.py`
- **Change**: Changed import from `from quantumvitas.core.engines.qe import EngineConfig` to `from quantumvitas.core.engines.base import EngineConfig`
- **Reason**: `EngineConfig` belongs to base engine module, not QE-specific
- **Fix**: Updated import to correct location

## Test Results

### Before Fixes
- 5 failed tests in `tests/core/test_qe_resolver.py`
- 2 import errors in `tests/test_qe_resolution_diagnostics.py` and `tests/unit/test_pw2wannier90_stderr_output.py`

### After Fixes
- ✅ All 11 tests in `tests/core/test_qe_resolver.py` pass
- ✅ `tests/test_qe_resolution_diagnostics.py` passes
- ✅ `tests/unit/test_pw2wannier90_stderr_output.py` passes
- ✅ Full test suite: **2367 passed, 148 warnings**

## Files Modified

1. `src/quantumvitas/core/engines/qe_resolver.py` - Added `home_qe_engines_dir` re-export
2. `src/quantumvitas/drivers/qe/engine/qe_resolver.py` - Modified to support monkeypatching via re-export
3. `src/quantumvitas/core/engines/qe_diagnostics.py` - Created (new file)
4. `src/quantumvitas/core/engines/qe_binary_locator.py` - Created (new file)
5. `tests/unit/test_pw2wannier90_stderr_output.py` - Fixed `EngineConfig` import

## Validation Commands

```bash
# Load venv and run targeted tests
source .venv/bin/activate
pytest tests/core/test_qe_resolver.py -q
pytest tests/test_qe_resolution_diagnostics.py -q
pytest tests/unit/test_pw2wannier90_stderr_output.py -q

# Full test suite (parallel)
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

All tests pass ✅

