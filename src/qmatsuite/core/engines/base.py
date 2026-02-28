"""
Base engine interface for quantum chemistry codes.

This module defines the abstract base class for all computational engines
(Quantum ESPRESSO, Wannier90, LAMMPS, etc.).
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


class EngineConfigError(Exception):
    """Raised when engine configuration is invalid."""


@dataclass
class EngineConfig:
    """Configuration for a computational engine."""
    name: str
    executable_path: Optional[Path] = None
    qe_home: Optional[Path] = None  # For QE: path to QE home directory (contains bin/ and test-suite/)
    mpi_command: Optional[str] = None
    mpi_cores: int = 1
    omp_threads: int = 1
    environment: Dict[str, str] = None

    def __post_init__(self):
        if self.environment is None:
            self.environment = {}
        # Environment variables override instance config (highest priority)
        env_cores = os.environ.get("QMS_MPI_CORES", "")
        if env_cores.isdigit():
            self.mpi_cores = int(env_cores)
        env_cmd = os.environ.get("QMS_MPI_COMMAND")
        if env_cmd:
            self.mpi_command = env_cmd
        # Validate: MPI mode requires mpi_command to exist in PATH
        if self.mpi_cores > 1:
            if not self.mpi_command:
                self.mpi_command = "mpirun"
            if not shutil.which(self.mpi_command):
                raise EngineConfigError(
                    f"QMS_MPI_CORES={self.mpi_cores} but '{self.mpi_command}' not found in PATH. "
                    f"Either install MPI (e.g., `brew install open-mpi`) or "
                    f"unset QMS_MPI_CORES to run in serial mode."
                )


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
        step_type_gen: str,
        input_data: Dict[str, Any],
        working_dir: Path,
        input_filename: Optional[str] = None
    ) -> Path:
        """
        Generate input file for a calculation step.
        
        Args:
            step_type_gen: Gen step type (e.g., "scf", "nscf") - GEN only
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
        step_type_spec: str,
        input_file: Path,
        working_dir: Path
    ) -> List[str]:
        """
        Build the command to execute the calculation.
        
        Args:
            step_type_spec: Spec step type (e.g., "qe_scf", "pyscf_scf") - SPEC only
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
        step_type_spec: str
    ) -> Dict[str, Any]:
        """
        Parse output file and extract results.
        
        Args:
            output_file: Path to output file
            step_type_spec: Spec step type (e.g., "qe_scf", "pyscf_scf") - SPEC only
            
        Returns:
            Dictionary containing parsed results
        """
        pass
    
    @abstractmethod
    def get_default_input_filename(self, step_type_gen: str) -> str:
        """
        Get default input filename for a step type.
        
        Args:
            step_type_gen: Type of calculation step (gen type, e.g., "scf", "nscf")
            
        Returns:
            Default input filename
        """
        pass
    
    @abstractmethod
    def get_default_output_filename(self, step_type_gen: str, input_filename: str) -> str:
        """
        Get default output filename for a step type.
        
        Args:
            step_type_gen: Type of calculation step (gen type, e.g., "scf", "nscf")
            input_filename: Input filename
            
        Returns:
            Default output filename
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any], step_type_gen: str) -> Tuple[bool, Optional[str]]:
        """
        Validate input data before generating input file.
        
        Args:
            input_data: Input parameters to validate
            step_type_gen: Type of calculation step (gen type, e.g., "scf", "nscf")
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Default implementation - engines can override
        return True, None
    
    def get_required_inputs(self, step_type_gen: str) -> List[str]:
        """
        Get list of required input parameters for a step type.
        
        Args:
            step_type_gen: Type of calculation step (gen type, e.g., "scf", "nscf")
            
        Returns:
            List of required parameter names
        """
        return []

