"""
Quantum ESPRESSO engine implementation.

This module provides the Quantum ESPRESSO-specific implementation
of the Engine interface.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import shutil
import platform
import os

from .base import Engine, EngineConfig
from .qe_installation import QEInstallation
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
        "cp": "cp.x",
        "ld1": "ld1.x",
        "hp": "hp.x",
        "pwcond": "pwcond.x",
        "postahc": "postahc.x",
        "dynmat": "dynmat.x",
        "oscdft_et": "oscdft_et.x",
        "oscdft_pp": "oscdft_pp.x",
        "band_interpolation": "band_interpolation.x",
        "cppp": "cppp.x",
        "d3hess": "d3hess.x",
        "ppacf": "ppacf.x",
        "pprism": "pprism.x",
    }
    
    # Mapping of QE modules to their primary namelists
    # Documentation links:
    # - pw: https://www.quantum-espresso.org/Doc/INPUT_PW.html
    # - ph: https://www.quantum-espresso.org/Doc/INPUT_PH.html
    # - q2r: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
    # - matdyn: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
    # - pp: https://www.quantum-espresso.org/Doc/INPUT_PP.html
    # - neb: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
    # - cp: https://www.quantum-espresso.org/Doc/INPUT_CP.html
    # - ld1: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
    # - hp: https://www.quantum-espresso.org/Doc/INPUT_HP.html
    # - pwcond: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
    # - bands: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
    # - dos: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
    # - projwfc: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
    # - postahc: https://www.quantum-espresso.org/Doc/INPUT_POSTAHC.html
    # - dynmat: https://www.quantum-espresso.org/Doc/INPUT_DYNMAT.html
    # - oscdft_et: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_ET.html
    # - oscdft_pp: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_PP.html
    # - band_interpolation: https://www.quantum-espresso.org/Doc/INPUT_BAND_INTERPOLATION.html
    # - cppp: https://www.quantum-espresso.org/Doc/INPUT_CPPP.html
    # - d3hess: https://www.quantum-espresso.org/Doc/INPUT_D3HESS.html
    # - ppacf: https://www.quantum-espresso.org/Doc/INPUT_PPACF.html
    # - pprism: https://www.quantum-espresso.org/Doc/INPUT_PPRISM.html
    MODULE_NAMELISTS = {
        "pw": ["control", "system", "electrons", "ions", "cell"],
        "ph": ["inputph"],
        "q2r": ["input"],  # q2r.x uses &input namelist
        "matdyn": ["input"],  # matdyn.x uses &input namelist
        "pp": ["inputpp"],
        "gipaw": ["inputgipaw"],
        "neb": ["path"],  # neb.x uses &PATH namelist (plus embedded pw.x input)
        "cp": ["control", "system", "electrons", "ions", "cell"],  # cp.x similar to pw.x
        "ld1": ["input"],  # ld1.x uses &input namelist
        "hp": ["inputhp"],  # hp.x uses &inputhp namelist
        "pwcond": ["cond"],  # pwcond.x uses &cond namelist
        "bands": ["bands"],  # bands.x uses &BANDS namelist
        "dos": ["dos"],  # dos.x uses &DOS namelist
        "projwfc": ["projwfc"],  # projwfc.x uses &PROJWFC namelist
        "postahc": ["input"],  # postahc.x uses &input namelist
        "dynmat": ["input"],  # dynmat.x uses &input namelist
        "oscdft_et": ["oscdft_et_namelist"],  # oscdft_et.x uses &oscdft_et_namelist
        "oscdft_pp": ["oscdft_pp_namelist"],  # oscdft_pp.x uses &oscdft_pp_namelist
        "band_interpolation": ["interpolation"],  # band_interpolation.x uses &interpolation namelist
        "cppp": ["inputpp"],  # cppp.x uses &inputpp namelist
        "d3hess": ["input"],  # d3hess.x uses &input namelist
        "ppacf": ["plot"],  # ppacf.x uses &plot namelist
        "pprism": ["inputpp", "plot"],  # pprism.x uses &inputpp and &plot namelists
    }
    
    def __init__(self, config: EngineConfig):
        """
        Initialize Quantum ESPRESSO engine.
        
        Automatically detects QE installation if executable_path is not provided.
        
        Args:
            config: Engine configuration. If executable_path is provided, it should
                   point to QE home directory (contains bin/ and test-suite/).
                   If None, will auto-detect.
        """
        super().__init__(config)
        
        # Use qe_home if provided, otherwise fallback to executable_path, otherwise auto-detect
        if config.qe_home:
            self._installation = QEInstallation(qe_home=config.qe_home)
        elif config.executable_path:
            # Backward compatibility: treat executable_path as QE home
            self._installation = QEInstallation(qe_home=config.executable_path)
        else:
            self._installation = QEInstallation()
        
        # For backward compatibility
        self.qe_bin_dir = self._installation.bin_dir or Path()
        self._detected_executables = {}  # Cache for detected executables
    
    @property
    def installation(self) -> QEInstallation:
        """Get QE installation information."""
        return self._installation
    
    @property
    def test_suite_dir(self) -> Optional[Path]:
        """Get QE test-suite directory (auto-detected)."""
        return self._installation.test_suite_dir
    
    @property
    def pseudo_dir(self) -> Optional[Path]:
        """Get QE pseudopotential directory (auto-detected)."""
        return self._installation.pseudo_dir
    
    def find_executable(self, executable_name: str, search_paths: Optional[List[Path]] = None) -> Optional[Path]:
        """
        Find QE executable in specified paths or system PATH.
        
        Args:
            executable_name: Name of executable (e.g., "pw.x", "pw.exe")
            search_paths: Optional list of paths to search. If None, uses:
                         - self.qe_bin_dir
                         - self.qe_bin_dir / "bin" (if qe_bin_dir is QE root)
                         - System PATH
            
        Returns:
            Path to executable if found, None otherwise
        """
        # Determine executable name based on platform
        system = platform.system()
        if system == "Windows":
            if not executable_name.endswith(".exe"):
                executable_name = executable_name.replace(".x", ".exe")
        else:
            # Linux/Mac: use .x extension
            executable_name = executable_name.replace(".exe", ".x")
        
        # Build search paths
        if search_paths is None:
            search_paths = []
            
            # Priority 1: Add configured bin directory from QE_HOME
            # First check if installation has a valid qe_home
            if self._installation and self._installation.qe_home:
                qe_home_bin = self._installation.qe_home / "bin"
                if qe_home_bin.exists() and qe_home_bin not in search_paths:
                    search_paths.append(qe_home_bin)
            
            # Priority 2: Add configured bin directory (backward compatibility)
            if self.qe_bin_dir:
                # If qe_bin_dir is QE root, check bin subdirectory
                if (self.qe_bin_dir / "bin").exists():
                    bin_subdir = self.qe_bin_dir / "bin"
                    if bin_subdir not in search_paths:
                        search_paths.append(bin_subdir)
                elif self.qe_bin_dir not in search_paths:
                    # qe_bin_dir is already a bin directory
                    search_paths.append(self.qe_bin_dir)
        
        # Search in specified paths (QE_HOME/bin first)
        for search_path in search_paths:
            exe_path = search_path / executable_name
            if exe_path.exists() and exe_path.is_file() and os.access(exe_path, os.X_OK):
                return exe_path
        
        # Fallback: Search in system PATH (only if not found in QE_HOME)
        exe_in_path = shutil.which(executable_name)
        if exe_in_path:
            exe_path = Path(exe_in_path)
            if exe_path.exists() and exe_path.is_file():
                return exe_path
        
        return None
    
    def detect_executable(self, executable_name: str = "pw.x") -> bool:
        """
        Detect if a QE executable is available.
        
        Args:
            executable_name: Name of executable to detect (default: "pw.x")
            
        Returns:
            True if executable is found and accessible
        """
        exe_path = self.find_executable(executable_name)
        return exe_path is not None
    
    def get_executable_path(self, executable_name: str) -> Path:
        """
        Get full path to QE executable.
        
        Args:
            executable_name: Name of executable (e.g., "pw.x", "ph.x")
            
        Returns:
            Path to executable
            
        Raises:
            FileNotFoundError: If executable is not found
        """
        # Check cache first
        if executable_name in self._detected_executables:
            return self._detected_executables[executable_name]
        
        exe_path = self.find_executable(executable_name)
        
        if exe_path is None:
            # Build helpful error message
            system = platform.system()
            if system == "Windows":
                expected_name = executable_name.replace(".x", ".exe")
            else:
                expected_name = executable_name.replace(".exe", ".x")
            
            search_locations = []
            if self.qe_bin_dir:
                search_locations.append(str(self.qe_bin_dir))
                search_locations.append(str(self.qe_bin_dir / "bin"))
            search_locations.append("system PATH")
            
            error_msg = (
                f"QE executable '{expected_name}' not found.\n"
                f"Searched in: {', '.join(search_locations)}\n"
                f"Please set executable_path in EngineConfig or ensure '{expected_name}' is in PATH."
            )
            raise FileNotFoundError(error_msg)
        
        # Cache the result
        self._detected_executables[executable_name] = exe_path
        return exe_path
    
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
        """
        Build QE command with MPI support if configured.
        
        Uses stdin redirection (pw.x < input.in) instead of command-line flags.
        
        Args:
            step_type: Type of calculation step
            input_file: Path to input file
            working_dir: Working directory for execution
            
        Returns:
            List of command arguments for subprocess (without input file flags)
            
        Raises:
            FileNotFoundError: If executable is not found
        """
        executable = self.EXECUTABLE_MAP.get(step_type, "pw.x")
        
        # Get executable path (handles platform-specific names and search)
        exe_path = self.get_executable_path(executable)
        
        command = [str(exe_path)]
        
        # No longer add input file flags (-inp or -i)
        # Input will be provided via stdin redirection
        
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

