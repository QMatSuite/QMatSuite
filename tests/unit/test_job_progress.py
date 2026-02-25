"""Tests for Job progress fields (engine install progress reporting)."""

from __future__ import annotations

from qmatsuite.daemon.jobs import Job


def test_job_progress_fields_default_none() -> None:
    """New Job instances have all 4 progress fields set to None."""
    job = Job(id="test-001", job_type="engine_install")
    assert job.progress_pct is None
    assert job.progress_bytes is None
    assert job.progress_total is None
    assert job.progress_stage is None


def test_job_progress_fields_in_to_dict() -> None:
    """Progress fields appear in both to_dict() and to_summary_dict()."""
    job = Job(id="test-002", job_type="engine_install")
    job.progress_pct = 42.5
    job.progress_bytes = 12345
    job.progress_total = 56789
    job.progress_stage = "Downloading"

    full = job.to_dict()
    assert full["progress_pct"] == 42.5
    assert full["progress_bytes"] == 12345
    assert full["progress_total"] == 56789
    assert full["progress_stage"] == "Downloading"

    summary = job.to_summary_dict()
    assert summary["progress_pct"] == 42.5
    assert summary["progress_bytes"] == 12345
    assert summary["progress_total"] == 56789
    assert summary["progress_stage"] == "Downloading"
