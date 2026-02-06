"""Tests for VASP POSCAR and KPOINTS pure parse/write functions.

Enforces the primary semantic loop:
    YAML(params+structure+kpoints) -> write -> parse -> YAML (semantic equality)

No text fidelity, no comments/whitespace preservation.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from quantumvitas.drivers.vasp.io.poscar import write_poscar_text, parse_poscar_text
from quantumvitas.drivers.vasp.io.kpoints import write_kpoints_text, parse_kpoints_text


SAMPLES_DIR = Path(__file__).parent.parent.parent / "inputformat" / "samples" / "vasp"

# ──────────────────────────────────────────────────────────────────────────
# Fixtures: canonical SSOT dicts
# ──────────────────────────────────────────────────────────────────────────

SI_DIAMOND_STRUCTURE = {
    "lattice": [
        [5.4309, 0.0, 0.0],
        [0.0, 5.4309, 0.0],
        [0.0, 0.0, 5.4309],
    ],
    "species": ["Si", "Si"],
    "frac_coords": [
        [0.0, 0.0, 0.0],
        [0.25, 0.25, 0.25],
    ],
    "comment": "Si diamond",
}

SI_FCC_STRUCTURE = {
    "lattice": [
        [0.0, 2.715, 2.715],
        [2.715, 0.0, 2.715],
        [2.715, 2.715, 0.0],
    ],
    "species": ["Si", "Si"],
    "frac_coords": [
        [0.0, 0.0, 0.0],
        [0.25, 0.25, 0.25],
    ],
    "comment": "Si FCC primitive",
}

NACL_STRUCTURE = {
    "lattice": [
        [5.64, 0.0, 0.0],
        [0.0, 5.64, 0.0],
        [0.0, 0.0, 5.64],
    ],
    "species": ["Na", "Na", "Na", "Na", "Cl", "Cl", "Cl", "Cl"],
    "frac_coords": [
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0],
        [0.0, 0.0, 0.5],
        [0.5, 0.5, 0.5],
    ],
    "comment": "NaCl rocksalt",
}

KPOINTS_AUTO_GAMMA = {
    "mode": "automatic",
    "mesh": [4, 4, 4],
    "shift": [0, 0, 0],
    "centering": "Gamma",
}

KPOINTS_AUTO_MP = {
    "mode": "automatic",
    "mesh": [6, 6, 6],
    "shift": [0.5, 0.5, 0.5],
    "centering": "Monkhorst-Pack",
}

KPOINTS_LINE = {
    "mode": "line",
    "npoints": 40,
    "coord_type": "reciprocal",
    "path": [
        {
            "start": [0.0, 0.0, 0.0],
            "end": [0.5, 0.0, 0.5],
            "start_label": "G",
            "end_label": "X",
        },
        {
            "start": [0.5, 0.0, 0.5],
            "end": [0.5, 0.25, 0.75],
            "start_label": "X",
            "end_label": "W",
        },
    ],
}

KPOINTS_EXPLICIT = {
    "mode": "explicit",
    "coord_type": "reciprocal",
    "kpoints": [
        [0.0, 0.0, 0.0, 1.0],
        [0.5, 0.0, 0.0, 3.0],
        [0.5, 0.5, 0.0, 3.0],
        [0.5, 0.5, 0.5, 1.0],
    ],
}


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _assert_lattice_equal(a: list, b: list, tol: float = 1e-10):
    """Assert two 3x3 lattice matrices are element-wise equal."""
    for i in range(3):
        for j in range(3):
            assert abs(a[i][j] - b[i][j]) < tol, (
                f"lattice[{i}][{j}]: {a[i][j]} != {b[i][j]}"
            )


def _assert_coords_equal(a: list, b: list, tol: float = 1e-10):
    """Assert two coordinate lists are element-wise equal."""
    assert len(a) == len(b), f"length mismatch: {len(a)} != {len(b)}"
    for i in range(len(a)):
        for j in range(3):
            assert abs(a[i][j] - b[i][j]) < tol, (
                f"coord[{i}][{j}]: {a[i][j]} != {b[i][j]}"
            )


def _assert_structure_equal(
    original: dict, recovered: dict, tol: float = 1e-10
):
    """Assert two StructureDoc dicts are semantically equal."""
    _assert_lattice_equal(original["lattice"], recovered["lattice"], tol)
    assert original["species"] == recovered["species"]
    _assert_coords_equal(original["frac_coords"], recovered["frac_coords"], tol)


def _assert_kpoints_equal(original: dict, recovered: dict, tol: float = 1e-6):
    """Assert two KpointsSpec dicts are semantically equal."""
    assert original["mode"] == recovered["mode"]

    if original["mode"] == "automatic":
        assert original["mesh"] == recovered["mesh"]
        for i in range(3):
            assert abs(original["shift"][i] - recovered["shift"][i]) < tol
        assert original.get("centering", "Gamma") == recovered.get("centering", "Gamma")

    elif original["mode"] == "line":
        assert original["npoints"] == recovered["npoints"]
        assert len(original["path"]) == len(recovered["path"])
        for orig_seg, rec_seg in zip(original["path"], recovered["path"]):
            for j in range(3):
                assert abs(orig_seg["start"][j] - rec_seg["start"][j]) < tol
                assert abs(orig_seg["end"][j] - rec_seg["end"][j]) < tol
            assert orig_seg.get("start_label", "") == rec_seg.get("start_label", "")
            assert orig_seg.get("end_label", "") == rec_seg.get("end_label", "")

    elif original["mode"] == "explicit":
        assert len(original["kpoints"]) == len(recovered["kpoints"])
        for orig_kpt, rec_kpt in zip(original["kpoints"], recovered["kpoints"]):
            for j in range(len(orig_kpt)):
                assert abs(orig_kpt[j] - rec_kpt[j]) < tol


# ══════════════════════════════════════════════════════════════════════════
# POSCAR roundtrip tests
# ══════════════════════════════════════════════════════════════════════════


class TestPOSCARRoundtrip:
    """Primary semantic loop: dict -> write -> parse -> dict."""

    def test_si_diamond_roundtrip(self):
        """Si diamond cubic — simplest case."""
        text = write_poscar_text(SI_DIAMOND_STRUCTURE)
        recovered = parse_poscar_text(text)
        _assert_structure_equal(SI_DIAMOND_STRUCTURE, recovered)

    def test_si_fcc_roundtrip(self):
        """Si FCC primitive cell — non-orthogonal lattice."""
        text = write_poscar_text(SI_FCC_STRUCTURE)
        recovered = parse_poscar_text(text)
        _assert_structure_equal(SI_FCC_STRUCTURE, recovered)

    def test_nacl_multi_species_roundtrip(self):
        """NaCl rocksalt — multi-species, atoms reordered by species."""
        text = write_poscar_text(NACL_STRUCTURE)
        recovered = parse_poscar_text(text)
        _assert_structure_equal(NACL_STRUCTURE, recovered)

    def test_comment_preserved_in_dict(self):
        """Comment is carried through as dict field (not in file formatting)."""
        text = write_poscar_text(SI_DIAMOND_STRUCTURE)
        recovered = parse_poscar_text(text)
        assert recovered["comment"] == "Si diamond"

    def test_writer_always_produces_direct_coords(self):
        """Writer output should contain 'Direct' coordinate keyword."""
        text = write_poscar_text(SI_DIAMOND_STRUCTURE)
        lines = text.strip().splitlines()
        # Find coordinate type line (after species/counts)
        assert any(l.strip() == "Direct" for l in lines)


class TestPOSCARParseCuratedSample:
    """Parse the curated sample and verify structure recovery."""

    def test_parse_curated_poscar(self):
        """Parse tests/inputformat/samples/vasp/si_scf_POSCAR."""
        text = (SAMPLES_DIR / "si_scf_POSCAR").read_text()
        result = parse_poscar_text(text)

        assert result["species"] == ["Si", "Si"]
        assert len(result["frac_coords"]) == 2
        _assert_lattice_equal(
            result["lattice"],
            [[5.4309, 0.0, 0.0], [0.0, 5.4309, 0.0], [0.0, 0.0, 5.4309]],
        )
        _assert_coords_equal(
            result["frac_coords"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        )

    def test_curated_poscar_roundtrip(self):
        """Parse curated sample -> write -> parse -> semantic equality."""
        original_text = (SAMPLES_DIR / "si_scf_POSCAR").read_text()
        parsed = parse_poscar_text(original_text)
        written = write_poscar_text(parsed)
        reparsed = parse_poscar_text(written)
        _assert_structure_equal(parsed, reparsed)


class TestPOSCARParseCartesian:
    """Parse POSCAR with Cartesian coordinates."""

    def test_cartesian_to_fractional(self):
        """Cartesian coordinates should be converted to fractional."""
        # Si diamond in Cartesian
        cartesian_poscar = """\
Si diamond cartesian
1.0
  5.4309000000000000  0.0000000000000000  0.0000000000000000
  0.0000000000000000  5.4309000000000000  0.0000000000000000
  0.0000000000000000  0.0000000000000000  5.4309000000000000
Si
2
Cartesian
  0.0000000000000000  0.0000000000000000  0.0000000000000000
  1.3577250000000000  1.3577250000000000  1.3577250000000000
"""
        result = parse_poscar_text(cartesian_poscar)
        _assert_coords_equal(
            result["frac_coords"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
            tol=1e-8,
        )


class TestPOSCARParseScaleFactor:
    """Parse POSCAR with non-unity scale factor."""

    def test_scale_factor_applied_to_lattice(self):
        """Scale factor multiplies lattice vectors."""
        scaled_poscar = """\
Si scaled
2.0
  2.7154500000000000  0.0000000000000000  0.0000000000000000
  0.0000000000000000  2.7154500000000000  0.0000000000000000
  0.0000000000000000  0.0000000000000000  2.7154500000000000
Si
2
Direct
  0.0  0.0  0.0
  0.25 0.25 0.25
"""
        result = parse_poscar_text(scaled_poscar)
        _assert_lattice_equal(
            result["lattice"],
            [[5.4309, 0.0, 0.0], [0.0, 5.4309, 0.0], [0.0, 0.0, 5.4309]],
            tol=1e-6,
        )


# ══════════════════════════════════════════════════════════════════════════
# KPOINTS roundtrip tests
# ══════════════════════════════════════════════════════════════════════════


class TestKPOINTSRoundtrip:
    """Primary semantic loop: dict -> write -> parse -> dict."""

    def test_automatic_gamma_roundtrip(self):
        text = write_kpoints_text(KPOINTS_AUTO_GAMMA)
        recovered = parse_kpoints_text(text)
        _assert_kpoints_equal(KPOINTS_AUTO_GAMMA, recovered)

    def test_automatic_mp_roundtrip(self):
        text = write_kpoints_text(KPOINTS_AUTO_MP)
        recovered = parse_kpoints_text(text)
        _assert_kpoints_equal(KPOINTS_AUTO_MP, recovered)

    def test_line_mode_roundtrip(self):
        text = write_kpoints_text(KPOINTS_LINE)
        recovered = parse_kpoints_text(text)
        _assert_kpoints_equal(KPOINTS_LINE, recovered)

    def test_explicit_roundtrip(self):
        text = write_kpoints_text(KPOINTS_EXPLICIT)
        recovered = parse_kpoints_text(text)
        _assert_kpoints_equal(KPOINTS_EXPLICIT, recovered)


class TestKPOINTSParseCuratedSample:
    """Parse the curated sample and verify kpoints recovery."""

    def test_parse_curated_kpoints(self):
        text = (SAMPLES_DIR / "si_scf_KPOINTS").read_text()
        result = parse_kpoints_text(text)

        assert result["mode"] == "automatic"
        assert result["mesh"] == [4, 4, 4]
        assert result["centering"] == "Gamma"

    def test_curated_kpoints_roundtrip(self):
        original_text = (SAMPLES_DIR / "si_scf_KPOINTS").read_text()
        parsed = parse_kpoints_text(original_text)
        written = write_kpoints_text(parsed)
        reparsed = parse_kpoints_text(written)
        _assert_kpoints_equal(parsed, reparsed)


# ══════════════════════════════════════════════════════════════════════════
# Combined VASP input roundtrip (POSCAR + KPOINTS together)
# ══════════════════════════════════════════════════════════════════════════


class TestVASPCombinedRoundtrip:
    """End-to-end: SSOT dicts -> write all files -> parse all files -> SSOT dicts."""

    def test_full_vasp_semantic_loop(self):
        """YAML(params+structure+kpoints) -> write -> parse -> YAML equality."""
        # SSOT inputs
        structure = SI_DIAMOND_STRUCTURE
        kpoints = KPOINTS_AUTO_GAMMA

        # Write
        poscar_text = write_poscar_text(structure)
        kpoints_text = write_kpoints_text(kpoints)

        # Parse
        recovered_structure = parse_poscar_text(poscar_text)
        recovered_kpoints = parse_kpoints_text(kpoints_text)

        # Semantic equality
        _assert_structure_equal(structure, recovered_structure)
        _assert_kpoints_equal(kpoints, recovered_kpoints)

    def test_full_vasp_with_line_kpoints(self):
        """Same loop with band-structure k-points."""
        structure = SI_FCC_STRUCTURE
        kpoints = KPOINTS_LINE

        poscar_text = write_poscar_text(structure)
        kpoints_text = write_kpoints_text(kpoints)

        recovered_structure = parse_poscar_text(poscar_text)
        recovered_kpoints = parse_kpoints_text(kpoints_text)

        _assert_structure_equal(structure, recovered_structure)
        _assert_kpoints_equal(kpoints, recovered_kpoints)


# ══════════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════════


class TestPOSCAREdgeCases:
    """Edge case handling."""

    def test_selective_dynamics_skipped(self):
        """Selective dynamics line is recognized and skipped."""
        sd_poscar = """\
Si with selective dynamics
1.0
  5.4309  0.0  0.0
  0.0  5.4309  0.0
  0.0  0.0  5.4309
Si
2
Selective dynamics
Direct
  0.0  0.0  0.0  T T T
  0.25 0.25 0.25  F F F
"""
        result = parse_poscar_text(sd_poscar)
        assert result["species"] == ["Si", "Si"]
        _assert_coords_equal(
            result["frac_coords"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
            tol=1e-8,
        )

    def test_poscar_too_short(self):
        """Raise ValueError for truncated POSCAR."""
        with pytest.raises(ValueError, match="too short"):
            parse_poscar_text("line1\nline2\n")


class TestKPOINTSEdgeCases:
    """Edge case handling."""

    def test_kpoints_too_short(self):
        """Raise ValueError for truncated KPOINTS."""
        with pytest.raises(ValueError, match="too short"):
            parse_kpoints_text("line1\n")

    def test_unknown_mode(self):
        """Raise ValueError for unknown KPOINTS mode in writer."""
        with pytest.raises(ValueError, match="Unknown KPOINTS mode"):
            write_kpoints_text({"mode": "invalid"})
