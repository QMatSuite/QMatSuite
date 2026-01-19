"""
Materialization policy for analysis objects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MaterializationPolicy(Enum):
    """Policy for analysis cache."""
    ENABLED = "enabled"    # Default: cache to .analysis/
    DISABLED = "disabled"  # Never cache
    
    @classmethod
    def from_settings(cls) -> "MaterializationPolicy":
        """
        Get policy from user settings.
        
        Reads from QMatSuiteSettings.analysis_cache_enabled.
        """
        try:
            from quantumvitas.core.settings import load_settings
            settings = load_settings()
            if not settings.analysis_cache_enabled:
                return cls.DISABLED
        except Exception:
            # If settings can't be loaded, default to enabled
            pass
        return cls.ENABLED


@dataclass
class CacheConfig:
    """Configuration for analysis caching."""
    policy: MaterializationPolicy = MaterializationPolicy.ENABLED
    format: str = "json"  # "json" or "hdf5"
    
    @classmethod
    def default(cls) -> "CacheConfig":
        return cls(policy=MaterializationPolicy.from_settings())

