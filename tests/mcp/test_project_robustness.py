"""Robustness tests for init_project and related project loading paths.

Tests that filesystem corruption (deleted directories, corrupt YAML,
orphaned references) produces clear warnings or errors — never hangs,
crashes, or misleading messages.
"""

from __future__ import annotations

import shutil

import pytest

from quantumvitas.api import QVService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_calc(qv_project):
    """Create a QE SCF calculation in the project, return calc_ulid."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="silicon",
    )
    assert result["status"] == "success", result
    return result["data"]["calc_ulid"]


def _init_project_for(project_root, monkeypatch):
    """Call init_project targeting the given project_root."""
    monkeypatch.setenv("QMATSUITE_PROJECT", str(project_root))

    from quantumvitas.mcp import project as mcp_project

    monkeypatch.setattr(mcp_project, "_project_root_override", None)

    from quantumvitas.mcp.tools.init_project import init_project

    return init_project.fn()


# ---------------------------------------------------------------------------
# init_project health check
# ---------------------------------------------------------------------------


class TestInitProjectHealthCheck:
    """Verify that init_project reports warnings for filesystem damage."""

    def test_init_with_missing_calc_dir(self, qv_project, monkeypatch):
        """Deleted calc directory → init_project returns warnings."""
        calc_ulid = _create_calc(qv_project)

        # Find and delete the calculation directory
        calcs_dir = qv_project / "calculations"
        calc_dirs = list(calcs_dir.iterdir())
        assert len(calc_dirs) >= 1
        shutil.rmtree(calc_dirs[0])

        result = _init_project_for(qv_project, monkeypatch)
        assert result["status"] == "success"
        assert result["data"]["loaded"] is True
        assert any("missing directory" in w for w in result["warnings"])

    def test_init_with_corrupt_calc_yaml(self, qv_project, monkeypatch):
        """Corrupt calculation.yaml → init_project returns warnings."""
        calc_ulid = _create_calc(qv_project)

        # Corrupt the calculation.yaml
        calcs_dir = qv_project / "calculations"
        calc_dirs = list(calcs_dir.iterdir())
        assert len(calc_dirs) >= 1
        calc_yaml = calc_dirs[0] / "calculation.yaml"
        calc_yaml.write_text("{{{{invalid yaml: [")

        result = _init_project_for(qv_project, monkeypatch)
        assert result["status"] == "success"
        # Resource index should report the corrupt file
        assert any("Skipped corrupt" in w for w in result["warnings"])

    def test_init_with_missing_structures_dir(self, qv_project, monkeypatch):
        """Deleted structures/ → init_project returns warning."""
        structs_dir = qv_project / "structures"
        shutil.rmtree(structs_dir)

        result = _init_project_for(qv_project, monkeypatch)
        assert result["status"] == "success"
        assert any("structures" in w and "missing" in w for w in result["warnings"])

    def test_init_with_corrupt_project_yaml(self, qv_project, monkeypatch):
        """Corrupt project.qv.yml → init_project returns warning."""
        config_file = qv_project / "project.qv.yml"
        config_file.write_text("{{{{invalid yaml: [")

        result = _init_project_for(qv_project, monkeypatch)
        assert result["status"] == "success"
        # Health check should report the unreadable config
        assert any("unreadable" in w for w in result["warnings"])

    def test_init_healthy_project_no_warnings(self, qv_project, monkeypatch):
        """A healthy project produces no warnings."""
        result = _init_project_for(qv_project, monkeypatch)
        assert result["status"] == "success"
        assert result["warnings"] == []


# ---------------------------------------------------------------------------
# get_service() error consistency (V1)
# ---------------------------------------------------------------------------


class TestGetServiceErrorConsistency:
    """Verify get_service() produces clean errors when project.qv.yml vanishes."""

    def test_get_service_after_project_yaml_deleted(self, qv_project, monkeypatch):
        """Delete project.qv.yml → ProjectNotFoundError, not ValueError."""
        config_file = qv_project / "project.qv.yml"
        config_file.unlink()

        from quantumvitas.mcp.project import ProjectNotFoundError, get_service

        with pytest.raises(ProjectNotFoundError, match="Not a project"):
            get_service()

    def test_list_structures_after_project_yaml_deleted(self, qv_project, monkeypatch):
        """Delete project.qv.yml → list_structures returns no_project error."""
        config_file = qv_project / "project.qv.yml"
        config_file.unlink()

        from quantumvitas.mcp.tools.list_structures import list_structures

        result = list_structures.fn()
        assert result["status"] == "error"
        assert result["error_type"] == "no_project"


# ---------------------------------------------------------------------------
# build_resource_index warnings (V2)
# ---------------------------------------------------------------------------


class TestBuildResourceIndexWarnings:
    """Verify build_resource_index collects warnings for corrupt files."""

    def test_warns_on_corrupt_calc_yaml(self, qv_project):
        """Corrupt calculation.yaml → warning collected."""
        calc_ulid = _create_calc(qv_project)

        # Corrupt it
        calcs_dir = qv_project / "calculations"
        calc_dirs = list(calcs_dir.iterdir())
        (calc_dirs[0] / "calculation.yaml").write_text("not: valid: yaml: {{")

        from quantumvitas.core.resolution import (
            build_resource_index,
            get_last_index_warnings,
        )

        index = build_resource_index(qv_project)
        warnings = get_last_index_warnings()
        assert any("Skipped corrupt calculation" in w for w in warnings)

    def test_warns_on_corrupt_structure_json(self, qv_project):
        """Corrupt structure JSON → warning collected."""
        structs_dir = qv_project / "structures"
        for f in structs_dir.glob("*.json"):
            f.write_text("not valid json {{{")
            break

        from quantumvitas.core.resolution import (
            build_resource_index,
            get_last_index_warnings,
        )

        index = build_resource_index(qv_project)
        warnings = get_last_index_warnings()
        assert any("Skipped corrupt structure" in w for w in warnings)

    def test_no_warnings_on_healthy_project(self, qv_project):
        """Healthy project → no warnings."""
        from quantumvitas.core.resolution import (
            build_resource_index,
            get_last_index_warnings,
        )

        build_resource_index(qv_project)
        assert get_last_index_warnings() == []


# ---------------------------------------------------------------------------
# load_project_config wraps errors (V3)
# ---------------------------------------------------------------------------


class TestLoadProjectConfig:
    """Verify load_project_config wraps errors cleanly."""

    def test_missing_project_yaml(self, tmp_path):
        """Missing project.qv.yml → ProjectConfigError."""
        from quantumvitas.core.project_utils import (
            ProjectConfigError,
            load_project_config,
        )

        with pytest.raises(ProjectConfigError, match="not found"):
            load_project_config(tmp_path)

    def test_corrupt_project_yaml(self, qv_project):
        """Corrupt project.qv.yml → ProjectConfigError with 'Failed to parse'."""
        (qv_project / "project.qv.yml").write_text("{{invalid")

        from quantumvitas.core.project_utils import (
            ProjectConfigError,
            load_project_config,
        )

        with pytest.raises(ProjectConfigError, match="Failed to parse"):
            load_project_config(qv_project)


# ---------------------------------------------------------------------------
# inspect_calculation after deletion
# ---------------------------------------------------------------------------


class TestInspectAfterDeletion:
    """Verify inspect_calculation returns a clear error for deleted calcs."""

    def test_inspect_missing_calc(self, qv_project):
        """inspect_calculation with bogus ULID returns not_found error."""
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        result = inspect_calculation.fn(calc_ulid="NONEXISTENT0000000000000000")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_inspect_after_deleted_calc_dir(self, qv_project):
        """Delete calc dir → inspect returns clear error."""
        calc_ulid = _create_calc(qv_project)

        # Delete the calc directory
        calcs_dir = qv_project / "calculations"
        for d in calcs_dir.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
                break

        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        result = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# cleanup_project tool (V5)
# ---------------------------------------------------------------------------


class TestCleanupProject:
    """Verify cleanup_project handles orphans correctly."""

    def test_no_orphans(self, qv_project):
        """Clean project → nothing to clean."""
        from quantumvitas.mcp.tools.cleanup_project import cleanup_project

        result = cleanup_project.fn(dry_run=True)
        assert result["status"] == "success"
        assert result["data"]["total_orphans"] == 0
        assert result["data"]["cleaned"] is False

    def test_dry_run_lists_orphans(self, qv_project):
        """Delete calc dir → dry_run reports orphan."""
        _create_calc(qv_project)

        # Delete calc directory
        calcs_dir = qv_project / "calculations"
        for d in calcs_dir.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
                break

        from quantumvitas.mcp.tools.cleanup_project import cleanup_project

        result = cleanup_project.fn(dry_run=True)
        assert result["status"] == "success"
        assert result["data"]["total_orphans"] >= 1
        assert result["data"]["cleaned"] is False
        assert len(result["data"]["orphaned_calculations"]) >= 1

    def test_cleanup_removes_orphans(self, qv_project):
        """dry_run=False → orphaned entries removed from config."""
        _create_calc(qv_project)

        # Delete calc directory
        calcs_dir = qv_project / "calculations"
        for d in calcs_dir.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
                break

        from quantumvitas.mcp.tools.cleanup_project import cleanup_project

        result = cleanup_project.fn(dry_run=False)
        assert result["status"] == "success"
        assert result["data"]["total_orphans"] >= 1
        assert result["data"]["cleaned"] is True

        # Verify the config no longer has the orphaned entry
        from quantumvitas.core.project_utils import load_project_config

        config = load_project_config(qv_project)
        # All remaining calculations should have existing directories
        for entry in config.get("calculations", []):
            meta = entry.get("meta") or {}
            path = entry.get("path") or meta.get("path", "")
            if path:
                assert (qv_project / path).exists(), f"Orphan not cleaned: {path}"

    def test_cleanup_no_project(self, tmp_path, monkeypatch):
        """cleanup_project without a project → no_project error."""
        from quantumvitas.mcp import project as mcp_project

        monkeypatch.setattr(mcp_project, "_project_root_override", tmp_path)

        from quantumvitas.mcp.tools.cleanup_project import cleanup_project

        result = cleanup_project.fn(dry_run=True)
        assert result["status"] == "error"
        assert result["error_type"] == "no_project"


# ---------------------------------------------------------------------------
# list_structures after structure deletion
# ---------------------------------------------------------------------------


class TestListStructuresAfterDeletion:
    """Verify list_structures handles missing structure files gracefully."""

    def test_list_after_deleted_structure_file(self, qv_project):
        """Delete a structure JSON → list_structures still returns, skipping it."""
        structs_dir = qv_project / "structures"
        json_files = list(structs_dir.glob("*.json"))
        assert len(json_files) >= 1
        json_files[0].unlink()

        from quantumvitas.mcp.tools.list_structures import list_structures

        result = list_structures.fn()
        # Should succeed (possibly with 0 structures)
        assert result["status"] == "success"
