"""
Engine registry and detection.

This module provides a registry for computational engines and utilities
for detecting and managing engine installations.
"""

from pathlib import Path
from typing import Dict, Optional, Type
import platform

from .engines.base import Engine, EngineConfig
from .engines.qe import QuantumEspressoEngine


class EngineRegistry:
    """
    Registry for computational engines.
    
    Manages available engines and provides factory methods for creating
    engine instances.
    """
    
    def __init__(self):
        """Initialize the engine registry."""
        self._engines: Dict[str, Type[Engine]] = {}
        self._configs: Dict[str, EngineConfig] = {}
        self._register_default_engines()
    
    def _register_default_engines(self):
        """Register default engines."""
        self.register_engine("qe", QuantumEspressoEngine)
        # TODO: Register Wannier90, LAMMPS, etc. when implemented
    
    def register_engine(self, name: str, engine_class: Type[Engine], config: Optional[EngineConfig] = None):
        """
        Register an engine class.
        
        Args:
            name: Engine identifier (e.g., "qe", "wannier90")
            engine_class: Engine class (subclass of Engine)
            config: Optional default configuration
        """
        if not issubclass(engine_class, Engine):
            raise TypeError(f"Engine class must be a subclass of Engine")
        self._engines[name] = engine_class
        if config:
            self._configs[name] = config
    
    def create_engine(self, name: str, config: Optional[EngineConfig] = None) -> Engine:
        """
        Create an engine instance.
        
        Args:
            name: Engine identifier
            config: Engine configuration (uses default if not provided)
            
        Returns:
            Engine instance
        """
        if name not in self._engines:
            raise ValueError(f"Unknown engine: {name}")
        
        engine_class = self._engines[name]
        if config is None:
            config = self._configs.get(name)
            if config is None:
                # Create default config
                config = EngineConfig(name=name)
        
        return engine_class(config)
    
    def get_available_engines(self) -> list[str]:
        """Get list of registered engine names."""
        return list(self._engines.keys())
    
    def detect_engine(self, name: str, search_paths: Optional[list[Path]] = None) -> Optional[EngineConfig]:
        """
        Detect engine installation and return configuration.
        
        Args:
            name: Engine identifier
            search_paths: Optional list of paths to search (default: common locations)
            
        Returns:
            EngineConfig if engine is detected, None otherwise
        """
        if name not in self._engines:
            return None
        
        if search_paths is None:
            search_paths = self._get_default_search_paths()
        
        # Try to find engine executable
        engine_class = self._engines[name]
        
        # Create a temporary instance to use its detection method
        temp_config = EngineConfig(name=name)
        temp_engine = engine_class(temp_config)
        
        # Search for executable
        for search_path in search_paths:
            temp_config.executable_path = search_path
            temp_engine.config = temp_config
            if temp_engine.detect_executable():
                return temp_config
        
        return None
    
    def _get_default_search_paths(self) -> list[Path]:
        """Get default search paths for engine executables."""
        paths = []
        
        # Common installation locations
        if platform.system() == "Windows":
            paths.extend([
                Path("C:/Program Files/QuantumEspresso"),
                Path("C:/QuantumEspresso"),
                Path.home() / "QuantumEspresso",
            ])
        else:  # Linux/macOS
            paths.extend([
                Path("/usr/local/bin"),
                Path("/usr/bin"),
                Path.home() / "qe" / "bin",
                Path.home() / "quantum-espresso" / "bin",
                Path("/opt/quantum-espresso/bin"),
            ])
        
        # Also check PATH
        import shutil
        for exe in ["pw.x", "pw.exe"]:
            exe_path = shutil.which(exe)
            if exe_path:
                paths.append(Path(exe_path).parent)
                break
        
        return paths


# Global registry instance
_registry = EngineRegistry()


def get_registry() -> EngineRegistry:
    """Get the global engine registry."""
    return _registry

