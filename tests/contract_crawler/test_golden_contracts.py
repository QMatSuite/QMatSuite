"""
Tests comparing current responses to golden fixtures.

CRITICAL: Dispatches based on golden source:
- auto_crawler methods: replayed with stored payload
- recipe methods: run fresh recipe, compare normalized responses
"""

import pytest
from io import StringIO
from pathlib import Path

from quantumvitas.daemon.server import QVDaemon, RPCRequest
from tests.contract_crawler.golden_comparison import load_golden, compare_to_golden
from tests.contract_crawler.recipes.structure_flow import GetStepDetailRecipe

# Registry of recipes (will be expanded)
ALL_RECIPES = [
    GetStepDetailRecipe,
]

GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden_0873ebf" / "daemon"


def get_golden_methods() -> list[str]:
    """Get list of methods with golden fixtures."""
    if not GOLDEN_DIR.exists():
        return []
    return [
        f.stem for f in GOLDEN_DIR.glob("*.json")
        if f.stem not in ("_manifest",)  # Skip manifest file
    ]


# Build recipe lookup by method_name
RECIPE_BY_METHOD = {r.method_name: r for r in ALL_RECIPES}


@pytest.fixture
def daemon():
    return QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())


class TestGoldenContracts:
    """Test current responses match golden fixtures."""

    @pytest.mark.parametrize("method_name", get_golden_methods())
    def test_matches_golden(self, daemon, method_name: str, tmp_path: Path):
        """
        Current response matches golden fixture.

        Dispatches based on source:
        - auto_crawler: replay with stored payload
        - recipe: run current recipe, compare normalized
        """
        golden = load_golden(method_name)
        assert golden is not None, f"Missing golden for {method_name}"

        if not golden.get("success"):
            pytest.skip(f"Golden shows expected failure for {method_name}")

        source = golden.get("source")
        assert source in ("auto_crawler", "recipe"), f"Unknown source: {source}"

        # Dispatch based on source
        if source == "auto_crawler":
            # Auto-crawler method: replay with stored payload
            payload = golden.get("payload", {})

            response = daemon.handle_request(RPCRequest(
                id=f"golden-test-{method_name}",
                type=method_name,
                payload=payload,
            ))

            assert response.ok, f"Request failed: {response.error}"

            matches, differences = compare_to_golden(method_name, response.data)

            assert matches, f"Contract drift detected:\n" + "\n".join(differences)

        elif source == "recipe":
            # Recipe method: run current recipe, compare normalized responses
            recipe_name = golden.get("recipe_name")
            assert recipe_name, f"Golden missing recipe_name for {method_name}"

            recipe_cls = RECIPE_BY_METHOD.get(method_name)
            assert recipe_cls is not None, (
                f"Recipe for {method_name} not found in current ALL_RECIPES. "
                f"Golden expects recipe: {recipe_name}"
            )

            # Run recipe to get current response
            recipe_dir = tmp_path / recipe_name
            recipe_dir.mkdir(exist_ok=True)

            recipe = recipe_cls(recipe_dir)
            result = recipe.execute()

            assert result.success, f"Recipe failed: {result.error}"

            # Compare normalized responses
            matches, differences = compare_to_golden(method_name, result.response_data)

            assert matches, f"Contract drift detected:\n" + "\n".join(differences)

    def test_all_golden_methods_have_metadata(self):
        """All golden fixtures have required metadata fields."""
        methods = get_golden_methods()
        if not methods:
            pytest.skip("No golden fixtures found. Run generate_golden.py first.")
        
        missing_metadata = []

        for method_name in methods:
            golden = load_golden(method_name)

            # Check required metadata
            required = ["method", "success", "baseline_commit", "source", "generated_at"]
            for field in required:
                if field not in golden:
                    missing_metadata.append(f"{method_name}: missing '{field}'")

            # Check source-specific metadata
            if golden.get("success"):
                source = golden.get("source")
                if source == "auto_crawler" and "payload" not in golden:
                    missing_metadata.append(f"{method_name}: auto_crawler missing 'payload'")
                elif source == "recipe" and "recipe_name" not in golden:
                    missing_metadata.append(f"{method_name}: recipe missing 'recipe_name'")

            # Check baseline_commit value
            if golden.get("baseline_commit") != "0873ebf":
                missing_metadata.append(
                    f"{method_name}: baseline_commit is '{golden.get('baseline_commit')}', expected '0873ebf'"
                )

        assert not missing_metadata, (
            f"Golden fixtures missing required metadata:\n" +
            "\n".join(f"  - {m}" for m in missing_metadata)
        )

