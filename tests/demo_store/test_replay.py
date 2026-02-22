"""Tests for the replay engine."""

from __future__ import annotations

import pytest
from pathlib import Path

from qmatsuite.demo_store.authoring_ops import (
    AddStep,
    CreateCalculation,
    ImportStructure,
    InitProject,
    SetField,
    UnsetField,
)
from qmatsuite.demo_store.replay import (
    _pointer_to_nested_dict,
    _parse_target,
    replay_ops,
)


class TestPointerToNestedDict:
    def test_single_level(self):
        result = _pointer_to_nested_dict("/input_name", "si.scf.in")
        assert result == {"input_name": "si.scf.in"}

    def test_multi_level(self):
        result = _pointer_to_nested_dict("/parameters/CONTROL/calculation", "scf")
        assert result == {"parameters": {"CONTROL": {"calculation": "scf"}}}

    def test_none_value(self):
        result = _pointer_to_nested_dict("/parameters/CONTROL", None)
        assert result == {"parameters": {"CONTROL": None}}

    def test_list_value(self):
        result = _pointer_to_nested_dict("/parameters/kpoints", [4, 4, 4])
        assert result == {"parameters": {"kpoints": [4, 4, 4]}}

    def test_invalid_pointer(self):
        with pytest.raises(ValueError, match="must start with"):
            _pointer_to_nested_dict("no_slash", "val")


class TestParseTarget:
    def test_valid_target(self):
        calc, step = _parse_target("step:my-calc/my-step")
        assert calc == "my-calc"
        assert step == "my-step"

    def test_invalid_prefix(self):
        with pytest.raises(ValueError, match="Invalid target"):
            _parse_target("calc:my-calc/my-step")

    def test_missing_slash(self):
        with pytest.raises(ValueError, match="Invalid target"):
            _parse_target("step:calcstep")


class TestReplayOps:
    def test_empty_ops_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            replay_ops([], Path("/tmp"))

    def test_missing_init_project_raises(self):
        ops = [AddStep(calc_selector="c", step_type_gen="scf", name="scf")]
        with pytest.raises(ValueError, match="First op must be InitProject"):
            replay_ops(ops, Path("/tmp"))

    def test_init_project_creates_directory(self, tmp_path):
        ops = [InitProject(name="test-project")]
        root = replay_ops(ops, tmp_path)
        assert root.exists()
        assert (root / "project.qms.yml").exists()

    def test_full_qe_scf_replay(self, tmp_path):
        """Replay a minimal QE SCF project end-to-end."""
        # Minimal Si structure in pymatgen format
        si_structure = {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "charge": 0,
            "lattice": {
                "matrix": [
                    [0.0, 2.715, 2.715],
                    [2.715, 0.0, 2.715],
                    [2.715, 2.715, 0.0],
                ],
                "pbc": [True, True, True],
            },
            "sites": [
                {
                    "species": [{"element": "Si", "occu": 1}],
                    "abc": [0.0, 0.0, 0.0],
                    "properties": {},
                    "label": "Si",
                },
                {
                    "species": [{"element": "Si", "occu": 1}],
                    "abc": [0.25, 0.25, 0.25],
                    "properties": {},
                    "label": "Si",
                },
            ],
        }

        ops = [
            InitProject(name="si-scf-test"),
            ImportStructure(name="Si", structure_data=si_structure),
            CreateCalculation(
                name="si-scf",
                engine_family="qe",
                structure_selector="si",
            ),
            AddStep(
                calc_selector="si-scf",
                step_type_gen="scf",
                name="scf",
            ),
            # Set specific parameters (leaf-level)
            SetField(
                target="step:si-scf/scf",
                pointer="/parameters/SYSTEM/ecutwfc",
                value=30,
            ),
            # Unset a default key
            UnsetField(
                target="step:si-scf/scf",
                pointer="/parameters/CONTROL/restart_mode",
            ),
        ]

        root = replay_ops(ops, tmp_path)

        # Verify project was created
        assert (root / "project.qms.yml").exists()

        # Verify structure
        structures_dir = root / "structures"
        assert structures_dir.exists()
        struct_files = list(structures_dir.glob("*.json"))
        assert len(struct_files) == 1

        # Verify calculation and step
        import yaml
        calc_dir = root / "calculations" / "si-scf"
        assert calc_dir.exists()
        calc_yaml = calc_dir / "calculation.yaml"
        assert calc_yaml.exists()
        calc_data = yaml.safe_load(calc_yaml.read_text())
        assert calc_data["engine_family"] == "qe"

        # Verify step file exists and has correct params
        step_files = list((calc_dir / "steps").glob("*.step.yaml"))
        assert len(step_files) == 1
        step_data = yaml.safe_load(step_files[0].read_text())
        assert step_data["step_type_spec"] == "qe_scf"
        assert step_data["parameters"]["SYSTEM"]["ecutwfc"] == 30
        # restart_mode should have been unset
        assert "restart_mode" not in step_data["parameters"].get("CONTROL", {})
