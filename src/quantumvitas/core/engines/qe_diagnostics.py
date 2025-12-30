"""
QE Engine Resolution Diagnostics.

This module provides diagnostic tools to trace how QE engines are resolved
using the two-state model:
- External QE: settings.qe.bin_dir is set (absolute path to bin directory)
- Internal QE: settings.qe.bin_dir is null (auto-selected from .qmatsuite/engines/qe/**/bin)
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir, find_internal_qe_bin_dir, validate_qe_bin_dir
from quantumvitas.core.settings import load_settings
from quantumvitas.core.paths import home_qe_engines_dir

logger = logging.getLogger(__name__)


@dataclass
class QEResolutionReport:
    """Diagnostic report for QE engine resolution (two-state model)."""
    mode: str = "unknown"  # "external" or "internal"
    qe_bin_dir: Optional[str] = None  # Resolved bin directory path
    settings_bin_dir: Optional[str] = None  # settings.qe.bin_dir value
    resolution_reason: str = "unknown"
    inputs_used: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None  # Error message if resolution failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "mode": self.mode,
            "qe_bin_dir": str(self.qe_bin_dir) if self.qe_bin_dir else None,
            "settings_bin_dir": str(self.settings_bin_dir) if self.settings_bin_dir else None,
            "resolution_reason": self.resolution_reason,
            "inputs_used": self.inputs_used,
            "warnings": self.warnings,
            "error": self.error,
        }


def diagnose_qe_resolution() -> QEResolutionReport:
    """
    Diagnose how QE engine would be resolved using the two-state model.
    
    Two-state model:
    1. External QE: settings.qe.bin_dir is set (absolute path)
       - Must validate pw* exists; if invalid, raise error (no fallback)
    2. Internal QE: settings.qe.bin_dir is null
       - Auto-select from .qmatsuite/engines/qe/**/bin
       - If none found, raise error (no fallback)
    
    Returns:
        QEResolutionReport with diagnostic information
    """
    report = QEResolutionReport()
    settings = load_settings()
    
    # Record settings value
    report.settings_bin_dir = settings.qe.bin_dir
    
    try:
        # Use the resolver (two-state model)
        resolved_bin_dir = resolve_qe_bin_dir(settings)
        report.qe_bin_dir = str(resolved_bin_dir)
        
        # Determine mode
        if settings.qe.bin_dir:
            report.mode = "external"
            report.resolution_reason = "external_explicit"
            report.inputs_used["settings.qe.bin_dir"] = settings.qe.bin_dir
        else:
            report.mode = "internal"
            report.resolution_reason = "internal_auto_selected"
            # Find all internal candidates for reporting
            engines_dir = home_qe_engines_dir()
            if engines_dir.exists():
                candidates = []
                for engine_dir in engines_dir.rglob("bin"):
                    if engine_dir.is_dir():
                        pw_x = engine_dir / "pw.x"
                        pw_exe = engine_dir / "pw.x.exe"
                        if pw_x.exists() or pw_exe.exists():
                            candidates.append(str(engine_dir))
                report.inputs_used["internal_candidates"] = candidates
                report.inputs_used["internal_candidates_count"] = len(candidates)
                report.inputs_used["selected_bin_dir"] = str(resolved_bin_dir)
        
    except RuntimeError as e:
        # Resolution failed
        report.error = str(e)
        if settings.qe.bin_dir:
            report.mode = "external"
            report.resolution_reason = "external_invalid"
            report.inputs_used["settings.qe.bin_dir"] = settings.qe.bin_dir
            report.warnings.append(
                f"External QE bin_dir is set but invalid: {settings.qe.bin_dir}. "
                f"Error: {e}"
            )
        else:
            report.mode = "internal"
            report.resolution_reason = "internal_not_found"
            # Check if internal engines directory exists
            engines_dir = home_qe_engines_dir()
            report.inputs_used["engines_dir_exists"] = engines_dir.exists()
            report.inputs_used["engines_dir_path"] = str(engines_dir)
            if engines_dir.exists():
                # Count candidates
                candidates = []
                for engine_dir in engines_dir.rglob("bin"):
                    if engine_dir.is_dir():
                        pw_x = engine_dir / "pw.x"
                        pw_exe = engine_dir / "pw.x.exe"
                        if pw_x.exists() or pw_exe.exists():
                            candidates.append(str(engine_dir))
                report.inputs_used["internal_candidates"] = candidates
                report.inputs_used["internal_candidates_count"] = len(candidates)
            report.warnings.append(
                f"No internal QE found. Error: {e}"
            )
    except Exception as e:
        report.error = str(e)
        report.resolution_reason = "resolution_error"
        report.warnings.append(f"Unexpected error during resolution: {e}")
    
    return report


def check_settings_for_external_engines() -> Dict[str, Any]:
    """Check settings.json for QE configuration (two-state model)."""
    settings = load_settings()
    result = {
        "qe_bin_dir": settings.qe.bin_dir,
        "mode": "external" if settings.qe.bin_dir else "internal",
    }
    
    # If external, validate the path
    if settings.qe.bin_dir:
        bin_dir = Path(settings.qe.bin_dir)
        result["bin_dir_exists"] = bin_dir.exists()
        result["bin_dir_is_dir"] = bin_dir.is_dir() if bin_dir.exists() else False
        pw_x = bin_dir / "pw.x"
        pw_exe = bin_dir / "pw.x.exe"
        result["has_pw_x"] = pw_x.exists()
        result["has_pw_exe"] = pw_exe.exists()
        result["is_valid"] = pw_x.exists() or pw_exe.exists()
    
    return result


def check_environment_variables() -> Dict[str, Any]:
    """Check environment variables that might affect QE resolution."""
    return {
        "QE_HOME": os.environ.get("QE_HOME"),
        "QE_BIN": os.environ.get("QE_BIN"),
        "QE_ROOT": os.environ.get("QE_ROOT"),
        "QMATSUITE_QE": os.environ.get("QMATSUITE_QE"),
        "PATH_contains_pw_x": shutil.which("pw.x") is not None,
        "PATH_pw_x_location": shutil.which("pw.x"),
    }


def check_managed_engines() -> Dict[str, Any]:
    """Check for managed engines in .qmatsuite/engines/qe/."""
    engines_dir = home_qe_engines_dir()
    engines = []
    
    if engines_dir.exists():
        for engine_dir in engines_dir.iterdir():
            if engine_dir.is_dir():
                pw_path = engine_dir / "bin" / "pw.x"
                if not pw_path.exists():
                    pw_path = engine_dir / "bin" / "pw.x.exe"
                if pw_path.exists():
                    engines.append({
                        "engine_id": engine_dir.name,
                        "engine_path": str(engine_dir),
                        "pw_path": str(pw_path),
                    })
    
    return {
        "engines_dir_exists": engines_dir.exists(),
        "engines_dir_path": str(engines_dir),
        "managed_engines_count": len(engines),
        "managed_engines": engines,
    }

