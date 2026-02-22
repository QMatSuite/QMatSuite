#!/usr/bin/env python3
"""
Generate reference packs for demo projects.

Reads golden output fixtures from tests/data/analysis_* directories, runs
analysis providers (convergence/dos/bands), and serializes CanonicalPrimitiveBundle
as JSON ref packs.

Usage: python tools/demo_store/generate_ref_packs.py [--dry-run] [--prune-stale]

Ref packs are stored at src/qmatsuite/resources/demo_projects/ref_packs/<demo_slug>/.
See DEMO_STORE_SPEC.md §S10.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

TESTS_DATA = REPO_ROOT / "tests" / "data"
RESOURCES_DIR = REPO_ROOT / "src" / "qmatsuite" / "resources"
REF_PACKS_DIR = RESOURCES_DIR / "demo_projects" / "ref_packs"
DEMO_PROJECTS_DIR = RESOURCES_DIR / "demo_projects"
GENERATOR_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Golden output map: demo_slug -> list of {dir, type, engine}
#
# "type" is the analysis provider type (convergence/dos/bands).
# "dir" is relative to tests/data/.
# "engine" is the engine key for the parser registry.
# ---------------------------------------------------------------------------
GOLDEN_OUTPUT_MAP: Dict[str, List[Dict[str, str]]] = {
    # ---- VASP demos ----
    "vasp_si_scf": [
        {"dir": "analysis_vasp_convergence", "type": "convergence", "engine": "vasp"},
    ],
    "vasp_si_relax": [
        {"dir": "analysis_vasp_convergence", "type": "convergence", "engine": "vasp"},
    ],
    "vasp_fe_magnetic": [
        {"dir": "analysis_vasp_convergence", "type": "convergence", "engine": "vasp"},
    ],
    "vasp_si_bands": [
        {"dir": "analysis_vasp_bands", "type": "bands", "engine": "vasp"},
    ],
    "vasp_si_dos": [
        {"dir": "analysis_vasp_dos", "type": "dos", "engine": "vasp"},
    ],
    # ---- QE demos ----
    "qe_si_scf": [
        {"dir": "analysis_scf", "type": "convergence", "engine": "qe"},
    ],
    "qe_si_vc_relax": [
        {"dir": "analysis_scf", "type": "convergence", "engine": "qe"},
    ],
    "qe_si_bulk_modulus": [
        {"dir": "analysis_scf", "type": "convergence", "engine": "qe"},
    ],
    "qe_si_phonon": [
        {"dir": "analysis_scf", "type": "convergence", "engine": "qe"},
    ],
    "qe_nmr_gipaw": [
        {"dir": "analysis_scf", "type": "convergence", "engine": "qe"},
    ],
    "qe_al_dos": [
        {"dir": "analysis_qe_dos", "type": "dos", "engine": "qe"},
    ],
    "qe_fe_scf": [
        {"dir": "analysis_qe_dos", "type": "dos", "engine": "qe"},
    ],
    "qe_si_dos_alt": [
        {"dir": "analysis_qe_dos", "type": "dos", "engine": "qe"},
    ],
    "qe_graphene_bands": [
        {"dir": "analysis_bands", "type": "bands", "engine": "qe"},
    ],
    "qe_si_bands_alt": [
        {"dir": "analysis_bands", "type": "bands", "engine": "qe"},
    ],
    "si_bands_demo": [
        {"dir": "analysis_bands", "type": "bands", "engine": "qe"},
    ],
    "si_dos_demo": [
        {"dir": "analysis_qe_dos", "type": "dos", "engine": "qe"},
    ],
    # ---- ABINIT demos ----
    "abinit_si_scf": [
        {"dir": "analysis_abinit_dos", "type": "convergence", "engine": "abinit"},
    ],
    "abinit_si_relax": [
        {"dir": "analysis_abinit_dos", "type": "convergence", "engine": "abinit"},
    ],
    "abinit_si_bands": [
        {"dir": "analysis_abinit_bands", "type": "bands", "engine": "abinit"},
    ],
    # ---- Siesta demos ----
    "siesta_si_scf": [
        {"dir": "analysis_siesta_dos", "type": "convergence", "engine": "siesta"},
    ],
    "siesta_si_relax": [
        {"dir": "analysis_siesta_dos", "type": "convergence", "engine": "siesta"},
    ],
    "siesta_si_bands": [
        {"dir": "analysis_siesta_bands", "type": "bands", "engine": "siesta"},
    ],
    # ---- CP2K demos ----
    "cp2k_h2o_energy": [
        {"dir": "analysis_cp2k_dos", "type": "convergence", "engine": "cp2k"},
    ],
    "cp2k_h2o_geo_opt": [
        {"dir": "analysis_cp2k_dos", "type": "convergence", "engine": "cp2k"},
    ],
    "cp2k_si_relax": [
        {"dir": "analysis_cp2k_dos", "type": "convergence", "engine": "cp2k"},
    ],
    # ---- GPAW demos ----
    "gpaw_si_bands": [
        {"dir": "analysis_gpaw_bands", "type": "bands", "engine": "gpaw"},
    ],
}


def _compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


_providers_loaded = False


def _ensure_providers_loaded():
    """Import all parser modules so @register_parser decorators fire."""
    global _providers_loaded
    if _providers_loaded:
        return
    import importlib

    engines = [
        "vasp", "qe", "abinit", "cp2k", "siesta", "gpaw",
        "gaussian", "lammps", "orca", "xtb", "qmcpack",
        "yambo", "w90", "psi4", "pyscf",
    ]
    # Import parsers package for each engine (triggers all @register_parser)
    for eng in engines:
        try:
            importlib.import_module(f"qmatsuite.drivers.{eng}.parsers")
        except ImportError:
            pass
        # Also try individual parser modules
        for obj_type in ("output", "convergence", "dos", "bands"):
            try:
                importlib.import_module(
                    f"qmatsuite.drivers.{eng}.parsers.{obj_type}"
                )
            except ImportError:
                pass
    _providers_loaded = True


def _try_parse_bundle(
    engine: str,
    provider_type: str,
    golden_dir: Path,
) -> Optional[Dict[str, Any]]:
    """
    Parse golden output files using the appropriate analysis provider.

    Returns CanonicalPrimitiveBundle.to_dict(), or None if parsing fails.
    """
    try:
        from qmatsuite.parsers.registry import get_parser
        from qmatsuite.core.analysis.evidence import EvidenceBundle

        parser_cls = get_parser(engine, provider_type)
        if parser_cls is None:
            print(f"    No {provider_type} parser for {engine}")
            return None

        parser = parser_cls()

        # Check can_parse if available
        if hasattr(parser, "can_parse") and not parser.can_parse(golden_dir):
            print(f"    Parser {engine}/{provider_type} cannot parse {golden_dir.name}")
            return None

        # Build minimal evidence bundle
        evidence = EvidenceBundle(
            primary_raw_dir=golden_dir,
            calc_dir=golden_dir,
            run_ulid="REFPACK",
            calc_ulid="REFPACK",
            step_ulids=["REFPACK"],
            gen_steps=["scf"],
            engine_name=engine,
            evidence_steps=[],
        )

        # Parse -> AnalysisObject -> CanonicalPrimitiveBundle -> dict
        analysis_obj = parser.parse(evidence)
        if analysis_obj is None:
            print(f"    Parser returned None for {engine}/{provider_type}")
            return None

        bundle = analysis_obj.to_primitives()
        return bundle.to_dict()

    except Exception as e:
        print(f"    Parse error for {engine}/{provider_type}: {e}")
        return None


def generate_ref_pack(
    demo_slug: str,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Generate a ref pack for a single demo using GOLDEN_OUTPUT_MAP.

    Returns manifest entry dict, or None if no output data available.
    """
    _ensure_providers_loaded()

    if demo_slug not in GOLDEN_OUTPUT_MAP:
        return None

    object_types: Dict[str, Dict[str, str]] = {}
    data_blobs: Dict[str, bytes] = {}

    for entry in GOLDEN_OUTPUT_MAP[demo_slug]:
        golden_dir = TESTS_DATA / entry["dir"]
        obj_type = entry["type"]
        engine = entry["engine"]

        if not golden_dir.exists():
            print(f"    Golden dir not found: {golden_dir}")
            continue

        bundle_dict = _try_parse_bundle(engine, obj_type, golden_dir)
        if bundle_dict is None:
            continue

        json_bytes = json.dumps(bundle_dict, indent=2, default=str).encode("utf-8")
        fname = f"{obj_type}.json"
        object_types[obj_type] = {
            "file": fname,
            "sha256": _compute_sha256(json_bytes),
        }
        data_blobs[fname] = json_bytes

    if not object_types:
        return None

    if dry_run:
        print(f"    Would write ref pack: {', '.join(object_types.keys())}")
        return {
            "demo_slug": demo_slug,
            "object_types": list(object_types.keys()),
        }

    # Write ref pack files
    pack_dir = REF_PACKS_DIR / demo_slug
    pack_dir.mkdir(parents=True, exist_ok=True)

    # Clean old files first
    for old_file in pack_dir.iterdir():
        old_file.unlink()

    for fname, blob in data_blobs.items():
        (pack_dir / fname).write_bytes(blob)

    # Write manifest
    manifest = {
        "demo_slug": demo_slug,
        "engine": GOLDEN_OUTPUT_MAP[demo_slug][0]["engine"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": GENERATOR_VERSION,
        "object_types": object_types,
    }
    manifest_json = json.dumps(manifest, indent=2)
    (pack_dir / "manifest.json").write_text(manifest_json + "\n")

    return manifest


def main():
    dry_run = "--dry-run" in sys.argv
    prune_stale = "--prune-stale" in sys.argv

    print(f"Golden output map: {len(GOLDEN_OUTPUT_MAP)} entries")
    print(f"Ref packs dir: {REF_PACKS_DIR}")
    if dry_run:
        print("DRY RUN — no files will be written\n")
    elif prune_stale:
        print("PRUNE mode enabled — stale ref packs will be removed\n")
    else:
        print("SAFE mode — stale ref packs are preserved (pass --prune-stale to remove)\n")

    # Remove ref packs that are no longer in the map only when explicitly requested.
    # The hardcoded map is intentionally partial and must not silently delete
    # canonical ref packs generated by other workflows.
    if not dry_run and prune_stale and REF_PACKS_DIR.exists():
        for existing in REF_PACKS_DIR.iterdir():
            if existing.is_dir() and existing.name not in GOLDEN_OUTPUT_MAP:
                print(f"  Removing stale ref pack: {existing.name}")
                for f in existing.iterdir():
                    f.unlink()
                existing.rmdir()

    generated = 0
    failed = 0

    for demo_slug in sorted(GOLDEN_OUTPUT_MAP.keys()):
        entries = GOLDEN_OUTPUT_MAP[demo_slug]
        types_str = ", ".join(e["type"] for e in entries)
        engine = entries[0]["engine"]
        print(f"  [{demo_slug}] ({engine}) target: {types_str}")

        result = generate_ref_pack(demo_slug, dry_run=dry_run)

        if result:
            generated += 1
            types = (
                list(result["object_types"].keys())
                if isinstance(result.get("object_types"), dict)
                else result.get("object_types", [])
            )
            print(f"    -> {', '.join(types)}")
        else:
            print(f"    -> FAILED")
            failed += 1

    print(f"\nGenerated: {generated} ref packs, Failed: {failed}")
    print(f"Total in map: {len(GOLDEN_OUTPUT_MAP)}")
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
