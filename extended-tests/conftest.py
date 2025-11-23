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

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


@pytest.fixture(scope="session")
def qe_engine():
    """Return QE engine (auto-detects installation)."""
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    
    if not engine.installation.is_valid():
        pytest.skip("QE installation not found")
    
    return engine


@pytest.fixture(scope="session")
def qe_bin_dir(qe_engine):
    """Return QE bin directory path (for backward compatibility)."""
    return qe_engine.installation.bin_dir


@pytest.fixture(scope="session")
def qe_test_suite_dir(qe_engine):
    """Return QE test-suite directory path."""
    return qe_engine.test_suite_dir


@pytest.fixture
def skip_if_no_qe(qe_engine):
    """Skip test if QE is not available."""
    if not qe_engine.installation.is_valid():
        pytest.skip("QE installation not found")


@pytest.fixture
def skip_if_no_test_suite(qe_test_suite_dir):
    """Skip test if QE test-suite is not available."""
    if not qe_test_suite_dir or not qe_test_suite_dir.exists():
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

