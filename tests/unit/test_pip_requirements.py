"""Tests for pip_requirements feature in engine meta, installer, and registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qmatsuite.core.engines.engine_meta import ENGINE_META


# ---------------------------------------------------------------------------
# ENGINE_META schema tests
# ---------------------------------------------------------------------------

def test_engine_meta_all_have_pip_requirements() -> None:
    """Every engine entry must have a pip_requirements key that is a dict."""
    for name, meta in ENGINE_META.items():
        assert "pip_requirements" in meta, f"{name} missing pip_requirements"
        assert isinstance(meta["pip_requirements"], dict), f"{name} pip_requirements must be dict"


def test_pyscf_declares_berny_and_geometric() -> None:
    """PySCF must declare pyberny and geometric as pip dependencies."""
    reqs = ENGINE_META["pyscf"]["pip_requirements"]
    assert reqs == {"pyberny": "berny", "geometric": "geometric"}


def test_binary_engines_empty_pip_requirements() -> None:
    """All binary engines must have empty pip_requirements."""
    binary_engines = [k for k, v in ENGINE_META.items() if v.get("engine_type") == "binary"]
    assert len(binary_engines) == 12, f"Expected 12 binary engines, got {len(binary_engines)}"
    for name in binary_engines:
        assert ENGINE_META[name]["pip_requirements"] == {}, f"{name} should have empty pip_requirements"


# ---------------------------------------------------------------------------
# engine_installer pip functions
# ---------------------------------------------------------------------------

def test_pip_install_called_for_nonempty() -> None:
    """_pip_install_requirements invokes pip install with the right packages."""
    from qmatsuite.core.engines.engine_installer import _pip_install_requirements

    fake_pyexe = Path("/fake/python")
    reqs = {"pyberny": "berny", "geometric": "geometric"}
    with patch("qmatsuite.core.engines.engine_installer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        _pip_install_requirements(fake_pyexe, reqs)

    mock_run.assert_called_once()
    args = mock_run.call_args
    cmd = args[0][0]
    assert cmd[0] == str(fake_pyexe)
    assert cmd[1:3] == ["-m", "pip"]
    assert "install" in cmd
    assert "pyberny" in cmd
    assert "geometric" in cmd


def test_pip_install_skipped_for_empty() -> None:
    """_pip_install_requirements is a no-op when requirements is empty."""
    from qmatsuite.core.engines.engine_installer import _pip_install_requirements

    with patch("qmatsuite.core.engines.engine_installer.subprocess.run") as mock_run:
        _pip_install_requirements(Path("/fake/python"), {})

    mock_run.assert_not_called()


def test_pip_install_failure_raises() -> None:
    """_pip_install_requirements raises RuntimeError on non-zero exit."""
    from qmatsuite.core.engines.engine_installer import _pip_install_requirements

    with patch("qmatsuite.core.engines.engine_installer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="No matching distribution", stdout="")
        with pytest.raises(RuntimeError, match="pip install failed"):
            _pip_install_requirements(Path("/fake/python"), {"badpkg": "badmod"})


def test_pip_install_failure_triggers_env_cleanup(tmp_path: Path) -> None:
    """When pip install fails during install_engine_conda, the env is cleaned up."""
    from qmatsuite.core.engines.engine_installer import install_engine_conda

    app_dir = tmp_path / "app"

    with (
        patch("qmatsuite.core.engines.engine_installer.create_env") as mock_create,
        patch("qmatsuite.core.engines.engine_installer.remove_env") as mock_remove,
        patch("qmatsuite.core.engines.engine_installer._find_python_executable") as mock_find_py,
        patch("qmatsuite.core.engines.engine_installer._verify_python_engine") as mock_verify,
        patch("qmatsuite.core.engines.engine_installer._pip_install_requirements") as mock_pip,
    ):
        fake_env = tmp_path / "envs" / "pyscf-latest"
        mock_create.return_value = fake_env
        mock_find_py.return_value = fake_env / "bin" / "python"
        mock_verify.return_value = "2.6.0"
        mock_pip.side_effect = RuntimeError("pip install failed for ['pyberny']")

        with pytest.raises(RuntimeError, match="pip install failed"):
            install_engine_conda("pyscf", app_data_dir=app_dir)

        mock_remove.assert_called_once()


def test_verify_pip_requirements_fails_when_dep_missing() -> None:
    """_verify_pip_requirements raises when import check fails."""
    from qmatsuite.core.engines.engine_installer import _verify_pip_requirements

    with patch("qmatsuite.core.engines.engine_installer.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="ModuleNotFoundError", stdout="")
        with pytest.raises(RuntimeError, match="pip dep 'pyberny'"):
            _verify_pip_requirements(Path("/fake/python"), {"pyberny": "berny"})


# ---------------------------------------------------------------------------
# engine_registry verification
# ---------------------------------------------------------------------------

def test_verify_checks_pip_deps(tmp_path: Path) -> None:
    """_verify_installation fails when a pip dependency is not importable."""
    from qmatsuite.core.engines.engine_registry import EngineRegistry

    registry = EngineRegistry(registry_path=tmp_path / "engines.json")
    installation = {
        "id": "conda-2.6.0",
        "source": "micromamba",
        "python_executable": str(tmp_path / "bin" / "python"),
        "env_vars": {},
    }
    # Create a fake python executable so path check passes
    pyexe = tmp_path / "bin" / "python"
    pyexe.parent.mkdir(parents=True, exist_ok=True)
    pyexe.write_text("#!/bin/sh\n", encoding="utf-8")
    pyexe.chmod(0o755)

    with patch.object(registry, "_check_python_import") as mock_check:
        # First call: main module succeeds; second call: pip dep fails
        mock_check.side_effect = [(True, "2.6.0"), (False, None)]
        ok, reason = registry._verify_installation("pyscf", installation)

    assert not ok
    assert "pip dependency" in reason
    assert "pyberny" in reason


def test_verify_passes_all_pip_deps(tmp_path: Path) -> None:
    """_verify_installation succeeds when all pip deps are importable."""
    from qmatsuite.core.engines.engine_registry import EngineRegistry

    registry = EngineRegistry(registry_path=tmp_path / "engines.json")
    installation = {
        "id": "conda-2.6.0",
        "source": "micromamba",
        "python_executable": str(tmp_path / "bin" / "python"),
        "env_vars": {},
    }
    pyexe = tmp_path / "bin" / "python"
    pyexe.parent.mkdir(parents=True, exist_ok=True)
    pyexe.write_text("#!/bin/sh\n", encoding="utf-8")
    pyexe.chmod(0o755)

    with patch.object(registry, "_check_python_import") as mock_check:
        # Main module + 2 pip deps all succeed
        mock_check.side_effect = [(True, "2.6.0"), (True, "0.8"), (True, "1.1")]
        ok, reason = registry._verify_installation("pyscf", installation)

    assert ok
    assert reason is None
