"""
QE Engine Registry and Selection.

DEPRECATED: This module is deprecated in favor of qe_resolver.py which implements
the new two-state QE resolution model. This module may be removed in a future version.

This module implements the QE engine resolution priority according to
CONSTITUTION_ZH.md section 9.4.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from quantumvitas.core.paths import home_qe_engines_dir
from quantumvitas.core.settings import load_settings, QMatSuiteSettings

logger = logging.getLogger(__name__)


@dataclass
class QEEngineInfo:
    """Information about a QE engine."""
    engine_id: str
    engine_path: Path
    pw_path: Path
    is_managed: bool  # True if in .qmatsuite/engines/qe/, False if external
    verified_sha256: Optional[str] = None


class QEEngineRegistry:
    """
    QE Engine Registry.
    
    Handles engine resolution according to priority:
    1. Project override (if project declares engine_id)
    2. settings.qe.discovered_engine_id
    3. settings.defaults.qe_engine_id
    4. Latest installed managed engine
    5. PATH fallback (if allow_path_fallback=true)
    6. Error with actionable message
    """
    
    def __init__(self, settings: Optional[QMatSuiteSettings] = None):
        """
        Initialize registry.
        
        Args:
            settings: Settings instance (loads if None)
        """
        self.settings = settings or load_settings()
        self._managed_engines_cache: Optional[List[QEEngineInfo]] = None
    
    def resolve_engine(
        self,
        project_engine_id: Optional[str] = None,
    ) -> QEEngineInfo:
        """
        Resolve QE engine according to priority.
        
        Args:
            project_engine_id: Optional engine_id from project metadata
            
        Returns:
            QEEngineInfo for the resolved engine
            
        Raises:
            RuntimeError: If no engine can be resolved
        """
        # Priority 1: Project override
        if project_engine_id:
            engine = self._get_engine_by_id(project_engine_id)
            if engine:
                logger.debug(f"Resolved engine from project override: {project_engine_id}")
                return engine
        
        # Priority 2: User explicit discovered engine (deprecated - no longer in settings)
        # Removed: settings.qe.discovered_engine_id
        
        # Priority 3: User default (deprecated - no longer in settings)
        # Removed: settings.defaults.qe_engine_id
        
        # Priority 4: Latest managed engine
        managed_engines = self.list_managed_engines()
        if managed_engines:
            latest = managed_engines[0]  # Assuming sorted by version/date
            logger.debug(f"Resolved engine from managed fallback: {latest.engine_id}")
            return latest
        
        # Priority 5: PATH fallback (deprecated - no longer in settings)
        # Removed: settings.qe.allow_path_fallback
        # PATH fallback is no longer supported in the new two-state model
        
        # Priority 6: Error with actionable message
        raise RuntimeError(
            "No QE engine found. Options:\n"
            "1. Install a managed QE engine via Settings\n"
            "2. Add an external QE engine via Settings\n"
            "3. Enable auto-discovery in Settings (if allow_auto_discover is enabled)\n"
            "4. Enable PATH fallback in Settings (if QE is in system PATH)"
        )
    
    def _get_engine_by_id(self, engine_id: str) -> Optional[QEEngineInfo]:
        """Get engine by ID (checks managed and external)."""
        # Check managed engines
        managed_engines = self.list_managed_engines()
        for eng in managed_engines:
            if eng.engine_id == engine_id:
                return eng
        
        # Check external engines (deprecated - no longer in settings)
        # Removed: settings.external_engines
        # External engines are now handled via settings.qe.bin_dir
        
        return None
    
    def list_managed_engines(self) -> List[QEEngineInfo]:
        """
        List all managed QE engines in .qmatsuite/engines/qe/.
        
        Returns:
            List of QEEngineInfo, sorted by engine_id (latest first)
        """
        if self._managed_engines_cache is not None:
            return self._managed_engines_cache
        
        engines_dir = home_qe_engines_dir()
        engines: List[QEEngineInfo] = []
        
        if not engines_dir.exists():
            self._managed_engines_cache = []
            return []
        
        for engine_dir in engines_dir.iterdir():
            if not engine_dir.is_dir():
                continue
            
            engine_id = engine_dir.name
            bin_dir = engine_dir / "bin"
            pw_path = bin_dir / "pw.x"
            
            # Check for Windows executable too
            if not pw_path.exists():
                pw_path = bin_dir / "pw.x.exe"
            
            if pw_path.exists():
                engines.append(QEEngineInfo(
                    engine_id=engine_id,
                    engine_path=engine_dir,
                    pw_path=pw_path,
                    is_managed=True,
                ))
        
        # Sort by engine_id (descending, assuming version-like IDs)
        engines.sort(key=lambda e: e.engine_id, reverse=True)
        self._managed_engines_cache = engines
        return engines
    
    def _find_engine_in_path(self) -> Optional[QEEngineInfo]:
        """
        Find QE engine in system PATH.
        
        Only searches PATH, does not do full disk scan.
        """
        import shutil
        
        pw_path = shutil.which("pw.x")
        if not pw_path:
            return None
        
        pw_path = Path(pw_path).resolve()
        # Infer engine root (assume bin/pw.x structure)
        bin_dir = pw_path.parent
        engine_path = bin_dir.parent
        
        return QEEngineInfo(
            engine_id="path-pw.x",
            engine_path=engine_path,
            pw_path=pw_path,
            is_managed=False,
        )
    
    def invalidate_cache(self):
        """Invalidate managed engines cache."""
        self._managed_engines_cache = None


def resolve_qe_engine(project_engine_id: Optional[str] = None) -> QEEngineInfo:
    """
    Convenience function to resolve QE engine.
    
    Args:
        project_engine_id: Optional engine_id from project metadata
        
    Returns:
        QEEngineInfo for the resolved engine
    """
    registry = QEEngineRegistry()
    return registry.resolve_engine(project_engine_id=project_engine_id)

