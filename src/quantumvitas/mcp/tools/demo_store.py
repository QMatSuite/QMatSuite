"""Demo store tools — browse, preview, and load demo calculations."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


def _build_engine_map() -> dict[str, str]:
    """Build a mapping from demo_id to engine family by reading YAML meta."""
    import yaml
    from quantumvitas.core.resources import get_resources_dir

    demo_dir = get_resources_dir() / "demo_projects"
    if not demo_dir.exists():
        return {}

    result: dict[str, str] = {}
    for path in demo_dir.glob("*.yml"):
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            meta = data.get("meta", {})
            engine = meta.get("required_engine", "")
            if not engine:
                # Fallback: read from first calculation's engine_family
                calcs = data.get("calculations", [])
                if calcs:
                    engine = calcs[0].get("engine_family", "")
            result[path.stem] = engine.lower()
        except Exception:
            continue
    return result


def _summarize_bundle(object_type: str, bundle: dict) -> dict:
    """Extract compact scalar summary from a canonical bundle dict.

    Avoids including large arrays (eigenvalues, DOS grids, trajectory positions)
    in the response. Returns only scalars useful for decision-making.
    """
    if not bundle:
        return {}

    render_meta = bundle.get("render_meta", {}) or {}
    extra = render_meta.get("extra", {}) or {}
    arrays = bundle.get("arrays", {}) or {}
    series = bundle.get("series", []) or []

    ot = object_type.lower()

    if ot == "convergence":
        ionic_energy = arrays.get("ionic_energy", [])
        scf_step = arrays.get("scf_step", [])
        return {
            "final_energy_eV": ionic_energy[-1] if ionic_energy else None,
            "n_scf_steps": len(scf_step),
            "n_ionic_steps": extra.get("n_ionic_steps"),
            "converged": extra.get("converged"),
            "algorithm": extra.get("algorithm"),
        }

    if ot == "bands":
        markers = render_meta.get("markers", []) or []
        series_labels = render_meta.get("series_labels", []) or []
        k_distances = arrays.get("k_distances", [])
        symm_labels = [m.get("label") for m in markers if m.get("label")]
        return {
            "reference_energy_eV": render_meta.get("reference_energy"),
            "n_kpoints": len(k_distances),
            "n_bands": len(series_labels),
            "high_symm_labels": symm_labels,
        }

    if ot == "dos":
        energies = arrays.get("energies", [])
        e_range = None
        if energies:
            e_range = [min(energies), max(energies)]
        return {
            "fermi_energy_eV": render_meta.get("reference_energy"),
            "n_series": len(series),
            "n_energy_points": len(energies),
            "energy_range_eV": e_range,
            "series_labels": render_meta.get("series_labels", []),
        }

    if ot == "trajectory":
        energy_arr = arrays.get("energy", [])
        if not energy_arr:
            # Trajectory bundles store energy in series (not arrays)
            for s in series:
                if (s.get("name") or "").lower() in ("total energy", "energy"):
                    energy_arr = s.get("y", [])
                    break
        return {
            "trajectory_type": extra.get("trajectory_type"),
            "n_frames": extra.get("n_frames"),
            "n_atoms": extra.get("n_atoms"),
            "initial_energy_eV": energy_arr[0] if energy_arr else None,
            "final_energy_eV": energy_arr[-1] if energy_arr else None,
        }

    if ot == "field3d":
        vol = extra.get("volume_metadata", {}) or {}
        return {
            "field_kind": extra.get("field_kind"),
            "grid_shape": vol.get("grid_shape"),
            "value_min": vol.get("value_min"),
            "value_max": vol.get("value_max"),
            "value_mean": vol.get("value_mean"),
            "n_grid_points": extra.get("n_grid_points"),
        }

    # Unknown type: return render_meta scalars only (no arrays)
    return {
        "reference_energy": render_meta.get("reference_energy"),
        "extra": extra,
    }


@mcp.tool
def search_demos(
    engine: str = "",
    tag: str = "",
    difficulty: str = "",
    query: str = "",
    system_class: str = "",
    method: str = "",
    property_of_interest: str = "",
) -> dict:
    """Search the catalog of pre-built demo calculations.

    Returns demos matching the given filters. All filters are optional and
    combined with AND logic. With no filters, returns the full catalog.

    Args:
        engine: Filter by engine family (e.g. 'qe', 'vasp', 'orca').
        tag: Filter by tag (e.g. 'bands', 'scf', 'tutorial').
        difficulty: Filter by difficulty level ('beginner', 'intermediate', 'advanced').
        query: Free-text search across title, subtitle, description, and tags.
        system_class: Filter by system type ('crystal', 'molecule', 'surface', '1d', 'cluster').
        method: Filter by DFT/QC method (e.g. 'dft-pbe', 'hf', 'mp2', 'vmc-dft').
        property_of_interest: Filter by computed property
            (e.g. 'band_structure', 'dos', 'geometry', 'total_energy', 'absorption').
    """
    from quantumvitas.api import QVService
    from quantumvitas.demo_store.ref_packs import list_all_ref_packs, list_ref_pack_types

    try:
        demos = QVService.list_demo_projects()
    except Exception as exc:
        return make_error("catalog_error", f"Failed to load demo catalog: {exc}")

    # Build engine lookup from YAML meta.required_engine
    engine_map = _build_engine_map()

    # Enrichment: ref pack info
    ref_pack_slugs = set(list_all_ref_packs())

    # Filter
    query_lower = query.lower()
    filtered = []
    for d in demos:
        demo_id = d.get("ulid", "")

        # Engine filter
        if engine:
            demo_engine = engine_map.get(demo_id, "")
            if demo_engine != engine.lower():
                continue

        # Tag filter
        if tag:
            demo_tags = [t.lower() for t in d.get("tags", [])]
            if tag.lower() not in demo_tags:
                continue

        # Difficulty filter
        if difficulty:
            if (d.get("difficulty") or "").lower() != difficulty.lower():
                continue

        # system_class filter
        if system_class:
            if (d.get("system_class") or "").lower() != system_class.lower():
                continue

        # method filter (substring match: 'pbe' matches 'dft-pbe')
        if method:
            demo_method = (d.get("method") or "").lower()
            if method.lower() not in demo_method:
                continue

        # property_of_interest filter
        if property_of_interest:
            if (d.get("property_of_interest") or "").lower() != property_of_interest.lower():
                continue

        # Text query: search title + subtitle + description + name + tags
        if query_lower:
            title = (d.get("title") or "").lower()
            subtitle = (d.get("subtitle") or "").lower()
            desc = (d.get("description") or "").lower()
            name = (d.get("name") or "").lower()
            tags_text = " ".join(d.get("tags", [])).lower()
            searchable = f"{title} {subtitle} {desc} {name} {tags_text}"
            if query_lower not in searchable:
                continue

        d["engine"] = engine_map.get(demo_id, "")
        has_ref = demo_id in ref_pack_slugs
        d["has_ref_pack"] = has_ref
        d["ref_pack_types"] = list_ref_pack_types(demo_id) if has_ref else []
        filtered.append(d)

    if filtered:
        hint = (
            "Use get_demo_results(demo_id=...) to preview pre-computed results, "
            "or load_demo(demo_id=...) to load a demo into your project."
        )
    else:
        hint = (
            "No demos matched. Try broader filters, or use "
            "create_calculation(...) to start from scratch."
        )
    return make_response(
        {"demos": filtered, "total": len(filtered)},
        context_hint=hint,
    )


@mcp.tool
def get_demo_results(demo_id: str, object_type: str = "") -> dict:
    """Preview pre-computed results for a demo calculation.

    Without object_type, lists available result types and manifest metadata.
    With object_type, returns a compact scalar summary of the analysis result
    (large arrays like eigenvalues or DOS grids are excluded to save context).

    Args:
        demo_id: Demo identifier (e.g. 'qe_si_scf', 'vasp_si_relax').
        object_type: Analysis type to load (e.g. 'bands', 'dos', 'convergence').
                     Empty string lists available types.
    """
    from quantumvitas.demo_store.ref_packs import (
        list_ref_pack_types,
        load_ref_pack,
        load_ref_pack_manifest,
    )

    if not object_type:
        # List available types + manifest
        types = list_ref_pack_types(demo_id)
        manifest = load_ref_pack_manifest(demo_id)
        if manifest is None:
            return make_error(
                "no_ref_pack",
                f"No pre-computed results available for demo '{demo_id}'.",
                suggestions=["Use search_demos() to find demos with ref packs."],
            )
        return make_response(
            {
                "demo_id": demo_id,
                "available_types": types,
                "manifest": manifest,
            },
            context_hint=(
                f"Use get_demo_results(demo_id='{demo_id}', object_type=...) "
                "to load a specific result type."
            ),
        )

    # Load specific result
    data = load_ref_pack(demo_id, object_type)
    if data is None:
        available = list_ref_pack_types(demo_id)
        if not available:
            return make_error(
                "no_ref_pack",
                f"No pre-computed results available for demo '{demo_id}'.",
            )
        return make_error(
            "type_not_found",
            f"Result type '{object_type}' not available for demo '{demo_id}'.",
            suggestions=available,
        )

    # Return compact scalar summary (no raw arrays)
    summary = _summarize_bundle(object_type, data)
    provenance = data.get("provenance_meta", {}) or {}

    return make_response(
        {
            "demo_id": demo_id,
            "object_type": object_type,
            "summary": summary,
            "engine": provenance.get("engine_name", ""),
            "gen_steps": provenance.get("gen_steps", []),
        },
        context_hint=(
            f"Showing scalar summary for '{object_type}' analysis of demo '{demo_id}'. "
            "Large arrays (eigenvalues, DOS grids, trajectory positions) are excluded. "
            "Use load_demo() then run_calculation() to reproduce the full result in your project."
        ),
    )


@mcp.tool
def load_demo(demo_id: str, name: str = "") -> dict:
    """Load a demo calculation into the current project.

    Imports the demo's structure and creates a calculation with the demo's
    engine, workflow steps, and parameters. Works within the current project
    — no project context switching.

    Args:
        demo_id: Demo identifier (e.g. 'qe_si_scf', 'vasp_si_relax').
        name: Optional name for the calculation (defaults to demo title).
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    try:
        import quantumvitas.drivers  # noqa: F401 — trigger registration
        result = svc.load_demo_as_calculation(demo_id, name=name or None)
    except FileNotFoundError as exc:
        return make_error("demo_not_found", str(exc))
    except ValueError as exc:
        return make_error("invalid_demo", str(exc))
    except Exception as exc:
        return make_error("load_failed", f"Failed to load demo: {exc}")

    calc_ulid = result["calc_ulid"]
    structure_ulid = result.get("structure_ulid", "")
    n_steps = len(result.get("steps", []))

    return make_response(
        result,
        context_hint=(
            f"Demo '{demo_id}' loaded. "
            f"Structure '{structure_ulid}' is now in your project library — "
            f"you do NOT need to import a structure separately. "
            f"Calculation '{calc_ulid}' is configured with {n_steps} step(s). "
            f"Use run_calculation(calc_ulid='{calc_ulid}') to execute, or "
            f"inspect_calculation(calc_ulid='{calc_ulid}') to review parameters. "
            f"To use a different material with the same workflow, use create_calculation() instead."
        ),
    )
