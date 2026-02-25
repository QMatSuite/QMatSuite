"""Infer bundled-engine staging status from filesystem state.

The Electron main process copies bundled engines and pseudo libraries from
app resources to AppData on first launch.  This module lets the daemon
check staging progress **without blocking** — it only reads the filesystem.

Staging protocol (main.ts):

    1. ``cpSync(src, <final>.staging)``    — staging dir appears
    2. ``renameSync(<final>.staging, <final>)`` — atomic rename
    3. ``writeFileSync(<final>/.bundled-staged-<ver>, ...)`` — marker written

The daemon reads these signals to infer the state:

    marker exists         → "ready"
    ``.staging`` dir      → "staging"     (copy in progress)
    final dir, no marker  → "staging_incomplete" (rename done, marker missing)
    neither               → "staging"     (hasn't started yet)

``QMATSUITE_RESOURCES_PATH`` (set by Electron when spawning the daemon)
tells us whether bundled assets exist in the app bundle at all.  If the
env var is absent or the expected directory is missing, this is a lite
variant and we return ``None``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from qmatsuite.core.paths import home_engines_dir, home_pseudo_libraries_dir

# Canonical paths — must match engine_registry._scan_bundled() expectations:
#   home_engines_dir() / "qe" / "bundled-7.5" / "bin" / "pw.x"
_QE_INSTALL_NAME = "bundled-7.5"
_QE_MARKER = f".bundled-staged-7.5"

# Canonical paths — must match pseudo.layout.iter_installed_libraries() expectations:
#   home_pseudo_libraries_dir() / "SSSP" / "efficiency" / "1.3.0" / "head.json"
_SSSP_DIR_NAME = "SSSP"
_SSSP_VARIANT = "efficiency"
_SSSP_VERSION = "1.3.0"
_SSSP_MARKER = f".bundled-staged-{_SSSP_VERSION}"

StagingStatus = Literal["ready", "staging", "staging_incomplete"]


def _resources_path() -> Optional[Path]:
    """Return the Electron app resources path, or None if not in Electron mode."""
    raw = os.environ.get("QMATSUITE_RESOURCES_PATH")
    if not raw:
        return None
    p = Path(raw)
    return p if p.is_dir() else None


def check_bundled_qe_status() -> Optional[StagingStatus]:
    """Infer bundled QE staging status from filesystem state.

    Returns
    -------
    None
        Not a full variant (no bundled QE in app resources).
    "ready"
        Staging complete — engine available for discovery by
        ``engine_registry._scan_bundled("qe")``.
    "staging"
        Staging in progress or hasn't started yet.
    "staging_incomplete"
        Previous staging crashed (final dir exists, no marker).
    """
    resources = _resources_path()
    if resources is None:
        return None

    # Check whether the app bundle contains a bundled QE
    bundled_src = resources / "engines" / "qe" / _QE_INSTALL_NAME
    if not bundled_src.exists():
        return None  # lite variant

    # Check staging state in AppData
    qe_dir = home_engines_dir() / "qe"
    final = qe_dir / _QE_INSTALL_NAME
    marker = final / _QE_MARKER
    staging = qe_dir / f"{_QE_INSTALL_NAME}.staging"

    if marker.exists():
        return "ready"
    if staging.exists():
        return "staging"
    if final.exists():
        return "staging_incomplete"
    return "staging"  # hasn't started yet


def check_bundled_sssp_status() -> Optional[StagingStatus]:
    """Infer bundled SSSP pseudo library staging status from filesystem state.

    Returns
    -------
    None
        Not a full variant (no bundled SSSP in app resources).
    "ready"
        Staging complete — library discoverable by
        ``pseudo.layout.iter_installed_libraries()``.
    "staging"
        Staging in progress or hasn't started yet.
    "staging_incomplete"
        Previous staging crashed (final dir exists, no marker).
    """
    resources = _resources_path()
    if resources is None:
        return None

    bundled_head = (
        resources / "libraries" / "pseudo"
        / _SSSP_DIR_NAME / _SSSP_VARIANT / _SSSP_VERSION / "head.json"
    )
    if not bundled_head.exists():
        return None  # lite variant

    sssp_dir = home_pseudo_libraries_dir() / _SSSP_DIR_NAME / _SSSP_VARIANT
    final = sssp_dir / _SSSP_VERSION
    marker = final / _SSSP_MARKER
    staging = sssp_dir / f"{_SSSP_VERSION}.staging"

    if marker.exists():
        return "ready"
    if staging.exists():
        return "staging"
    if final.exists():
        return "staging_incomplete"
    return "staging"  # hasn't started yet
