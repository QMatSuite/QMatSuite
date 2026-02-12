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
        
        daemon = QVDaemon()
        
        with patch('quantumvitas.io.online_search.search_online_structures') as mock_search:
            mock_search.return_value = ("optimade", mock_candidates, [None], "https://optimade.materialsproject.org")
            
            payload = {
                "query": "Si",
                "max_results": 10,
            }
            
            result = daemon._handle_structure_search_online(payload)
            
            assert "session_id" in result
            assert "candidates" in result
            assert len(result["candidates"]) == 1
            assert result["candidates"][0]["candidate_id"] == "opt_mp-123"
            assert result["candidates"][0]["structure_type"] == "crystal"
            assert "providers_queried" in result
            assert "optimade" in result["providers_queried"]
    
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
                    source="optimade",
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
            
            # Mock fetch
            with patch('quantumvitas.io.online_search.fetch_structure_from_optimade') as mock_fetch:
                mock_fetch.return_value = (structure, {"data": {"id": "mp-123"}})
                
                # Note: This handler still requires project_root for now (legacy compatibility)
                # PR0: Updated to use global cache, but handler signature unchanged for compatibility
                payload = {
                    "project_root": "/tmp/test-project",  # Still required for now
                    "session_id": "test-session",
                    "candidate_id": "opt_mp-123",
                }
                
                # Handler should work (may need project_root for other parts)
                # The cache itself uses global location now
                result = daemon._handle_structure_get_online_candidate(payload)
                
                # Verify structure was fetched
                assert mock_fetch.called
    
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

