"""
Unit tests for OPTIMADE provider registry.

PR1: Tests for registry fetching, caching, curated defaults, and fallback.
"""

import json
import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest

from quantumvitas.io.providers.optimade import (
    ProviderConfig,
    CURATED_DEFAULT_PROVIDERS,
    fetch_optimade_registry,
    get_providers_with_settings,
    OPTIMADE_REGISTRY_URL,
    REGISTRY_CACHE_TTL_SECONDS,
)


class TestProviderRegistry:
    """Test OPTIMADE provider registry fetching."""
    
    def test_curated_defaults(self):
        """Test that curated defaults are defined correctly."""
        assert len(CURATED_DEFAULT_PROVIDERS) == 6
        
        # Check all curated providers are enabled by default
        for provider in CURATED_DEFAULT_PROVIDERS:
            assert provider.enabled is True
            assert provider.source == "curated"
            assert provider.provider_key in ["mp", "cod", "alexandria", "oqmd", "jarvis", "mcloud"]
    
    def test_fetch_registry_success(self):
        """Test successful registry fetch."""
        # Mock registry response
        mock_response_data = {
            "data": [
                {
                    "id": "aflow",  # Provider ID at link level
                    "type": "links",
                    "attributes": {
                        "link_type": "child",
                        "base_url": "https://aflow.org/optimade/v1",
                        "name": "AFLOW",
                        "structures_count": 4000000,
                    }
                },
                {
                    "id": "nmd",  # Provider ID at link level
                    "type": "links",
                    "attributes": {
                        "link_type": "child",
                        "base_url": "https://nomad-lab.eu/optimade/v1",
                        "name": "NOMAD",
                        "structures_count": 13000000,
                    }
                },
            ]
        }
        
        with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            # Mock cache to return None (cache miss)
            with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
                with patch('quantumvitas.io.providers.optimade._save_registry_cache') as mock_save:
                    providers = fetch_optimade_registry(refresh=False)
                    
                    # Should include curated defaults + registry providers
                    provider_ids = [p.provider_key for p in providers]
                    assert "mp" in provider_ids  # Curated
                    assert "aflow" in provider_ids  # Registry
                    assert "nmd" in provider_ids  # Registry

                    # Registry providers should be disabled by default
                    aflow_provider = next(p for p in providers if p.provider_key == "aflow")
                    assert aflow_provider.enabled is False
                    assert aflow_provider.source == "registry"
                    
                    # Cache should be saved
                    assert mock_save.called
    
    def test_fetch_registry_fallback_on_error(self):
        """Test fallback to curated defaults when registry fetch fails."""
        with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            # Mock cache to return None
            with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
                providers = fetch_optimade_registry(refresh=False)
                
                # Should return only curated defaults
                assert len(providers) == len(CURATED_DEFAULT_PROVIDERS)
                assert all(p.source == "curated" for p in providers)
    
    def test_fetch_registry_cache_hit(self):
        """Test that cached registry is used when valid."""
        # Mock cache with valid data
        cached_data = {
            "cached_at": time.time() - 100,  # 100 seconds ago (within TTL)
            "providers": [
                {
                    "provider_key": "aflow",
                    "name": "AFLOW",
                    "base_url": "https://aflow.org/optimade/v1",
                    "enabled": False,
                    "structure_count": 4000000,
                    "trust_weight": 0.7,
                    "source": "registry",
                }
            ]
        }

        with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=cached_data):
            with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
                providers = fetch_optimade_registry(refresh=False)

                # Should use cached data (no network call)
                assert not mock_get.called

                # Should include cached registry provider
                provider_ids = [p.provider_key for p in providers]
                assert "aflow" in provider_ids
    
    def test_fetch_registry_cache_expired(self):
        """Test that expired cache triggers fresh fetch."""
        # Mock cache to return None (expired cache - TTL check happens inside _load_registry_cache)
        mock_response_data = {"data": []}
        
        with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
            with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = mock_response_data
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                with patch('quantumvitas.io.providers.optimade._save_registry_cache'):
                    providers = fetch_optimade_registry(refresh=False)
                    
                    # Should fetch fresh (network call made) because cache returned None
                    assert mock_get.called, "Expected network call when cache is expired (returns None)"
    
    def test_fetch_registry_refresh_force(self):
        """Test that refresh=True forces fresh fetch even with valid cache."""
        cached_data = {
            "cached_at": time.time() - 100,  # Valid cache
            "providers": []
        }
        
        mock_response_data = {"data": []}
        
        with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=cached_data):
            with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
                mock_response = Mock()
                mock_response.json.return_value = mock_response_data
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response
                
                with patch('quantumvitas.io.providers.optimade._save_registry_cache'):
                    providers = fetch_optimade_registry(refresh=True)
                    
                    # Should fetch fresh (network call made despite valid cache)
                    assert mock_get.called
    
    def test_get_providers_with_settings(self):
        """Test merging providers with user settings."""
        user_settings = {
            "optimade_providers": [
                {"provider_key": "mp", "enabled": True},  # Curated, keep enabled
                {"provider_key": "aflow", "enabled": True},  # Registry, user enabled
            ]
        }
        
        # Mock registry to return aflow
        mock_response_data = {
            "data": [
                {
                    "id": "aflow",
                    "type": "links",
                    "attributes": {
                        "link_type": "child",
                        "base_url": "https://aflow.org/optimade/v1",
                        "name": "AFLOW",
                    }
                },
            ]
        }
        
        with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
                with patch('quantumvitas.io.providers.optimade._save_registry_cache'):
                    providers = get_providers_with_settings(user_settings, refresh_registry=False)

                    # Check settings applied
                    mp_provider = next(p for p in providers if p.provider_key == "mp")
                    assert mp_provider.enabled is True

                    aflow_provider = next(p for p in providers if p.provider_key == "aflow")
                    assert aflow_provider.enabled is True  # User enabled it
    
    def test_registry_provider_defaults_disabled(self):
        """Test that registry-discovered providers default to enabled=False (R6)."""
        mock_response_data = {
            "data": [
                {
                    "id": "newprovider",  # Provider ID at link level
                    "type": "links",
                    "attributes": {
                        "link_type": "child",
                        "base_url": "https://newprovider.org/optimade/v1",
                        "name": "New Provider",
                    }
                },
            ]
        }
        
        with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
                with patch('quantumvitas.io.providers.optimade._save_registry_cache'):
                    providers = fetch_optimade_registry(refresh=False)
                    
                    newprovider = next((p for p in providers if p.provider_key == "newprovider"), None)
                    assert newprovider is not None
                    assert newprovider.enabled is False  # Registry providers disabled by default
                    assert newprovider.source == "registry"
    
    def test_curated_providers_enabled_by_default(self):
        """Test that curated providers are enabled by default (R6)."""
        # Fetch with no user settings
        with patch('quantumvitas.io.providers.optimade.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")  # Force fallback
            
            with patch('quantumvitas.io.providers.optimade._load_registry_cache', return_value=None):
                providers = fetch_optimade_registry(refresh=False)
                
                # All curated providers should be enabled
                curated_providers = [p for p in providers if p.source == "curated"]
                assert len(curated_providers) == len(CURATED_DEFAULT_PROVIDERS)
                assert all(p.enabled is True for p in curated_providers)
    
    def test_parse_registry_response(self):
        """Test parsing of registry response format."""
        from quantumvitas.io.providers.optimade import _parse_registry_response
        
        response_data = {
            "data": [
                {
                    "id": "test",  # Provider ID at link level
                    "type": "links",
                    "attributes": {
                        "link_type": "child",
                        "base_url": "https://test.org/optimade/v1",
                        "name": "Test Provider",
                        "structures_count": "1000",  # String format
                    }
                },
                {
                    "id": "index",
                    "type": "links",
                    "attributes": {
                        "link_type": "index",  # Should be skipped
                        "base_url": "https://index.org/optimade/v1",
                    }
                },
            ]
        }
        
        providers = _parse_registry_response(response_data)
        
        assert len(providers) == 1
        assert providers[0].provider_key == "test"
        assert providers[0].name == "Test Provider"
        assert providers[0].base_url == "https://test.org/optimade/v1"
        assert providers[0].enabled is False  # Registry providers disabled by default
        assert providers[0].structure_count == 1000  # Parsed from string
    
    def test_cache_ttl_mocking(self):
        """Test cache TTL behavior with mocked time (R5: non-flaky)."""
        from quantumvitas.io.providers.optimade import _load_registry_cache, _save_registry_cache
        
        # Save cache with fixed timestamp
        fixed_time = 1000000.0
        with patch('time.time', return_value=fixed_time):
            cache_data = {
                "cached_at": fixed_time,
                "providers": [{"provider_key": "test", "name": "Test", "base_url": "https://test.org", "enabled": False, "source": "registry"}]
            }
            _save_registry_cache(cache_data["providers"])
        
        # Load cache immediately (should be valid)
        with patch('time.time', return_value=fixed_time + 100):  # 100 seconds later
            cached = _load_registry_cache()
            assert cached is not None
        
        # Load cache after TTL expires (should be None)
        with patch('time.time', return_value=fixed_time + REGISTRY_CACHE_TTL_SECONDS + 1):
            cached = _load_registry_cache()
            assert cached is None

