# QE Resolution Review Summary

## Problem Statement

Local tests can find and use QE even when no managed engine is installed in `.qmatsuite/engines/qe/`. This violates the intended "default managed-only" policy.

## Root Cause

**Two parallel resolution systems exist, and tests use the wrong one:**

1. **New Registry System** (`QEEngineRegistry`) - ✅ Implemented, ❌ **NOT USED**
2. **Legacy Auto-Detection** (`QEInstallation`) - ⚠️ **ACTIVELY USED** by all tests

## How Tests Currently Find QE

### Code Path

```
Test Fixture
  → QuantumEspressoEngine(EngineConfig(name="qe"))
    → QEInstallation()  [qe.py:114]
      → get_qe_home()  [qe_installation.py:29]
        → _initialize_qe_home()  [qe_installation.py:88]
          → os.environ.get("QE_HOME")  [line 100] ← Check 1
          → QEInstallation._detect_qe_home()  [line 111]
            → shutil.which("pw.x")  [line 220] ← Check 2 (MOST LIKELY)
            → _extract_from_shell_config()  [line 228] ← Check 3
            → Home directory scan  [line 232] ← Check 4
```

### Resolution Sources (In Order)

1. **QE_HOME environment variable** (if set)
   - Code: `qe_installation.py:100`
   - Bypasses: Registry, settings.json, managed engines

2. **PATH lookup** (`shutil.which("pw.x")`)
   - Code: `qe_installation.py:220`
   - Bypasses: Registry, settings.json, managed engines
   - **Most likely source for local tests**

3. **Shell config files** (`~/.zshrc`, `~/.bashrc`, etc.)
   - Code: `qe_installation.py:368`
   - Bypasses: Registry, settings.json, managed engines

4. **Home directory scan** (`$HOME/q-e-qe*`, 3 levels deep)
   - Code: `qe_installation.py:232-365`
   - Bypasses: Registry, settings.json, managed engines

## Evidence from Code

### File: `src/quantumvitas/core/engines/qe.py:94-114`

```python
def __init__(self, config: EngineConfig):
    # ...
    if config.qe_home:
        self._installation = QEInstallation(qe_home=config.qe_home)
    elif config.executable_path:
        self._installation = QEInstallation(qe_home=config.executable_path)
    else:
        self._installation = QEInstallation()  # ← Auto-detection, bypasses registry!
```

**Problem**: When no explicit path provided, uses legacy auto-detection.

### File: `src/quantumvitas/core/engines/qe_installation.py:88-113`

```python
def _initialize_qe_home() -> None:
    # Read from environment variable (one-time read)
    qe_home_env = os.environ.get("QE_HOME")  # ← Always checks, no opt-in
    if qe_home_env:
        # ...
        return
    
    # Auto-detect using QEInstallation strategies
    detected = QEInstallation._detect_qe_home()  # ← Always runs, no opt-in
    if detected:
        _qe_home_registry = detected
```

**Problem**: Always checks `QE_HOME` and runs auto-detection, regardless of registry settings.

### File: `src/quantumvitas/core/engines/qe_installation.py:203-365`

```python
def _detect_qe_home() -> Optional[Path]:
    # Strategy 1: System PATH (using which pw.x)
    for exe_name in ("pw.x", "ph.x"):
        exe_path = shutil.which(exe_name)  # ← Always searches PATH
        # ...
    
    # Strategy 2: Shell configuration files
    shell_qe_home = QEInstallation._extract_from_shell_config()  # ← Always parses
    # ...
    
    # Strategy 3: Search in home directory
    # ... scans $HOME for q-e-qe* folders  # ← Always scans
```

**Problem**: Full disk search happens automatically, no opt-in required.

## Test Entry Points (All Bypass Registry)

### 1. Test Fixtures

**Files**:
- `tests/cli/test_cli_show_command_integration.py:22-23`
- `tests/integration/test_pw_step_specs.py:22-23`
- `tests/integration/test_pw_scf_ibrav_step_specs.py:22-23`

**Code**:
```python
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)  # ← Bypasses registry
```

### 2. CLI Commands

**File**: `src/quantumvitas/cli/main.py:1627`
```python
engine_config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(engine_config)  # ← Bypasses registry
```

### 3. API/Service Layer

**File**: `src/quantumvitas/api.py:1270`
```python
engine_config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(engine_config)  # ← Bypasses registry
```

## Registry System (Not Used)

The `QEEngineRegistry` class exists and implements the correct priority order:

1. Project override
2. `settings.qe.discovered_engine_id`
3. `settings.defaults.qe_engine_id`
4. Latest managed engine
5. PATH fallback (only if `allow_path_fallback=true`)
6. Error

**But it's never called** because `QuantumEspressoEngine` uses `QEInstallation()` directly.

## Diagnostic Tools Added

### 1. Diagnostic Module

**File**: `src/quantumvitas/core/engines/qe_diagnostics.py`

**Functions**:
- `diagnose_qe_resolution()`: Returns `QEResolutionReport` showing how QE would be resolved
- `check_settings_for_external_engines()`: Checks settings.json for external engines
- `check_environment_variables()`: Checks env vars that affect resolution
- `check_managed_engines()`: Lists managed engines in `.qmatsuite/engines/qe/`

### 2. Diagnostic Test

**File**: `tests/test_qe_resolution_diagnostics.py`

**Purpose**: 
- Prints full resolution report
- Asserts that tests don't use legacy paths (unless explicitly allowed)
- Helps identify resolution source

### 3. Test Fixture Warning

**File**: `tests/conftest.py:236-262`

**Purpose**: Warns when tests use legacy detection paths (informational, doesn't fail tests)

## Minimal Fixes Required

### Fix 1: Wire Registry into QuantumEspressoEngine (CRITICAL)

**File**: `src/quantumvitas/core/engines/qe.py:94-114`

**Change**: Use registry when no explicit path provided, fallback to legacy only if `allow_path_fallback=true`.

**Impact**: All code paths (tests, CLI, API) will use registry by default.

### Fix 2: Add Diagnostic Assertions (RECOMMENDED)

**Status**: ✅ Already added to `tests/conftest.py` and `tests/test_qe_resolution_diagnostics.py`

**Impact**: Tests will warn/assert when using legacy paths.

### Fix 3: Ensure allow_path_fallback Defaults to False (VERIFIED)

**Status**: ✅ Already defaults to `False` in `settings.py:370`

## Expected Behavior After Fix

1. **With managed engine**: Uses managed engine from `.qmatsuite/engines/qe/`
2. **With external engine registered**: Uses external engine from `settings.json`
3. **With allow_path_fallback=true**: Uses PATH fallback (explicit opt-in)
4. **Otherwise**: Fails with clear error message

## Current Behavior (Before Fix)

1. **Always**: Uses PATH/environment/shell configs/home scan (legacy auto-detection)
2. **Never**: Uses registry, settings.json, or checks for managed engines

## Files Changed (Diagnostics Only)

1. ✅ `src/quantumvitas/core/engines/qe_diagnostics.py` - Diagnostic module
2. ✅ `tests/test_qe_resolution_diagnostics.py` - Diagnostic test
3. ✅ `tests/conftest.py` - Added warning in fixture
4. ✅ `docs/QE_RESOLUTION_ANALYSIS.md` - Full analysis document
5. ✅ `docs/QE_RESOLUTION_REVIEW_SUMMARY.md` - This summary

## Next Steps

1. **Run diagnostic test**:
   ```bash
   pytest tests/test_qe_resolution_diagnostics.py -v -s
   ```

2. **Review output** to see exactly how QE is being resolved

3. **Implement Fix 1** (wire registry into `QuantumEspressoEngine.__init__()`)

4. **Verify** tests fail with clear error when no managed engine and `allow_path_fallback=false`

5. **Update test setup** to either:
   - Install managed engine before tests
   - Or explicitly enable `allow_path_fallback` in test setup (with documentation)

