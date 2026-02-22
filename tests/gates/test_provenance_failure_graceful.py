"""
Gate test for Law P7: Graceful Degradation.

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P7:
> Provenance failures MUST NOT fail YAML writes.

If SQLite append fails after YAML write succeeds:
- Log warning and continue
- Project remains runnable
- Provenance gap is logged
- History is NOT SSOT; YAML write success is the only success criterion
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_yaml_write_succeeds_despite_provenance_failure(tmp_path):
    """
    Law P7: YAML write succeeds even if provenance recording fails.

    Simulates a provenance failure and verifies the YAML write still completes.
    """
    from qmatsuite.core.yamldoc import YamlDoc
    from qmatsuite.core.yaml_io import save_yaml_doc
    from qmatsuite.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    # Create a project.qms.yml to mark as project root
    project_file = tmp_path / "project.qms.yml"
    project_file.write_text("project:\n  meta:\n    ulid: PROJ123\n")

    yaml_path = tmp_path / "test.yaml"
    doc = YamlDoc({"key": "value"})

    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_graceful_degradation",
        payload={},
    )

    # Patch record_operation_event to raise an exception
    with patch(
        "qmatsuite.provenance.recording.record_operation_event"
    ) as mock_record:
        mock_record.side_effect = Exception("Simulated provenance failure")

        # Save should still succeed
        save_yaml_doc(doc, yaml_path, opctx)

        # YAML file exists and is correct
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "key: value" in content

        # record_operation_event was called (and failed)
        mock_record.assert_called_once()


def test_yaml_write_with_database_corruption(tmp_path):
    """
    Law P7: YAML write succeeds even with corrupted provenance database.

    This tests a more realistic failure scenario where the SQLite database
    is corrupted or locked.
    """
    from qmatsuite.core.yamldoc import YamlDoc
    from qmatsuite.core.yaml_io import save_yaml_doc
    from qmatsuite.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
        ensure_provenance_initialized,
    )

    # Create a project.qms.yml to mark as project root
    project_file = tmp_path / "project.qms.yml"
    project_file.write_text("project:\n  meta:\n    ulid: PROJ123\n")

    # Initialize provenance
    ensure_provenance_initialized(tmp_path)

    # Corrupt the database by writing garbage
    db_path = tmp_path / ".provenance" / "provenance.db"
    db_path.write_text("not a sqlite database")

    yaml_path = tmp_path / "test.yaml"
    doc = YamlDoc({"key": "value"})

    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_database_corruption",
        payload={},
    )

    # Save should still succeed - YAML write is independent of provenance
    save_yaml_doc(doc, yaml_path, opctx)

    # YAML file exists and is correct
    assert yaml_path.exists()
    content = yaml_path.read_text()
    assert "key: value" in content


def test_yaml_write_without_opctx_no_provenance(tmp_path):
    """
    Law P7: YAML write without opctx doesn't attempt provenance (no failure).

    When opctx is None, provenance recording is skipped entirely.
    """
    from qmatsuite.core.yamldoc import YamlDoc
    from qmatsuite.core.yaml_io import save_yaml_doc

    yaml_path = tmp_path / "test.yaml"
    doc = YamlDoc({"key": "value"})

    # Save without opctx - no provenance recording attempted
    with patch(
        "qmatsuite.provenance.recording.record_operation_event"
    ) as mock_record:
        save_yaml_doc(doc, yaml_path)  # No opctx

        # record_operation_event should NOT be called
        mock_record.assert_not_called()

    # YAML file exists and is correct
    assert yaml_path.exists()


def test_provenance_error_is_logged(tmp_path, caplog):
    """
    Law P7: Provenance failures are logged as warnings.

    Verifies that when provenance fails, a warning is logged.
    """
    import logging

    from qmatsuite.core.yamldoc import YamlDoc
    from qmatsuite.core.yaml_io import save_yaml_doc
    from qmatsuite.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    # Create a project.qms.yml to mark as project root
    project_file = tmp_path / "project.qms.yml"
    project_file.write_text("project:\n  meta:\n    ulid: PROJ123\n")

    yaml_path = tmp_path / "test.yaml"
    doc = YamlDoc({"key": "value"})

    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_logging",
        payload={},
    )

    with patch(
        "qmatsuite.provenance.recording.record_operation_event"
    ) as mock_record:
        mock_record.side_effect = Exception("Simulated failure")

        with caplog.at_level(logging.WARNING):
            save_yaml_doc(doc, yaml_path, opctx)

        # Warning should be logged
        assert any("provenance" in record.message.lower() for record in caplog.records) or \
               any("non-fatal" in record.message.lower() for record in caplog.records)
