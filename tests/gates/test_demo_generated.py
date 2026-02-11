"""
Gate: S8.1 — Every demo .yml must be produced by the translator.

Verifies:
1. Every .yml in resources/demo_projects/ has a manifest entry.
2. The output_checksum in manifest matches actual file checksum.
3. No .yml file exists without a manifest entry.
"""

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
DEMO_DIR = REPO_ROOT / "resources" / "demo_projects"
MANIFEST_PATH = DEMO_DIR / ".generator_manifest.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_manifest_exists():
    """Generator manifest must exist."""
    assert MANIFEST_PATH.exists(), (
        f"Missing .generator_manifest.json at {MANIFEST_PATH}. "
        f"Run: python tools/demo_store/generate_all.py"
    )


def test_all_demos_have_manifest_entry():
    """Every .yml in demo_projects/ must have a manifest entry."""
    if not MANIFEST_PATH.exists():
        pytest.skip("No manifest file")

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    demos = manifest.get("demos", {})
    yml_files = sorted(DEMO_DIR.glob("*.yml"))

    missing = []
    for yml_path in yml_files:
        slug = yml_path.stem
        if slug not in demos:
            missing.append(yml_path.name)

    assert not missing, (
        f"Demo files without manifest entries: {missing}. "
        f"Run: python tools/demo_store/generate_all.py"
    )


def test_no_orphan_manifest_entries():
    """Every manifest entry must have a corresponding .yml file."""
    if not MANIFEST_PATH.exists():
        pytest.skip("No manifest file")

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    demos = manifest.get("demos", {})
    orphans = []

    for slug in demos:
        yml_path = DEMO_DIR / f"{slug}.yml"
        if not yml_path.exists():
            orphans.append(slug)

    assert not orphans, (
        f"Manifest entries without .yml files: {orphans}. "
        f"Run: python tools/demo_store/generate_all.py"
    )


def test_manifest_checksums_match():
    """Manifest output_checksum must match actual file checksums."""
    if not MANIFEST_PATH.exists():
        pytest.skip("No manifest file")

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    demos = manifest.get("demos", {})
    mismatches = []

    for slug, entry in demos.items():
        yml_path = DEMO_DIR / f"{slug}.yml"
        if not yml_path.exists():
            continue

        expected_checksum = entry.get("output_checksum", "")
        actual_checksum = _sha256_file(yml_path)

        if expected_checksum and expected_checksum != actual_checksum:
            mismatches.append(
                f"{slug}: manifest={expected_checksum[:12]}... actual={actual_checksum[:12]}..."
            )

    assert not mismatches, (
        f"Checksum mismatches (demos were hand-edited?):\n"
        + "\n".join(f"  {m}" for m in mismatches)
        + "\nRun: python tools/demo_store/generate_all.py"
    )
