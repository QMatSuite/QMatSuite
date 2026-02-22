"""
Online structure providers.

This module provides a unified interface for online structure search providers
(OPTIMADE, PubChem, Materials Project native).

PR1: Provider registry and unified search interface.
PR6: Unified search orchestration.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from qmatsuite.core.settings import load_settings

logger = logging.getLogger(__name__)

# Import provider modules
from qmatsuite.io.providers.optimade import (
    ProviderConfig,
    Candidate as OptimadeCandidate,
    ProviderResult,
    search_parallel as search_optimade_parallel,
    deduplicate_candidates,
    rank_candidates,
    get_providers_with_settings,
    fetch_optimade_registry,
)
from qmatsuite.io.providers.pubchem import (
    PubChemCandidate,
    search_pubchem,
)
from qmatsuite.io.providers.materials_project import (
    search_materials_project,
    MP_API_AVAILABLE,
)

__all__ = [
    "UnifiedSearchResult",
    "unified_search",
]


@dataclass
class UnifiedSearchResult:
    """Result from unified search across all providers."""
    candidates: List[Any]  # Mixed: OptimadeCandidate, PubChemCandidate, or MP Candidate
    providers_queried: List[str]  # Provider IDs that were queried
    partial: bool  # True if some providers timed out or errored
    errors: Dict[str, str] = field(default_factory=dict)  # Provider ID -> error message


def unified_search(
    query: str,
    *,
    mode: Literal["crystal", "molecule", "auto"] = "auto",
    max_results: int = 50,
    timeout_s: float = 8.0,
    refresh_registry: bool = False,
    user_settings: Optional[Dict[str, Any]] = None,
) -> UnifiedSearchResult:
    """
    Unified search across all providers (OPTIMADE, PubChem, MP native).
    
    Args:
        query: Chemical formula or molecule name
        mode: Search mode - "crystal" (OPTIMADE/MP only), "molecule" (PubChem only), "auto" (both)
        max_results: Maximum total results after aggregation
        timeout_s: Per-provider timeout
        refresh_registry: If True, force refresh OPTIMADE registry
        user_settings: User settings dict (if None, loads from global settings)
        
    Returns:
        UnifiedSearchResult with candidates from all providers
    """
    # Load settings if not provided
    if user_settings is None:
        settings = load_settings()
        user_settings = {
            "optimade_providers": settings.online_structures.optimade_providers,
            "pubchem_enabled": settings.online_structures.pubchem_enabled,
            "materials_project": {
                "enabled": settings.online_structures.materials_project.enabled,
                "api_key": settings.online_structures.materials_project.api_key,
            },
            "timeout_seconds": settings.online_structures.timeout_seconds,
            "max_results_per_provider": settings.online_structures.max_results_per_provider,
            "max_total_results": settings.online_structures.max_total_results,
        }
    
    # Override with provided settings
    timeout_s = user_settings.get("timeout_seconds", timeout_s)
    max_per_provider = user_settings.get("max_results_per_provider", 10)
    max_total_results = user_settings.get("max_total_results", max_results)
    
    all_candidates: List[Any] = []
    providers_queried: List[str] = []
    errors: Dict[str, str] = {}
    partial = False
    
    # Determine which providers to query based on mode
    search_crystals = mode in ("crystal", "auto")
    search_molecules = mode in ("molecule", "auto")
    
    # 1. OPTIMADE federation (crystals)
    if search_crystals:
        try:
            optimade_providers = get_providers_with_settings(
                user_settings,
                refresh_registry=refresh_registry,
            )
            
            # Query OPTIMADE providers in parallel
            optimade_results = search_optimade_parallel(
                query,
                optimade_providers,
                max_per_provider=max_per_provider,
                timeout_s=timeout_s,
            )
            
            # Check for timeouts/errors
            for result in optimade_results:
                providers_queried.append(result.provider_id)
                if result.timed_out:
                    partial = True
                    errors[result.provider_id] = "Timeout"
                elif result.error:
                    partial = True
                    errors[result.provider_id] = result.error
                else:
                    all_candidates.extend(result.candidates)
        except Exception as e:
            logger.error(f"OPTIMADE search failed: {e}")
            partial = True
            errors["optimade"] = str(e)
    
    # 2. PubChem (molecules)
    if search_molecules and user_settings.get("pubchem_enabled", True):
        try:
            providers_queried.append("pubchem")
            pubchem_candidates = search_pubchem(query, max_results=max_per_provider)
            all_candidates.extend(pubchem_candidates)
        except Exception as e:
            logger.error(f"PubChem search failed: {e}")
            partial = True
            errors["pubchem"] = str(e)
    
    # 3. Materials Project native (crystals, optional)
    mp_config = user_settings.get("materials_project", {})
    if search_crystals and mp_config.get("enabled", False) and mp_config.get("api_key"):
        if MP_API_AVAILABLE:
            try:
                providers_queried.append("mp-native")
                mp_candidates = search_materials_project(
                    query,
                    api_key=mp_config["api_key"],
                    max_results=max_per_provider,
                )
                all_candidates.extend(mp_candidates)
            except Exception as e:
                logger.error(f"MP native search failed: {e}")
                partial = True
                errors["mp-native"] = str(e)
        else:
            logger.warning("MP native API requested but mp-api package not available")
            partial = True
            errors["mp-native"] = "mp-api package not available"
    
    # Separate crystal candidates (OPTIMADE + MP native) from molecules (PubChem)
    crystal_candidates: List[OptimadeCandidate] = []
    molecule_candidates: List[PubChemCandidate] = []
    
    for candidate in all_candidates:
        if isinstance(candidate, OptimadeCandidate):
            crystal_candidates.append(candidate)
        elif isinstance(candidate, PubChemCandidate):
            molecule_candidates.append(candidate)
        # MP native returns Candidate (same as OptimadeCandidate)
        elif hasattr(candidate, "provider_id") and candidate.provider_id == "mp-native":
            crystal_candidates.append(candidate)
    
    # Deduplicate and rank crystal candidates (OPTIMADE + MP native)
    if crystal_candidates:
        # Group by provider for deduplication
        provider_results: List[ProviderResult] = []
        provider_map: Dict[str, List[OptimadeCandidate]] = {}
        
        for candidate in crystal_candidates:
            if candidate.provider_id not in provider_map:
                provider_map[candidate.provider_id] = []
            provider_map[candidate.provider_id].append(candidate)
        
        # Convert to ProviderResult list
        for provider_id, candidates_list in provider_map.items():
            provider_results.append(ProviderResult(
                provider_id=provider_id,
                provider_name=provider_id,
                candidates=candidates_list,
            ))
        
        # Deduplicate and rank
        if provider_results:
            aggregated = deduplicate_candidates(provider_results)
            optimade_providers = get_providers_with_settings(user_settings, refresh_registry=False)
            ranked = rank_candidates(aggregated, query, optimade_providers)
            
            # Convert back to flat list
            crystal_candidates = [agg.primary_candidate for agg in ranked]
    
    # Combine and limit
    final_candidates: List[Any] = crystal_candidates + molecule_candidates
    final_candidates = final_candidates[:max_total_results]
    
    return UnifiedSearchResult(
        candidates=final_candidates,
        providers_queried=providers_queried,
        partial=partial,
        errors=errors,
    )
