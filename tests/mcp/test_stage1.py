"""Stage 1 MCP discovery tools tests.

Tests the four read-only discovery tools: list_engines, list_workflows,
get_presets, and search_parameters. All tests call .fn() directly on the
@mcp.tool-decorated functions (no subprocess needed).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def test_make_error_shape():
    from quantumvitas.mcp.envelope import make_error

    result = make_error("test_error", "something broke")
    assert result["status"] == "error"
    assert result["error_type"] == "test_error"
    assert result["message"] == "something broke"
    assert result["suggestions"] == []


# ---------------------------------------------------------------------------
# list_engines
# ---------------------------------------------------------------------------

def test_list_engines_returns_all_15():
    from quantumvitas.mcp.tools.list_engines import list_engines

    result = list_engines.fn()
    assert result["status"] == "success"
    data = result["data"]
    assert data["total"] == 15
    assert len(data["engines"]) == 15


def test_list_engines_entry_shape():
    from quantumvitas.mcp.tools.list_engines import list_engines

    result = list_engines.fn()
    engines = result["data"]["engines"]
    # Find VASP entry
    vasp = next(e for e in engines if e["engine"] == "vasp")
    assert vasp["display_name"] == "VASP"
    assert isinstance(vasp["supported_gen_steps"], list)
    assert "scf" in vasp["supported_gen_steps"]
    assert isinstance(vasp["capabilities"], list)
    assert vasp["parameter_count"] > 0
    assert vasp["syntax_family"] != "unknown"
    assert vasp["installed"] is True


def test_list_engines_qe_parameter_count():
    from quantumvitas.mcp.tools.list_engines import list_engines

    result = list_engines.fn()
    qe = next(e for e in result["data"]["engines"] if e["engine"] == "qe")
    # QE has hundreds of params across modules (pw alone has ~292)
    assert qe["parameter_count"] > 200


# ---------------------------------------------------------------------------
# list_workflows
# ---------------------------------------------------------------------------

def test_list_workflows_qe_has_scf():
    from quantumvitas.mcp.tools.list_workflows import list_workflows

    result = list_workflows.fn(engine="qe")
    assert result["status"] == "success"
    data = result["data"]
    assert data["engine"] == "qe"
    ids = [w["workflow_id"] for w in data["workflows"]]
    assert "scf" in ids


def test_list_workflows_unknown_engine():
    from quantumvitas.mcp.tools.list_workflows import list_workflows

    result = list_workflows.fn(engine="nonexistent")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"
    assert len(result["suggestions"]) > 0


def test_list_workflows_spec_steps_materialized():
    from quantumvitas.mcp.tools.list_workflows import list_workflows

    result = list_workflows.fn(engine="vasp")
    data = result["data"]
    scf_wf = next(w for w in data["workflows"] if w["workflow_id"] == "scf")
    assert scf_wf["spec_steps"] == ["vasp_scf"]


# ---------------------------------------------------------------------------
# get_presets
# ---------------------------------------------------------------------------

def test_get_presets_qe_scf_has_dimensions():
    from quantumvitas.mcp.tools.get_presets import get_presets

    result = get_presets.fn(engine="qe", workflow="scf")
    assert result["status"] == "success"
    data = result["data"]
    assert data["presets_available"] is True
    dim_names = [d["name"] for d in data["dimensions"]]
    assert "precision" in dim_names
    assert "magnetism" in dim_names


def test_get_presets_unknown_workflow():
    from quantumvitas.mcp.tools.get_presets import get_presets

    result = get_presets.fn(engine="qe", workflow="nonexistent")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_workflow"


def test_get_presets_dimension_has_options():
    from quantumvitas.mcp.tools.get_presets import get_presets

    # Verify that returned dimensions have option entries
    result = get_presets.fn(engine="qe", workflow="scf")
    assert result["status"] == "success"
    for dim in result["data"]["dimensions"]:
        assert len(dim["options"]) > 0
        assert "value" in dim["options"][0]
        assert "label" in dim["options"][0]


# ---------------------------------------------------------------------------
# search_parameters
# ---------------------------------------------------------------------------

def test_search_parameters_energy_cutoff():
    from quantumvitas.mcp.tools.search_parameters import search_parameters

    result = search_parameters.fn(query="energy cutoff")
    assert result["status"] == "success"
    data = result["data"]
    assert data["total_results"] > 0
    # ENCUT (VASP) or ecutwfc (QE) should appear
    tag_names = [r["tag_name"] for r in data["results"]]
    assert any("ENCUT" in t or "ecut" in t.lower() for t in tag_names)


def test_search_parameters_filter_engine():
    from quantumvitas.mcp.tools.search_parameters import search_parameters

    result = search_parameters.fn(query="energy cutoff", engine="vasp")
    assert result["status"] == "success"
    for r in result["data"]["results"]:
        assert r["engine"] == "vasp"


def test_search_parameters_empty_query():
    from quantumvitas.mcp.tools.search_parameters import search_parameters

    result = search_parameters.fn(query="")
    assert result["status"] == "success"
    assert result["data"]["total_results"] == 0


def test_search_parameters_result_shape():
    from quantumvitas.mcp.tools.search_parameters import search_parameters

    result = search_parameters.fn(query="smearing")
    data = result["data"]
    if data["total_results"] > 0:
        r = data["results"][0]
        assert "engine" in r
        assert "tag_name" in r
        assert "type" in r
        assert "category" in r
        assert "description" in r
        assert "relevance_score" in r
        assert r["relevance_score"] > 0
