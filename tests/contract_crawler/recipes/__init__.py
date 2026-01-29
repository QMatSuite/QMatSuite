"""Recipes for testing complex RPC methods that require setup."""

# Use relative import to avoid dependency on tests package structure
from .structure_flow import GetStepDetailRecipe
from .parameterized import (
    ProjectMethodsRecipe,
    CalculationMethodsRecipe,
    StepMethodsRecipe,
    ProjectMutationsRecipe,
    CalculationMutationsRecipe,
    StepMutationsRecipe,
    WorkflowRecipe,
    ImportStepRecipe,
    get_recipe_for_method,
    PARAMETERIZED_RECIPES,
)

# Registry of all recipes for coverage tracking
# Note: Parameterized recipes are instantiated dynamically per method
ALL_RECIPES = [
    GetStepDetailRecipe,
    # Parameterized recipes are added dynamically via get_recipe_for_method()
]

# Convenience function to get all covered methods
def get_all_recipe_covered_methods() -> set[str]:
    """Return all methods covered by any recipe."""
    methods = {GetStepDetailRecipe.method_name}
    for recipe_cls in PARAMETERIZED_RECIPES:
        methods.update(recipe_cls.COVERED_METHODS)
    return methods

