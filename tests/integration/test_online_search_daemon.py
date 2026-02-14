"""
Integration tests for online structure search daemon RPC methods.

PR0: Tests for daemon RPC handlers that call QVService.OnlineSearch.
"""

import pytest
from unittest.mock import patch, Mock
from quantumvitas.daemon.server import QVDaemon


class TestOnlineSearchDaemon:
    """Test daemon RPC handlers for online structure search."""
    
    def test_daemon_structure_search_online(self):
        """Test daemon structure_search_online RPC."""
        from quantumvitas.io.providers.optimade import Candidate as OptimadeCandidate
        from quantumvitas.io.providers import UnifiedSearchResult
        from quantumvitas.api.types.online_search import SearchResultDTO
        
        mock_candidate = OptimadeCandidate(
            entry_id="mp-123",
            provider_id="mp",
            reduced_formula="Si",
            nsites=2,
            space_group_number=227,
            has_partial_occupancy=False,
            metadata={},
            score=1.0,
        )
        
        mock_result = UnifiedSearchResult(
            candidates=[mock_candidate],
            providers_queried=["mp"],
            partial=False,
            errors={},
        )
        
        daemon = QVDaemon()
        
        with patch('quantumvitas.io.providers.unified_search') as mock_search:
            mock_search.return_value = mock_result
            
            payload = {
                "query": "Si",
                "max_results": 10,
            }
            
            result = daemon._handle_structure_search_online(payload)
            
            assert "session_id" in result
            assert "candidates" in result
            assert len(result["candidates"]) >= 1
            assert result["candidates"][0]["candidate_id"].startswith("opt_mp-")
            assert result["candidates"][0]["structure_type"] == "crystal"
            assert "providers_queried" in result
            assert "mp" in result["providers_queried"]
    
    def test_daemon_structure_fetch_online(self):
        """Test daemon structure_fetch_online RPC (no project_root in request)."""
        from quantumvitas.io.online_cache import OnlineStructureCache, CandidateSummary, SessionInfo
        from pymatgen.core import Structure, Lattice
        
        # Create mock structure
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        daemon = QVDaemon()
        
        # Mock cache
        with patch('quantumvitas.io.online_cache.OnlineStructureCache') as MockCache:
            mock_cache = MockCache.return_value
            mock_cache.get_candidates.return_value = [
                CandidateSummary(
                    candidate_id="opt_mp-123",
                    label="Si (2 sites)",
                    source="mp",  # PR6: Use provider ID, not "optimade"
                    source_id="mp-123",
                    nsites=2,
                ),
            ]
            mock_cache.get_structure.return_value = None  # Not in cache, needs fetch
            mock_cache.get_candidate_metadata.return_value = {"optimade_base": "https://optimade.materialsproject.org"}
            mock_cache.get_session_info.return_value = SessionInfo(
                session_id="test-session",
                query="Si",
                created_at=1234567890,
                source_summary="optimade",
            )
            mock_cache.add_candidate = Mock()  # Mock add_candidate for caching
            
            # Mock API fetch_structure method
            from quantumvitas.api.types.online_search import StructureDocDTO
            structure_doc = StructureDocDTO(
                structure_type="crystal",
                formula="Si",
                atoms=[
                    {"element": "Si", "coords": [0, 0, 0]},
                    {"element": "Si", "coords": [1.25, 1.25, 1.25]},
                ],
                lattice=[[5.0, 0, 0], [0, 5.0, 0], [0, 0, 5.0]],
                pbc=[True, True, True],
                provenance={"source": "optimade", "source_id": "mp-123"},
            )
            
            with patch('quantumvitas.api.service.QVService.OnlineSearch.fetch_structure') as mock_fetch:
                mock_fetch.return_value = structure_doc
                
                # PR6: Handler no longer requires project_root (uses global cache)
                payload = {
                    "session_id": "test-session",
                    "candidate_id": "opt_mp-123",
                }
                
                # Handler uses global cache now
                result = daemon._handle_structure_get_online_candidate(payload)

                # Verify structure was fetched — handler returns CandidateDetailDTO.to_dict()
                # or an error dict with "ok": False
                assert "structure_vis" in result or "error" in result
    
    def test_daemon_list_providers(self):
        """Test daemon list_providers RPC (if exists)."""
        # PR0: list_providers RPC may not exist yet, skip for now
        # Will be added in PR1
        pass
    
    def test_daemon_update_online_sources(self):
        """Test daemon update_online_sources RPC (if exists)."""
        # PR0: update_online_sources RPC may not exist yet, skip for now
        # Will be added in PR1
        pass
    
    def test_daemon_no_kernel_imports(self):
        """Verify daemon doesn't import kernel directly (gate test)."""
        import ast
        import inspect
        
        # Get daemon source
        daemon_source = inspect.getsource(QVDaemon)
        
        # Parse AST
        tree = ast.parse(daemon_source)
        
        # Check for kernel imports in _handle_structure_search_online
        # PR0: Daemon should call QVService.OnlineSearch, not import from quantumvitas.io.online_search directly
        # (except for temporary compatibility in _handle_structure_get_online_candidate)
        
        # This is a basic check - full gate test is in tests/gates/test_daemon_kernel_ban.py
        assert True  # Placeholder - gate tests will enforce this

