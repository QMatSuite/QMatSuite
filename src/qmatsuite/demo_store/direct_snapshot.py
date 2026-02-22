"""
Direct snapshot builder for Python-script engines (GPAW, Psi4, PySCF).

These engines have no parseable input files - their "input" is a Python script.
The case.yaml includes inline parameters and structure metadata sufficient to
build a demo snapshot without parsing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from qmatsuite.demo_store.ulid_seed import deterministic_ulid
from qmatsuite.demo_store.translator import (
    _build_gallery_meta,
    _build_molecule_dict,
    _build_structure_dict,
    _element_mass,
    _make_structure_name,
    _slugify,
)


def build_direct_snapshot(
    case_data: Dict[str, Any],
    index_entry: Dict[str, Any],
    repo_root: Path,
) -> Dict[str, Any]:
    """
    Build a demo snapshot directly from case.yaml metadata.

    Used for Python-script engines where no parseable input files exist.
    The case.yaml must include 'inline_parameters' and optionally
    'inline_structure' with enough data to construct the snapshot.

    Args:
        case_data: Parsed case.yaml with inline_parameters/inline_structure.
        index_entry: Corresponding corpus_index entry.
        repo_root: Repository root path.

    Returns:
        Snapshot dict ready for YAML serialization.
    """
    demo_slug = case_data["demo_slug"]
    engine = case_data["engine"]
    species = case_data.get("species", [])
    step_type_gen = case_data["step_type_gen"]
    step_type_spec = case_data["step_type_spec"]

    # Get inline data from case.yaml
    params = case_data.get("inline_parameters", {})
    inline_struct = case_data.get("inline_structure")

    # Build structure data
    structure_data = None
    if inline_struct:
        struct_type = inline_struct.get("type", "molecule")
        if struct_type == "molecule":
            structure_data = _build_molecule_dict(
                inline_struct.get("species", species),
                inline_struct.get("cart_coords", []),
            )
        elif struct_type == "structure":
            structure_data = _build_structure_dict(
                inline_struct["lattice"],
                inline_struct.get("species", species),
                inline_struct["frac_coords"],
            )

    struct_name = _make_structure_name(species)
    struct_slug = _slugify(struct_name)
    calc_name = case_data.get("title", f"{engine} {step_type_gen}")
    calc_slug = _slugify(calc_name)

    # Deterministic ULIDs
    project_ulid = deterministic_ulid(demo_slug, "project")
    struct_ulid = deterministic_ulid(demo_slug, f"structure:{struct_slug}")
    calc_ulid = deterministic_ulid(demo_slug, f"calculation:{calc_slug}")
    step_ulid = deterministic_ulid(demo_slug, f"step:{calc_slug}:{_slugify(step_type_gen)}")

    # Build step
    step_dict = {
        "meta": {
            "name": step_type_gen,
            "slug": _slugify(step_type_gen),
            "path": f"calculations/{calc_slug}/steps/{_slugify(step_type_gen)}.step.yaml",
            "kind": "step",
            "ulid": step_ulid,
        },
        "parameters": params,
        "step_type_spec": step_type_spec,
    }

    # Build calculation
    calc_dict = {
        "meta": {
            "ulid": calc_ulid,
            "name": calc_name,
            "slug": calc_slug,
            "path": f"calculations/{calc_slug}",
            "kind": "calculation",
        },
        "mode": "normal",
        "working_dir": "raw",
        "engine_family": engine,
        "steps": [step_dict],
    }

    if structure_data:
        calc_dict["structure_ulid"] = struct_ulid

    structures = []
    if structure_data:
        structures.append({
            "meta": {
                "ulid": struct_ulid,
                "name": struct_name,
                "slug": struct_slug,
                "path": f"structures/{struct_slug}.json",
                "kind": "structure",
            },
            "data": structure_data,
        })

    project_name = case_data.get("title", demo_slug)

    snapshot = {
        "version": 1,
        "project": {
            "meta": {
                "ulid": project_ulid,
                "name": project_name,
                "slug": _slugify(project_name),
                "path": ".",
                "kind": "project",
            },
            "settings": {},
        },
        "structures": structures,
        "calculations": [calc_dict],
    }

    # Corpus dir for checksum
    corpus_root = repo_root / "tests" / "inputformat" / "samples"
    case_dir = corpus_root / engine / case_data.get("case_id", demo_slug)

    snapshot["meta"] = _build_gallery_meta(case_data, index_entry, case_dir)

    return snapshot
