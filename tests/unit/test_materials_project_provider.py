"""
Unit tests for Materials Project native API provider.

PR5: Tests for MP native search, API key validation, and candidate conversion.
"""

from unittest.mock import patch, Mock, MagicMock
import pytest

from quantumvitas.io.providers.materials_project import (
    search_materials_project,
    validate_api_key,
    _mp_doc_to_candidate,
    MPSummaryDoc,
    MP_API_AVAILABLE,
)
from quantumvitas.io.providers.optimade import Candidate


class TestMaterialsProjectSearch:
    """Test MP native API search functionality."""
    
    def test_search_success(self):
        """Test successful MP native search."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        # Mock MPRester and search results
        mock_doc = {
            "material_id": "mp-123",
            "structure": Mock(),  # Mock pymatgen Structure
            "band_gap": 1.1,
            "formation_energy_per_atom": -0.5,
            "energy_above_hull": 0.0,
            "is_stable": True,
            "symmetry": {"number": 227},
        }
        
        # Mock structure properties
        mock_structure = Mock()
        mock_structure.composition.reduced_formula = "Si"
        mock_structure.__len__ = Mock(return_value=2)
        mock_structure.sites = []
        mock_doc["structure"] = mock_structure
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.return_value = [mock_doc]
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    candidates = search_materials_project("Si", "test-api-key", max_results=10)
                    
                    assert len(candidates) == 1
                    assert candidates[0].entry_id == "mp-123"
                    assert candidates[0].provider_id == "mp-native"
                    assert candidates[0].reduced_formula == "Si"
                    assert candidates[0].metadata["band_gap"] == 1.1
                    assert candidates[0].metadata["is_stable"] is True
    
    def test_search_no_results(self):
        """Test MP search with no results."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.return_value = []
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    candidates = search_materials_project("XyZ999", "test-api-key", max_results=10)
                    
                    assert len(candidates) == 0
    
    def test_search_invalid_api_key(self):
        """Test MP search with invalid API key."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.side_effect = Exception("401 Unauthorized: Invalid API key")
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    with pytest.raises(ValueError, match="Invalid MP API key"):
                        search_materials_project("Si", "invalid-key", max_results=10)
    
    def test_search_empty_api_key(self):
        """Test MP search with empty API key."""
        # Mock MP_API_AVAILABLE to True so we can test the empty key check
        with patch('quantumvitas.io.providers.materials_project.MP_API_AVAILABLE', True):
            with pytest.raises(ValueError, match="MP API key is required"):
                search_materials_project("Si", "", max_results=10)
    
    def test_search_mp_api_not_available(self):
        """Test MP search when mp-api is not available."""
        with patch('quantumvitas.io.providers.materials_project.MP_API_AVAILABLE', False):
            with pytest.raises(ValueError, match="mp-api package not available"):
                search_materials_project("Si", "test-key", max_results=10)
    
    def test_search_api_error(self):
        """Test MP search with API error (non-auth)."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.side_effect = Exception("500 Internal Server Error")
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    with pytest.raises(ValueError, match="MP native API search failed"):
                        search_materials_project("Si", "test-key", max_results=10)


class TestAPIKeyValidation:
    """Test MP API key validation."""
    
    def test_validate_api_key_success(self):
        """Test successful API key validation."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.return_value = [{"material_id": "mp-123"}]
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    is_valid = validate_api_key("test-api-key")
                    
                    assert is_valid is True
    
    def test_validate_api_key_invalid(self):
        """Test API key validation with invalid key."""
        if not MP_API_AVAILABLE:
            pytest.skip("mp-api not available")
        
        mock_mpr = MagicMock()
        mock_mpr.summary.search.side_effect = Exception("401 Unauthorized")
        
        with patch('quantumvitas.io.providers.materials_project.MPRester', return_value=mock_mpr):
            with patch('quantumvitas.io.providers.materials_project.MPRester.__enter__', return_value=mock_mpr):
                with patch('quantumvitas.io.providers.materials_project.MPRester.__exit__', return_value=None):
                    is_valid = validate_api_key("invalid-key")
                    
                    assert is_valid is False
    
    def test_validate_api_key_empty(self):
        """Test API key validation with empty key."""
        is_valid = validate_api_key("")
        
        assert is_valid is False
    
    def test_validate_api_key_mp_api_not_available(self):
        """Test API key validation when mp-api is not available."""
        with patch('quantumvitas.io.providers.materials_project.MP_API_AVAILABLE', False):
            is_valid = validate_api_key("test-key")
            
            assert is_valid is False


class TestMPDocToCandidate:
    """Test conversion of MP documents to Candidate objects."""
    
    def test_mp_doc_to_candidate_basic(self):
        """Test basic MP doc to candidate conversion."""
        from pymatgen.core import Structure, Lattice
        
        # Create a simple structure
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])
        
        doc = MPSummaryDoc(
            material_id="mp-123",
            structure=structure,
            band_gap=1.1,
            formation_energy_per_atom=-0.5,
            energy_above_hull=0.0,
            is_stable=True,
            symmetry={"number": 227},
        )
        
        candidate = _mp_doc_to_candidate(doc)
        
        assert candidate.entry_id == "mp-123"
        assert candidate.provider_id == "mp-native"
        assert candidate.reduced_formula == "Si"
        assert candidate.nsites == 2
        assert candidate.space_group_number == 227
        assert candidate.metadata["band_gap"] == 1.1
        assert candidate.metadata["formation_energy_per_atom"] == -0.5
        assert candidate.metadata["is_stable"] is True
    
    def test_mp_doc_to_candidate_minimal(self):
        """Test MP doc to candidate conversion with minimal data."""
        from pymatgen.core import Structure, Lattice
        
        # Create a simple structure
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Fe"], [[0, 0, 0]])
        
        doc = MPSummaryDoc(
            material_id="mp-456",
            structure=structure,
        )
        
        candidate = _mp_doc_to_candidate(doc)
        
        assert candidate.entry_id == "mp-456"
        assert candidate.provider_id == "mp-native"
        assert candidate.reduced_formula == "Fe"
        assert candidate.nsites == 1
        assert candidate.space_group_number is None
        assert "band_gap" not in candidate.metadata

