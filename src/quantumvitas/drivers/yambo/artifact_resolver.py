"""Yambo artifact resolver.

Resolves cross-engine artifacts needed by yambo:
- QE prefix.save/ directory (for p2y conversion)
- Yambo SAVE/ directory (created by setup, used by gw/bse/optics)
- GW ndb.QP database (for BSE with GW corrections)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def find_qe_save_dir(calc_raw_dir: Path) -> Optional[Path]:
    """Find QE prefix.save/ directory in calc/raw/.

    Searches for *.save/ directories that contain the QE output
    (data-file-schema.xml or charge-density.dat).

    Args:
        calc_raw_dir: Path to calc/raw/ directory.

    Returns:
        Path to prefix.save/ directory, or None if not found.
    """
    # Search in QE's outdir pattern: calc/raw/outdir/prefix.save/
    outdir = calc_raw_dir / "outdir"
    if outdir.is_dir():
        for save_dir in sorted(outdir.iterdir(), reverse=True):
            if save_dir.is_dir() and save_dir.name.endswith(".save"):
                if (save_dir / "data-file-schema.xml").exists():
                    logger.debug("Found QE save dir: %s", save_dir)
                    return save_dir

    # Search in step subdirectories (ISOLATED workdir pattern)
    for step_dir in sorted(calc_raw_dir.iterdir(), reverse=True):
        if not step_dir.is_dir():
            continue
        # Check outdir inside step dir
        step_outdir = step_dir / "outdir"
        if step_outdir.is_dir():
            for save_dir in sorted(step_outdir.iterdir(), reverse=True):
                if save_dir.is_dir() and save_dir.name.endswith(".save"):
                    if (save_dir / "data-file-schema.xml").exists():
                        logger.debug("Found QE save dir: %s", save_dir)
                        return save_dir
        # Check directly in step dir
        for save_dir in sorted(step_dir.iterdir(), reverse=True):
            if save_dir.is_dir() and save_dir.name.endswith(".save"):
                if (save_dir / "data-file-schema.xml").exists():
                    logger.debug("Found QE save dir: %s", save_dir)
                    return save_dir

    return None


def find_yambo_save_dir(calc_raw_dir: Path) -> Optional[Path]:
    """Find yambo SAVE/ directory in calc/raw/.

    The SAVE directory is created by the setup step directly
    in calc/raw/SAVE/.

    Args:
        calc_raw_dir: Path to calc/raw/ directory.

    Returns:
        Path to SAVE/ directory, or None if not found.
    """
    save_dir = calc_raw_dir / "SAVE"
    if save_dir.is_dir() and (save_dir / "ns.db1").exists():
        return save_dir

    # Also search in step subdirectories
    for step_dir in sorted(calc_raw_dir.iterdir(), reverse=True):
        if not step_dir.is_dir():
            continue
        candidate = step_dir / "SAVE"
        if candidate.is_dir() and (candidate / "ns.db1").exists():
            return candidate

    return None


def find_gw_qp_db(calc_raw_dir: Path) -> Optional[Path]:
    """Find GW ndb.QP database from a previous GW step.

    Args:
        calc_raw_dir: Path to calc/raw/ directory.

    Returns:
        Path to ndb.QP file, or None if not found.
    """
    for step_dir in sorted(calc_raw_dir.iterdir(), reverse=True):
        if not step_dir.is_dir():
            continue
        # Search in job subdirectories (e.g., gw_run/ndb.QP)
        for sub in step_dir.iterdir():
            if sub.is_dir():
                qp_db = sub / "ndb.QP"
                if qp_db.exists():
                    return qp_db
    return None
