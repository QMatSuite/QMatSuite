"""
Pytest configuration for daemon tests.
"""

import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root_path() -> Path:
    """Get the project root path."""
    return Path(__file__).parent.parent.parent

