"""Stage 5 MCP integration tests — end-to-end scenario validation.

Tests that the 15-tool MCP server works as a coherent system by running
scripted scenarios that mimic real agent behavior.

- Scenario A: preset path (real QE, ~6 tool calls)
- Scenario B: manual path (real QE, ~8 tool calls)
- Knowledge consultation (no QE needed)
- Context hint chain (no QE needed)
- Error handling (no QE needed)

Shared fixtures (qv_project, qe_available, qe_project_with_si) are in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.api import QVService


def _setup_si_scf_calc(project_root: Path) -> str:
    """Create a QE SCF calc with species_map and ecutwfc=20.0. Returns calc_ulid."""
    from quantumvitas.mcp.tools.create_calculation import create_calculation
    from quantumvitas.mcp.tools.set_parameters import set_parameters

    svc = QVService(project_root)

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="si",
    )
    assert result["status"] == "success", f"create_calculation failed: {result}"
    calc_ulid = result["data"]["calc_ulid"]

    svc.calculation.update_species_map(
        calc_ulid,
        {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
    )

    set_result = set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"ecutwfc": 20.0}},
        step=0,
    )
    assert set_result["status"] == "success", f"set_parameters failed: {set_result}"

    return calc_ulid


# ===========================================================================
# Scenario A: Preset path (real QE)
# ===========================================================================


class TestScenarioAPresetPath:
    """User: "Calculate Si SCF with QE, standard settings."

    Mimics the agent following the discovery -> configure -> run -> results
    chain using presets and quick_run.
    """

    def test_scenario_a_full_journey(self, qe_project_with_si):
        from quantumvitas.mcp.tools.list_workflows import list_workflows
        from quantumvitas.mcp.tools.get_presets import get_presets
        from quantumvitas.mcp.tools.preview_compilation import preview_compilation
        from quantumvitas.mcp.tools.run_calculation import run_calculation
        from quantumvitas.mcp.tools.get_results_summary import get_results_summary

        svc = QVService(qe_project_with_si)

        # 1. Discovery — list workflows for QE
        wf = list_workflows.fn(engine="qe")
        assert wf["status"] == "success"
        wf_ids = [w["workflow_id"] for w in wf["data"]["workflows"]]
        assert "scf" in wf_ids

        # 2. Check presets
        presets = get_presets.fn(engine="qe", workflow="scf")
        assert presets["status"] == "success"
        assert presets["data"]["presets_available"] is True

        # 3. Preview compilation (stateless)
        preview = preview_compilation.fn(
            engine="qe", workflow="scf",
            presets={"precision": "LOW"},
        )
        assert preview["status"] == "success"
        assert "steps" in preview["data"]
        assert len(preview["data"]["steps"]) >= 1

        # 4. Create + configure + run (manual path since quick_run
        #    can't set species_map)
        calc_ulid = _setup_si_scf_calc(qe_project_with_si)

        run_result = run_calculation.fn(calc_ulid=calc_ulid)
        assert run_result["status"] == "success", f"run failed: {run_result}"
        assert run_result["data"]["status"] == "completed"

        # 5. Get results
        summary = get_results_summary.fn(calc_ulid=calc_ulid)
        assert summary["status"] == "success"
        data = summary["data"]
        assert data["converged"] is True
        assert data["total_energy_eV"] is not None
        assert data["total_energy_eV"] < 0  # physically reasonable

        # 6. Context hints chain correctly
        assert "get_results_summary" in run_result.get("context_hint", "")
        assert calc_ulid in run_result.get("context_hint", "")


# ===========================================================================
# Scenario B: Manual path (real QE)
# ===========================================================================


class TestScenarioBManualPath:
    """User: "Run Si SCF with QE, I want to set parameters myself."

    Mimics the agent discovering parameters, consulting knowledge, then
    manually configuring and running.
    """

    def test_scenario_b_full_journey(self, qe_project_with_si):
        from quantumvitas.mcp.tools.search_parameters import search_parameters
        from quantumvitas.mcp.tools.search_knowledge import search_knowledge
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.set_parameters import set_parameters
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation
        from quantumvitas.mcp.tools.run_calculation import run_calculation
        from quantumvitas.mcp.tools.get_results_summary import get_results_summary

        svc = QVService(qe_project_with_si)

        # 1. Search for relevant parameters
        params = search_parameters.fn(query="cutoff energy", engine="qe")
        assert params["status"] == "success"
        tag_names = [r["tag_name"].lower() for r in params["data"]["results"]]
        assert any("ecutwfc" in t for t in tag_names)

        # 2. Search for convergence threshold
        conv = search_parameters.fn(query="convergence threshold", engine="qe")
        assert conv["status"] == "success"
        assert len(conv["data"]["results"]) > 0

        # 3. Check knowledge for best practices
        knowledge = search_knowledge.fn(query="SCF convergence", engine="qe")
        assert knowledge["status"] == "success"
        assert knowledge["data"]["total_results"] > 0

        # 4. Create calculation
        calc = create_calculation.fn(
            engine="qe", workflow="scf",
            structure_selector="si",
            name="Si_scf_scenario_b",
        )
        assert calc["status"] == "success"
        calc_ulid = calc["data"]["calc_ulid"]

        # Verify hint includes calc_ulid
        assert calc_ulid in calc.get("context_hint", "")

        # Set species_map (engine-specific, not via MCP tool)
        svc.calculation.update_species_map(
            calc_ulid,
            {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
        )

        # 5. Set parameters manually
        set_result = set_parameters.fn(
            calc_ulid=calc_ulid, step=0,
            params={"SYSTEM": {"ecutwfc": 20.0}, "ELECTRONS": {"conv_thr": 1.0e-6}},
        )
        assert set_result["status"] == "success"
        assert calc_ulid in set_result.get("context_hint", "")

        # 6. Inspect current state
        inspection = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert inspection["status"] == "success"
        assert inspection["data"]["n_steps"] >= 1
        assert calc_ulid in inspection.get("context_hint", "")

        # 7. Run
        run_result = run_calculation.fn(calc_ulid=calc_ulid)
        assert run_result["status"] == "success", f"run failed: {run_result}"
        assert run_result["data"]["status"] == "completed"

        # 8. Get results
        summary = get_results_summary.fn(calc_ulid=calc_ulid)
        assert summary["status"] == "success"
        assert summary["data"]["converged"] is True
        assert summary["data"]["total_energy_eV"] < 0


# ===========================================================================
# Knowledge consultation (no QE needed)
# ===========================================================================


class TestKnowledgeConsultation:
    """Agent consults knowledge base before setting up calculation."""

    @pytest.fixture(autouse=True)
    def _patch_knowledge(self, tmp_path, monkeypatch):
        """Patch the search_knowledge tool to use a temp DB."""
        from quantumvitas.mcp.knowledge.store import KnowledgeStore
        from quantumvitas.mcp.knowledge.build_builtin import build_builtin_db
        import quantumvitas.mcp.tools.search_knowledge as mod

        db_path = tmp_path / "knowledge" / "test.db"
        build_builtin_db(output_path=db_path)
        s = KnowledgeStore(db_path=db_path)
        monkeypatch.setattr(mod, "_store", s)
        yield
        s.close()
        monkeypatch.setattr(mod, "_store", None)

    def test_knowledge_before_configuration(self):
        """search_knowledge for metal smearing tips returns actionable results."""
        from quantumvitas.mcp.tools.search_knowledge import search_knowledge

        tips = search_knowledge.fn(query="smearing metals")
        assert tips["status"] == "success"
        assert len(tips["data"]["results"]) > 0
        for r in tips["data"]["results"]:
            assert len(r["content"]) > 20

    def test_knowledge_hint_guides_to_parameters(self):
        """Knowledge results hint at using insights for parameter choices."""
        from quantumvitas.mcp.tools.search_knowledge import search_knowledge

        result = search_knowledge.fn(query="SCF convergence")
        assert result["status"] == "success"
        hint = result.get("context_hint", "")
        assert "set_parameters" in hint or "apply_preset" in hint


# ===========================================================================
# Context hint chain (no QE needed)
# ===========================================================================


class TestContextHintChain:
    """Verify context_hints form a logical chain guiding the agent."""

    def test_discovery_chain(self, qv_project):
        """list_engines -> list_workflows -> get_presets hints chain correctly."""
        from quantumvitas.mcp.tools.list_engines import list_engines
        from quantumvitas.mcp.tools.list_workflows import list_workflows
        from quantumvitas.mcp.tools.get_presets import get_presets

        # list_engines -> should mention list_workflows
        engines = list_engines.fn()
        assert "list_workflows" in engines.get("context_hint", "")

        # list_workflows -> should mention get_presets
        workflows = list_workflows.fn(engine="qe")
        assert "get_presets" in workflows.get("context_hint", "")

        # get_presets (available) -> should mention preview_compilation or quick_run
        presets = get_presets.fn(engine="qe", workflow="scf")
        hint = presets.get("context_hint", "")
        assert "preview_compilation" in hint or "quick_run" in hint

    def test_configuration_chain(self, qv_project):
        """create_calculation -> set_parameters -> inspect -> run hints chain."""
        from quantumvitas.mcp.tools.create_calculation import create_calculation
        from quantumvitas.mcp.tools.set_parameters import set_parameters
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        # Create
        result = create_calculation.fn(
            engine="qe", workflow="scf", structure_selector="silicon",
        )
        assert result["status"] == "success"
        calc_ulid = result["data"]["calc_ulid"]
        hint = result.get("context_hint", "")
        assert "set_parameters" in hint or "apply_preset" in hint
        assert calc_ulid in hint

        # Set parameters -> should mention inspect or run with calc_ulid
        set_result = set_parameters.fn(
            calc_ulid=calc_ulid,
            params={"SYSTEM": {"ecutwfc": 30.0}},
        )
        assert set_result["status"] == "success"
        hint = set_result.get("context_hint", "")
        assert "inspect_calculation" in hint or "run_calculation" in hint
        assert calc_ulid in hint

        # Inspect -> should mention set_parameters or run_calculation with calc_ulid
        inspect_result = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert inspect_result["status"] == "success"
        hint = inspect_result.get("context_hint", "")
        assert "run_calculation" in hint
        assert calc_ulid in hint


# ===========================================================================
# Error handling (no QE needed)
# ===========================================================================


class TestErrorHandlingGraceful:
    """Bad inputs produce structured errors, not stack traces."""

    def test_invalid_engine(self, qv_project):
        from quantumvitas.mcp.tools.list_workflows import list_workflows

        result = list_workflows.fn(engine="nonexistent_engine")
        assert result["status"] == "error"
        assert "error_type" in result

    def test_invalid_calc_ulid_run(self, qv_project):
        from quantumvitas.mcp.tools.run_calculation import run_calculation

        result = run_calculation.fn(calc_ulid="NONEXISTENT")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_invalid_calc_ulid_results(self, qv_project):
        from quantumvitas.mcp.tools.get_results_summary import get_results_summary

        result = get_results_summary.fn(calc_ulid="NONEXISTENT")
        assert result["status"] == "error"

    def test_invalid_calc_ulid_status(self, qv_project):
        from quantumvitas.mcp.tools.get_status import get_status

        result = get_status.fn(calc_ulid="NONEXISTENT")
        assert result["status"] == "error"

    def test_invalid_calc_ulid_inspect(self, qv_project):
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        result = inspect_calculation.fn(calc_ulid="NONEXISTENT")
        assert result["status"] == "error"

    def test_invalid_calc_ulid_set_params(self, qv_project):
        from quantumvitas.mcp.tools.set_parameters import set_parameters

        result = set_parameters.fn(calc_ulid="NONEXISTENT", params={"SYSTEM": {"ecutwfc": 30}})
        assert result["status"] == "error"

    def test_invalid_calc_ulid_apply_preset(self, qv_project):
        from quantumvitas.mcp.tools.apply_preset import apply_preset

        result = apply_preset.fn(calc_ulid="NONEXISTENT", presets={"precision": "LOW"})
        assert result["status"] == "error"
