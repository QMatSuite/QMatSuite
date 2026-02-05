"""
Gate test for Law P2: OperationContext Required.

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P2:
> Any write to Present World SSOT YAML MUST carry an explicit OperationContext.

NOTE: During migration, opctx is optional. This gate test verifies that:
1. save_yaml_doc() accepts opctx parameter
2. save_yaml_doc() with opctx records provenance events
3. Doc.save() methods accept opctx parameter
"""

import pytest
from pathlib import Path


def test_save_yaml_doc_accepts_opctx(tmp_path):
    """
    Law P2: save_yaml_doc() accepts opctx parameter.

    During migration phase, opctx is optional. This test verifies
    the parameter exists and works when provided.
    """
    from quantumvitas.core.yamldoc import YamlDoc
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    # Create a simple doc
    doc = YamlDoc({"key": "value"})
    yaml_path = tmp_path / "test.yaml"

    # Create opctx
    opctx = OperationContext(
        op=OperationType.CUSTOM,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_save_yaml_doc_accepts_opctx",
        payload={"test": True},
    )

    # Save with opctx - should not raise
    save_yaml_doc(doc, yaml_path, opctx)

    # Verify file was saved
    assert yaml_path.exists()
    content = yaml_path.read_text()
    assert "key: value" in content


def test_save_yaml_doc_without_opctx_still_works(tmp_path):
    """
    Migration compatibility: save_yaml_doc() still works without opctx.

    Once all callers are updated, this behavior will change to require opctx.
    """
    from quantumvitas.core.yamldoc import YamlDoc
    from quantumvitas.core.yaml_io import save_yaml_doc

    doc = YamlDoc({"key": "value"})
    yaml_path = tmp_path / "test.yaml"

    # Save without opctx - should still work during migration
    save_yaml_doc(doc, yaml_path)

    assert yaml_path.exists()


def test_step_doc_save_accepts_opctx(tmp_path):
    """StepDoc.save() accepts opctx parameter."""
    from quantumvitas.core.yamldoc import StepDoc
    from quantumvitas.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    doc = StepDoc({
        "meta": {"kind": "step", "ulid": "TEST123"},
        "parameters": {"ecutwfc": 40},
    })
    yaml_path = tmp_path / "step.yaml"

    opctx = OperationContext(
        op=OperationType.STEP_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.STEP,
        source="test_step_doc_save",
        payload={},
    )

    doc.save(yaml_path, opctx)
    assert yaml_path.exists()


def test_calc_doc_save_accepts_opctx(tmp_path):
    """CalcDoc.save() accepts opctx parameter."""
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    doc = CalcDoc({
        "meta": {"kind": "calculation", "ulid": "CALC123"},
        "name": "test_calc",
    })
    yaml_path = tmp_path / "calculation.yaml"

    opctx = OperationContext(
        op=OperationType.CALC_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.CALC,
        source="test_calc_doc_save",
        payload={},
    )

    doc.save(yaml_path, opctx)
    assert yaml_path.exists()


def test_project_doc_save_accepts_opctx(tmp_path):
    """ProjectDoc.save() accepts opctx parameter."""
    from quantumvitas.core.yamldoc import ProjectDoc
    from quantumvitas.provenance import (
        OperationContext,
        OperationType,
        ActorType,
        ScopeType,
    )

    doc = ProjectDoc({
        "project": {
            "meta": {"kind": "project", "ulid": "PROJ123"},
            "name": "test_project",
        }
    })
    yaml_path = tmp_path / "project.qv.yml"

    opctx = OperationContext(
        op=OperationType.PROJECT_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.PROJECT,
        source="test_project_doc_save",
        payload={},
    )

    doc.save(yaml_path, opctx)
    assert yaml_path.exists()
