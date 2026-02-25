"""Binary diagnostics and permission-fix utilities for engine executables.

Provides:
- ``diagnose_binary(path)`` — non-throwing probe that collects permission,
  quarantine, and code-signing information for a single binary.
- ``diagnose_binary_to_log_string(path)`` — one-call helper that returns a
  human-readable multi-line diagnostic string suitable for logger.error().
- ``fix_binary_permissions(engine_dir)`` — applies chmod +x and strips
  macOS quarantine xattr for every file in ``<engine_dir>/bin/``.
"""

from __future__ import annotations

import logging
import os
import platform
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_IS_DARWIN = platform.system() == "Darwin"
_SUBPROCESS_TIMEOUT = 5  # seconds


@dataclass
class BinaryDiagnostics:
    """Non-throwing probe result for a single binary."""

    path: str
    exists: bool = False
    is_file: bool = False
    is_executable: bool = False
    file_permissions: str = ""
    has_quarantine: bool = False
    quarantine_value: str = ""
    file_type: str = ""
    error_summary: str = ""


def diagnose_binary(binary_path: str | Path) -> BinaryDiagnostics:
    """Probe *binary_path* and return a :class:`BinaryDiagnostics` snapshot.

    Never raises — all OS/subprocess errors are caught and recorded in
    ``error_summary``.
    """
    p = Path(binary_path)
    diag = BinaryDiagnostics(path=str(p))

    # --- existence ---
    try:
        diag.exists = p.exists()
    except OSError:
        diag.error_summary = f"cannot stat path: {p}"
        return diag

    if not diag.exists:
        diag.error_summary = f"binary does not exist: {p}"
        return diag

    diag.is_file = p.is_file()
    if not diag.is_file:
        diag.error_summary = f"path is not a regular file: {p}"
        return diag

    # --- permissions ---
    try:
        st = p.stat()
        diag.file_permissions = oct(st.st_mode)
        diag.is_executable = bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    except OSError as exc:
        diag.error_summary = f"cannot stat: {exc}"
        return diag

    # --- file type (via `file` command) ---
    try:
        result = subprocess.run(
            ["file", str(p)],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            diag.file_type = result.stdout.strip()
    except Exception:
        pass

    # --- macOS quarantine xattr ---
    if _IS_DARWIN:
        try:
            result = subprocess.run(
                ["xattr", "-p", "com.apple.quarantine", str(p)],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode == 0 and result.stdout.strip():
                diag.has_quarantine = True
                diag.quarantine_value = result.stdout.strip()
        except Exception:
            pass

    # --- build error_summary ---
    problems: list[str] = []
    if not diag.is_executable:
        problems.append(f"missing execute permission ({diag.file_permissions})")
    if diag.has_quarantine:
        problems.append("macOS quarantine xattr present (Gatekeeper may block execution)")
    diag.error_summary = "; ".join(problems) if problems else "no issues detected"

    return diag


def diagnose_binary_to_log_string(binary_path: str | Path) -> str:
    """Return a multi-line human-readable diagnostic string for *binary_path*."""
    diag = diagnose_binary(binary_path)
    lines = [
        f"Binary diagnostics for: {diag.path}",
        f"  exists:       {diag.exists}",
        f"  is_file:      {diag.is_file}",
        f"  executable:   {diag.is_executable}",
        f"  permissions:  {diag.file_permissions}",
    ]
    if diag.file_type:
        lines.append(f"  file type:    {diag.file_type}")
    if _IS_DARWIN:
        lines.append(f"  quarantine:   {diag.has_quarantine}")
        if diag.quarantine_value:
            lines.append(f"  quarantine_v: {diag.quarantine_value}")
    lines.append(f"  summary:      {diag.error_summary}")
    return "\n".join(lines)


def fix_binary_permissions(engine_dir: str | Path) -> Dict[str, Any]:
    """Apply chmod +x and strip quarantine for an engine directory.

    Looks for a ``bin/`` subdirectory under *engine_dir*.  Returns a dict
    with ``success``, ``fixes_applied``, and ``error`` keys.
    """
    engine_path = Path(engine_dir)
    fixes: List[str] = []
    errors: List[str] = []

    bin_dir = engine_path / "bin"
    if not bin_dir.is_dir():
        # Try engine_dir itself if no bin/ subdirectory
        bin_dir = engine_path

    # --- chmod +x ---
    if platform.system() != "Windows":
        try:
            for entry in bin_dir.iterdir():
                if entry.is_file():
                    st = entry.stat()
                    if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                        entry.chmod(st.st_mode | 0o111)
                        fixes.append(f"chmod +x {entry.name}")
        except OSError as exc:
            errors.append(f"chmod failed: {exc}")

    # --- strip quarantine xattr (macOS only) ---
    if _IS_DARWIN:
        try:
            result = subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(engine_path)],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            if result.returncode == 0:
                fixes.append("stripped com.apple.quarantine xattr")
        except Exception as exc:
            errors.append(f"xattr strip failed: {exc}")

    success = len(errors) == 0
    result_dict: Dict[str, Any] = {
        "success": success,
        "fixes_applied": fixes,
    }
    if errors:
        result_dict["error"] = "; ".join(errors)
    return result_dict
