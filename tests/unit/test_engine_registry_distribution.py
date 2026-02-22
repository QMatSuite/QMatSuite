"""Tests for distribution engine registry (engines.json + discovery)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantumvitas.core.engines.engine_meta import ENGINE_META
from quantumvitas.core.engines.engine_registry import EngineRegistry

_INSTALL_ID_KEY = "id"


def _make_executable(path: Path, text: str = "echo ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{text}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _install_id(installation: dict) -> str | None:
    return installation.get(_INSTALL_ID_KEY)


def test_engine_meta_completeness() -> None:
    expected = {
        "qe",
        "vasp",
        "xtb",
        "lammps",
        "orca",
        "gaussian",
        "abinit",
        "cp2k",
        "siesta",
        "w90",
        "yambo",
        "qmcpack",
        "pyscf",
        "psi4",
        "gpaw",
    }
    assert set(ENGINE_META.keys()) == expected

    for name, meta in ENGINE_META.items():
        assert meta.get("display_name")
        assert meta.get("engine_type") in {"binary", "python"}
        assert "required_binaries" in meta


def test_engine_meta_binaries_match_runtime_sources() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checks = {
        "qe": ("src/quantumvitas/drivers/qe/recipe.py", "pw.x"),
        "vasp": ("src/quantumvitas/drivers/vasp/recipe.py", "vasp_std"),
        "xtb": ("src/quantumvitas/drivers/xtb/writer.py", 'executable: str = "xtb"'),
        "lammps": ("src/quantumvitas/drivers/lammps/recipe.py", '"lmp"'),
        "orca": ("src/quantumvitas/drivers/orca/recipe.py", '"orca"'),
        "gaussian": ("src/quantumvitas/drivers/gaussian/handler.py", "g09 or g16"),
        "abinit": ("src/quantumvitas/drivers/abinit/recipe.py", '"abinit"'),
        "cp2k": ("src/quantumvitas/drivers/cp2k/recipe.py", "cp2k.ssmp"),
        "siesta": ("src/quantumvitas/drivers/siesta/recipe.py", '"siesta"'),
        "w90": ("src/quantumvitas/drivers/w90/recipe.py", "wannier90.x"),
        "yambo": ("src/quantumvitas/drivers/yambo/recipe.py", '"yambo"'),
        "qmcpack": ("src/quantumvitas/drivers/qmcpack/recipe.py", '"qmcpack"'),
        "pyscf": ("src/quantumvitas/engine/pyscf_engine.py", "import pyscf"),
        "psi4": ("src/quantumvitas/engine/psi4_engine.py", "import psi4"),
        "gpaw": ("src/quantumvitas/engine/gpaw_engine.py", "import gpaw"),
    }
    for engine, (relpath, expected_fragment) in checks.items():
        text = (repo_root / relpath).read_text(encoding="utf-8")
        assert expected_fragment in text, f"{engine} metadata mismatch against {relpath}"


def test_registry_crud_roundtrip(tmp_path: Path) -> None:
    registry_path = tmp_path / "engines.json"
    registry = EngineRegistry(registry_path=registry_path)

    qe_install = {
        "id": "bundled-7.5",
        "source": "bundled",
        "path": str(tmp_path / "qe" / "bin"),
        "required_binaries": ["pw.x"],
        "env_vars": {},
    }
    registry.add_installation("qe", qe_install)
    assert _install_id(registry.get_active("qe") or {}) == "bundled-7.5"

    second = {
        "id": "system-pw.x",
        "source": "system_path",
        "path": str(tmp_path / "sysbin"),
        "required_binaries": ["pw.x"],
        "env_vars": {},
    }
    registry.add_installation("qe", second)
    assert registry.set_active("qe", "system-pw.x") is True
    assert _install_id(registry.get_active("qe") or {}) == "system-pw.x"

    assert registry.remove_installation("qe", "system-pw.x") is True
    assert _install_id(registry.get_active("qe") or {}) == "bundled-7.5"


def test_save_is_atomic_and_valid_json(tmp_path: Path) -> None:
    registry_path = tmp_path / "engines.json"
    registry = EngineRegistry(registry_path=registry_path)
    registry._data = {
        "schema_version": 1,
        "engines": {"qe": {"installations": [], "active": None}},
    }
    registry.save()

    loaded = json.loads(registry_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1
    assert not registry_path.with_suffix(".json.tmp").exists()


def test_discovery_finds_bundled_qe_and_preserves_user_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))

    _make_executable(home / "engines" / "qe" / "bundled-7.5" / "bin" / "pw.x")

    registry = EngineRegistry()
    registry._data = {
        "schema_version": 1,
        "engines": {
            "vasp": {
                "installations": [
                    {
                        "id": "user-vasp",
                        "source": "user_path",
                        "path": "/opt/vasp/bin",
                        "required_binaries": ["vasp_std"],
                        "env_vars": {},
                    }
                ],
                "active": "user-vasp",
            }
        },
    }
    registry.save()

    discovered = EngineRegistry().discover(persist=False)
    qe_entry = discovered["engines"]["qe"]
    assert any(inst["source"] == "bundled" for inst in qe_entry["installations"])

    vasp_entry = discovered["engines"]["vasp"]
    assert any(inst["source"] == "user_path" for inst in vasp_entry["installations"])


def test_discovery_marks_stale_installations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))

    registry = EngineRegistry()
    registry._data = {
        "schema_version": 1,
        "engines": {
            "qe": {
                "installations": [
                    {
                        "id": "system-pw.x",
                        "source": "system_path",
                        "path": str(tmp_path / "missing-bin"),
                        "required_binaries": ["pw.x"],
                        "env_vars": {},
                    }
                ],
                "active": "system-pw.x",
            }
        },
    }
    registry.save()

    discovered = EngineRegistry().discover(persist=False)
    qe_installs = discovered["engines"]["qe"]["installations"]
    stale = next(inst for inst in qe_installs if _install_id(inst) == "system-pw.x")
    assert stale["stale"] is True


def test_discovery_finds_system_path_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))

    _make_executable(bin_dir / "xtb")

    discovered = EngineRegistry().discover(persist=False)
    xtb_entry = discovered["engines"]["xtb"]
    system_installs = [i for i in xtb_entry["installations"] if i["source"] == "system_path"]
    assert system_installs, "xTB should be discovered from PATH"
    assert xtb_entry["active"] == _install_id(system_installs[0])


def test_get_active_binary_handles_windows_suffix_variant(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "qe-bin"
    _make_executable(bin_dir / "pw.exe")

    registry = EngineRegistry(registry_path=tmp_path / "engines.json")
    registry.add_installation(
        "qe",
        {
            "id": "user-qe",
            "source": "user_path",
            "path": str(bin_dir),
            "required_binaries": ["pw.x"],
            "env_vars": {},
        },
    )
    assert registry.set_active("qe", "user-qe") is True
    resolved = registry.get_active_binary("qe", binary_name="pw.x")
    assert resolved is not None
    assert resolved.name in {"pw.exe", "pw.x", "pw.x.exe"}
