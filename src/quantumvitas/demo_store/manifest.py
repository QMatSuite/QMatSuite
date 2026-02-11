"""
Generator manifest for tracking corpus-to-demo mappings and checksums.

The manifest file (.generator_manifest.json) records which corpus cases
produced which demo snapshots, with integrity checksums for change detection.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


GENERATOR_VERSION = "1.0.0"


def _compute_file_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_dir_checksum(dir_path: Path) -> str:
    """Compute a stable checksum of a directory's contents."""
    h = hashlib.sha256()
    for path in sorted(dir_path.rglob("*")):
        if path.is_file():
            rel = path.relative_to(dir_path)
            h.update(str(rel).encode("utf-8"))
            h.update(_compute_file_checksum(path).encode("utf-8"))
    return h.hexdigest()


def read_manifest(demo_dir: Path) -> Dict[str, Any]:
    """
    Read the generator manifest.

    Args:
        demo_dir: Path to resources/demo_projects/

    Returns:
        Parsed manifest dict, or empty structure if not found.
    """
    manifest_path = demo_dir / ".generator_manifest.json"
    if not manifest_path.exists():
        return {
            "generator_version": GENERATOR_VERSION,
            "generated_at": None,
            "corpus_root": "tests/inputformat/samples",
            "corpus_index_checksum": None,
            "demos": {},
        }
    with open(manifest_path, "r") as f:
        return json.load(f)


def write_manifest(
    demo_dir: Path,
    demos: Dict[str, Dict[str, Any]],
    corpus_index_checksum: str,
) -> Path:
    """
    Write the generator manifest.

    Args:
        demo_dir: Path to resources/demo_projects/
        demos: Dict mapping demo_slug -> demo metadata.
        corpus_index_checksum: SHA-256 of corpus_index.yaml.

    Returns:
        Path to written manifest file.
    """
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_root": "tests/inputformat/samples",
        "corpus_index_checksum": corpus_index_checksum,
        "demos": demos,
    }
    manifest_path = demo_dir / ".generator_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")
    return manifest_path


def build_demo_manifest_entry(
    engine: str,
    case_id: str,
    dir_name: str,
    corpus_dir: Path,
    output_file: Path,
    asset_policy: str,
) -> Dict[str, str]:
    """
    Build a manifest entry for one demo.

    Args:
        engine: Engine name.
        case_id: Corpus case ID.
        dir_name: Corpus directory name.
        corpus_dir: Path to the corpus case directory.
        output_file: Path to the generated .yml file.
        asset_policy: Asset policy string.

    Returns:
        Dict with manifest entry fields.
    """
    return {
        "engine": engine,
        "case_id": case_id,
        "dir_name": dir_name,
        "corpus_path": f"tests/inputformat/samples/{engine}/{dir_name}",
        "corpus_checksum": _compute_dir_checksum(corpus_dir),
        "output_file": f"resources/demo_projects/{output_file.name}",
        "output_checksum": _compute_file_checksum(output_file),
        "asset_policy": asset_policy,
    }
