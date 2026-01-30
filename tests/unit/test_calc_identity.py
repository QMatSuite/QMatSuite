"""
Tests for calculation identity inference and recovery (Phase 3A).
"""

import pytest
import yaml
from pathlib import Path
from tempfile import TemporaryDirectory

from quantumvitas.core.calc_identity import (
    infer_calculation_identity,
    ensure_calculation_identity,
    _infer_engine_family_from_machine_types,
    _infer_structure_kind_from_engine_family,
)
from quantumvitas.core.models import CalculationModel, CalculationStepEntry, ResourceMeta


def test_infer_engine_family_from_machine_types_qe():
    """Test inference of qe family from machine types."""
    machine_types = ["qe_scf", "qe_nscf", "qe_dos"]
    result = _infer_engine_family_from_machine_types(machine_types)
    assert result == "qe"


def test_infer_engine_family_from_machine_types_pyscf():
    """Test inference of pyscf family from machine types."""
    machine_types = ["pyscf_scf"]
    result = _infer_engine_family_from_machine_types(machine_types)
    assert result == "pyscf"


def test_infer_engine_family_from_machine_types_w90_separate_family():
    """Test that w90 steps are treated as separate family (no longer mapped to qe)."""
    machine_types = ["qe_scf", "w90_run"]
    result = _infer_engine_family_from_machine_types(machine_types)
    assert result is None  # Mixed families: qe and w90 are separate engines


def test_infer_engine_family_from_machine_types_mixed_returns_none():
    """Test that mixed families return None."""
    machine_types = ["qe_scf", "pyscf_scf"]
    result = _infer_engine_family_from_machine_types(machine_types)
    assert result is None


def test_infer_structure_kind_from_engine_family():
    """Test structure_kind inference from engine_family."""
    assert _infer_structure_kind_from_engine_family("pyscf") == "molecule"
    assert _infer_structure_kind_from_engine_family("qe") == "periodic"
    assert _infer_structure_kind_from_engine_family("w90") == "periodic"


def test_infer_calculation_identity_from_qe_steps():
    """Test identity inference from QE steps."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        
        steps = [
            CalculationStepEntry(step_id="step1", type="scf"),
            CalculationStepEntry(step_id="step2", type="nscf"),
        ]
        
        structure_kind, engine_family = infer_calculation_identity(calc_dir, steps)
        assert engine_family == "qe"
        assert structure_kind == "periodic"


def test_infer_calculation_identity_from_pyscf_steps():
    """Test identity inference from PySCF steps."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        
        steps = [
            CalculationStepEntry(step_id="step1", type="pyscf_scf"),
        ]
        
        structure_kind, engine_family = infer_calculation_identity(calc_dir, steps)
        assert engine_family == "pyscf"
        assert structure_kind == "molecule"


def test_infer_calculation_identity_from_step_yaml_files():
    """Test identity inference from step.yaml files when calculation.yaml steps empty."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        
        # Create step.yaml files with machine types
        step1_yaml = steps_dir / "step1.step.yaml"
        step1_yaml.write_text(yaml.safe_dump({
            "step_type_gen": "qe_scf",
            "meta": {"ulid": "step1"},
        }))
        
        step2_yaml = steps_dir / "step2.step.yaml"
        step2_yaml.write_text(yaml.safe_dump({
            "step_type_gen": "qe_nscf",
            "meta": {"ulid": "step2"},
        }))
        
        # Empty steps list - should fallback to step.yaml files
        steps = []
        
        structure_kind, engine_family = infer_calculation_identity(calc_dir, steps)
        assert engine_family == "qe"
        assert structure_kind == "periodic"


def test_ensure_calculation_identity_writes_back():
    """Test that ensure_calculation_identity writes inferred values back to calculation.yaml."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        
        # Create calculation.yaml without structure_kind/engine_family
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = {
            "meta": {"ulid": "calc1", "name": "Test Calc", "slug": "test-calc"},
            "steps": [
                {"step_ulid": "step1", "step_type_gen": "scf"},
                {"step_ulid": "step2", "step_type_gen": "nscf"},
            ],
        }
        calc_yaml.write_text(yaml.safe_dump(calc_data))
        
        # Ensure identity (should infer and write back)
        ensure_calculation_identity(calc_dir)
        
        # Read back and verify
        updated_data = yaml.safe_load(calc_yaml.read_text())
        assert updated_data.get("structure_kind") == "periodic"
        assert updated_data.get("engine_family") == "qe"


def test_ensure_calculation_identity_preserves_existing():
    """Test that ensure_calculation_identity preserves existing identity fields."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        
        # Create calculation.yaml with existing identity
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = {
            "meta": {"ulid": "calc1", "name": "Test Calc", "slug": "test-calc"},
            "structure_kind": "molecule",
            "engine_family": "pyscf",
            "steps": [],
        }
        calc_yaml.write_text(yaml.safe_dump(calc_data))
        
        # Ensure identity (should not change existing values)
        ensure_calculation_identity(calc_dir)
        
        # Read back and verify unchanged
        updated_data = yaml.safe_load(calc_yaml.read_text())
        assert updated_data.get("structure_kind") == "molecule"
        assert updated_data.get("engine_family") == "pyscf"


def test_ensure_calculation_identity_no_calc_yaml_does_nothing():
    """Test that ensure_calculation_identity does nothing if calculation.yaml doesn't exist."""
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        
        # No calculation.yaml - should not crash
        ensure_calculation_identity(calc_dir)
        
        # Verify no file created
        assert not (calc_dir / "calculation.yaml").exists()


@pytest.mark.parametrize("existing_kind,existing_family,new_kind,new_family,should_raise", [
    (None, None, "periodic", "qe", False),  # First-time set allowed
    ("periodic", "qe", "periodic", "qe", False),  # Same values allowed
    ("periodic", "qe", "molecule", "pyscf", True),  # Changing values raises
    ("periodic", "qe", "periodic", "pyscf", True),  # Changing engine_family raises
    ("periodic", "qe", "molecule", "qe", True),  # Changing structure_kind raises
])
def test_save_calculation_immutability(
    existing_kind, existing_family, new_kind, new_family, should_raise
):
    """Test that save_calculation enforces immutability of identity fields."""
    from quantumvitas.core.models import save_calculation, ResourceMeta
    
    with TemporaryDirectory() as tmpdir:
        calc_dir = Path(tmpdir) / "test_calc"
        calc_dir.mkdir()
        calc_yaml = calc_dir / "calculation.yaml"
        
        # Create initial calculation.yaml if existing values provided
        if existing_kind is not None or existing_family is not None:
            calc_data = {
                "meta": {"ulid": "calc1", "name": "Test", "slug": "test"},
            }
            if existing_kind:
                calc_data["structure_kind"] = existing_kind
            if existing_family:
                calc_data["engine_family"] = existing_family
            calc_yaml.write_text(yaml.safe_dump(calc_data))
        
        # Create model with new values
        meta = ResourceMeta(ulid="calc1",
            name="Test",
            slug="test",
            path="calculations/test",
            kind="calculation",
        )
        model = CalculationModel(
            meta=meta,
            structure_kind=new_kind,
            engine_family=new_family,
        )
        
        # Attempt to save
        if should_raise:
            with pytest.raises(ValueError, match="immutable"):
                save_calculation(model, calc_dir)
        else:
            # Should not raise
            save_calculation(model, calc_dir)
            # Verify values saved
            saved_data = yaml.safe_load(calc_yaml.read_text())
            assert saved_data.get("structure_kind") == new_kind
            assert saved_data.get("engine_family") == new_family

