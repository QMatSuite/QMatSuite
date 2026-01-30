"""
Unit tests for project history storage module.

Tests:
- Atomic writes and JSONL append
- Run revision creation and loading
- Event recording and filtering
- Pin de-duplication and latest-run restriction
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
import ulid

from quantumvitas.history.storage import (
    ProjectHistory,
    ensure_history_dir,
    get_latest_run_id,
    generate_run_id,
    HISTORY_DIR_NAME,
    EVENTS_FILE_NAME,
    RUNS_DIR_NAME,
)
from quantumvitas.history.events import (
    HistoryEvent,
    BaselineEvent,
    EditEvent,
    EditChange,
    EditOperation,
    RunStartedEvent,
    RunFinishedEvent,
    PinCreatedEvent,
    EventType,
    compute_semantic_diff,
)
from quantumvitas.history.run_revision import (
    RunRevision,
    RunStatus,
    create_run_revision,
    load_run_revision,
    complete_run_revision,
)
from quantumvitas.history.digests import (
    StepDigest,
    DigestValue,
    compute_step_digest,
    compute_run_digest,
)
from quantumvitas.history.pins import (
    pin_analysis_to_history,
    PinResult,
    PinError,
    can_pin_to_run,
    get_pin_data,
    list_pins_for_step,
)


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary project directory with basic structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir) / "test_project"
        project_root.mkdir()
        
        # Create minimal project.qv.yml
        project_config = project_root / "project.qv.yml"
        project_config.write_text("""
project:
  meta:
    ulid: test-project-001
    name: Test Project
""")

        # Create calculations directory
        calc_dir = project_root / "calculations" / "calc-001"
        calc_dir.mkdir(parents=True)

        # Create calculation.yaml
        calc_yaml = calc_dir / "calculation.yaml"
        calc_yaml.write_text("""
meta:
  ulid: calc-001
  kind: calculation
  name: Test Calculation
structure_ulid: struct-001
steps:
  - step_ulid: step-001
    step_type_spec: qe_scf
""")

        # Create steps directory with a step file
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        step_yaml = steps_dir / "step-001.step.yaml"
        step_yaml.write_text("""
meta:
  ulid: step-001
  kind: step
step_type_spec: qe_scf
parameters:
  SYSTEM:
    ecutwfc: 30.0
""")
        
        # Create structures directory
        structures_dir = project_root / "structures"
        structures_dir.mkdir()
        
        yield project_root


class TestProjectHistoryStorage:
    """Tests for ProjectHistory storage operations."""
    
    def test_ensure_history_dir_creates_structure(self, temp_project_dir: Path):
        """Test that ensure_history_dir creates the correct directory structure."""
        history_dir = ensure_history_dir(temp_project_dir)
        
        assert history_dir.exists()
        assert history_dir == temp_project_dir / HISTORY_DIR_NAME
        assert (history_dir / RUNS_DIR_NAME).exists()
    
    def test_project_history_initialization(self, temp_project_dir: Path):
        """Test ProjectHistory initialization."""
        history = ProjectHistory(temp_project_dir)
        
        # Use samefile to handle macOS /private/var symlinks
        assert history.project_root.samefile(temp_project_dir)
        assert history.history_dir.name == HISTORY_DIR_NAME
        assert history.events_file.name == EVENTS_FILE_NAME
        assert history.runs_dir.name == RUNS_DIR_NAME
    
    def test_is_initialized_false_initially(self, temp_project_dir: Path):
        """Test that is_initialized returns False before any events."""
        history = ProjectHistory(temp_project_dir)
        assert not history.is_initialized()
    
    def test_is_initialized_true_after_event(self, temp_project_dir: Path):
        """Test that is_initialized returns True after appending an event."""
        history = ProjectHistory(temp_project_dir)
        
        event = BaselineEvent.create(project_id="test-001")
        history.append_event(event)
        
        assert history.is_initialized()
    
    def test_append_event_creates_file(self, temp_project_dir: Path):
        """Test that append_event creates events.jsonl if it doesn't exist."""
        history = ProjectHistory(temp_project_dir)
        
        event = BaselineEvent.create(project_id="test-001")
        history.append_event(event)
        
        assert history.events_file.exists()
    
    def test_append_event_stores_valid_json(self, temp_project_dir: Path):
        """Test that appended events are valid JSON lines."""
        history = ProjectHistory(temp_project_dir)
        
        event = BaselineEvent.create(project_id="test-001")
        history.append_event(event)
        
        content = history.events_file.read_text()
        lines = content.strip().split("\n")
        
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == EventType.BASELINE.value
        assert data["project_ulid"] == "test-001"
    
    def test_append_multiple_events(self, temp_project_dir: Path):
        """Test appending multiple events."""
        history = ProjectHistory(temp_project_dir)
        
        events = [
            BaselineEvent.create(project_id="test-001"),
            EditEvent.create(
                project_id="test-001",
                calc_id="calc-001",
                step_id="step-001",
                doc_type="step",
                doc_path="steps/step-001.step.yaml",
                changes=[],
            ),
        ]
        
        for event in events:
            history.append_event(event)
        
        content = history.events_file.read_text()
        lines = content.strip().split("\n")
        
        assert len(lines) == 2
    
    def test_list_events_empty(self, temp_project_dir: Path):
        """Test list_events returns empty list for uninitialized history."""
        history = ProjectHistory(temp_project_dir)
        events = history.list_events()
        assert events == []
    
    def test_list_events_returns_events(self, temp_project_dir: Path):
        """Test list_events returns appended events."""
        history = ProjectHistory(temp_project_dir)
        
        event1 = BaselineEvent.create(project_id="test-001")
        event2 = EditEvent.create(
            project_id="test-001",
            calc_id="calc-001",
            step_id="step-001",
            doc_type="step",
            doc_path="test.yaml",
            changes=[],
        )
        
        history.append_event(event1)
        history.append_event(event2)
        
        events = history.list_events()
        
        assert len(events) == 2
    
    def test_list_events_filter_by_type(self, temp_project_dir: Path):
        """Test filtering events by type."""
        history = ProjectHistory(temp_project_dir)
        
        history.append_event(BaselineEvent.create(project_id="test-001"))
        history.append_event(EditEvent.create(
            project_id="test-001", calc_id=None, step_id=None,
            doc_type="step", doc_path="test.yaml", changes=[],
        ))
        
        baseline_events = history.list_events(event_types=[EventType.BASELINE.value])
        
        assert len(baseline_events) == 1
        assert baseline_events[0].event_type == EventType.BASELINE.value
    
    def test_list_events_filter_by_calc_id(self, temp_project_dir: Path):
        """Test filtering events by calculation ID."""
        history = ProjectHistory(temp_project_dir)
        
        history.append_event(EditEvent.create(
            project_id="test-001", calc_id="calc-001", step_id=None,
            doc_type="calc", doc_path="calc1.yaml", changes=[],
        ))
        history.append_event(EditEvent.create(
            project_id="test-001", calc_id="calc-002", step_id=None,
            doc_type="calc", doc_path="calc2.yaml", changes=[],
        ))
        
        events = history.list_events(calc_id="calc-001")
        
        assert len(events) == 1
        assert events[0].calc_ulid == "calc-001"
    
    def test_ensure_baseline_creates_baseline(self, temp_project_dir: Path):
        """Test that ensure_baseline creates a baseline event."""
        history = ProjectHistory(temp_project_dir)
        
        created = history.ensure_baseline()
        
        assert created
        events = history.list_events(event_types=[EventType.BASELINE.value])
        assert len(events) == 1
    
    def test_ensure_baseline_idempotent(self, temp_project_dir: Path):
        """Test that ensure_baseline doesn't create duplicate baselines."""
        history = ProjectHistory(temp_project_dir)
        
        created1 = history.ensure_baseline()
        created2 = history.ensure_baseline()
        
        assert created1
        assert not created2
        
        events = history.list_events(event_types=[EventType.BASELINE.value])
        assert len(events) == 1
    
    def test_create_run_dir(self, temp_project_dir: Path):
        """Test run directory creation."""
        history = ProjectHistory(temp_project_dir)
        run_id = generate_run_id()
        
        run_dir = history.create_run_dir(run_id)
        
        assert run_dir.exists()
        assert run_dir.name == f"run_{run_id}"
    
    def test_get_run_dir_exists(self, temp_project_dir: Path):
        """Test getting existing run directory."""
        history = ProjectHistory(temp_project_dir)
        run_id = generate_run_id()
        
        history.create_run_dir(run_id)
        
        result = history.get_run_dir(run_id)
        
        assert result is not None
        assert result.exists()
    
    def test_get_run_dir_not_exists(self, temp_project_dir: Path):
        """Test getting non-existent run directory."""
        history = ProjectHistory(temp_project_dir)
        
        result = history.get_run_dir("nonexistent-run-id")
        
        assert result is None


class TestEvents:
    """Tests for history event types."""
    
    def test_baseline_event_creation(self):
        """Test BaselineEvent creation."""
        event = BaselineEvent.create(
            project_id="proj-001",
            structure_ids=["struct-001"],
            calculation_ids=["calc-001"],
        )
        
        assert event.event_type == EventType.BASELINE.value
        assert event.project_ulid == "proj-001"
        assert event.structure_ulids == ["struct-001"]
        assert event.calculation_ulids == ["calc-001"]
        assert event.id  # Has ULID
        assert event.timestamp  # Has timestamp
    
    def test_edit_event_creation(self):
        """Test EditEvent creation."""
        changes = [EditChange(
            op=EditOperation.SET.value,
            path="/parameters/SYSTEM/ecutwfc",
            old_value=30.0,
            new_value=40.0,
        )]
        
        event = EditEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            step_id="step-001",
            doc_type="step",
            doc_path="steps/step-001.step.yaml",
            changes=changes,
            actor="gui",
            summary="Changed ecutwfc from 30 to 40",
        )
        
        assert event.event_type == EventType.EDIT.value
        assert event.doc_type == "step"
        assert len(event.changes) == 1
        assert event.actor == "gui"
    
    def test_run_started_event_creation(self):
        """Test RunStartedEvent creation."""
        event = RunStartedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id="run-001",
            step_ids=["step-001", "step-002"],
            step_types=["scf", "nscf"],
            engine="qe",
        )
        
        assert event.event_type == EventType.RUN_STARTED.value
        assert event.run_ulid == "run-001"
        assert event.step_ids == ["step-001", "step-002"]
    
    def test_run_finished_event_creation(self):
        """Test RunFinishedEvent creation."""
        event = RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id="run-001",
            status="success",
            duration_seconds=123.5,
            step_count=2,
            success_count=2,
            failure_count=0,
        )
        
        assert event.event_type == EventType.RUN_FINISHED.value
        assert event.status == "success"
        assert event.duration_seconds == 123.5
    
    def test_pin_created_event_creation(self):
        """Test PinCreatedEvent creation."""
        event = PinCreatedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            step_id="step-001",
            run_id="run-001",
            analysis_kind="bands",
            pin_path="pins/step-001/bands.png",
        )
        
        assert event.event_type == EventType.PIN_CREATED.value
        assert event.analysis_kind == "bands"
        assert event.pin_path == "pins/step-001/bands.png"
    
    def test_event_from_dict_dispatch(self):
        """Test that HistoryEvent.from_dict dispatches to correct subclass."""
        data = {
            "ulid": "test-id",
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": EventType.BASELINE.value,
            "project_id": "proj-001",
        }
        
        event = HistoryEvent.from_dict(data)
        
        assert isinstance(event, BaselineEvent)
    
    def test_event_to_json_line(self):
        """Test event serialization to JSON line."""
        event = BaselineEvent.create(project_id="proj-001")
        
        json_line = event.to_json_line()
        
        # Should be valid JSON
        data = json.loads(json_line)
        assert data["event_type"] == EventType.BASELINE.value


class TestSemanticDiff:
    """Tests for semantic diff computation."""
    
    def test_compute_diff_no_changes(self):
        """Test diff with identical dicts."""
        before = {"a": 1, "b": 2}
        after = {"a": 1, "b": 2}
        
        changes = compute_semantic_diff(before, after)
        
        assert changes == []
    
    def test_compute_diff_value_change(self):
        """Test diff with value change."""
        before = {"ecutwfc": 30.0}
        after = {"ecutwfc": 40.0}
        
        changes = compute_semantic_diff(before, after)
        
        assert len(changes) == 1
        assert changes[0].op == EditOperation.SET.value
        assert changes[0].path == "/ecutwfc"
        assert changes[0].old_value == 30.0
        assert changes[0].new_value == 40.0
    
    def test_compute_diff_key_added(self):
        """Test diff with new key added."""
        before = {"a": 1}
        after = {"a": 1, "b": 2}
        
        changes = compute_semantic_diff(before, after)
        
        assert len(changes) == 1
        assert changes[0].op == EditOperation.SET.value
        assert changes[0].path == "/b"
        assert changes[0].new_value == 2
    
    def test_compute_diff_key_deleted(self):
        """Test diff with key deleted."""
        before = {"a": 1, "b": 2}
        after = {"a": 1}
        
        changes = compute_semantic_diff(before, after)
        
        assert len(changes) == 1
        assert changes[0].op == EditOperation.DELETE.value
        assert changes[0].path == "/b"
    
    def test_compute_diff_nested(self):
        """Test diff with nested dict changes."""
        before = {"params": {"SYSTEM": {"ecutwfc": 30}}}
        after = {"params": {"SYSTEM": {"ecutwfc": 40}}}
        
        changes = compute_semantic_diff(before, after)
        
        assert len(changes) == 1
        assert changes[0].path == "/params/SYSTEM/ecutwfc"


class TestRunRevision:
    """Tests for run revision management."""
    
    def test_run_revision_to_dict(self):
        """Test RunRevision serialization."""
        revision = RunRevision(
            id="run-001",
            project_id="proj-001",
            calc_id="calc-001",
            status=RunStatus.SUCCESS,
            step_ids=["step-001"],
            step_types=["scf"],
        )
        
        data = revision.to_dict()
        
        assert data["ulid"] == "run-001"
        assert data["status"] == RunStatus.SUCCESS
    
    def test_run_revision_from_dict(self):
        """Test RunRevision deserialization."""
        data = {
            "ulid": "run-001",
            "project_id": "proj-001",
            "calc_id": "calc-001",
            "status": "success",
            "step_ids": ["step-001"],
            "step_types": ["scf"],
        }
        
        revision = RunRevision.from_dict(data)
        
        assert revision.id == "run-001"
        assert revision.status == "success"
    
    def test_run_revision_save_and_load(self, temp_project_dir: Path):
        """Test saving and loading run revision."""
        history = ProjectHistory(temp_project_dir)
        run_id = generate_run_id()
        run_dir = history.create_run_dir(run_id)
        
        revision = RunRevision(
            id=run_id,
            project_id="proj-001",
            calc_id="calc-001",
            status=RunStatus.SUCCESS,
            step_ids=["step-001"],
            step_types=["scf"],
        )
        
        revision.save(run_dir)
        
        loaded = load_run_revision(run_dir)
        
        assert loaded.id == run_id
        assert loaded.status == RunStatus.SUCCESS


class TestDigests:
    """Tests for digest computation."""
    
    def test_digest_value_ok(self):
        """Test DigestValue.ok creation."""
        dv = DigestValue.ok(42.5, "Ry")
        
        assert dv.value == 42.5
        assert dv.status == "ok"
        assert dv.unit == "Ry"
    
    def test_digest_value_missing(self):
        """Test DigestValue.missing creation."""
        dv = DigestValue.missing("File not found")
        
        assert dv.value is None
        assert dv.status == "missing"
        assert dv.message == "File not found"
    
    def test_digest_value_unknown(self):
        """Test DigestValue.unknown creation."""
        dv = DigestValue.unknown("Could not parse")
        
        assert dv.value is None
        assert dv.status == "unknown"
    
    def test_digest_value_to_dict(self):
        """Test DigestValue serialization."""
        dv = DigestValue.ok(42.5, "Ry")
        
        data = dv.to_dict()
        
        assert data["value"] == 42.5
        assert data["status"] == "ok"
        assert data["unit"] == "Ry"
    
    def test_step_digest_creation(self):
        """Test StepDigest creation."""
        digest = StepDigest(
            step_ulid="step-001",
            step_type_spec="qe_scf",
            status="success",
        )

        digest.total_energy = DigestValue.ok(-22.839, "Ry")
        digest.fermi_energy = DigestValue.ok(6.13, "eV")

        data = digest.to_dict()

        assert data["step_ulid"] == "step-001"
        assert data["total_energy"]["value"] == -22.839
    
    def test_compute_step_digest_missing_output(self, temp_project_dir: Path):
        """Test digest computation with missing output file."""
        working_dir = temp_project_dir / "missing_output"
        working_dir.mkdir()

        digest = compute_step_digest(
            step_ulid="step-001",
            step_type_spec="qe_scf",
            working_dir=working_dir,
            step_name="SCF Step",
            step_status="failed",
        )

        assert digest.step_ulid == "step-001"
        assert digest.output_exists is False
        assert digest.converged.status == "missing"
    
    def test_compute_run_digest(self):
        """Test run digest computation."""
        step_digests = [
            StepDigest(
                step_ulid="step-001",
                step_type_spec="qe_scf",
                status="success",
                converged=DigestValue.ok(True),
                total_energy=DigestValue.ok(-22.839, "Ry"),
            ),
            StepDigest(
                step_ulid="step-002",
                step_type_spec="qe_nscf",
                status="success",
                fermi_energy=DigestValue.ok(6.13, "eV"),
            ),
        ]

        started = datetime.now(timezone.utc)
        finished = datetime.now(timezone.utc)

        run_digest = compute_run_digest(
            run_id="run-001",
            calc_id="calc-001",
            status="success",
            started_at=started,
            finished_at=finished,
            step_digests=step_digests,
        )

        assert run_digest["run_id"] == "run-001"
        assert run_digest["status"] == "success"
        assert run_digest["step_count"] == 2
        assert run_digest["success_count"] == 2


class TestPins:
    """Tests for pin-to-history functionality."""
    
    def test_pin_error_run_not_found(self, temp_project_dir: Path):
        """Test pin error when run doesn't exist."""
        with pytest.raises(PinError) as exc_info:
            pin_analysis_to_history(
                project_root=temp_project_dir,
                run_id="nonexistent-run",
                step_id="step-001",
                analysis_kind="bands",
            )
        
        assert "Run not found" in str(exc_info.value)
    
    def test_pin_error_not_latest_run(self, temp_project_dir: Path):
        """Test pin error when trying to pin to non-latest run."""
        history = ProjectHistory(temp_project_dir)
        
        # Create two runs
        run1_id = generate_run_id()
        run2_id = generate_run_id()
        
        history.create_run_dir(run1_id)
        history.create_run_dir(run2_id)
        
        # Record run events to establish run2 as latest
        history.append_event(RunStartedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run1_id,
            step_ids=["step-001"],
        ))
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run1_id,
            status="success",
        ))
        history.append_event(RunStartedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run2_id,
            step_ids=["step-001"],
        ))
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run2_id,
            status="success",
        ))
        
        # Try to pin to run1 (not latest)
        with pytest.raises(PinError) as exc_info:
            pin_analysis_to_history(
                project_root=temp_project_dir,
                run_id=run1_id,
                step_id="step-001",
                analysis_kind="bands",
            )
        
        assert "latest run" in str(exc_info.value).lower()
    
    def test_pin_deduplication(self, temp_project_dir: Path):
        """Test that duplicate pins are de-duplicated."""
        history = ProjectHistory(temp_project_dir)
        
        run_id = generate_run_id()
        history.create_run_dir(run_id)
        
        # Record run events
        history.append_event(RunStartedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run_id,
            step_ids=["step-001"],
        ))
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run_id,
            status="success",
        ))
        
        # Pin first time
        result1 = pin_analysis_to_history(
            project_root=temp_project_dir,
            run_id=run_id,
            step_id="step-001",
            analysis_kind="bands",
            json_payload={"test": "data"},
        )
        
        assert result1.success
        
        # Pin second time (should be de-duplicated)
        result2 = pin_analysis_to_history(
            project_root=temp_project_dir,
            run_id=run_id,
            step_id="step-001",
            analysis_kind="bands",
            json_payload={"test": "data2"},  # Different data
        )
        
        assert result2.success
        assert "already exists" in (result2.error or "")
        
        # Should only have one pin event
        pin_events = history.list_events(event_types=[EventType.PIN_CREATED.value])
        assert len(pin_events) == 1
    
    def test_can_pin_to_run_allowed(self, temp_project_dir: Path):
        """Test can_pin_to_run returns allowed for latest run."""
        history = ProjectHistory(temp_project_dir)
        
        run_id = generate_run_id()
        history.create_run_dir(run_id)
        
        history.append_event(RunStartedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run_id,
            step_ids=["step-001"],
        ))
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run_id,
            status="success",
        ))
        
        result = can_pin_to_run(temp_project_dir, run_id, "step-001")
        
        assert result["allowed"]
    
    def test_can_pin_to_run_not_allowed(self, temp_project_dir: Path):
        """Test can_pin_to_run returns not allowed for old run."""
        history = ProjectHistory(temp_project_dir)
        
        # Create two runs
        run1_id = generate_run_id()
        run2_id = generate_run_id()
        
        history.create_run_dir(run1_id)
        history.create_run_dir(run2_id)
        
        # Record events
        for run_id in [run1_id, run2_id]:
            history.append_event(RunStartedEvent.create(
                project_id="proj-001",
                calc_id="calc-001",
                run_id=run_id,
                step_ids=["step-001"],
            ))
            history.append_event(RunFinishedEvent.create(
                project_id="proj-001",
                calc_id="calc-001",
                run_id=run_id,
                status="success",
            ))
        
        result = can_pin_to_run(temp_project_dir, run1_id, "step-001")
        
        assert not result["allowed"]
        assert "latest" in result["reason"].lower()


class TestGetLatestRunId:
    """Tests for get_latest_run_id function."""
    
    def test_no_runs(self, temp_project_dir: Path):
        """Test get_latest_run_id with no runs."""
        result = get_latest_run_id(temp_project_dir)
        assert result is None
    
    def test_single_run(self, temp_project_dir: Path):
        """Test get_latest_run_id with single run."""
        history = ProjectHistory(temp_project_dir)
        run_id = generate_run_id()
        
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run_id,
            status="success",
        ))
        
        result = get_latest_run_id(temp_project_dir)
        
        assert result == run_id
    
    def test_multiple_runs_returns_latest(self, temp_project_dir: Path):
        """Test get_latest_run_id returns most recent run."""
        history = ProjectHistory(temp_project_dir)
        
        run1_id = generate_run_id()
        run2_id = generate_run_id()
        
        # Add in order
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run1_id,
            status="success",
        ))
        history.append_event(RunFinishedEvent.create(
            project_id="proj-001",
            calc_id="calc-001",
            run_id=run2_id,
            status="success",
        ))
        
        result = get_latest_run_id(temp_project_dir)
        
        # Should return the latest (run2)
        assert result == run2_id


class TestGenerateRunId:
    """Tests for run ID generation."""
    
    def test_generates_valid_ulid(self):
        """Test that generate_run_id produces valid ULIDs."""
        run_id = generate_run_id()
        
        # Should be parseable as ULID
        parsed = ulid.parse(run_id)
        assert parsed is not None
    
    def test_generates_unique_ids(self):
        """Test that generate_run_id produces unique IDs."""
        ids = [generate_run_id() for _ in range(100)]
        
        assert len(set(ids)) == 100  # All unique


class TestJobHistoryIdUnification:
    """Tests for job_id == run_id unification.
    
    These tests verify that:
    1. External run_id can be passed to create_run_revision
    2. Job manager generates ULIDs (not UUIDs)
    3. The same ID is used in both jobs and history
    """
    
    def test_create_run_revision_with_external_id(self, temp_project_dir: Path):
        """Test that create_run_revision uses external run_id if provided."""
        external_id = str(ulid.new())
        
        revision = create_run_revision(
            project_root=temp_project_dir,
            calc_id="calc-001",
            calc_name="Test Calc",
            step_ids=["step-001"],
            step_types=["scf"],
            run_id=external_id,  # Provide external ID
        )
        
        assert revision.id == external_id
        
        # Verify run directory uses the external ID
        history = ProjectHistory(temp_project_dir)
        run_dir = history.get_run_dir(external_id)
        assert run_dir is not None
        assert run_dir.exists()
    
    def test_create_run_revision_generates_id_if_not_provided(self, temp_project_dir: Path):
        """Test that create_run_revision generates new ID if not provided."""
        revision = create_run_revision(
            project_root=temp_project_dir,
            calc_id="calc-001",
            calc_name="Test Calc",
            step_ids=["step-001"],
            step_types=["scf"],
            # No run_id provided
        )
        
        # Should have generated a valid ULID
        assert revision.id is not None
        parsed = ulid.parse(revision.id)
        assert parsed is not None
    
    def test_job_manager_generates_ulid(self):
        """Test that JobManager generates ULIDs (not UUIDs)."""
        from quantumvitas.daemon.jobs import JobManager
        
        manager = JobManager()
        
        # Submit a dummy job
        job_id = manager.submit(
            job_type="test_job",
            func=lambda: {"status": "ok"},
            params={},
        )
        
        # Job ID should be a valid ULID
        parsed = ulid.parse(job_id)
        assert parsed is not None
        
        manager.shutdown(wait=True)
    
    def test_job_manager_submit_with_id(self):
        """Test that JobManager.submit_with_id uses provided ID."""
        from quantumvitas.daemon.jobs import JobManager
        
        manager = JobManager()
        
        external_id = str(ulid.new())
        
        # Submit with specific ID
        returned_id = manager.submit_with_id(
            job_id=external_id,
            job_type="test_job",
            func=lambda: {"status": "ok"},
            params={},
        )
        
        assert returned_id == external_id
        
        # Verify job is tracked with that ID
        job = manager.get_job(external_id)
        assert job is not None
        assert job.id == external_id
        
        manager.shutdown(wait=True)
    
    def test_run_revision_events_use_same_id(self, temp_project_dir: Path):
        """Test that run events reference the same ID as the revision."""
        external_id = str(ulid.new())
        
        # Create revision with external ID
        revision = create_run_revision(
            project_root=temp_project_dir,
            calc_id="calc-001",
            calc_name="Test Calc",
            step_ids=["step-001"],
            step_types=["scf"],
            run_id=external_id,
        )
        
        # Create run events (simulating what runner does)
        history = ProjectHistory(temp_project_dir)
        
        started_event = RunStartedEvent.create(
            project_id=revision.project_id,
            calc_id="calc-001",
            run_id=external_id,  # Same ID
            step_ids=["step-001"],
            step_types=["scf"],
        )
        history.append_event(started_event)
        
        finished_event = RunFinishedEvent.create(
            project_id=revision.project_id,
            calc_id="calc-001",
            run_id=external_id,  # Same ID
            status="success",
        )
        history.append_event(finished_event)
        
        # Verify all reference the same ID
        assert revision.id == external_id
        assert started_event.run_ulid == external_id
        assert finished_event.run_ulid == external_id
        
        # Verify get_latest_run_id returns the external ID
        latest = get_latest_run_id(temp_project_dir)
        assert latest == external_id

