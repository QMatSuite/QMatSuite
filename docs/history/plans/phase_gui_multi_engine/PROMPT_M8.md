# M8: Cleanup — Delete QE-Only Code

## Scope

Delete all deprecated QE-specific RPC handlers from the daemon, delete QE-specific client methods and types from the GUI, and write a gate test to prevent regression.

## Prerequisites

M0-M7 must ALL be complete. Every consumer of the QE-specific RPCs must already be using the generic replacements. Verify this before proceeding.

## Pre-Deletion Verification

**CRITICAL**: Before deleting ANY code, run these checks to ensure nothing still depends on it:

```bash
# 1. Verify no GUI code still calls QE-specific RPCs
grep -rn "listQeUiParameters\|listQeParameterMetadata\|detect_qe\|list_qe_engines\|discover_qe_engines\|set_qe_engine\|reload_qe_parameter_metadata\|get_qe_parameter_metadata_debug_info\|import_step_from_qe_input" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: ONLY in useQMSClient.ts (the convenience method definitions) and qms.ts (type definitions)
# If found in any OTHER file, STOP and fix M5-M7 first

# 2. Verify renamed components are in use
grep -rn "EngineParameterBrowserPanel\|useEngineParameterMetadata" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: > 0 matches (the new generic versions are being used)

# 3. Verify generic RPCs are registered
grep -n "list_engine_families\|list_step_palette\|list_engine_ui_parameters\|list_engine_parameter_metadata\|set_engine_family" src/qmatsuite/daemon/server.py
# Expected: 5 entries in _handlers dict
```

If ANY of these checks fail, DO NOT proceed. Go back and fix the prerequisite milestones.

## Exact File List

### Modify

1. `src/qmatsuite/daemon/server.py` — Delete 9 QE RPC handlers + their registrations in `_handlers` dict
2. `gui/src/hooks/useQMSClient.ts` — Delete `listQeUiParameters` and `listQeParameterMetadata` convenience methods
3. `gui/src/types/qms.ts` — Delete `QEDetectionResult`, `detect_qe`, `list_qe_engines`, `discover_qe_engines`, `set_qe_engine`, `list_qe_ui_parameters`, `list_qe_parameter_metadata`, `reload_qe_parameter_metadata`, `get_qe_parameter_metadata_debug_info`, `import_step_from_qe_input` type entries

### Create

4. `tests/gates/test_no_qe_special_case.py`

## Do NOT Touch

- `src/qmatsuite/drivers/qe/` — QE driver code legitimately references "qe"
- `src/qmatsuite/api/utils.py` — QE metadata utilities may still be used by generic RPCs (the `list_engine_ui_parameters` handler delegates to them for engine_family="qe")
- `gui/src/components/panels/EngineParameterBrowserPanel.tsx` — Already generic (M7)
- `gui/src/hooks/useEngineParameterMetadata.ts` — Already generic (M7)

## Exact Instructions

### Step 1: Delete QE RPC registrations from server.py _handlers dict

Find the `_handlers` dict (around line 242-370). Remove these 9 entries:

```python
# DELETE these lines:
"detect_qe": self._handle_detect_qe,
"list_qe_engines": self._handle_list_qe_engines,
"discover_qe_engines": self._handle_discover_qe_engines,
"set_qe_engine": self._handle_set_qe_engine,
"list_qe_ui_parameters": self._handle_list_qe_ui_parameters,
"list_qe_parameter_metadata": self._handle_list_qe_parameter_metadata,
"reload_qe_parameter_metadata": self._handle_reload_qe_parameter_metadata,
"get_qe_parameter_metadata_debug_info": self._handle_get_qe_parameter_metadata_debug_info,
"import_step_from_qe_input": self._handle_import_step_from_qe_input,
```

### Step 2: Delete QE RPC handler methods from server.py

Delete these 9 methods from the DaemonServer class:

1. `_handle_detect_qe` (around line 718-726)
2. `_handle_list_qe_engines` (around line 738-746)
3. `_handle_discover_qe_engines` (around line 748-756)
4. `_handle_set_qe_engine` (around line 758-768)
5. `_handle_list_qe_ui_parameters` (around line 1432-1491)
6. `_handle_list_qe_parameter_metadata` (around line 1493-1909)
7. `_handle_reload_qe_parameter_metadata` (around line 1911-1957)
8. `_handle_get_qe_parameter_metadata_debug_info` (around line 1959-1990)
9. `_handle_import_step_from_qe_input` (around line 4157-4196)

**WARNING**: The `_handle_get_env_info` handler (line 728-736) calls `get_qe_engine_status()`. This handler is NOT QE-specific (it returns general environment info). Do NOT delete it. However, you may need to update it if it depends on deleted handlers.

**WARNING**: The `_handle_list_qe_parameter_metadata` handler is very long (~400 lines). Make sure you delete the entire method body including all internal branches.

### Step 3: Check for remaining QE handler references in server.py

After deletion, verify no dangling references:

```bash
grep -n "_handle_detect_qe\|_handle_list_qe_\|_handle_set_qe_\|_handle_discover_qe_\|_handle_reload_qe_\|_handle_get_qe_\|_handle_import_step_from_qe" src/qmatsuite/daemon/server.py
# Expected: 0 matches
```

### Step 4: Clean up server.py imports

After deleting the handlers, some imports at the top of server.py may become unused. Specifically, check these imports (around lines 66-77):

```python
from qmatsuite.api.utils import (
    get_ui_parameters,
    list_supported_modules,
    get_module_param_sections,
    get_module_card_sections,
    get_module_doc_url,
    get_metadata_file_info,
    get_qe_metadata_debug_info,
    safe_load_metadata,
    reload_metadata,
    _iter_params,
)
```

Check which of these are still used by the generic handlers (`_handle_list_engine_ui_parameters`, `_handle_list_engine_parameter_metadata`). Remove only the truly unused ones.

**IMPORTANT**: `get_ui_parameters`, `list_supported_modules`, and related imports may still be needed by the generic `_handle_list_engine_ui_parameters` handler (which delegates to QE metadata when engine_family="qe"). Do NOT remove these unless you verify they're unused.

### Step 5: Delete QE-specific client methods from useQMSClient.ts

In `gui/src/hooks/useQMSClient.ts`, delete:

```typescript
// DELETE these method declarations:
listQeUiParameters: (module: string, stepType: string) => Promise<...>;
listQeParameterMetadata: (operation: ..., params?: ...) => Promise<...>;
```

And their implementations:

```typescript
// DELETE these implementations:
listQeUiParameters: (module, stepType) => call('list_qe_ui_parameters', ...),
listQeParameterMetadata: (operation, params) => call('list_qe_parameter_metadata', ...),
```

### Step 6: Delete QE-specific types from qms.ts

In `gui/src/types/qms.ts`, delete:

1. The `QEDetectionResult` interface (lines 397-405):
```typescript
// DELETE:
export interface QEDetectionResult { ... }
```

2. The QE RPC entries from `QMSCommandMap` (around lines 493+):
```typescript
// DELETE these entries:
detect_qe: { ... };
list_qe_engines: { ... };
discover_qe_engines: { ... };
set_qe_engine: { ... };
list_qe_ui_parameters: { ... };
list_qe_parameter_metadata: { ... };
reload_qe_parameter_metadata: { ... };
get_qe_parameter_metadata_debug_info: { ... };
import_step_from_qe_input: { ... };
```

**WARNING**: If `QEDetectionResult` is still referenced by `SettingsPanel.tsx` (for the QE detection display), you need to either:
- Move QE detection to the generic engine status system first, OR
- Keep `QEDetectionResult` but rename it to something generic, OR
- Inline the type where it's used

Check: `grep -rn "QEDetectionResult" gui/src/`

If it's still used, keep it for now and add a TODO comment. The Settings panel's QE detection display may still need the detect_qe RPC. In that case, keep the `detect_qe` entry in the handler dict but rename it to something generic like `detect_engine` (takes engine_family parameter). This is a judgment call — if the generic RPCs fully replace QE detection, delete it; if not, keep it temporarily.

### Step 7: Write gate test

Create `tests/gates/test_no_qe_special_case.py`:

```python
"""
Gate: Final cleanup — No QE-specific RPC handlers or GUI bindings.

After M8, all QE-specific code should be eliminated from:
- daemon/server.py (no QE-specific RPC handlers)
- gui/src/ TypeScript (no QE-specific types or client methods)
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent


def test_no_qe_rpc_handlers_in_server():
    """No QE-specific RPC handler methods in daemon/server.py."""
    server_path = REPO_ROOT / "src" / "qmatsuite" / "daemon" / "server.py"
    text = server_path.read_text(encoding="utf-8")

    qe_handler_patterns = [
        r"_handle_detect_qe",
        r"_handle_list_qe_",
        r"_handle_set_qe_",
        r"_handle_discover_qe_",
        r"_handle_reload_qe_",
        r"_handle_get_qe_",
        r"_handle_import_step_from_qe",
    ]

    violations = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern in qe_handler_patterns:
            if re.search(pattern, line):
                violations.append(f"  server.py:{lineno}  {line.strip()}")

    assert not violations, (
        f"QE-specific RPC handlers still exist ({len(violations)}):\n"
        + "\n".join(violations[:20])
    )


def test_no_qe_rpc_registrations_in_server():
    """No QE-specific RPC names in the _handlers dict."""
    server_path = REPO_ROOT / "src" / "qmatsuite" / "daemon" / "server.py"
    text = server_path.read_text(encoding="utf-8")

    qe_rpc_names = [
        '"detect_qe"',
        '"list_qe_engines"',
        '"discover_qe_engines"',
        '"set_qe_engine"',
        '"list_qe_ui_parameters"',
        '"list_qe_parameter_metadata"',
        '"reload_qe_parameter_metadata"',
        '"get_qe_parameter_metadata_debug_info"',
        '"import_step_from_qe_input"',
    ]

    violations = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for rpc_name in qe_rpc_names:
            if rpc_name in line:
                violations.append(f"  server.py:{lineno}  {line.strip()}")

    assert not violations, (
        f"QE-specific RPC registrations still exist ({len(violations)}):\n"
        + "\n".join(violations[:20])
    )


def test_no_qe_specific_hooks_in_gui():
    """No QE-specific hooks or panel references in GUI TypeScript."""
    gui_src = REPO_ROOT / "gui" / "src"
    if not gui_src.exists():
        pytest.skip("GUI source not found")

    qe_patterns = [
        r"QEParameterBrowserPanel",
        r"useQEParameterMetadata",
        r"listQeUiParameters",
        r"listQeParameterMetadata",
    ]

    violations = []
    for ts_file in gui_src.rglob("*.ts"):
        try:
            text = ts_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            for pattern in qe_patterns:
                if re.search(pattern, line):
                    rel = ts_file.relative_to(REPO_ROOT)
                    violations.append(f"  {rel}:{lineno}  {line.strip()}")

    for tsx_file in gui_src.rglob("*.tsx"):
        try:
            text = tsx_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            for pattern in qe_patterns:
                if re.search(pattern, line):
                    rel = tsx_file.relative_to(REPO_ROOT)
                    violations.append(f"  {rel}:{lineno}  {line.strip()}")

    assert not violations, (
        f"QE-specific GUI code still exists ({len(violations)}):\n"
        + "\n".join(violations[:30])
    )
```

## Invariants to Preserve

- `drivers/qe/` is NOT touched — QE driver code legitimately references "qe"
- The generic RPCs (`list_engine_families`, `list_step_palette`, etc.) still work
- QE metadata utilities in `api/utils.py` may still be used by generic handlers — do NOT delete them
- `get_env_info` handler stays (it returns general environment info, not QE-specific)
- The daemon starts and processes requests without errors
- All existing tests pass (except tests that specifically tested deleted QE RPCs — those must be updated or removed)

## Verifiers

```bash
# 1. Gate test passes
source .venv/bin/activate && python -m pytest tests/gates/test_no_qe_special_case.py -v

# 2. No QE handlers in server
grep -rn "_handle_detect_qe\|_handle_list_qe_\|_handle_set_qe_\|_handle_discover_qe_\|_handle_reload_qe_\|_handle_get_qe_\|_handle_import_step_from_qe" src/qmatsuite/daemon/server.py
# Expected: 0 matches

# 3. No QE client methods in GUI
grep -rn "listQeUiParameters\|listQeParameterMetadata" gui/src/ --include="*.ts" --include="*.tsx"
# Expected: 0 matches

# 4. No QE types in GUI
grep -rn "QEDetectionResult\|QEParameterBrowser\|useQEParameterMetadata" gui/src/ --include="*.ts" --include="*.tsx"
# Expected: 0 matches (or only in comments/TODOs)

# 5. Generic RPCs still work
python -m pytest tests/daemon/test_generic_rpcs.py -v

# 6. Full test suite
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT delete `drivers/qe/` code (QE is a legitimate engine)
- Do NOT delete `api/utils.py` QE metadata functions (generic handler still uses them)
- Do NOT delete `_handle_get_env_info` (it's general-purpose, not QE-specific)
- Do NOT break the generic RPCs by removing shared infrastructure
- Do NOT delete tests/ gate tests or test infrastructure
- Do NOT delete `get_qe_engine_status` from api/utils.py if the generic settings/detection still needs it
- Do NOT introduce new QE defaults while deleting old ones

## Expected Failure Modes

1. **Tests that call deleted RPCs**: Some test files may directly test `detect_qe`, `list_qe_ui_parameters`, etc. Find and update/delete these tests first.
2. **GUI still imports deleted types**: If M7 didn't fully clean up `QEDetectionResult` usage, TypeScript compilation will fail. Check `grep -rn "QEDetectionResult" gui/src/` before deleting.
3. **Settings panel breaks**: If `SettingsPanel.tsx` still calls `detect_qe` for the QE detection display, you need to either keep it temporarily or replace with a generic `detect_engine` call.
4. **`_handle_get_env_info` depends on deleted handlers**: Check if this handler calls any of the deleted handlers internally.
5. **`_handle_list_engine_ui_parameters` depends on deleted imports**: The generic QE handler for `engine_family="qe"` imports from `api/utils`. Make sure those imports are NOT removed.
6. **Daemon crashes on startup**: If the `_handlers` dict has a stale reference to a deleted method, the daemon will crash. Verify dict and method deletion are consistent.
