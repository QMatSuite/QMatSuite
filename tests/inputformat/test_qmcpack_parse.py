"""Tests for QMCPACK XML input parser, writer, and roundtrip.

Tests the custom_parser and custom_writer in
src/quantumvitas/drivers/qmcpack/inputspec.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.qmcpack.inputspec import (
    _extract_resource_refs,
    _parse_pos_array,
    _parse_qmcpack_text,
    _parse_string_array,
    _write_qmcpack_text,
    get_qmcpack_input_spec,
)

SAMPLES_DIR = Path(__file__).parent / "samples" / "qmcpack"


def _read_sample(name: str) -> str:
    return (SAMPLES_DIR / name / "qmc_input.xml").read_text()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

class TestPosArray:
    def test_single_position(self):
        assert _parse_pos_array("0.0 0.0 0.0") == [[0.0, 0.0, 0.0]]

    def test_multiple_positions(self):
        result = _parse_pos_array("1.0 2.0 3.0\n4.0 5.0 6.0")
        assert len(result) == 2
        assert result[0] == [1.0, 2.0, 3.0]
        assert result[1] == [4.0, 5.0, 6.0]

    def test_scientific_notation(self):
        result = _parse_pos_array("1.5e-01  2.0e+00  -3.5e-02")
        assert len(result) == 1
        assert abs(result[0][0] - 0.15) < 1e-10

    def test_empty(self):
        assert _parse_pos_array("") == []
        assert _parse_pos_array("   ") == []


class TestStringArray:
    def test_basic(self):
        assert _parse_string_array("Li H") == ["Li", "H"]

    def test_whitespace(self):
        assert _parse_string_array("  H   H  ") == ["H", "H"]


# ---------------------------------------------------------------------------
# Parser: He VMC STO (simplest case)
# ---------------------------------------------------------------------------

class TestParseHeVmcSto:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("he_vmc_sto"))

    def test_has_params_and_structure(self, parsed):
        assert "params" in parsed
        assert "structure" in parsed

    def test_project(self, parsed):
        p = parsed["params"]
        assert p["project_id"] == "He"
        assert p["series"] == "0"
        assert p["driver_version"] == "batch"

    def test_species(self, parsed):
        s = parsed["structure"]
        assert s["species"] == ["He"]

    def test_coordinates_cartesian(self, parsed):
        s = parsed["structure"]
        assert "cart_coords" in s
        assert len(s["cart_coords"]) == 1
        assert s["cart_coords"][0] == [0.0, 0.0, 0.0]

    def test_no_lattice(self, parsed):
        assert "lattice" not in parsed["structure"]

    def test_electrons(self, parsed):
        e = parsed["params"]["electrons"]
        assert e == {"u": 1, "d": 1}

    def test_wavefunction_info(self, parsed):
        wf = parsed["params"]["wavefunction"]
        assert wf["name"] == "psi0"
        assert wf["determinantset"]["type"] == "MO"
        assert wf["determinantset"]["key"] == "STO"
        assert len(wf["jastrow"]) == 1
        assert wf["jastrow"][0]["type"] == "Two-Body"
        assert wf["jastrow"][0]["function"] == "pade"

    def test_hamiltonian_info(self, parsed):
        ham = parsed["params"]["hamiltonian"]
        assert ham["name"] == "h0"
        pairpots = ham["pairpots"]
        assert len(pairpots) == 2
        types = {pp["type"] for pp in pairpots}
        assert types == {"coulomb"}

    def test_qmc_blocks(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 1
        assert qmc[0]["method"] == "vmc"
        assert qmc[0]["blocks"] == "100"
        assert qmc[0]["steps"] == "50"
        assert qmc[0]["timestep"] == "0.1"

    def test_preserved_xml_strings(self, parsed):
        assert "_wavefunction_xml" in parsed["params"]
        assert "_hamiltonian_xml" in parsed["params"]
        assert "<wavefunction" in parsed["params"]["_wavefunction_xml"]
        assert "<hamiltonian" in parsed["params"]["_hamiltonian_xml"]

    def test_no_resource_refs(self, parsed):
        assert "_resource_refs" not in parsed["params"]


# ---------------------------------------------------------------------------
# Parser: H2 all-electron VMC (multi-atom molecule)
# ---------------------------------------------------------------------------

class TestParseH2AeVmc:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("h2_ae_vmc"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "H2"

    def test_random_seed(self, parsed):
        assert parsed["params"]["random_seed"] == "130"

    def test_species(self, parsed):
        s = parsed["structure"]
        assert s["species"] == ["H", "H"]

    def test_cartesian_coords(self, parsed):
        s = parsed["structure"]
        assert "cart_coords" in s
        coords = s["cart_coords"]
        assert len(coords) == 2
        # H2 bond along z-axis
        assert abs(coords[0][2] + coords[1][2]) < 1e-6  # symmetric

    def test_jastrow_types(self, parsed):
        wf = parsed["params"]["wavefunction"]
        jastrows = wf["jastrow"]
        assert len(jastrows) == 2
        types = {j["type"] for j in jastrows}
        assert types == {"Two-Body", "One-Body"}

    def test_hamiltonian_has_constant(self, parsed):
        ham = parsed["params"]["hamiltonian"]
        assert "constants" in ham
        assert ham["constants"][0]["name"] == "IonIon"

    def test_qmc_single_vmc(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 1
        assert qmc[0]["method"] == "vmc"
        assert qmc[0]["blocks"] == "200"


# ---------------------------------------------------------------------------
# Parser: LiH solid (periodic, PPs, 2 QMC blocks)
# ---------------------------------------------------------------------------

class TestParseLihSolid:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("lih_solid_vmc_pp"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "LiH"
        assert parsed["params"]["series"] == "1"

    def test_lattice(self, parsed):
        s = parsed["structure"]
        assert "lattice" in s
        lat = s["lattice"]
        assert len(lat) == 3
        assert abs(lat[0][0] - (-3.55)) < 0.01

    def test_bconds(self, parsed):
        assert parsed["params"]["bconds"] == "p p p"

    def test_lr_dim_cutoff(self, parsed):
        assert parsed["params"]["LR_dim_cutoff"] == "15"

    def test_species(self, parsed):
        s = parsed["structure"]
        assert s["species"] == ["Li", "H"]

    def test_fractional_coords(self, parsed):
        s = parsed["structure"]
        assert "frac_coords" in s
        coords = s["frac_coords"]
        assert len(coords) == 2
        assert coords[0] == [0.0, 0.0, 0.0]
        assert coords[1] == [0.5, 0.5, 0.5]

    def test_ion_pset_name_preserved(self, parsed):
        # LiH uses "i" not "ion0"
        assert parsed["params"]["_ion_particleset_name"] == "i"

    def test_electrons(self, parsed):
        assert parsed["params"]["electrons"] == {"u": 2, "d": 2}

    def test_wavefunction_einspline(self, parsed):
        wf = parsed["params"]["wavefunction"]
        ds = wf["determinantset"]
        assert ds["type"] == "einspline"
        assert ds["href"] == "LiH.h5"
        assert ds["source"] == "i"

    def test_two_qmc_blocks(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 2
        assert qmc[0]["method"] == "vmc"
        assert qmc[1]["method"] == "dmc"

    def test_qmc_estimators(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert "_estimators" in qmc[0]
        assert qmc[0]["_estimators"][0]["name"] == "LocalEnergy"

    def test_resource_refs(self, parsed):
        refs = parsed["params"]["_resource_refs"]
        assert "LiH.h5" in refs["wavefunction_hrefs"]
        assert "Li.xml" in refs["pseudopotential_hrefs"]
        assert "H.xml" in refs["pseudopotential_hrefs"]

    def test_hamiltonian_pseudo(self, parsed):
        ham = parsed["params"]["hamiltonian"]
        pp = [p for p in ham["pairpots"] if p["type"] == "pseudo"]
        assert len(pp) == 1
        assert len(pp[0]["pseudos"]) == 2


# ---------------------------------------------------------------------------
# Parser: He optimization with loop
# ---------------------------------------------------------------------------

class TestParseHeOptPade:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("he_opt_pade"))

    def test_driver_version_legacy(self, parsed):
        assert parsed["params"]["driver_version"] == "legacy"

    def test_two_qmc_blocks(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 2

    def test_optimization_loop(self, parsed):
        qmc = parsed["params"]["qmc"]
        opt_block = qmc[0]
        assert opt_block["method"] == "linear"
        assert opt_block["_loop_max"] == "4"

    def test_optimization_costs(self, parsed):
        opt_block = parsed["params"]["qmc"][0]
        assert "_costs" in opt_block
        costs = opt_block["_costs"]
        assert costs["energy"] == "0.95"
        assert costs["reweightedvariance"] == "0.05"

    def test_final_vmc(self, parsed):
        vmc = parsed["params"]["qmc"][1]
        assert vmc["method"] == "vmc"
        assert "_loop_max" not in vmc


# ---------------------------------------------------------------------------
# Parser: HEG VMC (no ions, periodic)
# ---------------------------------------------------------------------------

class TestParseHegVmc:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("heg_vmc"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "heg_SJ"

    def test_rs_parameter(self, parsed):
        assert parsed["params"]["rs"] == "5"
        assert parsed["params"]["rs_condition"] == "14"

    def test_no_ion_structure(self, parsed):
        # HEG has no ions — structure should have empty species
        s = parsed.get("structure")
        # There's no ion particleset, but there IS a simulationcell
        # So structure may exist (lattice only) or be None
        if s is not None:
            assert s["species"] == []

    def test_electrons_14(self, parsed):
        e = parsed["params"]["electrons"]
        assert e == {"u": 7, "d": 7}

    def test_wavefunction_free(self, parsed):
        wf = parsed["params"]["wavefunction"]
        assert wf["sposet_collection"]["type"] == "free"

    def test_hamiltonian_estimator(self, parsed):
        ham = parsed["params"]["hamiltonian"]
        assert "estimators" in ham
        assert ham["estimators"][0]["type"] == "gofr"

    def test_qmc_tau_param(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert qmc[0]["tau"] == "5.0"


# ---------------------------------------------------------------------------
# Parser: minimal / edge cases
# ---------------------------------------------------------------------------

class TestParseMinimal:
    def test_empty_simulation(self):
        result = _parse_qmcpack_text("<simulation/>")
        assert result == {"params": {}}

    def test_project_only(self):
        xml = '<simulation><project id="test" series="5"/></simulation>'
        result = _parse_qmcpack_text(xml)
        assert result["params"]["project_id"] == "test"
        assert result["params"]["series"] == "5"

    def test_no_wavefunction(self):
        xml = """<simulation>
        <project id="x" series="0"/>
        <qmc method="vmc"><parameter name="blocks">10</parameter></qmc>
        </simulation>"""
        result = _parse_qmcpack_text(xml)
        assert "wavefunction" not in result["params"]
        assert result["params"]["qmc"][0]["blocks"] == "10"


# ---------------------------------------------------------------------------
# Writer tests
# ---------------------------------------------------------------------------

class TestWriter:
    def test_write_minimal(self):
        xml = _write_qmcpack_text({"params": {}, "structure": {}})
        assert "<?xml" in xml
        assert "<simulation>" in xml or "<simulation " in xml

    def test_write_project(self):
        xml = _write_qmcpack_text({
            "params": {"project_id": "Test", "series": "3",
                       "driver_version": "batch"},
            "structure": {},
        })
        assert 'id="Test"' in xml
        assert 'series="3"' in xml
        assert "driver_version" in xml
        assert "batch" in xml

    def test_write_qmc_block(self):
        xml = _write_qmcpack_text({
            "params": {
                "qmc": [{"method": "vmc", "blocks": "50", "steps": "10"}],
            },
            "structure": {},
        })
        assert 'method="vmc"' in xml
        assert "blocks" in xml
        assert "50" in xml

    def test_write_multi_qmc(self):
        xml = _write_qmcpack_text({
            "params": {
                "qmc": [
                    {"method": "vmc", "blocks": "10"},
                    {"method": "dmc", "blocks": "20"},
                ],
            },
            "structure": {},
        })
        assert 'method="vmc"' in xml
        assert 'method="dmc"' in xml

    def test_write_loop(self):
        xml = _write_qmcpack_text({
            "params": {
                "qmc": [{"method": "linear", "_loop_max": "4", "blocks": "5"}],
            },
            "structure": {},
        })
        assert '<loop max="4">' in xml
        assert 'method="linear"' in xml

    def test_write_lattice(self):
        xml = _write_qmcpack_text({
            "params": {"bconds": "p p p"},
            "structure": {
                "lattice": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "species": ["Si"],
                "frac_coords": [[0.0, 0.0, 0.0]],
            },
        })
        assert "simulationcell" in xml
        assert "bconds" in xml
        assert 'condition="1"' in xml  # frac_coords → condition="1"

    def test_write_cartesian(self):
        xml = _write_qmcpack_text({
            "params": {},
            "structure": {
                "species": ["H", "H"],
                "cart_coords": [[0.0, 0.0, -0.9], [0.0, 0.0, 0.9]],
            },
        })
        assert "particleset" in xml
        assert "ionid" in xml
        assert 'condition="1"' not in xml  # cart_coords → no condition

    def test_write_costs(self):
        xml = _write_qmcpack_text({
            "params": {
                "qmc": [{
                    "method": "linear",
                    "_costs": {"energy": "0.95", "reweightedvariance": "0.05"},
                    "blocks": "10",
                }],
            },
            "structure": {},
        })
        assert '<cost name="energy">' in xml
        assert "0.95" in xml


# ---------------------------------------------------------------------------
# Roundtrip tests: parse → write → parse → compare
# ---------------------------------------------------------------------------

def _assert_semantic_equal(a: dict, b: dict, tolerance: float = 1e-6):
    """Assert two parsed dicts are semantically equal (ignoring formatting)."""
    pa, pb = a["params"], b["params"]

    # Compare top-level scalar params
    for key in ("project_id", "series", "driver_version", "bconds",
                "LR_dim_cutoff", "rs", "rs_condition"):
        assert pa.get(key) == pb.get(key), f"Mismatch on params[{key!r}]"

    # Compare electrons
    assert pa.get("electrons") == pb.get("electrons"), "Electrons mismatch"

    # Compare qmc blocks
    qa, qb = pa.get("qmc", []), pb.get("qmc", [])
    assert len(qa) == len(qb), f"QMC block count: {len(qa)} vs {len(qb)}"
    for i, (ba, bb) in enumerate(zip(qa, qb)):
        assert ba.get("method") == bb.get("method"), f"QMC[{i}] method"
        for pname in ("blocks", "steps", "timestep", "warmupsteps",
                      "warmupSteps", "substeps", "tau"):
            assert ba.get(pname) == bb.get(pname), f"QMC[{i}].{pname}"
        assert ba.get("_loop_max") == bb.get("_loop_max"), f"QMC[{i}] loop"

    # Compare structure
    sa = a.get("structure")
    sb = b.get("structure")
    if sa is None:
        assert sb is None
        return
    assert sa["species"] == sb["species"], "Species mismatch"
    coords_key = "frac_coords" if "frac_coords" in sa else "cart_coords"
    ca = sa.get(coords_key, [])
    cb_key = "frac_coords" if "frac_coords" in sb else "cart_coords"
    cb = sb.get(cb_key, [])
    assert len(ca) == len(cb), "Coord count mismatch"
    for i, (va, vb) in enumerate(zip(ca, cb)):
        for j in range(3):
            assert abs(va[j] - vb[j]) < tolerance, (
                f"Coord[{i}][{j}]: {va[j]} vs {vb[j]}"
            )


class TestRoundtrip:
    def test_roundtrip_he_vmc_sto(self):
        text = _read_sample("he_vmc_sto")
        parsed1 = _parse_qmcpack_text(text)
        written = _write_qmcpack_text(parsed1)
        parsed2 = _parse_qmcpack_text(written)
        _assert_semantic_equal(parsed1, parsed2)

    def test_roundtrip_h2_ae_vmc(self):
        text = _read_sample("h2_ae_vmc")
        parsed1 = _parse_qmcpack_text(text)
        written = _write_qmcpack_text(parsed1)
        parsed2 = _parse_qmcpack_text(written)
        _assert_semantic_equal(parsed1, parsed2)

    def test_roundtrip_lih_solid(self):
        text = _read_sample("lih_solid_vmc_pp")
        parsed1 = _parse_qmcpack_text(text)
        written = _write_qmcpack_text(parsed1)
        parsed2 = _parse_qmcpack_text(written)
        _assert_semantic_equal(parsed1, parsed2)

    def test_roundtrip_he_opt_pade(self):
        text = _read_sample("he_opt_pade")
        parsed1 = _parse_qmcpack_text(text)
        written = _write_qmcpack_text(parsed1)
        parsed2 = _parse_qmcpack_text(written)
        _assert_semantic_equal(parsed1, parsed2)

    def test_roundtrip_heg_vmc(self):
        text = _read_sample("heg_vmc")
        parsed1 = _parse_qmcpack_text(text)
        written = _write_qmcpack_text(parsed1)
        parsed2 = _parse_qmcpack_text(written)
        _assert_semantic_equal(parsed1, parsed2)


# ---------------------------------------------------------------------------
# Resource refs
# ---------------------------------------------------------------------------

class TestResourceRefs:
    def test_lih_has_refs(self):
        import xml.etree.ElementTree as ET
        text = _read_sample("lih_solid_vmc_pp")
        root = ET.fromstring(text)
        refs = _extract_resource_refs(root)
        assert refs["wavefunction_hrefs"] == ["LiH.h5"]
        assert set(refs["pseudopotential_hrefs"]) == {"Li.xml", "H.xml"}
        assert refs["include_hrefs"] == []

    def test_he_no_refs(self):
        import xml.etree.ElementTree as ET
        text = _read_sample("he_vmc_sto")
        root = ET.fromstring(text)
        refs = _extract_resource_refs(root)
        assert refs["wavefunction_hrefs"] == []
        assert refs["pseudopotential_hrefs"] == []

    def test_refs_in_parsed_params(self):
        parsed = _parse_qmcpack_text(_read_sample("lih_solid_vmc_pp"))
        assert "_resource_refs" in parsed["params"]
        refs = parsed["params"]["_resource_refs"]
        assert "LiH.h5" in refs["wavefunction_hrefs"]

    def test_no_refs_in_ae_params(self):
        parsed = _parse_qmcpack_text(_read_sample("he_vmc_sto"))
        assert "_resource_refs" not in parsed["params"]


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

class TestOrchestratorIntegration:
    def test_spec_has_parser(self):
        spec = get_qmcpack_input_spec()
        fspec = spec.input_files[0]
        assert fspec.custom_parser is not None
        assert fspec.custom_writer is not None

    def test_orchestrator_parse(self, tmp_path):
        from quantumvitas.inputformat.parser import parse_engine_inputs

        spec = get_qmcpack_input_spec()
        xml_text = _read_sample("he_vmc_sto")
        (tmp_path / "qmc_input.xml").write_text(xml_text)

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["project_id"] == "He"
        assert result.structure is not None
        assert result.structure["species"] == ["He"]

    def test_orchestrator_write(self, tmp_path):
        from quantumvitas.inputformat.writer import write_engine_inputs

        spec = get_qmcpack_input_spec()
        params = {
            "project_id": "Test",
            "driver_version": "batch",
            "qmc": [{"method": "vmc", "blocks": "10"}],
        }
        structure = {
            "species": ["He"],
            "cart_coords": [[0.0, 0.0, 0.0]],
        }
        written = write_engine_inputs(spec, tmp_path, params, structure)
        assert len(written) == 1
        assert (tmp_path / "qmc_input.xml").exists()
        content = (tmp_path / "qmc_input.xml").read_text()
        assert "<simulation>" in content or "<simulation " in content
        assert "Test" in content

    def test_orchestrator_roundtrip(self, tmp_path):
        from quantumvitas.inputformat.parser import parse_engine_inputs
        from quantumvitas.inputformat.writer import write_engine_inputs

        spec = get_qmcpack_input_spec()
        # Parse sample
        xml_text = _read_sample("he_vmc_sto")
        (tmp_path / "qmc_input.xml").write_text(xml_text)
        result1 = parse_engine_inputs(spec, tmp_path)

        # Write to new dir
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        write_engine_inputs(spec, out_dir, result1.params, result1.structure)

        # Re-parse
        result2 = parse_engine_inputs(spec, out_dir)
        assert result1.params["project_id"] == result2.params["project_id"]
        assert result1.structure["species"] == result2.structure["species"]


# ---------------------------------------------------------------------------
# Parser: He DMC (VMC+DMC chain)
# ---------------------------------------------------------------------------

class TestParseHeDmc:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("he_dmc"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "He"
        assert parsed["params"]["driver_version"] == "batch"

    def test_two_qmc_blocks(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 2
        assert qmc[0]["method"] == "vmc"
        assert qmc[1]["method"] == "dmc"

    def test_dmc_has_pbyp(self, parsed):
        dmc = parsed["params"]["qmc"][1]
        assert dmc.get("move") == "pbyp"

    def test_dmc_targetwalkers(self, parsed):
        dmc = parsed["params"]["qmc"][1]
        assert dmc["targetwalkers"] == "64"

    def test_species_he(self, parsed):
        assert parsed["structure"]["species"] == ["He"]

    def test_roundtrip(self):
        text = _read_sample("he_dmc")
        p1 = _parse_qmcpack_text(text)
        w = _write_qmcpack_text(p1)
        p2 = _parse_qmcpack_text(w)
        _assert_semantic_equal(p1, p2)


# ---------------------------------------------------------------------------
# Parser: Be STO VMC (sposet_collection MolecularOrbital)
# ---------------------------------------------------------------------------

class TestParseBeStoVmc:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("be_sto_vmc"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "be_vmc"

    def test_species(self, parsed):
        assert parsed["structure"]["species"] == ["Be"]

    def test_cartesian_coords(self, parsed):
        s = parsed["structure"]
        assert "cart_coords" in s
        assert len(s["cart_coords"]) == 1

    def test_electrons(self, parsed):
        assert parsed["params"]["electrons"] == {"u": 2, "d": 2}

    def test_wavefunction_mo(self, parsed):
        wf = parsed["params"]["wavefunction"]
        assert wf["sposet_collection"]["type"] == "MolecularOrbital"

    def test_qmc_vmc(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 1
        assert qmc[0]["method"] == "vmc"
        assert qmc[0]["substeps"] == "10"
        assert qmc[0]["useDrift"] == "yes"

    def test_roundtrip(self):
        text = _read_sample("be_sto_vmc")
        p1 = _parse_qmcpack_text(text)
        w = _write_qmcpack_text(p1)
        p2 = _parse_qmcpack_text(w)
        _assert_semantic_equal(p1, p2)


# ---------------------------------------------------------------------------
# Parser: LiH QE workflow (composite pipeline)
# ---------------------------------------------------------------------------

class TestParseLihQeWorkflow:
    @pytest.fixture
    def parsed(self):
        return _parse_qmcpack_text(_read_sample("lih_qe_workflow"))

    def test_project(self, parsed):
        assert parsed["params"]["project_id"] == "LiH"

    def test_einspline_href(self, parsed):
        wf = parsed["params"]["wavefunction"]
        ds = wf["determinantset"]
        assert ds["type"] == "einspline"
        assert ds["href"] == "./pwscf_output/LiH-gamma.pwscf.h5"

    def test_lattice(self, parsed):
        s = parsed["structure"]
        assert "lattice" in s
        assert len(s["lattice"]) == 3

    def test_fractional_coords(self, parsed):
        s = parsed["structure"]
        assert "frac_coords" in s
        assert s["species"] == ["Li", "H"]

    def test_resource_refs(self, parsed):
        refs = parsed["params"]["_resource_refs"]
        assert "./pwscf_output/LiH-gamma.pwscf.h5" in refs["wavefunction_hrefs"]
        assert "Li.xml" in refs["pseudopotential_hrefs"]
        assert "H.xml" in refs["pseudopotential_hrefs"]

    def test_single_qmc_block(self, parsed):
        qmc = parsed["params"]["qmc"]
        assert len(qmc) == 1
        assert qmc[0]["method"] == "vmc"

    def test_roundtrip(self):
        text = _read_sample("lih_qe_workflow")
        p1 = _parse_qmcpack_text(text)
        w = _write_qmcpack_text(p1)
        p2 = _parse_qmcpack_text(w)
        _assert_semantic_equal(p1, p2)


# ---------------------------------------------------------------------------
# Metadata module tests
# ---------------------------------------------------------------------------

class TestQMCPACKMetadata:
    def test_load_metadata(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import (
            safe_load_metadata,
        )
        data = safe_load_metadata()
        assert data["schema_version"] == 1
        assert data["engine"] == "qmcpack"
        assert len(data["tags"]) >= 50

    def test_get_tag_info(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import get_tag_info
        info = get_tag_info("vmc_blocks")
        assert info is not None
        assert info["category"] == "vmc"

    def test_get_tag_info_case_insensitive(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import get_tag_info
        info = get_tag_info("VMC_BLOCKS")
        assert info is not None

    def test_get_tag_info_unknown(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import get_tag_info
        assert get_tag_info("nonexistent_tag_xyz") is None

    def test_list_tags(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 50
        assert "vmc_blocks" in tags

    def test_list_tags_by_category(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import list_tags
        vmc_tags = list_tags(category="vmc")
        assert len(vmc_tags) >= 3
        assert "vmc_blocks" in vmc_tags

    def test_list_categories(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import list_categories
        cats = list_categories()
        assert "qmc" in cats
        assert "cell" in cats
        assert "wavefunction" in cats

    def test_validate_params_known(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import validate_params
        unknown = validate_params({"blocks": "100", "steps": "50"})
        assert unknown == []

    def test_validate_params_unknown(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import validate_params
        unknown = validate_params({"blocks": "100", "bogus_param_xyz": "1"})
        assert "bogus_param_xyz" in unknown

    def test_validate_params_skips_private(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import validate_params
        unknown = validate_params({"_internal": "x", "blocks": "100"})
        assert unknown == []

    def test_get_metadata_file_info(self):
        from quantumvitas.drivers.qmcpack.data.qmcpack_metadata import (
            get_metadata_file_info,
        )
        info = get_metadata_file_info()
        assert info["schema_version"] == 1
        assert info["tag_count"] >= 50
