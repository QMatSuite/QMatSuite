#!/usr/bin/env python3
"""
Generate corpus_index.yaml from all case.yaml files.

Reads every tests/inputformat/samples/<engine>/<dir>/case.yaml
and produces a unified corpus_index.yaml per S3.2 schema.

Usage: python tools/demo_store/generate_corpus_index.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_ROOT = REPO_ROOT / "tests" / "inputformat" / "samples"


def main():
    entries = []
    engines_found = set()

    for engine_dir in sorted(CORPUS_ROOT.iterdir()):
        if not engine_dir.is_dir():
            continue
        engine = engine_dir.name
        if engine.startswith(".") or engine == "__pycache__":
            continue

        engines_found.add(engine)

        for case_dir in sorted(engine_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            case_yaml = case_dir / "case.yaml"
            if not case_yaml.exists():
                continue

            with open(case_yaml) as f:
                data = yaml.safe_load(f)

            case_id = data.get("case_id", case_dir.name)
            dir_name = case_dir.name
            is_eligible = data.get("demo_eligible", False)
            demo_slug = data.get("demo_slug") if is_eligible else None
            asset_policy = data.get("asset_policy", "none") if is_eligible else "none"
            required_engine = data.get("required_engine", engine)
            availability = data.get("availability", "open_source")
            exclusion_reason = data.get("exclusion_reason")

            # Build required_assets
            required_assets = []
            asset_reqs = data.get("asset_requirements", {})
            for pseudo in asset_reqs.get("pseudopotentials", []):
                required_assets.append({
                    "type": "pseudopotential",
                    "file": pseudo.get("file", ""),
                    "element": pseudo.get("element", ""),
                    "source": pseudo.get("source", "src/qmatsuite/resources/pseudo"),
                    "vendored": True,
                })
            for prop in asset_reqs.get("proprietary", []):
                required_assets.append({
                    "type": prop.get("type", ""),
                    "species": prop.get("species", []),
                    "source": prop.get("description", ""),
                    "vendored": False,
                    "obtain_from": prop.get("obtain_from", ""),
                })

            entry = {
                "engine": engine,
                "case_id": case_id,
                "dir_name": dir_name,
                "demo_eligible": is_eligible,
                "demo_slug": demo_slug,
                "runnable": True,
                "asset_policy": asset_policy,
                "required_engine": required_engine,
                "availability": availability,
                "required_assets": required_assets,
                "exclusion_reason": exclusion_reason,
                "attribution": data.get("attribution"),
            }

            entries.append(entry)

    # Write corpus_index.yaml
    index = {
        "schema_version": 1,
        "entries": entries,
    }

    index_path = CORPUS_ROOT / "corpus_index.yaml"
    with open(index_path, "w") as f:
        yaml.safe_dump(index, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Summary
    eligible = sum(1 for e in entries if e["demo_eligible"])
    print(f"Generated corpus_index.yaml: {len(entries)} entries ({eligible} demo-eligible)")
    print(f"Engines: {sorted(engines_found)}")


if __name__ == "__main__":
    main()
