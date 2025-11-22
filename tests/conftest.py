"""
Pytest configuration and fixtures for quick tests.

Quick tests are fast, focused tests that run in CI.
"""

import pytest
from pathlib import Path
import sys

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))


@pytest.fixture
def project_root_path():
    """Return project root path."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_input_file(project_root_path):
    """Return path to a sample QE input file for testing."""
    # Use a simple test file from examples if available
    # Use auto-downloaded tutorial examples
    import sys
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "extended-tests"))
    from utils.download_tutorial_examples import ensure_tutorial_examples
    try:
        tutorial_dir = ensure_tutorial_examples()
        example_file = tutorial_dir / "0_Si_scf" / "si.scf.in" if tutorial_dir else None
    except Exception:
        example_file = None
    if example_file.exists():
        return example_file
    return None


@pytest.fixture
def temp_dir(tmp_path):
    """Return a temporary directory for test outputs."""
    return tmp_path


# Mark all tests in tests/ as quick tests
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "quick: Quick tests that run in CI"
    )


# Auto-mark tests in tests/ directory as quick
def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Mark tests in tests/ as quick
        if "tests/" in str(item.fspath) and "extended-tests" not in str(item.fspath):
            item.add_marker(pytest.mark.quick)
        
        # Mark tests in extended-tests/ as extended
        if "extended-tests" in str(item.fspath):
            item.add_marker(pytest.mark.extended)

