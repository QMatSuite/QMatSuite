"""VASP execution wrapper and reference verification (dev-only).

This module provides a lightweight execution wrapper for running VASP
calculations from curated input directories, and a reference-value
verification utility.

NOT a product-level runner — use the kernel CalculationRunner for real
workflows. This is a developer/testing convenience for validating that
the driver I/O stack produces inputs VASP actually accepts, and that
outputs parse to sensible values.

Depends on:
    drivers/vasp/engine/vasp_potcar.py  (stage_potcar)
    drivers/vasp/parsers/output.py      (VASPOutputParser, VASPDigest)
    drivers/vasp/io/                    (write_incar_text, write_poscar_text, write_kpoints_text)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# RunResult dataclass
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class RunResult:
    """Result of a single VASP execution."""

    success: bool
    digest: Any = None  # VASPDigest or None
    return_code: int = -1
    elapsed_s: float = 0.0
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""


# ──────────────────────────────────────────────────────────────────────────
# VASP binary resolution
# ──────────────────────────────────────────────────────────────────────────

def _get_vasp_roots() -> list[Path]:
    """Build list of VASP root directories to search.

    Uses the centralized ``_find_repo_root()`` from discovery module
    to handle test environments where CWD is a tmpdir.
    """
    roots = []
    # Project-local (via centralized repo root detection)
    try:
        from quantumvitas.core.engines.discovery import _find_repo_root
        repo_root = _find_repo_root()
        if repo_root:
            candidate = repo_root / ".qmatsuite" / "engines" / "vasp"
            if candidate.is_dir():
                roots.append(candidate)
    except ImportError:
        pass
    # CWD relative (for backwards compat)
    cwd_candidate = Path(".qmatsuite") / "engines" / "vasp"
    if cwd_candidate.is_dir() and cwd_candidate.resolve() not in [r.resolve() for r in roots]:
        roots.append(cwd_candidate)
    # Home directory
    home_candidate = Path.home() / ".qmatsuite" / "engines" / "vasp"
    if home_candidate.is_dir() and home_candidate.resolve() not in [r.resolve() for r in roots]:
        roots.append(home_candidate)
    return roots


def find_vasp_binary(variant: str = "vasp_std") -> Optional[Path]:
    """Locate a VASP binary.

    Search order:
        1. QMATS_VASP_STD_BIN / QMATS_VASP_GAM_BIN / QMATS_VASP_NCL_BIN
        2. <root>/vasp.*/bin/<variant> under detected roots

    Returns:
        Path to binary, or None if not found.
    """
    # Environment override
    env_map = {
        "vasp_std": "QMATS_VASP_STD_BIN",
        "vasp_gam": "QMATS_VASP_GAM_BIN",
        "vasp_ncl": "QMATS_VASP_NCL_BIN",
    }
    env_var = env_map.get(variant)
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path:
            p = Path(env_path)
            if p.is_file():
                return p

    # Search detected roots
    for root in _get_vasp_roots():
        if not root.is_dir():
            continue
        for version_dir in sorted(root.iterdir(), reverse=True):
            bin_path = version_dir / "bin" / variant
            if bin_path.is_file():
                return bin_path

    return None


# ──────────────────────────────────────────────────────────────────────────
# run_vasp_case
# ──────────────────────────────────────────────────────────────────────────


def run_vasp_case(
    case_dir: Path,
    work_dir: Path,
    vasp_binary: str = "vasp_std",
    functional: str = "PBE",
    mpi_np: int = 1,
    timeout: int = 600,
    vasp_potcar_root: Optional[Path] = None,
) -> RunResult:
    """Run a VASP calculation from a curated case directory.

    Copies INCAR/POSCAR/KPOINTS from *case_dir* to *work_dir*, stages
    POTCAR, then invokes the VASP binary. On success, parses outputs
    via VASPOutputParser.

    Args:
        case_dir: Directory containing INCAR, POSCAR, KPOINTS.
        work_dir: Working directory (will be created).
        vasp_binary: Binary variant name ("vasp_std", "vasp_gam", "vasp_ncl").
        functional: POTCAR functional ("PBE" or "LDA").
        mpi_np: Number of MPI ranks.
        timeout: Timeout in seconds.
        vasp_potcar_root: Override POTCAR library root.

    Returns:
        RunResult with digest, timing, and error info.
    """
    case_dir = Path(case_dir).resolve()
    work_dir = Path(work_dir)

    # Validate case directory
    required = ["INCAR", "POSCAR", "KPOINTS"]
    for fname in required:
        if not (case_dir / fname).is_file():
            return RunResult(
                success=False,
                error=f"Missing {fname} in {case_dir}",
            )

    # Locate binary
    bin_path = find_vasp_binary(vasp_binary)
    if bin_path is None:
        return RunResult(
            success=False,
            error=f"VASP binary '{vasp_binary}' not found",
        )

    # Create work directory and copy inputs
    work_dir.mkdir(parents=True, exist_ok=True)
    for fname in required:
        shutil.copy2(case_dir / fname, work_dir / fname)

    # Extract species from POSCAR for POTCAR staging
    species = _extract_species_from_poscar(work_dir / "POSCAR")
    if not species:
        return RunResult(
            success=False,
            error="Could not extract species from POSCAR",
        )

    # Stage POTCAR
    try:
        from quantumvitas.drivers.vasp.engine.vasp_potcar import stage_potcar

        stage_potcar(
            species,
            work_dir,
            functional=functional,
            vasp_potcar_root=vasp_potcar_root,
        )
    except (FileNotFoundError, ValueError) as exc:
        return RunResult(
            success=False,
            error=f"POTCAR staging failed: {exc}",
        )

    # Build command
    cmd: List[str] = []
    if mpi_np > 1:
        mpirun = shutil.which("mpirun") or shutil.which("mpiexec")
        if mpirun:
            cmd.extend([mpirun, "-np", str(mpi_np)])
        else:
            return RunResult(
                success=False,
                error="mpi_np > 1 but mpirun/mpiexec not found",
            )
    cmd.append(str(bin_path))

    # Run
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.monotonic() - t0
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t0
        return RunResult(
            success=False,
            elapsed_s=elapsed,
            error=f"VASP timed out after {timeout}s",
        )
    except OSError as exc:
        elapsed = time.monotonic() - t0
        return RunResult(
            success=False,
            elapsed_s=elapsed,
            error=f"Failed to launch VASP: {exc}",
        )

    # Parse outputs
    digest = None
    try:
        from quantumvitas.drivers.vasp.parsers.output import VASPOutputParser

        parser = VASPOutputParser()
        if parser.can_parse(work_dir):
            digest = parser.parse(work_dir)
    except Exception as exc:
        logger.warning("Output parsing failed: %s", exc)

    success = proc.returncode == 0
    return RunResult(
        success=success,
        digest=digest,
        return_code=proc.returncode,
        elapsed_s=elapsed,
        error=proc.stderr.strip() if not success else None,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


# ──────────────────────────────────────────────────────────────────────────
# Reference verification
# ──────────────────────────────────────────────────────────────────────────

DEFAULT_TOLERANCES = {
    "final_energy_eV": 0.01,  # 10 meV
    "energy_per_atom_eV": 0.005,  # 5 meV/atom
    "volume_A3": 0.5,
    "max_force_eV_A": 0.05,
    "total_magnetization": 0.1,
    "pressure_kBar": 1.0,
}


def verify_reference(
    digest: Any,
    ref: Dict[str, Any],
    tolerances: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compare a VASPDigest against reference values.

    Args:
        digest: VASPDigest instance (or object with matching attributes).
        ref: Dict of reference field_name -> expected_value.
        tolerances: Optional per-field absolute tolerances.
            Missing keys fall back to DEFAULT_TOLERANCES.

    Returns:
        Dict with keys:
            passed (bool): all checks passed
            checks (list[dict]): per-field results
            n_passed (int): number of passing checks
            n_failed (int): number of failing checks
    """
    tol = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    checks: List[Dict[str, Any]] = []

    for field_name, expected in ref.items():
        actual = getattr(digest, field_name, None)
        entry: Dict[str, Any] = {
            "field": field_name,
            "expected": expected,
            "actual": actual,
        }

        if actual is None:
            entry["passed"] = False
            entry["reason"] = "missing from digest"
        elif isinstance(expected, bool):
            entry["passed"] = actual == expected
            entry["reason"] = "" if entry["passed"] else f"expected {expected}"
        elif isinstance(expected, (int, float)):
            field_tol = tol.get(field_name, 0.0)
            diff = abs(float(actual) - float(expected))
            entry["passed"] = diff <= field_tol
            entry["tolerance"] = field_tol
            entry["diff"] = diff
            entry["reason"] = (
                ""
                if entry["passed"]
                else f"diff={diff:.6f} > tol={field_tol}"
            )
        else:
            entry["passed"] = actual == expected
            entry["reason"] = "" if entry["passed"] else f"expected {expected!r}"

        checks.append(entry)

    n_passed = sum(1 for c in checks if c["passed"])
    n_failed = len(checks) - n_passed

    return {
        "passed": n_failed == 0,
        "checks": checks,
        "n_passed": n_passed,
        "n_failed": n_failed,
    }


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _extract_species_from_poscar(path: Path) -> List[str]:
    """Extract species list from POSCAR (line 6 in VASP 5+ format)."""
    try:
        lines = path.read_text().splitlines()
        if len(lines) < 6:
            return []
        # Line 6 (0-indexed line 5) has species symbols
        species_line = lines[5].split()
        # Verify these are element symbols (alphabetic)
        if all(s.isalpha() for s in species_line):
            return species_line
        # Possibly VASP 4 format — species on line 1
        return []
    except (OSError, IndexError):
        return []
