"""
Test structure import pipeline: .cif → project .json → QE materialization.

End-to-end tests that verify the full import pipeline from CIF files
through the API service layer to QE input file generation.  Assertions
check numerical values (lattice parameters, atomic positions, cell vectors)
with physical tolerances rather than just string containment.
"""

import json
import re

import pytest
from pathlib import Path

from qmatsuite.api.service import QMSService
from qmatsuite.inputformat import write_engine_inputs
from qmatsuite.drivers.qe.inputspec import get_qe_input_spec

CIF_DIR = Path(__file__).parent.parent / "data" / "structures"

# --- Known reference values ---
# Si diamond primitive cell (FCC basis, 2 atoms)
SI_A = 3.840  # lattice constant a ≈ 3.84 Å (primitive, NOT conventional 5.43)
SI_ANGLE = 60.0  # all angles 60° for FCC primitive
SI_NATOMS = 2
SI_FRAC = [[0.0, 0.0, 0.0], [0.75, 0.75, 0.75]]
# Primitive cell vectors (Cartesian, angstrom)
SI_CELL = [
    [3.3256, 0.0000, 1.9200],
    [1.1085, 3.1354, 1.9200],
    [0.0000, 0.0000, 3.8401],
]

# Al FCC primitive cell (1 atom)
AL_A = 2.863  # lattice constant a ≈ 2.86 Å (primitive)
AL_ANGLE = 60.0
AL_NATOMS = 1
AL_FRAC = [[0.0, 0.0, 0.0]]
AL_CELL = [
    [2.4799, 0.0000, 1.4317],
    [0.8266, 2.3380, 1.4317],
    [0.0000, 0.0000, 2.8635],
]

TOL = 0.02  # angstrom / degree tolerance for lattice comparisons
COORD_TOL = 1e-4  # fractional coordinate tolerance


def _approx(a, b, tol=TOL):
    return abs(a - b) < tol


def _parse_qe_cell_parameters(text):
    """Extract 3×3 cell matrix from CELL_PARAMETERS block."""
    m = re.search(
        r"CELL_PARAMETERS\s*\(angstrom\)\s*\n"
        r"\s*([\d.Ee+-]+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)\s*\n"
        r"\s*([\d.Ee+-]+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)\s*\n"
        r"\s*([\d.Ee+-]+)\s+([\d.Ee+-]+)\s+([\d.Ee+-]+)",
        text,
    )
    assert m, "CELL_PARAMETERS (angstrom) block not found"
    vals = [float(m.group(i)) for i in range(1, 10)]
    return [vals[0:3], vals[3:6], vals[6:9]]


def _parse_qe_atomic_positions(text):
    """Extract list of (species, frac_x, frac_y, frac_z) from ATOMIC_POSITIONS."""
    m = re.search(r"ATOMIC_POSITIONS\s*\(crystal\)\s*\n((?:\s*\S+\s+[\d.Ee+-]+\s+[\d.Ee+-]+\s+[\d.Ee+-]+\s*\n?)+)", text)
    assert m, "ATOMIC_POSITIONS (crystal) block not found"
    atoms = []
    for line in m.group(1).strip().splitlines():
        parts = line.split()
        atoms.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
    return atoms


def _parse_qe_kpoints(text):
    """Extract k-point grid and shift from K_POINTS (automatic) block."""
    m = re.search(r"K_POINTS\s*\(automatic\)\s*\n\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text)
    assert m, "K_POINTS (automatic) block not found"
    grid = [int(m.group(i)) for i in range(1, 4)]
    shift = [int(m.group(i)) for i in range(4, 7)]
    return grid, shift


def _parse_qe_namelist(text, name):
    """Extract key=value pairs from a QE &NAMELIST block."""
    pattern = rf"&{name}\s*\n(.*?)\n\s*/"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    assert m, f"Namelist &{name} not found"
    params = {}
    for line in m.group(1).strip().splitlines():
        line = line.strip().rstrip(",")
        if "=" in line:
            k, v = line.split("=", 1)
            params[k.strip()] = v.strip().strip("'\"")
    return params


@pytest.fixture
def si_cif():
    p = CIF_DIR / "si_diamond.cif"
    assert p.exists(), f"Missing fixture: {p}"
    return p


@pytest.fixture
def al_cif():
    p = CIF_DIR / "al_fcc.cif"
    assert p.exists(), f"Missing fixture: {p}"
    return p


@pytest.fixture
def project(tmp_path):
    """Create a fresh QMSService project."""
    project_root = tmp_path / "test_project"
    QMSService.init_project(project_root, name="test")
    return QMSService(project_root)


def _import_and_read(project, cif_path, name):
    """Import CIF, read back pymatgen structure, return (StructureDTO, PMGStructure)."""
    from qmatsuite.io.structure_io import read_structure

    dto = project.structure.import_file(source=cif_path, name=name)
    ref = project.structure.require_ref(dto.meta.ulid)
    pmg = read_structure(ref.absolute_path)
    return dto, pmg


class TestSiImport:
    """Si diamond CIF import and JSON persistence."""

    def test_dto_metadata(self, project, si_cif):
        result = project.structure.import_file(source=si_cif, name="Silicon")
        assert result.meta is not None
        assert result.meta.ulid
        assert result.meta.name == "Silicon"
        assert result.num_atoms == SI_NATOMS
        assert "Si" in result.formula

    def test_json_persisted(self, project, si_cif):
        project.structure.import_file(source=si_cif, name="Silicon")
        json_files = list((project.project_root / "structures").glob("*.json"))
        assert len(json_files) == 1
        data = json.loads(json_files[0].read_text())
        assert "__qms_meta__" in data
        assert "structure" in data
        sites = data["structure"]["sites"]
        assert len(sites) == SI_NATOMS

    def test_lattice_parameters(self, project, si_cif):
        _, pmg = _import_and_read(project, si_cif, "Silicon")
        assert _approx(pmg.lattice.a, SI_A)
        assert _approx(pmg.lattice.b, SI_A)
        assert _approx(pmg.lattice.c, SI_A)
        assert _approx(pmg.lattice.alpha, SI_ANGLE)
        assert _approx(pmg.lattice.beta, SI_ANGLE)
        assert _approx(pmg.lattice.gamma, SI_ANGLE)

    def test_species_and_frac_coords(self, project, si_cif):
        _, pmg = _import_and_read(project, si_cif, "Silicon")
        species = [str(s) for s in pmg.species]
        assert species == ["Si", "Si"]
        frac = pmg.frac_coords.tolist()
        for i in range(SI_NATOMS):
            for j in range(3):
                assert abs(frac[i][j] - SI_FRAC[i][j]) < COORD_TOL, (
                    f"Si frac_coord[{i}][{j}]: {frac[i][j]} != {SI_FRAC[i][j]}"
                )

    def test_get_atoms_roundtrip(self, project, si_cif):
        result = project.structure.import_file(source=si_cif, name="Silicon")
        atoms = project.structure.get_atoms(result.meta.ulid)
        assert atoms["num_atoms"] == SI_NATOMS
        assert atoms["species"] == ["Si", "Si"]
        abc = atoms["lattice_abc"]
        assert _approx(abc[0], SI_A)
        assert _approx(abc[1], SI_A)
        assert _approx(abc[2], SI_A)


class TestAlImport:
    """Al FCC CIF import and JSON persistence."""

    def test_dto_metadata(self, project, al_cif):
        result = project.structure.import_file(source=al_cif, name="Aluminum")
        assert result.meta is not None
        assert result.meta.ulid
        assert result.num_atoms == AL_NATOMS
        assert "Al" in result.formula

    def test_lattice_parameters(self, project, al_cif):
        _, pmg = _import_and_read(project, al_cif, "Aluminum")
        assert _approx(pmg.lattice.a, AL_A)
        assert _approx(pmg.lattice.b, AL_A)
        assert _approx(pmg.lattice.c, AL_A)
        assert _approx(pmg.lattice.alpha, AL_ANGLE)
        assert _approx(pmg.lattice.beta, AL_ANGLE)
        assert _approx(pmg.lattice.gamma, AL_ANGLE)

    def test_species_and_frac_coords(self, project, al_cif):
        _, pmg = _import_and_read(project, al_cif, "Aluminum")
        species = [str(s) for s in pmg.species]
        assert species == ["Al"]
        frac = pmg.frac_coords.tolist()
        for j in range(3):
            assert abs(frac[0][j] - AL_FRAC[0][j]) < COORD_TOL


class TestSiMaterializeQE:
    """Si diamond → QE scf.in materialization with numerical checks."""

    @pytest.fixture
    def si_qe_content(self, project, si_cif, tmp_path):
        _, pmg = _import_and_read(project, si_cif, "Silicon")
        structure_doc = {
            "lattice": pmg.lattice.matrix.tolist(),
            "species": [str(s) for s in pmg.species],
            "frac_coords": pmg.frac_coords.tolist(),
        }
        params = {
            "CONTROL": {"calculation": "scf", "prefix": "si"},
            "SYSTEM": {"ecutwfc": 30.0, "nat": 2, "ntyp": 1},
            "ELECTRONS": {"conv_thr": 1.0e-8},
            "kpoints": {"grid": [4, 4, 4], "shift": [0, 0, 0]},
        }
        spec = get_qe_input_spec(gen_type="scf")
        workdir = tmp_path / "qe_si"
        workdir.mkdir()
        written = write_engine_inputs(spec, workdir, params=params, structure=structure_doc)
        assert len(written) == 1
        assert written[0].name == "scf.in"
        return written[0].read_text()

    def test_cell_parameters(self, si_qe_content):
        cell = _parse_qe_cell_parameters(si_qe_content)
        for i in range(3):
            for j in range(3):
                assert _approx(cell[i][j], SI_CELL[i][j]), (
                    f"Si CELL_PARAMETERS[{i}][{j}]: {cell[i][j]} != {SI_CELL[i][j]}"
                )

    def test_atomic_positions(self, si_qe_content):
        atoms = _parse_qe_atomic_positions(si_qe_content)
        assert len(atoms) == SI_NATOMS
        for i, (sp, fx, fy, fz) in enumerate(atoms):
            assert sp == "Si"
            assert abs(fx - SI_FRAC[i][0]) < COORD_TOL
            assert abs(fy - SI_FRAC[i][1]) < COORD_TOL
            assert abs(fz - SI_FRAC[i][2]) < COORD_TOL

    def test_namelists(self, si_qe_content):
        ctrl = _parse_qe_namelist(si_qe_content, "CONTROL")
        assert ctrl["calculation"] == "scf"
        assert ctrl["prefix"] == "si"

        sys_ = _parse_qe_namelist(si_qe_content, "SYSTEM")
        assert float(sys_["ecutwfc"]) == pytest.approx(30.0)
        assert int(sys_["nat"]) == 2
        assert int(sys_["ntyp"]) == 1

        elec = _parse_qe_namelist(si_qe_content, "ELECTRONS")
        assert float(elec["conv_thr"]) == pytest.approx(1.0e-8)

    def test_kpoints(self, si_qe_content):
        grid, shift = _parse_qe_kpoints(si_qe_content)
        assert grid == [4, 4, 4]
        assert shift == [0, 0, 0]

    def test_atomic_species_card(self, si_qe_content):
        m = re.search(r"ATOMIC_SPECIES\s*\n\s*(\S+)\s+([\d.]+)\s+(\S+)", si_qe_content)
        assert m, "ATOMIC_SPECIES card not found"
        assert m.group(1) == "Si"
        assert m.group(3).endswith(".UPF")


class TestAlMaterializeQE:
    """Al FCC → QE scf.in materialization with numerical checks."""

    @pytest.fixture
    def al_qe_content(self, project, al_cif, tmp_path):
        _, pmg = _import_and_read(project, al_cif, "Aluminum")
        structure_doc = {
            "lattice": pmg.lattice.matrix.tolist(),
            "species": [str(s) for s in pmg.species],
            "frac_coords": pmg.frac_coords.tolist(),
        }
        params = {
            "CONTROL": {"calculation": "scf", "prefix": "al"},
            "SYSTEM": {"ecutwfc": 25.0, "nat": 1, "ntyp": 1},
            "ELECTRONS": {"conv_thr": 1.0e-8},
            "kpoints": {"grid": [6, 6, 6], "shift": [1, 1, 1]},
        }
        spec = get_qe_input_spec(gen_type="scf")
        workdir = tmp_path / "qe_al"
        workdir.mkdir()
        written = write_engine_inputs(spec, workdir, params=params, structure=structure_doc)
        assert len(written) == 1
        assert written[0].name == "scf.in"
        return written[0].read_text()

    def test_cell_parameters(self, al_qe_content):
        cell = _parse_qe_cell_parameters(al_qe_content)
        for i in range(3):
            for j in range(3):
                assert _approx(cell[i][j], AL_CELL[i][j]), (
                    f"Al CELL_PARAMETERS[{i}][{j}]: {cell[i][j]} != {AL_CELL[i][j]}"
                )

    def test_atomic_positions(self, al_qe_content):
        atoms = _parse_qe_atomic_positions(al_qe_content)
        assert len(atoms) == AL_NATOMS
        sp, fx, fy, fz = atoms[0]
        assert sp == "Al"
        assert abs(fx - 0.0) < COORD_TOL
        assert abs(fy - 0.0) < COORD_TOL
        assert abs(fz - 0.0) < COORD_TOL

    def test_namelists(self, al_qe_content):
        sys_ = _parse_qe_namelist(al_qe_content, "SYSTEM")
        assert float(sys_["ecutwfc"]) == pytest.approx(25.0)
        assert int(sys_["nat"]) == 1

    def test_kpoints(self, al_qe_content):
        grid, shift = _parse_qe_kpoints(al_qe_content)
        assert grid == [6, 6, 6]
        assert shift == [1, 1, 1]


class TestDedupFingerprint:
    """Fingerprint-based deduplication on reimport."""

    def test_same_cif_dedup(self, project, si_cif):
        r1 = project.structure.import_file(source=si_cif, name="Si_first", dedup_by_fingerprint=True)
        r2 = project.structure.import_file(source=si_cif, name="Si_second", dedup_by_fingerprint=True)
        assert r1.meta.ulid == r2.meta.ulid

    def test_different_cif_no_dedup(self, project, si_cif, al_cif):
        r1 = project.structure.import_file(source=si_cif, name="Silicon", dedup_by_fingerprint=True)
        r2 = project.structure.import_file(source=al_cif, name="Aluminum", dedup_by_fingerprint=True)
        assert r1.meta.ulid != r2.meta.ulid
