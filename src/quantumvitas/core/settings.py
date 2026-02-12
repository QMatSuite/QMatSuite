"""
QMatSuite global settings management.

This module handles reading and writing .qmatsuite/config/settings.json,
the single minimal global configuration file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from quantumvitas.core.paths import get_settings_json_path

logger = logging.getLogger(__name__)


@dataclass
class QEConfig:
    """QE engine configuration (two-state model)."""
    bin_dir: Optional[str] = None  # Absolute path to QE bin directory, or null for internal QE


@dataclass
class MaterialsProjectConfig:
    """Materials Project native API configuration (PR5)."""
    enabled: bool = False  # Default: disabled (requires key)
    api_key: Optional[str] = None  # User-provided API key
    
    def has_key(self) -> bool:
        """Check if API key is present and non-empty."""
        return self.api_key is not None and self.api_key.strip() != ""


@dataclass
class OnlineStructuresConfig:
    """Online structure sources configuration (PR1)."""
    optimade_providers: List[Dict[str, Any]] = field(default_factory=list)  # [{"provider_key": "mp", "enabled": true}, ...]
    pubchem_enabled: bool = True  # PubChem enabled by default
    materials_project: MaterialsProjectConfig = field(default_factory=MaterialsProjectConfig)  # MP native API config (PR5)
    timeout_seconds: float = 8.0  # Per-provider timeout
    max_results_per_provider: int = 10  # Max results per provider
    max_total_results: int = 50  # Max total results after aggregation


@dataclass
class QMatSuiteSettings:
    """
    QMatSuite global settings.
    
    This is the minimal schema for settings.json.
    Two-state QE model:
    - If qe.bin_dir is set: use external QE at that path
    - If qe.bin_dir is null: use internal QE (auto-selected from .qmatsuite/engines/qe/**/bin)
    """
    version: int = 1
    qe: QEConfig = field(default_factory=QEConfig)
    debug_resolution: bool = False  # Enable detailed resolution/addressing debug logs
    max_concurrent_calcs: int = 2  # Maximum concurrent calculation runs (default 2)
    analysis_cache_enabled: bool = True  # Enable analysis object caching (default: enabled)
    online_structures: OnlineStructuresConfig = field(default_factory=OnlineStructuresConfig)  # PR1: Online structure sources
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "qe": asdict(self.qe),
            "debug_resolution": self.debug_resolution,
            "max_concurrent_calcs": self.max_concurrent_calcs,
            "analysis_cache_enabled": self.analysis_cache_enabled,
            "online_structures": asdict(self.online_structures),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QMatSuiteSettings:
        """Create from dictionary with migration from old schema."""
        # Migrate from old schema if present
        migrated_bin_dir = None
        
        # Check for old QE settings
        old_qe = data.get("qe", {})
        old_defaults = data.get("defaults", {})
        old_external_engines = data.get("external_engines", [])
        
        # Migration: if old settings had explicit external engine with pw_path, use it
        if old_external_engines:
            # Try to find an external engine with a valid pw_path
            for ext_eng in old_external_engines:
                pw_path_str = ext_eng.get("pw_path")
                if pw_path_str:
                    try:
                        pw_path = Path(pw_path_str)
                        if pw_path.exists() and pw_path.is_file():
                            # Use parent directory (bin dir) of pw executable
                            migrated_bin_dir = str(pw_path.parent.resolve())
                            logger.info(f"Migrated external engine pw_path to qe.bin_dir: {migrated_bin_dir}")
                            break
                    except Exception:
                        pass
        
        # Check if new schema already has bin_dir
        new_bin_dir = old_qe.get("bin_dir")
        if new_bin_dir:
            # New schema already present, use it
            qe = QEConfig(bin_dir=new_bin_dir)
        elif migrated_bin_dir:
            # Use migrated value
            qe = QEConfig(bin_dir=migrated_bin_dir)
        else:
            # Default: null (use internal QE)
            qe = QEConfig(bin_dir=None)
        
        # Parse online_structures config
        online_structures_data = data.get("online_structures", {})
        mp_data = online_structures_data.get("materials_project", {})
        if isinstance(mp_data, dict):
            materials_project = MaterialsProjectConfig(
                enabled=mp_data.get("enabled", False),
                api_key=mp_data.get("api_key", None),
            )
        else:
            # Fallback for old format
            materials_project = MaterialsProjectConfig()
        online_structures = OnlineStructuresConfig(
            optimade_providers=online_structures_data.get("optimade_providers", []),
            pubchem_enabled=online_structures_data.get("pubchem_enabled", True),
            materials_project=materials_project,
            timeout_seconds=online_structures_data.get("timeout_seconds", 8.0),
            max_results_per_provider=online_structures_data.get("max_results_per_provider", 10),
            max_total_results=online_structures_data.get("max_total_results", 50),
        )
        
        return cls(
            version=data.get("version", 1),
            qe=qe,
            debug_resolution=data.get("debug_resolution", False),  # Default: OFF
            max_concurrent_calcs=data.get("max_concurrent_calcs", 2),  # Default: 2
            analysis_cache_enabled=data.get("analysis_cache_enabled", True),  # Default: enabled
            online_structures=online_structures,
        )


def load_settings() -> QMatSuiteSettings:
    """
    Load settings from .qmatsuite/config/settings.json.
    
    Returns safe defaults if file does not exist or is invalid.
    
    Returns:
        QMatSuiteSettings instance
    """
    settings_path = get_settings_json_path()
    
    if not settings_path.exists():
        logger.debug(f"Settings file not found at {settings_path}, using defaults")
        return QMatSuiteSettings()
    
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return QMatSuiteSettings.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse settings.json: {e}, using defaults")
        return QMatSuiteSettings()


def save_settings(settings: QMatSuiteSettings) -> None:
    """
    Save settings to .qmatsuite/config/settings.json.
    
    Args:
        settings: Settings to save
    """
    settings_path = get_settings_json_path()
    
    try:
        # Ensure directory exists
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write with pretty formatting
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Settings saved to {settings_path}")
    except (OSError, IOError) as e:
        logger.error(f"Failed to save settings to {settings_path}: {e}")
        raise


def get_default_settings() -> QMatSuiteSettings:
    """Get default settings (same as load_settings when file doesn't exist)."""
    return QMatSuiteSettings()

