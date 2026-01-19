"""
Trajectory I/O: serialization to/from cache.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from quantumvitas.core.analysis.cache import CacheManager, get_cache_path
from quantumvitas.core.analysis.trajectory.model import Trajectory


def save_trajectory(
    trajectory: Trajectory,
    calc_dir: Path,
    cache_manager: Optional[CacheManager] = None,
) -> Optional[Path]:
    """
    Save trajectory to cache.
    
    Returns:
        Path to cache file, or None if caching disabled
    """
    if cache_manager is None:
        cache_manager = CacheManager(calc_dir)
    
    if not cache_manager.cache_enabled():
        return None
    
    return cache_manager.save_cache("trajectory", trajectory.to_dict())


def load_trajectory(
    calc_dir: Path,
    cache_manager: Optional[CacheManager] = None,
) -> Optional[Trajectory]:
    """
    Load trajectory from cache if exists and not stale.
    
    Returns:
        Trajectory or None if not cached/stale
    """
    if cache_manager is None:
        cache_manager = CacheManager(calc_dir)
    
    data = cache_manager.get_cached("trajectory")
    if data is None:
        return None
    
    return Trajectory.from_dict(data)

