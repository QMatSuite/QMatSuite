"""
Tests comparing current (HEAD) responses to golden fixtures (0873ebf baseline).

This test runs the same RPC methods on HEAD and compares the response shapes
to the golden fixtures generated from 0873ebf.
"""

import pytest
from io import StringIO
from pathlib import Path
from typing import Any

from quantumvitas.daemon.server import QVDaemon, RPCRequest
from tests.contract_crawler.golden_comparison import load_golden, compare_to_golden, GOLDEN_DIR
from tests.contract_crawler.recipes import get_recipe_for_method, PARAMETERIZED_RECIPES
from tests.contract_crawler.payloads import get_minimal_payload


def get_golden_methods() -> list[str]:
    """Get list of methods with golden fixtures."""
    if not GOLDEN_DIR.exists():
        return []
    methods = []
    for f in GOLDEN_DIR.glob("*.json"):
        if f.stem == "_manifest":
            continue
        methods.append(f.stem)
    return methods


@pytest.fixture
def daemon():
    """Create a QVDaemon instance for testing."""
    return QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())


class TestGoldenContracts:
    """Test current responses match golden fixtures."""

    @pytest.mark.parametrize("method_name", get_golden_methods())
    def test_matches_golden(self, daemon: QVDaemon, method_name: str, tmp_path: Path):
        """
        Current response matches golden fixture.

        Dispatches based on source:
        - auto_crawler: replay with minimal payload
        - recipe: run current recipe, compare normalized
        """
        golden = load_golden(method_name)
        assert golden is not None, f"Missing golden for {method_name}"

        if not golden.get("success"):
            pytest.skip(f"Golden shows expected failure for {method_name}: {golden.get('error')}")

        source = golden.get("source")

        # Dispatch based on source
        if source == "auto_crawler":
            # Auto-crawler method: replay with minimal payload
            payload = get_minimal_payload(method_name, tmp_path=tmp_path)
            if payload is None:
                pytest.skip(f"No minimal payload for {method_name}")

            response = daemon.handle_request(RPCRequest(
                id=f"golden-test-{method_name}",
                type=method_name,
                payload=payload,
            ))

            if not response.ok:
                pytest.fail(f"Request failed: {response.error}")

            matches, differences = compare_to_golden(method_name, response.data)

            if not matches:
                pytest.fail(f"Contract drift detected for {method_name}:\n" + "\n".join(differences))

        elif source == "recipe":
            # Recipe method: run current recipe, compare normalized responses
            recipe_name = golden.get("recipe_name")

            # Find recipe class for this method
            recipe_cls = get_recipe_for_method(method_name)
            if recipe_cls is None:
                pytest.skip(f"No recipe found for {method_name}")

            # Run recipe
            recipe_dir = tmp_path / method_name
            recipe_dir.mkdir(exist_ok=True)

            try:
                recipe = recipe_cls(recipe_dir, method_name)
            except TypeError:
                # Single-arg recipe (like GetStepDetailRecipe)
                recipe = recipe_cls(recipe_dir)

            if not recipe.setup():
                pytest.skip(f"Recipe setup failed for {method_name}")

            payload = recipe.build_payload()
            recipe_daemon = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())

            response = recipe_daemon.handle_request(RPCRequest(
                id=f"recipe-test-{method_name}",
                type=method_name,
                payload=payload,
            ))

            if not response.ok:
                pytest.fail(f"Recipe request failed for {method_name}: {response.error}")

            matches, differences = compare_to_golden(method_name, response.data)

            if not matches:
                pytest.fail(f"Contract drift detected for {method_name}:\n" + "\n".join(differences))

        else:
            pytest.skip(f"Unknown source: {source}")

    def test_all_golden_methods_have_metadata(self):
        """All golden fixtures have required metadata fields."""
        methods = get_golden_methods()
        if not methods:
            pytest.skip("No golden fixtures found")

        missing_metadata = []

        for method_name in methods:
            golden = load_golden(method_name)
            if golden is None:
                missing_metadata.append(f"{method_name}: fixture not found")
                continue

            # Check required metadata
            required = ["method", "success", "baseline_commit", "source", "generated_at"]
            for field in required:
                if field not in golden:
                    missing_metadata.append(f"{method_name}: missing '{field}'")

            # Check baseline_commit value
            if golden.get("baseline_commit") != "0873ebf":
                missing_metadata.append(
                    f"{method_name}: baseline_commit is '{golden.get('baseline_commit')}', expected '0873ebf'"
                )

        if missing_metadata:
            pytest.fail(
                f"Golden fixtures missing required metadata:\n" +
                "\n".join(f"  - {m}" for m in missing_metadata)
            )


class TestGoldenCoverage:
    """Test golden fixture coverage metrics."""

    def test_golden_coverage_summary(self):
        """Print summary of golden fixture coverage."""
        methods = get_golden_methods()

        success_count = 0
        failure_count = 0
        auto_count = 0
        recipe_count = 0

        for method_name in methods:
            golden = load_golden(method_name)
            if golden is None:
                continue

            if golden.get("success"):
                success_count += 1
                if golden.get("source") == "auto_crawler":
                    auto_count += 1
                elif golden.get("source") == "recipe":
                    recipe_count += 1
            else:
                failure_count += 1

        print(f"\nGolden Fixture Coverage Summary:")
        print(f"  Total fixtures: {len(methods)}")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {failure_count}")
        print(f"  Auto-crawler: {auto_count}")
        print(f"  Recipe: {recipe_count}")

        # This test always passes - it's just informational
        assert True
