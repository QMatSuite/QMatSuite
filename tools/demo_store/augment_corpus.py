#!/usr/bin/env python3
"""
Augment all corpus case.yaml files with demo store metadata fields.

Adds: demo_eligible, step_type_gen, step_type_spec, required_engine,
availability, exclusion_reason, demo_slug, asset_policy, asset_requirements.

Also generates corpus_index.yaml.

Usage: python tools/demo_store/augment_corpus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_ROOT = REPO_ROOT / "tests" / "inputformat" / "samples"

# ── Demo-eligible cases: engine -> {dir_name -> demo_slug} ──
DEMO_ELIGIBLE = {
    "vasp": {
        "si_scf": "vasp_si_scf",
        "si_relax": "vasp_si_relax",
        "fe_magnetic": "vasp_fe_magnetic",
        "si_bands": "vasp_si_bands",
    },
    "abinit": {
        "si_scf": "abinit_si_scf",
        "si_relax": "abinit_si_relax",
    },
    "cp2k": {
        "h2o_energy": "cp2k_h2o_energy",
        "si_relax": "cp2k_si_relax",
    },
    "gaussian": {
        "water_hf_sp": "gaussian_water_hf",
        "water_b3lyp_opt": "gaussian_water_opt",
    },
    "lammps": {
        "melt_lj_nve": "lammps_lj_melt",
        "minimize_2d_lj": "lammps_lj_minimize",
    },
    "orca": {
        "water_sp": "orca_water_sp",
        "methane_freq": "orca_methane_freq",
        "formaldehyde_tddft": "orca_formaldehyde_tddft",
    },
    "siesta": {
        "si_scf": "siesta_si_scf",
        "si_relax": "siesta_si_relax",
    },
    "xtb": {
        "water_opt": "xtb_water_opt",
        "water_md": "xtb_water_md",
    },
    "qmcpack": {
        "he_vmc_sto": "qmcpack_he_vmc",
    },
    "yambo": {
        "si_gw_ppa": "yambo_si_gw",
    },
    "w90": {},  # W90 demos handled via QE multi-step corpus, not standalone W90 corpus
}

# ── Workflow tag -> step_type_gen mapping ──
TAG_TO_GEN = {
    "scf": "scf",
    "energy": "scf",
    "electronic": "scf",
    "relax": "relax",
    "opt": "relax",
    "geo_opt": "relax",
    "cell_opt": "relax",
    "vc_relax": "relax",
    "bands": "bandspw",
    "dos": "dos",
    "pdos": "dos",
    "nscf": "nscf",
    "md": "md",
    "nve": "md",
    "nvt": "md",
    "npt": "md",
    "phonon": "ph",
    "dfpt": "ph",
    "tddft": "td",
    "td": "td",
    "frequencies": "freq",
    "freq": "freq",
    "gw": "gw",
    "bse": "bse",
    "optics": "optics",
    "vmc": "vmc",
    "dmc": "dmc",
    "wfopt": "wfopt",
    "wannierise": "wannier",
    "band_interpolation": "wannier",
    "minimize": "minimize",
    "scan": "relax",
    "ts": "relax",
    "solvation": "scf",
    "basic": "wannier",
    "spin": "scf",
    "hubbard": "scf",
    "vdw": "scf",
    "hybrid": "scf",
    "soc": "scf",
    "magnetic": "scf",
    "ionic": "relax",
}

# ── Engine-specific step_type_gen overrides ──
# Some engines need special handling for certain workflow_tags
ENGINE_GEN_OVERRIDES = {
    "lammps": {
        "minimize": "minimize",
        "nve": "md",
        "nvt": "md",
        "npt": "md",
        "md": "md",
        "relax": "relax",
        "equilibrate": "md",
    },
    "orca": {
        "tddft": "td",
        "freq": "freq",
        "scf": "scf",
        "opt": "relax",
        "dft": "scf",
        "small-molecule": None,  # Not a gen type
        "casscf": "scf",
        "uks": "scf",
    },
    "gaussian": {
        "tddft": "td",
        "freq": "freq",
        "mp2": "mp2",
        "scan": "relax",
        "ts": "relax",
        "uhf": "scf",
        "hf": "hf",
    },
    "qmcpack": {
        "vmc": "vmc",
        "dmc": "dmc",
        "optimization": "wfopt",
        "all_electron": "vmc",
    },
    "yambo": {
        "gw": "gw",
        "bse": "bse",
        "optics": "optics",
        "setup": "setup",
    },
    "w90": {
        "wannierise": "wannier",
        "band_interpolation": "wannier",
        "basic": "wannier",
    },
    "cp2k": {
        "geo_opt": "relax",
        "cell_opt": "relax",
        "tddft": "scf",
    },
    "abinit": {
        "dfpt": "scf",
        "vc_relax": "relax",
        "paw": "scf",
    },
    "vasp": {
        "vc_relax": "relax",
    },
}

# ── Engine availability ──
ENGINE_AVAILABILITY = {
    "qe": "open_source",
    "vasp": "requires_local_install",
    "abinit": "open_source",
    "cp2k": "open_source",
    "orca": "requires_local_install",
    "gaussian": "requires_local_install",
    "lammps": "open_source",
    "siesta": "open_source",
    "w90": "open_source",
    "gpaw": "open_source",
    "psi4": "open_source",
    "pyscf": "open_source",
    "xtb": "bundled",
    "qmcpack": "open_source",
    "yambo": "open_source",
}

# ── Asset policy by engine ──
ENGINE_ASSET_POLICY = {
    "qe": "redistributable",
    "vasp": "proprietary",
    "abinit": "redistributable",
    "cp2k": "none",
    "orca": "none",
    "gaussian": "none",
    "lammps": "none",
    "siesta": "none",
    "w90": "none",
    "gpaw": "none",
    "psi4": "none",
    "pyscf": "none",
    "xtb": "none",
    "qmcpack": "none",
    "yambo": "none",
}


def infer_step_type_gen(engine: str, workflow_tags: list[str]) -> str:
    """Infer step_type_gen from engine and workflow_tags."""
    overrides = ENGINE_GEN_OVERRIDES.get(engine, {})

    # Try engine-specific overrides first
    for tag in workflow_tags:
        if tag in overrides:
            val = overrides[tag]
            if val is not None:
                return val

    # Fall back to general mapping
    for tag in workflow_tags:
        if tag in TAG_TO_GEN:
            return TAG_TO_GEN[tag]

    return "scf"  # default


def infer_step_type_spec(engine: str, step_type_gen: str) -> str:
    """Build step_type_spec from engine prefix and gen type."""
    return f"{engine}_{step_type_gen}"


def augment_case_yaml(case_dir: Path, engine: str) -> dict:
    """Read, augment, and write a case.yaml file. Returns augmented data."""
    case_path = case_dir / "case.yaml"
    with open(case_path, "r") as f:
        data = yaml.safe_load(f)

    dir_name = case_dir.name
    case_id = data.get("case_id", dir_name)
    workflow_tags = data.get("workflow_tags", [])
    species = data.get("species", [])

    # Infer step types
    step_type_gen = infer_step_type_gen(engine, workflow_tags)
    step_type_spec = infer_step_type_spec(engine, step_type_gen)

    # Check demo eligibility
    eligible_map = DEMO_ELIGIBLE.get(engine, {})
    is_eligible = dir_name in eligible_map
    demo_slug = eligible_map.get(dir_name)

    # Required engine
    required_engine = engine

    # Availability
    availability = ENGINE_AVAILABILITY.get(engine, "open_source")

    # Asset policy
    asset_policy = ENGINE_ASSET_POLICY.get(engine, "none")
    if not is_eligible:
        asset_policy = ENGINE_ASSET_POLICY.get(engine, "none")

    # Build new fields
    data["demo_eligible"] = is_eligible
    data["step_type_gen"] = step_type_gen
    data["step_type_spec"] = step_type_spec
    data["required_engine"] = required_engine
    data["availability"] = availability

    if is_eligible:
        data["demo_slug"] = demo_slug
        data["asset_policy"] = asset_policy

        # Asset requirements for QE (redistributable pseudos)
        if engine == "qe" and asset_policy == "redistributable":
            pseudo_files = list(case_dir.glob("*.UPF")) + list(case_dir.glob("*.upf"))
            if pseudo_files:
                data["asset_requirements"] = {
                    "pseudopotentials": [
                        {"file": p.name, "element": p.stem.split(".")[0], "source": "src/quantumvitas/resources/pseudo"}
                        for p in pseudo_files
                    ]
                }

        # Asset requirements for VASP (proprietary POTCAR)
        if engine == "vasp" and asset_policy == "proprietary":
            data["asset_requirements"] = {
                "proprietary": [
                    {
                        "type": "potcar",
                        "description": f"VASP PAW PBE pseudopotentials for {', '.join(species)}",
                        "species": species,
                        "obtain_from": "VASP POTCAR library (requires VASP license)",
                    }
                ]
            }

        # Recommended analysis
        if "recommended_analysis" not in data:
            if step_type_gen in ("scf", "relax", "minimize"):
                data["recommended_analysis"] = "scf"
            elif step_type_gen in ("bandspw", "bands"):
                data["recommended_analysis"] = "bands"
            elif step_type_gen == "dos":
                data["recommended_analysis"] = "dos"
            elif step_type_gen == "md":
                data["recommended_analysis"] = "trajectory"
            else:
                data["recommended_analysis"] = "energy"

        data["exclusion_reason"] = None
    else:
        data["exclusion_reason"] = "Parser/writer test case only"
        data.pop("demo_slug", None)

    # Write back
    with open(case_path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return data


def main():
    """Augment all corpus case.yaml files."""
    total = 0
    augmented = 0
    eligible = 0

    for engine_dir in sorted(CORPUS_ROOT.iterdir()):
        if not engine_dir.is_dir():
            continue
        engine = engine_dir.name
        if engine.startswith(".") or engine == "__pycache__":
            continue

        # Skip non-engine directories
        if engine in ("corpus_index.yaml",):
            continue

        for case_dir in sorted(engine_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            case_yaml = case_dir / "case.yaml"
            if not case_yaml.exists():
                continue

            total += 1
            try:
                data = augment_case_yaml(case_dir, engine)
                augmented += 1
                if data.get("demo_eligible"):
                    eligible += 1
                print(f"  [{engine}/{case_dir.name}] gen={data['step_type_gen']} "
                      f"spec={data['step_type_spec']} eligible={data['demo_eligible']}")
            except Exception as e:
                print(f"  ERROR [{engine}/{case_dir.name}]: {e}", file=sys.stderr)

    print(f"\nDone: {augmented}/{total} augmented, {eligible} demo-eligible")


if __name__ == "__main__":
    main()
