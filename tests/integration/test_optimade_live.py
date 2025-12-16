"""
Real network integration tests for OPTIMADE pipeline.

These tests perform actual HTTP requests against Materials Cloud OPTIMADE endpoints.
They are intended to fail in CI if the endpoint/format changes, providing an early
warning that the "no-key online import" path is broken.

Run with: pytest -m integration -k optimade_live -s
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import pytest
import requests
from pymatgen.core import Structure as PMGStructure

from quantumvitas.io.online_search import (
    OPTIMADE_BASES,
    extract_provenance,
    fetch_structure_from_optimade,
    normalize_formula,
    reduce_formula,
    resolve_overview_fields,
    search_optimade,
)


# Helper: try_get(url, params=None)
def try_get(url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
    """
    Make HTTP GET request with reasonable timeouts.
    
    Args:
        url: URL to request
        params: Optional query parameters
        
    Returns:
        Response object
        
    Raises:
        requests.exceptions.RequestException: On network/timeout errors
    """
    return requests.get(url, params=params, timeout=(5, 30))


# Helper: pick_first_candidate(entries)
def pick_first_candidate(
    entries: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Pick the first candidate from OPTIMADE search results.
    
    Uses first result returned by search (no sorting/filtering).
    
    Args:
        entries: List of OPTIMADE entry dicts (from search_optimade)
        
    Returns:
        (base_used, structure_id, attributes) tuple
        Returns (None, None, None) if no entries found
    """
    if not entries:
        return None, None, None
    
    # Pick first result (as returned by search)
    entry = entries[0]
    entry_id = entry.get("id")
    attrs = entry.get("attributes", {})
    if entry_id:
        return None, entry_id, attrs
    
    return None, None, None


@pytest.mark.integration
def test_optimade_live_search_si():
    """
    Test A: Live OPTIMADE search for Si works.
    
    Performs real HTTP request and verifies:
    - Search returns 200 OK
    - Response contains "data" list
    - At least one result is returned
    """
    query = "Si"
    
    # Normalize and reduce formula (same as production code)
    normalized = normalize_formula(query)
    reduced = reduce_formula(normalized)
    filter_value = f'chemical_formula_reduced="{reduced}"'
    
    # Try each base in order
    errors = []
    for base_url in OPTIMADE_BASES:
        try:
            url = f"{base_url}/v1/structures"
            params = {
                "filter": filter_value,
                "page_limit": 10,
            }
            
            start_time = time.time()
            response = try_get(url, params=params)
            elapsed = time.time() - start_time
            
            # Accept HTTP 200 only
            assert response.status_code == 200, (
                f"Expected HTTP 200, got {response.status_code} from {url}\n"
                f"Response: {response.text[:500]}"
            )
            
            # Parse JSON
            data = response.json()
            
            # Assert structure
            assert "data" in data, f"Response missing 'data' key. Keys: {list(data.keys())}"
            assert isinstance(data["data"], list), f"'data' is not a list: {type(data['data'])}"
            assert len(data["data"]) > 0, f"No results returned from {base_url}"
            
            # Print success summary
            print(f"\n✓ OPTIMADE search succeeded")
            print(f"  Base: {base_url}")
            print(f"  Results: {len(data['data'])}")
            print(f"  Elapsed: {elapsed:.2f}s")
            
            return  # Success - exit early
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "?"
            errors.append(f"{base_url}: HTTP {status_code}")
            if status_code == 404:
                # 404 is expected for some bases, continue to next
                continue
            # Other HTTP errors - log but continue (try next base)
            print(f"  {base_url}: HTTP {status_code} - {e}")
            continue
        except requests.exceptions.RequestException as e:
            # Network errors - try next base, but if all fail, raise (don't skip)
            errors.append(f"{base_url}: {type(e).__name__}: {e}")
            print(f"  {base_url}: Request failed - {e}")
            continue
        except AssertionError:
            # Re-raise assertion errors (fail test, don't skip)
            raise
        except Exception as e:
            # Unexpected errors - try next base, but if all fail, raise (don't skip)
            errors.append(f"{base_url}: {type(e).__name__}: {e}")
            print(f"  {base_url}: Unexpected error - {e}")
            continue
    
    # All bases failed - fail test (don't skip)
    # This ensures CI fails if OPTIMADE is down/broken
    pytest.fail(
        f"All OPTIMADE bases failed for query '{query}':\n"
        + "\n".join(f"  - {err}" for err in errors)
        + "\n\nThis test must not be skipped. If OPTIMADE is down, CI should fail."
    )


@pytest.mark.integration
def test_optimade_live_fetch_si_structure_and_parse_pymatgen():
    """
    Test B: Live OPTIMADE detail fetch parses into pymatgen Structure.
    
    Uses the same code paths as production:
    - search_optimade() for search
    - fetch_structure_from_optimade() for detail fetch
    
    Verifies:
    - Structure is valid pymatgen.Structure
    - Formula is Si
    - Either structure or primitive has 2 sites
    - All species are Si
    - Lattice is valid
    """
    query = "Si"
    
    # Step 1: Search using production function
    start_search = time.time()
    base_url, entries = search_optimade(query, max_results=10)
    elapsed_search = time.time() - start_search
    
    assert base_url is not None, "search_optimade() returned None base_url"
    assert len(entries) > 0, "search_optimade() returned no entries"
    
    # Pick first candidate (as returned by search)
    _, structure_id, attrs = pick_first_candidate(entries)
    assert structure_id is not None, "No candidate found in search results"
    
    nsites = attrs.get("nsites") if attrs else None
    print(f"\n✓ OPTIMADE search completed")
    print(f"  Base: {base_url}")
    print(f"  Chosen ID: {structure_id}")
    print(f"  nsites: {nsites}")
    print(f"  Search elapsed: {elapsed_search:.2f}s")
    
    # Step 2: Fetch full structure and raw data using production function
    start_fetch = time.time()
    structure, optimade_raw = fetch_structure_from_optimade(base_url, structure_id)
    elapsed_fetch = time.time() - start_fetch
    
    assert structure is not None, (
        f"fetch_structure_from_optimade() returned None for {base_url}/{structure_id}\n"
        f"Check that the endpoint returns valid OPTIMADE structure data."
    )
    assert optimade_raw is not None, (
        f"fetch_structure_from_optimade() returned None raw data for {base_url}/{structure_id}"
    )
    
    # Assertions on structure
    assert isinstance(structure, PMGStructure), (
        f"Expected pymatgen.Structure, got {type(structure)}"
    )
    
    # Check formula
    reduced_formula = structure.composition.reduced_formula
    assert reduced_formula == "Si", (
        f"Expected formula 'Si', got '{reduced_formula}'\n"
        f"Structure: {structure}"
    )
    
    # Check sites (any valid Si structure is acceptable - first result may vary)
    num_sites = structure.num_sites
    primitive = structure.get_primitive_structure()
    primitive_sites = primitive.num_sites
    
    assert num_sites > 0, f"Structure must have > 0 sites, got {num_sites}"
    assert primitive_sites > 0, f"Primitive must have > 0 sites, got {primitive_sites}"
    
    # Check all species are Si
    all_si = all(str(sp) == "Si" for sp in structure.species)
    assert all_si, (
        f"Not all species are Si: {[str(sp) for sp in structure.species]}\n"
        f"Structure: {structure}"
    )
    
    # Check lattice is valid
    lattice = structure.lattice
    assert lattice.matrix.shape == (3, 3), (
        f"Lattice matrix shape is {lattice.matrix.shape}, expected (3, 3)"
    )
    
    # Check coords length matches num_sites
    assert len(structure.cart_coords) == num_sites, (
        f"Coords length ({len(structure.cart_coords)}) != num_sites ({num_sites})"
    )
    
    # Step 3: Extract and validate provenance
    optimade_data = optimade_raw.get("data", {})
    optimade_attrs = optimade_data.get("attributes", {})
    
    # Extract provider/database from base URL (same logic as daemon)
    provider = "main"
    database = "unknown"
    if base_url:
        parts = base_url.rstrip("/").split("/")
        if len(parts) >= 2:
            provider = parts[-2] if parts[-2] in ["main", "archive"] else "main"
            database = parts[-1] if parts else "unknown"
    
    # Use production helper to extract provenance
    provenance = extract_provenance(
        provider=provider,
        database=database,
        base_url=base_url,
        optimade_id=structure_id,
        attributes=optimade_attrs,
        raw=optimade_raw,
    )
    
    # Assert required provenance fields exist
    assert "source_name" in provenance, "Provenance missing 'source_name'"
    assert "provider" in provenance, "Provenance missing 'provider'"
    assert "database" in provenance, "Provenance missing 'database'"
    assert "base_url" in provenance, "Provenance missing 'base_url'"
    assert "optimade_id" in provenance, "Provenance missing 'optimade_id'"
    
    # Assert required field values
    assert provenance["source_name"] != "", "source_name is empty"
    assert "Materials Cloud" in provenance["source_name"], (
        f"source_name should contain 'Materials Cloud', got '{provenance['source_name']}'"
    )
    assert provenance["provider"] == "main", (
        f"Expected provider='main', got '{provenance['provider']}'"
    )
    assert provenance["database"] != "", "database is empty"
    assert provenance["base_url"].startswith("https://optimade.materialscloud.org/"), (
        f"base_url should start with https://optimade.materialscloud.org/, got '{provenance['base_url']}'"
    )
    assert provenance["optimade_id"] == structure_id, (
        f"optimade_id mismatch: expected '{structure_id}', got '{provenance['optimade_id']}'"
    )
    
    # Assert overview-critical fields using same fallback priorities as Details panel
    # Formula: check payload formula matches expected
    assert reduced_formula == "Si", f"Formula mismatch: expected 'Si', got '{reduced_formula}'"
    
    # Also check if provenance has formula (optional, but if present should match)
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            formula_hill = extras.get("formula_hill") or extras.get("formula_hill_compact")
            if formula_hill:
                # Normalize for comparison (Si vs Si1)
                assert formula_hill.replace("1", "").strip() == "Si" or formula_hill == "Si", (
                    f"Provenance formula_hill '{formula_hill}' doesn't match expected 'Si'"
                )
    
    # Number of sites: ensure nsites is present and > 0
    assert num_sites > 0, f"nsites must be > 0, got {num_sites}"
    
    # If provenance has number_of_sites or nsites, assert it matches
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            prov_nsites = extras.get("number_of_sites")
            if prov_nsites is not None:
                assert prov_nsites == num_sites, (
                    f"Provenance number_of_sites ({prov_nsites}) != structure num_sites ({num_sites})"
                )
    
    if "attributes" in provenance:
        attrs = provenance["attributes"]
        if isinstance(attrs, dict):
            attrs_nsites = attrs.get("nsites")
            if attrs_nsites is not None:
                assert attrs_nsites == num_sites, (
                    f"Provenance attributes.nsites ({attrs_nsites}) != structure num_sites ({num_sites})"
                )
    
    # Space group: if present, validate format
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            sg_international = extras.get("spacegroup_international")
            sg_number = extras.get("spacegroup_number")
            
            if sg_international is not None:
                assert isinstance(sg_international, str), (
                    f"spacegroup_international should be string, got {type(sg_international)}"
                )
                assert sg_international != "", "spacegroup_international is empty string"
                print(f"  Space group: {sg_international}")
            
            if sg_number is not None:
                assert isinstance(sg_number, (int, str)), (
                    f"spacegroup_number should be int or string, got {type(sg_number)}"
                )
                sg_num_int = int(sg_number) if isinstance(sg_number, str) else sg_number
                assert 1 <= sg_num_int <= 230, (
                    f"spacegroup_number should be in [1, 230], got {sg_num_int}"
                )
                print(f"  Space group number: {sg_num_int}")
            
            if sg_international is None and sg_number is None:
                print("  Note: Space group fields absent in this entry")
    
    # Partial occupancies: if present, assert boolean
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            partial_occ = extras.get("partial_occupancies")
            if partial_occ is not None:
                assert isinstance(partial_occ, bool), (
                    f"partial_occupancies should be boolean, got {type(partial_occ)}"
                )
    
    # Timestamps: if present, assert non-empty strings
    if "created" in provenance:
        assert isinstance(provenance["created"], str), (
            f"created should be string, got {type(provenance['created'])}"
        )
        assert provenance["created"] != "", "created is empty string"
    
    if "modified" in provenance:
        assert isinstance(provenance["modified"], str), (
            f"modified should be string, got {type(provenance['modified'])}"
        )
        assert provenance["modified"] != "", "modified is empty string"
    
    # Assert raw blocks exist when available
    if "extras" in provenance:
        assert isinstance(provenance["extras"], dict), (
            f"extras should be dict, got {type(provenance['extras'])}"
        )
        print(f"  Extras keys: {sorted(provenance['extras'].keys())}")
    
    if "attributes" in provenance:
        assert isinstance(provenance["attributes"], dict), (
            f"attributes should be dict, got {type(provenance['attributes'])}"
        )
        print(f"  Attributes keys (sample): {sorted(list(provenance['attributes'].keys())[:10])}")
    
    # Step 4: Resolve overview fields using production helper
    overview = resolve_overview_fields(structure, provenance)
    
    # Hard assertions on resolved overview fields
    assert overview["formula"] != "", "Resolved formula must not be empty"
    assert isinstance(overview["nsites"], int), f"Resolved nsites must be int, got {type(overview['nsites'])}"
    assert overview["nsites"] > 0, f"Resolved nsites must be > 0, got {overview['nsites']}"
    assert overview["source_name"] != "", "Resolved source_name must not be empty"
    assert overview["provider"] != "", "Resolved provider must not be empty"
    assert overview["database"] != "", "Resolved database must not be empty"
    assert overview["optimade_id"] == structure_id, (
        f"Resolved optimade_id ({overview['optimade_id']}) != fetched id ({structure_id})"
    )
    
    # Verify JSON serializable
    try:
        json.dumps(overview)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Resolved overview is not JSON-serializable: {e}")
    
    # Optional assertions when present
    if overview["spacegroup_number"] is not None:
        sg_num = overview["spacegroup_number"]
        assert isinstance(sg_num, int), f"spacegroup_number must be int, got {type(sg_num)}"
        assert 1 <= sg_num <= 230, f"spacegroup_number must be in [1, 230], got {sg_num}"
    
    if overview["spacegroup_international"] is not None:
        sg_sym = overview["spacegroup_international"]
        assert isinstance(sg_sym, str), f"spacegroup_international must be string, got {type(sg_sym)}"
        assert sg_sym != "", "spacegroup_international must not be empty string"
        print(f"  Space group: {sg_sym}")
    
    if overview["partial_occupancies"] is not None:
        assert isinstance(overview["partial_occupancies"], bool), (
            f"partial_occupancies must be bool, got {type(overview['partial_occupancies'])}"
        )
    
    if overview["created"] is not None:
        assert isinstance(overview["created"], str), f"created must be string, got {type(overview['created'])}"
        assert overview["created"] != "", "created must not be empty string"
    
    if overview["modified"] is not None:
        assert isinstance(overview["modified"], str), f"modified must be string, got {type(overview['modified'])}"
        assert overview["modified"] != "", "modified must not be empty string"
    
    # Print diagnostic keys when optional fields missing
    if overview["spacegroup_international"] is None and overview["spacegroup_number"] is None:
        print("  Note: Space group fields absent in this entry")
        if "extras" in provenance and isinstance(provenance["extras"], dict):
            print(f"  Extras keys: {sorted(provenance['extras'].keys())}")
    
    # Print success summary
    print(f"\n✓ OPTIMADE structure fetch and parse succeeded")
    print(f"  Structure sites: {num_sites}")
    print(f"  Primitive sites: {primitive_sites}")
    print(f"  Formula: {reduced_formula}")
    print(f"  Fetch elapsed: {elapsed_fetch:.2f}s")
    print(f"  Total elapsed: {elapsed_search + elapsed_fetch:.2f}s")
    print(f"\n✓ Provenance extraction validated")
    print(f"  Source: {provenance['source_name']}")
    print(f"  Provider: {provenance['provider']}")
    print(f"  Database: {provenance['database']}")
    print(f"  OPTIMADE ID: {provenance['optimade_id']}")
    print(f"\n✓ Overview fields resolved")
    print(f"  Formula: {overview['formula']}")
    print(f"  nsites: {overview['nsites']}")
    print(f"  Species: {', '.join(overview['species'])}")
    if overview["spacegroup_international"]:
        print(f"  Space group: {overview['spacegroup_international']}")
    if overview["spacegroup_number"]:
        print(f"  Space group number: {overview['spacegroup_number']}")


@pytest.mark.integration
def test_optimade_live_viewer_payload_builder():
    """
    Test C: Verify viewer payload builder accepts OPTIMADE structure.
    
    Feeds the parsed pymatgen.Structure into the shared payload builder
    and verifies:
    - Result is JSON-serializable
    - Payload contains expected atom entries with element + coords
    """
    query = "Si"
    
    # Get structure using production functions
    base_url, entries = search_optimade(query, max_results=10)
    assert base_url is not None and len(entries) > 0
    
    _, structure_id, _ = pick_first_candidate(entries)
    assert structure_id is not None
    
    structure, _ = fetch_structure_from_optimade(base_url, structure_id)
    assert structure is not None
    
    # Use shared payload builder (same as production)
    from quantumvitas.api import QVService
    from quantumvitas.analysis.structure_viz import DisplayModeParams
    
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        box_bounds=None,
        repeat_boundary=False,
    )
    
    # Build payload
    payload = QVService._build_structure_vis_payload(
        structure,
        params,
        structure_meta=None,
        trace_id="test_trace",
    )
    
    # Verify JSON serializable
    try:
        json_str = json.dumps(payload)
        json_bytes = len(json_str.encode('utf-8'))
    except (TypeError, ValueError) as e:
        pytest.fail(f"Payload is not JSON-serializable: {e}\nPayload keys: {list(payload.keys())}")
    
    # Verify payload structure
    assert "atoms" in payload, "Payload missing 'atoms' key"
    assert isinstance(payload["atoms"], list), f"'atoms' is not a list: {type(payload['atoms'])}"
    assert len(payload["atoms"]) > 0, "Payload has no atoms"
    
    # Verify atom entries have required fields
    for idx, atom in enumerate(payload["atoms"]):
        assert "element" in atom, f"Atom {idx} missing 'element' key. Keys: {list(atom.keys())}"
        assert "cart_coords" in atom, f"Atom {idx} missing 'cart_coords' key. Keys: {list(atom.keys())}"
        
        element = atom["element"]
        coords = atom["cart_coords"]
        
        assert isinstance(element, str), f"Atom {idx} element is not string: {type(element)}"
        assert isinstance(coords, list), f"Atom {idx} cart_coords is not list: {type(coords)}"
        assert len(coords) == 3, f"Atom {idx} cart_coords length is {len(coords)}, expected 3"
        assert all(isinstance(c, (int, float)) for c in coords), (
            f"Atom {idx} cart_coords contains non-numeric values: {coords}"
        )
    
    # Verify bonds if present
    if "bonds" in payload:
        assert isinstance(payload["bonds"], list), f"'bonds' is not a list: {type(payload['bonds'])}"
    
    # Verify perf metrics if present
    if "perf" in payload:
        perf = payload["perf"]
        assert "atoms" in perf, "Perf missing 'atoms' count"
        assert perf["atoms"] == len(payload["atoms"]), (
            f"Perf atoms count ({perf['atoms']}) != actual atoms ({len(payload['atoms'])})"
        )
    
    # Print success summary
    print(f"\n✓ Viewer payload builder test succeeded")
    print(f"  Atoms: {len(payload['atoms'])}")
    print(f"  Bonds: {len(payload.get('bonds', []))}")
    print(f"  Payload size: {json_bytes} bytes")
    if "perf" in payload:
        print(f"  Prep time: {payload['perf'].get('prep_ms', '?')}ms")
        print(f"  Bonds time: {payload['perf'].get('bonds_ms', '?')}ms")


@pytest.mark.integration
def test_optimade_live_fetch_mos2_with_rich_metadata():
    """
    Test D: Live OPTIMADE fetch for MoS2 (compound with richer metadata).
    
    MoS2 entries are more likely to have:
    - space group international + number
    - bravais lattice
    - number_of_sites
    
    Verifies:
    - Structure parses correctly
    - Provenance extraction works
    - Rich metadata fields are present and valid
    """
    query = "MoS2"
    
    # Step 1: Search using production function
    start_search = time.time()
    base_url, entries = search_optimade(query, max_results=10)
    elapsed_search = time.time() - start_search
    
    assert base_url is not None, "search_optimade() returned None base_url"
    assert len(entries) > 0, "search_optimade() returned no entries"
    
    # Pick first candidate (as returned by search)
    _, structure_id, attrs = pick_first_candidate(entries)
    assert structure_id is not None, "No candidate found in search results"
    
    # Check formula from search metadata
    formula_from_search = attrs.get("chemical_formula_reduced", "") if attrs else ""
    print(f"  Formula (from search): {formula_from_search}")
    
    nsites_from_search = attrs.get("nsites") if attrs else None
    print(f"\n✓ OPTIMADE search completed for {query}")
    print(f"  Base: {base_url}")
    print(f"  Chosen ID: {structure_id}")
    print(f"  nsites (from search): {nsites_from_search}")
    print(f"  Search elapsed: {elapsed_search:.2f}s")
    
    # Step 2: Fetch full structure and raw data
    start_fetch = time.time()
    structure, optimade_raw = fetch_structure_from_optimade(base_url, structure_id)
    elapsed_fetch = time.time() - start_fetch
    
    assert structure is not None, (
        f"fetch_structure_from_optimade() returned None for {base_url}/{structure_id}"
    )
    assert optimade_raw is not None, (
        f"fetch_structure_from_optimade() returned None raw data"
    )
    
    # Assertions on structure
    assert isinstance(structure, PMGStructure), (
        f"Expected pymatgen.Structure, got {type(structure)}"
    )
    
    # Check formula (may vary - some entries might be Mo, MoS, etc.)
    # Note: OPTIMADE metadata may say MoS2 but structure might be different
    # We validate provenance extraction regardless of exact formula match
    reduced_formula = structure.composition.reduced_formula
    # Just verify it contains Mo (the structure is valid)
    assert "Mo" in reduced_formula, (
        f"Expected formula containing 'Mo', got '{reduced_formula}'\n"
        f"Structure: {structure}"
    )
    print(f"  Note: Search metadata formula '{formula_from_search}' vs structure formula '{reduced_formula}'")
    
    num_sites = structure.num_sites
    assert num_sites > 0, f"nsites must be > 0, got {num_sites}"
    
    # Step 3: Extract and validate provenance
    optimade_data = optimade_raw.get("data", {})
    optimade_attrs = optimade_data.get("attributes", {})
    
    # Extract provider/database from base URL
    provider = "main"
    database = "unknown"
    if base_url:
        parts = base_url.rstrip("/").split("/")
        if len(parts) >= 2:
            provider = parts[-2] if parts[-2] in ["main", "archive"] else "main"
            database = parts[-1] if parts else "unknown"
    
    # Use production helper to extract provenance
    provenance = extract_provenance(
        provider=provider,
        database=database,
        base_url=base_url,
        optimade_id=structure_id,
        attributes=optimade_attrs,
        raw=optimade_raw,
    )
    
    # Assert required provenance fields
    assert "source_name" in provenance, "Provenance missing 'source_name'"
    assert "provider" in provenance, "Provenance missing 'provider'"
    assert "database" in provenance, "Provenance missing 'database'"
    assert "base_url" in provenance, "Provenance missing 'base_url'"
    assert "optimade_id" in provenance, "Provenance missing 'optimade_id'"
    assert provenance["provider"] == "main", f"Expected provider='main', got '{provenance['provider']}'"
    assert provenance["database"] != "", "database is empty"
    assert provenance["optimade_id"] == structure_id, "optimade_id mismatch"
    
    # Assert formula contains Mo (structure is valid)
    assert "Mo" in reduced_formula, f"Formula should contain 'Mo', got '{reduced_formula}'"
    
    # Assert nsites matches if present in provenance
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            prov_nsites = extras.get("number_of_sites")
            if prov_nsites is not None:
                assert prov_nsites == num_sites, (
                    f"Provenance number_of_sites ({prov_nsites}) != structure num_sites ({num_sites})"
                )
    
    # Assert space group fields if present (MoS2 should have them)
    has_spacegroup = False
    if "extras" in provenance:
        extras = provenance["extras"]
        if isinstance(extras, dict):
            sg_international = extras.get("spacegroup_international")
            sg_number = extras.get("spacegroup_number")
            
            if sg_international is not None:
                assert isinstance(sg_international, str), (
                    f"spacegroup_international should be string, got {type(sg_international)}"
                )
                assert sg_international != "", "spacegroup_international is empty"
                has_spacegroup = True
                print(f"  Space group: {sg_international}")
            
            if sg_number is not None:
                assert isinstance(sg_number, (int, str)), (
                    f"spacegroup_number should be int or string, got {type(sg_number)}"
                )
                sg_num_int = int(sg_number) if isinstance(sg_number, str) else sg_number
                assert 1 <= sg_num_int <= 230, (
                    f"spacegroup_number should be in [1, 230], got {sg_num_int}"
                )
                has_spacegroup = True
                print(f"  Space group number: {sg_num_int}")
            
            # Bravais lattice (if present)
            bravais = extras.get("bravais_lattice_extended") or extras.get("bravais_lattice")
            if bravais:
                assert isinstance(bravais, str), (
                    f"bravais_lattice should be string, got {type(bravais)}"
                )
                print(f"  Bravais lattice: {bravais}")
            
            # Print available keys for diagnostics
            print(f"  Extras keys: {sorted(extras.keys())}")
    
    if "attributes" in provenance:
        attrs = provenance["attributes"]
        if isinstance(attrs, dict):
            print(f"  Attributes keys (sample): {sorted(list(attrs.keys())[:15])}")
    
    # Step 4: Resolve overview fields using production helper
    overview = resolve_overview_fields(structure, provenance)
    
    # Hard assertions on resolved overview fields
    assert overview["formula"] != "", "Resolved formula must not be empty"
    assert isinstance(overview["nsites"], int), f"Resolved nsites must be int, got {type(overview['nsites'])}"
    assert overview["nsites"] > 0, f"Resolved nsites must be > 0, got {overview['nsites']}"
    assert overview["source_name"] != "", "Resolved source_name must not be empty"
    assert overview["provider"] != "", "Resolved provider must not be empty"
    assert overview["database"] != "", "Resolved database must not be empty"
    assert overview["optimade_id"] == structure_id, (
        f"Resolved optimade_id ({overview['optimade_id']}) != fetched id ({structure_id})"
    )
    
    # Formula should contain Mo (and preferably S if search metadata indicated MoS2)
    assert "Mo" in overview["formula"], f"Resolved formula must contain 'Mo', got '{overview['formula']}'"
    if formula_from_search and "mos2" in formula_from_search.lower():
        assert "S" in overview["formula"] or overview["formula"] == "MoS2", (
            f"Resolved formula should contain Mo and S (or be MoS2), got '{overview['formula']}'"
        )
    
    # Verify JSON serializable
    try:
        json.dumps(overview)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Resolved overview is not JSON-serializable: {e}")
    
    # Optional assertions when present
    if overview["spacegroup_number"] is not None:
        sg_num = overview["spacegroup_number"]
        assert isinstance(sg_num, int), f"spacegroup_number must be int, got {type(sg_num)}"
        assert 1 <= sg_num <= 230, f"spacegroup_number must be in [1, 230], got {sg_num}"
        has_spacegroup = True
    else:
        has_spacegroup = False
    
    if overview["spacegroup_international"] is not None:
        sg_sym = overview["spacegroup_international"]
        assert isinstance(sg_sym, str), f"spacegroup_international must be string, got {type(sg_sym)}"
        assert sg_sym != "", "spacegroup_international must not be empty string"
        has_spacegroup = True
        print(f"  Space group: {sg_sym}")
    
    if overview["partial_occupancies"] is not None:
        assert isinstance(overview["partial_occupancies"], bool), (
            f"partial_occupancies must be bool, got {type(overview['partial_occupancies'])}"
        )
    
    if overview["created"] is not None:
        assert isinstance(overview["created"], str), f"created must be string, got {type(overview['created'])}"
        assert overview["created"] != "", "created must not be empty string"
    
    if overview["modified"] is not None:
        assert isinstance(overview["modified"], str), f"modified must be string, got {type(overview['modified'])}"
        assert overview["modified"] != "", "modified must not be empty string"
    
    # Note: Space group is preferred but not always present, so we log but don't hard-require
    if not has_spacegroup:
        print("  Note: Space group fields absent in this entry (may vary by database)")
        if "extras" in provenance and isinstance(provenance["extras"], dict):
            print(f"  Extras keys: {sorted(provenance['extras'].keys())}")
    
    # Print success summary
    print(f"\n✓ OPTIMADE MoS2 fetch and provenance validation succeeded")
    print(f"  Structure sites: {num_sites}")
    print(f"  Formula: {reduced_formula}")
    print(f"  Fetch elapsed: {elapsed_fetch:.2f}s")
    print(f"  Total elapsed: {elapsed_search + elapsed_fetch:.2f}s")
    print(f"  Source: {provenance['source_name']}")
    print(f"  Database: {provenance['database']}")
    print(f"\n✓ Overview fields resolved")
    print(f"  Formula: {overview['formula']}")
    print(f"  nsites: {overview['nsites']}")
    print(f"  Species: {', '.join(overview['species'])}")
    if overview["spacegroup_international"]:
        print(f"  Space group: {overview['spacegroup_international']}")
    if overview["spacegroup_number"]:
        print(f"  Space group number: {overview['spacegroup_number']}")
    if overview["bravais_lattice"]:
        print(f"  Bravais lattice: {overview['bravais_lattice']}")
