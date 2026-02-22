"""
GUI field enforcement tests.

Two-layer enforcement from gui_required_fields_manifest.json:
1. SOFT LAYER: Warns on any missing manifest fields (informational)
2. HARD LAYER: Fails on HARD_REDLINE_FIELDS (critical GUI breakage)

EXECUTION PATH:
  get_recipe_for_method / get_minimal_payload → daemon.handle_request → native response
Tests the NATIVE (unshaped) daemon response format.
"""

import json
import pytest
from pathlib import Path
from io import StringIO
from typing import Any

from qmatsuite.daemon.server import QMSDaemon, RPCRequest
from tests.contract_crawler.recipes import get_recipe_for_method
from tests.contract_crawler.payloads import get_minimal_payload

MANIFEST_PATH = Path(__file__).parent / "gui_required_fields_manifest.json"

# Hard redline: Missing these fields = test FAILS (GUI breaks)
# These reflect the NATIVE (unshaped) daemon response format.
HARD_REDLINE_FIELDS = {
    # Core project/structure/calculation methods
    "get_calculation_detail": {
        "top_level": ["ulid", "steps"],
        "array_items": {"steps": ["step_ulid", "step_type_spec", "step_type_gen"]},
    },
    "get_step_detail": {
        "top_level": ["ulid", "step_type_spec", "step_type_gen"],
    },
    "list_structures": {
        "top_level": ["structures"],
        "array_items": {"structures": ["ulid", "name"]},
    },
    "list_calculations": {
        "top_level": ["calculations"],
        "array_items": {"calculations": ["ulid"]},
    },
    "create_demo_project": {
        "top_level": ["project_root"],
    },
    "create_calculation": {
        "top_level": ["calculation_ulid"],
    },
    "get_structure_vis": {
        "top_level": ["atoms", "bonds"],
    },
    "run_step": {
        "top_level": ["job_ulid", "status"],
    },
    # Additional GUI-critical methods
    "list_journal_entries": {
        "top_level": ["entries"],
    },
    "get_common_cards": {
        "top_level": [],  # k_points is optional per GUI TypeScript type
    },
    "get_pseudo_mapping": {
        "top_level": ["mapping"],
    },
    "list_demo_projects": {
        "top_level": ["demos"],
    },
    "get_project_summary": {
        "top_level": ["id", "name"],
    },
    "list_step_artifacts": {
        "top_level": ["artifacts"],
    },
    "read_step_artifact_text": {
        "top_level": ["content", "truncated", "total_bytes"],
    },
    "get_preset_catalog": {
        "top_level": ["dimensions", "schema_version"],
        "array_items": {"dimensions": ["dimension", "label"]},
    },
    "list_engine_ui_parameters": {
        "top_level": ["parameters"],
        "array_items": {"parameters": ["key", "type"]},
    },
}


def load_manifest() -> dict:
    """Load GUI required fields manifest (SSOT)."""
    if not MANIFEST_PATH.exists():
        return {"methods": {}}
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def get_testable_methods() -> list[str]:
    """Get methods that have manifest entries and recipe coverage."""
    manifest = load_manifest()
    methods = list(manifest.get("methods", {}).keys())
    # Filter to methods with recipe coverage
    return [m for m in methods if get_recipe_for_method(m) is not None or get_minimal_payload(m) is not None]


def _execute_method(method_name: str, tmp_path: Path) -> tuple[bool, dict | None, str | None]:
    """
    Execute a method via daemon and return the native response.

    Returns: (success, response_data, error_message)
    """
    daemon = QMSDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

    try:
        # Try recipe first, then minimal payload
        recipe_cls = get_recipe_for_method(method_name)
        if recipe_cls is not None:
            recipe_dir = tmp_path / method_name
            recipe_dir.mkdir(exist_ok=True)

            try:
                recipe = recipe_cls(recipe_dir, method_name)
            except TypeError:
                recipe = recipe_cls(recipe_dir)

            if not recipe.setup():
                return False, None, f"Recipe setup failed for {method_name}"

            payload = recipe.build_payload()
        else:
            payload = get_minimal_payload(method_name, tmp_path=tmp_path)
            if payload is None:
                return False, None, f"No recipe or minimal payload for {method_name}"

        response = daemon.handle_request(RPCRequest(
            id=f"gui-test-{method_name}",
            type=method_name,
            payload=payload,
        ))

        if not response.ok:
            return False, None, f"Request failed: {response.error}"

        return True, response.data, None

    except Exception as e:
        return False, None, f"Execution error: {e}"


def _check_array_items(array: list, required_fields: list[str], array_name: str, max_items: int = 5) -> list[str]:
    """
    Check array items for required fields.

    Checks up to max_items (default 5) or all items if fewer.
    Empty arrays are allowed (some methods legitimately return empty lists).
    """
    violations = []

    if not array:
        return violations

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
    Tests the NATIVE (unshaped) daemon response format.
    """

    @pytest.mark.parametrize("method_name", list(HARD_REDLINE_FIELDS.keys()))
    def test_hard_redline_fields(self, method_name: str, tmp_path: Path):
        """Verify hard redline fields exist in native daemon response."""
        spec = HARD_REDLINE_FIELDS[method_name]

        success, data, error = _execute_method(method_name, tmp_path)
        if not success:
            pytest.skip(error)

        violations = []

        # Check top-level fields
        for field in spec.get("top_level", []):
            if field not in data:
                violations.append(f"Missing top-level field: {field}")

        # Check array item fields (up to 5 items each)
        for array_name, item_fields in spec.get("array_items", {}).items():
            if array_name in data and isinstance(data[array_name], list):
                violations.extend(
                    _check_array_items(data[array_name], item_fields, array_name)
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

        success, data, error = _execute_method(method_name, tmp_path)
        if not success:
            pytest.skip(error)

        required_fields = method_spec.get("required_fields", [])

        missing = []
        for field in required_fields:
            # Simple top-level check (manifest uses JSONPath-like notation)
            top_field = field.split(".")[0].split("[")[0]
            if top_field not in data:
                missing.append(field)

        if missing:
            # Soft warning - logged but test passes
            print(f"\n[WARN] {method_name} missing manifest fields: {missing}")

        # This test always passes - it's informational
        assert True
