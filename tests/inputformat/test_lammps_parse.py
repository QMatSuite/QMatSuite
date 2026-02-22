"""Tests for LAMMPS input parser, writer, and roundtrip.

LAMMPS uses a command-stream syntax (F5): imperative, order-matters,
positional args. The parser produces a dual representation: flat semantic
fields for SSOT queries plus _commands list for faithful write-back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.lammps.inputspec import get_lammps_input_spec
from qmatsuite.drivers.lammps.io.data import (
    parse_lammps_data_text,
    write_lammps_data_text,
)
from qmatsuite.drivers.lammps.io.script import (
    join_continuation_lines,
    parse_lammps_script_text,
    write_lammps_script_text,
)

SAMPLES_DIR = Path(__file__).parent / "samples" / "lammps"


# ──────────────────────────────────────────────────────────────────────────
# Script parser unit tests
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSScriptParser:
    """Unit tests for parse_lammps_script_text."""

    def test_empty_input(self):
        result = parse_lammps_script_text("")
        assert result["_commands"] == []
        assert result["_variables"] == {}
        assert result["_includes"] == []

    def test_whitespace_only(self):
        result = parse_lammps_script_text("   \n\n  \n")
        assert result["_commands"] == []

    def test_comment_only(self):
        result = parse_lammps_script_text("# just a comment\n# another\n")
        assert result["_commands"] == []

    def test_units_extraction(self):
        result = parse_lammps_script_text("units lj\n")
        assert result["units"] == "lj"
        assert len(result["_commands"]) == 1
        assert result["_commands"][0]["cmd"] == "units"

    def test_atom_style_extraction(self):
        result = parse_lammps_script_text("atom_style full\n")
        assert result["atom_style"] == "full"

    def test_dimension_extraction(self):
        result = parse_lammps_script_text("dimension 2\n")
        assert result["dimension"] == 2
        assert isinstance(result["dimension"], int)

    def test_boundary_extraction(self):
        result = parse_lammps_script_text("boundary p p f\n")
        assert result["boundary"] == "p p f"

    def test_pair_style_extraction(self):
        result = parse_lammps_script_text("pair_style lj/cut 2.5\n")
        assert result["pair_style"] == "lj/cut 2.5"

    def test_pair_coeff_list(self):
        text = "pair_coeff 1 1 1.0 1.0 2.5\npair_coeff 2 2 0.5 0.5 2.5\n"
        result = parse_lammps_script_text(text)
        assert len(result["pair_coeff"]) == 2
        assert result["pair_coeff"][0] == "1 1 1.0 1.0 2.5"
        assert result["pair_coeff"][1] == "2 2 0.5 0.5 2.5"

    def test_mass_accumulation(self):
        text = "mass 1 1.0\nmass 2 28.0855\n"
        result = parse_lammps_script_text(text)
        assert len(result["masses"]) == 2
        assert "1 1.0" in result["masses"]

    def test_fix_extraction(self):
        text = "fix 1 all nve\nfix 2 mobile langevin 300 300 1.0 12345\n"
        result = parse_lammps_script_text(text)
        assert len(result["fixes"]) == 2
        assert result["fixes"][0] == {
            "fix_id": "1", "group": "all", "style": "nve", "args": "",
        }
        assert result["fixes"][1]["style"] == "langevin"
        assert "300" in result["fixes"][1]["args"]

    def test_unfix_removes_fix(self):
        text = "fix 1 all nve\nfix 2 all nvt temp 300 300 100\nunfix 1\n"
        result = parse_lammps_script_text(text)
        assert len(result["fixes"]) == 1
        assert result["fixes"][0]["fix_id"] == "2"

    def test_compute_extraction(self):
        text = "compute mytemp all temp\n"
        result = parse_lammps_script_text(text)
        assert len(result["computes"]) == 1
        assert result["computes"][0]["compute_id"] == "mytemp"
        assert result["computes"][0]["style"] == "temp"

    def test_uncompute_removes_compute(self):
        text = "compute c1 all temp\ncompute c2 all pe\nuncompute c1\n"
        result = parse_lammps_script_text(text)
        assert len(result["computes"]) == 1
        assert result["computes"][0]["compute_id"] == "c2"

    def test_thermo_number(self):
        result = parse_lammps_script_text("thermo 50\n")
        assert result["thermo"] == 50
        assert isinstance(result["thermo"], int)

    def test_timestep_float(self):
        result = parse_lammps_script_text("timestep 0.001\n")
        assert result["timestep"] == 0.001
        assert isinstance(result["timestep"], float)

    def test_run_extraction(self):
        result = parse_lammps_script_text("run 1000\n")
        assert result["run"] == 1000

    def test_minimize_extraction(self):
        result = parse_lammps_script_text("minimize 1.0e-6 0.001 1000 10000\n")
        assert result["minimize"] == "1.0e-6 0.001 1000 10000"

    def test_read_data_extraction(self):
        result = parse_lammps_script_text("read_data data.peptide\n")
        assert result["data_file"] == "data.peptide"

    def test_read_restart_extraction(self):
        result = parse_lammps_script_text("read_restart restart.equil\n")
        assert result["restart_file"] == "restart.equil"

    def test_kspace_style_extraction(self):
        result = parse_lammps_script_text("kspace_style pppm 0.0001\n")
        assert result["kspace_style"] == "pppm 0.0001"

    def test_special_bonds_extraction(self):
        result = parse_lammps_script_text("special_bonds charmm\n")
        assert result["special_bonds"] == "charmm"

    def test_variable_extraction(self):
        text = "variable T index 300\nvariable P equal 1.0\n"
        result = parse_lammps_script_text(text)
        assert result["_variables"]["T"] == "index 300"
        assert result["_variables"]["P"] == "equal 1.0"

    def test_include_extraction(self):
        text = "include init.mod\ninclude potential.mod\n"
        result = parse_lammps_script_text(text)
        assert result["_includes"] == ["init.mod", "potential.mod"]

    def test_comment_stripping(self):
        text = "units lj  # LJ units\npair_style lj/cut 2.5  # cutoff\n"
        result = parse_lammps_script_text(text)
        assert result["units"] == "lj"
        assert result["pair_style"] == "lj/cut 2.5"

    def test_commands_preserve_order(self):
        text = "units lj\natom_style atomic\npair_style lj/cut 2.5\nrun 100\n"
        result = parse_lammps_script_text(text)
        cmds = [c["cmd"] for c in result["_commands"]]
        assert cmds == ["units", "atom_style", "pair_style", "run"]

    def test_variable_references_preserved(self):
        text = "variable T index 300\nfix 1 all nvt temp ${T} ${T} 100\n"
        result = parse_lammps_script_text(text)
        assert "${T}" in result["fixes"][0]["args"]

    def test_bond_style_extraction(self):
        result = parse_lammps_script_text("bond_style harmonic\n")
        assert result["bond_style"] == "harmonic"

    def test_bond_coeff_list(self):
        text = "bond_coeff 1 63.014 0.0\nbond_coeff 2 25.724 0.0\n"
        result = parse_lammps_script_text(text)
        assert len(result["bond_coeff"]) == 2

    def test_min_style_extraction(self):
        result = parse_lammps_script_text("min_style cg\n")
        assert result["min_style"] == "cg"

    def test_run_last_wins(self):
        """Multiple run commands: last one wins for flat field."""
        text = "run 100\nrun 200\n"
        result = parse_lammps_script_text(text)
        assert result["run"] == 200
        # But both are in _commands
        run_cmds = [c for c in result["_commands"] if c["cmd"] == "run"]
        assert len(run_cmds) == 2


# ──────────────────────────────────────────────────────────────────────────
# Line continuation tests
# ──────────────────────────────────────────────────────────────────────────


class TestLineContinuation:
    """Tests for join_continuation_lines."""

    def test_no_continuation(self):
        text = "units lj\nrun 100\n"
        result = join_continuation_lines(text)
        assert result.strip() == text.strip()

    def test_simple_continuation(self):
        text = "thermo_style custom step temp &\n  epair etotal press\n"
        joined = join_continuation_lines(text)
        assert "&" not in joined
        assert "thermo_style custom step temp" in joined
        assert "epair etotal press" in joined

    def test_multi_line_continuation(self):
        text = "thermo_style custom step &\n  temp &\n  press\n"
        joined = join_continuation_lines(text)
        lines = joined.splitlines()
        assert len(lines) == 1
        assert "step" in lines[0]
        assert "temp" in lines[0]
        assert "press" in lines[0]

    def test_continuation_in_script_parsing(self):
        text = "thermo_style    custom step temp epair etotal press &\n                v_eb v_ea v_elp\n"
        result = parse_lammps_script_text(text)
        assert result["thermo_style"] == "custom step temp epair etotal press v_eb v_ea v_elp"

    def test_fix_with_continuation(self):
        text = "fix HL all hyper/local 3.2 0.3 0.4 400 &\n  10.0 200.0 4000.0\n"
        result = parse_lammps_script_text(text)
        assert len(result["fixes"]) == 1
        assert result["fixes"][0]["style"] == "hyper/local"
        assert "4000.0" in result["fixes"][0]["args"]


# ──────────────────────────────────────────────────────────────────────────
# Data file parser tests
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSDataParser:
    """Tests for parse_lammps_data_text."""

    MINIMAL_DATA = """\
# Simple test data

4 atoms
1 atom types
0.0 10.0 xlo xhi
0.0 10.0 ylo yhi
0.0 10.0 zlo zhi

Masses

1 26.98

Atoms

1 1 1.0 2.0 3.0
2 1 4.0 5.0 6.0
3 1 7.0 8.0 9.0
4 1 0.5 0.5 0.5
"""

    def test_empty_data(self):
        result = parse_lammps_data_text("")
        assert result == {}

    def test_header_parsing(self):
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        assert result["_n_types"] == 1
        assert len(result["species"]) == 4

    def test_box_bounds(self):
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        # Orthorhombic: 10x10x10
        assert result["lattice"] == [
            [10.0, 0.0, 0.0],
            [0.0, 10.0, 0.0],
            [0.0, 0.0, 10.0],
        ]

    def test_masses_extraction(self):
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        assert result["_masses"][1] == 26.98

    def test_atomic_style_coords(self):
        """5 columns = id type x y z (atomic style)."""
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        assert len(result["cart_coords"]) == 4
        assert result["cart_coords"][0] == [1.0, 2.0, 3.0]
        assert result["cart_coords"][3] == [0.5, 0.5, 0.5]

    def test_species_are_type_ids(self):
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        assert all(s == "1" for s in result["species"])

    def test_frac_coords_computed(self):
        result = parse_lammps_data_text(self.MINIMAL_DATA)
        assert len(result["frac_coords"]) == 4
        # For a 10x10x10 ortho box, frac = cart / 10
        for i in range(3):
            assert abs(result["frac_coords"][0][i] - result["cart_coords"][0][i] / 10.0) < 1e-10

    def test_charge_style_data(self):
        """6 columns = id type q x y z (charge style)."""
        text = """\
# Charge style

2 atoms
1 atom types
0.0 5.0 xlo xhi
0.0 5.0 ylo yhi
0.0 5.0 zlo zhi

Atoms

1 1 0.5 1.0 2.0 3.0
2 1 -0.5 4.0 5.0 1.0
"""
        result = parse_lammps_data_text(text)
        assert len(result["cart_coords"]) == 2
        assert result["cart_coords"][0] == [1.0, 2.0, 3.0]
        assert result["cart_coords"][1] == [4.0, 5.0, 1.0]

    def test_full_style_data(self):
        """7+ columns = id mol type q x y z (full style)."""
        text = """\
# Full style

2 atoms
2 atom types
0.0 10.0 xlo xhi
0.0 10.0 ylo yhi
0.0 10.0 zlo zhi

Atoms

1 1 1 -0.82 3.0 4.0 5.0
2 1 2 0.41 6.0 7.0 8.0
"""
        result = parse_lammps_data_text(text)
        assert len(result["cart_coords"]) == 2
        assert result["cart_coords"][0] == [3.0, 4.0, 5.0]
        # type column is the 3rd (index 2) in full style
        assert result["species"] == ["1", "2"]

    def test_triclinic_box(self):
        """Box with tilt factors."""
        text = """\
# Triclinic

2 atoms
1 atom types
0.0 10.0 xlo xhi
0.0 10.0 ylo yhi
0.0 10.0 zlo zhi
1.0 0.5 0.0 xy xz yz

Atoms

1 1 1.0 2.0 3.0
2 1 4.0 5.0 6.0
"""
        result = parse_lammps_data_text(text)
        assert result["lattice"] == [
            [10.0, 0.0, 0.0],
            [1.0, 10.0, 0.0],
            [0.5, 0.0, 10.0],
        ]


# ──────────────────────────────────────────────────────────────────────────
# Writer tests
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSWriter:
    """Tests for write_lammps_script_text and write_lammps_data_text."""

    def test_write_empty_params(self):
        assert write_lammps_script_text(None) == ""
        assert write_lammps_script_text({}) == ""

    def test_write_from_commands_mode(self):
        params = {
            "_commands": [
                {"cmd": "units", "args": ["lj"]},
                {"cmd": "pair_style", "args": ["lj/cut", "2.5"]},
                {"cmd": "run", "args": ["100"]},
            ],
        }
        text = write_lammps_script_text(params)
        assert "units" in text
        assert "lj/cut 2.5" in text
        assert "run" in text

    def test_write_from_flat_mode(self):
        params = {
            "units": "metal",
            "atom_style": "atomic",
            "pair_style": "eam",
            "thermo": 100,
            "run": 500,
        }
        text = write_lammps_script_text(params)
        assert "units           metal" in text
        assert "atom_style      atomic" in text
        assert "pair_style      eam" in text
        assert "thermo          100" in text
        assert "run             500" in text

    def test_write_flat_with_fixes(self):
        params = {
            "units": "lj",
            "fixes": [
                {"fix_id": "1", "group": "all", "style": "nve", "args": ""},
                {"fix_id": "2", "group": "all", "style": "langevin", "args": "1.0 1.0 0.1 12345"},
            ],
            "run": 100,
        }
        text = write_lammps_script_text(params)
        assert "fix             1 all nve" in text
        assert "fix             2 all langevin 1.0 1.0 0.1 12345" in text

    def test_write_data_empty(self):
        assert write_lammps_data_text(None) == ""
        assert write_lammps_data_text({}) == ""

    def test_write_data_basic(self):
        structure = {
            "lattice": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
            "species": ["1", "1"],
            "cart_coords": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
            "comment": "Test data",
        }
        text = write_lammps_data_text(structure)
        assert "2 atoms" in text
        assert "1 atom types" in text
        assert "xlo xhi" in text
        assert "Atoms" in text

    def test_write_data_triclinic(self):
        structure = {
            "lattice": [[10.0, 0.0, 0.0], [1.0, 10.0, 0.0], [0.5, 0.0, 10.0]],
            "species": ["1"],
            "cart_coords": [[1.0, 2.0, 3.0]],
        }
        text = write_lammps_data_text(structure)
        assert "xy xz yz" in text

    def test_write_data_frac_to_cart(self):
        """Writer should convert frac_coords to Cartesian using lattice."""
        structure = {
            "lattice": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
            "species": ["1"],
            "frac_coords": [[0.1, 0.2, 0.3]],
        }
        text = write_lammps_data_text(structure)
        assert "1.0000000000" in text
        assert "2.0000000000" in text
        assert "3.0000000000" in text


# ──────────────────────────────────────────────────────────────────────────
# Curated sample parsing tests
# ──────────────────────────────────────────────────────────────────────────


class TestCuratedSamples:
    """Parse all 8 curated samples and verify key fields."""

    @pytest.mark.parametrize("case_id", [
        "melt_lj_nve", "minimize_2d_lj", "peptide_nvt", "reaxff_rdx",
        "eam_hyper", "coreshell", "meam_sic", "elastic_sw",
    ])
    def test_sample_parses_without_error(self, case_id):
        text = (SAMPLES_DIR / case_id / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert "_commands" in result
        assert len(result["_commands"]) > 0

    def test_melt_lj_nve_fields(self):
        text = (SAMPLES_DIR / "melt_lj_nve" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "lj"
        assert result["atom_style"] == "atomic"
        assert result["pair_style"] == "lj/cut 2.5"
        assert result["run"] == 250
        assert result["thermo"] == 50
        assert len(result["fixes"]) == 1
        assert result["fixes"][0]["style"] == "nve"
        assert result["pair_coeff"] == ["1 1 1.0 1.0 2.5"]

    def test_minimize_2d_lj_fields(self):
        text = (SAMPLES_DIR / "minimize_2d_lj" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "lj"
        assert result["dimension"] == 2
        assert result["minimize"] == "1.0e-6 0.001 1000 10000"
        assert len(result["fixes"]) == 2  # nve + enforce2d

    def test_peptide_nvt_fields(self):
        text = (SAMPLES_DIR / "peptide_nvt" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "real"
        assert result["atom_style"] == "full"
        assert result["kspace_style"] == "pppm 0.0001"
        assert result["bond_style"] == "harmonic"
        assert result["dihedral_style"] == "charmm"
        assert result["data_file"] == "data.peptide"
        assert result["timestep"] == 2.0
        assert len(result["fixes"]) == 2  # nvt + shake

    def test_reaxff_rdx_fields(self):
        text = (SAMPLES_DIR / "reaxff_rdx" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "real"
        assert result["atom_style"] == "charge"
        assert "reaxff" in result["pair_style"]
        assert len(result["_variables"]) >= 3
        assert result["data_file"] == "data.rdx"

    def test_reaxff_rdx_line_continuation(self):
        """ReaxFF sample uses & continuation for thermo_style."""
        text = (SAMPLES_DIR / "reaxff_rdx" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert "v_eb" in result["thermo_style"]
        assert "v_elp" in result["thermo_style"]

    def test_eam_hyper_variables(self):
        text = (SAMPLES_DIR / "eam_hyper" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "metal"
        assert result["_variables"]["Tequil"] == "index 400.0"
        assert result["_variables"]["steps"] == "index 2000"
        assert "${Tequil}" in result["fixes"][1]["args"]

    def test_eam_hyper_line_continuation(self):
        """EAM hyper sample has fix with & continuation."""
        text = (SAMPLES_DIR / "eam_hyper" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        hl_fixes = [f for f in result["fixes"] if f["style"] == "hyper/local"]
        assert len(hl_fixes) == 1
        assert "4000.0" in hl_fixes[0]["args"]

    def test_coreshell_unfix(self):
        text = (SAMPLES_DIR / "coreshell" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        # thermoberendsen is unfixed; should not be in final fixes
        fix_ids = [f["fix_id"] for f in result["fixes"]]
        assert "thermoberendsen" not in fix_ids
        # nve should remain
        assert "nve" in fix_ids

    def test_coreshell_multi_run(self):
        """Coreshell has two run commands; last run = 1000."""
        text = (SAMPLES_DIR / "coreshell" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["run"] == 1000  # last run wins
        run_cmds = [c for c in result["_commands"] if c["cmd"] == "run"]
        assert len(run_cmds) == 2

    def test_meam_sic_fields(self):
        text = (SAMPLES_DIR / "meam_sic" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "metal"
        assert result["pair_style"] == "meam"
        assert result["data_file"] == "data.meam"
        assert result["timestep"] == 0.001

    def test_elastic_sw_includes(self):
        """elastic_sw sample does NOT have includes — uses inline variables."""
        text = (SAMPLES_DIR / "elastic_sw" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        assert result["units"] == "metal"
        assert "minimize" in result
        assert len(result["_variables"]) >= 6

    def test_elastic_sw_unfix(self):
        text = (SAMPLES_DIR / "elastic_sw" / "in.lammps").read_text()
        result = parse_lammps_script_text(text)
        fix_ids = [f["fix_id"] for f in result.get("fixes", [])]
        assert "3" not in fix_ids  # unfix 3 should remove it


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip tests: parse -> write -> parse
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSRoundtrip:
    """Roundtrip: parse text -> write from _commands -> parse again -> compare."""

    @pytest.mark.parametrize("case_id", [
        "melt_lj_nve", "minimize_2d_lj", "peptide_nvt", "meam_sic",
    ])
    def test_roundtrip_commands_preserved(self, case_id):
        """Parse sample -> write from commands -> parse again -> _commands match."""
        text = (SAMPLES_DIR / case_id / "in.lammps").read_text()
        parsed1 = parse_lammps_script_text(text)

        written = write_lammps_script_text(parsed1)
        parsed2 = parse_lammps_script_text(written)

        # _commands should have same length and same cmd sequence
        assert len(parsed2["_commands"]) == len(parsed1["_commands"])
        for c1, c2 in zip(parsed1["_commands"], parsed2["_commands"]):
            assert c1["cmd"] == c2["cmd"]
            assert c1["args"] == c2["args"]

    @pytest.mark.parametrize("case_id", [
        "melt_lj_nve", "minimize_2d_lj", "peptide_nvt", "meam_sic",
    ])
    def test_roundtrip_flat_fields_preserved(self, case_id):
        """Flat semantic fields survive roundtrip."""
        text = (SAMPLES_DIR / case_id / "in.lammps").read_text()
        parsed1 = parse_lammps_script_text(text)

        written = write_lammps_script_text(parsed1)
        parsed2 = parse_lammps_script_text(written)

        # Compare key flat fields
        for key in ("units", "atom_style", "pair_style", "thermo", "timestep"):
            if key in parsed1:
                assert parsed2.get(key) == parsed1[key], f"{key} mismatch in {case_id}"

    def test_data_roundtrip(self):
        """Write data file -> parse -> verify coords match."""
        structure = {
            "lattice": [[10.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 6.0]],
            "species": ["1", "2", "1"],
            "cart_coords": [[1.0, 2.0, 3.0], [4.0, 5.0, 1.0], [7.0, 3.0, 2.0]],
            "comment": "Test structure",
        }
        text = write_lammps_data_text(structure)
        parsed = parse_lammps_data_text(text)

        assert len(parsed["cart_coords"]) == 3
        for i in range(3):
            for j in range(3):
                assert abs(parsed["cart_coords"][i][j] - structure["cart_coords"][i][j]) < 1e-6


# ──────────────────────────────────────────────────────────────────────────
# Orchestrator tests
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSOrchestrator:
    """Test LAMMPS through write_engine_inputs / parse_engine_inputs orchestrators."""

    def test_spec_structure(self):
        spec = get_lammps_input_spec()
        assert spec.engine_family == "lammps"
        assert spec.syntax_family == "command-stream"
        assert len(spec.input_files) == 2
        assert spec.input_files[0].filename == "in.lammps"
        assert spec.input_files[1].filename == "structure.data"
        assert spec.input_files[1].optional is True

    def test_write_parse_script_only(self, tmp_path):
        """Write and parse a script-only case (no data file)."""
        from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

        spec = get_lammps_input_spec()
        params = {
            "units": "lj",
            "atom_style": "atomic",
            "pair_style": "lj/cut 2.5",
            "pair_coeff": ["1 1 1.0 1.0 2.5"],
            "fixes": [{"fix_id": "1", "group": "all", "style": "nve", "args": ""}],
            "thermo": 50,
            "run": 250,
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=None)
        assert (tmp_path / "in.lammps").is_file()
        # structure.data should not be written (no structure provided)

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["units"] == "lj"
        assert result.params["pair_style"] == "lj/cut 2.5"
        assert result.params["run"] == 250

    def test_write_parse_with_structure(self, tmp_path):
        """Write and parse with both script and data file."""
        from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

        spec = get_lammps_input_spec()
        params = {
            "units": "metal",
            "atom_style": "atomic",
            "pair_style": "eam",
            "thermo": 10,
            "run": 100,
        }
        structure = {
            "lattice": [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
            "species": ["1", "2"],
            "cart_coords": [[0.0, 0.0, 0.0], [2.5, 2.5, 2.5]],
            "comment": "Test BCC",
        }

        write_engine_inputs(spec, tmp_path, params=params, structure=structure)
        assert (tmp_path / "in.lammps").is_file()
        assert (tmp_path / "structure.data").is_file()

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["units"] == "metal"
        assert result.structure is not None
        assert len(result.structure["species"]) == 2

    def test_parse_missing_optional_data_file(self, tmp_path):
        """Parsing with missing optional structure.data should not error."""
        from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

        spec = get_lammps_input_spec()
        params = {"units": "lj", "run": 100}

        write_engine_inputs(spec, tmp_path, params=params, structure=None)
        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["units"] == "lj"
        assert result.structure is None


# ──────────────────────────────────────────────────────────────────────────
# EngineInputSpec wiring test
# ──────────────────────────────────────────────────────────────────────────


class TestLAMMPSInputSpec:
    """Verify that the LAMMPS EngineInputSpec is properly wired."""

    def test_spec_has_parsers(self):
        spec = get_lammps_input_spec()
        for fspec in spec.input_files:
            assert fspec.custom_parser is not None
            assert fspec.custom_writer is not None

    def test_spec_resource_refs(self):
        spec = get_lammps_input_spec()
        assert len(spec.resource_refs) == 1
        assert spec.resource_refs[0].name == "potentials"

    def test_spec_ssot_mapping(self):
        spec = get_lammps_input_spec()
        assert "in.lammps" in spec.ssot_mapping.params_in
        assert "structure.data" in spec.ssot_mapping.structure_in

    def test_driver_returns_spec(self):
        from qmatsuite.drivers.lammps.driver import LAMMPSDriver
        driver = LAMMPSDriver()
        spec = driver.get_input_spec()
        assert spec is not None
        assert spec.engine_family == "lammps"
