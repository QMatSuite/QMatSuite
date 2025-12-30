# QE Engine Resolution Analysis

## Executive Summary

Local tests can find and use QE even without a managed engine in `.qmatsuite/engines/qe/` because **tests bypass the new registry system** and use legacy auto-detection that searches PATH, environment variables, and home directories.

## Problem: Two Parallel Resolution Systems

### 1. New Registry System (Not Used by Tests)

**Location**: `src/quantumvitas/core/engines/qe_registry.py`

**Priority Order** (as designed):
1. Project override (`project_engine_id`)
2. `settings.qe.discovered_engine_id`
3. `settings.defaults.qe_engine_id`
4. Latest managed engine (`.qmatsuite/engines/qe/`)
5. PATH fallback (only if `allow_path_fallback=true`)
6. Error

**Status**: ✅ Implemented but **NOT USED** by tests

### 2. Legacy Auto-Detection (Currently Used by Tests)

**Location**: `src/quantumvitas/core/engines/qe_installation.py`

**How Tests Use It**:
```python
# tests/cli/test_cli_show_command_integration.py:22-23
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)  # ← Bypasses registry!
```

**What Happens**:
- `QuantumEspressoEngine.__init__()` calls `QEInstallation()` (line 114 in `qe.py`)
- `QEInstallation()` with no args triggers `_initialize_qe_home()` (line 88-113 in `qe_installation.py`)
- `_initialize_qe_home()` does:
  1. Check `QE_HOME` environment variable
  2. Call `QEInstallation._detect_qe_home()` which:
     - Searches PATH (`shutil.which("pw.x")`)
     - Parses shell config files (`~/.zshrc`, `~/.bashrc`, etc.)
     - Scans `$HOME` directory (3 levels deep) for `q-e-qe*` folders

**Status**: ⚠️ **ACTIVELY USED** by all tests, bypasses registry completely

## All Resolution Sources (Complete List)

### Registry-Based Sources (Intended, but bypassed)

1. **Project Override**
   - Source: Project metadata/config file
   - Code: `QEEngineRegistry.resolve_engine(project_engine_id=...)`
   - Used by: API/Service layer (if implemented)
   - **Not used by tests**

2. **settings.json: qe.discovered_engine_id**
   - Source: `.qmatsuite/config/settings.json`
   - Code: `QEEngineRegistry.resolve_engine()` priority 2
   - **Not used by tests**

3. **settings.json: defaults.qe_engine_id**
   - Source: `.qmatsuite/config/settings.json`
   - Code: `QEEngineRegistry.resolve_engine()` priority 3
   - **Not used by tests**

4. **Managed Engines**
   - Source: `.qmatsuite/engines/qe/<engine_id>/bin/pw.x`
   - Code: `QEEngineRegistry.list_managed_engines()`
   - **Not used by tests**

5. **PATH Fallback (Registry)**
   - Source: System PATH (`shutil.which("pw.x")`)
   - Code: `QEEngineRegistry._find_engine_in_path()`
   - Condition: `settings.qe.allow_path_fallback == true`
   - **Not used by tests**

### Legacy Auto-Detection Sources (Actually Used by Tests)

6. **QE_HOME Environment Variable**
   - Source: `os.environ.get("QE_HOME")`
   - Code: `qe_installation.py:_initialize_qe_home()` line 100
   - **Used by tests** (if set)

7. **PATH Detection (Legacy)**
   - Source: `shutil.which("pw.x")` or `shutil.which("ph.x")`
   - Code: `qe_installation.py:_detect_qe_home()` line 220-225
   - **Used by tests** (always, no opt-in required)

8. **Shell Config Files**
   - Source: `~/.zshrc`, `~/.zprofile`, `~/.zshenv`, `~/.bashrc`, `~/.bash_profile`, `~/.profile`
   - Code: `qe_installation.py:_extract_from_shell_config()` line 368
   - **Used by tests** (always, no opt-in required)

9. **Home Directory Scan**
   - Source: `$HOME` directory, 3 levels deep, searching for `q-e-qe*` or `quantum-espresso*`
   - Code: `qe_installation.py:_detect_qe_home()` line 232-365
   - **Used by tests** (always, no opt-in required)

## Code Paths Used by Tests

### Test Entry Points

1. **Direct Engine Creation** (Most Common)
   ```python
   # tests/cli/test_cli_show_command_integration.py:22-23
   # tests/integration/test_pw_step_specs.py:22-23
   # tests/integration/test_pw_scf_ibrav_step_specs.py:22-23
   config = EngineConfig(name="qe")
   engine = QuantumEspressoEngine(config)
   ```
   - **Bypasses**: Registry completely
   - **Uses**: Legacy `QEInstallation()` auto-detection
   - **Files**: `src/quantumvitas/core/engines/qe.py:114`

2. **CLI Commands** (If tests use CLI)
   - **Location**: `src/quantumvitas/cli/main.py`
   - **Status**: Need to check if CLI uses registry or legacy

3. **API/Service Layer** (If tests use daemon)
   - **Location**: `src/quantumvitas/api.py`
   - **Status**: Need to check if API uses registry or legacy

### Legacy Detection Flow

```
QuantumEspressoEngine(config)
  → QEInstallation()  [qe.py:114]
    → get_qe_home()  [qe_installation.py:29]
      → _initialize_qe_home()  [qe_installation.py:88]
        → os.environ.get("QE_HOME")  [line 100]
        → QEInstallation._detect_qe_home()  [line 111]
          → shutil.which("pw.x")  [line 220]
          → _extract_from_shell_config()  [line 228]
          → Home directory scan  [line 232]
```

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
        self._installation = QEInstallation()  # ← Auto-detection!
```

**Problem**: When `config` has no `qe_home` or `executable_path`, it calls `QEInstallation()` which triggers full auto-detection.

### File: `src/quantumvitas/core/engines/qe_installation.py:88-113`

```python
def _initialize_qe_home() -> None:
    # Read from environment variable (one-time read)
    qe_home_env = os.environ.get("QE_HOME")  # ← Bypass 1
    if qe_home_env:
        # ...
        return
    
    # Auto-detect using QEInstallation strategies
    detected = QEInstallation._detect_qe_home()  # ← Bypass 2
    if detected:
        _qe_home_registry = detected
```

**Problem**: Always checks `QE_HOME` env var and runs auto-detection, regardless of registry settings.

### File: `src/quantumvitas/core/engines/qe_installation.py:203-365`

```python
def _detect_qe_home() -> Optional[Path]:
    # Strategy 1: System PATH (using which pw.x)
    for exe_name in ("pw.x", "ph.x"):
        exe_path = shutil.which(exe_name)  # ← Always searches PATH
        # ...
    
    # Strategy 2: Shell configuration files
    shell_qe_home = QEInstallation._extract_from_shell_config()  # ← Always parses shell configs
    # ...
    
    # Strategy 3: Search in home directory
    # ... scans $HOME for q-e-qe* folders  # ← Always scans home
```

**Problem**: Full disk search happens automatically, no opt-in required.

## Code Paths: Where QE Engines Are Created

### 1. Test Fixtures (Bypass Registry)

**Files**:
- `tests/cli/test_cli_show_command_integration.py:22-23`
- `tests/integration/test_pw_step_specs.py:22-23`
- `tests/integration/test_pw_scf_ibrav_step_specs.py:22-23`

**Code**:
```python
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)  # ← Bypasses registry
```

**Resolution**: Legacy auto-detection (PATH, shell configs, home scan)

### 2. CLI Commands (Bypass Registry)

**File**: `src/quantumvitas/cli/main.py`

**Locations**:
- Line 1627: `_run_standalone_step()` creates `QuantumEspressoEngine(engine_config)`
- Line 1682: `run_structure_command()` uses `create_default_registry()` which wraps `QuantumEspressoEngine`

**Resolution**: Legacy auto-detection

### 3. API/Service Layer (Bypass Registry)

**File**: `src/quantumvitas/api.py`

**Location**: Line 1270 in `run_step()` method
```python
engine_config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(engine_config)  # ← Bypasses registry
```

**Resolution**: Legacy auto-detection

### 4. Engine Registry Wrapper (Also Bypasses Registry)

**File**: `src/quantumvitas/engine/registry.py:27-33`

**Code**:
```python
def create_default_registry(config: Optional[EngineConfig] = None) -> EngineRegistry:
    registry = EngineRegistry()
    registry.register(QeEngine(config))  # ← QeEngine wraps QuantumEspressoEngine
    return registry
```

**Resolution**: `QeEngine` wraps `QuantumEspressoEngine`, which still uses legacy auto-detection

## Minimal Fixes Required

### Fix 1: Make QuantumEspressoEngine Use Registry (High Priority)

**File**: `src/quantumvitas/core/engines/qe.py`

**Change**: Modify `__init__` to use registry when no explicit path provided:

```python
def __init__(self, config: EngineConfig):
    super().__init__(config)
    
    # If explicit path provided, use it (backward compatibility)
    if config.qe_home:
        self._installation = QEInstallation(qe_home=config.qe_home)
    elif config.executable_path:
        self._installation = QEInstallation(qe_home=config.executable_path)
    else:
        # Use registry for resolution
        from quantumvitas.core.engines.qe_registry import resolve_qe_engine
        try:
            engine_info = resolve_qe_engine()
            self._installation = QEInstallation(qe_home=engine_info.engine_path)
        except RuntimeError:
            # Fallback to legacy only if registry fails AND allow_path_fallback
            from quantumvitas.core.settings import load_settings
            settings = load_settings()
            if settings.qe.allow_path_fallback:
                self._installation = QEInstallation()  # Legacy auto-detect
            else:
                raise RuntimeError(
                    "No QE engine found via registry. "
                    "Install a managed engine or register an external engine."
                )
```

### Fix 2: Add Assertion in Test Fixtures (Medium Priority)

**File**: `tests/conftest.py` or test fixtures

**Change**: Add diagnostic check in test fixtures:

```python
@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    from quantumvitas.core.engines.qe_diagnostics import diagnose_qe_resolution
    report = diagnose_qe_resolution()
    
    if report.resolution_reason.startswith("legacy_"):
        pytest.fail(
            f"Test using legacy QE detection: {report.resolution_reason}\n"
            f"Tests should use managed engines or explicitly register external engines.\n"
            f"Full report: {report.to_dict()}"
        )
    
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    # ...
```

### Fix 3: Default allow_path_fallback to False (Low Priority)

**File**: `src/quantumvitas/core/settings.py`

**Change**: Already defaults to `False` ✅ (line 370 in settings.py)

## Recommended Test Changes

1. **Run diagnostic test first**:
   ```bash
   pytest tests/test_qe_resolution_diagnostics.py -v -s
   ```

2. **Check current resolution**:
   - The diagnostic will show exactly how QE is being found
   - Likely: `legacy_PATH_detection` or `legacy_QE_HOME_env`

3. **Fix test fixtures** to either:
   - Install managed engine before tests
   - Explicitly register external engine in test setup
   - Or explicitly enable `allow_path_fallback` in test setup (with warning)

## Summary

**Root Cause**: Tests create `QuantumEspressoEngine` directly, which uses legacy `QEInstallation()` auto-detection that bypasses the registry system entirely.

**Resolution Sources Actually Used**:
1. `QE_HOME` environment variable (if set)
2. PATH (`shutil.which("pw.x")`)
3. Shell config files (`~/.zshrc`, etc.)
4. Home directory scan (`$HOME/q-e-qe*`)

**Resolution Sources NOT Used**:
- Registry system (`QEEngineRegistry`)
- `settings.json` configuration
- Managed engines (`.qmatsuite/engines/qe/`)

**Minimal Fix**: Modify `QuantumEspressoEngine.__init__()` to use registry first, fallback to legacy only if `allow_path_fallback=true`.

## Complete Resolution Source Inventory

### Registry System (Intended, Not Used)

| Source | Location | Code Path | Used by Tests? |
|--------|----------|-----------|----------------|
| Project override | Project metadata | `QEEngineRegistry.resolve_engine(project_engine_id=...)` | ❌ No |
| settings.qe.discovered_engine_id | `.qmatsuite/config/settings.json` | `QEEngineRegistry.resolve_engine()` priority 2 | ❌ No |
| settings.defaults.qe_engine_id | `.qmatsuite/config/settings.json` | `QEEngineRegistry.resolve_engine()` priority 3 | ❌ No |
| Managed engines | `.qmatsuite/engines/qe/<engine_id>/` | `QEEngineRegistry.list_managed_engines()` | ❌ No |
| PATH fallback (registry) | System PATH | `QEEngineRegistry._find_engine_in_path()` | ❌ No |

### Legacy Auto-Detection (Actually Used)

| Source | Location | Code Path | Used by Tests? |
|--------|----------|-----------|----------------|
| QE_HOME env var | `os.environ.get("QE_HOME")` | `qe_installation.py:_initialize_qe_home()` line 100 | ✅ Yes |
| PATH detection | `shutil.which("pw.x")` | `qe_installation.py:_detect_qe_home()` line 220 | ✅ Yes |
| Shell config files | `~/.zshrc`, `~/.bashrc`, etc. | `qe_installation.py:_extract_from_shell_config()` line 368 | ✅ Yes |
| Home directory scan | `$HOME/q-e-qe*` (3 levels) | `qe_installation.py:_detect_qe_home()` line 232 | ✅ Yes |

## How Local Tests Currently Find QE

**Most Likely Path**: `legacy_PATH_detection`

1. Test creates `QuantumEspressoEngine(EngineConfig(name="qe"))`
2. `QuantumEspressoEngine.__init__()` calls `QEInstallation()` (no args)
3. `QEInstallation()` calls `get_qe_home()` which triggers `_initialize_qe_home()`
4. `_initialize_qe_home()` checks:
   - `QE_HOME` env var (if set, uses it)
   - Otherwise calls `_detect_qe_home()`
5. `_detect_qe_home()` searches:
   - PATH via `shutil.which("pw.x")` ← **Most likely finds QE here**
   - Shell config files
   - Home directory scan

**Result**: QE found via PATH, completely bypassing registry and managed engine requirement.

## Recommended Minimal Fixes

### Priority 1: Wire Registry into QuantumEspressoEngine

**File**: `src/quantumvitas/core/engines/qe.py:94-114`

**Change**: Use registry when no explicit path provided:

```python
def __init__(self, config: EngineConfig):
    super().__init__(config)
    
    # If explicit path provided, use it (backward compatibility)
    if config.qe_home:
        self._installation = QEInstallation(qe_home=config.qe_home)
    elif config.executable_path:
        self._installation = QEInstallation(qe_home=config.executable_path)
    else:
        # Use registry for resolution
        from quantumvitas.core.engines.qe_registry import resolve_qe_engine
        from quantumvitas.core.settings import load_settings
        
        try:
            engine_info = resolve_qe_engine()
            self._installation = QEInstallation(qe_home=engine_info.engine_path)
        except RuntimeError:
            # Fallback to legacy only if registry fails AND allow_path_fallback
            settings = load_settings()
            if settings.qe.allow_path_fallback:
                self._installation = QEInstallation()  # Legacy auto-detect
            else:
                raise RuntimeError(
                    "No QE engine found via registry. "
                    "Install a managed engine or register an external engine. "
                    "To use PATH fallback, set allow_path_fallback=true in settings.json"
                )
```

**Impact**: All tests, CLI, and API will use registry by default.

### Priority 2: Add Diagnostic Assertions in Tests

**File**: `tests/conftest.py` or individual test fixtures

**Change**: Add check in `reset_qe_registry` fixture:

```python
@pytest.fixture(autouse=True)
def reset_qe_registry():
    """Reset QE home registry before and after each test."""
    from quantumvitas.core.engines import reset_qe_home
    from quantumvitas.core.engines.qe_diagnostics import diagnose_qe_resolution
    
    reset_qe_home()
    
    # Diagnostic: check resolution path (only warn, don't fail)
    report = diagnose_qe_resolution(check_legacy=True)
    if report.resolution_reason.startswith("legacy_"):
        import warnings
        warnings.warn(
            f"Test using legacy QE detection: {report.resolution_reason}\n"
            f"Tests should use managed engines. Full report: {report.to_dict()}",
            UserWarning
        )
    
    yield
    reset_qe_home()
```

**Impact**: Tests will warn when using legacy detection, helping identify issues.

### Priority 3: Default allow_path_fallback Enforcement

**Status**: ✅ Already defaults to `False` in `settings.py:370`

**Additional**: Ensure tests that need PATH fallback explicitly enable it:

```python
# In test setup
from quantumvitas.core.settings import load_settings, save_settings
settings = load_settings()
settings.qe.allow_path_fallback = True  # Explicit opt-in
save_settings(settings)
```

## Summary

**Root Cause**: `QuantumEspressoEngine` uses legacy `QEInstallation()` auto-detection that bypasses the registry system entirely.

**Current Behavior**: Tests find QE via PATH/environment variables/shell configs/home scan, completely ignoring:
- Registry system
- `settings.json` configuration  
- Managed engines requirement

**Minimal Fix**: Wire registry into `QuantumEspressoEngine.__init__()` so it's used by default, with legacy fallback only when explicitly allowed.

**Expected After Fix**: Tests will fail with clear error if no managed engine and `allow_path_fallback=false`, enforcing deterministic behavior.

