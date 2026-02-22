"""QE parameter → namelist registry for section validation.

Provides a cached lookup from parameter name to expected QE namelist
(CONTROL, SYSTEM, ELECTRONS, IONS, CELL) for pw.x parameters. Used by
preflight checker and set_parameters validation.

Stdlib only — no kernel imports.
"""

from __future__ import annotations

from typing import Dict, Optional

# Module-level cache, built on first call.
_PW_PARAM_TO_NAMELIST: Dict[str, str] | None = None

# Namelists that appear in pw.x input files.
_PW_NAMELISTS = frozenset({"CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL"})


def _build_pw_param_lookup() -> Dict[str, str]:
    """Build param_name → namelist mapping from QE metadata for pw module."""
    from qmatsuite.drivers.qe.data.qe_metadata import _iter_params

    lookup: Dict[str, str] = {}
    for p in _iter_params("pw"):
        name = p.get("name", "")
        namelist = p.get("namelist", "")
        if name and namelist in _PW_NAMELISTS:
            # Store lowercase for case-insensitive matching
            lookup[name.lower()] = namelist
    return lookup


def get_qe_param_namelist(param_name: str) -> Optional[str]:
    """Return the expected namelist for a QE pw.x parameter, or None if unknown.

    Args:
        param_name: QE parameter name (case-insensitive).

    Returns:
        Namelist name (e.g. "ELECTRONS") or None if the parameter is
        not in the pw.x metadata.
    """
    global _PW_PARAM_TO_NAMELIST
    if _PW_PARAM_TO_NAMELIST is None:
        _PW_PARAM_TO_NAMELIST = _build_pw_param_lookup()
    return _PW_PARAM_TO_NAMELIST.get(param_name.lower())


def get_pw_namelists() -> frozenset[str]:
    """Return the set of valid pw.x namelist names."""
    return _PW_NAMELISTS
