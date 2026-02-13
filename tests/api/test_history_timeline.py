"""
Tests for the History.get_timeline() merged timeline.

Verifies that runs and operation events merge correctly with proper
sort order, limit semantics, and field presence.
"""

import pytest
from pathlib import Path

from quantumvitas.provenance import (
    OperationContext,
    OperationType,
    ActorType,
    ScopeType,
    record_operation_event,
    record_run_start,
    record_run_complete,
    ensure_provenance_initialized,
)
from quantumvitas.api.service import QVService


def _make_project(tmp_path: Path) -> Path:
    """Create minimal project structure with provenance initialized."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")
    ensure_provenance_initialized(project_root)
    return project_root


def _record_op(project_root: Path, op_type: OperationType, timestamp: str,
               summary: str = "", calc_ulid: str = "CALC01") -> str:
    """Helper to record a single operation event."""
    opctx = OperationContext(
        op=op_type,
        actor=ActorType.HUMAN,
        scope=ScopeType.STEP if "step" in op_type.value else ScopeType.CALC,
        source="test",
        payload={"summary": summary},
        timestamp=timestamp,
    )
    return record_operation_event(project_root, opctx, calc_ulid=calc_ulid)


def _record_run(project_root: Path, run_ulid: str, calc_ulid: str,
                started_at: str, finished_at: str | None = None,
                status: str = "success") -> None:
    """Helper to record a run start + optional completion."""
    record_run_start(project_root, run_ulid, calc_ulid)
    if finished_at:
        record_run_complete(project_root, run_ulid, status)


class TestTimelineEmpty:
    def test_timeline_empty_project(self, tmp_path):
        """get_timeline() returns empty timeline on fresh project."""
        project_root = _make_project(tmp_path)
        svc = QVService(project_root)
        result = svc.history.get_timeline()
        assert result["timeline"] == []
        assert result["total"] == 0


class TestTimelineWithOperations:
    def test_timeline_with_operations(self, tmp_path):
        """Operations appear in timeline."""
        project_root = _make_project(tmp_path)
        _record_op(project_root, OperationType.STEP_ADD, "2025-01-01T00:00:00Z", "Added step")
        _record_op(project_root, OperationType.PRESET_APPLY, "2025-01-01T00:01:00Z", "Applied preset")

        svc = QVService(project_root)
        result = svc.history.get_timeline()
        assert len(result["timeline"]) == 2
        # Newest first
        assert result["timeline"][0]["op_type"] == "preset_apply"
        assert result["timeline"][1]["op_type"] == "step_add"

    def test_timeline_operation_entry_fields(self, tmp_path):
        """Operation entries have required fields."""
        project_root = _make_project(tmp_path)
        _record_op(project_root, OperationType.STEP_UPDATE, "2025-01-01T00:00:00Z", "Updated params")

        svc = QVService(project_root)
        result = svc.history.get_timeline()
        entry = result["timeline"][0]
        assert entry["op_type"] == "step_update"
        assert entry["kind"] == "operation"
        assert "timestamp" in entry
        assert "ulid" in entry

    def test_timeline_kind_field(self, tmp_path):
        """kind='operation' on op entries, kind='run' on run entries."""
        project_root = _make_project(tmp_path)
        _record_op(project_root, OperationType.CALC_CREATE, "2025-01-01T00:00:00Z", "Created calc")
        record_run_start(project_root, "RUN001", "CALC01")
        record_run_complete(project_root, "RUN001", "success")

        svc = QVService(project_root)
        result = svc.history.get_timeline()

        kinds = {e.get("kind") for e in result["timeline"]}
        assert "operation" in kinds
        assert "run" in kinds

        for e in result["timeline"]:
            if e.get("run_ulid"):
                assert e["kind"] == "run"

    def test_timeline_operation_event_type_edit(self, tmp_path):
        """step_add/step_update/preset_apply/calc_create map to event_type='edit'."""
        project_root = _make_project(tmp_path)
        for i, op in enumerate([OperationType.STEP_ADD, OperationType.STEP_UPDATE,
                                 OperationType.PRESET_APPLY, OperationType.CALC_CREATE]):
            _record_op(project_root, op, f"2025-01-01T00:0{i}:00Z")

        svc = QVService(project_root)
        result = svc.history.get_timeline()
        for entry in result["timeline"]:
            assert entry["event_type"] == "edit"

    def test_timeline_operation_event_type_operation(self, tmp_path):
        """Other op types map to event_type='operation'."""
        project_root = _make_project(tmp_path)
        _record_op(project_root, OperationType.STRUCTURE_IMPORT, "2025-01-01T00:00:00Z", "Imported structure")

        svc = QVService(project_root)
        result = svc.history.get_timeline()
        entry = result["timeline"][0]
        assert entry["event_type"] == "operation"
        assert entry["op_type"] == "structure_import"


class TestTimelineMerged:
    def test_timeline_merged_ordering(self, tmp_path):
        """Runs and operations interleave correctly by timestamp."""
        project_root = _make_project(tmp_path)

        # Op at T=0
        _record_op(project_root, OperationType.STEP_ADD, "2025-01-01T00:00:00Z", "step add")
        # Run at T=1
        record_run_start(project_root, "RUN001", "CALC01")
        record_run_complete(project_root, "RUN001", "success")
        # Op at T=2
        _record_op(project_root, OperationType.STEP_UPDATE, "2025-01-01T00:02:00Z", "step update")

        svc = QVService(project_root)
        result = svc.history.get_timeline()

        timestamps = [e["timestamp"] for e in result["timeline"]]
        assert timestamps == sorted(timestamps, reverse=True), "Timeline should be sorted newest-first"

    def test_timeline_limit_after_merge(self, tmp_path):
        """Limit applies after merging both sources."""
        project_root = _make_project(tmp_path)

        # Create 6 operations
        for i in range(6):
            _record_op(project_root, OperationType.STEP_ADD, f"2025-01-01T00:{i:02d}:00Z", f"op {i}")

        # Create 4 runs
        for i in range(4):
            run_id = f"RUN{i:03d}"
            record_run_start(project_root, run_id, "CALC01")
            record_run_complete(project_root, run_id, "success")

        svc = QVService(project_root)
        result = svc.history.get_timeline(limit=5)
        assert len(result["timeline"]) == 5
        assert result["total"] == 5


class TestStorageSummary:
    def test_storage_summary_empty(self, tmp_path):
        """Returns zeros on fresh project (no .provenance)."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text("name: test\ncalculations: []\n")

        svc = QVService(project_root)
        result = svc.history.get_storage_summary()
        assert result["total_objects"] == 0
        assert result["run_count"] == 0
        assert result["operation_count"] == 0

    def test_storage_summary_with_data(self, tmp_path):
        """After recording runs + ops, counts are correct."""
        project_root = _make_project(tmp_path)
        _record_op(project_root, OperationType.STEP_ADD, "2025-01-01T00:00:00Z", "step add")
        _record_op(project_root, OperationType.STEP_UPDATE, "2025-01-01T00:01:00Z", "step update")
        record_run_start(project_root, "RUN001", "CALC01")
        record_run_complete(project_root, "RUN001", "success")

        svc = QVService(project_root)
        result = svc.history.get_storage_summary()
        assert result["run_count"] == 1
        assert result["operation_count"] == 2


class TestGetRunRevision:
    def test_get_run_revision_includes_snapshot(self, tmp_path):
        """Run revision returns step details."""
        project_root = _make_project(tmp_path)
        record_run_start(project_root, "RUN001", "CALC01")
        record_run_complete(project_root, "RUN001", "success")

        svc = QVService(project_root)
        result = svc.history.get_run_revision("RUN001")
        assert result["revision"] is not None
        assert result["revision"]["ulid"] == "RUN001"
        assert result["revision"]["status"] == "success"
