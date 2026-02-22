"""
Gate test: Reference pack integrity (Rule RP1).

Verifies that every ref pack directory has a valid manifest and that
all listed JSON files exist with correct SHA256 checksums.

See DEMO_STORE_SPEC.md §S10.5.
"""

import hashlib
import json
from pathlib import Path

import pytest

from quantumvitas.core.resources import get_resources_dir

REF_PACKS_DIR = get_resources_dir() / "demo_projects" / "ref_packs"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_ref_packs():
    """Collect all ref pack directories that have a manifest."""
    if not REF_PACKS_DIR.exists():
        return []
    return sorted(
        d for d in REF_PACKS_DIR.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


class TestRefPackIntegrity:
    """Gate: every ref pack must be well-formed and checksums must match."""

    def test_ref_packs_dir_exists(self):
        """The ref_packs directory must exist (may be empty)."""
        assert REF_PACKS_DIR.exists(), (
            f"ref_packs dir missing: {REF_PACKS_DIR}\n"
            f"Run: mkdir -p {REF_PACKS_DIR}"
        )

    def test_no_orphan_directories(self):
        """Every subdirectory of ref_packs/ must have a manifest.json."""
        if not REF_PACKS_DIR.exists():
            pytest.skip("No ref_packs directory")
        orphans = [
            d.name for d in REF_PACKS_DIR.iterdir()
            if d.is_dir() and not (d / "manifest.json").exists()
        ]
        assert not orphans, (
            f"Ref pack directories without manifest.json: {orphans}\n"
            f"Run: python tools/demo_store/generate_ref_packs.py"
        )

    @pytest.mark.parametrize(
        "pack_dir",
        _collect_ref_packs(),
        ids=lambda d: d.name,
    )
    def test_manifest_valid_json(self, pack_dir):
        """Every manifest.json must be valid JSON with required fields."""
        manifest_path = pack_dir / "manifest.json"
        data = json.loads(manifest_path.read_text())

        assert "demo_slug" in data, f"Missing demo_slug in {manifest_path}"
        assert "engine" in data, f"Missing engine in {manifest_path}"
        assert "object_types" in data, f"Missing object_types in {manifest_path}"
        assert isinstance(data["object_types"], dict), (
            f"object_types must be a dict in {manifest_path}"
        )

    @pytest.mark.parametrize(
        "pack_dir",
        _collect_ref_packs(),
        ids=lambda d: d.name,
    )
    def test_all_files_exist(self, pack_dir):
        """Every file listed in manifest must exist."""
        manifest = json.loads((pack_dir / "manifest.json").read_text())
        missing = []
        for obj_type, entry in manifest.get("object_types", {}).items():
            data_file = pack_dir / entry["file"]
            if not data_file.exists():
                missing.append(f"{obj_type}: {entry['file']}")
        assert not missing, (
            f"Missing ref pack files in {pack_dir.name}: {missing}\n"
            f"Run: python tools/demo_store/generate_ref_packs.py"
        )

    @pytest.mark.parametrize(
        "pack_dir",
        _collect_ref_packs(),
        ids=lambda d: d.name,
    )
    def test_checksums_match(self, pack_dir):
        """SHA256 checksums in manifest must match actual file content."""
        manifest = json.loads((pack_dir / "manifest.json").read_text())
        mismatches = []
        for obj_type, entry in manifest.get("object_types", {}).items():
            data_file = pack_dir / entry["file"]
            if not data_file.exists():
                continue
            actual = _sha256(data_file)
            expected = entry.get("sha256", "")
            if actual != expected:
                mismatches.append(
                    f"{obj_type}: expected {expected[:12]}..., got {actual[:12]}..."
                )
        assert not mismatches, (
            f"Checksum mismatches in {pack_dir.name}: {mismatches}\n"
            f"Run: python tools/demo_store/generate_ref_packs.py"
        )

    @pytest.mark.parametrize(
        "pack_dir",
        _collect_ref_packs(),
        ids=lambda d: d.name,
    )
    def test_json_loadable(self, pack_dir):
        """Every JSON file in the ref pack must be valid JSON."""
        manifest = json.loads((pack_dir / "manifest.json").read_text())
        errors = []
        for obj_type, entry in manifest.get("object_types", {}).items():
            data_file = pack_dir / entry["file"]
            if not data_file.exists():
                continue
            try:
                json.loads(data_file.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"{obj_type}: {e}")
        assert not errors, f"Invalid JSON in {pack_dir.name}: {errors}"
