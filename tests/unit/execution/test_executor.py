"""
Unit tests for JobExecutor.

Tests the execution pipeline with selection modes and skip logic.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from qmatsuite.execution.job_graph import Job, JobGraph, SelectionMode
from qmatsuite.execution.executor import (
    JobExecutor,
    JobResult,
    ExecutionResult,
    create_executor_with_default_handlers,
)


@dataclass
class MockManifestEntry:
    """Mock ManifestStepEntry for testing."""

    step_ulid: str
    kind: str
    done: bool
    step_sha: str = ""


@dataclass
class MockManifest:
    """Mock RunManifest for testing."""

    steps: list


def create_test_job(
    job_id: str,
    step_ulids: list,
    engine: str = "qe",
) -> Job:
    """Create a test job."""
    return Job(
        id=job_id,
        step_ulids=step_ulids,
        working_dir=Path("/calc/raw"),
        command=["pw.x", "scf.in"],
        metadata={"engine": engine},
    )


def success_handler(job: Job, calculation) -> JobResult:
    """Handler that always succeeds."""
    return JobResult(job_id=job.id, success=True)


def failure_handler(job: Job, calculation) -> JobResult:
    """Handler that always fails."""
    return JobResult(job_id=job.id, success=False, error="Simulated failure")


class TestJobExecutor:
    """Tests for JobExecutor class."""

    def test_executor_creation(self):
        """Executor can be created with no handlers."""
        executor = JobExecutor()
        assert executor.engine_handlers == {}

    def test_executor_creation_with_handlers(self):
        """Executor can be created with handlers."""
        handlers = {"qe": success_handler}
        executor = JobExecutor(engine_handlers=handlers)
        assert "qe" in executor.engine_handlers


class TestExecutorExecute:
    """Tests for JobExecutor.execute() method."""

    def test_execute_all_jobs(self):
        """ALL mode executes all jobs."""
        jobs = [
            create_test_job("step_00", ["ulid_0"]),
            create_test_job("step_01", ["ulid_1"]),
            create_test_job("step_02", ["ulid_2"]),
        ]
        graph = JobGraph(jobs=jobs)
        executor = JobExecutor(engine_handlers={"qe": success_handler})

        result = executor.execute(graph, MagicMock(), selection=SelectionMode.ALL)

        assert result.success is True
        assert len(result.job_results) == 3
        assert all(r.success for r in result.job_results)

    def test_execute_target_mode_prefix(self):
        """TARGET mode executes prefix to target."""
        jobs = [
            create_test_job("step_00", ["ulid_0"]),
            create_test_job("step_01", ["ulid_1"]),
            create_test_job("step_02", ["ulid_2"]),
        ]
        graph = JobGraph(jobs=jobs)
        executor = JobExecutor(engine_handlers={"qe": success_handler})

        # Target step_01 -> should run step_00 and step_01
        result = executor.execute(
            graph,
            MagicMock(),
            selection=SelectionMode.TARGET,
            target_step_ulid="ulid_1",
        )

        assert result.success is True
        assert len(result.job_results) == 2
        assert result.job_results[0].job_id == "step_00"
        assert result.job_results[1].job_id == "step_01"

    def test_execute_target_mode_requires_step_id(self):
        """TARGET mode requires target_step_id."""
        graph = JobGraph(jobs=[create_test_job("step_00", ["ulid_0"])])
        executor = JobExecutor()

        with pytest.raises(ValueError, match="target_step_ulid required"):
            executor.execute(graph, MagicMock(), selection=SelectionMode.TARGET)

    def test_execute_empty_graph(self):
        """Empty graph returns success with no results."""
        graph = JobGraph(jobs=[])
        executor = JobExecutor()

        result = executor.execute(graph, MagicMock())

        assert result.success is True
        assert len(result.job_results) == 0

    def test_execute_stops_on_failure(self):
        """Execution stops on first failure."""
        jobs = [
            create_test_job("step_00", ["ulid_0"]),
            create_test_job("step_01", ["ulid_1"]),
            create_test_job("step_02", ["ulid_2"]),
        ]
        graph = JobGraph(jobs=jobs)

        # First job succeeds, second fails
        call_count = [0]

        def counting_handler(job: Job, calc) -> JobResult:
            call_count[0] += 1
            if job.id == "step_01":
                return JobResult(job_id=job.id, success=False, error="Failed")
            return JobResult(job_id=job.id, success=True)

        executor = JobExecutor(engine_handlers={"qe": counting_handler})
        result = executor.execute(graph, MagicMock())

        assert result.success is False
        assert result.failed_job_id == "step_01"
        assert call_count[0] == 2  # Third job not executed

    def test_execute_no_handler_for_engine(self):
        """Missing handler returns failure."""
        jobs = [create_test_job("step_00", ["ulid_0"], engine="unknown")]
        graph = JobGraph(jobs=jobs)
        executor = JobExecutor(engine_handlers={})  # No handlers

        result = executor.execute(graph, MagicMock())

        assert result.success is False
        assert "No handler" in result.job_results[0].error


class TestExecutorSkipLogic:
    """Tests for incremental skip logic."""

    def test_skip_when_done_and_sha_matches(self):
        """Job is skipped when manifest says done and SHA matches."""
        jobs = [create_test_job("step_00", ["ulid_0"])]
        graph = JobGraph(jobs=jobs)

        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_0", kind="qe_scf", done=True, step_sha="sha_123"),
        ])
        step_shas = {"ulid_0": "sha_123"}

        executor = JobExecutor(engine_handlers={"qe": success_handler})
        result = executor.execute(
            graph,
            MagicMock(),
            manifest=manifest,
            step_shas=step_shas,
        )

        assert result.success is True
        assert len(result.job_results) == 1
        assert result.job_results[0].skipped is True

    def test_no_skip_when_sha_mismatch(self):
        """Job executes when SHA differs."""
        jobs = [create_test_job("step_00", ["ulid_0"])]
        graph = JobGraph(jobs=jobs)

        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_0", kind="qe_scf", done=True, step_sha="old_sha"),
        ])
        step_shas = {"ulid_0": "new_sha"}  # Different SHA

        executor = JobExecutor(engine_handlers={"qe": success_handler})
        result = executor.execute(
            graph,
            MagicMock(),
            manifest=manifest,
            step_shas=step_shas,
        )

        assert result.job_results[0].skipped is False

    def test_no_skip_when_not_done(self):
        """Job executes when manifest says not done."""
        jobs = [create_test_job("step_00", ["ulid_0"])]
        graph = JobGraph(jobs=jobs)

        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_0", kind="qe_scf", done=False, step_sha="sha_123"),
        ])
        step_shas = {"ulid_0": "sha_123"}

        executor = JobExecutor(engine_handlers={"qe": success_handler})
        result = executor.execute(
            graph,
            MagicMock(),
            manifest=manifest,
            step_shas=step_shas,
        )

        assert result.job_results[0].skipped is False

    def test_target_job_never_skipped(self):
        """Target job always runs even if eligible for skip."""
        jobs = [
            create_test_job("step_00", ["ulid_0"]),
            create_test_job("step_01", ["ulid_1"]),
        ]
        graph = JobGraph(jobs=jobs)

        # Both steps are done with matching SHAs
        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_0", kind="qe_scf", done=True, step_sha="sha_0"),
            MockManifestEntry(step_ulid="ulid_1", kind="qe_nscf", done=True, step_sha="sha_1"),
        ])
        step_shas = {"ulid_0": "sha_0", "ulid_1": "sha_1"}

        executor = JobExecutor(engine_handlers={"qe": success_handler})
        result = executor.execute(
            graph,
            MagicMock(),
            selection=SelectionMode.TARGET,
            target_step_ulid="ulid_1",
            manifest=manifest,
            step_shas=step_shas,
        )

        # First job should be skipped, target job should run
        assert result.job_results[0].skipped is True
        assert result.job_results[1].skipped is False

    def test_no_manifest_no_skip(self):
        """Without manifest, no jobs are skipped."""
        jobs = [create_test_job("step_00", ["ulid_0"])]
        graph = JobGraph(jobs=jobs)

        executor = JobExecutor(engine_handlers={"qe": success_handler})
        result = executor.execute(graph, MagicMock(), manifest=None)

        assert result.job_results[0].skipped is False


class TestExecutorMultiStepJobs:
    """Tests for multi-step jobs (ORCA/PySCF style)."""

    def test_skip_multi_step_job_all_done(self):
        """Multi-step job skipped only if ALL steps are done."""
        # Job covers two steps
        jobs = [
            Job(
                id="s_m2",
                step_ulids=["ulid_scf", "ulid_mp2"],
                working_dir=Path("/calc/raw/scf_ABCDEF"),
                command=["orca", "s_m2.inp"],
                metadata={"engine": "orca"},
            )
        ]
        graph = JobGraph(jobs=jobs)

        # Both steps done
        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_scf", kind="orca_scf", done=True, step_sha="sha_scf"),
            MockManifestEntry(step_ulid="ulid_mp2", kind="orca_mp2", done=True, step_sha="sha_mp2"),
        ])
        step_shas = {"ulid_scf": "sha_scf", "ulid_mp2": "sha_mp2"}

        executor = JobExecutor(engine_handlers={"orca": success_handler})
        result = executor.execute(graph, MagicMock(), manifest=manifest, step_shas=step_shas)

        assert result.job_results[0].skipped is True

    def test_no_skip_multi_step_job_one_not_done(self):
        """Multi-step job runs if ANY step is not done."""
        jobs = [
            Job(
                id="s_m2",
                step_ulids=["ulid_scf", "ulid_mp2"],
                working_dir=Path("/calc/raw/scf_ABCDEF"),
                command=["orca", "s_m2.inp"],
                metadata={"engine": "orca"},
            )
        ]
        graph = JobGraph(jobs=jobs)

        # Only SCF done
        manifest = MockManifest(steps=[
            MockManifestEntry(step_ulid="ulid_scf", kind="orca_scf", done=True, step_sha="sha_scf"),
            MockManifestEntry(step_ulid="ulid_mp2", kind="orca_mp2", done=False, step_sha="sha_mp2"),
        ])
        step_shas = {"ulid_scf": "sha_scf", "ulid_mp2": "sha_mp2"}

        executor = JobExecutor(engine_handlers={"orca": success_handler})
        result = executor.execute(graph, MagicMock(), manifest=manifest, step_shas=step_shas)

        assert result.job_results[0].skipped is False


class TestCreateExecutorWithDefaultHandlers:
    """Tests for factory function."""

    def test_creates_executor(self):
        """Factory creates an executor instance."""
        executor = create_executor_with_default_handlers()
        assert isinstance(executor, JobExecutor)
