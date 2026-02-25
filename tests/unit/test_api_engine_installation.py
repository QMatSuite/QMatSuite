"""Tests for API engine installation operations."""

from __future__ import annotations

import pytest

from qmatsuite.api.engines import (
    _qe_github_release_available,
    install_engine,
    list_installable_engines,
    uninstall_engine,
)


def test_install_engine_calls_conda_for_xtb(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_install_engine_conda(engine_family: str, version: str | None = None, on_progress=None):
        called["engine_family"] = engine_family
        called["version"] = version
        return {"id": "conda-6.7.1", "source": "micromamba"}

    monkeypatch.setattr("qmatsuite.api.engines.install_engine_conda", fake_install_engine_conda)

    result = install_engine("xtb", version="6.7.1", source="auto")
    assert called == {"engine_family": "xtb", "version": "6.7.1"}
    assert result["engine"] == "xtb"
    assert result["source"] == "conda"


def test_install_engine_routes_qe_github_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qmatsuite.api.engines.resolve_qe_github_release_asset",
        lambda version=None, variant="openmp": {
            "asset_url": "https://github.com/example/qe.tar.gz",
            "checksum_url": "https://github.com/example/qe.tar.gz.sha256",
        },
    )
    monkeypatch.setattr(
        "qmatsuite.api.engines.install_engine_github_release",
        lambda family, asset_url, checksum_url=None, expected_sha256=None, on_progress=None: {
            "ulid": "github-7.5-openmp",
            "source": "github_release",
            "family": family,
            "asset_url": asset_url,
            "checksum_url": checksum_url,
        },
    )

    result = install_engine("qe", source="github_release")
    assert result["source"] == "github_release"
    assert result["installation"]["ulid"] == "github-7.5-openmp"


def test_install_engine_rejects_commercial_auto() -> None:
    with pytest.raises(ValueError, match="no automatic installer"):
        install_engine("vasp", source="auto")


def test_uninstall_engine_calls_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, str] = {}

    def fake_uninstall(engine_family: str, installation_id: str) -> None:
        called["engine_family"] = engine_family
        called["installation_id"] = installation_id

    monkeypatch.setattr("qmatsuite.api.engines.uninstall_engine_kernel", fake_uninstall)

    result = uninstall_engine("xtb", "conda-6.7.1")
    assert called == {"engine_family": "xtb", "installation_id": "conda-6.7.1"}
    assert result["removed"] is True


def test_list_installable_engines_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qmatsuite.api.engines._list_installable_engines_kernel",
        lambda: [{"engine": "xtb", "manual_only": False}],
    )
    items = list_installable_engines()
    assert items == [{"engine": "xtb", "manual_only": False}]


# ---------------------------------------------------------------------------
# Auto-source selection tests
# ---------------------------------------------------------------------------


def _stub_github_release(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Patch both resolve + install for github_release path, returning a tracker dict."""
    called: dict[str, object] = {}

    monkeypatch.setattr(
        "qmatsuite.api.engines.resolve_qe_github_release_asset",
        lambda version=None, variant="openmp": {
            "asset_url": "https://example.com/qe.zip",
            "checksum_url": "",
        },
    )
    monkeypatch.setattr(
        "qmatsuite.api.engines.install_engine_github_release",
        lambda family, asset_url, checksum_url=None, expected_sha256=None, on_progress=None: (
            called.update(source="github_release", family=family)
            or {"id": "github-7.5", "source": "github_release"}
        ),
    )
    return called


def _stub_conda(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Patch install_engine_conda, returning a tracker dict."""
    called: dict[str, object] = {}

    monkeypatch.setattr(
        "qmatsuite.api.engines.install_engine_conda",
        lambda engine_family, version=None, on_progress=None: (
            called.update(source="conda", engine_family=engine_family)
            or {"id": "conda-latest", "source": "micromamba"}
        ),
    )
    return called


def test_auto_source_qe_macos_arm64_prefers_github_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """On macOS arm64, auto should select github_release for QE."""
    monkeypatch.setattr("qmatsuite.api.engines.platform.system", lambda: "Darwin")
    monkeypatch.setattr("qmatsuite.api.engines.platform.machine", lambda: "arm64")
    assert _qe_github_release_available() is True

    gh_called = _stub_github_release(monkeypatch)
    _stub_conda(monkeypatch)  # also stub conda so it doesn't explode if reached

    result = install_engine("qe", source="auto")
    assert result["source"] == "github_release"
    assert gh_called.get("source") == "github_release"


def test_auto_source_qe_windows_x64_prefers_github_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows x64, auto should select github_release for QE."""
    monkeypatch.setattr("qmatsuite.api.engines.platform.system", lambda: "Windows")
    monkeypatch.setattr("qmatsuite.api.engines.platform.machine", lambda: "AMD64")
    assert _qe_github_release_available() is True

    gh_called = _stub_github_release(monkeypatch)
    _stub_conda(monkeypatch)

    result = install_engine("qe", source="auto")
    assert result["source"] == "github_release"
    assert gh_called.get("source") == "github_release"


def test_auto_source_qe_linux_x64_falls_back_to_conda(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Linux x64, no toolchain release → auto falls back to conda for QE."""
    monkeypatch.setattr("qmatsuite.api.engines.platform.system", lambda: "Linux")
    monkeypatch.setattr("qmatsuite.api.engines.platform.machine", lambda: "x86_64")
    assert _qe_github_release_available() is False

    conda_called = _stub_conda(monkeypatch)
    result = install_engine("qe", source="auto")
    assert result["source"] == "conda"
    assert conda_called.get("source") == "conda"


def test_auto_source_xtb_always_uses_conda(monkeypatch: pytest.MonkeyPatch) -> None:
    """xTB should always use conda regardless of platform."""
    # Even on a platform with QE toolchain binaries, xTB goes via conda.
    monkeypatch.setattr("qmatsuite.api.engines.platform.system", lambda: "Darwin")
    monkeypatch.setattr("qmatsuite.api.engines.platform.machine", lambda: "arm64")

    conda_called = _stub_conda(monkeypatch)
    result = install_engine("xtb", source="auto")
    assert result["source"] == "conda"
    assert conda_called.get("source") == "conda"
