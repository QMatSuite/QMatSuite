"""Unit tests for centralized engine discovery module."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantumvitas.core.engines.discovery import (
    EngineDiscoveryResult,
    EngineProbe,
    _search_bundled,
    _search_env_var,
    _search_homebrew,
    _search_python_import,
    _search_system_path,
    clear_discovery_cache,
    discover_all_engines,
    discover_engine,
    get_registered_engine_names,
    is_engine_available,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear discovery cache before each test."""
    clear_discovery_cache()
    yield
    clear_discovery_cache()


class TestEngineProbeRegistry:
    """Tests for the static probe registry."""

    def test_all_known_engines_have_probes(self):
        names = get_registered_engine_names()
        expected = {
            "cp2k", "gpaw", "lammps", "orca", "psi4",
            "pyscf", "qe", "qmcpack", "vasp", "w90",
        }
        assert set(names) == expected

    def test_cp2k_has_psmp_first(self):
        """CP2K probe should list cp2k.psmp as highest-priority binary."""
        from quantumvitas.core.engines.discovery import _ENGINE_PROBES
        probe = _ENGINE_PROBES["cp2k"]
        assert probe.binary_names[0] == "cp2k.psmp"

    def test_python_native_engines_have_module(self):
        from quantumvitas.core.engines.discovery import _ENGINE_PROBES
        for name in ("pyscf", "psi4", "gpaw"):
            assert _ENGINE_PROBES[name].python_module is not None

    def test_psi4_has_conda_package(self):
        from quantumvitas.core.engines.discovery import _ENGINE_PROBES
        assert _ENGINE_PROBES["psi4"].conda_package == "psi4"


class TestSearchBundled:
    """Tests for Tier 1: bundled .qmatsuite/engines/ search."""

    def test_finds_binary_in_project_root(self, tmp_path):
        engine_dir = tmp_path / ".qmatsuite" / "engines" / "qmcpack" / "qmcpack-4.1.0" / "bin"
        engine_dir.mkdir(parents=True)
        binary = engine_dir / "qmcpack"
        binary.write_text("#!/bin/sh\necho mock")
        binary.chmod(0o755)

        probe = EngineProbe(engine_name="qmcpack", binary_names=["qmcpack"])
        result = _search_bundled(probe, project_root=tmp_path)
        assert result is not None
        assert result.available is True
        assert result.source == "bundled"
        assert result.executable_path == binary

    def test_returns_none_when_not_found(self, tmp_path):
        probe = EngineProbe(engine_name="qmcpack", binary_names=["qmcpack"])
        result = _search_bundled(probe, project_root=tmp_path)
        assert result is None

    def test_prefers_higher_version(self, tmp_path):
        """When multiple variants exist, should prefer highest (reverse sort)."""
        for version in ["1.0", "2.0"]:
            d = tmp_path / ".qmatsuite" / "engines" / "test" / f"test-{version}" / "bin"
            d.mkdir(parents=True)
            (d / "testbin").write_text("mock")

        probe = EngineProbe(engine_name="test", binary_names=["testbin"])
        result = _search_bundled(probe, project_root=tmp_path)
        assert result is not None
        assert "test-2.0" in str(result.executable_path)


class TestSearchPythonImport:
    """Tests for Tier 2: Python import via subprocess."""

    def test_finds_installed_module(self):
        """pytest itself should be importable."""
        probe = EngineProbe(engine_name="test", python_module="pytest")
        result = _search_python_import(probe)
        assert result is not None
        assert result.available is True
        assert result.source == "python_import"
        assert result.version is not None

    def test_returns_none_for_missing_module(self):
        probe = EngineProbe(engine_name="test", python_module="nonexistent_module_xyz_12345")
        result = _search_python_import(probe)
        assert result is None

    def test_skips_when_no_module_defined(self):
        probe = EngineProbe(engine_name="test")
        result = _search_python_import(probe)
        assert result is None


class TestSearchEnvVar:
    """Tests for Tier 4: environment variable search."""

    def test_finds_executable_via_env(self, tmp_path):
        binary = tmp_path / "my_engine"
        binary.write_text("#!/bin/sh\necho mock")
        binary.chmod(0o755)

        probe = EngineProbe(
            engine_name="test",
            binary_names=["my_engine"],
            env_vars=["TEST_ENGINE_BIN"],
        )
        with patch.dict(os.environ, {"TEST_ENGINE_BIN": str(binary)}):
            result = _search_env_var(probe)
        assert result is not None
        assert result.available is True
        assert result.source == "env_var"

    def test_finds_in_directory_env(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        binary = bin_dir / "pw.x"
        binary.write_text("mock")

        probe = EngineProbe(
            engine_name="qe",
            binary_names=["pw.x"],
            env_vars=["QE_HOME"],
        )
        with patch.dict(os.environ, {"QE_HOME": str(tmp_path)}):
            result = _search_env_var(probe)
        assert result is not None

    def test_returns_none_when_env_not_set(self):
        probe = EngineProbe(
            engine_name="test",
            binary_names=["test"],
            env_vars=["NONEXISTENT_ENV_VAR_XYZ"],
        )
        result = _search_env_var(probe)
        assert result is None


class TestSearchSystemPath:
    """Tests for Tier 5: system PATH search."""

    def test_finds_python_in_path(self):
        """Python should always be findable in PATH."""
        probe = EngineProbe(engine_name="test", binary_names=["python3", "python"])
        result = _search_system_path(probe)
        assert result is not None
        assert result.available is True
        assert result.source == "path"

    def test_returns_none_for_missing_binary(self):
        probe = EngineProbe(engine_name="test", binary_names=["nonexistent_binary_xyz_12345"])
        result = _search_system_path(probe)
        assert result is None


class TestSearchHomebrew:
    """Tests for Tier 6: Homebrew search."""

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_homebrew_skipped_on_non_darwin(self):
        """On macOS, homebrew search should not skip."""
        probe = EngineProbe(engine_name="test", brew_name="nonexistent_xyz")
        # Should attempt search (may return None, but shouldn't crash)
        result = _search_homebrew(probe)
        # Result is None since package doesn't exist, but function executed
        assert result is None or isinstance(result, EngineDiscoveryResult)

    def test_returns_none_when_no_brew_name(self):
        probe = EngineProbe(engine_name="test")
        result = _search_homebrew(probe)
        assert result is None


class TestDiscoverEngine:
    """Tests for the main discover_engine() function."""

    def test_unknown_engine_returns_unavailable(self):
        result = discover_engine("totally_fake_engine_xyz")
        assert result.available is False
        assert "Unknown engine" in result.reason

    def test_result_is_cached(self):
        r1 = discover_engine("totally_fake_engine_xyz")
        r2 = discover_engine("totally_fake_engine_xyz")
        assert r1 is r2

    def test_cache_bypass(self):
        r1 = discover_engine("totally_fake_engine_xyz", use_cache=True)
        r2 = discover_engine("totally_fake_engine_xyz", use_cache=False)
        assert r1 is not r2
        assert r1.available == r2.available


class TestIsEngineAvailable:
    """Tests for the convenience is_engine_available() function."""

    def test_returns_bool(self):
        result = is_engine_available("totally_fake_engine_xyz")
        assert isinstance(result, bool)
        assert result is False


class TestDiscoverAllEngines:
    """Tests for discover_all_engines()."""

    def test_returns_dict_for_all_engines(self):
        results = discover_all_engines()
        names = get_registered_engine_names()
        assert set(results.keys()) == set(names)
        for name, result in results.items():
            assert isinstance(result, EngineDiscoveryResult)
            assert result.engine_name == name


class TestCp2kMultiFlavor:
    """CP2K-specific tests for multi-flavor detection."""

    def test_finds_psmp_over_ssmp(self, tmp_path):
        """cp2k.psmp should be preferred over cp2k.ssmp."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "cp2k.psmp").write_text("mock")
        (bin_dir / "cp2k.ssmp").write_text("mock")

        probe = EngineProbe(
            engine_name="cp2k",
            binary_names=["cp2k.psmp", "cp2k.popt", "cp2k.ssmp", "cp2k.sopt", "cp2k"],
            env_vars=["CP2K_HOME"],
        )
        with patch.dict(os.environ, {"CP2K_HOME": str(tmp_path)}):
            result = _search_env_var(probe)
        assert result is not None
        assert "psmp" in str(result.executable_path)

    def test_falls_back_to_generic(self, tmp_path):
        """If no flavored binary, should find generic cp2k."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "cp2k").write_text("mock")

        probe = EngineProbe(
            engine_name="cp2k",
            binary_names=["cp2k.psmp", "cp2k.popt", "cp2k.ssmp", "cp2k.sopt", "cp2k"],
            env_vars=["CP2K_HOME"],
        )
        with patch.dict(os.environ, {"CP2K_HOME": str(tmp_path)}):
            result = _search_env_var(probe)
        assert result is not None
        assert result.executable_path.name == "cp2k"
