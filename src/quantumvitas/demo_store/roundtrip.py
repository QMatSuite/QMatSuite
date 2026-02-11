"""
Roundtrip equivalence verification for demo snapshots.

Per S6.3: two snapshots are content-equivalent if they agree on all fields
after stripping ULIDs, paths, managed keys, and demo gallery metadata.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Runtime-managed parameter keys that may differ between snapshots
# These are injected/overridden by engine materialization at runtime
MANAGED_KEYS_BY_ENGINE = {
    "qe": {"outdir", "pseudo_dir", "wfcdir", "prefix", "restart_mode"},
    "vasp": {"SYSTEM"},
    "abinit": {},
    "cp2k": {"PROJECT_NAME"},
    "orca": {},
    "gaussian": {},
    "lammps": {},
    "siesta": {"SystemLabel"},
    "w90": {},
    "gpaw": {},
    "psi4": {},
    "pyscf": {},
    "xtb": {},
    "qmcpack": {},
    "yambo": {},
}


@dataclass
class RoundtripReport:
    """Result of roundtrip equivalence check."""
    equivalent: bool
    differences: List[str] = field(default_factory=list)


def _strip_ulids(data: Any) -> Any:
    """Recursively strip 'ulid' keys from nested dicts."""
    if isinstance(data, dict):
        return {k: _strip_ulids(v) for k, v in data.items() if k != "ulid"}
    if isinstance(data, list):
        return [_strip_ulids(item) for item in data]
    return data


def _strip_paths(data: Any) -> Any:
    """Recursively strip 'path' keys from meta blocks."""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k == "meta" and isinstance(v, dict):
                result[k] = {mk: mv for mk, mv in _strip_paths(v).items() if mk != "path"}
            else:
                result[k] = _strip_paths(v)
        return result
    if isinstance(data, list):
        return [_strip_paths(item) for item in data]
    return data


def _strip_managed_keys(params: Dict[str, Any], engine: str) -> Dict[str, Any]:
    """Remove managed keys from step parameters."""
    managed = MANAGED_KEYS_BY_ENGINE.get(engine, set())
    if not managed:
        return params

    result = {}
    for section_key, section_val in params.items():
        if isinstance(section_val, dict):
            result[section_key] = {
                k: v for k, v in section_val.items() if k not in managed
            }
        else:
            result[section_key] = section_val
    return result


def _canonicalize_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonicalize a snapshot dict for equivalence comparison.

    Strips: ULIDs, paths, top-level meta, managed parameter keys,
    structure_ulid cross-references, and working_dir defaults.
    """
    data = copy.deepcopy(snap)

    # Strip top-level demo gallery metadata
    data.pop("meta", None)

    # Strip ULIDs and paths
    data = _strip_ulids(data)
    data = _strip_paths(data)

    # Strip structure_ulid from calculations (cross-reference differs by design)
    for calc in data.get("calculations", []):
        calc.pop("structure_ulid", None)
        calc.pop("structure_name", None)
        calc.pop("structure_kind", None)

        # Determine engine for managed key stripping
        engine = calc.get("engine_family", "")

        # Strip managed keys from step parameters
        for step in calc.get("steps", []):
            if "parameters" in step:
                step["parameters"] = _strip_managed_keys(step["parameters"], engine)

    return data


def verify_roundtrip_equivalence(
    snap_a: Dict[str, Any],
    snap_b: Dict[str, Any],
) -> RoundtripReport:
    """
    Verify that two snapshot dicts are content-equivalent per S6.3.

    Args:
        snap_a: First snapshot (e.g., original demo snapshot).
        snap_b: Second snapshot (e.g., re-exported after materialization).

    Returns:
        RoundtripReport with equivalence result and any differences.
    """
    canon_a = _canonicalize_snapshot(snap_a)
    canon_b = _canonicalize_snapshot(snap_b)

    differences = _deep_diff(canon_a, canon_b, path="")

    return RoundtripReport(
        equivalent=len(differences) == 0,
        differences=differences,
    )


def _deep_diff(a: Any, b: Any, path: str) -> List[str]:
    """Recursively compare two values and return list of differences."""
    diffs = []

    if type(a) != type(b):
        diffs.append(f"{path}: type mismatch: {type(a).__name__} vs {type(b).__name__}")
        return diffs

    if isinstance(a, dict):
        all_keys = set(a.keys()) | set(b.keys())
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key not in a:
                diffs.append(f"{child_path}: missing in first snapshot")
            elif key not in b:
                diffs.append(f"{child_path}: missing in second snapshot")
            else:
                diffs.extend(_deep_diff(a[key], b[key], child_path))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list length mismatch: {len(a)} vs {len(b)}")
        for i, (item_a, item_b) in enumerate(zip(a, b)):
            diffs.extend(_deep_diff(item_a, item_b, f"{path}[{i}]"))
    elif isinstance(a, float) and isinstance(b, float):
        if abs(a - b) > 1e-10:
            diffs.append(f"{path}: float mismatch: {a} vs {b}")
    elif a != b:
        diffs.append(f"{path}: value mismatch: {a!r} vs {b!r}")

    return diffs
