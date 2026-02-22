"""Tests for AuthoringOps IR: serialization, is_bulk_op, value type validation."""

from __future__ import annotations

import pytest

from qmatsuite.demo_store.authoring_ops import (
    AddStep,
    ConfigureSpeciesMap,
    CreateCalculation,
    ImportStructure,
    InitProject,
    ReplaceMap,
    SetField,
    UnsetField,
    is_bulk_op,
    ops_from_json,
    ops_to_json,
)


class TestSerialization:
    """Roundtrip JSON serialization."""

    def test_roundtrip_all_op_types(self):
        ops = [
            InitProject(name="test"),
            ImportStructure(name="Si", structure_data={"lattice": []}),
            CreateCalculation(name="calc", engine_family="qe", structure_selector="si"),
            AddStep(calc_selector="calc", step_type_gen="scf", name="scf"),
            SetField(target="step:calc/scf", pointer="/parameters/CONTROL/calculation", value="scf"),
            UnsetField(target="step:calc/scf", pointer="/parameters/CONTROL/outdir"),
            ReplaceMap(target="step:calc/scf", pointer="/cards/K_POINTS", value={"option": "automatic"}),
            ConfigureSpeciesMap(calc_selector="calc", species_map={"Si": {"pseudo": "Si.upf"}}),
        ]
        json_str = ops_to_json(ops)
        restored = ops_from_json(json_str)
        assert len(restored) == len(ops)
        for orig, rest in zip(ops, restored):
            assert type(orig) is type(rest)
            assert orig == rest

    def test_setfield_with_list_value(self):
        op = SetField(target="step:c/s", pointer="/parameters/kpoints", value=[4, 4, 4])
        json_str = ops_to_json([op])
        restored = ops_from_json(json_str)
        assert restored[0].value == [4, 4, 4]


class TestIsBulkOp:
    """is_bulk_op detects forbidden bulk operations."""

    def test_replacemap_at_parameters_is_bulk(self):
        op = ReplaceMap(target="step:c/s", pointer="/parameters", value={"CONTROL": {}})
        assert is_bulk_op(op) is True

    def test_replacemap_at_card_is_not_bulk(self):
        op = ReplaceMap(target="step:c/s", pointer="/cards/K_POINTS", value={"option": "auto"})
        assert is_bulk_op(op) is False

    def test_setfield_is_never_bulk(self):
        op = SetField(target="step:c/s", pointer="/parameters/ENCUT", value=240)
        assert is_bulk_op(op) is False

    def test_unsetfield_is_never_bulk(self):
        op = UnsetField(target="step:c/s", pointer="/parameters")
        assert is_bulk_op(op) is False

    def test_addstep_is_never_bulk(self):
        op = AddStep(calc_selector="c", step_type_gen="scf", name="scf")
        assert is_bulk_op(op) is False


class TestOpFields:
    """Op dataclass field validation."""

    def test_setfield_frozen(self):
        op = SetField(target="step:c/s", pointer="/x", value=1)
        with pytest.raises(AttributeError):
            op.value = 2  # type: ignore[misc]

    def test_op_field_is_auto(self):
        """The 'op' field is set automatically."""
        assert InitProject(name="test").op == "InitProject"
        assert SetField(target="t", pointer="/x", value=1).op == "SetField"
        assert UnsetField(target="t", pointer="/x").op == "UnsetField"
        assert ReplaceMap(target="t", pointer="/x", value={}).op == "ReplaceMap"
