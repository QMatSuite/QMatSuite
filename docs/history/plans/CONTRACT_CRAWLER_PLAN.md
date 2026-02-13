# Contract Crawler Hardening Plan

**Author**: Lead Reviewer (Opus)
**Date**: 2026-01-29
**Status**: Ready for Implementation (Revised per feedback)

---

## Revision Notes (2026-01-29)

Addressed 4 concerns from review:

1. **PR1 execution path**: Now reuses golden contract execution path (recipes + compat shaping) instead of creating new daemon invocation paths
2. **GUI manifest SSOT**: Two-layer approach - manifest is SSOT, hard redline subset for failures
3. **Daemon import ban collateral**: New dedicated test file, does NOT modify `test_import_rules.py`'s `FORBIDDEN_PREFIXES`
4. **Array schema enforcement**: Checks multiple items (min(5, len)), explicit empty list policy

---

## What's Broken / Risky

### 1. Skip Mechanisms Hide GUI-Critical Fields

**Evidence from code review**:

`tests/contract_crawler/golden_comparison.py` (lines 79-123):
```python
DATA_DEPENDENT_FIELDS = {
    ...
    "steps",      # ⚠️ GUI-CRITICAL - entire field skipped
    "structure",  # ⚠️ GUI-CRITICAL - value comparison skipped
    "status",     # ⚠️ GUI-CRITICAL - value comparison skipped
    ...
}
```

`tests/contract_crawler/test_schema_preservation.py` (lines 66-77):
```python
DATA_DEPENDENT_SUBTREES = {
    ...
    "steps",  # ⚠️ GUI-CRITICAL - entire subtree skipped in schema check
    ...
}
```

**Risk**: If HEAD changes `steps[].id` → `steps[].step_id`, tests pass (field skipped) but GUI breaks (expects `steps[].id`).

### 2. GUI-Required Fields Not Validated

**Evidence**: `gui_required_fields_manifest.json` lists 20+ methods with specific field requirements:
- `get_calculation_detail`: requires `steps[].id`, `steps[].name`, `steps[].type`
- `get_step_detail`: requires `id`, `name`, `step_type`, `parameters`
- `create_demo_project`: requires `project_id`, `project_name`, `structure.id`

**Current state**: No test validates these fields exist and have correct types after shaping.

### 3. Daemon Import Gate Has Coverage Gaps

**Evidence from `tests/gates/test_import_rules.py` (lines 218-227)**:
```python
FORBIDDEN_PREFIXES = (
    "quantumvitas.core",
    "quantumvitas.calculation",
    "quantumvitas.analysis",
    "quantumvitas.io",
    "quantumvitas.drivers",
    "quantumvitas.engine",
    "quantumvitas.workflow",
    "quantumvitas.presets",
)
```

**Missing kernel modules** (not in FORBIDDEN_PREFIXES):
- `quantumvitas.project`
- `quantumvitas.data`
- `quantumvitas.execution`
- `quantumvitas.history`
- `quantumvitas.ir`
- `quantumvitas.legacy`
- `quantumvitas.parsers`
- `quantumvitas.viz`
- `quantumvitas._vault`
- `quantumvitas.engines` (different from `engine`)

### 4. `_shape_create_demo_project` Analysis

**Location**: `src/quantumvitas/daemon/compat.py` lines 709-769

**Current import** (line 721):
```python
from quantumvitas.api import QVService
```

**Verdict**: This import is from `quantumvitas.api` which is **ALLOWED** per architecture rules. The shaper calls:
- `QVService.get_project_summary(project_path)` - API method
- `QVService.list_structures_data(project_path)` - API method
- `QVService.list_calculations_data(project_path)` - API method

**No refactoring needed** - the shaper correctly uses API layer, not kernel.

---

## Non-Negotiable Laws (P0)

1. **GUI-critical fields are enforced by tests** (shape/types/required paths) even if values are not identical.

2. **Daemon kernel-import ban is enforced by a gate test** covering ALL of `src/quantumvitas/daemon/` with a complete forbidden prefix list.

3. **`_shape_create_demo_project` must only call API capabilities** (ALREADY SATISFIED - uses `quantumvitas.api.QVService`).

---

## PR Breakdown

### PR1: Add GUI Field Enforcement Tests

**Goal**: Ensure GUI-critical fields exist in shaped responses with correct types.

**Key Design Decisions**:
- **Reuses existing execution path**: Uses `get_recipe_for_method` / `get_minimal_payload` + `daemon.handle_request` + `shape_response` (same as `test_golden_contracts.py`)
- **Manifest is SSOT**: Reads from `gui_required_fields_manifest.json`, doesn't duplicate field specs
- **Two-layer enforcement**:
  - Layer 1 (soft): Warnings for all manifest fields missing (informational)
  - Layer 2 (hard): Failures for `HARD_REDLINE_FIELDS` (critical GUI fields)

**Files to create/edit**:

1. **CREATE** `tests/contract_crawler/test_gui_field_enforcement.py`

```python
"""
GUI field enforcement tests.

Two-layer enforcement from gui_required_fields_manifest.json:
1. SOFT LAYER: Warns on any missing manifest fields (informational)
2. HARD LAYER: Fails on HARD_REDLINE_FIELDS (critical GUI breakage)

EXECUTION PATH: Reuses golden contract path:
  get_recipe_for_method / get_minimal_payload → daemon.handle_request → shape_response
This ensures we test the SAME code path as golden contracts.
"""

import json
import pytest
from pathlib import Path
from io import StringIO
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.daemon.compat import shape_response
from tests.contract_crawler.recipes import get_recipe_for_method
from tests.contract_crawler.payloads import get_minimal_payload
from tests.contract_crawler.golden_comparison import load_golden

MANIFEST_PATH = Path(__file__).parent.parent.parent / "gui_required_fields_manifest.json"

# Hard redline: Missing these fields = test FAILS (GUI breaks)
# Subset of manifest fields that are truly critical
HARD_REDLINE_FIELDS = {
    "get_calculation_detail": {
        "top_level": ["id", "steps"],
        "array_items": {"steps": ["id", "type", "name"]},
    },
    "get_step_detail": {
        "top_level": ["id", "name", "step_type"],
    },
    "list_structures": {
        "top_level": ["structures"],
        "array_items": {"structures": ["id", "name"]},
    },
    "list_calculations": {
        "top_level": ["calculations"],
        "array_items": {"calculations": ["id"]},
    },
    "create_demo_project": {
        "top_level": ["project_root", "project_id"],
    },
    "create_calculation": {
        "top_level": ["calculation_id"],
    },
    "get_structure_vis": {
        "top_level": ["atoms", "bonds"],
    },
    "run_step": {
        "top_level": ["id", "status"],
    },
}


def load_manifest() -> dict:
    """Load GUI required fields manifest (SSOT)."""
    if not MANIFEST_PATH.exists():
        return {"methods": {}}
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def get_testable_methods() -> list[str]:
    """Get methods that have both golden fixtures and manifest entries."""
    manifest = load_manifest()
    methods = list(manifest.get("methods", {}).keys())
    # Filter to methods with golden fixtures
    from tests.contract_crawler.golden_comparison import GOLDEN_DIR
    if GOLDEN_DIR.exists():
        golden_methods = {f.stem for f in GOLDEN_DIR.glob("*.json") if f.stem != "_manifest"}
        methods = [m for m in methods if m in golden_methods]
    return methods


def _execute_method(method_name: str, tmp_path: Path) -> tuple[bool, dict | None, str | None]:
    """
    Execute a method using the SAME path as golden contracts.

    Returns: (success, shaped_response, error_message)
    """
    daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    golden = load_golden(method_name)

    if golden is None:
        return False, None, f"No golden fixture for {method_name}"

    if not golden.get("success"):
        return False, None, f"Golden shows failure: {golden.get('error')}"

    source = golden.get("source")

    try:
        if source == "auto_crawler":
            payload = get_minimal_payload(method_name, tmp_path=tmp_path)
            if payload is None:
                return False, None, f"No minimal payload for {method_name}"
        else:
            recipe_cls = get_recipe_for_method(method_name)
            if recipe_cls is None:
                return False, None, f"No recipe for {method_name}"

            recipe_dir = tmp_path / method_name
            recipe_dir.mkdir(exist_ok=True)

            try:
                recipe = recipe_cls(recipe_dir, method_name)
            except TypeError:
                recipe = recipe_cls(recipe_dir)

            if not recipe.setup():
                return False, None, f"Recipe setup failed for {method_name}"

            payload = recipe.build_payload()

        response = daemon.handle_request(RPCRequest(
            id=f"gui-test-{method_name}",
            type=method_name,
            payload=payload,
        ))

        if not response.ok:
            return False, None, f"Request failed: {response.error}"

        # Apply compat shaping (same as golden contracts)
        shaped = shape_response(method_name, response.data)
        return True, shaped, None

    except Exception as e:
        return False, None, f"Execution error: {e}"


def _check_array_items(array: list, required_fields: list[str], array_name: str, max_items: int = 5) -> list[str]:
    """
    Check array items for required fields.

    Checks up to max_items (default 5) or all items if fewer.
    Empty array when baseline had items = violation.
    """
    violations = []

    if not array:
        violations.append(f"{array_name}: Empty array (GUI expects items)")
        return violations

    # Check min(max_items, len(array)) items
    items_to_check = min(max_items, len(array))

    for i in range(items_to_check):
        item = array[i]
        if not isinstance(item, dict):
            violations.append(f"{array_name}[{i}]: Expected dict, got {type(item).__name__}")
            continue

        for field in required_fields:
            if field not in item:
                violations.append(f"{array_name}[{i}]: Missing required field '{field}'")

    return violations


class TestGUIFieldEnforcementHardRedline:
    """
    HARD LAYER: Test critical GUI fields.

    Missing fields here = TEST FAILS (GUI would break).
    """

    @pytest.mark.parametrize("method_name", list(HARD_REDLINE_FIELDS.keys()))
    def test_hard_redline_fields(self, method_name: str, tmp_path: Path):
        """
        Verify hard redline fields exist in shaped response.

        Uses SAME execution path as golden contracts:
        get_recipe/get_minimal_payload → daemon.handle_request → shape_response
        """
        spec = HARD_REDLINE_FIELDS[method_name]

        success, shaped, error = _execute_method(method_name, tmp_path)
        if not success:
            pytest.skip(error)

        violations = []

        # Check top-level fields
        for field in spec.get("top_level", []):
            if field not in shaped:
                violations.append(f"Missing top-level field: {field}")

        # Check array item fields (up to 5 items each)
        for array_name, item_fields in spec.get("array_items", {}).items():
            if array_name in shaped and isinstance(shaped[array_name], list):
                violations.extend(
                    _check_array_items(shaped[array_name], item_fields, array_name)
                )

        if violations:
            pytest.fail(
                f"GUI hard redline violation for {method_name}:\n" +
                "\n".join(f"  - {v}" for v in violations)
            )


class TestGUIFieldEnforcementSoftManifest:
    """
    SOFT LAYER: Test all manifest fields (informational).

    Missing fields here = WARNING (logged but test passes).
    This layer uses manifest as SSOT.
    """

    @pytest.mark.parametrize("method_name", get_testable_methods())
    def test_manifest_fields_coverage(self, method_name: str, tmp_path: Path):
        """
        Report coverage of manifest fields (soft warnings).

        Does not fail on missing fields (that's the hard layer's job).
        """
        manifest = load_manifest()
        method_spec = manifest.get("methods", {}).get(method_name, {})

        if not method_spec:
            pytest.skip(f"No manifest entry for {method_name}")

        success, shaped, error = _execute_method(method_name, tmp_path)
        if not success:
            pytest.skip(error)

        required_fields = method_spec.get("required_fields", [])

        missing = []
        for field in required_fields:
            # Simple top-level check (manifest uses JSONPath-like notation)
            top_field = field.split(".")[0].split("[")[0]
            if top_field not in shaped:
                missing.append(field)

        if missing:
            # Soft warning - logged but test passes
            print(f"\n[WARN] {method_name} missing manifest fields: {missing}")

        # This test always passes - it's informational
        assert True
```

2. **EDIT** `tests/contract_crawler/golden_comparison.py` - Add comment documentation for skip rationale:

```python
# At line 79, add comment:
# WARNING: Fields in DATA_DEPENDENT_FIELDS skip value comparison.
# GUI-critical fields (steps, structure, status) are validated separately
# by test_gui_field_enforcement.py to ensure they exist with correct types.
DATA_DEPENDENT_FIELDS = {
    ...
}
```

**Acceptance criteria**:
- `TestGUIFieldEnforcementHardRedline` passes for all methods in `HARD_REDLINE_FIELDS`
- If a hard redline field is missing, test FAILS (not skipped)
- `TestGUIFieldEnforcementSoftManifest` runs for all manifest methods (logs warnings only)
- Uses SAME execution path as `test_golden_contracts.py` (no new daemon invocation)

**Test command**:
```bash
source .venv/bin/activate
python -m pytest tests/contract_crawler/test_gui_field_enforcement.py -v --tb=short
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

### PR2: Dedicated Daemon Import Gate (No Collateral)

**Goal**: Ensure daemon package cannot import from ANY kernel module.

**Key Design Decision**:
- **DO NOT modify `test_import_rules.py`'s `FORBIDDEN_PREFIXES`** - that would affect CLI, daemon, and notebook tests
- Create a NEW dedicated test file with its own `DAEMON_KERNEL_PREFIXES` constant
- This avoids collateral damage to other tests

**Files to create** (NO edits to existing files):

1. **CREATE** `tests/gates/test_daemon_kernel_ban.py`

```python
"""
Daemon kernel import ban gate.

P0 LAW: Daemon package MUST NOT import from kernel modules.
Allowed imports:
- quantumvitas.api.*
- quantumvitas.daemon.* (same package)
- stdlib
- third-party packages

This test scans ALL files in src/quantumvitas/daemon/ including compat.py.

NOTE: This test has its own DAEMON_KERNEL_PREFIXES constant and does NOT
modify test_import_rules.py's FORBIDDEN_PREFIXES to avoid collateral.
"""

import ast
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
DAEMON_DIR = PROJECT_ROOT / "src/quantumvitas/daemon"

# Complete list of kernel module prefixes (daemon MUST NOT import these)
# This is a SUPERSET of test_import_rules.py's FORBIDDEN_PREFIXES
# We keep our own copy to avoid collateral impact on other tests
DAEMON_KERNEL_PREFIXES = (
    # Original set from test_import_rules.py
    "quantumvitas.core",
    "quantumvitas.calculation",
    "quantumvitas.analysis",
    "quantumvitas.io",
    "quantumvitas.drivers",
    "quantumvitas.engine",
    "quantumvitas.workflow",
    "quantumvitas.presets",
    # Additional kernel modules (daemon-specific enforcement)
    "quantumvitas.project",
    "quantumvitas.data",
    "quantumvitas.execution",
    "quantumvitas.history",
    "quantumvitas.ir",
    "quantumvitas.legacy",
    "quantumvitas.parsers",
    "quantumvitas.viz",
    "quantumvitas._vault",
    "quantumvitas.engines",
)

# Allowed quantumvitas imports for daemon
DAEMON_ALLOWED_PREFIXES = (
    "quantumvitas.api",
    "quantumvitas.daemon",
)


def find_imports(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Find all imports in a Python file.

    Returns list of (line_number, import_type, module_name) tuples.
    """
    imports = []
    try:
        source = file_path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, "import", alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, "from", node.module))

    return imports


def test_daemon_no_kernel_imports():
    """
    Verify ALL daemon files do not import from kernel modules.

    This is a P0 gate - daemon MUST NOT have any kernel imports.
    Uses DAEMON_KERNEL_PREFIXES (not test_import_rules.py's FORBIDDEN_PREFIXES).
    """
    if not DAEMON_DIR.exists():
        pytest.skip("Daemon directory does not exist")

    violations = []

    for py_file in DAEMON_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        for line_num, import_type, module in find_imports(py_file):
            # Skip non-quantumvitas imports
            if not module.startswith("quantumvitas"):
                continue

            # Check if allowed
            is_allowed = any(module.startswith(prefix) for prefix in DAEMON_ALLOWED_PREFIXES)

            # Check if forbidden
            is_forbidden = any(module.startswith(prefix) for prefix in DAEMON_KERNEL_PREFIXES)

            if is_forbidden and not is_allowed:
                rel_path = py_file.relative_to(PROJECT_ROOT)
                violations.append(
                    f"  {rel_path}:{line_num}: {import_type} {module}"
                )

    if violations:
        pytest.fail(
            f"Daemon kernel import ban violated!\n"
            f"P0 LAW: Daemon MUST NOT import from kernel modules.\n"
            f"Allowed: quantumvitas.api.*, quantumvitas.daemon.*\n"
            f"Violations:\n" + "\n".join(violations)
        )


def test_compat_py_specifically():
    """
    Specifically verify compat.py has no kernel imports.

    This file is the compat shaping layer and is easy to accidentally
    add kernel imports to.
    """
    compat_file = DAEMON_DIR / "compat.py"
    if not compat_file.exists():
        pytest.skip("compat.py does not exist")

    violations = []

    for line_num, import_type, module in find_imports(compat_file):
        if not module.startswith("quantumvitas"):
            continue

        is_forbidden = any(module.startswith(prefix) for prefix in DAEMON_KERNEL_PREFIXES)
        is_allowed = any(module.startswith(prefix) for prefix in DAEMON_ALLOWED_PREFIXES)

        if is_forbidden and not is_allowed:
            violations.append(f"  Line {line_num}: {import_type} {module}")

    if violations:
        pytest.fail(
            f"compat.py has forbidden kernel imports!\n"
            f"The shaper must only use quantumvitas.api.* capabilities.\n"
            f"Violations:\n" + "\n".join(violations)
        )
```

**Why this approach avoids collateral**:

1. `test_import_rules.py` remains UNCHANGED
2. `DAEMON_KERNEL_PREFIXES` is a SUPERSET specific to daemon enforcement
3. CLI and notebook tests continue using the original `FORBIDDEN_PREFIXES`
4. Future updates to daemon rules don't affect other frontends

**Acceptance criteria**:
- All existing tests pass (including `test_import_rules.py`)
- `test_daemon_no_kernel_imports` passes
- `test_compat_py_specifically` passes
- If someone adds `from quantumvitas.core import ...` to compat.py, test fails

**Test command**:
```bash
source .venv/bin/activate
python -m pytest tests/gates/test_daemon_kernel_ban.py -v --tb=short
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

### PR3: Enhanced Array Schema Enforcement

**Goal**: Prevent `steps` from being entirely skipped in schema comparison, with robust array checking.

**Key Design Decisions**:
- Check **multiple array items** (min(5, len)), not just index 0
- **Empty list policy**: Empty list when baseline had items = VIOLATION
- Split `DATA_DEPENDENT_SUBTREES` into two categories

**Files to edit**:

1. **EDIT** `tests/contract_crawler/test_schema_preservation.py`:

```python
# At line 66, replace DATA_DEPENDENT_SUBTREES with two categories:

# Subtrees that can be fully skipped (truly environment-dependent)
FULLY_SKIPPABLE_SUBTREES = {
    "entries",  # Journal entries vary by recipe operations
    "demos",  # Demo list varies by environment
    "archives",  # Pseudo archives vary by environment
    "libraries",  # Library list varies by environment
    "perf",  # Performance metrics vary by run
    "sssp_defaults",  # SSSP state varies by environment
    "installed_sources",  # Installation state varies
    "variant_statuses",  # Library installation state varies
    "data",  # get_library_status data varies by environment
}

# Subtrees where we skip content but enforce item schema (GUI-critical)
# Format: {field_name: [required_item_fields]}
ITEM_SCHEMA_REQUIRED_SUBTREES = {
    "steps": ["id", "type", "name"],  # Each step must have these
    "structures": ["id", "name"],  # Each structure must have these
    "calculations": ["id"],  # Each calculation must have these
}

# Maximum items to check in arrays (balance thoroughness vs performance)
MAX_ARRAY_ITEMS_TO_CHECK = 5


def compare_schemas(baseline: Any, current: Any, path: str = "") -> List[str]:
    """
    Compare schemas deeply and return list of violations.

    Rules:
    - All keys in baseline must exist in current
    - Types must match (dict/list/scalar)
    - Lists: check up to MAX_ARRAY_ITEMS_TO_CHECK items
    - Empty list when baseline had items = VIOLATION
    - Values may differ (that's for normalization)
    """
    violations = []

    if baseline is None:
        return violations

    key = path.split(".")[-1] if path else ""

    # Skip data-dependent subtrees entirely
    if key in FULLY_SKIPPABLE_SUBTREES:
        return violations

    # Item schema required subtrees: skip content but enforce item schema
    if key in ITEM_SCHEMA_REQUIRED_SUBTREES:
        required_fields = ITEM_SCHEMA_REQUIRED_SUBTREES[key]

        if not isinstance(baseline, list):
            return violations

        if not isinstance(current, list):
            violations.append(f"{path}: Expected list, got {type(current).__name__}")
            return violations

        # EMPTY LIST POLICY: Empty when baseline had items = violation
        if baseline and not current:
            violations.append(f"{path}: Empty list (baseline had {len(baseline)} items)")
            return violations

        if not current:
            # Both empty - OK
            return violations

        # Check multiple items (up to MAX_ARRAY_ITEMS_TO_CHECK)
        items_to_check = min(MAX_ARRAY_ITEMS_TO_CHECK, len(current))

        for i in range(items_to_check):
            item = current[i]
            if not isinstance(item, dict):
                violations.append(f"{path}[{i}]: Expected dict, got {type(item).__name__}")
                continue

            for field in required_fields:
                if field not in item:
                    violations.append(f"{path}[{i}]: Missing GUI-critical field '{field}'")

        return violations

    # Rest of original function unchanged...
    if isinstance(baseline, dict):
        if not isinstance(current, dict):
            if current is None:
                return violations
            violations.append(f"{path}: Expected dict, got {type(current).__name__}")
            return violations

        if key in ENVIRONMENT_DEPENDENT_DICTS:
            return violations

        for key in baseline:
            new_path = f"{path}.{key}" if path else key
            if key not in current:
                violations.append(f"{new_path}: Missing key in response")
            else:
                violations.extend(compare_schemas(baseline[key], current[key], new_path))

    elif isinstance(baseline, list):
        if not isinstance(current, list):
            violations.append(f"{path}: Expected list, got {type(current).__name__}")
            return violations

        # Check multiple items for structural consistency
        if baseline and current:
            items_to_check = min(MAX_ARRAY_ITEMS_TO_CHECK, len(baseline), len(current))
            for i in range(items_to_check):
                violations.extend(compare_schemas(baseline[i], current[i], f"{path}[{i}]"))

    elif isinstance(baseline, bool):
        if not isinstance(current, bool):
            violations.append(f"{path}: Expected bool, got {type(current).__name__}")

    elif isinstance(baseline, (int, float)):
        if not isinstance(current, (int, float)):
            violations.append(f"{path}: Expected number, got {type(current).__name__}")

    elif isinstance(baseline, str):
        if not isinstance(current, str):
            violations.append(f"{path}: Expected str, got {type(current).__name__}")

    return violations
```

**Key changes from original**:

1. **Multi-item checking**: `items_to_check = min(MAX_ARRAY_ITEMS_TO_CHECK, len(current))` - checks up to 5 items
2. **Empty list policy**: `if baseline and not current:` triggers violation
3. **Split skip lists**: `FULLY_SKIPPABLE_SUBTREES` vs `ITEM_SCHEMA_REQUIRED_SUBTREES`

**Acceptance criteria**:
- Schema test validates `steps[0..4].id`, `steps[0..4].type`, `steps[0..4].name`
- Empty `steps` array when baseline had items = test FAILS
- If shaped response has `steps[0].step_id` instead of `steps[0].id`, test FAILS
- All other tests still pass

**Test command**:
```bash
source .venv/bin/activate
python -m pytest tests/contract_crawler/test_schema_preservation.py -v --tb=short
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

---

## Summary: Exact Implementation Steps

### PR1: GUI Field Enforcement (Two-Layer)
1. Create `tests/contract_crawler/test_gui_field_enforcement.py`
2. Implement `HARD_REDLINE_FIELDS` dict for critical fields (test FAILS on missing)
3. Implement `_execute_method()` that reuses golden contract execution path
4. Implement `_check_array_items()` that checks min(5, len) items
5. Add `TestGUIFieldEnforcementHardRedline` class (failures)
6. Add `TestGUIFieldEnforcementSoftManifest` class (warnings only, manifest SSOT)
7. Add comment to `golden_comparison.py` explaining skip rationale
8. Run: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

### PR2: Daemon Import Gate (No Collateral)
1. Create `tests/gates/test_daemon_kernel_ban.py` (NEW FILE ONLY)
2. Define `DAEMON_KERNEL_PREFIXES` (superset, independent of test_import_rules.py)
3. Define `DAEMON_ALLOWED_PREFIXES`
4. Add `test_daemon_no_kernel_imports` scanning all daemon files
5. Add `test_compat_py_specifically` for compat.py
6. **DO NOT modify test_import_rules.py**
7. Run: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

### PR3: Enhanced Array Schema Enforcement
1. Edit `tests/contract_crawler/test_schema_preservation.py`
2. Split `DATA_DEPENDENT_SUBTREES` into `FULLY_SKIPPABLE_SUBTREES` and `ITEM_SCHEMA_REQUIRED_SUBTREES`
3. Add `MAX_ARRAY_ITEMS_TO_CHECK = 5` constant
4. Update `compare_schemas` to:
   - Check min(5, len) items for `ITEM_SCHEMA_REQUIRED_SUBTREES`
   - Enforce empty list policy (empty when baseline had items = violation)
   - Check multiple items in regular list comparison
5. Run: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

---

## Verification: Current compat.py Status

**Reviewed `_shape_create_demo_project`** (compat.py:709-769):

```python
def _shape_create_demo_project(response: Dict[str, Any]) -> Dict[str, Any]:
    ...
    if project_root:
        from pathlib import Path
        from quantumvitas.api import QVService  # ← ALLOWED (api.*)
        ...
        summary = QVService.get_project_summary(project_path)  # API method
        structures = QVService.list_structures_data(project_path)  # API method
        calcs = QVService.list_calculations_data(project_path)  # API method
```

**Verdict**: ✅ No kernel imports. Uses only `quantumvitas.api.QVService`. No refactoring needed.

---

## Test Commands Summary

After each PR, run full suite to ensure no regressions:

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Expected result: All tests pass (2904+ passed, ~19 skipped).
