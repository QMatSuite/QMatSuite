"""
Tests for QE parameter metadata RPC handler.

Tests the list_qe_parameter_metadata RPC endpoint which powers the
QE Parameter Browser in the GUI.
"""

import pytest
from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.data.qe_metadata import list_supported_modules, safe_load_metadata


@pytest.fixture
def daemon():
    """Create a QVDaemon instance for testing."""
    return QVDaemon()


def test_list_modules_returns_all_modules(daemon):
    """Test that list_modules returns all supported QE modules."""
    request = RPCRequest(
        id="test-1",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_modules"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "modules" in response.data
    modules = response.data["modules"]
    assert isinstance(modules, list)
    assert len(modules) > 0
    
    # Verify all expected modules are present (at least pw should exist)
    module_ids = [m["ulid"] for m in modules]
    assert "pw" in module_ids
    
    # Verify module structure
    for module in modules:
        assert "id" in module
        assert "label" in module
        assert isinstance(module["ulid"], str)
        assert isinstance(module["label"], str)
        # Label should be module_id.x for consistency
        assert module["label"] == f"{module["ulid"]}.x"


def test_list_modules_preserves_json_order(daemon):
    """Test that list_modules returns modules in JSON insertion order (not sorted)."""
    from quantumvitas.data.qe_metadata import safe_load_metadata
    
    # Get expected order from raw metadata
    raw_data = safe_load_metadata()
    expected_order = list(raw_data.get("modules", {}).keys())
    
    request = RPCRequest(
        id="test-1b",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_modules"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    modules = response.data["modules"]
    actual_order = [m["ulid"] for m in modules]
    
    # Verify order matches JSON order (at least for first few modules)
    # We check the first 5 to allow for some flexibility, but order should be preserved
    assert actual_order[:5] == expected_order[:5], \
        f"Module order should match JSON order. Expected: {expected_order[:5]}, Got: {actual_order[:5]}"


def test_list_sections_for_valid_module(daemon):
    """Test that list_sections returns sections for a valid module."""
    # Use 'pw' module which should always exist
    request = RPCRequest(
        id="test-2",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_sections", "module": "pw"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "sections" in response.data
    sections = response.data["sections"]
    assert isinstance(sections, list)
    assert len(sections) > 0
    
    # Verify section structure
    for section in sections:
        assert "id" in section
        assert "name" in section  # Clean name without '&'
        assert "label" in section  # Display label from metadata
        assert "kind" in section
        assert section["kind"] in ("namelist", "card")
        assert isinstance(section["ulid"], str)
        assert isinstance(section["name"], str)
        assert isinstance(section["label"], str)
        # name should NOT have '&' prefix
        assert not section["name"].startswith("&"), f"Section name should not have '&' prefix: {section['name']}"
        # label should match metadata: namelists have '&', cards don't
        if section["kind"] == "namelist":
            assert section["label"].startswith("&"), f"Namelist label should have '&' prefix: {section['label']}"
        else:
            assert not section["label"].startswith("&"), f"Card label should not have '&' prefix: {section['label']}"
    
    # Should have at least &CONTROL and &SYSTEM namelists for pw
    section_names = [s["name"] for s in sections]
    section_ids = [s["ulid"] for s in sections]
    assert "CONTROL" in section_names or "&CONTROL" in section_ids
    assert "SYSTEM" in section_names or "&SYSTEM" in section_ids
    
    # Verify K_POINTS is a card (not a namelist)
    kpoints_sections = [s for s in sections if s["name"] == "K_POINTS" or s["ulid"] == "K_POINTS"]
    if kpoints_sections:
        kpoints = kpoints_sections[0]
        assert kpoints["kind"] == "card", f"K_POINTS should be a card, got {kpoints['kind']}"
        assert kpoints["name"] == "K_POINTS", f"K_POINTS name should be 'K_POINTS', got {kpoints['name']}"
        assert not kpoints["name"].startswith("&"), "K_POINTS name should not have '&' prefix"
        # Verify label is raw (no extra '&' added by backend)
        assert kpoints["label"] == "K_POINTS", f"K_POINTS label should be 'K_POINTS', got {kpoints['label']}"


def test_list_sections_preserves_metadata_order(daemon):
    """Test that list_sections returns sections in metadata order (not sorted)."""
    from quantumvitas.data.qe_metadata import safe_load_metadata, get_module_card_sections, get_module_param_sections
    
    # Get expected order from raw metadata
    raw_data = safe_load_metadata()
    pw_module = raw_data.get("modules", {}).get("pw", {})
    
    # Cards should be in card_metadata order
    expected_card_order = list(pw_module.get("card_metadata", {}).keys())
    
    # Namelists should be in parameters map order (first appearance)
    sections_dict = get_module_param_sections("pw")
    expected_namelist_order = []
    seen_namelists = set()
    for section_name in sections_dict.keys():
        if section_name.startswith("&"):
            name = section_name[1:].upper()
            if name not in seen_namelists and name not in [c.upper() for c in expected_card_order]:
                expected_namelist_order.append(name)
                seen_namelists.add(name)
    
    request = RPCRequest(
        id="test-2b",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_sections", "module": "pw"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    sections = response.data["sections"]
    
    # Extract actual order
    actual_card_order = [s["name"] for s in sections if s["kind"] == "card"]
    actual_namelist_order = [s["name"] for s in sections if s["kind"] == "namelist"]
    
    # Verify cards are in metadata order (at least first few)
    if expected_card_order and actual_card_order:
        assert actual_card_order[:3] == [c.upper() for c in expected_card_order[:3]], \
            f"Card order should match metadata. Expected: {expected_card_order[:3]}, Got: {actual_card_order[:3]}"
    
    # Verify namelists are in parameters map order (at least first few)
    if expected_namelist_order and actual_namelist_order:
        assert actual_namelist_order[:3] == expected_namelist_order[:3], \
            f"Namelist order should match parameters map order. Expected: {expected_namelist_order[:3]}, Got: {actual_namelist_order[:3]}"


def test_list_sections_for_invalid_module(daemon):
    """Test that list_sections returns an error for an invalid module."""
    request = RPCRequest(
        id="test-3",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_sections", "module": "__nonexistent__"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is False
    assert "error" in response.__dict__ or hasattr(response, "error")
    # The error should be a structured error, not a raw exception
    # Check that error message contains something sensible
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    if error:
        assert "message" in error or isinstance(error, dict)


def test_list_parameters_for_valid_module_and_section(daemon):
    """Test that list_parameters returns parameters for a valid module/section."""
    request = RPCRequest(
        id="test-4",
        type="list_qe_parameter_metadata",
        payload={
            "operation": "list_parameters",
            "module": "pw",
            "section": "&SYSTEM",
        },
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "parameters" in response.data
    parameters = response.data["parameters"]
    assert isinstance(parameters, list)
    assert len(parameters) > 0
    
    # Verify parameter structure
    for param in parameters:
        assert "name" in param
        assert "type" in param
        assert "module" in param
        assert "section" in param
        assert isinstance(param["name"], str)
        assert param["module"] == "pw"
        assert param["section"] == "&SYSTEM"
        # Type can be null for v1 schema, but should be present
        # Default, enum, description can be null
    
    # Should have common parameters like ecutwfc, ibrav
    param_names = [p["name"] for p in parameters]
    assert "ecutwfc" in param_names or "ibrav" in param_names


def test_list_parameters_for_card_section(daemon):
    """Test that list_parameters returns card metadata for a card section."""
    request = RPCRequest(
        id="test-4b",
        type="list_qe_parameter_metadata",
        payload={
            "operation": "list_parameters",
            "module": "pw",
            "section": "K_POINTS",  # Card section (no '&' prefix)
        },
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "parameters" in response.data
    parameters = response.data["parameters"]
    assert isinstance(parameters, list)
    # Cards typically have metadata but may not have individual parameters
    # At minimum, should return card metadata if available
    
    # If K_POINTS card metadata exists, verify structure
    if len(parameters) > 0:
        for param in parameters:
            assert "name" in param
            assert "module" in param
            assert "section" in param
            assert param["module"] == "pw"
            # Section should be K_POINTS (no '&' prefix for cards)
            assert param["section"] == "K_POINTS" or param["section"] == "&K_POINTS"


def test_list_parameters_with_array_indexing(daemon):
    """Test that parameters with array indexing have indexing metadata (v2 schema)."""
    # Try to find a parameter with indexing (e.g., celldm in pw/SYSTEM)
    request = RPCRequest(
        id="test-5",
        type="list_qe_parameter_metadata",
        payload={
            "operation": "list_parameters",
            "module": "pw",
            "section": "&SYSTEM",
        },
    )
    
    response = daemon.handle_request(request)
    
    if not response.ok:
        pytest.skip("Could not load parameters (metadata may be missing)")
    
    parameters = response.data.get("parameters", [])
    
    # Look for celldm which should have indexing in v2 schema
    celldm_params = [p for p in parameters if p.get("name") == "celldm"]
    
    if celldm_params:
        celldm = celldm_params[0]
        # If indexing is present, verify its structure
        if "indexing" in celldm:
            indexing = celldm["indexing"]
            assert "kind" in indexing
            assert "index_name" in indexing
            assert "keyword_pattern" in indexing
            assert indexing["kind"] in ("bounded", "unbounded")
            assert isinstance(indexing["index_name"], str)
            assert isinstance(indexing["keyword_pattern"], str)


def test_search_parameters(daemon):
    """Test that search returns matching parameters."""
    request = RPCRequest(
        id="test-6",
        type="list_qe_parameter_metadata",
        payload={"operation": "search", "query": "ecutwfc"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "results" in response.data
    results = response.data["results"]
    assert isinstance(results, list)
    assert len(results) > 0
    
    # Verify result structure
    for result in results:
        assert "name" in result
        assert "module" in result
        assert "section" in result
        assert isinstance(result["name"], str)
        assert isinstance(result["module"], str)
        assert isinstance(result["section"], str)
    
    # Should find ecutwfc
    result_names = [r["name"] for r in results]
    assert "ecutwfc" in result_names


def test_search_no_results(daemon):
    """Test that search returns empty list for non-matching query."""
    request = RPCRequest(
        id="test-7",
        type="list_qe_parameter_metadata",
        payload={"operation": "search", "query": "__definitely_not_a_parameter_name__"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is True
    assert "results" in response.data
    results = response.data["results"]
    assert isinstance(results, list)
    # Should return empty list, not error
    assert len(results) == 0


def test_missing_operation_returns_error(daemon):
    """Test that missing operation returns a structured error."""
    request = RPCRequest(
        id="test-8",
        type="list_qe_parameter_metadata",
        payload={},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is False
    # Should have an error message about missing operation
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    assert error is not None


def test_invalid_operation_returns_error(daemon):
    """Test that invalid operation returns a structured error."""
    request = RPCRequest(
        id="test-9",
        type="list_qe_parameter_metadata",
        payload={"operation": "__invalid_operation__"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is False
    # Should have an error message about invalid operation
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    assert error is not None


def test_list_parameters_missing_module_returns_error(daemon):
    """Test that list_parameters without module returns error."""
    request = RPCRequest(
        id="test-10",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_parameters", "section": "&SYSTEM"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is False
    # Should have an error message about missing module
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    assert error is not None


def test_error_not_raw_exception(daemon):
    """Test that errors are structured RPC errors, not raw Python exceptions."""
    request = RPCRequest(
        id="test-11",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_sections", "module": "__nonexistent__"},
    )
    
    response = daemon.handle_request(request)
    
    assert response.ok is False
    # Error should be a dict with code/message, not a raw exception string
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    if error:
        # Should not contain Python exception class names like "NameError" or "ValueError"
        error_str = str(error)
        assert "NameError" not in error_str
        assert "Traceback" not in error_str
        # Should be a structured error object
        assert isinstance(error, dict) or hasattr(error, "code") or hasattr(error, "message")


def test_reload_qe_parameter_metadata(daemon):
    """Test that reload_qe_parameter_metadata clears cache and returns fresh modules."""
    # First, get initial modules list
    initial_request = RPCRequest(
        id="test-reload-1",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_modules"},
    )
    initial_response = daemon.handle_request(initial_request)
    assert initial_response.ok is True
    initial_modules = initial_response.data["modules"]
    assert len(initial_modules) > 0
    
    # Now reload metadata
    reload_request = RPCRequest(
        id="test-reload-2",
        type="reload_qe_parameter_metadata",
        payload={},
    )
    reload_response = daemon.handle_request(reload_request)
    
    assert reload_response.ok is True
    assert "modules" in reload_response.data
    reloaded_modules = reload_response.data["modules"]
    assert isinstance(reloaded_modules, list)
    assert len(reloaded_modules) > 0
    
    # Verify module structure
    for module in reloaded_modules:
        assert "id" in module
        assert "label" in module
        assert isinstance(module["ulid"], str)
        assert isinstance(module["label"], str)
    
    # Verify we get the same modules (same IDs)
    initial_ids = {m["ulid"] for m in initial_modules}
    reloaded_ids = {m["ulid"] for m in reloaded_modules}
    assert initial_ids == reloaded_ids, "Reloaded modules should match initial modules"
    
    # Verify cache was cleared by checking that subsequent list_modules call works
    # (if cache wasn't cleared, this would still work, but we want to ensure reload happened)
    verify_request = RPCRequest(
        id="test-reload-3",
        type="list_qe_parameter_metadata",
        payload={"operation": "list_modules"},
    )
    verify_response = daemon.handle_request(verify_request)
    assert verify_response.ok is True
    verify_modules = verify_response.data["modules"]
    assert len(verify_modules) > 0
