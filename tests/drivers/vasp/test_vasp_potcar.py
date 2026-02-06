"""Tests for VASP POTCAR staging utility.

Tests that require a real POTCAR library are marked with skipif.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.vasp.engine.vasp_potcar import (
    POTCAR_LIBRARY_DIRS,
    get_default_potcar_root,
    list_available_potcars,
    stage_potcar,
)


def _potcar_root_available() -> bool:
    """Check if a POTCAR library is accessible."""
    root = get_default_potcar_root()
    if root is None:
        return False
    for lib in POTCAR_LIBRARY_DIRS.values():
        if (root / lib).is_dir():
            return True
    return False


skip_no_potcar = pytest.mark.skipif(
    not _potcar_root_available(),
    reason="POTCAR library not found",
)


class TestPotcarUtilities:
    """Non-conditional tests."""

    def test_get_default_potcar_root_type(self):
        """Return type is Path or None."""
        result = get_default_potcar_root()
        assert result is None or isinstance(result, Path)

    def test_unknown_functional_raises(self, tmp_path):
        """Unknown functional raises ValueError."""
        with pytest.raises(ValueError, match="Unknown functional"):
            stage_potcar(["Si"], tmp_path, functional="UNKNOWN")

    def test_missing_root_raises(self, tmp_path):
        """Missing root directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            stage_potcar(
                ["Si"], tmp_path,
                vasp_potcar_root=tmp_path / "nonexistent",
            )

    def test_missing_library_dir_raises(self, tmp_path):
        """Existing root but missing library subdir raises."""
        fake_root = tmp_path / "fake_vasp"
        fake_root.mkdir()
        with pytest.raises(FileNotFoundError, match="library directory"):
            stage_potcar(["Si"], tmp_path / "out", vasp_potcar_root=fake_root)

    def test_list_available_unknown_functional(self):
        """Unknown functional returns empty list."""
        result = list_available_potcars(functional="UNKNOWN")
        assert result == []

    def test_stage_potcar_single_element(self, tmp_path):
        """Stage POTCAR for a single element from a mock library."""
        # Build a minimal fake POTCAR library
        fake_root = tmp_path / "pp"
        pbe_dir = fake_root / "potpaw_PBE.64" / "Si"
        pbe_dir.mkdir(parents=True)
        (pbe_dir / "POTCAR").write_text("PAW_PBE Si 01Jan2000\nEND\n")

        out_dir = tmp_path / "work"
        potcar = stage_potcar(
            ["Si"], out_dir, vasp_potcar_root=fake_root,
        )
        assert potcar.exists()
        content = potcar.read_text()
        assert "PAW_PBE Si" in content

    def test_stage_potcar_multi_element(self, tmp_path):
        """Stage POTCAR for multiple elements (Na, Cl) concatenated."""
        fake_root = tmp_path / "pp"
        for elem, header in [("Na", "PAW_PBE Na 01Jan2000"),
                             ("Cl", "PAW_PBE Cl 01Jan2000")]:
            d = fake_root / "potpaw_PBE.64" / elem
            d.mkdir(parents=True)
            (d / "POTCAR").write_text(f"{header}\nEND\n")

        out_dir = tmp_path / "work"
        potcar = stage_potcar(
            ["Na", "Cl"], out_dir, vasp_potcar_root=fake_root,
        )
        content = potcar.read_text()
        # Both elements present, in order
        na_pos = content.index("Na")
        cl_pos = content.index("Cl")
        assert na_pos < cl_pos

    def test_stage_potcar_with_override(self, tmp_path):
        """Override element variant (e.g., Fe -> Fe_pv)."""
        fake_root = tmp_path / "pp"
        d = fake_root / "potpaw_PBE.64" / "Fe_pv"
        d.mkdir(parents=True)
        (d / "POTCAR").write_text("PAW_PBE Fe_pv 01Jan2000\nEND\n")

        out_dir = tmp_path / "work"
        potcar = stage_potcar(
            ["Fe"], out_dir,
            potcar_overrides={"Fe": "Fe_pv"},
            vasp_potcar_root=fake_root,
        )
        content = potcar.read_text()
        assert "Fe_pv" in content

    def test_missing_element_error(self, tmp_path):
        """Missing element POTCAR raises FileNotFoundError."""
        fake_root = tmp_path / "pp"
        (fake_root / "potpaw_PBE.64").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="POTCAR not found"):
            stage_potcar(
                ["Unobtanium"], tmp_path / "work",
                vasp_potcar_root=fake_root,
            )

    def test_list_available_potcars_mock(self, tmp_path):
        """List elements from a mock library."""
        fake_root = tmp_path / "pp"
        for elem in ["Si", "O", "Fe", "Fe_pv"]:
            d = fake_root / "potpaw_PBE.64" / elem
            d.mkdir(parents=True)
            (d / "POTCAR").write_text(f"PAW_PBE {elem}\nEND\n")
        # Also a dir without POTCAR (should be excluded)
        (fake_root / "potpaw_PBE.64" / "NOPOTCAR").mkdir()

        result = list_available_potcars(vasp_potcar_root=fake_root)
        assert result == ["Fe", "Fe_pv", "O", "Si"]


@skip_no_potcar
class TestPotcarWithRealLibrary:
    """Tests using the real POTCAR library on this machine."""

    def test_list_available_potcars_real(self):
        """Real library has available POTCARs."""
        result = list_available_potcars()
        assert len(result) > 0
        assert "Si" in result

    def test_stage_si_potcar(self, tmp_path):
        """Stage Si POTCAR from real library."""
        out_dir = tmp_path / "work"
        potcar = stage_potcar(["Si"], out_dir)
        assert potcar.exists()
        content = potcar.read_text()
        assert "Si" in content
        assert "END" in content
