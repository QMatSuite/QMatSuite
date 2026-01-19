"""
Cache management for analysis objects.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat
from quantumvitas.core.analysis.policy import CacheConfig, MaterializationPolicy

logger = logging.getLogger(__name__)

# Cache directory name (hidden)
ANALYSIS_CACHE_DIR = ".analysis"


def get_cache_dir(calc_dir: Path) -> Path:
    """Get the analysis cache directory for a calculation."""
    return calc_dir / ANALYSIS_CACHE_DIR


def get_cache_path(calc_dir: Path, object_type: str) -> Path:
    """
    Get cache file path for an object type.
    
    Convention: .analysis/<object_type>.json
    """
    return get_cache_dir(calc_dir) / f"{object_type}.json"


def is_cache_stale(
    meta: AnalysisObjectMeta,
    calc_dir: Path,
) -> Tuple[bool, str]:
    """
    Check if cached analysis object is stale.
    
    Hard stale criterion: source file stat mismatch.
    Provenance is NOT used for staleness (UI explanation only).
    
    Returns:
        (is_stale, reason)
    """
    for source in meta.source_files:
        source_path = calc_dir / source.path
        
        # File missing → stale
        if not source_path.exists():
            return (True, f"Source file missing: {source.path}")
        
        stat = source_path.stat()
        
        # Size mismatch → stale
        if stat.st_size != source.size_bytes:
            return (True, f"Size changed: {source.path} ({source.size_bytes} → {stat.st_size})")
        
        # Mtime mismatch → stale (with tolerance for float comparison)
        if abs(stat.st_mtime - source.mtime) > 0.01:
            return (True, f"Modified: {source.path}")
    
    return (False, "")


class CacheManager:
    """
    Manages analysis object caching.
    """
    
    def __init__(self, calc_dir: Path, config: Optional[CacheConfig] = None):
        self.calc_dir = calc_dir
        self.config = config or CacheConfig.default()
    
    def cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.policy == MaterializationPolicy.ENABLED
    
    def get_cached(self, object_type: str) -> Optional[Dict[str, Any]]:
        """
        Load cached object if exists and not stale.
        
        Returns:
            Object dict if cache hit, None if miss or stale
        """
        if not self.cache_enabled():
            return None
        
        cache_path = get_cache_path(self.calc_dir, object_type)
        if not cache_path.exists():
            logger.debug(f"Cache miss: {cache_path} does not exist")
            return None
        
        try:
            data = json.loads(cache_path.read_text())
            meta = AnalysisObjectMeta.from_dict(data.get("meta", {}))
            
            is_stale, reason = is_cache_stale(meta, self.calc_dir)
            if is_stale:
                logger.debug(f"Cache stale: {reason}")
                return None
            
            logger.debug(f"Cache hit: {cache_path}")
            return data
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_path}: {e}")
            return None
    
    def save_cache(self, object_type: str, data: Dict[str, Any]) -> Path:
        """
        Save object to cache.
        
        Returns:
            Path to cache file
        """
        if not self.cache_enabled():
            raise RuntimeError("Cannot save cache when caching is disabled")
        
        cache_dir = get_cache_dir(self.calc_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_path = get_cache_path(self.calc_dir, object_type)
        cache_path.write_text(json.dumps(data, indent=2, default=str))
        
        logger.debug(f"Saved cache: {cache_path}")
        return cache_path
    
    def invalidate(self, object_type: str) -> bool:
        """
        Invalidate (delete) cache for an object type.
        
        Returns:
            True if cache was deleted, False if it didn't exist
        """
        cache_path = get_cache_path(self.calc_dir, object_type)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Invalidated cache: {cache_path}")
            return True
        return False
    
    def invalidate_all(self) -> int:
        """
        Invalidate all cached objects.
        
        Returns:
            Number of caches deleted
        """
        cache_dir = get_cache_dir(self.calc_dir)
        if not cache_dir.exists():
            return 0
        
        count = 0
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        
        logger.debug(f"Invalidated {count} caches")
        return count

