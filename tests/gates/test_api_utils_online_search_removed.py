"""
Gate test: Verify online search functions removed from api.utils.

PR0: Enforce Law H3 - online search is domain capability, not utility.
"""

import pytest
import importlib
import inspect


class TestAPIUtilsOnlineSearchRemoved:
    """Test that online search functions are not re-exported from api.utils."""
    
    def test_utils_no_online_search_reexports(self):
        """Verify no search_online_structures in api.utils."""
        from quantumvitas import api
        
        # Check that search_online_structures is not in api.utils
        utils_module = api.utils
        
        # Check __all__ if it exists
        if hasattr(utils_module, '__all__'):
            assert 'search_online_structures' not in utils_module.__all__
        
        # Check that it's not directly accessible
        assert not hasattr(utils_module, 'search_online_structures'), \
            "search_online_structures should not be in api.utils (Law H3)"
    
    def test_utils_no_fetch_structure_reexports(self):
        """Verify no fetch_structure_from_optimade in api.utils."""
        from quantumvitas import api
        
        utils_module = api.utils
        
        # Check __all__ if it exists
        if hasattr(utils_module, '__all__'):
            assert 'fetch_structure_from_optimade' not in utils_module.__all__
        
        # Check that it's not directly accessible
        assert not hasattr(utils_module, 'fetch_structure_from_optimade'), \
            "fetch_structure_from_optimade should not be in api.utils (Law H3)"
    
    def test_online_search_via_service_only(self):
        """Verify online search is only accessible via QVService.OnlineSearch."""
        from quantumvitas.api import QVService
        
        # Verify OnlineSearch class exists
        assert hasattr(QVService, 'OnlineSearch'), \
            "QVService.OnlineSearch should exist"
        
        # Verify methods exist
        assert hasattr(QVService.OnlineSearch, 'search_structures'), \
            "QVService.OnlineSearch.search_structures should exist"
        assert hasattr(QVService.OnlineSearch, 'fetch_structure'), \
            "QVService.OnlineSearch.fetch_structure should exist"
        assert hasattr(QVService.OnlineSearch, 'list_providers'), \
            "QVService.OnlineSearch.list_providers should exist"
        assert hasattr(QVService.OnlineSearch, 'update_online_sources'), \
            "QVService.OnlineSearch.update_online_sources should exist"

