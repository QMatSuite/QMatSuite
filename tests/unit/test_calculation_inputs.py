"""
Unit tests for calculation input files and jobconfig ordering.
"""

from pathlib import Path

import pytest

from quantumvitas.io import QEInputParser
from tests.core.test_data import load_test_cases

pytestmark = pytest.mark.unit


@pytest.fixture
def si_dos_dir(ci_test_data_dir: Path) -> Path:
    return ci_test_data_dir / "4_Si_DOS"


@pytest.fixture
def si_bands_dir(ci_test_data_dir: Path) -> Path:
    return ci_test_data_dir / "7_Si_bandStructure"


def test_si_dos_parse_inputs(si_dos_dir: Path):
    scf = QEInputParser.parse_file(si_dos_dir / "si.1_scf.in")
    nscf = QEInputParser.parse_file(si_dos_dir / "si.2_nscf.in")
    dos = QEInputParser.parse_file(si_dos_dir / "si.3_dos.in")

    assert scf.get_namelist("control").get("calculation") == "scf"
    assert nscf.get_namelist("control").get("calculation") == "nscf"
    assert dos.get_namelist("dos") is not None
    assert (si_dos_dir / "reference" / "si.1_scf.out").exists()


def test_si_dos_jobconfig_sequence(ci_test_data_dir: Path, si_dos_dir: Path):
    cases = load_test_cases(si_dos_dir, ci_root=ci_test_data_dir)
    assert cases, "No si_dos test cases discovered"
    expected = ["si.1_scf.in", "si.2_nscf.in", "si.3_dos.in"]
    assert [case.input_path.name for case in cases] == expected
    for case in cases:
        assert case.input_path.exists()


def test_si_bands_parse_inputs(si_bands_dir: Path):
    scf = QEInputParser.parse_file(si_bands_dir / "si.0_scf.in")
    nscf = QEInputParser.parse_file(si_bands_dir / "si.1_nscf.in")
    bands = QEInputParser.parse_file(si_bands_dir / "si.2_bands.in")
    bands_pp = QEInputParser.parse_file(si_bands_dir / "si.3_bands.pp.in")

    assert scf.get_namelist("control").get("calculation") == "scf"
    assert nscf.get_namelist("control").get("calculation") == "nscf"
    assert bands.get_namelist("control").get("calculation") == "bands"
    assert bands_pp.get_namelist("bands") is not None
    assert (si_bands_dir / "reference" / "si.0_scf.out").exists()


def test_si_bands_jobconfig_sequence(ci_test_data_dir: Path, si_bands_dir: Path):
    cases = load_test_cases(si_bands_dir, ci_root=ci_test_data_dir)
    assert cases, "No si_bands test cases discovered"
    expected = [
        "si.0_scf.in",
        "si.1_nscf.in",
        "si.2_bands.in",
        "si.3_bands.pp.in",
        "si.4_plotband.in",
    ]
    assert [case.input_path.name for case in cases] == expected
    for case in cases:
        assert case.input_path.exists()

