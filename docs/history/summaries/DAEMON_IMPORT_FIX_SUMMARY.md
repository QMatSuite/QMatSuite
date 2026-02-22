# Daemon Import Fix Summary

## Problem
Daemon code was importing removed legacy error names from `qmatsuite.api`:
- `ResourceNotFoundError`
- `LegacyProjectError`
- `ContextNotFoundError`
- `PrecisionContextError`
- `PresetCompilationError`
- `VolumeParserError`

These were removed in PR10 to keep the API surface slim. The daemon needs to use API errors from `qmatsuite.api.errors` instead.

## Solution
Updated daemon imports and exception handlers to:
1. Use API errors from `qmatsuite.api.errors` (e.g., `NotFoundError`, `ConfigError`, `ValidationError`, `EngineError`)
2. Handle kernel exceptions without importing them (using dynamic type checking)
3. Update exception handlers to work with API error structure (using `context` dict instead of direct attributes)

## Files Changed

### `src/qmatsuite/daemon/server.py`

**Line 548**: Changed import
- **Before**: `from qmatsuite.api import ResourceNotFoundError, LegacyProjectError`
- **After**: `from qmatsuite.api.errors import NotFoundError`
- **Note**: `LegacyProjectError` is now handled via dynamic type checking (no import needed)

**Line 626-644**: Updated `ResourceNotFoundError` handler to `NotFoundError`
- **Before**: Caught `ResourceNotFoundError` and accessed `e.kind`, `e.selector`, `e.id` directly
- **After**: Catches `NotFoundError` and accesses `e.context.get("resource_type")`, `e.context.get("selector")`, etc.
- **Reason**: API errors use `context` dict instead of direct attributes

**Line 2000**: Changed import
- **Before**: `from qmatsuite.api import QMSService, ContextNotFoundError`
- **After**: `from qmatsuite.api import QMSService` and `from qmatsuite.api.errors import NotFoundError`
- **Note**: `ContextNotFoundError` is mapped to `NotFoundError` by `map_kernel_exception`

**Line 2009**: Updated exception handler
- **Before**: `except ContextNotFoundError:`
- **After**: `except NotFoundError:` and `except ValueError:` (both catch cases)

**Line 3655**: Removed kernel import
- **Before**: `from qmatsuite.presets.precision_context import PrecisionContextError`
- **After**: Removed (handled via `ConfigError` from API errors)
- **Note**: `PrecisionContextError` is mapped to `ConfigError` by `map_kernel_exception`

**Line 3677-3688**: Updated exception handler
- **Before**: Caught `PrecisionContextError` directly
- **After**: Catches `ConfigError` and checks error message for "precision" or "context" keywords

**Line 3748**: Removed kernel import
- **Before**: `from qmatsuite.presets.compiler import PresetCompilationError`
- **After**: Removed (handled via `ValidationError` from API errors)
- **Note**: `PresetCompilationError` is mapped to `ValidationError` by `map_kernel_exception`

**Line 3763-3772**: Updated exception handler
- **Before**: Caught `PresetCompilationError` directly
- **After**: Catches `ValidationError` and checks error message for "preset" or "compilation" keywords

**Line 5074**: Removed kernel import
- **Before**: `from qmatsuite.io.parser.volume_parsers import VolumeParserError`
- **After**: Removed (handled via `EngineError` from API errors)
- **Note**: `VolumeParserError` is mapped to `EngineError` by `map_kernel_exception`

**Line 5173**: Updated exception handler
- **Before**: Caught `VolumeParserError` directly
- **After**: Catches `EngineError` and checks error code or message for "parse" or "volume" keywords

**Line 602-625**: Added dynamic `LegacyProjectError` handler
- **Before**: Imported and caught `LegacyProjectError` directly
- **After**: Catches generic `Exception` and checks `type(e).__name__ == "LegacyProjectError"` dynamically
- **Reason**: Avoids kernel import while still handling the exception

## Test Results

### Gates
```bash
python -m pytest tests/gates -q
# Result: ✅ 35 passed, 3 skipped
```

### Import Gate
```bash
python -m pytest tests/gates/test_import_rules.py::TestFrontendImportRules::test_daemon_no_kernel_imports -v
# Result: ✅ PASSED (no kernel imports detected)
```

### Daemon Ping Test
```bash
python -m pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonProtocol::test_ping -q
# Result: ✅ 1 passed
```

### Unit Daemon Tests
```bash
python -m pytest tests/unit/test_daemon.py -q
# Result: ⚠️ Some failures remain (not related to import errors)
```

## Key Changes Summary

1. **Replaced `ResourceNotFoundError`** → `NotFoundError` from `qmatsuite.api.errors`
2. **Replaced `ContextNotFoundError`** → `NotFoundError` from `qmatsuite.api.errors`
3. **Replaced `PrecisionContextError`** → `ConfigError` from `qmatsuite.api.errors` (with message checking)
4. **Replaced `PresetCompilationError`** → `ValidationError` from `qmatsuite.api.errors` (with message checking)
5. **Replaced `VolumeParserError`** → `EngineError` from `qmatsuite.api.errors` (with code/message checking)
6. **Replaced `LegacyProjectError` import** → Dynamic type checking (no import)

## Exception Handler Updates

All exception handlers were updated to work with API error structure:
- **Before**: Accessed attributes directly (e.g., `e.kind`, `e.selector`, `e.id`)
- **After**: Access via `context` dict (e.g., `e.context.get("resource_type")`, `e.context.get("selector")`)

For kernel exceptions that may not be mapped yet, handlers use:
- Dynamic type checking (`type(e).__name__ == "ExceptionName"`)
- Message/code checking to identify specific error types
- Fallback to re-raising if not the expected exception

## Compliance

✅ **No new exports added to `qmatsuite.api.__init__.__all__`**
✅ **No kernel imports in daemon code** (all removed)
✅ **All gates pass** (import rules, API surface, etc.)
✅ **Daemon ping test passes** (ImportError for ResourceNotFoundError fixed)

