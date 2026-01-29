"""Tests for recipe-based RPC method coverage."""

import pytest
from pathlib import Path

from tests.contract_crawler.recipes.structure_flow import GetStepDetailRecipe
# Import more recipes as they're added


class TestStructureFlowRecipes:
    """Test structure-related recipes."""

    def test_get_step_detail_recipe(self, tmp_path: Path):
        """get_step_detail recipe executes successfully."""
        recipe = GetStepDetailRecipe(tmp_path)
        result = recipe.execute()

        assert result.setup_ok, f"Setup failed: {result.error}"
        assert result.success, f"Recipe failed: {result.error}"
        assert result.response_data is not None


# Registry of all recipes for coverage tracking
ALL_RECIPES = [
    GetStepDetailRecipe,
    # Add more recipes here
]


class TestRecipeCoverage:
    """Verify recipe coverage of complex methods."""

    def test_all_recipes_execute(self, tmp_path: Path):
        """All registered recipes execute successfully."""
        failures = []

        for recipe_cls in ALL_RECIPES:
            recipe = recipe_cls(tmp_path / recipe_cls.__name__)
            (tmp_path / recipe_cls.__name__).mkdir(exist_ok=True)

            result = recipe.execute()
            if not result.success:
                failures.append(f"{recipe_cls.__name__}: {result.error}")

        assert not failures, f"Recipe failures:\n" + "\n".join(failures)

    def test_recipe_methods_not_duplicated(self):
        """Each method has at most one recipe."""
        method_names = [r.method_name for r in ALL_RECIPES]
        duplicates = [m for m in method_names if method_names.count(m) > 1]

        assert not duplicates, f"Duplicate recipes for: {set(duplicates)}"

