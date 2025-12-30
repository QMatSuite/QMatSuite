"""
QE Engine Resolution Diagnostics.

This module provides diagnostic tools to trace how QE engines are resolved,
helping identify when legacy auto-detection bypasses the registry system.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

from quantumvitas.core.engines.qe_registry import QEEngineRegistry, resolve_qe_engine
from quantumvitas.core.engines.qe_installation import get_qe_home, QEInstallation
from quantumvitas.core.settings import load_settings
from quantumvitas.core.paths import home_qe_engines_dir

logger = logging.getLogger(__name__)


@dataclass
class QEResolutionReport:
    """Diagnostic report for QE engine resolution."""
    resolved_engine_id: Optional[str] = None
    resolved_pw_path: Optional[str] = None
    resolution_reason: str = "unknown"
    inputs_used: Dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "resolved_engine_id": self.resolved_engine_id,
            "resolved_pw_path": str(self.resolved_pw_path) if self.resolved_pw_path else None,
            "resolution_reason": self.resolution_reason,
            "inputs_used": self.inputs_used,
            "warnings": self.warnings,
        }


def diagnose_qe_resolution(
    project_engine_id: Optional[str] = None,
    check_legacy: bool = True,
) -> QEResolutionReport:
    """
    Diagnose how QE engine would be resolved.
    
    This function traces through all possible resolution paths and reports
    which one would be used and why.
    
    Args:
        project_engine_id: Optional project-level engine_id override
        check_legacy: If True, also check legacy auto-detection paths
        
    Returns:
        QEResolutionReport with diagnostic information
    """
    report = QEResolutionReport()
    settings = load_settings()
    
    # Check registry-based resolution first
    try:
        registry = QEEngineRegistry(settings)
        
        # Priority 1: Project override
        if project_engine_id:
            engine = registry._get_engine_by_id(project_engine_id)
            if engine:
                report.resolved_engine_id = engine.engine_id
                report.resolved_pw_path = str(engine.pw_path)
                report.resolution_reason = "project_override"
                report.inputs_used["project_engine_id"] = project_engine_id
                return report
        
        # Priority 2: Discovered engine
        if settings.qe.discovered_engine_id:
            engine = registry._get_engine_by_id(settings.qe.discovered_engine_id)
            if engine:
                report.resolved_engine_id = engine.engine_id
                report.resolved_pw_path = str(engine.pw_path)
                report.resolution_reason = "settings_discovered_engine_id"
                report.inputs_used["settings.qe.discovered_engine_id"] = settings.qe.discovered_engine_id
                return report
        
        # Priority 3: Default engine
        if settings.defaults.qe_engine_id:
            engine = registry._get_engine_by_id(settings.defaults.qe_engine_id)
            if engine:
                report.resolved_engine_id = engine.engine_id
                report.resolved_pw_path = str(engine.pw_path)
                report.resolution_reason = "settings_defaults_qe_engine_id"
                report.inputs_used["settings.defaults.qe_engine_id"] = settings.defaults.qe_engine_id
                return report
        
        # Priority 4: Managed engines
        managed_engines = registry.list_managed_engines()
        if managed_engines:
            latest = managed_engines[0]
            report.resolved_engine_id = latest.engine_id
            report.resolved_pw_path = str(latest.pw_path)
            report.resolution_reason = "managed_engine_fallback"
            report.inputs_used["managed_engines_count"] = len(managed_engines)
            report.inputs_used["managed_engines_dir"] = str(home_qe_engines_dir())
            return report
        
        # Priority 5: PATH fallback (if allowed)
        if settings.qe.allow_path_fallback:
            path_engine = registry._find_engine_in_path()
            if path_engine:
                report.resolved_engine_id = path_engine.engine_id
                report.resolved_pw_path = str(path_engine.pw_path)
                report.resolution_reason = "path_fallback"
                report.inputs_used["settings.qe.allow_path_fallback"] = True
                report.inputs_used["path_pw_x"] = str(path_engine.pw_path)
                report.warnings.append(
                    "PATH fallback is enabled. This bypasses managed engine requirement."
                )
                return report
        
    except Exception as e:
        report.warnings.append(f"Registry resolution failed: {e}")
    
    # Check legacy auto-detection (if enabled)
    if check_legacy:
        legacy_qe_home = get_qe_home()
        if legacy_qe_home:
            pw_path = legacy_qe_home / "bin" / "pw.x"
            if pw_path.exists():
                report.resolved_engine_id = "legacy-auto-detected"
                report.resolved_pw_path = str(pw_path)
                report.resolution_reason = "legacy_auto_detection"
                
                # Trace how it was detected
                qe_home_env = os.environ.get("QE_HOME")
                if qe_home_env:
                    report.inputs_used["QE_HOME_env"] = qe_home_env
                    report.resolution_reason = "legacy_QE_HOME_env"
                else:
                    # Check PATH
                    path_pw = shutil.which("pw.x")
                    if path_pw:
                        report.inputs_used["PATH_pw_x"] = path_pw
                        report.resolution_reason = "legacy_PATH_detection"
                    else:
                        # Shell config or home directory scan
                        report.inputs_used["detection_method"] = "shell_config_or_home_scan"
                        report.resolution_reason = "legacy_shell_config_or_home_scan"
                
                report.warnings.append(
                    "Legacy auto-detection bypassed registry. "
                    "This violates 'default managed-only' policy."
                )
                return report
    
    # No resolution found
    report.resolution_reason = "no_engine_found"
    return report


def check_settings_for_external_engines() -> Dict[str, Any]:
    """Check if settings.json contains external engines that might be used."""
    settings = load_settings()
    return {
        "has_discovered_engine_id": settings.qe.discovered_engine_id is not None,
        "discovered_engine_id": settings.qe.discovered_engine_id,
        "has_default_engine_id": settings.defaults.qe_engine_id is not None,
        "default_engine_id": settings.defaults.qe_engine_id,
        "allow_path_fallback": settings.qe.allow_path_fallback,
        "external_engines_count": len(settings.external_engines),
        "external_engines": [
            {"id": eng.id, "pw_path": eng.pw_path, "label": eng.label}
            for eng in settings.external_engines
        ],
    }


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

