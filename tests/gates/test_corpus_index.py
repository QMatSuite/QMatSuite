"""
Gate: S8.2 — Corpus index consistency.

Verifies:
1. Every corpus dir with case.yaml has a corpus_index entry.
2. No orphan entries in corpus_index.yaml.
3. demo_slug uniqueness among eligible entries.
4. case.yaml and corpus_index.yaml agree on key fields.
5. Redistributable assets exist in-repo for eligible entries.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
CORPUS_ROOT = REPO_ROOT / "tests" / "inputformat" / "samples"
INDEX_PATH = CORPUS_ROOT / "corpus_index.yaml"


def _load_index():
    if not INDEX_PATH.exists():
        pytest.skip("No corpus_index.yaml")
    with open(INDEX_PATH) as f:
        return yaml.safe_load(f)


def _scan_corpus_dirs():
    """Find all (engine, dir_name) pairs that have case.yaml."""
    pairs = set()
    for engine_dir in CORPUS_ROOT.iterdir():
        if not engine_dir.is_dir() or engine_dir.name.startswith("."):
            continue
        for case_dir in engine_dir.iterdir():
            if case_dir.is_dir() and (case_dir / "case.yaml").exists():
                pairs.add((engine_dir.name, case_dir.name))
    return pairs


def test_corpus_index_exists():
    """Corpus index must exist."""
    assert INDEX_PATH.exists(), (
        f"Missing corpus_index.yaml at {INDEX_PATH}. "
        f"Run: python tools/demo_store/generate_corpus_index.py"
    )


def test_no_orphan_dirs():
    """Every corpus dir with case.yaml must have an index entry (Rule CI1)."""
    index = _load_index()
    entries = index.get("entries", [])

    indexed = {(e["engine"], e["dir_name"]) for e in entries}
    actual = _scan_corpus_dirs()

    orphan_dirs = actual - indexed
    assert not orphan_dirs, (
        f"Corpus dirs without index entries: {sorted(orphan_dirs)}. "
        f"Run: python tools/demo_store/generate_corpus_index.py"
    )


def test_no_orphan_entries():
    """Every index entry must have a corresponding corpus dir."""
    index = _load_index()
    entries = index.get("entries", [])

    actual = _scan_corpus_dirs()
    orphan_entries = []

    for e in entries:
        key = (e["engine"], e["dir_name"])
        if key not in actual:
            orphan_entries.append(key)

    assert not orphan_entries, (
        f"Index entries without corpus dirs: {sorted(orphan_entries)}"
    )


def test_demo_slug_uniqueness():
    """demo_slug must be globally unique among eligible entries (Rule CI5)."""
    index = _load_index()
    entries = index.get("entries", [])

    slugs = {}
    duplicates = []

    for e in entries:
        if not e.get("demo_eligible"):
            continue
        slug = e.get("demo_slug")
        if slug in slugs:
            duplicates.append(f"{slug}: {slugs[slug]} and {e['engine']}/{e['dir_name']}")
        else:
            slugs[slug] = f"{e['engine']}/{e['dir_name']}"

    assert not duplicates, f"Duplicate demo_slugs: {duplicates}"


def test_case_yaml_agreement():
    """case.yaml and corpus_index must agree on key fields (Rule CI6)."""
    index = _load_index()
    entries = index.get("entries", [])

    disagreements = []

    for entry in entries:
        engine = entry["engine"]
        dir_name = entry["dir_name"]
        case_dir = CORPUS_ROOT / engine / dir_name
        case_yaml = case_dir / "case.yaml"

        if not case_yaml.exists():
            continue

        with open(case_yaml) as f:
            case_data = yaml.safe_load(f)

        for field in ("demo_eligible", "demo_slug", "engine", "case_id"):
            case_val = case_data.get(field)
            index_val = entry.get(field)
            if case_val != index_val:
                disagreements.append(
                    f"{engine}/{dir_name}: {field} case={case_val!r} index={index_val!r}"
                )

    assert not disagreements, (
        f"case.yaml/index disagreements:\n" + "\n".join(f"  {d}" for d in disagreements)
    )


def test_redistributable_assets_present():
    """For eligible redistributable entries, required assets must exist in-repo."""
    index = _load_index()
    entries = index.get("entries", [])

    missing = []

    for entry in entries:
        if not entry.get("demo_eligible"):
            continue
        if entry.get("asset_policy") != "redistributable":
            continue

        for asset in entry.get("required_assets", []):
            if not asset.get("vendored", True):
                continue
            asset_file = asset.get("file", "")
            source = asset.get("source", "")
            if asset_file and source:
                asset_path = REPO_ROOT / source / asset_file
                if not asset_path.exists():
                    missing.append(
                        f"{entry['engine']}/{entry['dir_name']}: {source}/{asset_file}"
                    )

    assert not missing, (
        f"Missing redistributable assets:\n" + "\n".join(f"  {m}" for m in missing)
    )
