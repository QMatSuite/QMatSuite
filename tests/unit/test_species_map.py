"""
Tests for calculation-level species_map (pseudopotential mapping) semantics.

This module tests the TASK 2 refactor: moving pseudo mapping from step-level
species_overrides to calculation-level species_map.
"""

import pytest
from pathlib import Path
from typing import Dict, Any


class TestSpeciesMapMigration:
    """Test migration from step-level species_overrides to calc-level species_map."""
    
    def test_migrate_empty_returns_none(self):
        """Migration with no species_overrides returns None species_map."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta, migrate_species_overrides_to_calc
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation")
        )
        
        result = migrate_species_overrides_to_calc(calc, [None, None, {}])
        assert result.species_map is None
    
    def test_migrate_single_step(self):
        """Migration from single step's species_overrides works."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta, migrate_species_overrides_to_calc
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation")
        )
        
        step_overrides = [
            {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "mass": 28.0855}},
        ]
        
        result = migrate_species_overrides_to_calc(calc, step_overrides)
        assert result.species_map is not None
        assert "Si" in result.species_map
        assert result.species_map["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
        assert result.species_map["Si"]["mass"] == 28.0855
    
    def test_migrate_multiple_steps_consistent(self):
        """Migration from multiple steps with consistent overrides works."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta, migrate_species_overrides_to_calc
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation")
        )
        
        step_overrides = [
            {"Si": {"pseudopot": "Si.UPF", "mass": 28.0}},
            {"Si": {"pseudopot": "Si.UPF", "mass": 28.0}},  # Same as first
            None,  # Some steps don't have it
        ]
        
        result = migrate_species_overrides_to_calc(calc, step_overrides)
        assert result.species_map is not None
        assert result.species_map["Si"]["pseudopot"] == "Si.UPF"
    
    def test_migrate_conflict_raises(self):
        """Migration with conflicting pseudopot mappings raises ValueError."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta, migrate_species_overrides_to_calc
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation")
        )
        
        step_overrides = [
            {"Si": {"pseudopot": "Si_v1.UPF", "mass": 28.0}},
            {"Si": {"pseudopot": "Si_v2.UPF", "mass": 28.0}},  # Different pseudo!
        ]
        
        with pytest.raises(ValueError, match="Conflicting pseudopotential mapping"):
            migrate_species_overrides_to_calc(calc, step_overrides)
    
    def test_skip_if_species_map_already_set(self):
        """Migration is skipped if species_map is already set."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta, migrate_species_overrides_to_calc
        
        existing_map = {"Si": {"pseudopot": "existing.UPF"}}
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation"),
            species_map=existing_map,
        )
        
        step_overrides = [
            {"Si": {"pseudopot": "different.UPF"}},
        ]
        
        result = migrate_species_overrides_to_calc(calc, step_overrides)
        # Should not change - already set
        assert result.species_map == existing_map


class TestMergeSpeciesMaps:
    """Test merge_species_maps helper function."""
    
    def test_merge_empty(self):
        """Merging empty maps returns empty."""
        from quantumvitas.calculation.folder_import import merge_species_maps
        
        result = merge_species_maps({}, {})
        assert result == {}
    
    def test_merge_new_element(self):
        """Merging new element adds it."""
        from quantumvitas.calculation.folder_import import merge_species_maps
        
        existing = {"Si": {"pseudopot": "Si.UPF"}}
        new = {"Ge": {"pseudopot": "Ge.UPF"}}
        
        result = merge_species_maps(existing, new)
        assert "Si" in result
        assert "Ge" in result
    
    def test_merge_consistent(self):
        """Merging consistent mappings succeeds."""
        from quantumvitas.calculation.folder_import import merge_species_maps
        
        existing = {"Si": {"pseudopot": "Si.UPF", "mass": 28.0}}
        new = {"Si": {"pseudopot": "Si.UPF", "mass": 28.0}}
        
        result = merge_species_maps(existing, new)
        assert result["Si"]["pseudopot"] == "Si.UPF"
    
    def test_merge_conflict_raises(self):
        """Merging conflicting pseudopot raises ValueError."""
        from quantumvitas.calculation.folder_import import merge_species_maps
        
        existing = {"Si": {"pseudopot": "Si_v1.UPF"}}
        new = {"Si": {"pseudopot": "Si_v2.UPF"}}
        
        with pytest.raises(ValueError, match="Conflicting pseudopotential"):
            merge_species_maps(existing, new, source_file="test.in")


class TestExtractSpeciesMap:
    """Test extract_species_map_from_qe_input helper function."""
    
    def test_extract_empty(self):
        """Extracting from input without ATOMIC_SPECIES returns empty dict."""
        from quantumvitas.calculation.folder_import import extract_species_map_from_qe_input
        from quantumvitas.io.model import QEInput, QENamelist
        
        qe_input = QEInput(
            namelists=[QENamelist(name="CONTROL", parameters={})],
            cards=[],
        )
        
        result = extract_species_map_from_qe_input(qe_input)
        assert result == {}
    
    def test_extract_with_atomic_species(self):
        """Extracting from input with ATOMIC_SPECIES returns species_map."""
        from quantumvitas.calculation.folder_import import extract_species_map_from_qe_input
        from quantumvitas.io.model import QEInput, QENamelist, QECard, QECardType
        
        qe_input = QEInput(
            namelists=[QENamelist(name="CONTROL", parameters={})],
            cards=[
                QECard(
                    card_type=QECardType.ATOMIC_SPECIES,
                    data=[
                        ["Si", 28.0855, "Si.pbe-n-rrkjus_psl.1.0.0.UPF"],
                    ]
                )
            ],
        )
        
        result = extract_species_map_from_qe_input(qe_input)
        assert "Si" in result
        assert result["Si"]["pseudopot"] == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
        assert result["Si"]["mass"] == 28.0855
    
    def test_extract_skips_placeholder(self):
        """Extracting skips placeholder pseudo names."""
        from quantumvitas.calculation.folder_import import extract_species_map_from_qe_input
        from quantumvitas.io.model import QEInput, QENamelist, QECard, QECardType
        
        qe_input = QEInput(
            namelists=[QENamelist(name="CONTROL", parameters={})],
            cards=[
                QECard(
                    card_type=QECardType.ATOMIC_SPECIES,
                    data=[
                        ["Si", 28.0855, "__MISSING_PSEUDO__Si"],
                    ]
                )
            ],
        )
        
        result = extract_species_map_from_qe_input(qe_input)
        # Should have mass but not pseudopot (placeholder skipped)
        assert "Si" in result
        assert "pseudopot" not in result["Si"]
        assert result["Si"]["mass"] == 28.0855


class TestCalculationModelSpeciesMap:
    """Test CalculationModel species_map serialization."""
    
    def test_round_trip(self):
        """species_map round-trips through to_dict/from_dict."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta
        
        species_map = {
            "Si": {"pseudopot": "Si.UPF", "mass": 28.0855},
            "Ge": {"pseudopot": "Ge.UPF"},
        }
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation"),
            species_map=species_map,
        )
        
        data = calc.to_dict()
        assert "species_map" in data
        assert data["species_map"]["Si"]["pseudopot"] == "Si.UPF"
        
        # Load back
        restored = CalculationModel.from_dict(data)
        assert restored.species_map == species_map
    
    def test_to_dict_omits_none(self):
        """to_dict omits species_map if None."""
        from quantumvitas.core.models import CalculationModel, ResourceMeta
        
        calc = CalculationModel(
            meta=ResourceMeta(id="01TEST", name="test", slug="test", path=".", kind="calculation"),
            species_map=None,
        )
        
        data = calc.to_dict()
        assert "species_map" not in data

