"""
Tests for `qv history` CLI subcommands.

Uses run_qv() subprocess helper to test the CLI interface
against minimal project directories.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_qv(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run qv CLI command."""
    cmd = [sys.executable, "-m", "quantumvitas.cli.main"] + args
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "MPLCONFIGDIR": "/tmp/mpl"},
    )
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


@pytest.fixture
def fresh_project(tmp_path):
    """Create a minimal project directory."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    return project


class TestHistoryListCommand:
    def test_history_list_empty(self, fresh_project):
        """qv history list on fresh project shows 'No history' message."""
        result = run_qv(["history", "list"], cwd=fresh_project)
        assert "No history" in result.stdout or "no history" in result.stdout.lower()

    def test_history_list_help(self, fresh_project):
        """--help shows usage info."""
        result = run_qv(["history", "list", "--help"], cwd=fresh_project)
        assert "Maximum events" in result.stdout or "limit" in result.stdout.lower()


class TestHistoryShowCommand:
    def test_history_show_not_found(self, fresh_project):
        """Non-existent run ULID returns error."""
        result = run_qv(["history", "show", "NONEXISTENT_ULID"], cwd=fresh_project, check=False)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "not found" in combined.lower() or "error" in combined.lower()


class TestHistoryStorageCommand:
    def test_history_storage_fresh(self, fresh_project):
        """Shows zero counts on fresh project."""
        result = run_qv(["history", "storage"], cwd=fresh_project)
        assert "0" in result.stdout
        assert "Runs" in result.stdout or "runs" in result.stdout.lower()


class TestHistoryClearCommand:
    def test_history_clear_without_force(self, fresh_project):
        """Without --force, exits without deleting (non-interactive)."""
        result = run_qv(["history", "clear"], cwd=fresh_project, check=False)
        # In non-interactive mode, typer.confirm will abort
        # Either exits with 1 or prints "Aborted"
        combined = result.stdout + result.stderr
        assert result.returncode != 0 or "abort" in combined.lower()


class TestHistoryHelp:
    def test_history_no_args(self, fresh_project):
        """qv history with no args shows help (no_args_is_help=True)."""
        result = run_qv(["history"], cwd=fresh_project, check=False)
        combined = result.stdout + result.stderr
        assert "list" in combined.lower()
        assert "show" in combined.lower()
        assert "storage" in combined.lower()
        assert "clear" in combined.lower()
