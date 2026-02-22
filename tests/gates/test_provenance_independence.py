"""
Gate test for Law P1: SSOT Separation (History World Independence).

Per PROVENANCE_VERSIONED_HISTORY_SPEC.md Law P1:
> The History World (SQLite + CAS) MUST NOT participate in any runtime logic.
> Deleting .provenance/ directory MUST leave the project fully runnable.

This test verifies that:
1. Projects can load and run without .provenance/
2. Deleting .provenance/ doesn't break existing functionality
3. Runtime operations don't depend on provenance data
"""

import pytest
import shutil
from pathlib import Path


def test_project_loadable_without_provenance(tmp_path):
    """
    Law P1: Project files are loadable without .provenance/ directory.

    The SSOT is YAML files, not provenance database.
    """
    from qmatsuite.core.yamldoc import CalcDoc, StepDoc

    # Create a minimal project structure
    calc_dir = tmp_path / "calculations" / "TEST_CALC_123"
    calc_dir.mkdir(parents=True)

    # Create calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text("""
meta:
  kind: calculation
  ulid: TEST_CALC_123
name: test
structure_ulid: STRUCT123
""")

    # Create step.yaml
    step_yaml = calc_dir / "step_scf.yaml"
    step_yaml.write_text("""
meta:
  kind: step
  ulid: STEP123
step_type_spec: qe_scf
parameters:
  ecutwfc: 40
""")

    # Ensure no .provenance directory
    provenance_dir = tmp_path / ".provenance"
    assert not provenance_dir.exists()

    # Load documents - should work without provenance
    calc_doc = CalcDoc.load(calc_yaml)
    step_doc = StepDoc.load(step_yaml)

    assert calc_doc.get(("name",)) == "test"
    assert step_doc.get(("step_type_spec",)) == "qe_scf"
    assert step_doc.get(("parameters", "ecutwfc")) == 40


def test_save_works_without_existing_provenance(tmp_path):
    """
    Law P1: Saving documents works even if .provenance/ doesn't exist.

    Provenance is lazily initialized on first write with opctx.
    """
    from qmatsuite.core.yamldoc import StepDoc
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

    step_path = tmp_path / "step.yaml"
    doc = StepDoc({
        "meta": {"kind": "step", "ulid": "STEP123"},
        "parameters": {"ecutwfc": 40},
    })

    opctx = OperationContext(
        op=OperationType.STEP_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.STEP,
        source="test_save_works",
        payload={},
    )

    # Should succeed - provenance is auto-initialized
    save_yaml_doc(doc, step_path, opctx)

    assert step_path.exists()


def test_delete_provenance_then_save(tmp_path):
    """
    Law P1: Deleting .provenance/ then saving still works.

    Provenance is re-initialized automatically.
    """
    from qmatsuite.core.yamldoc import StepDoc
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

    step_path = tmp_path / "step.yaml"
    doc = StepDoc({
        "meta": {"kind": "step", "ulid": "STEP123"},
        "parameters": {"ecutwfc": 40},
    })

    opctx = OperationContext(
        op=OperationType.STEP_UPDATE,
        actor=ActorType.SYSTEM,
        scope=ScopeType.STEP,
        source="test_delete_provenance",
        payload={},
    )

    # First save - initializes provenance
    save_yaml_doc(doc, step_path, opctx)

    provenance_dir = tmp_path / ".provenance"
    assert provenance_dir.exists()

    # Delete provenance
    shutil.rmtree(provenance_dir)
    assert not provenance_dir.exists()

    # Update and save again - should work
    doc.set("parameters/ecutwfc", 60)
    save_yaml_doc(doc, step_path, opctx)

    assert step_path.exists()
    # Provenance is re-initialized
    assert provenance_dir.exists()


def test_runtime_does_not_depend_on_provenance():
    """
    Law P1: Core runtime imports don't require provenance to exist.

    This verifies the import structure doesn't create runtime dependencies.
    """
    # These imports should work without any provenance initialization
    from qmatsuite.core.yamldoc import YamlDoc, StepDoc, CalcDoc, ProjectDoc
    from qmatsuite.core.yaml_io import save_yaml_doc, load_yaml_doc

    # Creating documents doesn't require provenance
    doc = YamlDoc({"key": "value"})
    assert doc.get(("key",)) == "value"


def test_manifest_independent_of_provenance(tmp_path):
    """
    Law P1 + P3: Manifest (skip logic) doesn't depend on provenance.

    This is also covered by test_provenance_skip_isolation.py, but we
    verify the runtime behavior here.
    """
    # Just verify manifest can be imported and used without provenance
    try:
        from qmatsuite.calculation.manifest import ManifestStepEntry

        entry = ManifestStepEntry(
            kind="scf",
            step_ulid="STEP123",
            pseudo_set_sha="abc123",
            structure_sha="def456",
            step_sha="ghi789",
            done=False,
        )

        assert entry.step_ulid == "STEP123"
        assert not entry.done
    except ImportError:
        pytest.skip("Manifest module not available")
