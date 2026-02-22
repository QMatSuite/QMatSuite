"""Tests for API engine installation operations."""

from __future__ import annotations

import pytest

from quantumvitas.api.engines import (
    install_engine,
    list_installable_engines,
    uninstall_engine,
)


def test_install_engine_calls_conda_for_xtb(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    def fake_install_engine_conda(engine_family: str, version: str | None = None):
        called["engine_family"] = engine_family
        called["version"] = version
        return {"id": "conda-6.7.1", "source": "micromamba"}

    monkeypatch.setattr("quantumvitas.api.engines.install_engine_conda", fake_install_engine_conda)

    result = install_engine("xtb", version="6.7.1", source="auto")
    assert called == {"engine_family": "xtb", "version": "6.7.1"}
    assert result["engine"] == "xtb"
    assert result["source"] == "conda"


def test_install_engine_routes_qe_github_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quantumvitas.api.engines.resolve_qe_github_release_asset",
        lambda version=None, variant="openmp": {
            "asset_url": "https://github.com/example/qe.tar.gz",
            "checksum_url": "https://github.com/example/qe.tar.gz.sha256",
        },
    )
    monkeypatch.setattr(
        "quantumvitas.api.engines.install_engine_github_release",
        lambda family, asset_url, checksum_url=None: {
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

    monkeypatch.setattr("quantumvitas.api.engines.uninstall_engine_kernel", fake_uninstall)

    result = uninstall_engine("xtb", "conda-6.7.1")
    assert called == {"engine_family": "xtb", "installation_id": "conda-6.7.1"}
    assert result["removed"] is True


def test_list_installable_engines_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "quantumvitas.api.engines._list_installable_engines_kernel",
        lambda: [{"engine": "xtb", "manual_only": False}],
    )
    items = list_installable_engines()
    assert items == [{"engine": "xtb", "manual_only": False}]
