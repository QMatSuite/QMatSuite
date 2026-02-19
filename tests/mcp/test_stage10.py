"""Stage 10 MCP tests — demo store (search, preview results, load).

Tests for:
- search_demos tool (catalog browsing, filtering)
- get_demo_results tool (ref pack preview)
- load_demo tool (load demo into current project, ALL engines)
- Integration: search → load → inspect

Shared fixtures (qv_project, etc.) are in conftest.py.
"""

from __future__ import annotations

import pytest

from quantumvitas.api import QVService


# ---------------------------------------------------------------------------
# Helper: collect all demo IDs from the resource directory
# ---------------------------------------------------------------------------

def _all_demo_ids() -> list[str]:
    """Return sorted list of every demo ID in resources/demo_projects/."""
    from quantumvitas.core.resources import get_resources_dir

    demo_dir = get_resources_dir() / "demo_projects"
    if not demo_dir.exists():
        return []
    return sorted(p.stem for p in demo_dir.glob("*.yml"))


ALL_DEMO_IDS = _all_demo_ids()


# ===========================================================================
# search_demos tests (no project needed)
# ===========================================================================


class TestSearchDemos:
    """Tests for the search_demos tool — catalog discovery."""

    def test_search_all_returns_demos(self):
        """No filters → returns all demos."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn()
        assert result["status"] == "success"
        demos = result["data"]["demos"]
        assert len(demos) > 0
        assert result["data"]["total"] == len(demos)
        # Each demo should have required fields
        for d in demos:
            assert "ulid" in d
            assert "title" in d
            assert "tags" in d
            assert "has_ref_pack" in d
            assert "engine" in d

    def test_search_by_engine(self):
        """engine='qe' → only QE demos."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(engine="qe")
        assert result["status"] == "success"
        demos = result["data"]["demos"]
        assert len(demos) > 0
        for d in demos:
            assert d["engine"] == "qe", f"Expected qe, got {d['engine']} for {d['ulid']}"

    def test_search_by_tag(self):
        """tag='scf' → only demos tagged 'scf'."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(tag="scf")
        assert result["status"] == "success"
        demos = result["data"]["demos"]
        assert len(demos) > 0
        for d in demos:
            tags_lower = [t.lower() for t in d["tags"]]
            assert "scf" in tags_lower

    def test_search_by_difficulty(self):
        """difficulty='beginner' → only beginner demos."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(difficulty="beginner")
        assert result["status"] == "success"
        demos = result["data"]["demos"]
        assert len(demos) > 0
        for d in demos:
            assert (d.get("difficulty") or "").lower() == "beginner"

    def test_search_by_query(self):
        """query='Si' → matches title/description/name containing 'Si'."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(query="Si")
        assert result["status"] == "success"
        demos = result["data"]["demos"]
        assert len(demos) > 0

    def test_search_no_results(self):
        """engine='nonexistent' → empty list."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(engine="nonexistent_engine_xyz")
        assert result["status"] == "success"
        assert result["data"]["total"] == 0
        assert result["data"]["demos"] == []

    def test_search_combined_filters(self):
        """engine + tag combined → AND logic."""
        from quantumvitas.mcp.tools.demo_store import search_demos

        result = search_demos.fn(engine="qe", tag="scf")
        assert result["status"] == "success"
        for d in result["data"]["demos"]:
            assert d["engine"] == "qe"
            assert "scf" in [t.lower() for t in d["tags"]]


# ===========================================================================
# get_demo_results tests (no project needed)
# ===========================================================================


class TestGetDemoResults:
    """Tests for the get_demo_results tool — ref pack preview."""

    def _find_demo_with_ref_pack(self):
        """Find a demo that has a ref pack."""
        from quantumvitas.demo_store.ref_packs import list_all_ref_packs

        packs = list_all_ref_packs()
        if not packs:
            pytest.skip("No ref packs available")
        return packs[0]

    def test_list_available_types(self):
        """object_type='' → returns available types list."""
        demo_id = self._find_demo_with_ref_pack()
        from quantumvitas.mcp.tools.demo_store import get_demo_results

        result = get_demo_results.fn(demo_id=demo_id)
        assert result["status"] == "success"
        assert "available_types" in result["data"]
        assert "manifest" in result["data"]
        assert len(result["data"]["available_types"]) > 0

    def test_get_specific_result(self):
        """Load a specific object_type from a ref pack."""
        demo_id = self._find_demo_with_ref_pack()
        from quantumvitas.demo_store.ref_packs import list_ref_pack_types
        from quantumvitas.mcp.tools.demo_store import get_demo_results

        types = list_ref_pack_types(demo_id)
        assert len(types) > 0
        result = get_demo_results.fn(demo_id=demo_id, object_type=types[0])
        assert result["status"] == "success"
        assert result["data"]["object_type"] == types[0]
        assert "data" in result["data"]

    def test_invalid_demo_id(self):
        """Nonexistent demo → error."""
        from quantumvitas.mcp.tools.demo_store import get_demo_results

        result = get_demo_results.fn(demo_id="nonexistent_demo_xyz")
        assert result["status"] == "error"
        assert result["error_type"] == "no_ref_pack"

    def test_invalid_object_type(self):
        """Valid demo but invalid object_type → error."""
        demo_id = self._find_demo_with_ref_pack()
        from quantumvitas.mcp.tools.demo_store import get_demo_results

        result = get_demo_results.fn(demo_id=demo_id, object_type="nonexistent_type")
        assert result["status"] == "error"
        assert result["error_type"] == "type_not_found"


# ===========================================================================
# load_demo tests — parametrised across ALL demo snapshots
# ===========================================================================


class TestLoadDemoAllEngines:
    """Load every demo into a project and verify structure + steps.

    This is the exhaustive correctness test: every engine-specific parameter
    nesting must survive the direct-write path (same as create_demo_project).
    """

    @pytest.mark.parametrize("demo_id", ALL_DEMO_IDS)
    def test_load_demo_succeeds(self, demo_id, tmp_path, monkeypatch):
        """load_demo(demo_id) → success for every demo snapshot."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        # Fresh project per demo (isolation)
        project_root = QVService.init_project(tmp_path / demo_id)
        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        import quantumvitas.drivers  # noqa: F401

        result = load_demo.fn(demo_id=demo_id)
        assert result["status"] == "success", (
            f"load_demo failed for {demo_id}: {result.get('message', result)}"
        )
        data = result["data"]
        assert data["calc_ulid"], f"No calc_ulid for {demo_id}"
        assert data["demo_id"] == demo_id
        assert data["engine"], f"No engine for {demo_id}"

    @pytest.mark.parametrize("demo_id", ALL_DEMO_IDS)
    def test_load_demo_steps_match_snapshot(self, demo_id, tmp_path, monkeypatch):
        """Loaded demo has same number of steps as snapshot YAML."""
        import yaml
        from quantumvitas.core.resources import get_resources_dir
        from quantumvitas.mcp.tools.demo_store import load_demo

        # Load snapshot to get expected step count
        demo_path = get_resources_dir() / "demo_projects" / f"{demo_id}.yml"
        with open(demo_path) as f:
            snapshot = yaml.safe_load(f)
        expected_steps = len(snapshot["calculations"][0].get("steps", []))

        # Fresh project
        project_root = QVService.init_project(tmp_path / demo_id)
        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        import quantumvitas.drivers  # noqa: F401

        result = load_demo.fn(demo_id=demo_id)
        assert result["status"] == "success", (
            f"load_demo failed for {demo_id}: {result.get('message', result)}"
        )
        actual_steps = len(result["data"]["steps"])
        assert actual_steps == expected_steps, (
            f"{demo_id}: expected {expected_steps} steps, got {actual_steps}"
        )

    @pytest.mark.parametrize("demo_id", ALL_DEMO_IDS)
    def test_load_demo_step_yaml_has_parameters(self, demo_id, tmp_path, monkeypatch):
        """Each step YAML file written to disk has the demo's parameters."""
        import yaml as _yaml
        from quantumvitas.core.resources import get_resources_dir
        from quantumvitas.mcp.tools.demo_store import load_demo

        # Load snapshot for reference
        demo_path = get_resources_dir() / "demo_projects" / f"{demo_id}.yml"
        with open(demo_path) as f:
            snapshot = _yaml.safe_load(f)
        snapshot_steps = snapshot["calculations"][0].get("steps", [])

        # Fresh project
        project_root = QVService.init_project(tmp_path / demo_id)
        from quantumvitas.mcp import project as mcp_project
        monkeypatch.setattr(mcp_project, "_project_root_override", project_root)

        import quantumvitas.drivers  # noqa: F401

        result = load_demo.fn(demo_id=demo_id)
        assert result["status"] == "success", (
            f"load_demo failed for {demo_id}: {result.get('message', result)}"
        )

        # Read back each step YAML and compare parameters
        calc_ulid = result["data"]["calc_ulid"]
        svc = QVService(project_root)
        detail = svc.calculation.get_detail(calc_ulid)
        disk_steps = detail.get("steps", [])

        for idx, snap_step in enumerate(snapshot_steps):
            snap_params = snap_step.get("parameters", {})
            if not snap_params:
                continue  # Skip steps without parameters

            # Read actual step YAML from disk
            step_ulid = disk_steps[idx].get("step_ulid") or disk_steps[idx].get("ulid", "")
            step_detail = svc.calculation.get_step_detail(calc_ulid, step_ulid)
            disk_params = step_detail.get("parameters", {})

            # Top-level parameter keys must match
            for key in snap_params:
                assert key in disk_params, (
                    f"{demo_id} step {idx}: parameter key '{key}' missing from disk. "
                    f"Snapshot keys: {list(snap_params.keys())}, "
                    f"Disk keys: {list(disk_params.keys())}"
                )


# ===========================================================================
# load_demo tests — basic (single demo, qv_project fixture)
# ===========================================================================


class TestLoadDemo:
    """Focused load_demo tests with the shared qv_project fixture."""

    def test_load_demo_creates_calculation(self, qv_project):
        """Loading qe_si_scf → calc created in current project."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success", f"Failed: {result}"
        data = result["data"]
        assert data["calc_ulid"]
        assert data["demo_id"] == "qe_si_scf"
        assert data["engine"] == "qe"

    def test_load_demo_imports_structure(self, qv_project):
        """Loaded demo has structure in project."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]
        assert data["structure_ulid"] is not None

        # Verify structure exists in project
        svc = QVService(qv_project)
        structures = svc.structure.list()
        ulids = [s.structure_ulid for s in structures]
        assert data["structure_ulid"] in ulids

    def test_load_demo_has_steps(self, qv_project):
        """Loaded calculation has expected steps."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        steps = result["data"]["steps"]
        assert len(steps) >= 1
        step_types = [s["step_type_spec"] for s in steps]
        assert any("scf" in t for t in step_types)

    def test_load_demo_invalid_id(self, qv_project):
        """Nonexistent demo → error."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="nonexistent_demo_xyz")
        assert result["status"] == "error"
        assert result["error_type"] == "demo_not_found"

    def test_load_demo_custom_name(self, qv_project):
        """load_demo with custom name sets that name on the calculation."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf", name="My Custom Calc")
        assert result["status"] == "success"
        assert result["data"]["name"] == "My Custom Calc"

    def test_load_demo_species_map_preserved(self, qv_project):
        """Demo with species_map (e.g. QE) has it on the calculation."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"

        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(result["data"]["calc_ulid"])
        species_map = detail.get("species_map")
        # QE Si demo should have species_map with Si entry
        assert species_map is not None
        assert "Si" in species_map

    def test_load_two_demos_same_project(self, qv_project):
        """Loading two different demos → two distinct calculations."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        r1 = load_demo.fn(demo_id="qe_si_scf")
        assert r1["status"] == "success"
        r2 = load_demo.fn(demo_id="orca_water_sp")
        assert r2["status"] == "success"

        assert r1["data"]["calc_ulid"] != r2["data"]["calc_ulid"]
        assert r1["data"]["engine"] == "qe"
        assert r2["data"]["engine"] == "orca"

        # Both should be in the project
        svc = QVService(qv_project)
        calcs = svc.calculation.list()
        calc_ulids = [c.calc_ulid for c in calcs]
        assert r1["data"]["calc_ulid"] in calc_ulids
        assert r2["data"]["calc_ulid"] in calc_ulids


# ===========================================================================
# Repeated load & meta consistency tests
# ===========================================================================


class TestLoadDemoRepeated:
    """Loading the same demo multiple times: ULIDs unique, slugs never collide."""

    def test_load_same_demo_three_times(self, qv_project):
        """Load qe_si_scf 3× → 3 distinct calc_ulids, no slug collision."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        results = []
        for _ in range(3):
            r = load_demo.fn(demo_id="qe_si_scf")
            assert r["status"] == "success", f"Failed: {r}"
            results.append(r["data"])

        # All calc_ulids must be unique
        calc_ulids = [r["calc_ulid"] for r in results]
        assert len(set(calc_ulids)) == 3, f"Duplicate calc_ulids: {calc_ulids}"

        # All structure_ulids must be unique
        struct_ulids = [r["structure_ulid"] for r in results]
        assert len(set(struct_ulids)) == 3, f"Duplicate struct_ulids: {struct_ulids}"

        # All step_ulids must be unique
        all_step_ulids = [
            s["step_ulid"] for r in results for s in r["steps"]
        ]
        assert len(set(all_step_ulids)) == len(all_step_ulids), (
            f"Duplicate step_ulids: {all_step_ulids}"
        )

        # All calcs must be in the project
        svc = QVService(qv_project)
        calcs = svc.calculation.list()
        project_calc_ulids = {c.calc_ulid for c in calcs}
        for cid in calc_ulids:
            assert cid in project_calc_ulids

        # All structures must be in the project
        structs = svc.structure.list()
        project_struct_ulids = {s.structure_ulid for s in structs}
        for sid in struct_ulids:
            assert sid in project_struct_ulids

    def test_repeated_load_slugs_unique_on_disk(self, qv_project):
        """3× load → calculation directories have distinct slugs on disk."""
        from quantumvitas.mcp.tools.demo_store import load_demo

        for _ in range(3):
            r = load_demo.fn(demo_id="qe_si_scf")
            assert r["status"] == "success"

        # Check disk: each should be a separate directory
        calc_dirs = sorted(
            (qv_project / "calculations").iterdir()
        )
        # At least 3 calculation directories (fixture may have others)
        assert len(calc_dirs) >= 3, (
            f"Expected >=3 calc dirs, got {len(calc_dirs)}: {[d.name for d in calc_dirs]}"
        )
        # All directory names must be unique (slugs)
        dir_names = [d.name for d in calc_dirs]
        assert len(set(dir_names)) == len(dir_names), (
            f"Slug collision on disk: {dir_names}"
        )


class TestLoadDemoMetaConsistency:
    """Verify all resource meta (structure, calculation, steps) are internally consistent."""

    def test_meta_ulids_consistent(self, qv_project):
        """calc_ulid in project.qv.yml matches calculation.yaml meta.ulid."""
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]

        # Read project.qv.yml — entries use flat {calculation_id: ULID} format
        with open(qv_project / "project.qv.yml") as f:
            project_config = yaml.safe_load(f)

        calc_entries = project_config.get("calculations", [])
        calc_ids = [e.get("calculation_id") for e in calc_entries]
        assert data["calc_ulid"] in calc_ids, (
            f"calc_ulid {data['calc_ulid']} not in project.qv.yml calc_ids: {calc_ids}"
        )

        # Also verify calculation.yaml has matching meta.ulid
        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(data["calc_ulid"])
        calc_slug = detail.get("slug", "")
        calc_yaml_path = qv_project / "calculations" / calc_slug / "calculation.yaml"
        with open(calc_yaml_path) as f:
            calc_config = yaml.safe_load(f)
        calc_meta = calc_config.get("meta", {})
        assert calc_meta.get("ulid") == data["calc_ulid"]
        assert calc_meta.get("kind") == "calculation"
        assert calc_meta.get("slug") == calc_slug

    def test_structure_meta_consistent(self, qv_project):
        """structure_ulid in project.qv.yml matches structure file meta."""
        import json
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        struct_ulid = result["data"]["structure_ulid"]

        # Read project.qv.yml — entries use flat {structure_ulid: ULID} format
        with open(qv_project / "project.qv.yml") as f:
            project_config = yaml.safe_load(f)

        struct_entries = project_config.get("structures", [])
        struct_ids = [e.get("structure_ulid") for e in struct_entries]
        assert struct_ulid in struct_ids, (
            f"struct_ulid {struct_ulid} not in project.qv.yml struct_ids: {struct_ids}"
        )

        # Find the actual structure JSON file by scanning structures/
        structures_dir = qv_project / "structures"
        found = False
        for sf in structures_dir.glob("*.json"):
            struct_json = json.loads(sf.read_text())
            file_meta = struct_json.get("__qv_meta__", {})
            if file_meta.get("ulid") == struct_ulid:
                found = True
                assert file_meta.get("kind") == "structure"
                assert file_meta.get("slug"), "Structure slug is empty"
                break
        assert found, f"No structure file found with ulid {struct_ulid}"

    def test_step_ulids_in_calculation_yaml(self, qv_project):
        """Step ULIDs returned by load_demo match calculation.yaml step list."""
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]

        # Find calculation directory
        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(data["calc_ulid"])
        calc_slug = detail.get("slug", "")
        calc_yaml_path = qv_project / "calculations" / calc_slug / "calculation.yaml"
        assert calc_yaml_path.exists(), f"calculation.yaml missing: {calc_yaml_path}"

        with open(calc_yaml_path) as f:
            calc_config = yaml.safe_load(f)

        yaml_step_ulids = [
            s.get("step_ulid") for s in calc_config.get("steps", [])
        ]
        returned_step_ulids = [s["step_ulid"] for s in data["steps"]]

        assert yaml_step_ulids == returned_step_ulids, (
            f"Step ULIDs mismatch: yaml={yaml_step_ulids}, returned={returned_step_ulids}"
        )

    def test_step_yaml_files_exist_on_disk(self, qv_project):
        """Each step has a corresponding .step.yaml file in steps/ dir."""
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"

        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(result["data"]["calc_ulid"])
        calc_slug = detail.get("slug", "")
        steps_dir = qv_project / "calculations" / calc_slug / "steps"

        step_files = list(steps_dir.glob("*.step.yaml"))
        assert len(step_files) == len(result["data"]["steps"]), (
            f"Expected {len(result['data']['steps'])} step files, "
            f"got {len(step_files)}: {[f.name for f in step_files]}"
        )

        # Each step file should have valid meta with ulid
        for sf in step_files:
            with open(sf) as f:
                step_data = yaml.safe_load(f)
            step_meta = step_data.get("meta", {})
            assert step_meta.get("ulid"), f"Step file {sf.name} missing meta.ulid"
            assert step_meta.get("kind") == "step"

    def test_calc_structure_ulid_points_to_loaded_structure(self, qv_project):
        """calculation.yaml structure_ulid matches the loaded structure."""
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]

        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(data["calc_ulid"])
        calc_slug = detail.get("slug", "")
        calc_yaml_path = qv_project / "calculations" / calc_slug / "calculation.yaml"

        with open(calc_yaml_path) as f:
            calc_config = yaml.safe_load(f)

        assert calc_config.get("structure_ulid") == data["structure_ulid"]


# ===========================================================================
# Integration tests (require qv_project fixture)
# ===========================================================================


class TestDemoOrigin:
    """Tests for per-calculation demo_origin provenance tracking."""

    def test_load_demo_has_demo_origin(self, qv_project):
        """Loading a demo → calculation.yaml has demo_origin with correct fields."""
        import yaml
        from quantumvitas.mcp.tools.demo_store import load_demo

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]

        # Read calculation.yaml directly to verify demo_origin persisted
        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(data["calc_ulid"])
        calc_slug = detail.get("slug", "")
        calc_yaml_path = qv_project / "calculations" / calc_slug / "calculation.yaml"
        with open(calc_yaml_path) as f:
            calc_config = yaml.safe_load(f)

        demo_origin = calc_config.get("demo_origin")
        assert demo_origin is not None, "demo_origin missing from calculation.yaml"
        assert demo_origin["demo_id"] == "qe_si_scf"
        assert demo_origin["engine"] == "qe"
        assert "materialized_at" in demo_origin
        # materialized_at should be an ISO 8601 timestamp
        from datetime import datetime
        datetime.fromisoformat(demo_origin["materialized_at"])

    def test_regular_calc_no_demo_origin(self, qv_project):
        """A normal (non-demo) calculation has no demo_origin."""
        from quantumvitas.core.models import CalculationModel, save_calculation, load_calculation
        from quantumvitas.core.resources import ResourceMeta, generate_resource_id, slugify

        calc_ulid = generate_resource_id()
        calc_name = "Manual Calculation"
        calc_slug = slugify(calc_name)
        calc_dir = qv_project / "calculations" / calc_slug
        calc_dir.mkdir(parents=True, exist_ok=True)

        model = CalculationModel(
            meta=ResourceMeta(
                ulid=calc_ulid,
                name=calc_name,
                slug=calc_slug,
                path=f"calculations/{calc_slug}",
                kind="calculation",
            ),
            engine_family="qe",
        )
        save_calculation(model, calc_dir / "calculation.yaml")

        # Reload and verify demo_origin is None
        reloaded = load_calculation(calc_dir / "calculation.yaml", project_root=qv_project)
        assert reloaded.demo_origin is None

    def test_demo_origin_preserved_on_reload(self, qv_project):
        """demo_origin survives save → reload cycle via CalculationModel."""
        from quantumvitas.mcp.tools.demo_store import load_demo
        from quantumvitas.core.models import load_calculation

        result = load_demo.fn(demo_id="qe_si_scf")
        assert result["status"] == "success"
        data = result["data"]

        svc = QVService(qv_project)
        detail = svc.calculation.get_detail(data["calc_ulid"])
        calc_slug = detail.get("slug", "")
        calc_yaml_path = qv_project / "calculations" / calc_slug / "calculation.yaml"

        # Reload via CalculationModel (not raw YAML) — tests from_dict roundtrip
        model = load_calculation(calc_yaml_path, project_root=qv_project)
        assert model.demo_origin is not None
        assert model.demo_origin["demo_id"] == "qe_si_scf"
        assert model.demo_origin["engine"] == "qe"
        assert "materialized_at" in model.demo_origin

    def test_get_reference_analysis_via_calc_demo_origin(self, qv_project):
        """get_reference_analysis() finds ref pack via calculation.demo_origin."""
        from quantumvitas.demo_store.ref_packs import list_all_ref_packs, list_ref_pack_types
        from quantumvitas.mcp.tools.demo_store import load_demo

        # Find a demo that has a ref pack
        packs = list_all_ref_packs()
        if not packs:
            pytest.skip("No ref packs available")

        # Pick a demo with a ref pack and load it
        demo_id = packs[0]
        types = list_ref_pack_types(demo_id)
        if not types:
            pytest.skip(f"Ref pack {demo_id} has no object types")

        result = load_demo.fn(demo_id=demo_id)
        assert result["status"] == "success"
        calc_ulid = result["data"]["calc_ulid"]

        # The project is NOT a demo project (no project-level demo_source),
        # so get_reference_analysis should find the ref pack via demo_origin
        svc = QVService(qv_project)
        ref = svc.analysis.get_reference_analysis(calc_ulid, types[0])
        assert ref is not None, (
            f"get_reference_analysis returned None for demo {demo_id}, type {types[0]}. "
            "Expected demo_origin fallback to find ref pack."
        )
        assert ref["_is_reference"] is True
        assert ref["_reference_source"] == demo_id
        assert ref["object_type"] == types[0]


class TestDemoStoreIntegration:
    """Integration tests — search → load → inspect."""

    def test_search_then_load(self, qv_project):
        """Search for QE demos, pick first, load it."""
        from quantumvitas.mcp.tools.demo_store import load_demo, search_demos

        search_result = search_demos.fn(engine="qe")
        assert search_result["status"] == "success"
        demos = search_result["data"]["demos"]
        assert len(demos) > 0

        demo_id = demos[0]["ulid"]
        load_result = load_demo.fn(demo_id=demo_id)
        assert load_result["status"] == "success"
        assert load_result["data"]["engine"] == "qe"

    def test_load_then_inspect(self, qv_project):
        """Load demo, then inspect_calculation works on it."""
        from quantumvitas.mcp.tools.demo_store import load_demo
        from quantumvitas.mcp.tools.inspect_calculation import inspect_calculation

        load_result = load_demo.fn(demo_id="qe_si_scf")
        assert load_result["status"] == "success"
        calc_ulid = load_result["data"]["calc_ulid"]

        inspect_result = inspect_calculation.fn(calc_ulid=calc_ulid)
        assert inspect_result["status"] == "success"
        assert inspect_result["data"]["engine"] == "qe"
        assert inspect_result["data"]["n_steps"] >= 1
