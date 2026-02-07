"""Tests for Gaussian input parser and write-parse roundtrip.

Gaussian uses keyword-block format (F4) with blank-line-delimited sections.
The writer produces Cartesian coords; the parser handles both Cartesian and
Z-matrix. Roundtrip tests compare Cartesian coordinates with tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.gaussian.inputspec import (
    _parse_gaussian_text,
    _parse_route_keywords,
    _write_gaussian_text,
    get_gaussian_input_spec,
)


SAMPLES_DIR = Path(__file__).parent / "samples" / "gaussian"


# ──────────────────────────────────────────────────────────────────────────
# Route keyword parser tests
# ──────────────────────────────────────────────────────────────────────────


class TestRouteKeywordParser:
    """Tests for _parse_route_keywords()."""

    def test_method_basis_combo(self):
        result = _parse_route_keywords("#p B3LYP/6-31G*")
        assert result["method"] == "B3LYP"
        assert result["basis"] == "6-31G*"

    def test_hf_sto3g(self):
        result = _parse_route_keywords("#p HF/STO-3G")
        assert result["method"] == "HF"
        assert result["basis"] == "STO-3G"

    def test_opt_keyword(self):
        result = _parse_route_keywords("#p HF/STO-3G Opt")
        assert result["gen_type"] == "relax"

    def test_opt_tight(self):
        result = _parse_route_keywords("#p HF/STO-3G Opt=(Tight)")
        assert result["gen_type"] == "relax"
        assert result["opt_tight"] is True

    def test_opt_with_maxcycles(self):
        result = _parse_route_keywords("#p HF/STO-3G Opt=(Tight,MaxCycles=100)")
        assert result["gen_type"] == "relax"
        assert result["opt_tight"] is True
        assert result["opt_maxcycles"] == "100"

    def test_freq_keyword(self):
        result = _parse_route_keywords("#p HF/STO-3G Freq")
        assert result["gen_type"] == "freq"

    def test_combined_opt_freq(self):
        result = _parse_route_keywords("#p HF/STO-3G Opt Freq")
        assert result["gen_type"] == "relax"
        assert result["freq"] is True

    def test_td_nstates(self):
        result = _parse_route_keywords("#p B3LYP/STO-3G TD=(NStates=3)")
        assert result["gen_type"] == "td"
        assert result["td_nstates"] == 3

    def test_scrf_smd_solvent(self):
        result = _parse_route_keywords("#p B3LYP/6-31G* SCRF=(SMD,Solvent=Water)")
        assert result["scrf_model"] == "SMD"
        assert result["scrf_solvent"] == "Water"

    def test_scan_keyword(self):
        result = _parse_route_keywords("#p HF/STO-3G Scan")
        assert result["gen_type"] == "scan"

    def test_nmr_keyword(self):
        result = _parse_route_keywords("#p B3LYP/6-31G* NMR")
        assert result["gen_type"] == "nmr"

    def test_uhf_method(self):
        result = _parse_route_keywords("#p UHF/6-31G*")
        assert result["method"] == "UHF"

    def test_mp2_method(self):
        result = _parse_route_keywords("#p MP2/STO-3G")
        assert result["method"] == "MP2"
        assert result["basis"] == "STO-3G"

    def test_verbosity_flags(self):
        """# #p #n #t should all parse the same."""
        for prefix in ("#", "#p", "#P", "#n", "#N", "#t", "#T"):
            result = _parse_route_keywords(f"{prefix} HF/STO-3G")
            assert result["method"] == "HF"

    def test_empirical_dispersion(self):
        result = _parse_route_keywords("#p B3LYP/6-31G* EmpiricalDispersion=GD3BJ")
        assert result["dispersion"] == "GD3BJ"

    def test_nosymm(self):
        result = _parse_route_keywords("#p HF/STO-3G NoSymm")
        assert result["nosymm"] is True

    def test_composite_method(self):
        result = _parse_route_keywords("#p G4")
        assert result["method"] == "G4"
        assert result["gen_type"] == "composite"

    def test_scf_options(self):
        result = _parse_route_keywords("#p HF/STO-3G SCF=(Tight,MaxCycle=128)")
        assert "scf_options" in result
        assert "Tight" in result["scf_options"]
        assert result["scf_maxcycle"] == "128"


# ──────────────────────────────────────────────────────────────────────────
# Full input parser tests
# ──────────────────────────────────────────────────────────────────────────


class TestGaussianParser:
    """Unit tests for _parse_gaussian_text."""

    def test_minimal_sp(self):
        text = "%mem=500MB\n%nproc=1\n#p HF/STO-3G\n\nTitle\n\n0 1\nH  0.0  0.0  0.0\n\n"
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["mem"] == "500MB"
        assert result["params"]["nproc"] == 1
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1
        assert result["params"]["title"] == "Title"
        assert result["structure"]["species"] == ["H"]

    def test_cartesian_geometry(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p HF/STO-3G\n\nTest\n\n0 1\n"
            "O    0.000000    0.000000    0.117499\n"
            "H    0.000000    0.756950   -0.469996\n"
            "H    0.000000   -0.756950   -0.469996\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["structure"]["species"] == ["O", "H", "H"]
        assert len(result["structure"]["cart_coords"]) == 3
        assert abs(result["structure"]["cart_coords"][0][2] - 0.117499) < 1e-6

    def test_zmatrix_geometry(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p HF/STO-3G\n\nZ-mat\n\n0 1\n"
            "O\n"
            "H  1  R1\n"
            "H  1  R1  2  A1\n\n"
            "R1=0.96\n"
            "A1=104.5\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["structure"]["species"] == ["O", "H", "H"]
        assert "zmatrix" in result["params"]
        zmat = result["params"]["zmatrix"]
        assert len(zmat) == 3
        assert zmat[1]["bond_atom"] == "1"
        assert zmat[1]["bond_length"] == "R1"
        # Z-matrix variables
        assert result["params"]["zmatrix_variables"]["R1"] == 0.96
        assert result["params"]["zmatrix_variables"]["A1"] == 104.5

    def test_zmatrix_scan_variables(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p HF/STO-3G Scan\n\nScan test\n\n0 1\n"
            "H\n"
            "C  1  R1\n"
            "N  2  R2  1  A1\n\n"
            "R1=1.07 5 0.05\n"
            "R2=1.16\n"
            "A1=180.0\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["gen_type"] == "scan"
        zvars = result["params"]["zmatrix_variables"]
        assert zvars["R1"] == 1.07
        assert zvars["R1_scan_steps"] == 5
        assert zvars["R1_scan_step_size"] == 0.05
        assert zvars["R2"] == 1.16
        assert zvars["A1"] == 180.0

    def test_link0_directives(self):
        text = (
            "%mem=2GB\n%nproc=4\n%chk=test.chk\n%oldchk=prev.chk\n"
            "#p HF/STO-3G\n\nTitle\n\n0 1\nH  0.0  0.0  0.0\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["mem"] == "2GB"
        assert result["params"]["nproc"] == 4
        assert result["params"]["chk_name"] == "test.chk"
        assert result["params"]["oldchk"] == "prev.chk"

    def test_link1_parsing(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p HF/STO-3G\n\nJob 1\n\n0 1\n"
            "H  0.0  0.0  0.0\n\n"
            "--Link1--\n"
            "%mem=500MB\n%nproc=1\n#p MP2/STO-3G Geom=AllCheck\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["link1_jobs"] == 2

    def test_solvation_parsing(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p B3LYP/6-31G* SCRF=(SMD,Solvent=Water)\n\n"
            "Test\n\n0 1\nH  0.0  0.0  0.0\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["scrf_model"] == "SMD"
        assert result["params"]["scrf_solvent"] == "Water"

    def test_empty_input(self):
        result = _parse_gaussian_text("")
        assert result["params"] == {}
        assert result["structure"] == {}

    def test_charged_species(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p HF/STO-3G\n\nLi cation\n\n1 1\n"
            "Li  0.0  0.0  0.0\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["charge"] == 1
        assert result["params"]["multiplicity"] == 1

    def test_open_shell(self):
        text = (
            "%mem=500MB\n%nproc=1\n#p UHF/6-31G*\n\nO2 triplet\n\n0 3\n"
            "O  0.0  0.0  0.0\nO  0.0  0.0  1.21\n\n"
        )
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "UHF"
        assert result["params"]["multiplicity"] == 3
        assert result["structure"]["species"] == ["O", "O"]


# ──────────────────────────────────────────────────────────────────────────
# Curated sample tests
# ──────────────────────────────────────────────────────────────────────────


class TestCuratedSamples:
    """Parse curated .gjf samples from tests/inputformat/samples/gaussian/."""

    def test_water_hf_sp(self):
        text = (SAMPLES_DIR / "water_hf_sp" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["charge"] == 0
        assert result["params"]["multiplicity"] == 1
        assert result["structure"]["species"] == ["O", "H", "H"]
        assert len(result["structure"]["cart_coords"]) == 3
        assert result["params"]["chk_name"] == "water.chk"

    def test_water_b3lyp_opt(self):
        text = (SAMPLES_DIR / "water_b3lyp_opt" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "6-31G*"
        assert result["params"]["gen_type"] == "relax"
        assert result["structure"]["species"] == ["O", "H", "H"]

    def test_methanol_solvation(self):
        text = (SAMPLES_DIR / "methanol_solvation" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "6-31G*"
        assert result["params"]["scrf_model"] == "SMD"
        assert result["params"]["scrf_solvent"] == "Water"
        assert len(result["structure"]["species"]) == 6

    def test_water_zmatrix(self):
        text = (SAMPLES_DIR / "water_zmatrix" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert "zmatrix" in result["params"]
        assert len(result["params"]["zmatrix"]) == 3
        assert result["params"]["zmatrix_variables"]["R1"] == 0.96
        assert result["params"]["zmatrix_variables"]["A1"] == 104.5
        assert result["structure"]["species"] == ["O", "H", "H"]

    def test_formaldehyde_tddft(self):
        text = (SAMPLES_DIR / "formaldehyde_tddft" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["gen_type"] == "td"
        assert result["params"]["td_nstates"] == 3
        assert len(result["structure"]["species"]) == 4

    def test_hcn_scan(self):
        text = (SAMPLES_DIR / "hcn_scan" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["gen_type"] == "scan"
        assert "zmatrix" in result["params"]
        zvars = result["params"]["zmatrix_variables"]
        assert zvars["R1"] == 1.07
        assert zvars["R1_scan_steps"] == 5
        assert zvars["R1_scan_step_size"] == 0.05

    def test_ethylene_mp2(self):
        text = (SAMPLES_DIR / "ethylene_mp2" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "MP2"
        assert result["params"]["basis"] == "STO-3G"
        assert result["structure"]["species"] == ["C", "C", "H", "H", "H", "H"]
        assert len(result["structure"]["cart_coords"]) == 6

    def test_o2_triplet_uhf(self):
        text = (SAMPLES_DIR / "o2_triplet_uhf" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "UHF"
        assert result["params"]["basis"] == "6-31G*"
        assert result["params"]["multiplicity"] == 3
        assert result["structure"]["species"] == ["O", "O"]

    def test_water_opt_freq(self):
        text = (SAMPLES_DIR / "water_opt_freq" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["gen_type"] == "relax"
        assert result["params"]["freq"] is True
        assert result["structure"]["species"] == ["O", "H", "H"]

    def test_multi_step_link1(self):
        text = (SAMPLES_DIR / "multi_step_link1" / "input.gjf").read_text()
        result = _parse_gaussian_text(text)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["link1_jobs"] == 2
        assert result["structure"]["species"] == ["O", "H", "H"]


# ──────────────────────────────────────────────────────────────────────────
# Write-parse roundtrip tests
# ──────────────────────────────────────────────────────────────────────────


class TestWriteParseRoundtrip:
    """Verify that write -> parse recovers the original data."""

    def _roundtrip(self, params: dict, structure: dict) -> dict:
        """Write and then parse, returning the parsed result."""
        text = _write_gaussian_text({"params": params, "structure": structure})
        return _parse_gaussian_text(text)

    def test_roundtrip_sp(self):
        params = {"method": "HF", "basis": "STO-3G", "charge": 0,
                  "multiplicity": 1, "gen_type": "scf"}
        structure = {"species": ["H", "H"],
                     "cart_coords": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]]}
        result = self._roundtrip(params, structure)
        assert result["params"]["method"] == "HF"
        assert result["params"]["basis"] == "STO-3G"
        assert result["params"]["charge"] == 0
        assert result["structure"]["species"] == ["H", "H"]
        for orig, parsed in zip(structure["cart_coords"],
                                result["structure"]["cart_coords"]):
            for a, b in zip(orig, parsed):
                assert abs(a - b) < 1e-5

    def test_roundtrip_opt(self):
        params = {"method": "B3LYP", "basis": "6-31G*", "charge": 0,
                  "multiplicity": 1, "gen_type": "relax"}
        structure = {"species": ["O", "H", "H"],
                     "cart_coords": [[0.0, 0.0, 0.117],
                                     [0.0, 0.757, -0.470],
                                     [0.0, -0.757, -0.470]]}
        result = self._roundtrip(params, structure)
        assert result["params"]["method"] == "B3LYP"
        assert result["params"]["gen_type"] == "relax"

    def test_roundtrip_td(self):
        params = {"method": "B3LYP", "basis": "STO-3G", "charge": 0,
                  "multiplicity": 1, "gen_type": "td", "td_nstates": 5}
        structure = {"species": ["H"], "cart_coords": [[0.0, 0.0, 0.0]]}
        result = self._roundtrip(params, structure)
        assert result["params"]["gen_type"] == "td"
        assert result["params"]["td_nstates"] == 5

    def test_roundtrip_opt_tight(self):
        params = {"method": "HF", "basis": "STO-3G", "charge": 0,
                  "multiplicity": 1, "gen_type": "relax", "opt_tight": True}
        structure = {"species": ["H"], "cart_coords": [[0.0, 0.0, 0.0]]}
        result = self._roundtrip(params, structure)
        assert result["params"]["gen_type"] == "relax"
        assert result["params"]["opt_tight"] is True

    def test_roundtrip_charged(self):
        params = {"method": "HF", "basis": "STO-3G", "charge": 1,
                  "multiplicity": 1, "gen_type": "scf"}
        structure = {"species": ["Li"], "cart_coords": [[0.0, 0.0, 0.0]]}
        result = self._roundtrip(params, structure)
        assert result["params"]["charge"] == 1

    def test_roundtrip_frac_coords(self):
        """Writer converts frac_coords to Cartesian; parser reads Cartesian."""
        params = {"method": "HF", "basis": "STO-3G", "charge": 0,
                  "multiplicity": 1, "gen_type": "scf"}
        lattice = [[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]]
        structure = {"species": ["H"], "lattice": lattice,
                     "frac_coords": [[0.1, 0.2, 0.3]]}
        result = self._roundtrip(params, structure)
        assert result["structure"]["species"] == ["H"]
        cc = result["structure"]["cart_coords"][0]
        assert abs(cc[0] - 0.5) < 1e-4  # 0.1 * 5.0
        assert abs(cc[1] - 1.0) < 1e-4  # 0.2 * 5.0
        assert abs(cc[2] - 1.5) < 1e-4  # 0.3 * 5.0


# ──────────────────────────────────────────────────────────────────────────
# InputSpec wiring test
# ──────────────────────────────────────────────────────────────────────────


class TestInputSpecWiring:
    """Verify the EngineInputSpec is properly configured."""

    def test_spec_has_parser(self):
        spec = get_gaussian_input_spec()
        assert spec.engine_family == "gaussian"
        assert spec.syntax_family == "keyword-block"
        file_spec = spec.input_files[0]
        assert file_spec.filename == "input.gjf"
        assert file_spec.content_role == "combined"
        assert file_spec.custom_writer is not None
        assert file_spec.custom_parser is not None

    def test_spec_ssot_mapping(self):
        spec = get_gaussian_input_spec()
        assert "input.gjf" in spec.ssot_mapping.structure_in
        assert "input.gjf" in spec.ssot_mapping.params_in
