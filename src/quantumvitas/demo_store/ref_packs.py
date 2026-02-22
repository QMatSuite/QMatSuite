"""
Reference pack loader for demo projects.

Ref packs are pre-computed analysis bundles stored as JSON files in
src/quantumvitas/resources/demo_projects/ref_packs/<demo_slug>/. Each ref pack contains
a manifest.json and one or more analysis JSON files (bands.json, dos.json,
convergence.json, etc.).

See DEMO_STORE_SPEC.md §S10 for the specification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _ref_packs_dir() -> Path:
    """Return the root ref packs directory."""
    from quantumvitas.core.resources import get_resources_dir
    return get_resources_dir() / "demo_projects" / "ref_packs"


def load_ref_pack_manifest(demo_id: str) -> Optional[Dict[str, Any]]:
    """
    Load the manifest for a ref pack.

    Args:
        demo_id: Demo slug (e.g., "vasp_si_scf")

    Returns:
        Manifest dict, or None if no ref pack exists.
    """
    manifest_path = _ref_packs_dir() / demo_id / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())


def load_ref_pack(demo_id: str, object_type: str) -> Optional[Dict[str, Any]]:
    """
    Load a specific analysis bundle from a ref pack.

    Args:
        demo_id: Demo slug (e.g., "vasp_si_scf")
        object_type: Analysis type (e.g., "bands", "dos", "convergence")

    Returns:
        Deserialized analysis bundle dict, or None if not available.
    """
    manifest = load_ref_pack_manifest(demo_id)
    if manifest is None:
        return None

    object_types = manifest.get("object_types", {})
    entry = object_types.get(object_type)
    if entry is None:
        return None

    data_file = _ref_packs_dir() / demo_id / entry["file"]
    if not data_file.exists():
        return None

    return json.loads(data_file.read_text())


def list_ref_pack_types(demo_id: str) -> List[str]:
    """
    List available analysis types for a demo's ref pack.

    Args:
        demo_id: Demo slug (e.g., "vasp_si_scf")

    Returns:
        List of available object type names (e.g., ["bands", "convergence"]).
        Empty list if no ref pack exists.
    """
    manifest = load_ref_pack_manifest(demo_id)
    if manifest is None:
        return []
    return list(manifest.get("object_types", {}).keys())


def list_all_ref_packs() -> List[str]:
    """
    List all demo slugs that have ref packs.

    Returns:
        List of demo slugs with ref packs.
    """
    ref_dir = _ref_packs_dir()
    if not ref_dir.exists():
        return []
    return sorted(
        d.name
        for d in ref_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
