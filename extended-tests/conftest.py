"""
Pytest configuration and fixtures for extended tests.

Extended tests are comprehensive tests based on QE official test-suite.
"""

import pytest
from pathlib import Path
import sys
import os

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))


@pytest.fixture
def qe_bin_dir():
    """Return QE bin directory path."""
    # Try to find from environment or default location
    qe_bin = os.environ.get("QE_BIN_DIR")
    if qe_bin:
        return Path(qe_bin)
    
    # Default location
    return Path.home() / "src" / "q-e-qe-7.5" / "bin"


@pytest.fixture
def qe_test_suite_dir(qe_bin_dir):
    """Return QE test-suite directory path."""
    # Infer from bin directory
    if qe_bin_dir.is_dir():
        qe_root = qe_bin_dir.parent
    else:
        qe_root = qe_bin_dir.parent.parent
    return qe_root / "test-suite"


@pytest.fixture
def skip_if_no_qe(qe_bin_dir):
    """Skip test if QE is not available."""
    if not qe_bin_dir.exists():
        pytest.skip("QE installation not found")


@pytest.fixture
def skip_if_no_test_suite(qe_test_suite_dir):
    """Skip test if QE test-suite is not available."""
    if not qe_test_suite_dir.exists():
        pytest.skip("QE test-suite not found")


# Mark all tests in extended-tests/ as extended
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "extended: Extended tests based on QE official test-suite"
    )


# Auto-mark tests in extended-tests/ directory as extended
def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        if "extended-tests" in str(item.fspath):
            item.add_marker(pytest.mark.extended)
            item.add_marker(pytest.mark.requires_qe)
            item.add_marker(pytest.mark.requires_test_suite)

