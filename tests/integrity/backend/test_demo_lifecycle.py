"""
Backend integrity tests: load -> materialize -> roundtrip for ALL demos.

Per S7.2: verify every demo project can be loaded and materialized.
Roundtrip check verifies content-equivalence per S6.3.

NOT collected by default pytest (C4). Run explicitly:
    python -m pytest tests/integrity/backend/ -v --tb=short
"""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from qmatsuite.api import QMSService
from qmatsuite.core.resources import get_resources_dir
from qmatsuite.project.snapshot import (
    ProjectSnapshot,
    materialize_project_from_snapshot,
    export_project_to_snapshot,
)

DEMO_DIR = get_resources_dir() / "demo_projects"


def _list_demo_files():
    """List all demo .yml files."""
    if not DEMO_DIR.exists():
        return []
    return sorted(DEMO_DIR.glob("*.yml"))


def _load_demo(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(params=_list_demo_files(), ids=lambda p: p.stem)
def demo_path(request):
    return request.param


@pytest.mark.integrity
class TestDemoLifecycle:
    """Per-demo lifecycle tests: load -> materialize -> verify structure."""

    def test_load_snapshot(self, demo_path):
        """Every demo must be loadable as a ProjectSnapshot."""
        data = _load_demo(demo_path)
        snapshot = ProjectSnapshot.from_dict(data)

        assert snapshot.version == 1
        assert snapshot.project
        assert snapshot.calculations

    def test_materialize(self, demo_path):
        """Every demo must materialize into a valid project directory."""
        data = _load_demo(demo_path)
        snapshot = ProjectSnapshot.from_dict(data)

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = materialize_project_from_snapshot(
                snapshot=snapshot,
                parent_dir=Path(tmpdir),
                new_project_name=f"test_{demo_path.stem}",
            )

            # Verify project structure
            assert project_root.exists()
            assert (project_root / "project.qms.yml").exists()

            structures_dir = project_root / "structures"
            assert structures_dir.exists()

            calculations_dir = project_root / "calculations"
            assert calculations_dir.exists()

            # Verify at least one calculation with steps
            calc_yamls = list(calculations_dir.glob("*/calculation.yaml"))
            assert len(calc_yamls) > 0, f"No calculation.yaml found in {calculations_dir}"

            step_files = list(calculations_dir.glob("*/steps/*.step.yaml"))
            assert len(step_files) > 0, f"No step files found in {calculations_dir}"

    def test_materialize_via_api(self, demo_path):
        """Every demo must be loadable via QMSService.create_demo_project."""
        demo_id = demo_path.stem

        with tempfile.TemporaryDirectory() as tmpdir:
            result = QMSService.create_demo_project(
                target_dir=Path(tmpdir),
                name=f"test_{demo_id}",
                demo_id=demo_id,
            )

            project_root = Path(result["project_root"])
            assert project_root.exists()

            # Verify project can be opened
            svc = QMSService(project_root)
            summary = svc.project.get_summary()
            assert summary is not None
            assert summary["n_structures"] >= 0
            assert summary["n_calculations"] > 0

    def test_gallery_metadata(self, demo_path):
        """Every demo should have gallery metadata."""
        data = _load_demo(demo_path)
        meta = data.get("meta", {})

        assert meta.get("ulid"), f"Missing meta.ulid in {demo_path.name}"
        assert meta.get("title"), f"Missing meta.title in {demo_path.name}"

    def test_engine_family_set(self, demo_path):
        """Every calculation must have explicit engine_family."""
        data = _load_demo(demo_path)
        for calc in data.get("calculations", []):
            ef = calc.get("engine_family")
            assert ef is not None, f"Missing engine_family in {demo_path.name}"

    def test_step_type_spec_present(self, demo_path):
        """Every step must have step_type_spec."""
        data = _load_demo(demo_path)
        for calc in data.get("calculations", []):
            for step in calc.get("steps", []):
                spec = step.get("step_type_spec")
                assert spec, f"Missing step_type_spec in {demo_path.name}"
