#!/usr/bin/env python3
"""
Generate all demo project snapshots from the corpus.

Reads corpus_index.yaml, translates eligible cases, writes demo .yml files
and the generator manifest.

Usage: python tools/demo_store/generate_all.py [--dry-run]

This is the SINGLE WRITER for src/quantumvitas/resources/demo_projects/ (Rule T1).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

CORPUS_ROOT = REPO_ROOT / "tests" / "inputformat" / "samples"
RESOURCES_DIR = REPO_ROOT / "src" / "quantumvitas" / "resources"
DEMO_DIR = RESOURCES_DIR / "demo_projects"

# Mapping: old demo filename stem -> new demo_slug
OLD_TO_NEW_SLUG = {
    "00_Si_scf": "qe_si_scf",
    "03_Si_vc_relax": "qe_si_vc_relax",
    "04_Si_DOS": "qe_si_dos_alt",
    "06_Al_DOS": "qe_al_dos",
    "07_Si_bandStructure": "qe_si_bands_alt",
    "08_Fe_DOS": "qe_fe_scf",
    "qe_fe_dos": "qe_fe_scf",
    "09_Si_phonon": "qe_si_phonon",
    "12_NMR_gipaw": "qe_nmr_gipaw",
    "13_graphene": "qe_graphene_bands",
    "15_bulk_modulus_Si": "qe_si_bulk_modulus",
    "19_Si_CPMD": "qe_si_cpmd",
    "water_orca_scf": "orca_water_sp",
    "methane_orca_freq": "orca_methane_freq",
    "formaldehyde_orca_tddft": "orca_formaldehyde_tddft",
    "si_bands_vasp_demo": "vasp_si_bands",
    "water_pyscf_scf": "pyscf_water_scf",
    "copper_wannier90_demo": "qe_w90_copper",
    "diamond_wannier90_demo": "qe_w90_diamond",
    "silicon_wannier90_demo": "qe_w90_silicon",
}

# Reverse mapping for lookup
NEW_SLUG_TO_OLD = {v: k for k, v in OLD_TO_NEW_SLUG.items()}


def _matches_old_demo(old_stem: str, new_slug: str, engine: str) -> bool:
    """Check if an old demo filename matches a new demo_slug."""
    return OLD_TO_NEW_SLUG.get(old_stem) == new_slug


def _compute_file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _yaml_dump(data: dict) -> str:
    """Deterministic YAML serialization (Rule T4)."""
    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def generate_demo_from_existing(
    demo_slug: str,
    existing_demo_path: Path,
    case_data: Dict[str, Any],
    case_dir: Path,
) -> Dict[str, Any]:
    """
    For demos that already exist with correct content, regenerate with
    deterministic ULIDs and updated gallery metadata while preserving
    the core project data (structure, steps, parameters).
    """
    from quantumvitas.demo_store.ulid_seed import deterministic_ulid
    from quantumvitas.demo_store.manifest import _compute_dir_checksum, GENERATOR_VERSION
    from quantumvitas.demo_store.translator import _strip_managed_params

    with open(existing_demo_path) as f:
        existing = yaml.safe_load(f)

    # Rewrite ULIDs to be deterministic
    project_slug = existing["project"]["meta"].get("slug", demo_slug)
    calc_slug = None

    # Project ULID
    existing["project"]["meta"]["ulid"] = deterministic_ulid(demo_slug, "project")

    # Structure ULIDs
    old_to_new_struct = {}
    for struct in existing.get("structures", []):
        old_ulid = struct["meta"]["ulid"]
        s_slug = struct["meta"].get("slug", "structure")
        new_ulid = deterministic_ulid(demo_slug, f"structure:{s_slug}")
        old_to_new_struct[old_ulid] = new_ulid
        struct["meta"]["ulid"] = new_ulid

    # Calculation ULIDs
    for calc in existing.get("calculations", []):
        c_slug = calc["meta"].get("slug", "calculation")
        calc_slug = c_slug
        calc["meta"]["ulid"] = deterministic_ulid(demo_slug, f"calculation:{c_slug}")

        # Remap structure_ulid
        old_struct_ulid = calc.get("structure_ulid")
        if old_struct_ulid and old_struct_ulid in old_to_new_struct:
            calc["structure_ulid"] = old_to_new_struct[old_struct_ulid]

        # Step ULIDs + strip managed keys
        engine = calc.get("engine_family", case_data.get("engine", ""))
        for step in calc.get("steps", []):
            s_slug = step["meta"].get("slug", "step")
            step["meta"]["ulid"] = deterministic_ulid(
                demo_slug, f"step:{c_slug}:{s_slug}"
            )
            # Strip runtime-managed keys (prefix, outdir, etc.) from parameters
            if "parameters" in step:
                step["parameters"] = _strip_managed_params(
                    step["parameters"], engine
                )

    # Update gallery metadata
    tags = case_data.get("tags", case_data.get("workflow_tags", []))
    existing_meta = existing.get("meta", {})
    meta = {
        "ulid": demo_slug,
        "title": case_data.get("title", existing_meta.get("title", demo_slug)),
        "subtitle": case_data.get("subtitle", existing_meta.get("subtitle", "")),
        "description": case_data.get("description", existing_meta.get("description", "")),
        "tags": tags,
        "recommended_analysis": case_data.get(
            "recommended_analysis",
            existing_meta.get("recommended_analysis", "scf"),
        ),
        "difficulty": case_data.get(
            "difficulty",
            existing_meta.get("difficulty", "beginner"),
        ),
        "system_class": case_data.get("system_class", existing_meta.get("system_class", "")),
        "periodicity": case_data.get("periodicity", existing_meta.get("periodicity", "")),
        "method": case_data.get("method", existing_meta.get("method", "")),
        "property_of_interest": case_data.get("property_of_interest", existing_meta.get("property_of_interest", "")),
        "spin_treatment": case_data.get("spin_treatment", existing_meta.get("spin_treatment", "nonmagnetic")),
        "estimated_runtime_s": case_data.get("estimated_runtime_s", existing_meta.get("estimated_runtime_s")),
        "multi_engine": case_data.get("multi_engine", existing_meta.get("multi_engine", False)),
        "engines_used": case_data.get("engines_used", existing_meta.get("engines_used", [case_data.get("engine", "")])),
        "n_steps": case_data.get("n_steps", existing_meta.get("n_steps")),
        "step_summary": case_data.get("step_summary", existing_meta.get("step_summary", "")),
        "available_analysis": case_data.get("available_analysis", existing_meta.get("available_analysis", [])),
    }

    # Asset and engine info
    asset_policy = case_data.get("asset_policy", "none")
    if asset_policy != "none":
        meta["asset_policy"] = asset_policy
    meta["required_engine"] = case_data.get("required_engine", case_data["engine"])
    meta["availability"] = case_data.get("availability", "open_source")

    # Generator provenance
    meta["generator_version"] = GENERATOR_VERSION
    meta["corpus_engine"] = case_data["engine"]
    meta["corpus_case_id"] = case_data["case_id"]
    meta["corpus_checksum"] = _compute_dir_checksum(case_dir)

    # Preserve reference_artifacts from existing demo
    if "reference_artifacts" in existing_meta:
        meta["reference_artifacts"] = existing_meta["reference_artifacts"]

    existing["meta"] = meta

    return existing


def generate_demo_via_translator(
    case_data: Dict[str, Any],
    case_dir: Path,
    index_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a demo snapshot using the full translator pipeline."""
    from quantumvitas.demo_store.translator import translate_corpus_case

    return translate_corpus_case(case_dir, case_data, index_entry, REPO_ROOT)


def main():
    dry_run = "--dry-run" in sys.argv

    # Load corpus index
    with open(CORPUS_ROOT / "corpus_index.yaml") as f:
        index = yaml.safe_load(f)

    entries = index.get("entries", [])
    eligible = [e for e in entries if e.get("demo_eligible")]

    print(f"Corpus index: {len(entries)} total, {len(eligible)} demo-eligible")

    # Build mapping of old demo filenames to new demo_slugs
    # for identifying which existing demos to preserve
    existing_demos = {p.stem: p for p in DEMO_DIR.glob("*.yml")}

    # Track generated demos
    generated = {}
    errors = []
    demo_manifest = {}

    for entry in eligible:
        engine = entry["engine"]
        case_id = entry["case_id"]
        dir_name = entry["dir_name"]
        demo_slug = entry["demo_slug"]

        case_dir = CORPUS_ROOT / engine / dir_name
        case_yaml_path = case_dir / "case.yaml"

        if not case_yaml_path.exists():
            errors.append(f"Missing case.yaml: {case_dir}")
            continue

        with open(case_yaml_path) as f:
            case_data = yaml.safe_load(f)

        output_path = DEMO_DIR / f"{demo_slug}.yml"

        try:
            # Strategy:
            # 1. If an existing demo with this slug exists, use the preserve
            #    approach (regenerate with deterministic ULIDs + updated metadata).
            # 2. If parser_mode is direct_snapshot, use direct builder.
            # 3. Otherwise use the full translator pipeline.
            existing_path = existing_demos.get(demo_slug)

            # Also check for old-name demos that map to new slugs
            if not existing_path or not existing_path.exists():
                for old_name, old_path in existing_demos.items():
                    if old_path.exists() and _matches_old_demo(old_name, demo_slug, engine):
                        existing_path = old_path
                        break

            if existing_path and existing_path.exists():
                snapshot = generate_demo_from_existing(
                    demo_slug, existing_path, case_data, case_dir
                )
            elif case_data.get("parser_mode") == "direct_snapshot":
                from quantumvitas.demo_store.direct_snapshot import build_direct_snapshot
                snapshot = build_direct_snapshot(case_data, entry, REPO_ROOT)
            else:
                snapshot = generate_demo_via_translator(case_data, case_dir, entry)

            yaml_text = _yaml_dump(snapshot)

            if not dry_run:
                output_path.write_text(yaml_text)

            generated[demo_slug] = output_path
            print(f"  [{engine}/{dir_name}] -> {demo_slug}.yml")

            # Build manifest entry
            from quantumvitas.demo_store.manifest import _compute_dir_checksum
            demo_manifest[demo_slug] = {
                "engine": engine,
                "case_id": case_id,
                "dir_name": dir_name,
                "corpus_path": f"tests/inputformat/samples/{engine}/{dir_name}",
                "corpus_checksum": _compute_dir_checksum(case_dir),
                "output_file": f"src/quantumvitas/resources/demo_projects/{demo_slug}.yml",
                "output_checksum": _compute_file_checksum(output_path) if not dry_run else "",
                "asset_policy": entry.get("asset_policy", "none"),
            }

        except Exception as e:
            errors.append(f"[{engine}/{dir_name}] {e}")
            import traceback
            traceback.print_exc()

    # Remove old demos that are no longer generated
    OLD_DEMO_FILENAMES = {
        "00_Si_scf.yml", "03_Si_vc_relax.yml", "04_Si_DOS.yml",
        "06_Al_DOS.yml", "07_Si_bandStructure.yml", "08_Fe_DOS.yml",
        "09_Si_phonon.yml", "12_NMR_gipaw.yml", "13_graphene.yml",
        "15_bulk_modulus_Si.yml", "19_Si_CPMD.yml",
        "copper_wannier90_demo.yml", "diamond_wannier90_demo.yml",
        "silicon_wannier90_demo.yml",
        "water_orca_scf.yml", "formaldehyde_orca_tddft.yml",
        "methane_orca_freq.yml",
        "si_bands_vasp_demo.yml",
        "water_pyscf_scf.yml",
        "qe_fe_dos.yml",
    }

    if not dry_run:
        for old_name in OLD_DEMO_FILENAMES:
            old_path = DEMO_DIR / old_name
            # Only remove if the demo was regenerated under a new slug
            stem = old_path.stem
            if old_path.exists() and stem not in generated:
                old_path.unlink()
                print(f"  Removed old: {old_name}")

    # Write manifest
    if not dry_run:
        from quantumvitas.demo_store.manifest import write_manifest
        corpus_index_checksum = _compute_file_checksum(CORPUS_ROOT / "corpus_index.yaml")
        write_manifest(DEMO_DIR, demo_manifest, corpus_index_checksum)
        print(f"\n  Wrote .generator_manifest.json")

    # Summary
    print(f"\nGenerated: {len(generated)} demos")
    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  {e}")

    return len(errors) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
