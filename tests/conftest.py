"""Pytest configuration and fixtures for quick tests.

Quick tests are fast, focused tests that run in CI.
Imports assume `quantumvitas` is importable (e.g. via `pip install -e .`
or `PYTHONPATH=src`).
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root_path() -> Path:
    """Return project root path."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def ci_test_data_dir(project_root_path: Path) -> Path:
    """Return path to bundled test data directory."""
    data_dir = project_root_path / "tests" / "data"
    if not data_dir.exists():
        pytest.skip(f"Test data not found: {data_dir}")
    return data_dir


@pytest.fixture
def sample_input_file(project_root_path: Path):
    """Return path to a sample QE input file for testing.

    Prefer a small local CI test file; fall back to tutorial examples only
    if they have already been downloaded.
    """
    project_root = project_root_path

    # Prefer local CI test data
    local_test_file = (
        project_root
        / "tests"
        / "data"
        / "pw_single_tests"
        / "scf-cg.in"
    )
    if local_test_file.exists():
        return local_test_file

    # Fallback: use tutorial examples if already downloaded (do not auto-download)
    tutorial_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
    if tutorial_dir.exists() and (tutorial_dir / ".git").exists():
        example_file = tutorial_dir / "0_Si_scf" / "si.scf.in"
        if example_file.exists():
            return example_file

    # Nothing suitable found
    return None


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "quick: Quick tests that run in CI")
    config.addinivalue_line("markers", "extended: Extended tests")
    config.addinivalue_line("markers", "unit: Tests that do not run QE")
    config.addinivalue_line("markers", "qe_core: Tests that run QE via the engine helpers")
    config.addinivalue_line("markers", "qe_cli: Tests that run QE via the CLI")


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Automatically mark tests based on their location."""
    for item in items:
        path = Path(item.fspath).as_posix()
        if "tests/" in path and "extended-tests" not in path:
            item.add_marker(pytest.mark.quick)
        if "extended-tests" in path:
            item.add_marker(pytest.mark.extended)
        if "/tests/unit/" in path or path.endswith("/tests/unit"):
            item.add_marker(pytest.mark.unit)
        elif "/tests/cli/" in path:
            item.add_marker(pytest.mark.qe_cli)
        elif "/tests/integration/" in path:
            item.add_marker(pytest.mark.qe_core)


@pytest.fixture(autouse=True)
def cleanup_temp_outdir(project_root_path: Path):
    """Automatically clean up temp/outdir after each test."""
    import shutil

    temp_outdir = project_root_path / "temp" / "outdir"

    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass

    yield

    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def reset_qe_registry():
    """Reset QE home registry before and after each test.
    
    This prevents test pollution where a unit test's fake QE installation
    persists into CLI tests that need the real QE.
    """
    from quantumvitas.core.engines import reset_qe_home
    
    reset_qe_home()
    yield
    reset_qe_home()