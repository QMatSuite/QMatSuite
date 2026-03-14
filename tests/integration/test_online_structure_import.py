"""
Real network tests for online structure import across all providers.

These tests hit real network endpoints to verify the full import pipeline
works end-to-end. They are NOT mocked — they validate actual provider
responses, parsing, and structure reconstruction.

Markers:
    @pytest.mark.network — requires internet access
    @pytest.mark.integration — integration test

Expected to PASS locally with internet. Can be skipped via:
    pytest -m "not network"

These tests WILL FAIL if:
- Network is unavailable
- A provider is down or has changed its API
- Rate limits are hit (PubChem: 5 req/sec)
"""

import time
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip entire module if requests is not available
# ---------------------------------------------------------------------------
requests = pytest.importorskip("requests", reason="requests library required for network tests")


# ---------------------------------------------------------------------------
# Retry decorator for flaky network tests
# ---------------------------------------------------------------------------
def retry_on_network_error(max_attempts: int = 3, wait_seconds: float = 5.0):
    """Decorator to retry test on transient network failures."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (AssertionError, Exception) as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        time.sleep(wait_seconds)
            raise last_error  # type: ignore[misc]
        return wrapper
    return decorator


# ======================================================================
# OPTIMADE Provider Tests (Crystal search)
# ======================================================================

class TestOPTIMADEProviders:
    """Test each curated OPTIMADE provider individually."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_materials_project_search(self):
        """Materials Project OPTIMADE: search for Si."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="mp",
            name="Materials Project",
            base_url="https://optimade.materialsproject.org",
            enabled=True,
        )
        result = _query_single_provider(provider, "Si", max_results=3, timeout_s=15.0)

        assert not result.timed_out, f"Materials Project timed out: {result.error}"
        assert result.error is None, f"Materials Project error: {result.error}"
        assert len(result.candidates) > 0, "Materials Project returned no Si candidates"

        cand = result.candidates[0]
        assert cand.provider_id == "mp"
        assert cand.reduced_formula is not None
        assert cand.nsites is not None and cand.nsites > 0

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_cod_search(self):
        """COD OPTIMADE: search for NaCl."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="cod",
            name="COD",
            base_url="https://www.crystallography.net/cod/optimade/v1",
            enabled=True,
            trust_weight=1.0,
        )
        result = _query_single_provider(provider, "NaCl", max_results=3, timeout_s=15.0)

        if result.timed_out or result.error:
            pytest.skip(f"COD unavailable: {result.error or 'timeout'}")
        assert len(result.candidates) > 0, "COD returned no NaCl candidates"

        cand = result.candidates[0]
        assert cand.provider_id == "cod"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_alexandria_search(self):
        """Alexandria OPTIMADE: search for Si."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="alexandria",
            name="Alexandria",
            base_url="https://alexandria.icams.rub.de/pbe",
            enabled=True,
        )
        result = _query_single_provider(provider, "Si", max_results=3, timeout_s=15.0)

        assert not result.timed_out, f"Alexandria timed out"
        assert result.error is None, f"Alexandria error: {result.error}"
        assert len(result.candidates) > 0, "Alexandria returned no Si candidates"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=3, wait_seconds=5.0)
    def test_oqmd_search(self):
        """OQMD OPTIMADE: search for Fe."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="oqmd",
            name="OQMD",
            base_url="http://oqmd.org/optimade/v1",
            enabled=True,
        )
        result = _query_single_provider(provider, "Fe", max_results=3, timeout_s=20.0)

        if result.timed_out:
            pytest.skip("OQMD timed out (transient network issue)")
        if result.error is not None:
            pytest.skip(f"OQMD unavailable: {result.error}")
        assert len(result.candidates) > 0, "OQMD returned no Fe candidates"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_jarvis_search(self):
        """JARVIS OPTIMADE: search for TiO2."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="jarvis",
            name="JARVIS",
            base_url="https://jarvis.nist.gov/optimade/jarvisdft/v1",
            enabled=True,
        )
        result = _query_single_provider(provider, "TiO2", max_results=3, timeout_s=15.0)

        if result.timed_out or result.error:
            pytest.skip(f"JARVIS unavailable: {result.error or 'timeout'}")
        assert len(result.candidates) > 0, "JARVIS returned no TiO2 candidates"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_materials_cloud_search(self):
        """Materials Cloud OPTIMADE: search for MgO."""
        from qmatsuite.io.providers.optimade import _query_single_provider, ProviderConfig

        provider = ProviderConfig(
            provider_key="mcloud",
            name="Materials Cloud",
            base_url="https://optimade.materialscloud.org/main/mc3d-pbe-v1",
            enabled=True,
        )
        result = _query_single_provider(provider, "MgO", max_results=3, timeout_s=15.0)

        assert not result.timed_out, f"Materials Cloud timed out"
        assert result.error is None, f"Materials Cloud error: {result.error}"
        assert len(result.candidates) > 0, "Materials Cloud returned no MgO candidates"


class TestOPTIMADEParallelSearch:
    """Test parallel OPTIMADE federation search."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_parallel_search_si(self):
        """Search Si across all curated OPTIMADE providers in parallel."""
        from qmatsuite.io.providers.optimade import (
            search_parallel,
            CURATED_DEFAULT_PROVIDERS,
        )

        results = search_parallel(
            "Si",
            CURATED_DEFAULT_PROVIDERS,
            max_per_provider=3,
            timeout_s=15.0,
        )

        assert len(results) > 0, "No provider results returned"

        # At least one provider should have candidates
        total_candidates = sum(len(r.candidates) for r in results)
        providers_with_results = [r.provider_id for r in results if len(r.candidates) > 0]
        assert total_candidates > 0, (
            f"No candidates from any provider. "
            f"Timeouts: {[r.provider_id for r in results if r.timed_out]}, "
            f"Errors: {[r.provider_id for r in results if r.error]}"
        )
        assert len(providers_with_results) >= 1, "At least one provider should return results"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_parallel_search_dedup_and_rank(self):
        """Search, deduplicate, and rank candidates across providers."""
        from qmatsuite.io.providers.optimade import (
            search_parallel,
            deduplicate_candidates,
            rank_candidates,
            CURATED_DEFAULT_PROVIDERS,
        )

        results = search_parallel(
            "Si",
            CURATED_DEFAULT_PROVIDERS,
            max_per_provider=5,
            timeout_s=15.0,
        )

        # Filter to results with candidates
        results_with_candidates = [r for r in results if len(r.candidates) > 0]
        if not results_with_candidates:
            pytest.skip("No providers returned candidates (all timed out or errored)")

        # Deduplicate
        aggregated = deduplicate_candidates(results_with_candidates)
        assert len(aggregated) > 0, "Deduplication produced no candidates"

        # Rank
        ranked = rank_candidates(aggregated, "Si", CURATED_DEFAULT_PROVIDERS)
        assert len(ranked) > 0, "Ranking produced no candidates"

        # Top candidate should have a reasonable score
        top = ranked[0]
        assert top.primary_candidate.reduced_formula is not None


# ======================================================================
# OPTIMADE Structure Fetch Tests
# ======================================================================

class TestOPTIMADEStructureFetch:
    """Test fetching full structures from OPTIMADE."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=3, wait_seconds=5.0)
    def test_fetch_structure_materials_project(self):
        """Fetch a real Si structure from Materials Project OPTIMADE."""
        from qmatsuite.io.online_search import search_optimade, fetch_structure_from_optimade

        base_url, entries = search_optimade("Si", max_results=1)
        assert entries and len(entries) > 0, "No Si entries found"

        entry_id = entries[0]["id"]
        structure, raw_data = fetch_structure_from_optimade(base_url, entry_id)

        assert structure is not None, "Structure fetch returned None"
        assert len(structure) > 0, "Structure has no sites"
        assert structure.lattice is not None, "Structure has no lattice"
        assert len(structure.species) > 0, "Structure has no species"

        # Verify raw data
        assert "data" in raw_data
        assert "attributes" in raw_data["data"]

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=3, wait_seconds=5.0)
    def test_fetched_structure_has_visualization_fields(self):
        """Fetched structure should have fields needed for 3D visualization."""
        from qmatsuite.io.online_search import search_optimade, fetch_structure_from_optimade

        base_url, entries = search_optimade("Si", max_results=1)
        assert entries and len(entries) > 0

        entry_id = entries[0]["id"]
        structure, _ = fetch_structure_from_optimade(base_url, entry_id)

        # Required for visualization
        assert structure.lattice is not None
        lattice = structure.lattice
        assert lattice.a > 0 and lattice.b > 0 and lattice.c > 0
        assert len(structure.cart_coords) == len(structure)
        assert len(structure.frac_coords) == len(structure)


# ======================================================================
# PubChem Provider Tests (Molecule search)
# ======================================================================

class TestPubChemProvider:
    """Test PubChem molecule search."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_search_by_name_caffeine(self):
        """PubChem: search by name 'caffeine'."""
        from qmatsuite.io.providers.pubchem import search_by_name

        cids = search_by_name("caffeine", max_results=3)
        assert len(cids) > 0, "PubChem returned no CIDs for 'caffeine'"
        # Caffeine CID is 2519
        assert "2519" in cids, f"Expected CID 2519 for caffeine, got: {cids}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_search_by_name_aspirin(self):
        """PubChem: search by name 'aspirin'."""
        from qmatsuite.io.providers.pubchem import search_by_name

        cids = search_by_name("aspirin", max_results=3)
        assert len(cids) > 0, "PubChem returned no CIDs for 'aspirin'"
        # Aspirin CID is 2244
        assert "2244" in cids, f"Expected CID 2244 for aspirin, got: {cids}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_search_by_formula_h2o(self):
        """PubChem: search by formula H2O."""
        from qmatsuite.io.providers.pubchem import search_by_formula

        cids = search_by_formula("H2O", max_results=3)
        assert len(cids) > 0, "PubChem returned no CIDs for H2O"
        # Water CID is 962
        assert "962" in cids, f"Expected CID 962 for H2O, got: {cids}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_fetch_3d_sdf_caffeine(self):
        """PubChem: fetch 3D SDF for caffeine (CID 2519)."""
        from qmatsuite.io.providers.pubchem import fetch_3d_sdf

        sdf_content = fetch_3d_sdf("2519")
        assert sdf_content is not None, "fetch_3d_sdf returned None for caffeine"
        assert len(sdf_content) > 100, "SDF content too short"
        assert "V2000" in sdf_content or "V3000" in sdf_content, "SDF missing version line"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_parse_sdf_to_molecule(self):
        """PubChem: parse SDF to pymatgen Molecule."""
        from qmatsuite.io.providers.pubchem import fetch_3d_sdf, parse_sdf_to_molecule

        sdf_content = fetch_3d_sdf("962")  # Water
        assert sdf_content is not None

        molecule = parse_sdf_to_molecule(sdf_content, "962")
        assert molecule is not None, "parse_sdf_to_molecule returned None for water"
        assert len(molecule) == 3, f"Water should have 3 atoms, got {len(molecule)}"

        # Check species
        species = sorted([str(sp) for sp in molecule.species])
        assert "H" in species, f"Water should contain H, got: {species}"
        assert "O" in species, f"Water should contain O, got: {species}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_search_pubchem_unified(self):
        """PubChem: unified search for 'ethanol' returns PubChemCandidate."""
        from qmatsuite.io.providers.pubchem import search_pubchem, PubChemCandidate

        candidates = search_pubchem("ethanol", max_results=3)
        assert len(candidates) > 0, "search_pubchem returned no candidates for ethanol"

        cand = candidates[0]
        assert isinstance(cand, PubChemCandidate)
        assert cand.cid is not None
        assert cand.name is not None
        assert cand.formula is not None
        # Molecule may or may not be parsed depending on SDF availability
        if cand.molecule is not None:
            assert len(cand.molecule) > 0


# ======================================================================
# OPTIMADE Registry Tests
# ======================================================================

class TestOPTIMADERegistry:
    """Test OPTIMADE provider registry fetching."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_fetch_optimade_registry(self):
        """Fetch the live OPTIMADE provider registry."""
        from qmatsuite.io.providers.optimade import fetch_optimade_registry

        providers = fetch_optimade_registry()
        assert providers is not None, "Registry fetch returned None"
        assert len(providers) > 0, "Registry returned no providers"

        # Verify at least some known providers exist
        provider_keys = [p.provider_key for p in providers]
        # Materials Project should always be in the registry
        assert any("mp" in k.lower() or "materials" in k.lower() for k in provider_keys), (
            f"Materials Project not found in registry. Keys: {provider_keys[:10]}..."
        )


# ======================================================================
# Unified Search Tests (Full Pipeline)
# ======================================================================

class TestUnifiedSearch:
    """Test the full unified_search pipeline with real network."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_unified_search_crystal_mode(self):
        """Full pipeline: unified_search in crystal mode for Si."""
        from qmatsuite.io.providers import unified_search

        result = unified_search(
            "Si",
            mode="crystal",
            max_results=10,
            timeout_s=15.0,
        )

        assert len(result.providers_queried) > 0, "No providers were queried"
        assert len(result.candidates) > 0, (
            f"No crystal candidates for Si. "
            f"Providers: {result.providers_queried}, "
            f"Errors: {result.errors}"
        )

        # All candidates should be OPTIMADE-type
        from qmatsuite.io.providers.optimade import Candidate as OptimadeCandidate
        for cand in result.candidates:
            assert isinstance(cand, OptimadeCandidate), f"Expected OptimadeCandidate, got {type(cand)}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_unified_search_molecule_mode(self):
        """Full pipeline: unified_search in molecule mode for caffeine."""
        from qmatsuite.io.providers import unified_search

        result = unified_search(
            "caffeine",
            mode="molecule",
            max_results=5,
            timeout_s=15.0,
        )

        assert "pubchem" in result.providers_queried, "PubChem was not queried in molecule mode"
        assert len(result.candidates) > 0, (
            f"No molecule candidates for caffeine. Errors: {result.errors}"
        )

        # All candidates should be PubChem-type
        from qmatsuite.io.providers.pubchem import PubChemCandidate
        for cand in result.candidates:
            assert isinstance(cand, PubChemCandidate), f"Expected PubChemCandidate, got {type(cand)}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_unified_search_auto_mode(self):
        """Full pipeline: unified_search in auto mode for H2O."""
        from qmatsuite.io.providers import unified_search

        result = unified_search(
            "H2O",
            mode="auto",
            max_results=10,
            timeout_s=15.0,
        )

        assert len(result.providers_queried) > 1, (
            f"Auto mode should query multiple providers, got: {result.providers_queried}"
        )
        assert "pubchem" in result.providers_queried, "PubChem should be queried in auto mode"
        assert len(result.candidates) > 0, (
            f"No candidates for H2O in auto mode. Errors: {result.errors}"
        )


# ======================================================================
# QMSService API Layer Tests (Real Network)
# ======================================================================

class TestQMSServiceOnlineSearch:
    """Test QMSService.OnlineSearch with real network calls."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_service_search_crystal(self):
        """QMSService API: search_structures crystal mode."""
        from qmatsuite.api import QMSService
        from qmatsuite.api.types.online_search import SearchResultDTO

        result = QMSService.OnlineSearch.search_structures(
            query="Si",
            mode="crystal",
            limit=5,
            timeout_s=15.0,
        )

        assert isinstance(result, SearchResultDTO)
        assert result.query == "Si"
        assert result.mode == "crystal"
        assert len(result.candidates) > 0, (
            f"No crystal candidates. Providers: {result.providers_queried}, partial: {result.partial}"
        )

        # Verify candidate DTO structure
        cand = result.candidates[0]
        assert cand.candidate_id is not None
        assert cand.structure_type == "crystal"
        assert cand.formula is not None

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_service_search_molecule(self):
        """QMSService API: search_structures molecule mode."""
        from qmatsuite.api import QMSService
        from qmatsuite.api.types.online_search import SearchResultDTO

        result = QMSService.OnlineSearch.search_structures(
            query="aspirin",
            mode="molecule",
            limit=5,
            timeout_s=15.0,
        )

        assert isinstance(result, SearchResultDTO)
        assert result.query == "aspirin"
        assert result.mode == "molecule"
        # PubChem should return candidates for aspirin
        if len(result.candidates) > 0:
            cand = result.candidates[0]
            assert cand.structure_type == "molecule"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_service_list_providers(self):
        """QMSService API: list_providers returns curated OPTIMADE + PubChem."""
        from qmatsuite.api import QMSService
        from qmatsuite.api.types.online_search import ProviderListDTO

        result = QMSService.OnlineSearch.list_providers()

        assert isinstance(result, ProviderListDTO)
        assert len(result.optimade_providers) > 0
        assert result.pubchem_enabled is True

        # Verify curated providers are present
        provider_keys = [p.provider_key for p in result.optimade_providers]
        assert "mp" in provider_keys, f"Materials Project not in providers: {provider_keys}"


# ======================================================================
# Daemon RPC Layer Tests (Real Network)
# ======================================================================

class TestDaemonOnlineSearchRPC:
    """Test daemon RPC handlers with real network calls."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_daemon_search_online_crystal(self):
        """Daemon RPC: structure_search_online for Si (crystal)."""
        from qmatsuite.daemon.server import QMSDaemon

        daemon = QMSDaemon()
        payload = {
            "query": "Si",
            "mode": "crystal",
            "max_results": 5,
        }

        result = daemon._handle_structure_search_online(payload)

        assert "session_id" in result, f"Missing session_id in result: {list(result.keys())}"
        assert "candidates" in result
        assert len(result["candidates"]) > 0, (
            f"No candidates. Partial: {result.get('partial')}, "
            f"Providers: {result.get('providers_queried')}"
        )
        assert result["candidates"][0]["structure_type"] == "crystal"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_daemon_search_online_molecule(self):
        """Daemon RPC: structure_search_online for ethanol (molecule)."""
        from qmatsuite.daemon.server import QMSDaemon

        daemon = QMSDaemon()
        payload = {
            "query": "ethanol",
            "mode": "molecule",
            "max_results": 5,
        }

        result = daemon._handle_structure_search_online(payload)

        assert "session_id" in result
        assert "candidates" in result
        # PubChem should find ethanol
        if len(result["candidates"]) > 0:
            assert result["candidates"][0]["structure_type"] == "molecule"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_daemon_search_online_auto(self):
        """Daemon RPC: structure_search_online in auto mode for H2O."""
        from qmatsuite.daemon.server import QMSDaemon

        daemon = QMSDaemon()
        payload = {
            "query": "H2O",
            "mode": "auto",
            "max_results": 10,
        }

        result = daemon._handle_structure_search_online(payload)

        assert "session_id" in result
        assert "candidates" in result
        assert len(result["candidates"]) > 0, "H2O in auto mode should find results"
        assert "providers_queried" in result
        assert len(result["providers_queried"]) > 1, "Auto mode should query multiple providers"


# ======================================================================
# Diverse Search Pattern Tests
# ======================================================================

class TestDiverseSearchPatterns:
    """Test different search patterns: simple elements, multi-element, formulas, molecule names."""

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_single_element_si(self):
        """Crystal search: single element Si."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("Si", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No Si crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_single_element_fe(self):
        """Crystal search: single element Fe."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("Fe", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No Fe crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_binary_compound_nacl(self):
        """Crystal search: binary compound NaCl."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("NaCl", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No NaCl crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_ternary_compound_batio3(self):
        """Crystal search: ternary compound BaTiO3 (perovskite)."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("BaTiO3", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No BaTiO3 crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_semiconductor_gaas(self):
        """Crystal search: semiconductor GaAs."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("GaAs", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No GaAs crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_crystal_oxide_tio2(self):
        """Crystal search: oxide TiO2."""
        from qmatsuite.io.providers import unified_search

        result = unified_search("TiO2", mode="crystal", max_results=5, timeout_s=15.0)
        assert len(result.candidates) > 0, f"No TiO2 crystals. Errors: {result.errors}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_molecule_by_name_caffeine(self):
        """Molecule search by common name: caffeine."""
        from qmatsuite.io.providers.pubchem import search_by_name

        cids = search_by_name("caffeine", max_results=3)
        assert len(cids) > 0, "PubChem found no CIDs for 'caffeine'"
        assert "2519" in cids

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_molecule_by_name_ibuprofen(self):
        """Molecule search by common name: ibuprofen."""
        from qmatsuite.io.providers.pubchem import search_by_name

        cids = search_by_name("ibuprofen", max_results=3)
        assert len(cids) > 0, "PubChem found no CIDs for 'ibuprofen'"
        assert "3672" in cids

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_molecule_by_name_benzene(self):
        """Molecule search by common name: benzene."""
        from qmatsuite.io.providers.pubchem import search_by_name

        cids = search_by_name("benzene", max_results=3)
        assert len(cids) > 0, "PubChem found no CIDs for 'benzene'"
        assert "241" in cids

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_molecule_by_formula_c6h6(self):
        """Molecule search by formula: C6H6 (benzene)."""
        from qmatsuite.io.providers.pubchem import search_by_formula

        cids = search_by_formula("C6H6", max_results=5)
        assert len(cids) > 0, "PubChem found no CIDs for formula C6H6"
        # Benzene (CID 241) should be among results
        assert "241" in cids, f"Benzene CID 241 not in formula results: {cids}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=3.0)
    def test_molecule_3d_structure_fetch(self):
        """Molecule: fetch 3D structure from PubChem and parse to Molecule."""
        from qmatsuite.io.providers.pubchem import fetch_3d_sdf, parse_sdf_to_molecule

        # Benzene (CID 241) - well-known 3D structure
        sdf = fetch_3d_sdf("241")
        assert sdf is not None, "Failed to fetch benzene SDF"

        mol = parse_sdf_to_molecule(sdf, "241")
        assert mol is not None, "Failed to parse benzene SDF to Molecule"
        assert len(mol) == 12, f"Benzene should have 12 atoms (6C + 6H), got {len(mol)}"

    @pytest.mark.network
    @pytest.mark.integration
    @retry_on_network_error(max_attempts=2, wait_seconds=5.0)
    def test_molecule_by_formula_h2o(self):
        """Molecule search by formula: H2O (water, async PubChem)."""
        from qmatsuite.io.providers.pubchem import search_by_formula

        cids = search_by_formula("H2O", max_results=5)
        assert len(cids) > 0, "PubChem found no CIDs for formula H2O"
        assert "962" in cids, f"Water CID 962 not in formula results: {cids}"
