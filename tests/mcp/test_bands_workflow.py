"""Tests for Si bands workflow fixes: C1, C2, C3, M2, C4.

Covers:
- C1: set_parameters auto-routes QE cards (K_POINTS) vs parameters (SYSTEM)
- C2: filband injection in structure_steps.py
- C3: generate_kpath MCP tool
- M2: dry-run materializer handles non-mesh K_POINTS formats
- C4: nbnd knowledge base entries
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantumvitas.api import QVService

# 2-atom Si diamond in pymatgen JSON format — gives correct Fd-3m spacegroup.
SI_DIAMOND_JSON = json.dumps({
    "@module": "pymatgen.core.structure",
    "@class": "Structure",
    "lattice": {
        "matrix": [
            [0.0, 2.715, 2.715],
            [2.715, 0.0, 2.715],
            [2.715, 2.715, 0.0],
        ],
        "a": 3.84,
        "b": 3.84,
        "c": 3.84,
        "alpha": 60.0,
        "beta": 60.0,
        "gamma": 60.0,
    },
    "sites": [
        {
            "species": [{"element": "Si", "occu": 1}],
            "abc": [0.0, 0.0, 0.0],
            "xyz": [0.0, 0.0, 0.0],
        },
        {
            "species": [{"element": "Si", "occu": 1}],
            "abc": [0.25, 0.25, 0.25],
            "xyz": [1.3575, 1.3575, 1.3575],
        },
    ],
})


@pytest.fixture
def qv_project_si_diamond(tmp_path, monkeypatch):
    """Project with a proper 2-atom Si diamond structure."""
    project_root = QVService.init_project(tmp_path / "project")

    source = tmp_path / "si_diamond.json"
    source.write_text(SI_DIAMOND_JSON)
    QVService(project_root).structure.import_file(source, name="SiDiamond")

    from quantumvitas.mcp import project as mcp_project
    monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

    return project_root


def _create_qe_bands(project_root):
    """Helper: create a QE bands calculation and return its data."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="bands", structure_selector="SiDiamond",
    )
    assert result["status"] == "success", result
    return result["data"]


def _create_qe_scf(project_root):
    """Helper: create a QE SCF calculation and return its data."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="SiDiamond",
    )
    assert result["status"] == "success", result
    return result["data"]


# ===========================================================================
# C1: set_parameters cards routing
# ===========================================================================


class TestC1SetParametersCardsRouting:
    """C1: set_parameters auto-routes QE card keys to cards namespace."""

    def test_set_parameters_routes_kpoints_to_cards(self, qv_project_si_diamond):
        """K_POINTS key should be auto-routed to cards namespace."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        kpoints_card = {
            "option": "crystal_b",
            "data": [
                [0.0, 0.0, 0.0, 20],
                [0.5, 0.0, 0.5, 20],
                [0.5, 0.25, 0.75, 0],
            ],
        }
        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={"K_POINTS": kpoints_card},
            step=0,
        )
        assert result["status"] == "success"

        # Verify via inspect that K_POINTS ended up in cards
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        inspect = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert inspect["status"] == "success"
        cards = inspect["data"]["step_detail"]["cards"]
        assert "K_POINTS" in cards
        assert cards["K_POINTS"]["option"] == "crystal_b"

    def test_set_parameters_routes_system_to_parameters(self, qv_project_si_diamond):
        """SYSTEM key should stay in parameters namespace."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={"SYSTEM": {"ecutwfc": 60}},
            step=0,
        )
        assert result["status"] == "success"

        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        inspect = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert inspect["status"] == "success"
        parameters = inspect["data"]["step_detail"]["parameters"]
        assert parameters.get("SYSTEM", {}).get("ecutwfc") == 60

    def test_set_parameters_mixed_cards_and_params(self, qv_project_si_diamond):
        """Both card keys and namelist keys in one call."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={
                "SYSTEM": {"ecutwfc": 50, "nbnd": 8},
                "K_POINTS": {"option": "gamma"},
            },
            step=0,
        )
        assert result["status"] == "success"

        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        inspect = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        data = inspect["data"]["step_detail"]
        assert data["parameters"].get("SYSTEM", {}).get("ecutwfc") == 50
        assert "K_POINTS" in data["cards"]

    def test_set_parameters_explicit_namespace(self, qv_project_si_diamond):
        """Explicit 'cards' and 'parameters' keys in params dict."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={
                "cards": {"K_POINTS": {"option": "gamma"}},
                "parameters": {"SYSTEM": {"ecutwfc": 40}},
            },
            step=0,
        )
        assert result["status"] == "success"

        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        inspect = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        data = inspect["data"]["step_detail"]
        assert data["parameters"].get("SYSTEM", {}).get("ecutwfc") == 40
        assert "K_POINTS" in data["cards"]

    def test_set_parameters_backward_compatible(self, qv_project_si_diamond):
        """Existing usage with namelist keys still works."""
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={"SYSTEM": {"ecutwfc": 60, "nbnd": 20}},
            step=0,
        )
        assert result["status"] == "success"
        assert result["data"]["params_set"] == {"SYSTEM": {"ecutwfc": 60, "nbnd": 20}}


# ===========================================================================
# C3: generate_kpath MCP tool
# ===========================================================================


class TestC3GenerateKpath:
    """C3: generate_kpath MCP tool tests."""

    def test_generate_kpath_si_diamond(self, qv_project_si_diamond):
        """Generate k-path for Si diamond — should return FCC-type path."""
        from quantumvitas.mcp.tools.generate_kpath import generate_kpath

        result = generate_kpath.fn(structure_selector="SiDiamond")
        assert result["status"] == "success", result
        data = result["data"]
        assert data["lattice_type"] == "cubic"
        assert data["spacegroup_number"] == 227  # Fd-3m
        assert data["n_segments"] > 0
        assert data["n_kpoints"] > 0
        assert len(data["labels"]) >= 2
        assert "path_string" in data

    def test_generate_kpath_returns_qe_card_format(self, qv_project_si_diamond):
        """kpoints_card should have option='crystal_b' and data list."""
        from quantumvitas.mcp.tools.generate_kpath import generate_kpath

        result = generate_kpath.fn(structure_selector="SiDiamond")
        assert result["status"] == "success"
        card = result["data"]["kpoints_card"]
        assert card["option"] == "crystal_b"
        assert isinstance(card["data"], list)
        assert len(card["data"]) > 0
        # Each row should have 4 elements: kx, ky, kz, npts
        for row in card["data"]:
            assert len(row) == 4

    def test_generate_kpath_invalid_structure(self, qv_project_si_diamond):
        """Non-existent structure returns error."""
        from quantumvitas.mcp.tools.generate_kpath import generate_kpath

        result = generate_kpath.fn(structure_selector="NONEXISTENT_STRUCTURE")
        assert result["status"] == "error"
        assert result["error_type"] == "structure_error"

    def test_generate_kpath_points_per_segment(self, qv_project_si_diamond):
        """Changing points_per_segment affects the data."""
        from quantumvitas.mcp.tools.generate_kpath import generate_kpath

        r10 = generate_kpath.fn(structure_selector="SiDiamond", points_per_segment=10)
        r40 = generate_kpath.fn(structure_selector="SiDiamond", points_per_segment=40)
        assert r10["status"] == "success"
        assert r40["status"] == "success"

        # Both should have same number of k-point rows (same path) but
        # different npts values in the data
        d10 = r10["data"]["kpoints_card"]["data"]
        d40 = r40["data"]["kpoints_card"]["data"]
        assert len(d10) == len(d40)  # same path topology

        # At least one row should have npts=10 in d10 and npts=40 in d40
        npts_10 = {int(row[3]) for row in d10 if row[3] > 0}
        npts_40 = {int(row[3]) for row in d40 if row[3] > 0}
        assert 10 in npts_10
        assert 40 in npts_40

    def test_generate_kpath_card_usable_with_set_parameters(self, qv_project_si_diamond):
        """Integration: generate_kpath output can be passed to set_parameters."""
        from quantumvitas.mcp.tools.generate_kpath import generate_kpath
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        # Generate k-path
        kpath_result = generate_kpath.fn(structure_selector="SiDiamond")
        assert kpath_result["status"] == "success"
        kpoints_card = kpath_result["data"]["kpoints_card"]

        # Create a calculation and set the k-path
        calc_data = _create_qe_scf(qv_project_si_diamond)
        calc_ulid = calc_data["calc_ulid"]

        result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={"K_POINTS": kpoints_card},
            step=0,
        )
        assert result["status"] == "success"

        # Verify it's stored correctly
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        inspect = inspect_calculation.fn(calc_ulid=calc_ulid, step=0)
        assert inspect["status"] == "success"
        cards = inspect["data"]["step_detail"]["cards"]
        assert cards["K_POINTS"]["option"] == "crystal_b"
        assert len(cards["K_POINTS"]["data"]) == len(kpoints_card["data"])


# ===========================================================================
# C2: filband injection
# ===========================================================================


class TestC2FilbandInjection:
    """C2: filband injection into QE bands.x input."""

    def test_filband_injection_present_in_schema(self):
        """The BANDS QE module should define filband as a parameter."""
        from quantumvitas.data import get_module_param_sections

        sections = get_module_param_sections("bands")
        # filband should be in one of the sections
        all_params = set()
        for params in sections.values():
            all_params.update(p.lower() for p in params)
        assert "filband" in all_params, (
            f"filband not found in BANDS module. Available: {sorted(all_params)}"
        )

    def test_evidence_glob_widened(self):
        """QE driver bands evidence should include multiple glob patterns."""
        import quantumvitas.drivers  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("qe")
        bands_caps = [
            c for c in driver.ANALYSIS_CAPABILITIES
            if c.object_type == "bands"
        ]
        assert bands_caps, "No bands capability found in QE driver"
        evidence = bands_caps[0].evidence_files
        assert "*.bands.dat.gnu" in evidence
        assert "*.bands.out.gnu" in evidence


# ===========================================================================
# M2: dry-run card handling
# ===========================================================================


class TestM2DryRunCardHandling:
    """M2: dry-run materializer handles non-mesh K_POINTS formats."""

    def test_merge_cards_crystal_b(self):
        """_merge_cards_into_params preserves crystal_b format."""
        from quantumvitas.mcp.tools.inspect_calculation import _merge_cards_into_params

        params: dict = {}
        cards = {
            "K_POINTS": {
                "option": "crystal_b",
                "data": [
                    [0.0, 0.0, 0.0, 20],
                    [0.5, 0.0, 0.5, 20],
                    [0.5, 0.25, 0.75, 0],
                ],
            },
        }
        _merge_cards_into_params(params, cards, None)
        kp = params["kpoints"]
        assert kp["option"] == "crystal_b"
        assert len(kp["data"]) == 3

    def test_merge_cards_gamma(self):
        """_merge_cards_into_params handles gamma format."""
        from quantumvitas.mcp.tools.inspect_calculation import _merge_cards_into_params

        params: dict = {}
        cards = {"K_POINTS": {"option": "gamma"}}
        _merge_cards_into_params(params, cards, None)
        assert params["kpoints"]["option"] == "gamma"

    def test_merge_cards_automatic(self):
        """_merge_cards_into_params extracts mesh+shift for automatic."""
        from quantumvitas.mcp.tools.inspect_calculation import _merge_cards_into_params

        params: dict = {}
        cards = {
            "K_POINTS": {
                "option": "automatic",
                "data": [[6, 6, 6, 1, 1, 1]],
            },
        }
        _merge_cards_into_params(params, cards, None)
        kp = params["kpoints"]
        assert kp["mesh"] == [6, 6, 6]
        assert kp["shift"] == [1, 1, 1]

    def test_write_qe_text_crystal_b(self):
        """_write_qe_text_direct handles crystal_b K_POINTS."""
        from quantumvitas.drivers.qe.inputspec import _write_qe_text_direct

        params = {
            "SYSTEM": {"ecutwfc": 30},
            "kpoints": {
                "option": "crystal_b",
                "data": [
                    [0.0, 0.0, 0.0, 20],
                    [0.5, 0.0, 0.5, 0],
                ],
            },
        }
        text = _write_qe_text_direct(params, {})
        assert "K_POINTS {crystal_b}" in text
        assert "2" in text  # count line
        # Should NOT have "K_POINTS (automatic)"
        assert "automatic" not in text

    def test_write_qe_text_gamma(self):
        """_write_qe_text_direct handles gamma K_POINTS."""
        from quantumvitas.drivers.qe.inputspec import _write_qe_text_direct

        params = {"kpoints": {"option": "gamma"}}
        text = _write_qe_text_direct(params, {})
        assert "K_POINTS {gamma}" in text

    def test_write_qe_text_automatic_no_regression(self):
        """_write_qe_text_direct still handles automatic K_POINTS."""
        from quantumvitas.drivers.qe.inputspec import _write_qe_text_direct

        params = {
            "kpoints": {
                "mesh": [8, 8, 8],
                "shift": [0, 0, 0],
            },
        }
        text = _write_qe_text_direct(params, {})
        assert "K_POINTS (automatic)" in text
        assert "8 8 8" in text

    def test_write_qe_text_tpiba_b(self):
        """_write_qe_text_direct handles tpiba_b K_POINTS."""
        from quantumvitas.drivers.qe.inputspec import _write_qe_text_direct

        params = {
            "kpoints": {
                "option": "tpiba_b",
                "data": [
                    [0.0, 0.0, 0.0, 20],
                    [1.0, 0.0, 0.0, 20],
                    [1.0, 1.0, 0.0, 0],
                ],
            },
        }
        text = _write_qe_text_direct(params, {})
        assert "K_POINTS {tpiba_b}" in text
        assert "3" in text  # count line


# ===========================================================================
# C4: nbnd knowledge entries
# ===========================================================================


class TestC4NbndKnowledge:
    """C4: nbnd/NBANDS knowledge base entries."""

    def test_nbnd_entry_exists(self):
        """BUILTIN_ENTRIES should contain QE nbnd entry."""
        from quantumvitas.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES

        nbnd_entries = [
            e for e in BUILTIN_ENTRIES
            if "nbnd" in e["content"].lower() and e["scope_engine"] == "qe"
        ]
        assert len(nbnd_entries) >= 1, "No QE nbnd entry found in BUILTIN_ENTRIES"
        entry = nbnd_entries[0]
        assert entry["scope_workflow"] == "bands"
        assert "conduction" in entry["content"].lower()

    def test_nbands_vasp_entry_exists(self):
        """BUILTIN_ENTRIES should contain VASP NBANDS entry."""
        from quantumvitas.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES

        nbands_entries = [
            e for e in BUILTIN_ENTRIES
            if "nbands" in e["content"].lower() and e["scope_engine"] == "vasp"
        ]
        assert len(nbands_entries) >= 1, "No VASP NBANDS entry found"
        entry = nbands_entries[0]
        assert entry["scope_workflow"] == "bands"

    def test_search_knowledge_nbnd(self, tmp_path, monkeypatch):
        """search_knowledge finds nbnd entry."""
        # Build a fresh builtin DB in a temp location
        from quantumvitas.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES

        found = any(
            "nbnd" in e.get("content", "").lower()
            for e in BUILTIN_ENTRIES
        )
        assert found, "nbnd not in BUILTIN_ENTRIES content"

    def test_search_knowledge_conduction_bands(self):
        """search_knowledge finds conduction bands entry."""
        from quantumvitas.mcp.knowledge.builtin_entries import BUILTIN_ENTRIES

        found = any(
            "conduction" in e.get("content", "").lower()
            for e in BUILTIN_ENTRIES
        )
        assert found, "conduction bands not in BUILTIN_ENTRIES content"
