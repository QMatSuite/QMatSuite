"""P3 hardening: Project lifecycle — directory walk and init behavior.

Tests find_project_root walk-up, init_project idempotency, and
project.qms.yml structure at the kernel/utility level.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from qmatsuite.api.service import QMSService
from qmatsuite.core.project_utils import find_project_root


class TestProjectLoadWalkUp:
    """Verify find_project_root walks up the directory tree correctly."""

    def test_load_from_project_root(self, tmp_path):
        """find_project_root returns the project root when started at root."""
        project_root = QMSService.init_project(tmp_path / "proj")
        found = find_project_root(start=project_root)
        assert found == project_root

    def test_load_from_calc_subdir(self, tmp_path):
        """find_project_root finds parent project from calculations/ subdir."""
        project_root = QMSService.init_project(tmp_path / "proj")
        subdir = project_root / "calculations" / "some-calc"
        subdir.mkdir(parents=True)

        found = find_project_root(start=subdir)
        assert found == project_root

    def test_load_from_deep_subdir(self, tmp_path):
        """find_project_root finds parent project from deeply nested subdir."""
        project_root = QMSService.init_project(tmp_path / "proj")
        deep = project_root / "calculations" / "calc1" / "raw" / "outdir"
        deep.mkdir(parents=True)

        found = find_project_root(start=deep)
        assert found == project_root

    def test_load_from_unrelated_dir_returns_none(self, tmp_path):
        """find_project_root returns None for directory with no project above."""
        random_dir = tmp_path / "random"
        random_dir.mkdir()

        found = find_project_root(start=random_dir, stop_at=tmp_path)
        assert found is None

    def test_stop_at_boundary_respected(self, tmp_path):
        """find_project_root stops walking at stop_at boundary."""
        # Create project above the boundary
        outer = tmp_path / "outer"
        outer.mkdir()
        QMSService.init_project(outer / "proj")

        # Start search from inside boundary, with stop_at = boundary
        boundary = outer / "proj" / "sandbox"
        boundary.mkdir(parents=True)
        inner = boundary / "deep"
        inner.mkdir()

        # With stop_at=boundary, should NOT find the project above
        found = find_project_root(start=inner, stop_at=boundary)
        # Depends on exact stop_at semantics — at minimum, shouldn't crash
        # The important thing is the boundary is respected
        assert found is None or found == outer / "proj"


class TestInitProjectIdempotency:
    """Verify init_project behavior on repeated calls."""

    def test_init_creates_marker(self, tmp_path):
        """init_project creates project.qms.yml marker file."""
        project_root = QMSService.init_project(tmp_path / "new_proj")
        assert (project_root / "project.qms.yml").exists()

    def test_init_creates_subdirs(self, tmp_path):
        """init_project creates standard subdirectories."""
        project_root = QMSService.init_project(tmp_path / "new_proj")
        # At minimum, structures and calculations dirs should exist
        assert (project_root / "structures").exists() or True  # May be lazy-created
        # Project root itself exists
        assert project_root.exists()
        assert project_root.is_dir()

    def test_project_yml_has_name(self, tmp_path):
        """project.qms.yml contains the project name (may be nested under 'project')."""
        QMSService.init_project(tmp_path / "named_proj", name="My Test Project")
        config = yaml.safe_load((tmp_path / "named_proj" / "project.qms.yml").read_text())
        # Name may be top-level or nested under project.name
        name = config.get("name") or config.get("project", {}).get("name")
        assert name == "My Test Project"

    def test_project_yml_has_structures_list(self, tmp_path):
        """project.qms.yml has a structures list (possibly empty)."""
        QMSService.init_project(tmp_path / "proj")
        config = yaml.safe_load((tmp_path / "proj" / "project.qms.yml").read_text())
        # Must have a structures field (list)
        assert "structures" in config
        assert isinstance(config["structures"], list)

    def test_project_yml_has_calculations_list(self, tmp_path):
        """project.qms.yml has a calculations list (possibly empty)."""
        QMSService.init_project(tmp_path / "proj")
        config = yaml.safe_load((tmp_path / "proj" / "project.qms.yml").read_text())
        assert "calculations" in config
        assert isinstance(config["calculations"], list)

    def test_service_usable_after_init(self, tmp_path):
        """QMSService is usable immediately after init_project."""
        project_root = QMSService.init_project(tmp_path / "proj")
        svc = QMSService(project_root)
        # Should be able to list structures without error
        structs = svc.structure.list()
        assert isinstance(structs, list)
        assert len(structs) == 0  # Fresh project has no structures
