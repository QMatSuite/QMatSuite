"""Tests for Wannier90 curated case library.

Validates that all curated samples parse, have case.yaml, and roundtrip cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qmatsuite.drivers.w90.inputspec import _parse_win_text, _write_win_text

SAMPLES_DIR = Path(__file__).parents[2] / "inputformat" / "samples" / "w90"

# All curated case directories
CASE_DIRS = sorted(
    d for d in SAMPLES_DIR.iterdir()
    if d.is_dir() and not d.name.startswith(".")
)

CASE_IDS = [d.name for d in CASE_DIRS]

REQUIRED_CASE_YAML_FIELDS = {"case_id", "title", "engine", "workflow_tags", "species", "description"}


# ──────────────────────────────────────────────────────────────────────────
# Structure validation
# ──────────────────────────────────────────────────────────────────────────


class TestCaseLibraryStructure:
    """Validate the curated case library structure."""

    def test_minimum_case_count(self):
        """At least 8 curated cases exist (playbook requirement)."""
        assert len(CASE_DIRS) >= 8, (
            f"Only {len(CASE_DIRS)} curated cases found, need >= 8"
        )

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_case_has_win_file(self, case_dir: Path):
        """Each case has a wannier90.win file."""
        win = case_dir / "wannier90.win"
        assert win.exists(), f"Missing wannier90.win in {case_dir.name}"

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_case_has_case_yaml(self, case_dir: Path):
        """Each case has a case.yaml file."""
        cy = case_dir / "case.yaml"
        assert cy.exists(), f"Missing case.yaml in {case_dir.name}"

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_case_yaml_schema(self, case_dir: Path):
        """case.yaml has all required fields."""
        cy = case_dir / "case.yaml"
        if not cy.exists():
            pytest.skip("No case.yaml")
        data = yaml.safe_load(cy.read_text(encoding="utf-8"))
        missing = REQUIRED_CASE_YAML_FIELDS - set(data.keys())
        assert not missing, f"case.yaml in {case_dir.name} missing: {missing}"

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_case_yaml_engine(self, case_dir: Path):
        """case.yaml engine field is 'w90'."""
        cy = case_dir / "case.yaml"
        if not cy.exists():
            pytest.skip("No case.yaml")
        data = yaml.safe_load(cy.read_text(encoding="utf-8"))
        assert data["engine"] == "w90"

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_case_yaml_id_matches_dir(self, case_dir: Path):
        """case.yaml case_id matches the directory name."""
        cy = case_dir / "case.yaml"
        if not cy.exists():
            pytest.skip("No case.yaml")
        data = yaml.safe_load(cy.read_text(encoding="utf-8"))
        assert data["case_id"] == case_dir.name


# ──────────────────────────────────────────────────────────────────────────
# Parse validation
# ──────────────────────────────────────────────────────────────────────────


class TestCaseParsing:
    """Validate that all curated cases parse without error."""

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_parse_no_error(self, case_dir: Path):
        """Parse the .win file without raising exceptions."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")
        result = _parse_win_text(text)
        assert "params" in result

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_parse_has_structure(self, case_dir: Path):
        """Parse produces structure data (lattice + species)."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")
        result = _parse_win_text(text)
        assert "structure" in result, f"No structure in {case_dir.name}"
        struct = result["structure"]
        assert "lattice" in struct
        assert "species" in struct
        assert len(struct["lattice"]) == 3

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_parse_has_num_wann(self, case_dir: Path):
        """Every case must specify num_wann."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")
        result = _parse_win_text(text)
        assert "num_wann" in result["params"]

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_parse_has_mp_grid(self, case_dir: Path):
        """Every case must specify mp_grid."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")
        result = _parse_win_text(text)
        assert "mp_grid" in result["params"]
        mp = result["params"]["mp_grid"]
        assert len(mp) == 3


# ──────────────────────────────────────────────────────────────────────────
# Roundtrip validation
# ──────────────────────────────────────────────────────────────────────────


class TestCaseRoundtrip:
    """Validate semantic roundtrip: parse -> write -> parse preserves data."""

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_roundtrip_params(self, case_dir: Path):
        """Parameters survive a write -> parse roundtrip."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")

        # Parse original
        result1 = _parse_win_text(text)

        # Write from parsed data
        fragment = dict(result1)
        if "structure" in result1:
            fragment.update(result1["structure"])
        written = _write_win_text(fragment)

        # Re-parse
        result2 = _parse_win_text(written)

        # Compare key parameters
        for key in ("num_wann", "num_iter", "mp_grid"):
            if key in result1["params"]:
                assert result1["params"][key] == result2["params"][key], (
                    f"Roundtrip mismatch for {key} in {case_dir.name}: "
                    f"{result1['params'][key]} != {result2['params'][key]}"
                )

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_roundtrip_species(self, case_dir: Path):
        """Species survive a write -> parse roundtrip."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")

        result1 = _parse_win_text(text)
        fragment = dict(result1)
        if "structure" in result1:
            fragment.update(result1["structure"])
        written = _write_win_text(fragment)
        result2 = _parse_win_text(written)

        assert result1["structure"]["species"] == result2["structure"]["species"], (
            f"Species mismatch in {case_dir.name}"
        )

    @pytest.mark.parametrize("case_dir", CASE_DIRS, ids=CASE_IDS)
    def test_roundtrip_lattice(self, case_dir: Path):
        """Lattice vectors survive roundtrip (within tolerance)."""
        win = case_dir / "wannier90.win"
        text = win.read_text(encoding="utf-8")

        result1 = _parse_win_text(text)
        fragment = dict(result1)
        if "structure" in result1:
            fragment.update(result1["structure"])
        written = _write_win_text(fragment)
        result2 = _parse_win_text(written)

        lat1 = result1["structure"]["lattice"]
        lat2 = result2["structure"]["lattice"]
        for i in range(3):
            for j in range(3):
                assert abs(lat1[i][j] - lat2[i][j]) < 1e-6, (
                    f"Lattice mismatch at [{i}][{j}] in {case_dir.name}: "
                    f"{lat1[i][j]} vs {lat2[i][j]}"
                )
