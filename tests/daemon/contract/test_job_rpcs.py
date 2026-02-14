"""RPC contract tests for job management endpoints."""

from pathlib import Path
import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestListJobs:
    """Contract tests for list_jobs RPC."""

    def test_list_jobs_empty(self, temp_project: Path, daemon: QVDaemon):
        """list_jobs returns empty list for project with no jobs."""
        response = send_request(daemon, "list_jobs", {
            "project_root": str(temp_project)
        })

        assert "jobs" in response
        assert response["jobs"] == []

    def test_list_jobs_no_param(self, daemon: QVDaemon):
        """list_jobs without project_root returns all jobs."""
        response = send_request(daemon, "list_jobs", {})
        
        assert "jobs" in response
        assert isinstance(response["jobs"], list)


class TestJobCounts:
    """Contract tests for job_counts RPC."""

    def test_job_counts_empty(self, temp_project: Path, daemon: QVDaemon):
        """job_counts returns zero counts for no jobs."""
        response = send_request(daemon, "job_counts", {})

        assert "counts" in response
        assert "running" in response
        assert "pending" in response
        assert response["running"] == 0
        assert response["pending"] == 0

    def test_job_counts_workflow(self, temp_project: Path, daemon: QVDaemon):
        """job_counts used for GUI polling."""
        # Poll multiple times
        for _ in range(3):
            response = send_request(daemon, "job_counts", {})
            assert "counts" in response
            assert "running" in response
            assert "pending" in response


class TestGetJobStatus:
    """Contract tests for get_job_status RPC."""

    def test_get_job_status_not_found(self, temp_project: Path, daemon: QVDaemon):
        """get_job_status errors on non-existent job."""
        with pytest.raises(RuntimeError):
            send_request(daemon, "get_job_status", {
                "project_root": str(temp_project),
                "job_id": "nonexistent_job"
            })
