"""Contract tests for the demo store MCP tools.

Tests search_demos, get_demo_results, and load_demo MCP tools.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_search_demos(**kwargs):
    """Directly call the search_demos function (bypassing MCP transport)."""
    from quantumvitas.mcp.tools.demo_store import search_demos
    # @mcp.tool wraps the function in a FunctionTool; call .fn() for the raw function
    return search_demos.fn(**kwargs)


def _call_get_demo_results(demo_id: str, object_type: str = ""):
    from quantumvitas.mcp.tools.demo_store import get_demo_results
    return get_demo_results.fn(demo_id=demo_id, object_type=object_type)


def _call_load_demo(qv_project, demo_id: str, name: str = ""):
    from quantumvitas.mcp.tools.demo_store import load_demo
    return load_demo.fn(demo_id=demo_id, name=name)


def _is_ok(result: dict) -> bool:
    return result.get("status") == "success"


def _is_error(result: dict) -> bool:
    return result.get("status") == "error"


# ---------------------------------------------------------------------------
# search_demos — no-filter returns all
# ---------------------------------------------------------------------------

def test_search_demos_no_filters_returns_all():
    result = _call_search_demos()
    assert _is_ok(result), result
    data = result["data"]
    assert data["total"] >= 52, f"Expected >=52 demos, got {data['total']}"
    assert len(data["demos"]) == data["total"]


def test_search_demos_all_have_engine_field():
    result = _call_search_demos()
    for d in result["data"]["demos"]:
        assert "engine" in d, f"Demo {d.get('ulid')} missing engine field"
        assert d["engine"], f"Demo {d.get('ulid')} has empty engine"


# ---------------------------------------------------------------------------
# search_demos — engine filter
# ---------------------------------------------------------------------------

def test_search_demos_engine_filter_qe():
    result = _call_search_demos(engine="qe")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d["engine"] == "qe", f"Non-QE demo in results: {d.get('ulid')}"


def test_search_demos_engine_filter_vasp():
    result = _call_search_demos(engine="vasp")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) >= 5
    for d in demos:
        assert d["engine"] == "vasp"


# ---------------------------------------------------------------------------
# search_demos — difficulty filter
# ---------------------------------------------------------------------------

def test_search_demos_difficulty_filter_beginner():
    result = _call_search_demos(difficulty="beginner")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d.get("difficulty") == "beginner"


# ---------------------------------------------------------------------------
# search_demos — text query
# ---------------------------------------------------------------------------

def test_search_demos_query_silicon():
    result = _call_search_demos(query="silicon")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    # All results should have 'silicon' somewhere in title/subtitle/desc/tags
    for d in demos:
        combined = " ".join([
            (d.get("title") or ""),
            (d.get("subtitle") or ""),
            (d.get("description") or ""),
            (d.get("name") or ""),
            " ".join(d.get("tags", [])),
        ]).lower()
        assert "silicon" in combined or "si" in combined.split(), \
            f"Demo {d.get('ulid')} matched 'silicon' but text doesn't contain it: {combined[:100]}"


def test_search_demos_query_no_results():
    result = _call_search_demos(query="xyznonexistent12345")
    assert _is_ok(result)
    assert result["data"]["total"] == 0
    assert "no demos matched" in (result.get("context_hint") or "").lower()


# ---------------------------------------------------------------------------
# search_demos — new filters (Wave 2)
# ---------------------------------------------------------------------------

def test_search_demos_system_class_filter_crystal():
    result = _call_search_demos(system_class="crystal")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d.get("system_class") == "crystal", \
            f"Demo {d.get('ulid')} has system_class={d.get('system_class')}"


def test_search_demos_system_class_filter_molecule():
    result = _call_search_demos(system_class="molecule")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d.get("system_class") == "molecule"


def test_search_demos_method_filter_pbe():
    result = _call_search_demos(method="pbe")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert "pbe" in (d.get("method") or "").lower(), \
            f"Demo {d.get('ulid')} has method={d.get('method')}"


def test_search_demos_property_of_interest_filter_band_structure():
    result = _call_search_demos(property_of_interest="band_structure")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d.get("property_of_interest") == "band_structure"


# ---------------------------------------------------------------------------
# search_demos — new fields returned (Wave 2)
# ---------------------------------------------------------------------------

def test_search_demos_returns_new_enriched_fields():
    result = _call_search_demos(engine="qe", difficulty="beginner")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0

    for d in demos:
        uid = d.get("ulid", "?")
        # All new fields should be present
        assert "system_class" in d, f"{uid}: missing system_class"
        assert "method" in d, f"{uid}: missing method"
        assert "property_of_interest" in d, f"{uid}: missing property_of_interest"
        assert "spin_treatment" in d, f"{uid}: missing spin_treatment"
        assert "estimated_runtime_s" in d, f"{uid}: missing estimated_runtime_s"
        assert "n_steps" in d, f"{uid}: missing n_steps"
        assert "step_summary" in d, f"{uid}: missing step_summary"
        assert "available_analysis" in d, f"{uid}: missing available_analysis"
        assert "multi_engine" in d, f"{uid}: missing multi_engine"
        assert "engines_used" in d, f"{uid}: missing engines_used"


def test_search_demos_estimated_runtime_s_is_numeric():
    result = _call_search_demos(engine="qe")
    for d in result["data"]["demos"]:
        rt = d.get("estimated_runtime_s")
        if rt is not None:
            assert isinstance(rt, (int, float)), \
                f"estimated_runtime_s should be numeric, got {type(rt)} for {d.get('ulid')}"


def test_search_demos_available_analysis_is_list():
    result = _call_search_demos()
    for d in result["data"]["demos"]:
        aa = d.get("available_analysis")
        assert isinstance(aa, list), \
            f"available_analysis should be list, got {type(aa)} for {d.get('ulid')}"


# ---------------------------------------------------------------------------
# search_demos — combined filters
# ---------------------------------------------------------------------------

def test_search_demos_combined_engine_and_system_class():
    result = _call_search_demos(engine="orca", system_class="molecule")
    assert _is_ok(result)
    demos = result["data"]["demos"]
    assert len(demos) > 0
    for d in demos:
        assert d["engine"] == "orca"
        assert d.get("system_class") == "molecule"


# ---------------------------------------------------------------------------
# get_demo_results — list types
# ---------------------------------------------------------------------------

def test_get_demo_results_no_type_lists_available():
    result = _call_get_demo_results("qe_si_scf")
    assert _is_ok(result), result
    data = result["data"]
    assert "available_types" in data
    assert "convergence" in data["available_types"]


def test_get_demo_results_invalid_demo_id():
    result = _call_get_demo_results("nonexistent_demo_xyz")
    assert _is_error(result)
    assert result["error_type"] == "no_ref_pack"


def test_get_demo_results_type_not_found():
    result = _call_get_demo_results("qe_si_scf", object_type="nonexistent_type")
    assert _is_error(result)
    assert result["error_type"] == "type_not_found"


# ---------------------------------------------------------------------------
# get_demo_results — compact scalar summary (not raw arrays)
# ---------------------------------------------------------------------------

def test_get_demo_results_convergence_is_compact():
    result = _call_get_demo_results("qe_si_scf", object_type="convergence")
    assert _is_ok(result), result
    data = result["data"]
    assert "summary" in data
    summary = data["summary"]

    # Should have scalar fields
    assert "converged" in summary
    assert "n_scf_steps" in summary
    assert "final_energy_eV" in summary

    # Should NOT contain raw array data
    assert "data" not in data, "Full bundle data should not be returned"
    assert "arrays" not in data, "Raw arrays should not be returned"
    assert "series" not in data, "Raw series should not be returned"

    # converged should be a boolean (not an array)
    if summary["converged"] is not None:
        assert isinstance(summary["converged"], bool)


def test_get_demo_results_convergence_final_energy_is_float():
    result = _call_get_demo_results("qe_si_scf", object_type="convergence")
    assert _is_ok(result)
    summary = result["data"]["summary"]
    if summary.get("final_energy_eV") is not None:
        assert isinstance(summary["final_energy_eV"], (int, float))


def test_get_demo_results_bands_summary():
    result = _call_get_demo_results("qe_si_bands_alt", object_type="bands")
    assert _is_ok(result), result
    summary = result["data"]["summary"]
    assert "n_kpoints" in summary
    assert "n_bands" in summary
    assert "high_symm_labels" in summary
    assert isinstance(summary["high_symm_labels"], list)
    # No raw eigenvalue arrays
    assert "eigenvalues" not in result["data"]


def test_get_demo_results_dos_summary():
    result = _call_get_demo_results("qe_si_dos_alt", object_type="dos")
    assert _is_ok(result), result
    summary = result["data"]["summary"]
    assert "fermi_energy_eV" in summary
    assert "n_energy_points" in summary
    assert "n_series" in summary


def test_get_demo_results_trajectory_summary():
    result = _call_get_demo_results("siesta_si_relax", object_type="trajectory")
    assert _is_ok(result), result
    summary = result["data"]["summary"]
    assert "n_frames" in summary
    assert "trajectory_type" in summary
    assert summary["n_frames"] is not None
    assert summary["n_frames"] > 1, "Trajectory should have >1 frame"
    # Energy should be extracted from series fallback (not arrays)
    assert summary["initial_energy_eV"] is not None, \
        "Trajectory energy should not be None (series fallback)"
    assert summary["final_energy_eV"] is not None, \
        "Trajectory final energy should not be None (series fallback)"
    assert isinstance(summary["initial_energy_eV"], (int, float))
    assert isinstance(summary["final_energy_eV"], (int, float))


def test_get_demo_results_returns_engine_field():
    result = _call_get_demo_results("qe_si_scf", object_type="convergence")
    assert _is_ok(result)
    assert "engine" in result["data"]
    assert result["data"]["engine"] == "qe"


# ---------------------------------------------------------------------------
# get_demo_results — all 52 have manifests
# ---------------------------------------------------------------------------

def test_get_demo_results_all_demos_have_ref_packs():
    """All 52 demos should have ref packs with at least one analysis type."""
    from quantumvitas.demo_store.ref_packs import list_all_ref_packs, list_ref_pack_types

    ref_packs = list_all_ref_packs()
    assert len(ref_packs) >= 52, f"Expected >=52 ref packs, got {len(ref_packs)}"

    for demo_id in ref_packs:
        types = list_ref_pack_types(demo_id)
        assert len(types) > 0, f"Demo {demo_id} has empty ref pack"


# ---------------------------------------------------------------------------
# load_demo
# ---------------------------------------------------------------------------

def test_load_demo_valid_id_creates_calc(qv_project):
    result = _call_load_demo(qv_project, "qe_si_scf")
    assert _is_ok(result), result
    data = result["data"]
    assert "calc_ulid" in data
    assert data["calc_ulid"]


def test_load_demo_structure_ulid_in_result(qv_project):
    result = _call_load_demo(qv_project, "qe_si_scf")
    assert _is_ok(result), result
    data = result["data"]
    assert "structure_ulid" in data, "structure_ulid should be in load_demo result"
    assert data["structure_ulid"], "structure_ulid should not be empty"


def test_load_demo_context_hint_mentions_structure(qv_project):
    result = _call_load_demo(qv_project, "qe_si_scf")
    assert _is_ok(result), result
    hint = result.get("context_hint", "")
    assert "structure" in hint.lower(), f"context_hint should mention structure: {hint}"
    assert "do not need to import" in hint.lower(), \
        f"context_hint should say user doesn't need to import separately: {hint}"


def test_load_demo_invalid_id_error(qv_project):
    result = _call_load_demo(qv_project, "nonexistent_demo_xyz")
    assert _is_error(result)
    assert result["error_type"] == "demo_not_found"


def test_load_demo_requires_project():
    """load_demo should return error if no project is active."""
    from unittest.mock import patch
    from quantumvitas.mcp.project import ProjectNotFoundError

    with patch(
        "quantumvitas.mcp.project.get_service",
        side_effect=ProjectNotFoundError("No project"),
    ):
        result = _call_load_demo(None, "qe_si_scf")
    assert _is_error(result)
    assert result["error_type"] == "no_project"


def test_load_demo_context_hint_mentions_calc_ulid(qv_project):
    result = _call_load_demo(qv_project, "qe_si_scf")
    assert _is_ok(result)
    calc_ulid = result["data"]["calc_ulid"]
    hint = result.get("context_hint", "")
    assert calc_ulid in hint, f"context_hint should contain calc_ulid {calc_ulid}"


# ---------------------------------------------------------------------------
# Integration: search → pick → get_results → load
# ---------------------------------------------------------------------------

def test_full_demo_flow_search_to_load(qv_project):
    """End-to-end: search demos, pick one, preview results, load it."""
    # 1. Search
    search_result = _call_search_demos(engine="qe", difficulty="beginner")
    assert _is_ok(search_result)
    demos = search_result["data"]["demos"]
    assert len(demos) > 0

    # 2. Pick first one with a ref pack
    chosen = next((d for d in demos if d.get("has_ref_pack")), None)
    assert chosen is not None, "Expected at least one beginner QE demo with ref pack"
    demo_id = chosen["ulid"]

    # 3. Preview results
    results_result = _call_get_demo_results(demo_id)
    assert _is_ok(results_result)
    types = results_result["data"]["available_types"]
    assert len(types) > 0

    # 4. Load into project
    load_result = _call_load_demo(qv_project, demo_id)
    assert _is_ok(load_result), load_result
    assert "calc_ulid" in load_result["data"]
    assert "structure_ulid" in load_result["data"]
