#!/usr/bin/env python3
"""
Create QE corpus entries from existing demo snapshots.

For each QE demo, extracts step parameters and creates:
- tests/inputformat/samples/qe/<dir_name>/case.yaml
- tests/inputformat/samples/qe/<dir_name>/*.in (QE input files)

Usage: python tools/demo_store/create_qe_corpus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_ROOT = REPO_ROOT / "tests" / "inputformat" / "samples"
RESOURCES_DIR = REPO_ROOT / "src" / "quantumvitas" / "resources"
DEMO_DIR = RESOURCES_DIR / "demo_projects"

# Map demo filename -> (corpus_dir_name, demo_slug, is_multi_step)
QE_DEMO_MAP = {
    "00_Si_scf.yml": ("si_scf", "qe_si_scf", False),
    "03_Si_vc_relax.yml": ("si_vc_relax", "qe_si_vc_relax", False),
    "si_dos_demo.yml": ("si_dos", "si_dos_demo", True),
    "04_Si_DOS.yml": ("si_dos_alt", "qe_si_dos_alt", True),
    "06_Al_DOS.yml": ("al_dos", "qe_al_dos", True),
    "si_bands_demo.yml": ("si_bands", "si_bands_demo", True),
    "07_Si_bandStructure.yml": ("si_bands_alt", "qe_si_bands_alt", True),
    "08_Fe_DOS.yml": ("fe_dos", "qe_fe_dos", True),
    "09_Si_phonon.yml": ("si_phonon", "qe_si_phonon", True),
    "12_NMR_gipaw.yml": ("nmr_gipaw", "qe_nmr_gipaw", True),
    "13_graphene.yml": ("graphene_bands", "qe_graphene_bands", True),
    "15_bulk_modulus_Si.yml": ("si_bulk_modulus", "qe_si_bulk_modulus", False),
    "19_Si_CPMD.yml": ("si_cpmd", "qe_si_cpmd", False),
}

# step_type_spec -> step_type_gen
SPEC_TO_GEN = {
    "qe_scf": "scf",
    "qe_nscf": "nscf",
    "qe_relax": "relax",
    "qe_bandspw": "bandspw",
    "qe_bands": "bands",
    "qe_dos": "dos",
    "qe_pdos": "pdos",
    "qe_ph": "ph",
    "qe_gipaw": "gipaw",
    "qe_md": "md",
    "qe_pp": "pp",
    "qe_plotband": "plotband",
    "qe_q2r": "q2r",
    "qe_matdyn": "matdyn",
    "qe_dynmat": "dynmat",
}

# Map demo to recommended analysis and tags
DEMO_ANALYSIS = {
    "qe_si_scf": ("scf", ["scf", "Si", "PW", "tutorial", "beginner"]),
    "qe_si_vc_relax": ("scf", ["relax", "Si", "PW", "tutorial"]),
    "si_dos_demo": ("dos", ["dos", "Si", "PW", "tutorial", "beginner"]),
    "qe_si_dos_alt": ("dos", ["dos", "Si", "PW", "tutorial"]),
    "qe_al_dos": ("dos", ["dos", "Al", "PW", "metal", "tutorial"]),
    "si_bands_demo": ("bands", ["bands", "Si", "PW", "tutorial", "beginner"]),
    "qe_si_bands_alt": ("bands", ["bands", "Si", "PW", "tutorial"]),
    "qe_fe_dos": ("dos", ["dos", "Fe", "PW", "magnetic", "tutorial"]),
    "qe_si_phonon": ("scf", ["phonon", "Si", "PW", "DFPT", "tutorial"]),
    "qe_nmr_gipaw": ("scf", ["NMR", "GIPAW", "PW", "advanced"]),
    "qe_graphene_bands": ("bands", ["bands", "graphene", "2D", "PW", "tutorial"]),
    "qe_si_bulk_modulus": ("scf", ["scf", "Si", "PW", "equation-of-state", "tutorial"]),
    "qe_si_cpmd": ("trajectory", ["md", "Si", "PW", "CPMD", "advanced"]),
}


def _generate_qe_input_text(step_params: dict, step_spec: str, species_map: dict = None) -> str:
    """
    Generate a minimal QE input file text from step parameters.

    This is a simplified writer that produces parseable .in files
    from the demo snapshot's step parameters.
    """
    lines = []

    # Namelists: CONTROL, SYSTEM, ELECTRONS, IONS, CELL, BANDS, DOS, etc.
    namelist_order = ["CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL", "BANDS", "DOS",
                      "INPUTPH", "INPUTPP", "PLOT", "PROJWFC", "GIPAW"]

    for nl_name in namelist_order:
        if nl_name in step_params:
            nl_data = step_params[nl_name]
            if not isinstance(nl_data, dict):
                continue
            lines.append(f"&{nl_name}")
            for key, val in nl_data.items():
                if isinstance(val, str):
                    lines.append(f"  {key} = '{val}'")
                elif isinstance(val, bool):
                    lines.append(f"  {key} = .{'true' if val else 'false'}.")
                elif isinstance(val, float):
                    lines.append(f"  {key} = {val}")
                elif isinstance(val, int):
                    lines.append(f"  {key} = {val}")
            lines.append("/")
            lines.append("")

    # Cards: ATOMIC_SPECIES, ATOMIC_POSITIONS, K_POINTS, CELL_PARAMETERS
    cards = step_params.get("cards") if isinstance(step_params.get("cards"), dict) else {}
    # Also check if cards are at the same level as parameters in multi-step

    if "K_POINTS" in cards:
        kp = cards["K_POINTS"]
        option = kp.get("option", "automatic")
        lines.append(f"K_POINTS {{{option}}}")
        for row in kp.get("data", []):
            if isinstance(row, list):
                lines.append("  " + " ".join(str(x) for x in row))
            else:
                lines.append(f"  {row}")
        lines.append("")

    return "\n".join(lines) + "\n"


def create_qe_corpus_entry(demo_file: str, dir_name: str, demo_slug: str, multi_step: bool):
    """Create a QE corpus entry from an existing demo snapshot."""
    demo_path = DEMO_DIR / demo_file
    if not demo_path.exists():
        print(f"  SKIP: {demo_file} not found")
        return

    with open(demo_path) as f:
        demo = yaml.safe_load(f)

    # Create corpus directory
    qe_dir = CORPUS_ROOT / "qe"
    qe_dir.mkdir(exist_ok=True)
    case_dir = qe_dir / dir_name
    case_dir.mkdir(exist_ok=True)

    # Extract info from demo
    calcs = demo.get("calculations", [])
    if not calcs:
        print(f"  SKIP: {demo_file} has no calculations")
        return

    calc = calcs[0]
    steps = calc.get("steps", [])
    species_map = calc.get("species_map", {})
    demo_meta = demo.get("meta", {})

    # Determine structure species
    structures = demo.get("structures", [])
    species = []
    if structures:
        struct_data = structures[0].get("data", {})
        for site in struct_data.get("sites", []):
            for sp in site.get("species", []):
                elem = sp.get("element", "")
                if elem and elem not in species:
                    species.append(elem)

    # Determine step types
    if multi_step:
        steps_def = []
        first_gen = None
        for step in steps:
            spec = step.get("step_type_spec", "qe_scf")
            gen = SPEC_TO_GEN.get(spec, "scf")
            if first_gen is None:
                first_gen = gen

            # Determine input filename
            step_slug = step.get("meta", {}).get("slug", gen)
            input_name = step.get("input_name", f"{step_slug}.in")

            steps_def.append({
                "step_type_gen": gen,
                "step_type_spec": spec,
                "input_files": [input_name],
            })

            # Write the .in file
            params = dict(step.get("parameters", {}))
            if "cards" in step:
                params["cards"] = step["cards"]
            input_text = _generate_qe_input_text(params, spec, species_map)
            (case_dir / input_name).write_text(input_text)

        step_type_gen = first_gen or "scf"
        step_type_spec = f"qe_{step_type_gen}"
    else:
        step = steps[0] if steps else {}
        spec = step.get("step_type_spec", "qe_scf")
        step_type_gen = SPEC_TO_GEN.get(spec, "scf")
        step_type_spec = spec

        # Write single .in file
        params = dict(step.get("parameters", {}))
        if "cards" in step:
            params["cards"] = step["cards"]
        input_name = step.get("input_name", f"{dir_name}.in")
        input_text = _generate_qe_input_text(params, spec, species_map)
        (case_dir / input_name).write_text(input_text)
        steps_def = None

    # Determine analysis and tags
    analysis_info = DEMO_ANALYSIS.get(demo_slug, ("scf", ["tutorial", "qe"]))
    recommended_analysis = analysis_info[0]
    tags = analysis_info[1]

    # Determine title and subtitle
    title = demo_meta.get("title", demo_slug)
    subtitle = demo_meta.get("subtitle", "")
    difficulty = demo_meta.get("difficulty", "beginner")

    # Pseudo requirements
    pseudo_files = demo.get("pseudo", {}).get("files", [])
    asset_requirements = {}
    if pseudo_files:
        asset_requirements["pseudopotentials"] = [
            {"file": pf, "element": pf.split(".")[0], "source": "src/quantumvitas/resources/pseudo"}
            for pf in pseudo_files
        ]

    # Build workflow_tags from demo tags + analysis type
    workflow_tags = []
    if step_type_gen in ("scf",):
        workflow_tags.append("scf")
    elif step_type_gen in ("relax",):
        workflow_tags.append("relax")
    elif step_type_gen in ("bandspw", "bands"):
        workflow_tags.append("bands")
    elif step_type_gen in ("dos",):
        workflow_tags.append("dos")
    elif step_type_gen in ("md",):
        workflow_tags.append("md")
    elif step_type_gen in ("ph",):
        workflow_tags.append("phonon")

    if multi_step:
        # Add all step gen types
        for sd in (steps_def or []):
            g = sd["step_type_gen"]
            if g not in workflow_tags:
                workflow_tags.append(g)

    workflow_tags.append("electronic")

    # Build case.yaml
    case_data = {
        "case_id": dir_name,
        "engine": "qe",
        "title": title,
        "description": subtitle or title,
        "workflow_tags": workflow_tags,
        "species": species,
        "demo_eligible": True,
        "step_type_gen": step_type_gen,
        "step_type_spec": step_type_spec,
        "required_engine": "qe",
        "availability": "open_source",
        "demo_slug": demo_slug,
        "asset_policy": "redistributable" if pseudo_files else "none",
        "recommended_analysis": recommended_analysis,
        "difficulty": difficulty,
        "subtitle": subtitle,
        "tags": tags,
        "exclusion_reason": None,
    }

    if asset_requirements:
        case_data["asset_requirements"] = asset_requirements

    if multi_step:
        case_data["multi_step"] = True
        case_data["steps"] = steps_def
    else:
        case_data["multi_step"] = False

    # Write case.yaml
    with open(case_dir / "case.yaml", "w") as f:
        yaml.safe_dump(case_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"  Created qe/{dir_name}/ (slug={demo_slug}, multi_step={multi_step}, "
          f"species={species}, steps={len(steps)})")


def main():
    print("Creating QE corpus entries from existing demos...")

    for demo_file, (dir_name, demo_slug, multi_step) in QE_DEMO_MAP.items():
        try:
            create_qe_corpus_entry(demo_file, dir_name, demo_slug, multi_step)
        except Exception as e:
            print(f"  ERROR [{demo_file}]: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
