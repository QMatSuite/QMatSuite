"""
Test Analysis DTOs.

Tests for AnalysisRefDTO and AnalysisSummaryDTO.
"""

import pytest

from qmatsuite.api.types.analysis import AnalysisRefDTO, AnalysisSummaryDTO


def test_analysis_ref_dto_required_fields():
    """AnalysisRefDTO has all required fields."""
    dto = AnalysisRefDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        property_name="band_structure",
        artifact_path=".qmatsuite/artifacts/01HX.../bands.hdf5",
        artifact_format="hdf5",
        artifact_sha256="a1b2c3d4e5f6",
        artifact_size_bytes=2456789,
        summary={
            "n_bands": 120,
            "n_kpoints": 150,
            "fermi_energy_ev": 6.234
        }
    )
    d = dto.to_dict()
    assert d["calc_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert d["property_name"] == "band_structure"
    assert d["artifact_format"] == "hdf5"
    assert d["summary"]["n_bands"] == 120


def test_analysis_ref_dto_with_preview():
    """AnalysisRefDTO can include preview."""
    dto = AnalysisRefDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        property_name="band_structure",
        artifact_path=".qmatsuite/artifacts/01HX.../bands.hdf5",
        artifact_format="hdf5",
        artifact_sha256="a1b2c3d4e5f6",
        artifact_size_bytes=2456789,
        summary={"n_bands": 120},
        preview={
            "kpoint_labels": ["Γ", "X", "M", "Γ"],
            "kpoint_indices": [0, 37, 75, 149]
        }
    )
    d = dto.to_dict()
    assert d["preview"]["kpoint_labels"] == ["Γ", "X", "M", "Γ"]


def test_analysis_summary_dto_required_fields():
    """AnalysisSummaryDTO has required identity fields."""
    dto = AnalysisSummaryDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012"
    )
    d = dto.to_dict()
    assert d["calc_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert d["step_ulid"] == "01HX7YPVK8DQNZPMJ4GHAB9012"


def test_analysis_summary_dto_with_results():
    """AnalysisSummaryDTO can include key results."""
    dto = AnalysisSummaryDTO(
        calc_ulid="01HX7YPVK8DQNZPMJ4GHAB1234",
        step_ulid="01HX7YPVK8DQNZPMJ4GHAB9012",
        converged=True,
        total_energy_ev=-310.456789,
        fermi_energy_ev=6.234,
        band_gap_ev=0.52,
        band_gap_type="indirect",
        available_properties=["band_structure", "dos", "charge_density"]
    )
    d = dto.to_dict()
    assert d["converged"] is True
    assert d["total_energy_ev"] == -310.456789
    assert d["band_gap_type"] == "indirect"
    assert len(d["available_properties"]) == 3

