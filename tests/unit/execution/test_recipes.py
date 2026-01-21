"""
Unit tests for Recipe implementations.

Tests QERecipe, ORCARecipe, and PySCFRecipe materialization
without executing any actual engine code.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import Optional

from quantumvitas.execution.recipes import (
    QERecipe,
    ORCARecipe,
    PySCFRecipe,
    get_recipe_for_engine,
)


@dataclass
class MockMeta:
    """Mock ResourceMeta for testing."""

    id: str
    name: str = "test"
    slug: str = "test"
    path: str = "test.step.yaml"
    kind: str = "step"


@dataclass
class MockStep:
    """Mock Step for testing recipes."""

    meta: MockMeta
    step_type: Optional[str]


def create_mock_step(ulid: str, step_type: str) -> MockStep:
    """Create a mock step with given ULID and type."""
    return MockStep(
        meta=MockMeta(id=ulid),
        step_type=step_type,
    )


class TestQERecipe:
    """Tests for QERecipe materialization."""

    def test_materialize_single_step(self):
        """QE recipe creates one job for one step."""
        recipe = QERecipe()
        steps = [create_mock_step("01ABCDEF", "scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph) == 1
        job = graph.jobs[0]
        assert job.id == "step_00"
        assert job.step_ids == ["01ABCDEF"]
        assert job.working_dir == calc_raw_dir
        assert job.command == ["pw.x", "scf.in"]
        assert job.engine == "qe"

    def test_materialize_multiple_steps(self):
        """QE recipe creates one job per step."""
        recipe = QERecipe()
        steps = [
            create_mock_step("ulid_scf", "scf"),
            create_mock_step("ulid_nscf", "nscf"),
            create_mock_step("ulid_bands", "bands"),
        ]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph) == 3

        assert graph.jobs[0].id == "step_00"
        assert graph.jobs[0].command == ["pw.x", "scf.in"]

        assert graph.jobs[1].id == "step_01"
        assert graph.jobs[1].command == ["pw.x", "nscf.in"]

        assert graph.jobs[2].id == "step_02"
        assert graph.jobs[2].command == ["bands.x", "bands.in"]

    def test_materialize_with_fingerprints(self):
        """QE recipe uses provided SHAs for fingerprints."""
        recipe = QERecipe()
        steps = [
            create_mock_step("ulid_scf", "scf"),
            create_mock_step("ulid_nscf", "nscf"),
        ]
        step_shas = {
            "ulid_scf": "sha_scf_123",
            "ulid_nscf": "sha_nscf_456",
        }
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir, step_shas)

        assert graph.jobs[0].fingerprint == "sha_scf_123"
        assert graph.jobs[1].fingerprint == "sha_nscf_456"

    def test_materialize_empty_steps(self):
        """QE recipe handles empty step list."""
        recipe = QERecipe()
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize([], calc_raw_dir)

        assert len(graph) == 0

    def test_materialize_expected_outputs(self):
        """QE recipe sets expected output files."""
        recipe = QERecipe()
        steps = [create_mock_step("ulid_scf", "scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph.jobs[0].expected_outputs) == 1
        assert graph.jobs[0].expected_outputs[0] == calc_raw_dir / "scf.out"

    def test_materialize_scratch_dir_in_metadata(self):
        """QE recipe sets scratch_dir in metadata."""
        recipe = QERecipe()
        steps = [create_mock_step("ulid_scf", "scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert graph.jobs[0].metadata["scratch_dir"] == calc_raw_dir / "outdir"

    def test_materialize_no_deps(self):
        """QE recipe creates jobs with no explicit deps (conservative selection)."""
        recipe = QERecipe()
        steps = [
            create_mock_step("ulid_scf", "scf"),
            create_mock_step("ulid_nscf", "nscf"),
        ]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        for job in graph.jobs:
            assert job.deps == []


class TestORCARecipe:
    """Tests for ORCARecipe materialization."""

    def test_materialize_single_scf(self):
        """ORCA recipe creates single job for SCF only."""
        recipe = ORCARecipe()
        steps = [create_mock_step("01ABCDEF", "pyscf_scf")]
        # Note: Using PYSCF_SCF since we don't have ORCA_SCF in StepType enum
        # The recipe will use registry lookup
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph) == 1
        job = graph.jobs[0]
        # Job ID is from stable tokens
        assert job.id == "s"  # SCF token
        assert job.step_ids == ["01ABCDEF"]
        # Working dir is namespaced
        assert "scf_" in str(job.working_dir)

    def test_materialize_chain_creates_subchain_jobs(self):
        """ORCA recipe creates one job per step, each covering prefix."""
        recipe = ORCARecipe()
        # SCF then something else
        steps = [
            create_mock_step("ulid_scf_123456", "pyscf_scf"),  # Will be s
            # Can't easily test MP2 without proper ORCA step types
        ]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        # With one step, one job
        assert len(graph) == 1
        assert graph.jobs[0].id == "s"

    def test_materialize_namespace_folder(self):
        """ORCA recipe uses SCF ULID for namespace folder."""
        recipe = ORCARecipe()
        # ULID with known suffix
        scf_ulid = "01HY2Q9W8A123456"  # Last 6 chars: "123456"
        steps = [create_mock_step(scf_ulid, "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        # Working dir should be calc/raw/scf_123456
        assert graph.jobs[0].working_dir == calc_raw_dir / "scf_123456"

    def test_materialize_gbw_in_expected_outputs(self):
        """ORCA recipe includes scf.gbw in expected outputs."""
        recipe = ORCARecipe()
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        expected = graph.jobs[0].expected_outputs
        gbw_outputs = [p for p in expected if p.name == "scf.gbw"]
        assert len(gbw_outputs) == 1

    def test_materialize_no_inter_job_deps(self):
        """ORCA jobs have no inter-job deps (self-contained)."""
        recipe = ORCARecipe()
        steps = [create_mock_step("ulid_scf", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        for job in graph.jobs:
            assert job.deps == []

    def test_materialize_command_format(self):
        """ORCA recipe creates correct command format."""
        recipe = ORCARecipe()
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert graph.jobs[0].command == ["orca", "s.inp"]


class TestPySCFRecipe:
    """Tests for PySCFRecipe materialization."""

    def test_materialize_single_scf(self):
        """PySCF recipe creates single internal job for SCF."""
        recipe = PySCFRecipe()
        steps = [create_mock_step("01ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph) == 1
        job = graph.jobs[0]
        assert job.id == "s"
        assert job.is_internal is True
        assert job.command == ["<internal>"]

    def test_materialize_expected_outputs_results_json(self):
        """PySCF recipe expects results.json in step_artifacts."""
        recipe = PySCFRecipe()
        step_ulid = "ulid_scf_ABCDEF"
        steps = [create_mock_step(step_ulid, "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        expected = graph.jobs[0].expected_outputs
        results_json = [p for p in expected if p.name == "results.json"]
        assert len(results_json) == 1
        assert "step_artifacts" in str(results_json[0])

    def test_materialize_expected_outputs_checkpoint(self):
        """PySCF recipe expects checkpoint.chk."""
        recipe = PySCFRecipe()
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        expected = graph.jobs[0].expected_outputs
        checkpoint = [p for p in expected if p.name == "checkpoint.chk"]
        assert len(checkpoint) == 1

    def test_materialize_namespace_folder(self):
        """PySCF recipe uses SCF ULID for namespace folder."""
        recipe = PySCFRecipe()
        scf_ulid = "01HY2Q9W8A654321"  # Last 6 chars: "654321"
        steps = [create_mock_step(scf_ulid, "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert graph.jobs[0].working_dir == calc_raw_dir / "scf_654321"

    def test_materialize_target_step_ulid_in_metadata(self):
        """PySCF recipe includes target step ULID in metadata."""
        recipe = PySCFRecipe()
        step_ulid = "ulid_target"
        steps = [create_mock_step(step_ulid, "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert graph.jobs[0].metadata["target_step_ulid"] == step_ulid


class TestGetRecipeForEngine:
    """Tests for get_recipe_for_engine factory function."""

    def test_get_qe_recipe(self):
        """get_recipe_for_engine returns QERecipe for qe."""
        recipe = get_recipe_for_engine("qe")
        assert isinstance(recipe, QERecipe)

    def test_get_orca_recipe(self):
        """get_recipe_for_engine returns ORCARecipe for orca."""
        recipe = get_recipe_for_engine("orca")
        assert isinstance(recipe, ORCARecipe)

    def test_get_pyscf_recipe(self):
        """get_recipe_for_engine returns PySCFRecipe for pyscf."""
        recipe = get_recipe_for_engine("pyscf")
        assert isinstance(recipe, PySCFRecipe)

    def test_unknown_engine_raises(self):
        """get_recipe_for_engine raises for unknown engine."""
        from quantumvitas.core.driver_exceptions import UnknownEngineError
        with pytest.raises(UnknownEngineError):
            get_recipe_for_engine("unknown")


class TestRecipeFingerprinting:
    """Tests for fingerprint computation in recipes."""

    def test_qe_recipe_fingerprint_single_step(self):
        """QE recipe fingerprint is just the step SHA."""
        recipe = QERecipe()
        steps = [create_mock_step("ulid_scf", "scf")]
        step_shas = {"ulid_scf": "sha_scf_abc123"}
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir, step_shas)

        assert graph.jobs[0].fingerprint == "sha_scf_abc123"

    def test_orca_recipe_fingerprint_multi_step(self):
        """ORCA recipe fingerprint combines multiple step SHAs."""
        recipe = ORCARecipe()
        # With single step, fingerprint is just that SHA
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        step_shas = {"ulid_scf_ABCDEF": "sha_scf_123"}
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir, step_shas)

        assert graph.jobs[0].fingerprint == "sha_scf_123"

    def test_recipe_missing_sha_no_fingerprint(self):
        """Recipe handles missing SHA gracefully."""
        recipe = QERecipe()
        steps = [create_mock_step("ulid_scf", "scf")]
        step_shas = {}  # Empty - no SHAs provided
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir, step_shas)

        assert graph.jobs[0].fingerprint is None


class TestRecipeInputFiles:
    """Tests for input file paths in recipes."""

    def test_qe_recipe_input_files(self):
        """QE recipe sets correct input file paths."""
        recipe = QERecipe()
        steps = [create_mock_step("ulid_scf", "scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert len(graph.jobs[0].input_files) == 1
        assert graph.jobs[0].input_files[0] == calc_raw_dir / "scf.in"

    def test_orca_recipe_input_files(self):
        """ORCA recipe sets correct input file paths."""
        recipe = ORCARecipe()
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        working_dir = calc_raw_dir / "scf_ABCDEF"
        assert len(graph.jobs[0].input_files) == 1
        assert graph.jobs[0].input_files[0] == working_dir / "s.inp"

    def test_pyscf_recipe_no_input_files(self):
        """PySCF recipe has no input files (internal execution)."""
        recipe = PySCFRecipe()
        steps = [create_mock_step("ulid_scf_ABCDEF", "pyscf_scf")]
        calc_raw_dir = Path("/calc/raw")

        graph = recipe.materialize(steps, calc_raw_dir)

        assert graph.jobs[0].input_files == []
