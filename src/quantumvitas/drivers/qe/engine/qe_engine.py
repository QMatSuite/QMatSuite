"""
Quantum ESPRESSO engine implementation.

This module provides the Quantum ESPRESSO-specific implementation
of the Engine interface.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import shutil
import platform
import os

from quantumvitas.core.engines.base import Engine, EngineConfig
from quantumvitas.drivers.qe.engine.qe_installation import QEInstallation
from quantumvitas.io import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType, QEModule
)
from quantumvitas.drivers.qe.engine.qe_calculation import QECalculationRunner, StepResult, CalculationResult


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
        "bands_pw": "pw.x",  # pw.x bands calculation (calculation='bands')
        "ph": "ph.x",
        "q2r": "q2r.x",
        "matdyn": "matdyn.x",
        "bands": "bands.x",  # bands.x post-processing tool
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
        # Wannier90 step types
        "w90_preproc": "wannier90.x",
        "pw2wannier90": "pw2wannier90.x",
        "w90_run": "wannier90.x",
    }
    
    # Mapping of QE modules to their primary namelists.
    # Note: This is a convenience mapping for module detection.
    # For complete parameter metadata and documentation URLs, see:
    # - qe_module_parameters.json (via quantumvitas.data.qe_metadata)
    # - docs/QE_MODULE_DOCUMENTATION.md
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
        
        Uses two-state QE resolution model:
        - If config.qe_home or config.executable_path provided: use that (explicit override)
        - Otherwise: resolve via settings.qe.bin_dir (external) or internal QE (auto-selected)
        
        Args:
            config: Engine configuration. If qe_home or executable_path is provided,
                   it should point to QE home directory (contains bin/ and test-suite/).
                   If None, will use two-state resolver.
        """
        super().__init__(config)
        
        # Explicit override: use provided path (backward compatibility for tests)
        if config.qe_home:
            self._installation = QEInstallation(qe_home=config.qe_home)
        elif config.executable_path:
            # Backward compatibility: treat executable_path as QE home
            self._installation = QEInstallation(qe_home=config.executable_path)
        else:
            # Use two-state resolver
            from quantumvitas.drivers.qe.engine.qe_resolver import resolve_qe_bin_dir
            
            try:
                qe_bin_dir = resolve_qe_bin_dir()
                # Convert bin_dir to qe_home (parent of bin)
                qe_home = qe_bin_dir.parent
                self._installation = QEInstallation(qe_home=qe_home)
            except RuntimeError as e:
                # Re-raise with clear error message
                raise RuntimeError(str(e)) from e
        
        # For backward compatibility
        self.qe_bin_dir = self._installation.bin_dir or Path()
        self._detected_executables = {}  # Cache for detected executables
        
        # Calculation runner for step/calculation execution
        self.calculation_runner = QECalculationRunner(self)
    
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
        
        # Always prefer QE_HOME/bin if available
        installation_path = None
        if self._installation and self._installation.qe_home:
            installation_path = self._installation.qe_home / "bin" / executable_name
            if installation_path.exists() and os.access(installation_path, os.X_OK):
                return installation_path

        # Build search paths (legacy/back-compat)
        if search_paths is None:
            search_paths = []
            
            # Priority 1: Add configured bin directory from QE_HOME
            # First check if installation has a valid qe_home
            if self._installation and self._installation.qe_home:
                qe_home_bin = self._installation.qe_home / "bin"
                if qe_home_bin.exists() and qe_home_bin not in search_paths:
                    search_paths.append(qe_home_bin)
            
            # Priority 2: Add configured bin directory (backward compatibility)
            # NOTE: According to two-state resolver contract, qe_bin_dir is always the bin directory,
            # never the QE root. So we should never append "/bin" again.
            if self.qe_bin_dir:
                # Check if qe_bin_dir is actually a QE root (has bin subdirectory)
                # This is for backward compatibility with old code that might pass QE root
                if (self.qe_bin_dir / "bin").exists() and self.qe_bin_dir.name != "bin":
                    # qe_bin_dir is QE root, use bin subdirectory
                    bin_subdir = self.qe_bin_dir / "bin"
                    if bin_subdir not in search_paths:
                        search_paths.append(bin_subdir)
                elif self.qe_bin_dir not in search_paths:
                    # qe_bin_dir is already a bin directory (normal case with two-state resolver)
                    search_paths.append(self.qe_bin_dir)
        
        # Search in specified paths
        for search_path in search_paths:
            exe_path = search_path / executable_name
            if exe_path.exists() and exe_path.is_file() and os.access(exe_path, os.X_OK):
                return exe_path
        
        # Fallback: Search in system PATH and update QE_HOME if possible
        exe_in_path = shutil.which(executable_name)
        if exe_in_path:
            exe_path = Path(exe_in_path)
            if exe_path.exists() and exe_path.is_file():
                inferred_home = QEInstallation.qe_home_from_binary(exe_path)
                if inferred_home:
                    # Refresh installation so future lookups hit QE_HOME/bin
                    self._installation = QEInstallation(qe_home=inferred_home)
                    refreshed = self._installation.qe_home / "bin" / executable_name
                    if refreshed.exists() and os.access(refreshed, os.X_OK):
                        return refreshed
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
                # According to two-state resolver contract, qe_bin_dir is always the bin directory
                search_locations.append(str(self.qe_bin_dir))
                # Only add qe_bin_dir/bin if qe_bin_dir is actually a QE root (for backward compatibility)
                if (self.qe_bin_dir / "bin").exists() and self.qe_bin_dir.name != "bin":
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
        
        Uses stdin redirection (pw.x < input.in) instead of command-line flags,
        except for Wannier90 steps which use command-line arguments.
        
        Args:
            step_type: Type of calculation step
            input_file: Path to input file
            working_dir: Working directory for execution
            
        Returns:
            List of command arguments for subprocess
            
        Raises:
            FileNotFoundError: If executable is not found
        """
        # Convert step_type_spec (e.g., 'qe_bands') to step_type_gen (e.g., 'bands') for lookup
        from quantumvitas.workflow.registry import normalize_step_type_to_gen
        step_gen_type = normalize_step_type_to_gen(step_type)

        executable = self.EXECUTABLE_MAP.get(step_gen_type, "pw.x")

        # Get executable path (handles platform-specific names and search)
        exe_path = self.get_executable_path(executable)

        command = [str(exe_path)]

        # Wannier90-specific command building (use step_type_gen for comparisons)
        if step_gen_type == "w90_preproc":
            # wannier90.x -pp seedname
            # Extract seedname from input file (e.g., diamond.win -> diamond)
            seedname = input_file.stem
            command.append("-pp")
            command.append(seedname)
        elif step_gen_type == "w90_run":
            # wannier90.x seedname
            seedname = input_file.stem
            command.append(seedname)
        elif step_gen_type == "pw2wannier90":
            # pw2wannier90.x -i input.in (use -i flag, NOT stdin)
            # IMPORTANT: Use relative path from working_dir to avoid path issues
            # Always use relative path from working_dir (pw2wannier90.x runs with cwd=working_dir)
            input_file_resolved = Path(input_file)
            
            # Safety check: prevent '.' or directory paths
            if str(input_file_resolved) in (".", "./", ".."):
                raise ValueError(
                    f"Invalid input_file for pw2wannier90: '{input_file_resolved}'. "
                    f"Cannot be '.' or a directory. Must be a valid file path."
                )
            
            if input_file_resolved.is_absolute():
                # Make relative to working_dir if possible
                try:
                    working_dir_resolved = working_dir.resolve()
                    input_file_rel = input_file_resolved.relative_to(working_dir_resolved)
                    # Use relative path (e.g., "pw2wan.in")
                    command.append("-i")
                    command.append(str(input_file_rel))
                except ValueError:
                    # Not relative to working_dir - this is unexpected, but use absolute as fallback
                    # Log a warning but continue (some edge cases might need absolute paths)
                    command.append("-i")
                    command.append(str(input_file_resolved))
            else:
                # Already relative, use as-is (should be relative to working_dir)
                command.append("-i")
                command.append(str(input_file_resolved))
        
        # Add MPI wrapper if configured
        if self.config.mpi_command and self.config.mpi_cores is not None and self.config.mpi_cores > 1:
            mpi_cmd = [self.config.mpi_command, "-np", str(self.config.mpi_cores)]
            command = mpi_cmd + command
        
        return command
    
    def uses_stdin(self, step_type: str) -> bool:
        """
        Check if step type uses stdin for input (vs command-line arguments).
        
        Wannier90 steps (w90_preproc, w90_run) use command-line seedname,
        while most QE steps use stdin redirection.
        
        Args:
            step_type: Type of calculation step
            
        Returns:
            True if step uses stdin, False if uses command-line arguments
        """
        # These Wannier90 steps use command-line arguments, not stdin
        # pw2wannier90 uses -i flag to avoid Errno 21 issues with stdin redirection
        no_stdin_steps = {"w90_preproc", "w90_run", "pw2wannier90"}
        return step_type not in no_stdin_steps
    
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
            "step_type_spec": step_type,
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
    
    def detect_step_type(self, input_file: Path) -> str:
        """
        Detect step type from input file.
        
        This is a convenience method that delegates to the calculation runner.
        
        Args:
            input_file: Path to QE input file
            
        Returns:
            Step type string (e.g., "scf", "nscf", "dos", "bands", "ph", etc.)
        """
        return self.calculation_runner.detect_step_type(input_file)
    
    def run_step(
        self,
        input_file: Path,
        working_dir: Path,
        step_type: Optional[str] = None,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None
    ) -> StepResult:
        """
        Run a single QE calculation step.
        
        This is a convenience method that delegates to the calculation runner.
        
        Args:
            input_file: Path to QE input file
            working_dir: Working directory for execution
            step_type: Optional step type (auto-detected if not provided)
            timeout: Optional timeout in seconds
            environment: Optional environment variables dict
            
        Returns:
            StepResult with execution results
        """
        return self.calculation_runner.run_step(
            input_file=input_file,
            working_dir=working_dir,
            step_type=step_type,
            timeout=timeout,
            environment=environment
        )
    
    def run_calculation(
        self,
        steps: List[Tuple[Path, Optional[str]]],
        working_dir: Path,
        timeout: Optional[float] = None,
        environment: Optional[Dict[str, str]] = None,
        stop_on_error: bool = True
    ) -> CalculationResult:
        """
        Run a calculation of multiple QE calculation steps sequentially.
        
        This is a convenience method that delegates to the calculation runner.
        
        Args:
            steps: List of (input_file, step_type) tuples. step_type can be None for auto-detection.
            working_dir: Working directory for execution
            timeout: Optional timeout per step (in seconds)
            environment: Optional environment variables dict
            stop_on_error: If True, stop calculation on first error
            
        Returns:
            CalculationResult with all step results
        """
        return self.calculation_runner.run_calculation(
            steps=steps,
            working_dir=working_dir,
            timeout=timeout,
            environment=environment,
            stop_on_error=stop_on_error
        )

