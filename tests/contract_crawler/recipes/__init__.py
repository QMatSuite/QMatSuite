"""Recipes for testing complex RPC methods that require setup."""

# Use relative import to avoid dependency on tests package structure
from .structure_flow import GetStepDetailRecipe

# Registry of all recipes for coverage tracking
ALL_RECIPES = [
    GetStepDetailRecipe,
    # Add more recipes here
]

