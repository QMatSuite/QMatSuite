"""
Unit tests for JobGraph data structures.

Tests Job and JobGraph dataclasses, fingerprint computation,
and selection mode logic.
"""

import pytest
from pathlib import Path

from quantumvitas.execution.job_graph import (
    Job,
    JobGraph,
    SelectionMode,
    compute_job_fingerprint,
)


class TestJob:
    """Tests for Job dataclass."""

    def test_job_creation_minimal(self):
        """Job can be created with minimal required fields."""
        job = Job(
            id="step_00",
            step_ids=["ulid_001"],
            working_dir=Path("/calc/raw"),
            command=["pw.x", "scf.in"],
        )

        assert job.id == "step_00"
        assert job.step_ids == ["ulid_001"]
        assert job.working_dir == Path("/calc/raw")
        assert job.command == ["pw.x", "scf.in"]
        assert job.deps == []
        assert job.fingerprint is None
        assert job.metadata == {}

    def test_job_creation_full(self):
        """Job can be created with all fields."""
        job = Job(
            id="s_m2",
            step_ids=["ulid_001", "ulid_002"],
            working_dir=Path("/calc/raw/scf_ABCDEF"),
            command=["orca", "s_m2.inp"],
            input_files=[Path("/calc/raw/scf_ABCDEF/s_m2.inp")],
            expected_outputs=[
                Path("/calc/raw/scf_ABCDEF/s_m2.out"),
                Path("/calc/raw/scf_ABCDEF/scf.gbw"),
            ],
            deps=["s"],
            fingerprint="abc123",
            metadata={"engine": "orca", "moread_file": "scf.gbw"},
        )

        assert job.id == "s_m2"
        assert len(job.step_ids) == 2
        assert job.deps == ["s"]
        assert job.fingerprint == "abc123"
        assert job.engine == "orca"
        assert job.metadata["moread_file"] == "scf.gbw"

    def test_job_engine_property(self):
        """engine property returns metadata engine value."""
        job = Job(
            id="test",
            step_ids=["ulid"],
            working_dir=Path("/tmp"),
            command=["test"],
            metadata={"engine": "pyscf"},
        )

        assert job.engine == "pyscf"

    def test_job_engine_property_missing(self):
        """engine property returns None if not set."""
        job = Job(
            id="test",
            step_ids=["ulid"],
            working_dir=Path("/tmp"),
            command=["test"],
        )

        assert job.engine is None

    def test_job_is_internal(self):
        """is_internal detects PySCF internal jobs."""
        internal_job = Job(
            id="s",
            step_ids=["ulid"],
            working_dir=Path("/tmp"),
            command=["<internal>"],
        )

        external_job = Job(
            id="s",
            step_ids=["ulid"],
            working_dir=Path("/tmp"),
            command=["orca", "s.inp"],
        )

        assert internal_job.is_internal is True
        assert external_job.is_internal is False

    def test_job_spec_step_type_property(self):
        """spec_step_type property returns metadata value."""
        job = Job(
            id="test",
            step_ids=["ulid"],
            working_dir=Path("/tmp"),
            command=["test"],
            metadata={"spec_step_type": "qe_scf"},
        )

        assert job.spec_step_type == "qe_scf"


class TestJobGraph:
    """Tests for JobGraph dataclass."""

    def _create_sample_graph(self) -> JobGraph:
        """Create a sample JobGraph for testing."""
        jobs = [
            Job(
                id="step_00",
                step_ids=["ulid_scf"],
                working_dir=Path("/calc/raw"),
                command=["pw.x", "scf.in"],
                metadata={"engine": "qe"},
            ),
            Job(
                id="step_01",
                step_ids=["ulid_nscf"],
                working_dir=Path("/calc/raw"),
                command=["pw.x", "nscf.in"],
                metadata={"engine": "qe"},
            ),
            Job(
                id="step_02",
                step_ids=["ulid_bands"],
                working_dir=Path("/calc/raw"),
                command=["bands.x", "bands.in"],
                metadata={"engine": "qe"},
            ),
        ]
        return JobGraph(jobs=jobs)

    def test_jobgraph_len(self):
        """JobGraph len returns number of jobs."""
        graph = self._create_sample_graph()
        assert len(graph) == 3

    def test_jobgraph_iter(self):
        """JobGraph is iterable."""
        graph = self._create_sample_graph()
        ids = [job.id for job in graph]
        assert ids == ["step_00", "step_01", "step_02"]

    def test_get_job_by_id(self):
        """get_job finds job by ID."""
        graph = self._create_sample_graph()

        job = graph.get_job("step_01")
        assert job is not None
        assert job.id == "step_01"
        assert job.step_ids == ["ulid_nscf"]

    def test_get_job_not_found(self):
        """get_job returns None for unknown ID."""
        graph = self._create_sample_graph()
        assert graph.get_job("nonexistent") is None

    def test_get_job_by_step_id(self):
        """get_job_by_step_id finds job containing step."""
        graph = self._create_sample_graph()

        job = graph.get_job_by_step_id("ulid_nscf")
        assert job is not None
        assert job.id == "step_01"

    def test_get_job_by_step_id_not_found(self):
        """get_job_by_step_id returns None for unknown step."""
        graph = self._create_sample_graph()
        assert graph.get_job_by_step_id("unknown_ulid") is None

    def test_get_jobs_for_target_all_mode(self):
        """ALL mode returns all jobs."""
        graph = self._create_sample_graph()

        result = graph.get_jobs_for_target("ulid_nscf", SelectionMode.ALL)
        assert len(result) == 3

    def test_get_jobs_for_target_target_mode_first(self):
        """TARGET mode for first step returns only first job."""
        graph = self._create_sample_graph()

        result = graph.get_jobs_for_target("ulid_scf", SelectionMode.TARGET)
        assert len(result) == 1
        assert result[0].id == "step_00"

    def test_get_jobs_for_target_target_mode_middle(self):
        """TARGET mode for middle step returns prefix jobs."""
        graph = self._create_sample_graph()

        result = graph.get_jobs_for_target("ulid_nscf", SelectionMode.TARGET)
        assert len(result) == 2
        assert result[0].id == "step_00"
        assert result[1].id == "step_01"

    def test_get_jobs_for_target_target_mode_last(self):
        """TARGET mode for last step returns all jobs."""
        graph = self._create_sample_graph()

        result = graph.get_jobs_for_target("ulid_bands", SelectionMode.TARGET)
        assert len(result) == 3

    def test_get_jobs_for_target_unknown_step(self):
        """TARGET mode for unknown step returns empty list."""
        graph = self._create_sample_graph()

        result = graph.get_jobs_for_target("unknown", SelectionMode.TARGET)
        assert result == []

    def test_get_dependencies(self):
        """get_dependencies returns dependent jobs."""
        jobs = [
            Job(
                id="step_00",
                step_ids=["ulid_scf"],
                working_dir=Path("/calc/raw"),
                command=["pw.x", "scf.in"],
                deps=[],
            ),
            Job(
                id="step_01",
                step_ids=["ulid_nscf"],
                working_dir=Path("/calc/raw"),
                command=["pw.x", "nscf.in"],
                deps=["step_00"],
            ),
        ]
        graph = JobGraph(jobs=jobs)

        deps = graph.get_dependencies("step_01")
        assert len(deps) == 1
        assert deps[0].id == "step_00"

    def test_get_dependencies_no_deps(self):
        """get_dependencies returns empty for job with no deps."""
        graph = self._create_sample_graph()

        deps = graph.get_dependencies("step_00")
        assert deps == []

    def test_get_dependencies_unknown_job(self):
        """get_dependencies returns empty for unknown job."""
        graph = self._create_sample_graph()

        deps = graph.get_dependencies("nonexistent")
        assert deps == []


class TestComputeJobFingerprint:
    """Tests for compute_job_fingerprint function."""

    def test_single_sha(self):
        """Single SHA returns unchanged."""
        sha = "abc123def456"
        result = compute_job_fingerprint([sha])
        assert result == sha

    def test_empty_list(self):
        """Empty list returns empty string."""
        result = compute_job_fingerprint([])
        assert result == ""

    def test_multiple_shas_deterministic(self):
        """Multiple SHAs produce consistent hash."""
        shas = ["sha1", "sha2", "sha3"]

        result1 = compute_job_fingerprint(shas)
        result2 = compute_job_fingerprint(shas)

        assert result1 == result2
        assert len(result1) == 64  # SHA256 hex

    def test_order_independent(self):
        """Order doesn't affect fingerprint (sorted internally)."""
        shas1 = ["sha1", "sha2", "sha3"]
        shas2 = ["sha3", "sha1", "sha2"]

        result1 = compute_job_fingerprint(shas1)
        result2 = compute_job_fingerprint(shas2)

        assert result1 == result2

    def test_different_shas_different_fingerprint(self):
        """Different SHA sets produce different fingerprints."""
        shas1 = ["sha1", "sha2"]
        shas2 = ["sha1", "sha3"]

        result1 = compute_job_fingerprint(shas1)
        result2 = compute_job_fingerprint(shas2)

        assert result1 != result2


class TestJobGraphWithMultiStepJobs:
    """Tests for JobGraph with multi-step jobs (ORCA/PySCF style)."""

    def _create_orca_style_graph(self) -> JobGraph:
        """Create ORCA-style graph with subchain jobs."""
        jobs = [
            Job(
                id="s",
                step_ids=["ulid_scf"],
                working_dir=Path("/calc/raw/scf_ABCDEF"),
                command=["orca", "s.inp"],
                metadata={"engine": "orca"},
            ),
            Job(
                id="s_m2",
                step_ids=["ulid_scf", "ulid_mp2"],
                working_dir=Path("/calc/raw/scf_ABCDEF"),
                command=["orca", "s_m2.inp"],
                metadata={"engine": "orca"},
            ),
            Job(
                id="s_t",
                step_ids=["ulid_scf", "ulid_td"],
                working_dir=Path("/calc/raw/scf_ABCDEF"),
                command=["orca", "s_t.inp"],
                metadata={"engine": "orca"},
            ),
        ]
        return JobGraph(jobs=jobs)

    def test_get_job_by_step_id_multi_step(self):
        """get_job_by_step_id finds job for step in multi-step job."""
        graph = self._create_orca_style_graph()

        # MP2 step is in s_m2 job
        job = graph.get_job_by_step_id("ulid_mp2")
        assert job is not None
        assert job.id == "s_m2"

        # TD step is in s_t job
        job = graph.get_job_by_step_id("ulid_td")
        assert job is not None
        assert job.id == "s_t"

    def test_get_job_by_step_id_scf_in_multiple(self):
        """SCF step appears in multiple jobs; first match returned."""
        graph = self._create_orca_style_graph()

        job = graph.get_job_by_step_id("ulid_scf")
        assert job is not None
        # First job containing SCF is "s"
        assert job.id == "s"

    def test_get_jobs_for_target_orca_style(self):
        """TARGET mode works with ORCA-style multi-step jobs."""
        graph = self._create_orca_style_graph()

        # Target MP2 -> should return jobs up to s_m2
        result = graph.get_jobs_for_target("ulid_mp2", SelectionMode.TARGET)
        assert len(result) == 2
        assert result[0].id == "s"
        assert result[1].id == "s_m2"
