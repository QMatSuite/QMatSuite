"""
Shared fixtures for unit tests.

This module provides fixtures used across multiple test files.
"""

import pytest
from typing import Dict, Any


@pytest.fixture
def empty_step_yaml() -> Dict[str, Any]:
    """Fixture providing an empty step YAML structure."""
    return {
        "step_type_gen": "scf",
        "parameters": {},
        "cards": {},
    }


@pytest.fixture
def scf_step_yaml() -> Dict[str, Any]:
    """Fixture providing a basic SCF step YAML structure."""
    return {
        "step_type_gen": "scf",
        "parameters": {
            "SYSTEM": {},
            "ELECTRONS": {},
        },
        "cards": {},
    }

