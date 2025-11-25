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
    # Only check if tutorial examples exist, don't auto-download
    # (downloads should only happen in extended-tests, not in tests/)
    import sys
    project_root = Path(__file__).parent.parent
    tutorial_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
    
    # Only use if already downloaded (don't trigger download)
    if tutorial_dir.exists() and (tutorial_dir / ".git").exists():
        example_file = tutorial_dir / "0_Si_scf" / "si.scf.in"
        if example_file.exists():
            return example_file
    
    # Fallback: use a local test file if available
    local_test_file = project_root / "tests" / "integration" / "ci_test_data" / "pw_scf" / "scf-cg.in"
    if local_test_file.exists():
        return local_test_file
    
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


@pytest.fixture(autouse=True)
def cleanup_temp_outdir(project_root_path):
    """Automatically clean up temp/outdir after each test."""
    import shutil
    temp_outdir = project_root_path / "temp" / "outdir"
    
    # Clean up before test (in case previous test failed)
    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass  # Ignore cleanup errors
    
    yield
    
    # Clean up after test
    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass  # Ignore cleanup errors

