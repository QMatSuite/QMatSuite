"""
Unit tests for workflow input files and jobconfig ordering.
"""

from pathlib import Path

import pytest

from quantumvitas.io import QEInputParser
from tests.core.qe_test_utils import parse_jobconfig

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


def test_si_dos_jobconfig_sequence(ci_test_data_dir: Path, si_dos_dir: Path):
    jobconfig_path = ci_test_data_dir / "jobconfig"
    if not jobconfig_path.exists():
        pytest.skip(f"jobconfig file not found: {jobconfig_path}")

    all_tests = parse_jobconfig(jobconfig_path, "")
    category = "4_Si_DOS"
    if category not in all_tests:
        pytest.skip(f"Category '{category}' not found in jobconfig")

    for input_file, _ in all_tests[category]:
        assert (si_dos_dir / input_file).exists()


def test_si_bands_parse_inputs(si_bands_dir: Path):
    scf = QEInputParser.parse_file(si_bands_dir / "si.0_scf.in")
    nscf = QEInputParser.parse_file(si_bands_dir / "si.1_nscf.in")
    bands = QEInputParser.parse_file(si_bands_dir / "si.2_bands.in")
    bands_pp = QEInputParser.parse_file(si_bands_dir / "si.3_bands.pp.in")

    assert scf.get_namelist("control").get("calculation") == "scf"
    assert nscf.get_namelist("control").get("calculation") == "nscf"
    assert bands.get_namelist("control").get("calculation") == "bands"
    assert bands_pp.get_namelist("bands") is not None


def test_si_bands_jobconfig_sequence(ci_test_data_dir: Path, si_bands_dir: Path):
    jobconfig_path = ci_test_data_dir / "jobconfig"
    if not jobconfig_path.exists():
        pytest.skip(f"jobconfig file not found: {jobconfig_path}")

    all_tests = parse_jobconfig(jobconfig_path, "")
    category = "7_Si_bandStructure"
    if category not in all_tests:
        pytest.skip(f"Category '{category}' not found in jobconfig")

    for input_file, _ in all_tests[category]:
        assert (si_bands_dir / input_file).exists()

