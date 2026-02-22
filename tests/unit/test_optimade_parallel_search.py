"""
Unit tests for OPTIMADE parallel search.

PR2: Tests for parallel provider querying with timeouts.
"""

from unittest.mock import patch, Mock
import pytest

from qmatsuite.io.providers.optimade import (
    ProviderConfig,
    ProviderResult,
    Candidate,
    search_parallel,
    _query_single_provider,
)


class TestParallelSearch:
    """Test parallel OPTIMADE search."""
    
    def test_search_parallel_success(self):
        """Test successful parallel search across multiple providers."""
        providers = [
            ProviderConfig(provider_key="mp", name="MP", base_url="https://optimade.materialsproject.org", enabled=True, trust_weight=0.9),
            ProviderConfig(provider_key="cod", name="COD", base_url="https://www.crystallography.net/cod/optimade/v1", enabled=True, trust_weight=1.0),
        ]
        
        # Mock OPTIMADE responses
        mock_response_mp = Mock()
        mock_response_mp.json.return_value = {
            "data": [
                {
                    "id": "mp-123",
                    "attributes": {
                        "chemical_formula_reduced": "Si",
                        "nsites": 2,
                        "space_group_number": 227,
                    }
                }
            ]
        }
        mock_response_mp.raise_for_status = Mock()
        
        mock_response_cod = Mock()
        mock_response_cod.json.return_value = {
            "data": [
                {
                    "id": "cod-456",
                    "attributes": {
                        "chemical_formula_reduced": "Si",
                        "nsites": 2,
                        "space_group_number": 227,
                    }
                }
            ]
        }
        mock_response_cod.raise_for_status = Mock()
        
        with patch('qmatsuite.io.providers.optimade.requests.get') as mock_get:
            # Mock get to return different responses based on URL
            def side_effect(url, **kwargs):
                if "materialsproject" in url:
                    return mock_response_mp
                elif "crystallography" in url:
                    return mock_response_cod
                return Mock()
            
            mock_get.side_effect = side_effect
            
            results = search_parallel("Si", providers, max_per_provider=10, timeout_s=8.0)
            
            assert len(results) == 2
            assert any(r.provider_id == "mp" and len(r.candidates) > 0 for r in results)
            assert any(r.provider_id == "cod" and len(r.candidates) > 0 for r in results)
    
    def test_search_parallel_timeout(self):
        """Test that timeout is handled correctly."""
        providers = [
            ProviderConfig(provider_key="slow", name="Slow", base_url="https://slow.example.com", enabled=True, trust_weight=0.8),
        ]
        
        with patch('qmatsuite.io.providers.optimade.requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
            
            results = search_parallel("Si", providers, max_per_provider=10, timeout_s=0.1)
            
            assert len(results) == 1
            assert results[0].timed_out is True
            assert results[0].error is None
    
    def test_search_parallel_http_error(self):
        """Test that HTTP errors are handled correctly."""
        providers = [
            ProviderConfig(provider_key="error", name="Error", base_url="https://error.example.com", enabled=True, trust_weight=0.8),
        ]
        
        with patch('qmatsuite.io.providers.optimade.requests.get') as mock_get:
            import requests
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)
            
            results = search_parallel("Si", providers, max_per_provider=10, timeout_s=8.0)
            
            assert len(results) == 1
            assert results[0].error is not None
            assert "HTTP" in results[0].error
    
    def test_search_parallel_only_enabled(self):
        """Test that only enabled providers are queried."""
        providers = [
            ProviderConfig(provider_key="enabled", name="Enabled", base_url="https://enabled.example.com", enabled=True, trust_weight=0.8),
            ProviderConfig(provider_key="disabled", name="Disabled", base_url="https://disabled.example.com", enabled=False, trust_weight=0.8),
        ]
        
        with patch('qmatsuite.io.providers.optimade.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"data": []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            results = search_parallel("Si", providers, max_per_provider=10, timeout_s=8.0)
            
            # Only enabled provider should be queried
            assert len(results) == 1
            assert results[0].provider_id == "enabled"
    
    def test_query_single_provider_success(self):
        """Test successful single provider query."""
        provider = ProviderConfig(provider_key="test", name="Test", base_url="https://test.example.com", enabled=True, trust_weight=0.8)
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "test-123",
                    "attributes": {
                        "chemical_formula_reduced": "Si",
                        "nsites": 2,
                        "space_group_number": 227,
                    }
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('qmatsuite.io.providers.optimade.requests.get', return_value=mock_response):
            result = _query_single_provider(provider, "Si", max_results=10, timeout_s=8.0)
            
            assert result.provider_id == "test"
            assert len(result.candidates) == 1
            assert result.candidates[0].entry_id == "test-123"
            assert result.candidates[0].reduced_formula == "Si"
            assert result.candidates[0].nsites == 2
            assert result.candidates[0].space_group_number == 227

