"""
Tests for QE parameter metadata via the generic engine parameter metadata RPC.

Tests the list_engine_parameter_metadata RPC endpoint (with engine_family=qe)
which powers the Engine Parameter Browser in the GUI.
QE-specific operations (list_sections) are tested via the internal helper.
"""

import pytest
from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.data.qe_metadata import list_supported_modules, safe_load_metadata


@pytest.fixture
def daemon():
    """Create a QVDaemon instance for testing."""
    return QVDaemon()


def _generic_request(id_, operation, **extra):
    """Build a generic engine parameter metadata RPC request for QE."""
    payload = {"engine_family": "qe", "operation": operation, **extra}
    return RPCRequest(id=id_, type="list_engine_parameter_metadata", payload=payload)


def test_list_modules_returns_all_modules(daemon):
    """Test that list_categories (→ list_modules) returns all supported QE modules."""
    request = _generic_request("test-1", "list_categories")

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
    """Test that list_categories returns modules in JSON insertion order (not sorted)."""
    # Get expected order from raw metadata
    raw_data = safe_load_metadata()
    expected_order = list(raw_data.get("modules", {}).keys())

    request = _generic_request("test-1b", "list_categories")

    response = daemon.handle_request(request)

    assert response.ok is True
    modules = response.data["modules"]
    actual_order = [m["ulid"] for m in modules]

    # Verify order matches JSON order (at least for first few modules)
    assert actual_order[:5] == expected_order[:5], \
        f"Module order should match JSON order. Expected: {expected_order[:5]}, Got: {actual_order[:5]}"


def test_list_sections_for_valid_module(daemon):
    """Test that list_sections returns sections for a valid module (QE-specific)."""
    request = _generic_request("test-3a", "list_sections", category="pw")
    response = daemon.handle_request(request)
    assert response.ok is True
    result = response.data

    assert "sections" in result
    sections = result["sections"]
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

    request = _generic_request("test-3b", "list_sections", category="pw")
    response = daemon.handle_request(request)
    assert response.ok is True
    result = response.data

    sections = result["sections"]

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
    request = _generic_request("test-3c", "list_sections", category="__nonexistent__")
    response = daemon.handle_request(request)
    assert response.ok is False


def test_list_parameters_for_valid_module_and_section(daemon):
    """Test that list_tags (→ list_parameters) returns parameters for a valid module/section."""
    request = _generic_request(
        "test-4", "list_tags",
        category="pw", section="&SYSTEM",
    )

    response = daemon.handle_request(request)

    assert response.ok is True
    assert "tags" in response.data
    parameters = response.data["tags"]
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

    # Should have common parameters like ecutwfc, ibrav
    param_names = [p["name"] for p in parameters]
    assert "ecutwfc" in param_names or "ibrav" in param_names


def test_list_parameters_for_card_section(daemon):
    """Test that list_tags returns card metadata for a card section."""
    request = _generic_request(
        "test-4b", "list_tags",
        category="pw", section="K_POINTS",
    )

    response = daemon.handle_request(request)

    assert response.ok is True
    assert "tags" in response.data
    parameters = response.data["tags"]
    assert isinstance(parameters, list)

    # If K_POINTS card metadata exists, verify structure
    if len(parameters) > 0:
        for param in parameters:
            assert "name" in param
            assert "module" in param
            assert "section" in param
            assert param["module"] == "pw"
            assert param["section"] == "K_POINTS" or param["section"] == "&K_POINTS"


def test_list_parameters_with_array_indexing(daemon):
    """Test that parameters with array indexing have indexing metadata (v2 schema)."""
    request = _generic_request(
        "test-5", "list_tags",
        category="pw", section="&SYSTEM",
    )

    response = daemon.handle_request(request)

    if not response.ok:
        pytest.skip("Could not load parameters (metadata may be missing)")

    parameters = response.data.get("tags", [])

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
    request = _generic_request("test-6", "search", query="ecutwfc")

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
    request = _generic_request(
        "test-7", "search",
        query="__definitely_not_a_parameter_name__",
    )

    response = daemon.handle_request(request)

    assert response.ok is True
    assert "results" in response.data
    results = response.data["results"]
    assert isinstance(results, list)
    assert len(results) == 0


def test_missing_operation_returns_error(daemon):
    """Test that missing operation returns a structured error."""
    request = RPCRequest(
        id="test-8",
        type="list_engine_parameter_metadata",
        payload={"engine_family": "qe"},
    )

    response = daemon.handle_request(request)

    assert response.ok is False
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    assert error is not None


def test_invalid_operation_returns_error(daemon):
    """Test that invalid operation returns a structured error."""
    request = _generic_request("test-9", "__invalid_operation__")

    response = daemon.handle_request(request)

    assert response.ok is False
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    assert error is not None


def test_list_parameters_without_section_returns_all(daemon):
    """Test that list_tags with category but no section returns ALL params in the module."""
    request = _generic_request("test-10a", "list_tags", category="pw")

    response = daemon.handle_request(request)

    assert response.ok is True
    assert "tags" in response.data
    tags = response.data["tags"]
    assert isinstance(tags, list)
    assert len(tags) > 0

    # Should contain params from multiple sections (flattened 2-level view)
    sections_seen = set()
    for tag in tags:
        assert "name" in tag
        assert "section" in tag
        assert "module" in tag
        assert tag["module"] == "pw"
        sections_seen.add(tag["section"])

    # pw module should have at least &CONTROL and &SYSTEM namelists
    assert len(sections_seen) > 1, f"Expected multiple sections, got: {sections_seen}"

    # Common params should be present
    names = [t["name"] for t in tags]
    assert "ecutwfc" in names or "ibrav" in names


def test_list_parameters_missing_category_returns_error(daemon):
    """Test that list_tags without category returns an error (no silent default)."""
    request = _generic_request("test-10", "list_tags", section="&SYSTEM")

    response = daemon.handle_request(request)

    # Should fail — category (module) is required, no silent default
    assert response.ok is False


def test_error_not_raw_exception(daemon):
    """Test that errors are structured RPC errors, not raw Python exceptions."""
    # Missing category (module) — should return a structured error
    request = RPCRequest(
        id="test-11",
        type="list_engine_parameter_metadata",
        payload={"engine_family": "qe", "operation": "list_tags"},
    )

    response = daemon.handle_request(request)

    assert response.ok is False
    error = getattr(response, "error", None) or (response.__dict__.get("error") if hasattr(response, "__dict__") else None)
    if error:
        error_str = str(error)
        assert "NameError" not in error_str
        assert "Traceback" not in error_str
        assert isinstance(error, dict) or hasattr(error, "code") or hasattr(error, "message")


def test_nonexistent_module_returns_empty_tags(daemon):
    """Test that list_tags for a nonexistent module returns empty tags (not an error)."""
    request = _generic_request("test-11b", "list_tags", category="__nonexistent__")

    response = daemon.handle_request(request)

    assert response.ok is True
    assert "tags" in response.data
    assert response.data["tags"] == []


def test_missing_engine_family_returns_error(daemon):
    """Test that missing engine_family returns error."""
    request = RPCRequest(
        id="test-12",
        type="list_engine_parameter_metadata",
        payload={"operation": "list_categories"},
    )

    response = daemon.handle_request(request)

    assert response.ok is False
