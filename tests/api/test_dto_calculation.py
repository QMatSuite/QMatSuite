"""
Test Calculation and Step DTOs.

Tests for CalculationDTO and StepDTO.
"""

import pytest

from quantumvitas.api.types.calculation import CalculationDTO, StepDTO
from quantumvitas.api.types.common import MetaDTO


def test_calculation_dto_required_fields():
    """CalculationDTO has required ULID fields."""
    dto = CalculationDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        engine="qe",
        status="completed"
    )
    d = dto.to_dict()
    assert d["calc_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert d["engine"] == "qe"
    assert d["status"] == "completed"


def test_calculation_dto_no_params_field():
    """CalculationDTO must NOT have params field."""
    dto = CalculationDTO(calc_ulid="x", engine="qe", status="pending")
    d = dto.to_dict()
    assert "params" not in d


def test_calculation_dto_with_meta():
    """CalculationDTO can include MetaDTO."""
    dto = CalculationDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        engine="qe",
        status="completed",
        meta=MetaDTO(
            slug="si-scf",
            name="Silicon SCF",
            description="SCF calculation for bulk silicon"
        )
    )
    d = dto.to_dict()
    assert d["meta"]["slug"] == "si-scf"
    assert d["meta"]["name"] == "Silicon SCF"


def test_calculation_dto_with_references():
    """CalculationDTO can include structure and step references."""
    dto = CalculationDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        engine="qe",
        status="completed",
        structure_ulid="01HX7YPVK8DQNZPMJ4GHAB5678",
        step_ulids=["01HX7YPVK8DQNZPMJ4GHAB9012", "01HX7YPVK8DQNZPMJ4GHAB3456"]
    )
    d = dto.to_dict()
    assert d["structure_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB5678"
    assert len(d["step_ulids"]) == 2


def test_step_dto_required_fields():
    """StepDTO has required ULID fields."""
    dto = StepDTO(
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_type_spec="qe_scf",
        step_type_gen="scf",
        status="completed"
    )
    d = dto.to_dict()
    assert d["step_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB9012"
    assert d["calc_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert d["step_type_spec"] == "qe_scf"
    assert d["step_type_gen"] == "scf"
    assert d["status"] == "completed"


def test_step_dto_with_execution_details():
    """StepDTO can include execution details."""
    dto = StepDTO(
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_type_spec="qe_scf",
        step_type_gen="scf",
        status="completed",
        started_at="2026-01-21T14:00:00Z",
        completed_at="2026-01-21T14:05:30Z",
        duration_seconds=330.5,
        exit_code=0
    )
    d = dto.to_dict()
    assert d["started_at"] == "2026-01-21T14:00:00Z"
    assert d["duration_seconds"] == 330.5
    assert d["exit_code"] == 0


def test_step_dto_with_error():
    """StepDTO can include error message."""
    dto = StepDTO(
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_type_spec="qe_scf",
        step_type_gen="scf",
        status="failed",
        error_message="Convergence not achieved"
    )
    d = dto.to_dict()
    assert d["error_message"] == "Convergence not achieved"

