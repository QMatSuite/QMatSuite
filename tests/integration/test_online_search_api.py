"""
Integration tests for online structure search API.

PR0: Tests for QVService.OnlineSearch API methods.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from quantumvitas.api import QVService
from quantumvitas.api.types.online_search import (
    SearchResultDTO,
    CandidateDTO,
    StructureRefDTO,
    StructureDocDTO,
    ProviderListDTO,
    OnlineSourcesPatchDTO,
    OnlineSourcesSettingsDTO,
)


class TestOnlineSearchAPI:
    """Test QVService.OnlineSearch API methods."""
    
    def test_search_structures_crystal_mode(self):
        """Test search_structures with crystal mode."""
        # Mock the underlying search_online_structures function
        from quantumvitas.io.online_search import CandidateSummary
        
        mock_candidates = [
            CandidateSummary(
                candidate_id="opt_mp-123",
                label="Si (2 sites)",
                source="optimade",
                source_id="mp-123",
                nsites=2,
                spacegroup="Fd-3m",
                flags=[],
                score=1.0,
            ),
        ]
        
        with patch('quantumvitas.io.online_search.search_online_structures') as mock_search:
            mock_search.return_value = ("optimade", mock_candidates, [None], "https://optimade.materialsproject.org")
            
            result = QVService.OnlineSearch.search_structures(
                query="Si",
                mode="crystal",
                limit=10,
            )
            
            assert isinstance(result, SearchResultDTO)
            assert result.query == "Si"
            assert result.mode == "crystal"
            assert len(result.candidates) == 1
            assert result.candidates[0].candidate_id == "opt_mp-123"
            assert result.candidates[0].structure_type == "crystal"
            assert "optimade" in result.providers_queried
    
    def test_search_structures_molecule_mode(self):
        """Test search_structures with molecule mode (stub for PR4)."""
        # PR0: Molecule mode not yet implemented, should return empty results
        with patch('quantumvitas.io.online_search.search_online_structures') as mock_search:
            mock_search.return_value = ("none", [], [], None)
            
            result = QVService.OnlineSearch.search_structures(
                query="caffeine",
                mode="molecule",
                limit=10,
            )
            
            assert isinstance(result, SearchResultDTO)
            assert result.query == "caffeine"
            assert result.mode == "molecule"
            assert len(result.candidates) == 0
    
    def test_search_structures_auto_mode(self):
        """Test search_structures with auto mode."""
        from quantumvitas.io.online_search import CandidateSummary
        
        mock_candidates = [
            CandidateSummary(
                candidate_id="opt_mp-123",
                label="H2O (3 sites)",
                source="optimade",
                source_id="mp-123",
                nsites=3,
                spacegroup=None,
                flags=[],
                score=1.0,
            ),
        ]
        
        with patch('quantumvitas.io.online_search.search_online_structures') as mock_search:
            mock_search.return_value = ("optimade", mock_candidates, [None], "https://optimade.materialsproject.org")
            
            result = QVService.OnlineSearch.search_structures(
                query="H2O",
                mode="auto",
                limit=10,
            )
            
            assert isinstance(result, SearchResultDTO)
            assert result.mode == "auto"
            assert len(result.candidates) > 0
    
    def test_fetch_structure_optimade(self):
        """Test fetch_structure for OPTIMADE candidate."""
        from quantumvitas.io.online_cache import CandidateSummary, SessionInfo
        from pymatgen.core import Structure, Lattice
        
        # Create mock structure
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        # Mock cache methods
        with patch('quantumvitas.io.online_cache.OnlineStructureCache') as MockCache:
            mock_cache = MockCache.return_value
            # get_candidates returns a list
            mock_cache.get_candidates.return_value = [
                CandidateSummary(
                    candidate_id="opt_mp-123",
                    label="Si (2 sites)",
                    source="optimade",
                    source_id="mp-123",
                    nsites=2,
                ),
            ]
            mock_cache.get_structure.return_value = None  # Not in cache, needs fetch
            mock_cache.get_session_info.return_value = SessionInfo(
                session_id="test-session",
                query="Si",
                created_at=1234567890,
                source_summary="optimade|base=https://optimade.materialsproject.org",
            )
            
            # Mock fetch_structure_from_optimade
            with patch('quantumvitas.io.online_search.fetch_structure_from_optimade') as mock_fetch:
                mock_fetch.return_value = (structure, {"data": {"id": "mp-123"}})
                
                from quantumvitas.api.types.online_search import StructureRefDTO
                ref = StructureRefDTO(
                    session_id="test-session",
                    candidate_id="opt_mp-123",
                )
                
                result = QVService.OnlineSearch.fetch_structure(ref)
                
                assert isinstance(result, StructureDocDTO)
                assert result.structure_type == "crystal"
                assert result.formula == "Si"
                assert len(result.atoms) == 2
                assert result.lattice is not None
                assert result.pbc == [True, True, True]
    
    def test_fetch_structure_uses_global_cache(self):
        """Test that fetch_structure uses global cache location."""
        from quantumvitas.core.paths import get_qmatsuite_home_root
        from quantumvitas.io.online_cache import OnlineStructureCache
        
        # Verify cache uses global location
        cache = OnlineStructureCache()
        expected_cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
        assert cache.cache_dir == expected_cache_dir
    
    def test_list_providers(self):
        """Test list_providers (stub for PR0)."""
        result = QVService.OnlineSearch.list_providers()
        
        assert isinstance(result, ProviderListDTO)
        assert len(result.optimade_providers) > 0
        assert result.optimade_providers[0].id == "mp"
        assert result.pubchem_enabled is False  # PR4 will enable
        assert result.materials_project_enabled is False  # PR5 will enable
    
    def test_update_online_sources(self):
        """Test update_online_sources (stub for PR0)."""
        patch_dto = OnlineSourcesPatchDTO(
            pubchem_enabled=True,
        )
        
        result = QVService.OnlineSearch.update_online_sources(patch_dto)
        
        assert isinstance(result, OnlineSourcesSettingsDTO)
        assert result.timeout_seconds == 8.0
        assert result.max_results_per_provider == 10
        assert result.max_total_results == 50

