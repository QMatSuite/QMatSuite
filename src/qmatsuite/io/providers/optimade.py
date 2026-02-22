"""
OPTIMADE provider registry and search.

PR1: Provider registry fetching with curated defaults and caching.
PR2: Parallel search, deduplication, and ranking.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from qmatsuite.core.paths import get_qmatsuite_home_root

logger = logging.getLogger(__name__)

# Registry URL
OPTIMADE_REGISTRY_URL = "https://providers.optimade.org/v1/links"

# Registry cache TTL: 24 hours
REGISTRY_CACHE_TTL_SECONDS = 24 * 60 * 60


@dataclass
class ProviderConfig:
    """OPTIMADE provider configuration (local model, not API DTO)."""
    provider_key: str  # e.g., "mp", "cod", "alexandria"
    name: str  # Display name
    base_url: str  # OPTIMADE base URL
    enabled: bool  # From user settings:
                   # - Curated defaults: enabled=True by default (unless user disabled)
                   # - Registry providers: enabled=False by default (user must opt-in)
    structure_count: Optional[int] = None  # From registry metadata
    trust_weight: float = 1.0  # For ranking (experimental > computed > ML)
    source: Literal["curated", "registry"] = "curated"  # Track if provider is from curated list or registry


# Curated default providers (R6: Enabled by default)
CURATED_DEFAULT_PROVIDERS = [
    ProviderConfig(
        provider_key="mp",
        name="Materials Project",
        base_url="https://optimade.materialsproject.org",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.9,  # Computed, high quality
        source="curated",
    ),
    ProviderConfig(
        provider_key="cod",
        name="COD (Crystallography Open Database)",
        base_url="https://www.crystallography.net/cod/optimade/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=1.0,  # Experimental, highest priority
        source="curated",
    ),
    ProviderConfig(
        provider_key="alexandria",
        name="Alexandria",
        base_url="https://alexandria.icams.rub.de/pbe",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed, large database
        source="curated",
    ),
    ProviderConfig(
        provider_key="oqmd",
        name="OQMD",
        base_url="http://oqmd.org/optimade/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed
        source="curated",
    ),
    ProviderConfig(
        provider_key="jarvis",
        name="JARVIS",
        base_url="https://jarvis.nist.gov/optimade/jarvisdft/v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.85,  # NIST quality
        source="curated",
    ),
    ProviderConfig(
        provider_key="mcloud",
        name="Materials Cloud",
        base_url="https://optimade.materialscloud.org/main/mc3d-pbe-v1",
        enabled=True,  # Enabled by default (curated allowlist)
        trust_weight=0.8,  # Computed
        source="curated",
    ),
]


def _get_registry_cache_path() -> Path:
    """Get registry cache file path (global cache location)."""
    cache_dir = get_qmatsuite_home_root() / "cache" / "online_structures"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "registry_cache.json"


def _load_registry_cache() -> Optional[Dict[str, Any]]:
    """Load registry from cache if valid (TTL check)."""
    cache_path = _get_registry_cache_path()
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)
        
        # Check TTL
        cached_time = cache_data.get("cached_at", 0)
        current_time = time.time()
        if current_time - cached_time > REGISTRY_CACHE_TTL_SECONDS:
            logger.debug("Registry cache expired")
            return None
        
        return cache_data
    except Exception as e:
        logger.warning(f"Failed to load registry cache: {e}")
        return None


def _save_registry_cache(providers: List[Dict[str, Any]]) -> None:
    """Save registry to cache with timestamp."""
    cache_path = _get_registry_cache_path()
    try:
        cache_data = {
            "cached_at": time.time(),
            "providers": providers,
        }
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save registry cache: {e}")


def _parse_registry_response(response_data: Dict[str, Any]) -> List[ProviderConfig]:
    """
    Parse OPTIMADE registry response.
    
    Registry format: JSON API with "data" array of link objects.
    Each link has "attributes" with provider metadata.
    """
    providers = []
    
    try:
        data = response_data.get("data", [])
        for link in data:
            attrs = link.get("attributes", {})
            link_type = attrs.get("link_type", "")
            
            # Only process "child" links (actual providers, not index meta-dbs)
            if link_type != "child":
                continue
            
            # Extract provider info
            base_url = attrs.get("base_url", "")
            if not base_url:
                continue
            
            # Extract provider ID: first try link.id, then attrs.id, then derive from URL
            provider_id = link.get("id", "") or attrs.get("id", "")
            if not provider_id:
                # Try to extract from base URL
                # e.g., "https://optimade.materialsproject.org" -> "mp"
                # e.g., "https://aflow.org/optimade/v1" -> "aflow"
                url_parts = base_url.rstrip('/').split('/')
                # Look for known provider patterns in URL (skip common path segments)
                for part in reversed(url_parts):
                    if part and part not in ['v1', 'optimade', 'v0', 'v2', 'v1.0', '']:
                        # Skip domain parts (contain dots)
                        if '.' not in part:
                            provider_id = part
                            break
                if not provider_id:
                    provider_id = "unknown"
            
            # Extract name
            name = attrs.get("name", provider_id)
            
            # Extract structure count if available
            structure_count = attrs.get("structures_count")
            if structure_count is not None:
                try:
                    structure_count = int(structure_count)
                except (ValueError, TypeError):
                    structure_count = None
            
            # Registry providers default to enabled=False (R6)
            provider = ProviderConfig(
                provider_key=provider_id.lower(),  # Normalize to lowercase
                name=name,
                base_url=base_url.rstrip('/'),
                enabled=False,  # User must opt-in
                structure_count=structure_count,
                trust_weight=0.7,  # Default trust weight for registry providers
                source="registry",
            )
            providers.append(provider)
    except Exception as e:
        logger.warning(f"Failed to parse registry response: {e}")
    
    return providers


def fetch_optimade_registry(
    *,
    refresh: bool = False,
) -> List[ProviderConfig]:
    """
    Fetch OPTIMADE provider registry.
    
    Returns curated default list if registry unavailable.
    Registry-discovered providers default to enabled=False (user must opt-in).
    
    Args:
        refresh: If True, force refresh registry (ignore cache)
        
    Returns:
        List of ProviderConfig (curated + registry providers)
    """
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available, using curated defaults only")
        return CURATED_DEFAULT_PROVIDERS.copy()
    
    # Check cache first (unless refresh=True)
    if not refresh:
        cached_data = _load_registry_cache()
        if cached_data:
            try:
                # Support both "id" and "provider_key" for backward compatibility
                providers_list = []
                for p in cached_data.get("providers", []):
                    # Migrate "id" to "provider_key" if present
                    if "id" in p and "provider_key" not in p:
                        p = p.copy()
                        p["provider_key"] = p.pop("id")
                    providers_list.append(ProviderConfig(**p))
                registry_providers = providers_list
                # Merge with curated defaults
                return _merge_providers(registry_providers)
            except Exception as e:
                logger.warning(f"Failed to load cached providers: {e}, fetching fresh")
                # Fall through to fetch fresh
    
    # Fetch from registry
    try:
        response = requests.get(OPTIMADE_REGISTRY_URL, timeout=10)
        response.raise_for_status()
        response_data = response.json()
        
        # Parse registry response
        registry_providers = _parse_registry_response(response_data)
        
        # Save to cache
        providers_dict = [
            {
                "provider_key": p.provider_key,
                "name": p.name,
                "base_url": p.base_url,
                "enabled": p.enabled,
                "structure_count": p.structure_count,
                "trust_weight": p.trust_weight,
                "source": p.source,
            }
            for p in registry_providers
        ]
        _save_registry_cache(providers_dict)
        
        # Merge with curated defaults
        return _merge_providers(registry_providers)
        
    except Exception as e:
        logger.warning(f"Failed to fetch OPTIMADE registry: {e}, using curated defaults")
        # Fallback to curated defaults
        return CURATED_DEFAULT_PROVIDERS.copy()


def _merge_providers(registry_providers: List[ProviderConfig]) -> List[ProviderConfig]:
    """
    Merge registry providers with curated defaults.
    
    Strategy:
    - Curated providers: Keep enabled=True (unless user disabled in settings)
    - Registry providers: Keep enabled=False (user must opt-in)
    - If a provider appears in both, prefer curated version (higher trust)
    """
    # Build map of curated providers by provider_key
    curated_map = {p.provider_key: p for p in CURATED_DEFAULT_PROVIDERS}

    # Start with curated defaults
    merged = CURATED_DEFAULT_PROVIDERS.copy()

    # Add registry providers that aren't in curated list
    for reg_provider in registry_providers:
        if reg_provider.provider_key not in curated_map:
            merged.append(reg_provider)
    
    return merged


def get_providers_with_settings(
    user_settings: Optional[Dict[str, Any]] = None,
    *,
    refresh_registry: bool = False,
) -> List[ProviderConfig]:
    """
    Get provider list merged with user settings.
    
    Args:
        user_settings: User settings dict (from QMatSuiteSettings.online_structures)
        refresh_registry: If True, force refresh registry
        
    Returns:
        List of ProviderConfig with enabled flags from user settings
    """
    # Fetch registry (or use cached)
    all_providers = fetch_optimade_registry(refresh=refresh_registry)
    
    # Apply user settings if provided
    if user_settings:
        optimade_providers_settings = user_settings.get("optimade_providers", [])
        settings_map = {p.get("provider_key", p.get("id", "")): p for p in optimade_providers_settings}  # Migrate legacy "id" key
        
        # Update enabled flags from settings
        for provider in all_providers:
            if provider.provider_key in settings_map:
                provider.enabled = settings_map[provider.provider_key].get("enabled", provider.enabled)
    
    return all_providers


# =============================================================================
# PR2: Parallel Search, Deduplication, and Ranking
# =============================================================================

@dataclass
class Candidate:
    """Candidate structure from OPTIMADE provider (internal model)."""
    entry_id: str  # OPTIMADE entry ID (e.g., "mp-123")
    provider_id: str  # Provider ID (e.g., "mp", "cod")
    reduced_formula: str  # Reduced chemical formula
    nsites: int  # Number of sites
    space_group_number: Optional[int] = None  # Space group number (if available)
    has_partial_occupancy: bool = False  # Whether structure has partial occupancy
    metadata: Dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata
    score: float = 0.0  # Computed score (for ranking)


@dataclass
class ProviderResult:
    """Result from a single OPTIMADE provider query."""
    provider_id: str
    provider_name: str
    candidates: List[Candidate] = field(default_factory=list)
    timed_out: bool = False
    error: Optional[str] = None


@dataclass
class AggregatedCandidate:
    """Deduplicated candidate with aggregated provider info."""
    primary_candidate: Candidate
    providers: List[str]  # All provider IDs that had this structure
    aggregated_metadata: Dict[str, Any] = field(default_factory=dict)


def _query_single_provider(
    provider: ProviderConfig,
    query: str,
    max_results: int,
    timeout_s: float,
) -> ProviderResult:
    """
    Query a single OPTIMADE provider.
    
    Args:
        provider: Provider configuration
        query: Chemical formula query
        max_results: Maximum results per provider
        timeout_s: Timeout in seconds
        
    Returns:
        ProviderResult with candidates or error/timeout info
    """
    if not REQUESTS_AVAILABLE:
        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            error="requests library not available",
        )
    
    # Normalize and reduce formula
    try:
        from qmatsuite.io.online_search import normalize_formula, reduce_formula
        normalized = normalize_formula(query)
        reduced = reduce_formula(normalized)
    except Exception as e:
        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            error=f"Formula normalization failed: {e}",
        )
    
    # Normalize base_url: avoid double /v1 if base already ends with it
    base = provider.base_url.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/structures"
    else:
        url = f"{base}/v1/structures"

    # Build OPTIMADE filter — try chemical_formula_reduced first, fall back to elements HAS
    filters_to_try = [f'chemical_formula_reduced="{reduced}"']

    # Build elements fallback filter (e.g., 'elements HAS "Si"' or 'elements HAS ALL "Na","Cl"')
    try:
        from pymatgen.core import Composition
        comp = Composition(reduced)
        elements = sorted(str(el) for el in comp.elements)
        if len(elements) == 1:
            filters_to_try.append(f'elements HAS "{elements[0]}"')
        else:
            quoted = ",".join(f'"{el}"' for el in elements)
            filters_to_try.append(f'elements HAS ALL {quoted}')
    except Exception:
        pass  # Keep only the first filter

    page_limit = min(max_results, 100)

    try:
        data = None
        for filter_value in filters_to_try:
            params = {"filter": filter_value, "page_limit": page_limit}
            response = requests.get(url, params=params, timeout=timeout_s)
            if response.status_code in (501, 400):
                # Filter not supported by this provider — try next
                logger.debug(
                    f"Provider {provider.provider_key} returned {response.status_code} "
                    f"for filter '{filter_value}', trying fallback"
                )
                continue
            response.raise_for_status()
            data = response.json()
            break

        if data is None:
            return ProviderResult(
                provider_id=provider.provider_key,
                provider_name=provider.name,
                error="No supported filter found",
            )

        # Parse entries
        entries = data.get("data", [])
        candidates = []

        for entry in entries:
            attrs = entry.get("attributes", {})
            entry_id = entry.get("id", "")

            # Extract structure info
            formula = attrs.get("chemical_formula_reduced", reduced)
            nsites = attrs.get("nsites", 0)
            space_group = attrs.get("space_group_number")

            has_partial = False

            candidate = Candidate(
                entry_id=entry_id,
                provider_id=provider.provider_key,
                reduced_formula=formula,
                nsites=nsites,
                space_group_number=space_group,
                has_partial_occupancy=has_partial,
                metadata=attrs,
            )
            candidates.append(candidate)

        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            candidates=candidates,
        )

    except requests.exceptions.Timeout:
        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            timed_out=True,
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 0
        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            error=f"HTTP {status_code}",
        )
    except Exception as e:
        return ProviderResult(
            provider_id=provider.provider_key,
            provider_name=provider.name,
            error=str(e),
        )


def search_parallel(
    query: str,
    providers: List[ProviderConfig],
    max_per_provider: int = 10,
    timeout_s: float = 8.0,
) -> List[ProviderResult]:
    """
    Query multiple OPTIMADE providers in parallel.
    
    Args:
        query: Chemical formula query
        providers: List of enabled providers to query
        max_per_provider: Maximum results per provider
        timeout_s: Per-provider timeout
        
    Returns:
        List of ProviderResult (one per provider)
    """
    enabled_providers = [p for p in providers if p.enabled]
    if not enabled_providers:
        return []
    
    # Use ThreadPoolExecutor for parallel queries
    max_workers = min(len(enabled_providers), 10)
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all queries
        future_to_provider = {
            executor.submit(_query_single_provider, provider, query, max_per_provider, timeout_s): provider
            for provider in enabled_providers
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_provider):
            provider = future_to_provider[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.warning(f"Provider {provider.provider_key} query failed: {e}")
                results.append(ProviderResult(
                    provider_id=provider.provider_key,
                    provider_name=provider.name,
                    error=str(e),
                ))
    
    return results


def compute_dedup_key(candidate: Candidate) -> tuple:
    """
    Compute deduplication key.
    
    Key: (reduced_formula, space_group_number, nsites)
    """
    return (
        candidate.reduced_formula,
        candidate.space_group_number or 0,  # 0 if unknown
        candidate.nsites,
    )


def deduplicate_candidates(
    provider_results: List[ProviderResult],
) -> List[AggregatedCandidate]:
    """
    Deduplicate candidates across providers.
    
    Args:
        provider_results: Results from all providers
        
    Returns:
        List of AggregatedCandidate with merged provider info
    """
    # Group candidates by dedup key
    key_to_candidates: Dict[tuple, List[tuple[Candidate, str]]] = {}  # (candidate, provider_id)
    
    for result in provider_results:
        if result.error or result.timed_out:
            continue
        
        for candidate in result.candidates:
            key = compute_dedup_key(candidate)
            if key not in key_to_candidates:
                key_to_candidates[key] = []
            key_to_candidates[key].append((candidate, result.provider_id))
    
    # Aggregate candidates
    aggregated = []
    for key, candidate_list in key_to_candidates.items():
        if not candidate_list:
            continue
        
        # Select primary candidate (highest trust weight provider, then highest score)
        # Provider trust weights: COD (1.0) > MP (0.9) > others
        primary_candidate = candidate_list[0][0]
        primary_provider_id = candidate_list[0][1]
        primary_trust = 0.0
        
        # Find provider configs to get trust weights
        all_providers = CURATED_DEFAULT_PROVIDERS.copy()
        provider_trust_map = {p.provider_key: p.trust_weight for p in all_providers}
        
        for candidate, provider_id in candidate_list:
            trust = provider_trust_map.get(provider_id, 0.7)
            if trust > primary_trust:
                primary_trust = trust
                primary_candidate = candidate
                primary_provider_id = provider_id
        
        # Collect all provider IDs
        provider_ids = list(set(provider_id for _, provider_id in candidate_list))
        
        # Merge metadata (prefer experimental > computed)
        aggregated_metadata = primary_candidate.metadata.copy()
        for candidate, provider_id in candidate_list:
            if provider_id != primary_provider_id:
                # Merge metadata (simple merge for v1)
                aggregated_metadata.update(candidate.metadata)
        
        aggregated.append(AggregatedCandidate(
            primary_candidate=primary_candidate,
            providers=provider_ids,
            aggregated_metadata=aggregated_metadata,
        ))
    
    return aggregated


def score_candidate(
    candidate: Candidate,
    provider: ProviderConfig,
    query_formula: str,
) -> float:
    """
    Score a candidate structure.
    
    Args:
        candidate: Candidate to score
        provider: Provider configuration
        query_formula: Original query formula (reduced)
        
    Returns:
        Score (higher is better, 0.0 to 1.0+)
    """
    score = 1.0
    
    # 1. Provider trust weight (experimental > computed > ML)
    score *= provider.trust_weight
    
    # 2. Formula match (exact match = +0.2, mismatch = -0.5)
    if candidate.reduced_formula == query_formula:
        score += 0.2
    else:
        score -= 0.5
    
    # 3. Partial occupancy penalty (-0.4)
    if candidate.has_partial_occupancy:
        score -= 0.4
    
    # 4. Size penalty (large cells: -0.2 if nsites > 200)
    if candidate.nsites > 200:
        score -= 0.2
    
    # 5. Size bonus (small cells: +0.1 if nsites < 50, +0.2 if < 20)
    if candidate.nsites < 50:
        score += 0.1
    if candidate.nsites < 20:
        score += 0.2
    
    # 6. Space group bonus (+0.05 if known)
    if candidate.space_group_number:
        score += 0.05
    
    return max(0.0, score)


def rank_candidates(
    aggregated_candidates: List[AggregatedCandidate],
    query_formula: str,
    providers: List[ProviderConfig],
) -> List[AggregatedCandidate]:
    """
    Rank aggregated candidates by score.
    
    Args:
        aggregated_candidates: Deduplicated candidates
        query_formula: Original query formula (reduced)
        providers: Provider configurations (for trust weights)
        
    Returns:
        Sorted list of AggregatedCandidate (highest score first)
    """
    provider_map = {p.provider_key: p for p in providers}
    
    # Score all candidates
    for agg_candidate in aggregated_candidates:
        provider = provider_map.get(agg_candidate.primary_candidate.provider_id)
        if provider:
            score = score_candidate(
                agg_candidate.primary_candidate,
                provider,
                query_formula,
            )
            agg_candidate.primary_candidate.score = score
    
    # Sort by score (descending), then nsites (ascending), then provider order
    def sort_key(agg: AggregatedCandidate) -> tuple:
        return (
            -agg.primary_candidate.score,  # Negative for descending
            agg.primary_candidate.nsites,  # Ascending
            agg.primary_candidate.provider_id,  # Stable sort
        )
    
    return sorted(aggregated_candidates, key=sort_key)

