"""Tests for xTB output digest parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.xtb.parsers.output import (
    HARTREE_TO_EV,
    XTBDigest,
    XTBOutputParser,
    parse_xtb_output_text,
)


SAMPLE_SP_OUTPUT = """
normal termination of xtb
          | TOTAL ENERGY               -5.070364560763 Eh   |
          | GRADIENT NORM               0.007345375354 Eh/a |
          | HOMO-LUMO GAP              14.631971916676 eV   |
 * wall-time:     0 d,  0 h,  0 min,  0.022 sec
"""

SAMPLE_OPT_FREQ_OUTPUT = """
   *** GEOMETRY OPTIMIZATION CONVERGED AFTER 4 ITERATIONS ***
 projected vibrational frequencies (cm⁻¹)
 eigval :   1539.03   3642.76   3651.17
         :: total free energy          -5.068041330881 Eh   ::
         :: zero point energy           0.020120982582 Eh   ::
normal termination of xtb
          | TOTAL ENERGY               -5.070544373345 Eh   |
          | GRADIENT NORM               0.000148873657 Eh/a |
          | HOMO-LUMO GAP              14.384652490063 eV   |
 * wall-time:     0 d,  0 h,  0 min,  0.041 sec
"""

SAMPLE_FAILED_OUTPUT = """
xTB error: failed to converge SCC within iteration limit
"""


class TestXTBDigestTextParsing:
    def test_sp_parse(self):
        d = parse_xtb_output_text(SAMPLE_SP_OUTPUT)
        assert d.normal_termination is True
        assert d.success is True
        assert d.final_energy_Ha is not None
        assert abs(d.final_energy_Ha - (-5.070364560763)) < 1e-12
        assert d.final_energy_eV is not None
        assert abs(d.final_energy_eV - d.final_energy_Ha * HARTREE_TO_EV) < 1e-6

    def test_opt_freq_parse(self):
        d = parse_xtb_output_text(SAMPLE_OPT_FREQ_OUTPUT)
        assert d.converged_geometry is True
        assert d.n_opt_cycles == 4
        assert d.free_energy_Ha is not None
        assert abs(d.free_energy_Ha - (-5.068041330881)) < 1e-12
        assert d.zpe_Ha is not None
        assert abs(d.zpe_Ha - 0.020120982582) < 1e-12
        assert d.frequencies_cm is not None
        assert len(d.frequencies_cm) == 3

    def test_failed_parse(self):
        d = parse_xtb_output_text(SAMPLE_FAILED_OUTPUT)
        assert d.success is False
        assert d.final_energy_Ha is None

    def test_to_dict(self):
        d = XTBDigest(success=True, final_energy_Ha=-1.0)
        as_dict = d.to_dict()
        assert isinstance(as_dict, dict)
        assert as_dict["success"] is True


class TestXTBOutputParserClass:
    def test_can_parse(self, tmp_path):
        (tmp_path / "xtb.out").write_text(SAMPLE_SP_OUTPUT, encoding="utf-8")
        parser = XTBOutputParser()
        assert parser.can_parse(tmp_path)

    def test_parse_directory_with_geometry(self, tmp_path):
        (tmp_path / "xtb.out").write_text(SAMPLE_OPT_FREQ_OUTPUT, encoding="utf-8")
        (tmp_path / "xtbopt.xyz").write_text(
            "3\nenergy: -5.070544 gnorm: 0.000148\n"
            "O 0.0 0.0 0.117\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469\n",
            encoding="utf-8",
        )
        parser = XTBOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.n_atoms == 3
        assert d.final_species == ["O", "H", "H"]

    def test_parse_missing_output(self, tmp_path):
        parser = XTBOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is False
        assert d.error_message is not None

    def test_registry(self):
        from quantumvitas.parsers.registry import get_parser

        cls = get_parser("xtb", "scf_digest")
        assert cls is XTBOutputParser


_REAL_RUN_DIR = Path(__file__).resolve().parents[2] / ".tmp" / "engine_research" / "xtb" / "real_run"


@pytest.mark.skipif(not _REAL_RUN_DIR.is_dir(), reason="No xTB real_run corpus in .tmp")
class TestXTBRealRuns:
    @pytest.mark.parametrize(
        "slug",
        [
            "water_sp_gfn2",
            "water_opt_gfn2",
            "water_freq_ohess",
            "water_md_short",
            "ethanol_opt_tight",
            "water_sp_solvation_alpb",
            "o2_triplet_sp",
            "caffeine_grad",
        ],
    )
    def test_parse_real_run(self, slug):
        run_dir = _REAL_RUN_DIR / slug / "outputs"
        if not run_dir.is_dir():
            pytest.skip(f"real_run missing for {slug}")
        parser = XTBOutputParser()
        digest = parser.parse(run_dir)
        assert digest.normal_termination is True
        assert digest.final_energy_Ha is not None
