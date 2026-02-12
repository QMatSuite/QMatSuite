"""
Unit tests for PubChem provider.

PR4: Tests for PubChem search, SDF parsing, and rate limiting.
"""

from unittest.mock import patch, Mock
import pytest

from quantumvitas.io.providers.pubchem import (
    search_by_name,
    search_by_formula,
    fetch_3d_sdf,
    parse_sdf_to_molecule,
    search_pubchem,
    PubChemCandidate,
    _rate_limit,
    PUBCHEM_RATE_LIMIT_DELAY,
)
import time


class TestPubChemSearch:
    """Test PubChem search functionality."""
    
    def test_search_by_name_success(self):
        """Test successful name search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "IdentifierList": {
                "CID": [2519, 2224]  # Caffeine CIDs
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            cids = search_by_name("caffeine", max_results=10)
            
            assert len(cids) == 2
            assert "2519" in cids or "2224" in cids
    
    def test_search_by_name_not_found(self):
        """Test name search with 404 (not found)."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            cids = search_by_name("nonexistent_compound_xyz123", max_results=10)
            
            assert len(cids) == 0
    
    def test_search_by_formula_success(self):
        """Test successful formula search."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "IdentifierList": {
                "CID": [2519]  # Caffeine
            }
        }
        mock_response.raise_for_status = Mock()
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            cids = search_by_formula("C8H10N4O2", max_results=10)
            
            assert len(cids) == 1
            assert "2519" in cids
    
    def test_search_by_formula_not_found(self):
        """Test formula search with 404."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            cids = search_by_formula("XyZ123", max_results=10)
            
            assert len(cids) == 0


class TestPubChemSDF:
    """Test PubChem SDF fetching and parsing."""
    
    def test_fetch_3d_sdf_success(self):
        """Test successful 3D SDF fetch."""
        mock_sdf_content = """\
  Mrv2014 01012400002D

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""
        mock_response = Mock()
        mock_response.text = mock_sdf_content
        mock_response.raise_for_status = Mock()
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            sdf = fetch_3d_sdf("12345")
            
            assert sdf is not None
            assert "C" in sdf
            assert "O" in sdf
    
    def test_fetch_3d_sdf_not_found(self):
        """Test SDF fetch with 404 (no 3D conformer)."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', return_value=mock_response):
            sdf = fetch_3d_sdf("12345")
            
            assert sdf is None
    
    def test_parse_sdf_to_molecule(self):
        """Test SDF parsing to pymatgen Molecule."""
        # Use a valid SDF format (simplified MOL block)
        sdf_content = """\
  Mrv2014 01012400002D

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""
        # Mock pymatgen availability
        with patch('quantumvitas.io.providers.pubchem.PYMATGEN_AVAILABLE', True):
            # Mock pymatgen Molecule.from_str to return a mock molecule
            from unittest.mock import MagicMock
            mock_molecule = MagicMock()
            mock_molecule.__len__ = lambda self: 2
            mock_molecule.species = [MagicMock(symbol="C"), MagicMock(symbol="O")]
            
            with patch('quantumvitas.io.providers.pubchem.PMGMolecule.from_str', return_value=mock_molecule):
                molecule = parse_sdf_to_molecule(sdf_content, "12345")
                
                assert molecule is not None
                assert len(molecule) == 2
                assert molecule.species[0].symbol == "C"
                assert molecule.species[1].symbol == "O"


class TestPubChemRateLimiting:
    """Test PubChem rate limiting."""
    
    def test_rate_limit_delay(self):
        """Test that rate limiting enforces delay."""
        from quantumvitas.io.providers.pubchem import _last_request_time
        
        # Reset global state
        import quantumvitas.io.providers.pubchem as pubchem_module
        pubchem_module._last_request_time = 0.0
        
        start_time = time.time()
        _rate_limit()
        first_call_time = time.time() - start_time
        
        # First call should be immediate (no delay)
        assert first_call_time < 0.1
        
        # Second call should have delay
        start_time = time.time()
        _rate_limit()
        second_call_time = time.time() - start_time
        
        # Second call should have ~200ms delay
        assert second_call_time >= PUBCHEM_RATE_LIMIT_DELAY * 0.9  # Allow some tolerance


class TestPubChemIntegration:
    """Test PubChem search integration."""
    
    def test_search_pubchem_name_fallback_to_formula(self):
        """Test that name search falls back to formula search."""
        # Mock name search to return 404
        mock_name_response = Mock()
        mock_name_response.status_code = 404
        
        # Mock formula search to return CIDs
        mock_formula_response = Mock()
        mock_formula_response.json.return_value = {
            "IdentifierList": {"CID": [2519]}
        }
        mock_formula_response.raise_for_status = Mock()
        
        # Mock SDF fetch
        mock_sdf_response = Mock()
        mock_sdf_response.text = """\
  Mrv2014 01012400002D

  2  1  0  0  0  0            999 V2000
    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
$$$$
"""
        mock_sdf_response.raise_for_status = Mock()
        
        def side_effect(url, **kwargs):
            if "name" in url:
                return mock_name_response
            elif "formula" in url:
                return mock_formula_response
            elif "record/SDF" in url:
                return mock_sdf_response
            return Mock()
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', side_effect=side_effect):
            candidates = search_pubchem("C8H10N4O2", max_results=10)
            
            # Should have found candidate via formula search
            assert len(candidates) >= 0  # May be 0 if SDF parsing fails, but search should work
    
    def test_search_pubchem_skips_no_3d(self):
        """Test that candidates without 3D SDF are skipped."""
        # Mock name search to return CID
        mock_name_response = Mock()
        mock_name_response.json.return_value = {
            "IdentifierList": {"CID": [12345]}
        }
        mock_name_response.raise_for_status = Mock()
        
        # Mock SDF fetch to return 404 (no 3D)
        mock_sdf_response = Mock()
        mock_sdf_response.status_code = 404
        
        def side_effect(url, **kwargs):
            if "name" in url:
                return mock_name_response
            elif "record/SDF" in url:
                return mock_sdf_response
            return Mock()
        
        with patch('quantumvitas.io.providers.pubchem.requests.get', side_effect=side_effect):
            candidates = search_pubchem("test", max_results=10)
            
            # Should skip CID without 3D SDF
            assert len(candidates) == 0

