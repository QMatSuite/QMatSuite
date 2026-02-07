"""Tests for LAMMPS command metadata catalog and access layer.

Validates the JSON catalog structure and the lammps_metadata.py access API.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────────
# JSON catalog validation (Phase 1)
# ──────────────────────────────────────────────────────────────────────────

VALID_TYPES = {"command", "style", "setting"}

VALID_CATEGORIES = {
    "setup", "lattice_geometry", "potential", "bonded_interaction",
    "fix", "compute", "output", "run_control", "io",
    "neighbor", "group", "variable", "atom_manipulation",
}

REQUIRED_FIELDS = {"name", "type", "default", "category", "description", "status"}


@pytest.fixture(scope="module")
def raw_catalog() -> dict:
    """Load the raw JSON catalog."""
    data_path = resources.files("quantumvitas.drivers.lammps.data").joinpath(
        "lammps_commands.json"
    )
    with resources.as_file(data_path) as path:
        return json.loads(Path(path).read_text(encoding="utf-8"))


class TestLAMMPSCatalogJSON:
    """Validate lammps_commands.json structure."""

    def test_json_loads_valid(self, raw_catalog):
        """JSON parses without error and has expected top-level keys."""
        assert "schema_version" in raw_catalog
        assert "commands" in raw_catalog
        assert raw_catalog["engine"] == "lammps"

    def test_command_count_minimum(self, raw_catalog):
        """Catalog has 100+ commands (playbook requirement for classical MD)."""
        assert len(raw_catalog["commands"]) >= 100

    def test_required_fields_present(self, raw_catalog):
        """Every command has the required fields."""
        for cmd_name, cmd in raw_catalog["commands"].items():
            missing = REQUIRED_FIELDS - set(cmd.keys())
            assert not missing, f"Command {cmd_name} missing fields: {missing}"

    def test_type_enum_valid(self, raw_catalog):
        """Every command type is in the valid set."""
        for cmd_name, cmd in raw_catalog["commands"].items():
            assert cmd["type"] in VALID_TYPES, (
                f"Command {cmd_name} has invalid type: {cmd['type']}"
            )

    def test_category_valid(self, raw_catalog):
        """Every command category is in the valid set."""
        for cmd_name, cmd in raw_catalog["commands"].items():
            assert cmd["category"] in VALID_CATEGORIES, (
                f"Command {cmd_name} has invalid category: {cmd['category']}"
            )

    def test_no_duplicate_commands(self, raw_catalog):
        """No duplicate command names (JSON keys are unique by spec)."""
        for key, cmd in raw_catalog["commands"].items():
            assert cmd["name"] == key, (
                f"Command key {key} != name field {cmd['name']}"
            )

    def test_see_also_is_list(self, raw_catalog):
        """Every command's see_also is a list."""
        for cmd_name, cmd in raw_catalog["commands"].items():
            assert isinstance(cmd.get("see_also", []), list), (
                f"Command {cmd_name} see_also is not a list"
            )

    def test_core_commands_present(self, raw_catalog):
        """Core LAMMPS commands are in the catalog."""
        core = [
            "units", "atom_style", "boundary", "dimension",
            "pair_style", "pair_coeff", "fix", "compute",
            "run", "minimize", "thermo", "timestep",
            "read_data", "write_data", "dump",
        ]
        commands = raw_catalog["commands"]
        for cmd in core:
            assert cmd in commands, f"Core command {cmd} missing from catalog"


# ──────────────────────────────────────────────────────────────────────────
# Metadata access layer (Phase 2)
# ──────────────────────────────────────────────────────────────────────────


class TestMetadataAccessLayer:
    """Test lammps_metadata.py API."""

    def test_safe_load_metadata(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import safe_load_metadata
        data = safe_load_metadata()
        assert "commands" in data
        assert len(data["commands"]) >= 100

    def test_get_tag_info_units(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_tag_info
        info = get_tag_info("units")
        assert info is not None
        assert info["type"] == "command"
        assert info["category"] == "setup"

    def test_get_tag_info_case_insensitive(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_tag_info
        info = get_tag_info("UNITS")
        assert info is not None
        assert info["name"] == "units"

    def test_get_tag_info_missing(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_tag_info
        info = get_tag_info("nonexistent_command_xyz")
        assert info is None

    def test_list_tags_all(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import list_tags
        tags = list_tags()
        assert len(tags) >= 100
        assert "units" in tags
        assert "run" in tags

    def test_list_tags_by_category(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import list_tags
        setup_tags = list_tags(category="setup")
        assert len(setup_tags) >= 3
        assert "units" in setup_tags
        assert "run" not in setup_tags  # run_control

    def test_list_categories(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import list_categories
        cats = list_categories()
        assert len(cats) >= 10
        assert "setup" in cats
        assert "potential" in cats
        assert "fix" in cats

    def test_validate_params_all_valid(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import validate_params
        unknowns = validate_params({"units": "metal", "run": 1000, "thermo": 100})
        assert unknowns == []

    def test_validate_params_unknown_flagged(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import validate_params
        unknowns = validate_params({"units": "metal", "fakecmd": 42})
        assert "fakecmd" in unknowns
        assert "units" not in unknowns

    def test_validate_params_ignores_internal_keys(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import validate_params
        unknowns = validate_params({
            "units": "metal",
            "_commands": [],
            "_variables": {},
        })
        assert unknowns == []

    def test_reload_metadata(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import (
            reload_metadata, safe_load_metadata,
        )
        reload_metadata()
        data = safe_load_metadata()
        assert len(data["commands"]) >= 100

    def test_metadata_debug_info(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_metadata_file_info
        info = get_metadata_file_info()
        assert "metadata_path_abs" in info
        assert "schema_version" in info

    def test_get_tag_type(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_tag_type
        assert get_tag_type("units") == "command"
        assert get_tag_type("pair_style") == "style"
        assert get_tag_type("nonexistent") is None

    def test_get_tag_default(self):
        from quantumvitas.drivers.lammps.data.lammps_metadata import get_tag_default
        default = get_tag_default("units")
        assert default is not None  # "lj"
        assert get_tag_default("nonexistent") is None
