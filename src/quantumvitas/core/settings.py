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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "qe": asdict(self.qe),
            "debug_resolution": self.debug_resolution,
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
        
        return cls(
            version=data.get("version", 1),
            qe=qe,
            debug_resolution=data.get("debug_resolution", False),  # Default: OFF
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

