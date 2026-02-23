"""Unit tests for core.engines.engine_installer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

import pytest

from qmatsuite.core.engines import engine_installer
from qmatsuite.core.engines.engine_registry import EngineRegistry


def _make_executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{text}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_install_engine_conda_creates_env_and_registers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        assert env_name == "xtb-6.7.1"
        assert "xtb=6.7.1" in packages
        assert channels == ["conda-forge"]
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        _make_executable(env_dir / "bin" / "xtb", "echo 'xtb version 6.7.1'")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)

    installation = engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)
    assert installation["source"] == "micromamba"
    assert installation["conda_env"] == "xtb-6.7.1"

    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    active = registry.get_active("xtb")
    assert active is not None
    assert active["source"] == "micromamba"


def test_install_engine_conda_verification_failure_cleans_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    removed: list[str] = []

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        env_dir.mkdir(parents=True, exist_ok=True)
        return env_dir

    def fake_remove_env(env_name: str, app_data_dir: Path) -> None:
        removed.append(env_name)

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)
    monkeypatch.setattr(engine_installer, "remove_env", fake_remove_env)

    with pytest.raises(RuntimeError, match="No required executable"):
        engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)

    assert removed == ["xtb-6.7.1"]


def test_install_engine_conda_sets_active_if_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        _make_executable(env_dir / "bin" / "xtb", "echo 'xtb version 6.7.1'")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)

    installation = engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)
    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    assert registry.get_active("xtb") is not None
    active = registry.get_active("xtb")
    assert active is not None
    assert active["source"] == installation["source"]
    assert active["conda_env"] == installation["conda_env"]


def test_uninstall_engine_removes_env_and_deregisters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    removed: list[str] = []

    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    registry.add_installation(
        "xtb",
        {
            "id": "conda-6.7.1",
            "source": "micromamba",
            "version": "6.7.1",
            "path": str(home / "micromamba" / "envs" / "xtb-6.7.1" / "bin"),
            "conda_env": "xtb-6.7.1",
            "required_binaries": ["xtb"],
            "env_vars": {},
        },
    )
    registry.set_active("xtb", "conda-6.7.1")

    monkeypatch.setattr(engine_installer, "remove_env", lambda env_name, _app_data_dir: removed.append(env_name))

    engine_installer.uninstall_engine("xtb", "conda-6.7.1", app_data_dir=home)

    assert removed == ["xtb-6.7.1"]
    updated = EngineRegistry(registry_path=home / "config" / "engines.json")
    assert updated.list_installations("xtb") == []


def test_python_engine_install_adds_python_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    captured_packages: list[str] = []

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        captured_packages.extend(packages)
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        (env_dir / "bin").mkdir(parents=True, exist_ok=True)
        (env_dir / "bin" / "python").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)
    monkeypatch.setattr(engine_installer, "_verify_python_engine", lambda _py, _mod: "2.7.0")

    installation = engine_installer.install_engine_conda("pyscf", version="2.7", app_data_dir=home)

    assert "python=3.12" in captured_packages
    assert "pyscf=2.7" in captured_packages
    assert installation["source"] == "micromamba"
    assert installation.get("python_executable")


def test_list_installable_engines_flags_manual_only() -> None:
    items = {row["engine"]: row for row in engine_installer.list_installable_engines()}
    assert items["xtb"]["manual_only"] is False
    assert items["vasp"]["manual_only"] is True


def test_installer_version_probe_does_not_pollute_caller_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("QMATSUITE_HOME", str(home))

    binary = _make_executable(
        tmp_path / "bin" / "xtb",
        "touch input_tmp.in CRASH\necho 'xtb version 6.7.1'",
    )

    caller_cwd = tmp_path / "caller"
    caller_cwd.mkdir(parents=True, exist_ok=True)
    previous_cwd = Path.cwd()
    os.chdir(caller_cwd)
    try:
        version = engine_installer._detect_binary_version("xtb", binary)
    finally:
        os.chdir(previous_cwd)

    assert version == "6.7.1"
    assert not (caller_cwd / "input_tmp.in").exists()
    assert not (caller_cwd / "CRASH").exists()


def test_verify_binary_engine_rejects_non_runnable_binary(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _make_executable(
        bin_dir / "xtb",
        "echo 'dyld: Library not loaded: libfoo.dylib' 1>&2\nexit 1",
    )

    with pytest.raises(RuntimeError, match="Version probe failed"):
        engine_installer._verify_binary_engine("xtb", bin_dir)


def test_resolve_qe_github_release_asset_macos_arm64(monkeypatch: pytest.MonkeyPatch) -> None:
    releases = [
        {
            "tag_name": "qe-7.5-macos-arm64-openmp-20260223-2367b8b",
            "html_url": "https://github.com/QMatSuite/qmatsuite-toolchain/releases/tag/qe-7.5-macos-arm64-openmp-20260223-2367b8b",
            "assets": [
                {
                    "name": "qe-7.5-macos-arm64-openmp.zip",
                    "browser_download_url": "https://example.invalid/qe-7.5-macos-arm64-openmp.zip",
                }
            ],
        }
    ]

    monkeypatch.setattr(engine_installer.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(engine_installer.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(engine_installer, "_download_text", lambda _url: json.dumps(releases))

    resolved = engine_installer.resolve_qe_github_release_asset(version="v7.5", variant="openmp")
    assert resolved["repo"] == "QMatSuite/qmatsuite-toolchain"
    assert resolved["release_tag"] == "qe-7.5-macos-arm64-openmp-20260223-2367b8b"
    assert resolved["asset_name"] == "qe-7.5-macos-arm64-openmp.zip"
    assert resolved["variant"] == "macos-arm64-openmp"


def test_resolve_qe_github_release_asset_windows_skips_libxc_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    releases = [
        {
            "tag_name": "qe-7.5-win-oneapi-msmpi-libxc-20251223-a04eb07",
            "html_url": "https://example.invalid/libxc",
            "assets": [
                {
                    "name": "qe-7.5-win-oneapi-msmpi-libxc.zip",
                    "browser_download_url": "https://example.invalid/libxc.zip",
                }
            ],
        },
        {
            "tag_name": "qe-7.5-win-oneapi-msmpi-20251223-d409e9b",
            "html_url": "https://example.invalid/win",
            "assets": [
                {
                    "name": "qe-7.5-win-oneapi-msmpi.zip",
                    "browser_download_url": "https://example.invalid/win.zip",
                }
            ],
        },
    ]

    monkeypatch.setattr(engine_installer.platform, "system", lambda: "Windows")
    monkeypatch.setattr(engine_installer.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(engine_installer, "_download_text", lambda _url: json.dumps(releases))

    resolved = engine_installer.resolve_qe_github_release_asset(version="7.5", variant="openmp")
    assert resolved["asset_name"] == "qe-7.5-win-oneapi-msmpi.zip"
    assert resolved["asset_url"] == "https://example.invalid/win.zip"
    assert resolved["variant"] == "win-oneapi-msmpi"


def test_resolve_qe_github_release_asset_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(engine_installer.platform, "machine", lambda: "riscv64")

    with pytest.raises(RuntimeError, match="No QE GitHub binary mapping"):
        engine_installer.resolve_qe_github_release_asset()


def test_install_engine_github_release_sets_executable_bits_on_unix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    archive_path = tmp_path / "qe.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("qe-7.5/bin/pw.x", "#!/bin/sh\necho test\n")

    monkeypatch.setattr(engine_installer.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        engine_installer,
        "_download_binary",
        lambda _url, output_path: output_path.write_bytes(archive_path.read_bytes()),
    )
    monkeypatch.setattr(engine_installer, "_verify_or_download_sha256", lambda _path, _checksum: None)

    installation = engine_installer.install_engine_github_release(
        "qe",
        asset_url="https://example.invalid/qe.zip",
        app_data_dir=home,
    )

    pw_path = Path(installation["path"]) / "pw.x"
    assert pw_path.exists()
    assert os.access(pw_path, os.X_OK)
