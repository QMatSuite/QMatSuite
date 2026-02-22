"""Pytest configuration and fixtures for quick tests.

Quick tests are fast, focused tests that run in CI.
Imports assume `qmatsuite` is importable (e.g. via `pip install -e .`
or `PYTHONPATH=src`).
"""

from pathlib import Path
import os
import shutil
import traceback

import pytest

from qmatsuite.core.resources import get_resources_dir


def pytest_ignore_collect(collection_path, config):
    """C4: Integrity tests must NOT run under default pytest invocation.

    Run explicitly: python -m pytest tests/integrity/ -v --tb=short
    """
    if "integrity" in str(collection_path):
        # Only collect if user explicitly requested an integrity path
        args = config.getoption("file_or_dir", [])
        return not any("integrity" in str(a) for a in args)


def _find_repo_root() -> Path:
    """Find repository root (directory containing pyproject.toml or .git)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


@pytest.fixture(scope="session", autouse=True)
def cleanup_repo_pseudo_at_start():
    """Clean up repo_root/pseudo at session start to avoid leftover confusion."""
    repo_root = _find_repo_root()
    repo_pseudo = repo_root / "pseudo"
    if repo_pseudo.exists():
        shutil.rmtree(repo_pseudo)
    yield
    # Assert at session end that it wasn't recreated
    if repo_pseudo.exists():
        pytest.fail(
            f"BUG: repo_root/pseudo was created during test session at {repo_pseudo}. "
            f"The mkdir trap should have caught this. Check test output for stack traces."
        )


@pytest.fixture(scope="session", autouse=True)
def cleanup_repo_temp_at_start():
    """Clean up repo_root/temp at session start and end (forbidden per CONSTITUTION_ZH.md 9.1.3)."""
    repo_root = _find_repo_root()
    repo_temp = repo_root / "temp"
    if repo_temp.exists():
        shutil.rmtree(repo_temp)
    yield
    # Clean up at session end as well
    if repo_temp.exists():
        shutil.rmtree(repo_temp)


@pytest.fixture(scope="session", autouse=True)
def force_test_cwd_to_tmp(tmp_path_factory):
    """Force CWD to a tmp directory to prevent relative Path('pseudo') from landing in repo root."""
    original_cwd = os.getcwd()
    tmp_cwd = tmp_path_factory.mktemp("test_cwd")
    os.chdir(tmp_cwd)
    yield
    os.chdir(original_cwd)


@pytest.fixture(scope="function", autouse=True)
def trap_repo_pseudo_creation():
    """Intercept mkdir operations to catch creation of repo_root/pseudo."""
    repo_root = _find_repo_root()
    repo_pseudo = repo_root / "pseudo"
    
    # Store original functions
    original_path_mkdir = Path.mkdir
    original_os_mkdir = os.mkdir
    original_os_makedirs = os.makedirs
    
    def check_path(target_path, operation_name):
        """Check if target_path would create repo_root/pseudo."""
        try:
            # Resolve to absolute path (best effort)
            if isinstance(target_path, Path):
                resolved = target_path.resolve()
            else:
                resolved = Path(target_path).resolve()
            
            # Check if it's exactly repo_root/pseudo or inside it
            if resolved == repo_pseudo.resolve() or repo_pseudo.resolve() in resolved.parents:
                stack = ''.join(traceback.format_stack())
                raise RuntimeError(
                    f"BUG: {operation_name} attempted to create repo_root/pseudo at {target_path} (resolved: {resolved}).\n"
                    f"Stack trace:\n{stack}"
                )
            
            # Enforce repo write policy: only allow writes to specific directories
            if resolved.is_relative_to(repo_root.resolve()):
                allowed_dirs = [
                    repo_root / ".tmp",  # New scratch directory
                    repo_root / ".qmatsuite",  # New persistent directory
                    repo_root / ".pytest_cache",
                    repo_root / "htmlcov",
                    repo_root / ".venv",  # Virtual environment
                    get_resources_dir() / "pseudo",  # Bundled pseudo library (read-only)
                ]
                # Check if it's in an allowed directory
                is_allowed = any(
                    resolved.is_relative_to(allowed.resolve()) or resolved == allowed.resolve()
                    for allowed in allowed_dirs
                )
                if not is_allowed:
                    # Allow if it's a file (not a directory creation)
                    if not resolved.exists() or resolved.is_file():
                        return  # Might be creating a file, not a directory
                    # Otherwise, this is suspicious
                    stack = ''.join(traceback.format_stack())
                    raise RuntimeError(
                        f"BUG: {operation_name} attempted to create directory under repo_root at {target_path} (resolved: {resolved}).\n"
                        f"Tests should only write to tmp directories. Allowed: .tmp/, .qmatsuite/, .pytest_cache/, htmlcov/, .venv/, src/qmatsuite/resources/pseudo/\n"
                        f"Stack trace:\n{stack}"
                    )
        except (ValueError, OSError):
            # If resolve fails (e.g., path doesn't exist yet), try string comparison
            target_str = str(target_path)
            if "pseudo" in target_str and str(repo_root) in target_str:
                stack = ''.join(traceback.format_stack())
                raise RuntimeError(
                    f"BUG: {operation_name} attempted to create path containing 'pseudo' under repo_root: {target_path}.\n"
                    f"Stack trace:\n{stack}"
                )
    
    def guarded_path_mkdir(self, *args, **kwargs):
        check_path(self, "Path.mkdir")
        return original_path_mkdir(self, *args, **kwargs)
    
    def guarded_os_mkdir(path, *args, **kwargs):
        check_path(path, "os.mkdir")
        return original_os_mkdir(path, *args, **kwargs)
    
    def guarded_os_makedirs(path, *args, **kwargs):
        check_path(path, "os.makedirs")
        return original_os_makedirs(path, *args, **kwargs)
    
    # Apply monkeypatch
    Path.mkdir = guarded_path_mkdir
    os.mkdir = guarded_os_mkdir
    os.makedirs = guarded_os_makedirs
    
    yield
    
    # Restore original functions
    Path.mkdir = original_path_mkdir
    os.mkdir = original_os_mkdir
    os.makedirs = original_os_makedirs


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
    from qmatsuite.core.paths import tmp_downloads_dir
    tutorial_dir = tmp_downloads_dir() / "qe_tutorial_examples"
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
    config.addinivalue_line("markers", "vasp_core: Tests that run VASP via the engine helpers")
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
    """Automatically clean up .tmp/runs/outdir after each test."""
    import shutil
    from qmatsuite.core.paths import tmp_runs_dir

    temp_outdir = tmp_runs_dir() / "outdir"

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
    from qmatsuite.core.engines import reset_qe_home
    
    reset_qe_home()
    
    # Diagnostic: check if QE resolution would use legacy paths
    # (Only warn, don't fail - this is informational)
    try:
        from qmatsuite.core.engines.qe_diagnostics import diagnose_qe_resolution
        report = diagnose_qe_resolution(check_legacy=True)
        if report.resolution_reason.startswith("legacy_"):
            import warnings
            warnings.warn(
                f"QE resolution using legacy path: {report.resolution_reason}\n"
                f"This bypasses the registry system. Consider using managed engines.\n"
                f"Resolved: {report.resolved_pw_path}\n"
                f"Inputs: {report.inputs_used}",
                UserWarning,
                stacklevel=2
            )
    except Exception:
        # Silently ignore diagnostic failures (don't break tests)
        pass
    
    yield
    reset_qe_home()
