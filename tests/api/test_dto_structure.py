"""
Test Structure DTO.

Tests for StructureDTO.
"""

import pytest

from qmatsuite.api.types.common import MetaDTO
from qmatsuite.api.types.structure import StructureDTO


def test_structure_dto_required_fields():
    """StructureDTO has required fields."""
    dto = StructureDTO(
        structure_ulid="01HX7YPVK8DQNZPMJ4GHAB5678",
        formula="Si8",
        num_atoms=8
    )
    d = dto.to_dict()
    assert d["structure_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB5678"
    assert d["formula"] == "Si8"
    assert d["num_atoms"] == 8


def test_structure_dto_no_positions_field():
    """StructureDTO must NOT have positions or species arrays."""
    dto = StructureDTO(
        structure_ulid="01HX7YPVK8DQNZPMJ4GHAB5678",
        formula="Si8",
        num_atoms=8
    )
    d = dto.to_dict()
    assert "positions" not in d
    assert "species" not in d


def test_structure_dto_with_crystallographic():
    """StructureDTO can include crystallographic info."""
    dto = StructureDTO(
        structure_ulid="01HX7YPVK8DQNZPMJ4GHAB5678",
        formula="Si8",
        num_atoms=8,
        space_group="Fd-3m",
        point_group="m-3m",
        cell_volume_ang3=160.103,
        lattice_abc=[5.43, 5.43, 5.43],
        lattice_angles=[90.0, 90.0, 90.0]
    )
    d = dto.to_dict()
    assert d["space_group"] == "Fd-3m"
    assert d["cell_volume_ang3"] == 160.103
    assert d["lattice_abc"] == [5.43, 5.43, 5.43]


def test_structure_dto_with_meta():
    """StructureDTO can include MetaDTO."""
    dto = StructureDTO(
        structure_ulid="01HX7YPVK8DQNZPMJ4GHAB5678",
        formula="Si8",
        num_atoms=8,
        meta=MetaDTO(
            slug="si-bulk",
            name="Silicon FCC",
            description="Conventional FCC silicon cell"
        )
    )
    d = dto.to_dict()
    assert d["meta"]["slug"] == "si-bulk"
    assert d["meta"]["name"] == "Silicon FCC"

