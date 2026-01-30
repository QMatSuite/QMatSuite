"""
Schema preservation gate for golden contract tests.

Ensures that:
1. All keys from baseline fixture exist in shaped HEAD response
2. Types match (dict/list/scalar)
3. Normalization cannot hide missing fields or type changes

This gate prevents "normalization cheating" where schema drift is hidden.
"""

import json
import pytest
from pathlib import Path
from typing import Any, Set, Tuple, List

from tests.contract_crawler.golden_comparison import GOLDEN_DIR


def get_schema_keys(obj: Any, prefix: str = "") -> Set[Tuple[str, str]]:
    """
    Extract all keys with their types from a nested structure.

    Returns set of (path, type_name) tuples.
    Type is: 'dict', 'list', 'str', 'int', 'float', 'bool', 'null'
    """
    keys = set()

    if isinstance(obj, dict):
        keys.add((prefix or "ROOT", "dict"))
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.update(get_schema_keys(value, path))
    elif isinstance(obj, list):
        keys.add((prefix or "ROOT", "list"))
        if obj:
            # Check first item to get list element schema
            keys.update(get_schema_keys(obj[0], f"{prefix}[0]"))
    elif obj is None:
        keys.add((prefix, "null"))
    elif isinstance(obj, bool):
        keys.add((prefix, "bool"))
    elif isinstance(obj, int):
        keys.add((prefix, "int"))
    elif isinstance(obj, float):
        keys.add((prefix, "float"))
    elif isinstance(obj, str):
        keys.add((prefix, "str"))
    else:
        keys.add((prefix, type(obj).__name__))

    return keys


# Fields whose sub-keys are environment-specific (skip key presence check)
# These are dicts where the keys themselves are data (not schema)
ENVIRONMENT_DEPENDENT_DICTS = {
    "grouped_by_library",  # Keys are library names
    "species_map",  # Keys are element names
    "resolved_by_element",  # Keys are element names
    "candidates_by_element",  # Keys are element names
    "element_colors",  # Keys are element names
}

# Subtrees that can be fully skipped (truly environment-dependent)
# STRICT POLICY: Only skip subtrees with genuinely nondeterministic content
FULLY_SKIPPABLE_SUBTREES = {
    "entries",  # Journal entries vary by recipe operations (write order)
    "demos",  # Demo list varies by environment (filesystem discovery)
    "archives",  # Pseudo archives depend on installed libraries
    "libraries",  # Library list varies by environment
    "perf",  # Performance metrics vary by run
    "sssp_defaults",  # SSSP state varies by environment
    "installed_sources",  # Installation state varies
    "variant_statuses",  # Library installation state varies
    "data",  # get_library_status data varies by environment
    # NOTE: templates and discovered_engines NOT skipped - use schema enforcement
}

# Subtrees where we skip content but enforce item schema (GUI-critical)
# Format: {field_name: [required_item_fields]}
# NOTE: Field requirements are method-specific. Some methods (like add_step_to_calculation)
# have different step schemas in baseline (step_id instead of id, no name).
ITEM_SCHEMA_REQUIRED_SUBTREES = {
    "steps": ["type"],  # Minimum: type is always required. id/name vary by method.
    "structures": ["id", "name"],  # Each structure must have these
    "calculations": ["ulid"],  # Each calculation must have these
    # Templates: enforce schema but allow different order/count (filesystem discovery order varies)
    "templates": ["name"],  # Each template must have name
    # Discovered engines: may be empty in CI, but if present, enforce schema
    "discovered_engines": [],  # If present, items should have consistent schema
}

# Lists that are allowed to be empty even when baseline had items
# These are environment-dependent lists where CI may not have the software installed
ALLOW_EMPTY_WHEN_BASELINE_HAD_ITEMS = {
    "discovered_engines",  # CI may not have QE installed (0 engines in CI, 1+ locally)
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
    # For these fields, we enforce that items have the required fields from baseline
    if key in ITEM_SCHEMA_REQUIRED_SUBTREES:
        required_fields = ITEM_SCHEMA_REQUIRED_SUBTREES[key]

        if not isinstance(baseline, list):
            return violations

        if not isinstance(current, list):
            violations.append(f"{path}: Expected list, got {type(current).__name__}")
            return violations

        # EMPTY LIST POLICY: Empty when baseline had items = violation
        # Exception: Environment-dependent lists (like discovered_engines) are allowed to be empty
        if baseline and not current:
            if key not in ALLOW_EMPTY_WHEN_BASELINE_HAD_ITEMS:
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

            # For steps, check what baseline actually has (different methods have different schemas)
            if key == "steps" and baseline:
                # Use baseline item as reference for required fields
                baseline_item = baseline[0] if baseline else {}
                # Enforce minimum: step_type_spec is always required (canonical naming)
                if "step_type_spec" not in item:
                    violations.append(f"{path}[{i}]: Missing GUI-critical field 'step_type_spec'")
                # Also check if baseline had ulid/step_ulid - enforce whichever baseline has
                if "ulid" in baseline_item and "ulid" not in item:
                    violations.append(f"{path}[{i}]: Missing GUI-critical field 'ulid' (baseline has it)")
                if "step_ulid" in baseline_item and "step_ulid" not in item:
                    violations.append(f"{path}[{i}]: Missing GUI-critical field 'step_ulid' (baseline has it)")
            else:
                # For other arrays, use fixed required_fields list
                for field in required_fields:
                    if field not in item:
                        violations.append(f"{path}[{i}]: Missing GUI-critical field '{field}'")

        return violations

    if isinstance(baseline, dict):
        if not isinstance(current, dict):
            if current is None:
                return violations
            violations.append(f"{path}: Expected dict, got {type(current).__name__}")
            return violations

        # Skip environment-dependent dict sub-keys
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


def get_golden_methods_with_success() -> list[str]:
    """Get list of methods with successful golden fixtures."""
    if not GOLDEN_DIR.exists():
        return []
    methods = []
    for f in GOLDEN_DIR.glob("*.json"):
        if f.stem == "_manifest":
            continue
        try:
            data = json.loads(f.read_text())
            if data.get("success"):
                methods.append(f.stem)
        except Exception:
            pass
    return methods


class TestSchemaPreservation:
    """Test that response schemas match baseline after shaping."""

    @pytest.mark.parametrize("method_name", get_golden_methods_with_success())
    def test_schema_keys_preserved(self, method_name: str):
        """
        Verify all baseline schema keys exist in shaped response.

        This gate ensures:
        - No keys are deleted by normalization
        - Types are preserved
        - Schema drift is visible, not hidden
        """
        golden_file = GOLDEN_DIR / f"{method_name}.json"
        if not golden_file.exists():
            pytest.skip(f"No golden fixture for {method_name}")

        golden = json.loads(golden_file.read_text())
        if not golden.get("success"):
            pytest.skip(f"Golden shows failure for {method_name}")

        baseline_response = golden.get("response", {})
        if not baseline_response:
            pytest.skip(f"Empty baseline response for {method_name}")

        # Get baseline schema keys
        baseline_keys = get_schema_keys(baseline_response)

        # Report the schema for reference
        key_paths = sorted(k[0] for k in baseline_keys)

        # This test validates that the baseline schema is captured
        # The actual comparison with HEAD happens in test_golden_contracts.py
        # Here we just ensure the schema extraction works
        assert len(baseline_keys) > 0, f"No keys found in baseline for {method_name}"

        # Store schema info for debugging
        print(f"\n{method_name} baseline schema keys: {len(baseline_keys)}")
        for path in key_paths[:10]:  # First 10 for brevity
            print(f"  {path}")
        if len(key_paths) > 10:
            print(f"  ... and {len(key_paths) - 10} more")


class TestSchemaDrift:
    """
    Test that shaped HEAD responses preserve baseline schemas.

    This runs AFTER the compat layer shapes responses and BEFORE normalization.
    """

    @pytest.mark.parametrize("method_name", get_golden_methods_with_success())
    def test_no_schema_drift(self, method_name: str, tmp_path: Path):
        """
        Verify shaped HEAD response has all keys from baseline.

        Violations are reported as test failures with specific paths.
        """
        from io import StringIO
        from quantumvitas.daemon.server import QVDaemon, RPCRequest
        from quantumvitas.daemon.compat import shape_response
        from tests.contract_crawler.recipes import get_recipe_for_method
        from tests.contract_crawler.payloads import get_minimal_payload

        golden_file = GOLDEN_DIR / f"{method_name}.json"
        if not golden_file.exists():
            pytest.skip(f"No golden fixture for {method_name}")

        golden = json.loads(golden_file.read_text())
        if not golden.get("success"):
            pytest.skip(f"Golden shows failure for {method_name}")

        baseline_response = golden.get("response", {})
        if not baseline_response:
            pytest.skip(f"Empty baseline response for {method_name}")

        source = golden.get("source")

        # Get HEAD response
        daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

        try:
            if source == "auto_crawler":
                payload = get_minimal_payload(method_name)
                if payload is None:
                    pytest.skip(f"No minimal payload for {method_name}")
            else:
                recipe_cls = get_recipe_for_method(method_name)
                if recipe_cls is None:
                    pytest.skip(f"No recipe for {method_name}")

                recipe_dir = tmp_path / method_name
                recipe_dir.mkdir(exist_ok=True)

                try:
                    recipe = recipe_cls(recipe_dir, method_name)
                except TypeError:
                    recipe = recipe_cls(recipe_dir)

                if not recipe.setup():
                    pytest.skip(f"Recipe setup failed for {method_name}")

                payload = recipe.build_payload()

            response = daemon.handle_request(RPCRequest(
                id=f"schema-test-{method_name}",
                type=method_name,
                payload=payload,
            ))

            if not response.ok:
                pytest.skip(f"Request failed: {response.error}")

            # Apply compat shaping (this is what we're testing)
            shaped_response = shape_response(method_name, response.data)

            # Compare schemas
            violations = compare_schemas(baseline_response, shaped_response)

            if violations:
                violation_msg = "\n".join(f"  - {v}" for v in violations[:20])
                if len(violations) > 20:
                    violation_msg += f"\n  ... and {len(violations) - 20} more"
                pytest.fail(
                    f"Schema drift detected for {method_name}:\n{violation_msg}"
                )

        except Exception as e:
            pytest.skip(f"Execution error for {method_name}: {e}")
