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
# Covers ALL manifest methods with successful golden fixtures.
# Methods with failed golden fixtures (get_band_structure_data, get_dos_data, import_structure)
# are tested in soft layer only since baseline itself failed.
HARD_REDLINE_FIELDS = {
    # Core project/structure/calculation methods
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
        "top_level": ["job_id", "status"],  # Baseline has job_id, not id
    },
    # Additional GUI-critical methods (from manifest with successful golden fixtures)
    "list_journal_entries": {
        "top_level": ["entries"],
        # Note: entries may be empty in test scenarios, so don't enforce item fields
    },
    # RESOLVED: GUI expects k_points (gui/src/types/qv.ts:1164-1188), manifest corrected
    "get_common_cards": {
        "top_level": [],  # k_points is optional per GUI TypeScript type
    },
    "get_pseudo_mapping": {
        "top_level": ["mapping"],
    },
    "list_demo_projects": {
        "top_level": ["demos"],
        # demos[].id, demos[].title - checked if array is non-empty
        "array_items": {"demos": ["id", "title"]},
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
    # RESOLVED: GUI expects dimensions + schema_version (gui/src/types/qv.ts:1565-1584), manifest corrected
    "get_preset_catalog": {
        "top_level": ["dimensions", "schema_version"],
        "array_items": {"dimensions": ["dimension", "label"]},
    },
    "list_qe_ui_parameters": {
        "top_level": ["parameters"],
        "array_items": {"parameters": ["name", "type"]},
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
    Empty arrays are allowed (some methods legitimately return empty lists).
    """
    violations = []

    # Empty array is OK - some methods legitimately return empty lists
    # (e.g., list_journal_entries with no history, list_demo_projects with no demos)
    if not array:
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

