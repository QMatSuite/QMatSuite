"""
Base engine interface for quantum chemistry codes.

This module defines the abstract base class for all computational engines
(Quantum ESPRESSO, Wannier90, LAMMPS, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class EngineConfig:
    """Configuration for a computational engine."""
    name: str
    executable_path: Optional[Path] = None
    mpi_command: Optional[str] = None
    mpi_cores: int = 1
    omp_threads: int = 1
    environment: Dict[str, str] = None
    
    def __post_init__(self):
        if self.environment is None:
            self.environment = {}


class Engine(ABC):
    """
    Abstract base class for computational engines.
    
    Each engine (QE, Wannier90, LAMMPS, etc.) must implement this interface.
    """
    
    def __init__(self, config: EngineConfig):
        """
        Initialize the engine.
        
        Args:
            config: Engine configuration
        """
        self.config = config
        self.name = config.name
    
    @abstractmethod
    def detect_executable(self) -> bool:
        """
        Detect if the engine executable is available.
        
        Returns:
            True if executable is found and accessible
        """
        pass
    
    @abstractmethod
    def generate_input(
        self,
        step_type: str,
        input_data: Dict[str, Any],
        working_dir: Path,
        input_filename: Optional[str] = None
    ) -> Path:
        """
        Generate input file for a calculation step.
        
        Args:
            step_type: Type of calculation step (e.g., "scf", "nscf")
            input_data: Dictionary containing input parameters
            working_dir: Directory where input file should be created
            input_filename: Optional custom filename (default: engine-specific)
            
        Returns:
            Path to the generated input file
        """
        pass
    
    @abstractmethod
    def build_command(
        self,
        step_type: str,
        input_file: Path,
        working_dir: Path
    ) -> List[str]:
        """
        Build the command to execute the calculation.
        
        Args:
            step_type: Type of calculation step
            input_file: Path to input file
            working_dir: Working directory for execution
            
        Returns:
            List of command arguments (for subprocess)
        """
        pass
    
    @abstractmethod
    def parse_output(
        self,
        output_file: Path,
        step_type: str
    ) -> Dict[str, Any]:
        """
        Parse output file and extract results.
        
        Args:
            output_file: Path to output file
            step_type: Type of calculation step
            
        Returns:
            Dictionary containing parsed results
        """
        pass
    
    @abstractmethod
    def get_default_input_filename(self, step_type: str) -> str:
        """
        Get default input filename for a step type.
        
        Args:
            step_type: Type of calculation step
            
        Returns:
            Default input filename
        """
        pass
    
    @abstractmethod
    def get_default_output_filename(self, step_type: str, input_filename: str) -> str:
        """
        Get default output filename for a step type.
        
        Args:
            step_type: Type of calculation step
            input_filename: Input filename
            
        Returns:
            Default output filename
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any], step_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate input data before generating input file.
        
        Args:
            input_data: Input parameters to validate
            step_type: Type of calculation step
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation - engines can override
        return True, None
    
    def get_required_inputs(self, step_type: str) -> List[str]:
        """
        Get list of required input parameters for a step type.
        
        Args:
            step_type: Type of calculation step
            
        Returns:
            List of required parameter names
        """
        return []

