"""
Test DTO frontend compatibility contracts.

These tests ensure that DTOs maintain backward-compatible serialization
for CLI and daemon frontends. These contracts prevent silent breakage
when DTO/API refactors occur.

Contracts tested:
1. DTO serialization contracts (StructureDTO, CalculationDTO, RunResultDTO)
2. Legacy status mapping (COMPLETED -> SUCCESS)
3. Compatibility properties (id/name/slug/path/n_atoms/n_steps)
"""

import pytest

from qmatsuite.api.types.calculation import CalculationDTO
from qmatsuite.api.types.common import MetaDTO
from qmatsuite.api.types.run import RunResultDTO
from qmatsuite.api.types.structure import StructureDTO


class TestStructureDTOContract:
    """Test StructureDTO frontend compatibility contract."""
    
    def test_structure_dto_has_compat_properties_with_meta(self):
        """StructureDTO.to_dict() includes id/name/slug/path/n_atoms when meta exists."""
        meta = MetaDTO(
            ulid="01ABC123",
            name="si-bulk",
            slug="si-bulk",
            path="structures/si-bulk.json"
        )
        dto = StructureDTO(
            structure_ulid="01ABC123",
            formula="Si8",
            num_atoms=8,
            meta=meta
        )
        
        result = dto.to_dict()
        
        # Compatibility properties must be present
        assert result["ulid"] == "01ABC123"
        assert result["name"] == "si-bulk"
        assert result["slug"] == "si-bulk"
        assert result["path"] == "structures/si-bulk.json"
        assert result["n_atoms"] == 8
        # Canonical field also present
        assert result["num_atoms"] == 8
        assert result["structure_ulid"] == "01ABC123"
    
    def test_structure_dto_has_compat_properties_without_meta(self):
        """StructureDTO.to_dict() includes id/n_atoms when meta is None (name/slug/path may be omitted if None)."""
        dto = StructureDTO(
            structure_ulid="01ABC123",
            formula="Si8",
            num_atoms=8,
            meta=None
        )
        
        result = dto.to_dict()
        
        # Compatibility properties must be present (fallback to structure_ulid for id)
        assert result["ulid"] == "01ABC123"  # Falls back to structure_ulid
        assert result["n_atoms"] == 8
        # Canonical fields still present
        assert result["num_atoms"] == 8
        assert result["structure_ulid"] == "01ABC123"
        # name/slug/path are only included if not None (current implementation)
        # This is acceptable for compatibility - frontends should handle missing keys


class TestCalculationDTOContract:
    """Test CalculationDTO frontend compatibility contract."""
    
    def test_calculation_dto_has_compat_properties_with_meta(self):
        """CalculationDTO.to_dict() includes id/name/slug/path/n_steps when meta exists."""
        meta = MetaDTO(
            ulid="01DEF456",
            name="si-dos",
            slug="si-dos",
            path="calculations/si-dos"
        )
        dto = CalculationDTO(
            calc_ulid="01DEF456",
            engine="qe",
            status="completed",
            step_count=3,
            meta=meta
        )
        
        result = dto.to_dict()
        
        # Compatibility properties must be present
        assert result["ulid"] == "01DEF456"
        assert result["name"] == "si-dos"
        assert result["slug"] == "si-dos"
        assert result["path"] == "calculations/si-dos"
        assert result["n_steps"] == 3
        # Canonical field also present
        assert result["step_count"] == 3
        assert result["calc_ulid"] == "01DEF456"

    def test_calculation_dto_has_compat_properties_without_meta(self):
        """CalculationDTO.to_dict() includes id/n_steps when meta is None (name/slug/path may be omitted if None)."""
        dto = CalculationDTO(
            calc_ulid="01DEF456",
            engine="qe",
            status="completed",
            step_count=3,
            meta=None
        )

        result = dto.to_dict()

        # Compatibility properties must be present (fallback to calc_ulid for id)
        assert result["ulid"] == "01DEF456"  # Falls back to calc_ulid
        assert result["n_steps"] == 3
        # Canonical fields still present
        assert result["step_count"] == 3
        assert result["calc_ulid"] == "01DEF456"
        # name/slug/path are only included if not None (current implementation)
        # This is acceptable for compatibility - frontends should handle missing keys


class TestRunResultDTOContract:
    """Test RunResultDTO frontend compatibility contract."""
    
    def test_run_result_dto_has_steps_list(self):
        """RunResultDTO.to_dict() includes steps as list of dicts."""
        dto = RunResultDTO(
            run_ulid="01RUN789",
            calc_ulid="01DEF456",
            status="completed",
            step_ulids=["step1", "step2"],
            _step_details=[
                {
                    "step_ulid": "step1",
                    "step_ulid": "step1",  # Backwards compat
                    "step_type_spec": "qe_scf",
                    "step_type_gen": "scf",
                    "step_type_gen": "scf",  # Backwards compat
                    "status": "completed",
                    "message": "Step completed",
                    "metrics": {"energy": -10.5}
                },
                {
                    "step_ulid": "step2",
                    "step_ulid": "step2",  # Backwards compat
                    "step_type_spec": "qe_nscf",
                    "step_type_gen": "nscf",
                    "step_type_gen": "nscf",  # Backwards compat
                    "status": "completed",
                    "message": None,
                    "metrics": {}
                }
            ],
            io_dir="/path/to/io",
            input_file="/path/to/input.in",
            output_file="/path/to/output.out"
        )
        
        result = dto.to_dict()
        
        # Steps must be a list of dicts
        assert "steps" in result
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) == 2
        
        # Each step must have required keys
        step1 = result["steps"][0]
        assert step1["step_ulid"] == "step1"
        assert step1["step_type_spec"] == "qe_scf"
        assert step1["step_type_gen"] == "scf"
        assert step1["status"] == "completed"
        assert step1["message"] == "Step completed"
        assert step1["metrics"] == {"energy": -10.5}

        step2 = result["steps"][1]
        assert step2["step_ulid"] == "step2"
        assert step2["step_type_spec"] == "qe_nscf"
        assert step2["step_type_gen"] == "nscf"
        assert step2["status"] == "completed"
        assert step2["message"] is None
        assert step2["metrics"] == {}
    
    def test_run_result_dto_has_io_fields(self):
        """RunResultDTO.to_dict() includes io_dir/input_file/output_file."""
        dto = RunResultDTO(
            run_ulid="01RUN789",
            calc_ulid="01DEF456",
            status="completed",
            step_ulids=[],
            io_dir="/path/to/io",
            input_file="/path/to/input.in",
            output_file="/path/to/output.out"
        )
        
        result = dto.to_dict()
        
        assert result["io_dir"] == "/path/to/io"
        assert result["input_file"] == "/path/to/input.in"
        assert result["output_file"] == "/path/to/output.out"
    
    def test_run_result_dto_legacy_status_mapping(self):
        """RunResultDTO.to_dict() maps canonical status to legacy status for frontends."""
        test_cases = [
            ("completed", "SUCCESS"),
            ("failed", "FAILED"),
            ("running", "RUNNING"),
            ("submitted", "PENDING"),
            ("pending", "PENDING"),
            ("cancelled", "CANCELLED"),
        ]
        
        for canonical_status, expected_legacy in test_cases:
            dto = RunResultDTO(
                run_ulid="01RUN789",
                calc_ulid="01DEF456",
                status=canonical_status,
                step_ulids=[]
            )
            
            result = dto.to_dict()
            
            # Status must be mapped to legacy format
            assert result["status"] == expected_legacy, \
                f"Status {canonical_status} should map to {expected_legacy}, got {result['status']}"
    
    def test_run_result_dto_steps_empty_when_no_details(self):
        """RunResultDTO.to_dict() handles empty steps gracefully."""
        dto = RunResultDTO(
            run_ulid="01RUN789",
            calc_ulid="01DEF456",
            status="completed",
            step_ulids=[],
            _step_details=None
        )
        
        result = dto.to_dict()
        
        # Steps should be present (may be empty list)
        assert "steps" in result
        # If steps property returns empty list, to_dict should handle it
        # (steps property creates minimal step objects from step_ids when _step_details is None)
        assert isinstance(result.get("steps"), list)

