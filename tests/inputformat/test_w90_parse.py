"""Tests for Wannier90 .win input parser, writer, and roundtrip.

Wannier90 uses a flat-keyval format with begin/end blocks.
Single combined file (wannier90.win) contains parameters + structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.w90.inputspec import (
    _parse_win_text,
    _write_win_text,
    get_w90_input_spec,
)

SAMPLES_DIR = Path(__file__).parent / "samples" / "w90"
_BOHR_TO_ANG = 0.529177210903


# ──────────────────────────────────────────────────────────────────────────
# Parser unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestW90Parser:
    """Unit tests for _parse_win_text."""

    def test_empty_input(self):
        result = _parse_win_text("")
        assert result["params"] == {}
        assert "structure" not in result

    def test_whitespace_only(self):
        result = _parse_win_text("   \n\n  \n")
        assert result["params"] == {}

    def test_comment_bang(self):
        result = _parse_win_text("! this is a comment\nnum_wann = 4\n")
        assert result["params"]["num_wann"] == 4

    def test_comment_hash(self):
        result = _parse_win_text("# this is a comment\nnum_wann = 4\n")
        assert result["params"]["num_wann"] == 4

    def test_inline_comment_bang(self):
        result = _parse_win_text("num_wann = 4 ! number of WFs\n")
        assert result["params"]["num_wann"] == 4

    def test_inline_comment_hash(self):
        result = _parse_win_text("berry_kmesh =  25 #100\n")
        assert result["params"]["berry_kmesh"] == 25

    def test_scalar_int(self):
        result = _parse_win_text("num_wann = 4\n")
        assert result["params"]["num_wann"] == 4
        assert isinstance(result["params"]["num_wann"], int)

    def test_scalar_float(self):
        result = _parse_win_text("dis_win_max = 38.0\n")
        assert result["params"]["dis_win_max"] == 38.0
        assert isinstance(result["params"]["dis_win_max"], float)

    def test_scalar_fortran_float_d(self):
        result = _parse_win_text("dis_mix_ratio = 1.0d0\n")
        assert result["params"]["dis_mix_ratio"] == 1.0

    def test_scalar_fortran_float_negative_exp(self):
        result = _parse_win_text("dis_conv_tol = 1.0d-10\n")
        assert abs(result["params"]["dis_conv_tol"] - 1.0e-10) < 1e-20

    def test_scalar_fortran_float_e0(self):
        """Fortran-style e0 notation like -3.703863220455861e0."""
        result = _parse_win_text("some_val = -3.703863220455861e0\n")
        assert abs(result["params"]["some_val"] - (-3.703863220455861)) < 1e-12

    def test_scalar_bool_true_dot(self):
        result = _parse_win_text("wannier_plot = .true.\n")
        assert result["params"]["wannier_plot"] is True

    def test_scalar_bool_true_plain(self):
        result = _parse_win_text("spinors = true\n")
        assert result["params"]["spinors"] is True

    def test_scalar_bool_true_t(self):
        result = _parse_win_text("guiding_centres = T\n")
        assert result["params"]["guiding_centres"] is True

    def test_scalar_bool_false_dot(self):
        result = _parse_win_text("shc_freq_scan = .false.\n")
        assert result["params"]["shc_freq_scan"] is False

    def test_scalar_bool_false_plain(self):
        result = _parse_win_text("shc_freq_scan = false\n")
        assert result["params"]["shc_freq_scan"] is False

    def test_scalar_bool_false_f(self):
        result = _parse_win_text("shc_freq_scan = F\n")
        assert result["params"]["shc_freq_scan"] is False

    def test_scalar_string(self):
        result = _parse_win_text("berry_task = eval_shc\n")
        assert result["params"]["berry_task"] == "eval_shc"

    def test_mp_grid_equals(self):
        result = _parse_win_text("mp_grid = 4 4 4\n")
        assert result["params"]["mp_grid"] == [4, 4, 4]

    def test_mp_grid_colon(self):
        result = _parse_win_text("mp_grid : 4 4 4\n")
        assert result["params"]["mp_grid"] == [4, 4, 4]

    def test_mp_grid_asymmetric(self):
        result = _parse_win_text("mp_grid = 8 8 8\n")
        assert result["params"]["mp_grid"] == [8, 8, 8]

    def test_key_separator_equals(self):
        result = _parse_win_text("num_wann = 4\n")
        assert result["params"]["num_wann"] == 4

    def test_key_separator_colon(self):
        result = _parse_win_text("mp_grid : 2 2 2\n")
        assert result["params"]["mp_grid"] == [2, 2, 2]

    def test_key_separator_space(self):
        result = _parse_win_text("num_wann 4\n")
        assert result["params"]["num_wann"] == 4

    def test_key_separator_no_space(self):
        result = _parse_win_text("wvfn_formatted=.true.\n")
        assert result["params"]["wvfn_formatted"] is True

    def test_case_insensitive_keys(self):
        result = _parse_win_text("Num_Wann = 4\nNUM_ITER = 20\n")
        assert result["params"]["num_wann"] == 4
        assert result["params"]["num_iter"] == 20

    def test_unit_cell_cart_bohr(self):
        text = """\
begin unit_cell_cart
bohr
-5.367  0.000  5.367
 0.000  5.367  5.367
-5.367  5.367  0.000
end unit_cell_cart
"""
        result = _parse_win_text(text)
        lattice = result["structure"]["lattice"]
        assert len(lattice) == 3
        # Bohr should be converted to angstrom
        assert abs(lattice[0][0] - (-5.367 * _BOHR_TO_ANG)) < 1e-6
        assert abs(lattice[1][1] - (5.367 * _BOHR_TO_ANG)) < 1e-6
        assert result["structure"]["lattice_units"] == "bohr"

    def test_unit_cell_cart_ang(self):
        text = """\
begin unit_cell_cart
ang
-1.614  0.000  1.614
 0.000  1.614  1.614
-1.614  1.614  0.000
end unit_cell_cart
"""
        result = _parse_win_text(text)
        lattice = result["structure"]["lattice"]
        # Angstrom: no conversion
        assert abs(lattice[0][0] - (-1.614)) < 1e-6

    def test_unit_cell_cart_no_units(self):
        """No units line means angstrom by default."""
        text = """\
begin unit_cell_cart
-1.613990   0.000000   1.613990
 0.000000   1.613990   1.613990
-1.613990   1.613990   0.000000
end unit_cell_cart
"""
        result = _parse_win_text(text)
        lattice = result["structure"]["lattice"]
        assert abs(lattice[0][0] - (-1.613990)) < 1e-6

    def test_atoms_frac(self):
        text = """\
begin atoms_frac
Ga 0.00   0.00   0.00
As 0.25  0.25  0.25
end atoms_frac
"""
        result = _parse_win_text(text)
        assert result["structure"]["species"] == ["Ga", "As"]
        assert len(result["structure"]["frac_coords"]) == 2
        assert result["structure"]["frac_coords"][0] == [0.0, 0.0, 0.0]
        assert result["structure"]["frac_coords"][1] == [0.25, 0.25, 0.25]

    def test_atoms_cart_ang(self):
        text = """\
begin atoms_cart
ang
Si  0.000  0.000  0.000
Si  1.357  1.357  1.357
end atoms_cart
"""
        result = _parse_win_text(text)
        assert result["structure"]["species"] == ["Si", "Si"]
        assert "cart_coords" in result["structure"]
        assert result["structure"]["cart_coords"][1] == [1.357, 1.357, 1.357]

    def test_atoms_cart_bohr_conversion(self):
        text = """\
begin atoms_cart
bohr
Si  0.000  0.000  0.000
Si  2.565  2.565  2.565
end atoms_cart
"""
        result = _parse_win_text(text)
        coords = result["structure"]["cart_coords"]
        assert abs(coords[1][0] - 2.565 * _BOHR_TO_ANG) < 1e-6

    def test_projections_block(self):
        text = """\
begin projections
As:sp3
end projections
"""
        result = _parse_win_text(text)
        assert result["params"]["projections"] == ["As:sp3"]

    def test_projections_multi(self):
        text = """\
begin projections
Cu:d
f=0.25,0.25,0.25:s
f=-0.25,-0.25,-0.25:s
end projections
"""
        result = _parse_win_text(text)
        assert len(result["params"]["projections"]) == 3
        assert result["params"]["projections"][0] == "Cu:d"
        assert result["params"]["projections"][1] == "f=0.25,0.25,0.25:s"

    def test_projections_complex(self):
        text = """\
begin projections
Fe: sp3d2;dxy;dxz;dyz
end projections
"""
        result = _parse_win_text(text)
        assert result["params"]["projections"] == ["Fe: sp3d2;dxy;dxz;dyz"]

    def test_kpoints_no_weights(self):
        text = """\
begin kpoints
0.0 0.0 0.0
0.0 0.0 0.5
0.5 0.5 0.0
end kpoints
"""
        result = _parse_win_text(text)
        kp = result["params"]["kpoints"]
        assert len(kp["points"]) == 3
        assert kp["points"][0] == [0.0, 0.0, 0.0]
        assert kp["points"][2] == [0.5, 0.5, 0.0]
        assert "weights" not in kp

    def test_kpoints_with_weights(self):
        text = """\
begin kpoints
  0.00000000  0.00000000  0.00000000  1.953125e-03
  0.00000000  0.00000000  0.12500000  1.953125e-03
end kpoints
"""
        result = _parse_win_text(text)
        kp = result["params"]["kpoints"]
        assert len(kp["points"]) == 2
        assert "weights" in kp
        assert len(kp["weights"]) == 2
        assert abs(kp["weights"][0] - 1.953125e-03) < 1e-10

    def test_kpoint_path(self):
        text = """\
begin kpoint_path
G 0.00  0.00  0.00    X 0.50  0.50  0.00
X 0.50  0.50  0.00    W 0.50  0.75  0.25
end kpoint_path
"""
        result = _parse_win_text(text)
        path = result["params"]["kpoint_path"]
        assert len(path) == 2
        assert path[0]["start_label"] == "G"
        assert path[0]["start"] == [0.0, 0.0, 0.0]
        assert path[0]["end_label"] == "X"
        assert path[0]["end"] == [0.5, 0.5, 0.0]
        assert path[1]["start_label"] == "X"
        assert path[1]["end_label"] == "W"

    def test_exclude_bands_ranges(self):
        text = """\
begin exclude_bands
1-4, 6, 8-10
end exclude_bands
"""
        result = _parse_win_text(text)
        bands = result["params"]["exclude_bands"]
        assert bands == [1, 2, 3, 4, 6, 8, 9, 10]

    def test_exclude_bands_single(self):
        text = """\
begin exclude_bands
5
end exclude_bands
"""
        result = _parse_win_text(text)
        assert result["params"]["exclude_bands"] == [5]

    def test_unknown_key_diagnostic(self):
        result = _parse_win_text("totally_unknown_key = 42\n")
        assert result["params"]["totally_unknown_key"] == 42
        assert len(result.get("diagnostics", [])) >= 1
        diag = result["diagnostics"][0]
        assert diag["code"] == "unknown_parameter"
        assert "totally_unknown_key" in diag["message"]

    def test_unknown_block_diagnostic(self):
        text = """\
begin totally_unknown_block
some data
end totally_unknown_block
"""
        result = _parse_win_text(text)
        assert len(result.get("diagnostics", [])) >= 1
        diag = result["diagnostics"][0]
        assert diag["code"] == "unknown_block"

    def test_case_insensitive_blocks(self):
        text = """\
BEGIN Unit_Cell_Cart
ang
1.0 0.0 0.0
0.0 1.0 0.0
0.0 0.0 1.0
END Unit_Cell_Cart
"""
        result = _parse_win_text(text)
        assert "lattice" in result["structure"]
        assert len(result["structure"]["lattice"]) == 3

    def test_known_block_stored_raw(self):
        """Known blocks without special parsing (nnkpts, dis_spheres) stored as raw lines."""
        text = """\
begin nnkpts
1 2 0 0 0
2 1 0 0 0
end nnkpts
"""
        result = _parse_win_text(text)
        assert "nnkpts" in result["params"]
        assert isinstance(result["params"]["nnkpts"], list)
        assert len(result["params"]["nnkpts"]) == 2

    def test_negative_coordinates(self):
        text = """\
begin atoms_frac
C   -0.12500  -0.1250    -0.125000
C    0.12500   0.1250     0.125000
end atoms_frac
"""
        result = _parse_win_text(text)
        assert result["structure"]["frac_coords"][0] == [-0.125, -0.125, -0.125]
        assert result["structure"]["frac_coords"][1] == [0.125, 0.125, 0.125]


# ──────────────────────────────────────────────────────────────────────────
# Writer unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestW90Writer:
    """Unit tests for _write_win_text."""

    def test_write_empty(self):
        result = _write_win_text({})
        assert result.strip() == ""

    def test_write_empty_params(self):
        result = _write_win_text({"params": {}})
        assert result.strip() == ""

    def test_write_scalar_int(self):
        text = _write_win_text({"params": {"num_wann": 4}})
        assert "num_wann = 4" in text

    def test_write_scalar_float(self):
        text = _write_win_text({"params": {"dis_win_max": 38.0}})
        assert "dis_win_max = 38" in text

    def test_write_bool_true(self):
        text = _write_win_text({"params": {"spinors": True}})
        assert "spinors = .true." in text

    def test_write_bool_false(self):
        text = _write_win_text({"params": {"shc_freq_scan": False}})
        assert "shc_freq_scan = .false." in text

    def test_write_mp_grid(self):
        text = _write_win_text({"params": {"mp_grid": [4, 4, 4]}})
        assert "mp_grid = 4 4 4" in text

    def test_write_structure_lattice(self):
        text = _write_win_text({
            "structure": {
                "lattice": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            },
        })
        assert "begin unit_cell_cart" in text
        assert "ang" in text
        assert "end unit_cell_cart" in text

    def test_write_structure_atoms_frac(self):
        text = _write_win_text({
            "structure": {
                "species": ["Ga", "As"],
                "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
            },
        })
        assert "begin atoms_frac" in text
        assert "Ga" in text
        assert "As" in text
        assert "end atoms_frac" in text

    def test_write_structure_atoms_cart(self):
        text = _write_win_text({
            "structure": {
                "species": ["Si", "Si"],
                "cart_coords": [[0.0, 0.0, 0.0], [1.357, 1.357, 1.357]],
            },
        })
        assert "begin atoms_cart" in text
        assert "ang" in text
        assert "end atoms_cart" in text

    def test_write_projections(self):
        text = _write_win_text({"params": {"projections": ["As:sp3"]}})
        assert "begin projections" in text
        assert "As:sp3" in text
        assert "end projections" in text

    def test_write_kpoint_path(self):
        text = _write_win_text({
            "params": {
                "kpoint_path": [
                    {"start_label": "G", "start": [0.0, 0.0, 0.0],
                     "end_label": "X", "end": [0.5, 0.5, 0.0]},
                ],
            },
        })
        assert "begin kpoint_path" in text
        assert "G" in text
        assert "X" in text
        assert "end kpoint_path" in text

    def test_write_exclude_bands(self):
        text = _write_win_text({"params": {"exclude_bands": [1, 2, 3, 4, 6]}})
        assert "begin exclude_bands" in text
        assert "1, 2, 3, 4, 6" in text
        assert "end exclude_bands" in text

    def test_write_kpoints(self):
        text = _write_win_text({
            "params": {
                "kpoints": {
                    "points": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]],
                },
            },
        })
        assert "begin kpoints" in text
        assert "end kpoints" in text

    def test_write_kpoints_with_weights(self):
        text = _write_win_text({
            "params": {
                "kpoints": {
                    "points": [[0.0, 0.0, 0.0]],
                    "weights": [0.125],
                },
            },
        })
        assert "begin kpoints" in text
        # Weight should appear on the kpoint line
        lines = text.strip().splitlines()
        kpoint_lines = [l for l in lines if "0.0000000000" in l]
        assert len(kpoint_lines) == 1
        parts = kpoint_lines[0].split()
        assert len(parts) >= 4  # x y z weight

    def test_write_scalars_sorted(self):
        text = _write_win_text({"params": {"num_wann": 4, "dis_win_max": 38.0, "berry": True}})
        lines = text.strip().splitlines()
        scalar_lines = [l for l in lines if "=" in l]
        keys = [l.split("=")[0].strip() for l in scalar_lines]
        assert keys == sorted(keys)


# ──────────────────────────────────────────────────────────────────────────
# Curated sample tests
# ──────────────────────────────────────────────────────────────────────────


class TestW90CuratedSamples:
    """Parse all 5 curated samples and verify key fields."""

    @pytest.mark.parametrize("case_id", [
        "gaas_basic", "copper_disentangle", "diamond_pipeline",
        "iron_spinor", "pt_shc",
    ])
    def test_sample_parses_without_error(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        result = _parse_win_text(text)
        assert "params" in result
        assert len(result["params"]) > 0

    def test_gaas_basic_fields(self):
        text = (SAMPLES_DIR / "gaas_basic" / "wannier90.win").read_text()
        result = _parse_win_text(text)
        p = result["params"]
        s = result["structure"]
        assert p["num_wann"] == 4
        assert p["num_iter"] == 20
        assert p["mp_grid"] == [2, 2, 2]
        assert p["wvfn_formatted"] is True
        assert p["projections"] == ["As:sp3"]
        assert len(p["kpoints"]["points"]) == 8
        assert s["species"] == ["Ga", "As"]
        assert len(s["frac_coords"]) == 2
        assert len(s["lattice"]) == 3
        # Bohr → Ang conversion
        assert abs(s["lattice"][0][0] - (-5.367 * _BOHR_TO_ANG)) < 1e-4

    def test_copper_disentangle_fields(self):
        text = (SAMPLES_DIR / "copper_disentangle" / "wannier90.win").read_text()
        result = _parse_win_text(text)
        p = result["params"]
        assert p["num_bands"] == 12
        assert p["num_wann"] == 7
        assert p["dis_win_max"] == 38.0
        assert p["dis_froz_max"] == 13.0
        assert p["dis_num_iter"] == 60
        assert p["dis_mix_ratio"] == 1.0  # Fortran 1.0d0
        assert p["mp_grid"] == [4, 4, 4]
        assert len(p["projections"]) == 3
        assert len(p["kpoint_path"]) == 5
        assert p["kpoint_path"][0]["start_label"] == "G"
        assert p["kpoint_path"][0]["end_label"] == "X"
        assert result["structure"]["species"] == ["Cu"]

    def test_diamond_pipeline_fields(self):
        text = (SAMPLES_DIR / "diamond_pipeline" / "wannier90.win").read_text()
        result = _parse_win_text(text)
        p = result["params"]
        s = result["structure"]
        assert p["num_wann"] == 4
        assert p["wannier_plot"] is True
        assert p["wannier_plot_supercell"] == 3
        assert p["mp_grid"] == [4, 4, 4]
        assert s["species"] == ["C", "C"]
        assert s["frac_coords"][0] == [-0.125, -0.125, -0.125]
        # No bohr header → angstrom, no conversion
        assert abs(s["lattice"][0][0] - (-1.613990)) < 1e-6

    def test_iron_spinor_fields(self):
        text = (SAMPLES_DIR / "iron_spinor" / "wannier90.win").read_text()
        result = _parse_win_text(text)
        p = result["params"]
        assert p["num_bands"] == 28
        assert p["num_wann"] == 18
        assert p["spinors"] is True
        assert p["kpath"] is True
        assert p["kpath_task"] == "bands"
        assert p["kpath_num_points"] == 500
        assert p["dis_win_min"] == -8.0  # Fortran -8.0d0
        assert p["dis_win_max"] == 70.0
        assert p["mp_grid"] == [8, 8, 8]
        assert len(p["kpoint_path"]) == 9
        # Kpoints with weights
        kp = p["kpoints"]
        assert len(kp["points"]) == 4
        assert "weights" in kp
        assert result["structure"]["species"] == ["Fe"]
        # Bohr conversion
        assert abs(result["structure"]["lattice"][0][0] - 2.71175 * _BOHR_TO_ANG) < 1e-4

    def test_pt_shc_fields(self):
        text = (SAMPLES_DIR / "pt_shc" / "wannier90.win").read_text()
        result = _parse_win_text(text)
        p = result["params"]
        assert p["shc_freq_scan"] is False
        assert p["shc_alpha"] == 1
        assert p["berry"] is True
        assert p["berry_task"] == "eval_shc"
        assert p["berry_kmesh"] == 25  # Comment after value stripped
        assert p["spinors"] is True
        assert p["guiding_centres"] is True  # T format
        assert p["num_bands"] == 40
        assert p["num_wann"] == 18
        assert p["dis_conv_tol"] == 1.0e-10
        assert p["conv_tol"] == 1.0e-10
        assert p["mp_grid"] == [10, 10, 10]
        assert len(p["kpoint_path"]) == 5
        assert p["kpoint_path"][0]["start_label"] == "W"
        assert p["projections"] == ["Pt: d;s;p"]
        assert result["structure"]["species"] == ["Pt"]


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip tests: parse -> write -> parse -> compare
# ──────────────────────────────────────────────────────────────────────────


class TestW90Roundtrip:
    """Semantic roundtrip: parse .win text → write → parse again → compare."""

    @pytest.mark.parametrize("case_id", [
        "gaas_basic", "copper_disentangle", "diamond_pipeline",
        "iron_spinor", "pt_shc",
    ])
    def test_roundtrip_params_preserved(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        parsed1 = _parse_win_text(text)

        # Write from parsed result
        fragment = {"params": parsed1["params"]}
        if "structure" in parsed1:
            fragment["structure"] = parsed1["structure"]
        written = _write_win_text(fragment)

        # Parse the written text
        parsed2 = _parse_win_text(written)

        # Compare scalar params
        skip_keys = {"kpoints", "kpoint_path", "projections", "exclude_bands",
                     "nnkpts", "dis_spheres", "slwf_centres"}
        for key, val in parsed1["params"].items():
            if key in skip_keys:
                continue
            if isinstance(val, (list, tuple, dict)):
                continue
            assert key in parsed2["params"], f"Missing key {key} in roundtrip for {case_id}"
            v2 = parsed2["params"][key]
            if isinstance(val, float):
                assert abs(val - v2) < 1e-6, f"Float mismatch for {key}: {val} vs {v2}"
            else:
                assert val == v2, f"Mismatch for {key}: {val} vs {v2}"

    @pytest.mark.parametrize("case_id", [
        "gaas_basic", "copper_disentangle", "diamond_pipeline",
        "iron_spinor", "pt_shc",
    ])
    def test_roundtrip_structure_preserved(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        parsed1 = _parse_win_text(text)
        if "structure" not in parsed1:
            pytest.skip("No structure in this sample")

        fragment = {"params": parsed1["params"], "structure": parsed1["structure"]}
        written = _write_win_text(fragment)
        parsed2 = _parse_win_text(written)

        s1 = parsed1["structure"]
        s2 = parsed2["structure"]

        # Species
        assert s1.get("species") == s2.get("species")

        # Coordinates (tolerance for float formatting)
        coord_key = "frac_coords" if "frac_coords" in s1 else "cart_coords"
        if coord_key in s1:
            assert len(s1[coord_key]) == len(s2[coord_key])
            for c1, c2 in zip(s1[coord_key], s2[coord_key]):
                for a, b in zip(c1, c2):
                    assert abs(a - b) < 1e-6

        # Lattice (writer always outputs ang; parser converts bohr → ang)
        if "lattice" in s1:
            for row1, row2 in zip(s1["lattice"], s2["lattice"]):
                for a, b in zip(row1, row2):
                    assert abs(a - b) < 1e-6

    @pytest.mark.parametrize("case_id", [
        "copper_disentangle", "iron_spinor", "pt_shc",
    ])
    def test_roundtrip_kpoint_path_preserved(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        parsed1 = _parse_win_text(text)
        if "kpoint_path" not in parsed1["params"]:
            pytest.skip("No kpoint_path")

        fragment = {"params": parsed1["params"]}
        if "structure" in parsed1:
            fragment["structure"] = parsed1["structure"]
        written = _write_win_text(fragment)
        parsed2 = _parse_win_text(written)

        path1 = parsed1["params"]["kpoint_path"]
        path2 = parsed2["params"]["kpoint_path"]
        assert len(path1) == len(path2)
        for seg1, seg2 in zip(path1, path2):
            assert seg1["start_label"] == seg2["start_label"]
            assert seg1["end_label"] == seg2["end_label"]
            for a, b in zip(seg1["start"], seg2["start"]):
                assert abs(a - b) < 1e-4
            for a, b in zip(seg1["end"], seg2["end"]):
                assert abs(a - b) < 1e-4

    @pytest.mark.parametrize("case_id", [
        "gaas_basic", "copper_disentangle", "diamond_pipeline",
        "iron_spinor", "pt_shc",
    ])
    def test_roundtrip_projections_preserved(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        parsed1 = _parse_win_text(text)
        if "projections" not in parsed1["params"]:
            pytest.skip("No projections")

        fragment = {"params": parsed1["params"]}
        if "structure" in parsed1:
            fragment["structure"] = parsed1["structure"]
        written = _write_win_text(fragment)
        parsed2 = _parse_win_text(written)

        # Projections preserved verbatim (modulo whitespace)
        p1 = [p.strip() for p in parsed1["params"]["projections"]]
        p2 = [p.strip() for p in parsed2["params"]["projections"]]
        assert p1 == p2

    @pytest.mark.parametrize("case_id", [
        "gaas_basic", "copper_disentangle", "diamond_pipeline",
        "iron_spinor", "pt_shc",
    ])
    def test_roundtrip_kpoints_preserved(self, case_id):
        text = (SAMPLES_DIR / case_id / "wannier90.win").read_text()
        parsed1 = _parse_win_text(text)
        if "kpoints" not in parsed1["params"]:
            pytest.skip("No kpoints")

        fragment = {"params": parsed1["params"]}
        if "structure" in parsed1:
            fragment["structure"] = parsed1["structure"]
        written = _write_win_text(fragment)
        parsed2 = _parse_win_text(written)

        kp1 = parsed1["params"]["kpoints"]
        kp2 = parsed2["params"]["kpoints"]
        assert len(kp1["points"]) == len(kp2["points"])
        for pt1, pt2 in zip(kp1["points"], kp2["points"]):
            for a, b in zip(pt1, pt2):
                assert abs(a - b) < 1e-6


# ──────────────────────────────────────────────────────────────────────────
# Orchestrator tests
# ──────────────────────────────────────────────────────────────────────────


class TestW90Orchestrator:
    """Test W90 through write_engine_inputs / parse_engine_inputs orchestrators."""

    def test_spec_structure(self):
        spec = get_w90_input_spec()
        assert spec.engine_family == "w90"
        assert spec.syntax_family == "flat-keyval"
        assert len(spec.input_files) == 1
        assert spec.input_files[0].filename == "wannier90.win"
        assert spec.input_files[0].content_role == "combined"

    def test_write_parse_basic(self, tmp_path):
        from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

        spec = get_w90_input_spec()
        params = {
            "num_wann": 4,
            "num_iter": 20,
            "mp_grid": [2, 2, 2],
            "projections": ["As:sp3"],
        }
        structure = {
            "lattice": [[-2.84, 0.0, 2.84], [0.0, 2.84, 2.84], [-2.84, 2.84, 0.0]],
            "species": ["Ga", "As"],
            "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=structure)
        assert (tmp_path / "wannier90.win").is_file()

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["num_wann"] == 4
        assert result.params["num_iter"] == 20
        assert result.params["mp_grid"] == [2, 2, 2]
        assert result.params["projections"] == ["As:sp3"]
        assert result.structure is not None
        assert result.structure["species"] == ["Ga", "As"]

    def test_write_parse_with_kpoint_path(self, tmp_path):
        from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

        spec = get_w90_input_spec()
        params = {
            "num_wann": 7,
            "kpoint_path": [
                {"start_label": "G", "start": [0.0, 0.0, 0.0],
                 "end_label": "X", "end": [0.5, 0.5, 0.0]},
            ],
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=None)
        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["num_wann"] == 7
        assert len(result.params["kpoint_path"]) == 1
        assert result.params["kpoint_path"][0]["start_label"] == "G"

    def test_parse_sample_dir(self, tmp_path):
        """Parse a sample .win file through the orchestrator."""
        import shutil
        from qmatsuite.inputformat import parse_engine_inputs

        src = SAMPLES_DIR / "gaas_basic" / "wannier90.win"
        shutil.copy(src, tmp_path / "wannier90.win")

        spec = get_w90_input_spec()
        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["num_wann"] == 4
        assert result.structure is not None
        assert result.structure["species"] == ["Ga", "As"]


# ──────────────────────────────────────────────────────────────────────────
# EngineInputSpec wiring tests
# ──────────────────────────────────────────────────────────────────────────


class TestW90InputSpec:
    """Verify that the W90 EngineInputSpec is properly wired."""

    def test_spec_has_parser_and_writer(self):
        spec = get_w90_input_spec()
        fspec = spec.input_files[0]
        assert fspec.custom_parser is not None
        assert fspec.custom_writer is not None

    def test_spec_resource_refs(self):
        spec = get_w90_input_spec()
        assert len(spec.resource_refs) == 1
        assert spec.resource_refs[0].name == "amn_mmn_eig"
        assert spec.resource_refs[0].staging_policy == "symlink"

    def test_spec_ssot_mapping(self):
        spec = get_w90_input_spec()
        assert "wannier90.win" in spec.ssot_mapping.params_in
        assert "wannier90.win" in spec.ssot_mapping.structure_in
        assert "wannier90.win" in spec.ssot_mapping.kpoints_in

    def test_driver_returns_spec(self):
        from qmatsuite.drivers.w90.driver import W90Driver
        driver = W90Driver()
        spec = driver.get_input_spec()
        assert spec is not None
        assert spec.engine_family == "w90"
