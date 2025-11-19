"""
Quantum ESPRESSO engine implementation.

This module provides the Quantum ESPRESSO-specific implementation
of the Engine interface.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import shutil

from .base import Engine, EngineConfig
from .qe_input import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType, QEModule
)


class QuantumEspressoEngine(Engine):
    """
    Quantum ESPRESSO engine implementation.
    
    Supports pw.x, ph.x, bands.x, dos.x, projwfc.x, and other QE executables.
    """
    
    # Mapping of step types to QE executables
    EXECUTABLE_MAP = {
        "scf": "pw.x",
        "nscf": "pw.x",
        "opt": "pw.x",
        "md": "pw.x",
        "ph": "ph.x",
        "q2r": "q2r.x",
        "matdyn": "matdyn.x",
        "bands": "bands.x",
        "dos": "dos.x",
        "projwfc": "projwfc.x",
        "sumpdos": "sumpdos.x",
        "tddft_lanczos": "turbo_lanczos.x",
        "tddft_spectrum": "turbo_spectrum.x",
        "neb": "neb.x",
        "pp": "pp.x",
        "gipaw": "gipaw.x",
    }
    
    # Mapping of QE modules to their primary namelists
    MODULE_NAMELISTS = {
        "pw": ["control", "system", "electrons", "ions", "cell"],
        "ph": ["inputph"],
        "pp": ["inputpp"],
        "gipaw": ["inputgipaw"],
        "neb": ["path"],
        "bands": ["control", "system", "electrons", "bands"],
        "dos": ["control", "system", "electrons", "dos"],
        "projwfc": ["control", "system", "electrons", "projwfc"],
    }
    
    def __init__(self, config: EngineConfig):
        """Initialize Quantum ESPRESSO engine."""
        super().__init__(config)
        self.qe_bin_dir = config.executable_path or Path()
    
    def detect_executable(self) -> bool:
        """Detect if QE executables are available."""
        # Check for at least one common executable
        test_executables = ["pw.x", "pw.exe"]
        for exe in test_executables:
            exe_path = self.qe_bin_dir / exe
            if exe_path.exists() and exe_path.is_file():
                return True
        return False
    
    def generate_input(
        self,
        step_type: str,
        input_data: Dict[str, Any],
        working_dir: Path,
        input_filename: Optional[str] = None
    ) -> Path:
        """
        Generate QE input file from structured input data.
        
        Args:
            step_type: Type of calculation step
            input_data: Dictionary containing:
                - 'namelists': Dict of namelist_name -> parameters
                - 'cards': List of card data
            working_dir: Working directory
            input_filename: Optional custom filename
            
        Returns:
            Path to generated input file
        """
        if input_filename is None:
            input_filename = self.get_default_input_filename(step_type)
        
        input_path = working_dir / input_filename
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Create QEInput object
        qe_input = QEInput()
        
        # Add namelists
        namelists_data = input_data.get('namelists', {})
        for nl_name, nl_params in namelists_data.items():
            namelist = QENamelist(name=nl_name, parameters=nl_params)
            qe_input.namelists.append(namelist)
        
        # Add cards
        cards_data = input_data.get('cards', [])
        for card_data in cards_data:
            card_type = QECardType[card_data['type']]
            card = QECard(
                card_type=card_type,
                option=card_data.get('option'),
                data=card_data.get('data', [])
            )
            qe_input.cards.append(card)
        
        # Generate and write file
        QEInputGenerator.write_file(qe_input, input_path)
        
        return input_path
    
    def build_command(
        self,
        step_type: str,
        input_file: Path,
        working_dir: Path
    ) -> List[str]:
        """Build QE command with MPI support if configured."""
        executable = self.EXECUTABLE_MAP.get(step_type, "pw.x")
        exe_path = self.qe_bin_dir / executable
        
        # Check for .exe on Windows
        if not exe_path.exists():
            exe_path = self.qe_bin_dir / f"{executable}.exe"
        
        if not exe_path.exists():
            raise FileNotFoundError(f"QE executable not found: {executable}")
        
        command = [str(exe_path)]
        
        # Add input file flag (different modules may use different flags)
        # Most use -inp, but some use -i or other flags
        if step_type in ["ph", "pp", "gipaw"]:
            # Some modules use -i instead of -inp
            command.extend(["-i", str(input_file.name)])
        else:
            command.extend(["-inp", str(input_file.name)])
        
        # Add MPI wrapper if configured
        if self.config.mpi_command and self.config.mpi_cores > 1:
            mpi_cmd = [self.config.mpi_command, "-np", str(self.config.mpi_cores)]
            command = mpi_cmd + command
        
        return command
    
    def detect_module_from_input(self, input_file: Path) -> QEModule:
        """
        Detect QE module from input file.
        
        Args:
            input_file: Path to QE input file
            
        Returns:
            Detected QE module
        """
        qe_input = self.parse_input_file(input_file)
        return qe_input.module or QEModule.UNKNOWN
    
    def parse_output(
        self,
        output_file: Path,
        step_type: str
    ) -> Dict[str, Any]:
        """
        Parse QE output file.
        
        This is a placeholder. Full implementation will extract:
        - Total energy
        - Forces
        - Stresses
        - Band structure data
        - DOS data
        - etc.
        """
        if not output_file.exists():
            return {"error": "Output file not found"}
        
        # TODO: Implement full QE output parsing
        # This will use regex or specialized parsers to extract data
        results = {
            "step_type": step_type,
            "output_file": str(output_file),
            "parsed": False,  # Placeholder
        }
        
        return results
    
    def parse_input_file(self, input_file: Path) -> QEInput:
        """
        Parse a QE input file to structured format.
        
        Args:
            input_file: Path to QE input file
            
        Returns:
            QEInput object
        """
        return QEInputParser.parse_file(input_file)
    
    def generate_input_from_file(
        self,
        input_file: Path,
        output_file: Path,
        modifications: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Read a QE input file, optionally modify it, and write to output.
        
        Args:
            input_file: Path to input QE file
            output_file: Path to output QE file
            modifications: Optional dict with modifications:
                - 'namelists': Dict of namelist_name -> {param: value}
                - 'cards': List of card modifications
                
        Returns:
            Path to output file
        """
        qe_input = QEInputParser.parse_file(input_file)
        
        # Apply modifications
        if modifications:
            # Modify namelists
            for nl_name, nl_params in modifications.get('namelists', {}).items():
                nl = qe_input.get_namelist(nl_name)
                if nl:
                    nl.parameters.update(nl_params)
            
            # Modify cards (simplified - full implementation would be more complex)
            # TODO: Implement card modifications
        
        # Write output
        QEInputGenerator.write_file(qe_input, output_file)
        return output_file
    
    def get_default_input_filename(self, step_type: str) -> str:
        """Get default QE input filename."""
        # QE typically uses .in or .pwi for input files
        return f"{step_type}.in"
    
    def get_default_output_filename(self, step_type: str, input_filename: str) -> str:
        """Get default QE output filename."""
        # QE typically uses .out or .pwo for output files
        base = Path(input_filename).stem
        return f"{base}.out"

