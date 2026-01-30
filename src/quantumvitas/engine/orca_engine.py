"""ORCA quantum chemistry engine.

Implements chain-based execution model where each chain is executed
as a single ORCA job with fused input.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import Engine


@dataclass
class ORCAEngineConfig:
    """ORCA engine configuration."""
    orca_bin: Optional[Path] = None
    nprocs: int = 1
    timeout: int = 3600  # 1 hour default timeout


@dataclass
class ORCAStepResult:
    """Result of executing a step within a chain."""
    step_ulid: str
    success: bool
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None


class ORCAEngine(Engine):
    """
    ORCA quantum chemistry engine.

    Executes ORCA as external process, compiles chains to single input files.
    Each chain runs as one ORCA job - this is the STRONG-CHAIN model.
    """

    name = "orca"

    def __init__(
        self,
        orca_bin: Optional[Path] = None,
        config: Optional[ORCAEngineConfig] = None,
        defer_binary_resolution: bool = False,
    ):
        """
        Initialize ORCA engine.

        Args:
            orca_bin: Path to ORCA binary (optional, auto-resolved)
            config: Engine configuration
            defer_binary_resolution: If True, do not resolve binary in __init__.
                Binary will be resolved on first use (probe/run_chain).
                Use this for capability queries when binary may not be available.
        """
        self.config = config or ORCAEngineConfig()
        self._defer_binary_resolution = defer_binary_resolution
        self._orca_binary: Optional[Path] = None
        self._orca_dir: Optional[Path] = None

        if orca_bin:
            # Use provided path
            if orca_bin.is_dir():
                self._orca_dir = orca_bin
                self._orca_binary = orca_bin / "orca"
            else:
                self._orca_binary = orca_bin
                self._orca_dir = orca_bin.parent
        elif self.config.orca_bin:
            # Use config path
            if self.config.orca_bin.is_dir():
                self._orca_dir = self.config.orca_bin
                self._orca_binary = self.config.orca_bin / "orca"
            else:
                self._orca_binary = self.config.orca_bin
                self._orca_dir = self.config.orca_bin.parent
        elif not defer_binary_resolution:
            # Auto-resolve (only if not deferred)
            from quantumvitas.core.engines.orca_resolver import resolve_orca_bin_dir
            self._orca_dir = resolve_orca_bin_dir()
            self._orca_binary = self._orca_dir / "orca"
    
    def _ensure_binary_resolved(self) -> None:
        """Ensure ORCA binary is resolved. Raises RuntimeError if not found."""
        if self._orca_binary is not None and self._orca_dir is not None:
            return  # Already resolved
        
        if self._defer_binary_resolution:
            # Now we need to resolve
            from quantumvitas.core.engines.orca_resolver import resolve_orca_bin_dir
            self._orca_dir = resolve_orca_bin_dir()
            self._orca_binary = self._orca_dir / "orca"
    
    @property
    def orca_binary(self) -> Path:
        """Get ORCA binary path. Resolves if deferred."""
        self._ensure_binary_resolved()
        assert self._orca_binary is not None
        return self._orca_binary
    
    @property
    def orca_dir(self) -> Path:
        """Get ORCA directory. Resolves if deferred."""
        self._ensure_binary_resolved()
        assert self._orca_dir is not None
        return self._orca_dir

    @property
    def supported_presets(self) -> List[str]:
        """
        ORCA engine supports QC-based preset dimensions.
        
        Returns:
            List of supported preset dimensions: qc_precision
        """
        return ["qc_precision"]

    def probe(self) -> Tuple[bool, str]:
        """
        Check if ORCA is available.

        Returns:
            Tuple of (available, version_or_error_message)
        """
        try:
            self._ensure_binary_resolved()
        except RuntimeError as e:
            return False, str(e)
        
        if not self.orca_binary.exists():
            return False, f"ORCA binary not found at {self.orca_binary}"

        try:
            # ORCA prints version info when run without arguments
            result = subprocess.run(
                [str(self.orca_binary)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout + result.stderr

            # Look for ORCA version in output
            for line in output.split('\n'):
                if 'ORCA' in line:
                    return True, line.strip()

            return True, "ORCA (version unknown)"
        except subprocess.TimeoutExpired:
            return False, "ORCA timed out during version check"
        except Exception as e:
            return False, str(e)

    def supported_step_types(self) -> List[str]:
        """Return list of supported step types."""
        return [
            "orca_scf",
            "orca_hf",
            "orca_td",
            "orca_relax",
            "orca_mp2",  # Future
            "orca_freq",  # Future
        ]

    def _build_command(self, input_file: Path) -> List[str]:
        """Build ORCA command line."""
        return [str(self.orca_binary), str(input_file)]

    def run_step(self, step, working_dir: Path) -> StepResult:
        """
        Execute a single ORCA step.
        
        For ORCA, single steps are executed as chains of length 1.
        This method delegates to run_step_with_chain with a single-step chain.
        
        Args:
            step: Step object to execute
            working_dir: Working directory for execution
            
        Returns:
            StepResult with execution status
        """
        # Extract structure_ulid and project_root from step.options (set by handler)
        structure_ulid = None
        project_root = None
        
        if hasattr(step, 'options'):
            structure_ulid = step.options.get('structure_ulid') or step.options.get('structure_id')
            project_root_str = step.options.get('project_root')
            if project_root_str:
                project_root = Path(project_root_str)
        
        return self.run_step_with_chain(
            target_step=step,
            chain_steps=[step],  # Chain of length 1
            calculation_raw_dir=working_dir,
            structure_ulid=structure_ulid,
            project_root=project_root,
        )

    def run_chain(
        self,
        chain: Any,  # QCChain
        working_dir: Path,
        molecule: Any,
        fresh: bool = False,
    ) -> List[ORCAStepResult]:
        """
        Execute a chain as single ORCA job.

        This is the core execution method. Each chain runs as one ORCA process
        with all steps fused into a single input file.

        Args:
            chain: QCChain to execute
            working_dir: Directory for I/O (e.g., calc/raw/chains/chain01_scf/)
            molecule: Molecule object with atoms, charge, multiplicity
            fresh: Force fresh run (NoAutoStart)

        Returns:
            List of ORCAStepResult for each step in chain
            
        Raises:
            RuntimeError: If ORCA binary is not found (only checked at execution time)
        """
        # Ensure binary is resolved before execution
        self._ensure_binary_resolved()
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_energy,
            get_tddft_excitations,
            is_converged,
        )
        from pymatgen.core import Molecule as PMGMolecule

        start_time = time.time()

        # Ensure working directory exists
        working_dir.mkdir(parents=True, exist_ok=True)

        # Convert pymatgen Molecule to MoleculeLike adapter
        # MoleculeLike expects: atoms (str), charge (int), multiplicity (int)
        # pymatgen Molecule has: spin_multiplicity (not multiplicity)
        if isinstance(molecule, PMGMolecule):
            # Create adapter object
            class MoleculeAdapter:
                def __init__(self, mol: PMGMolecule):
                    # Convert to XYZ string format
                    xyz_lines = []
                    for site in mol:
                        symbol = site.specie.symbol
                        coords = site.coords
                        xyz_lines.append(f"{symbol:4s} {coords[0]:15.10f} {coords[1]:15.10f} {coords[2]:15.10f}")
                    self.atoms = "\n".join(xyz_lines)
                    self.charge = mol.charge
                    self.multiplicity = mol.spin_multiplicity  # pymatgen uses spin_multiplicity
            
            molecule_adapter = MoleculeAdapter(molecule)
        else:
            # Assume it's already MoleculeLike
            molecule_adapter = molecule

        # 1. Compile chain to input file
        compiler = ORCAInputCompiler()
        input_content = compiler.compile(
            chain,
            molecule_adapter,
            fresh=fresh,
            nprocs=self.config.nprocs,
        )

        # 2. Write input file
        input_file = working_dir / f"{chain.key}.inp"
        input_file.write_text(input_content)

        # 3. Execute ORCA
        output_file = working_dir / f"{chain.key}.out"
        cmd = self._build_command(input_file)

        # Setup environment
        env = os.environ.copy()
        # Ensure ORCA can find its helper binaries
        env["PATH"] = f"{self.orca_dir}:{env.get('PATH', '')}"

        success = False
        return_code = -1
        error_msg = None

        try:
            with open(output_file, 'w') as out_f:
                result = subprocess.run(
                    cmd,
                    cwd=working_dir,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=self.config.timeout,
                )
            return_code = result.returncode
            success = return_code == 0
        except subprocess.TimeoutExpired:
            error_msg = f"ORCA timed out after {self.config.timeout}s"
        except Exception as e:
            error_msg = str(e)

        execution_time = time.time() - start_time

        # 4. Parse results
        property_file = working_dir / f"{chain.key}.property.txt"
        parsed_properties = {}
        if property_file.exists():
            try:
                parsed_properties = parse_orca_property_txt(property_file)
            except Exception:
                pass

        # 5. Check convergence if property file parsed
        if parsed_properties:
            converged = is_converged(parsed_properties)
            if not converged:
                success = False
                if not error_msg:
                    error_msg = "SCF did not converge"

        # 6. Build per-step results
        results = []
        for step in chain.all_steps:
            step_result = self._extract_step_result(
                step=step,
                chain_key=chain.key,
                success=success,
                properties=parsed_properties,
                working_dir=working_dir,
                execution_time=execution_time,
                error_msg=error_msg,
            )
            results.append(step_result)

        return results

    def _extract_step_result(
        self,
        step: Any,
        chain_key: str,
        success: bool,
        properties: Dict[str, Any],
        working_dir: Path,
        execution_time: float,
        error_msg: Optional[str],
    ) -> ORCAStepResult:
        """Extract results for a specific step from chain output."""
        from quantumvitas.engines.orca.property_parser import (
            get_energy,
            get_tddft_excitations,
        )

        metrics: Dict[str, Any] = {
            "execution_time": execution_time,
        }

        if step.step_type_gen in ("scf", "hf", "dft"):
            # SCF-like step: extract energy
            energy = get_energy(properties)
            if energy is not None:
                metrics["energy"] = energy
                metrics["energy_unit"] = "Hartree"

            # Extract additional SCF info
            if "Calculation_Info" in properties:
                info = properties["Calculation_Info"]
                if "NumOfAtoms" in info:
                    metrics["n_atoms"] = info["NumOfAtoms"]
                if "NumOfElectrons" in info:
                    metrics["n_electrons"] = info["NumOfElectrons"]

            # Check convergence
            if "Single_Point_Data" in properties:
                spd = properties["Single_Point_Data"]
                metrics["converged"] = spd.get("Converged", False)

        elif step.step_type_gen == "td":
            # TDDFT step: extract excitations
            tddft_data = get_tddft_excitations(properties)
            if tddft_data:
                if "excitation_energies_ev" in tddft_data:
                    metrics["excitation_energies"] = tddft_data["excitation_energies_ev"]
                    metrics["excitation_energies_unit"] = "eV"
                if "nroots" in tddft_data:
                    metrics["nroots"] = tddft_data["nroots"]
                if "mode" in tddft_data:
                    metrics["tddft_mode"] = tddft_data["mode"]

        # Build artifacts dict
        artifacts = {
            "input": str(working_dir / f"{chain_key}.inp"),
            "output": str(working_dir / f"{chain_key}.out"),
        }
        property_file = working_dir / f"{chain_key}.property.txt"
        if property_file.exists():
            artifacts["property"] = str(property_file)
        gbw_file = working_dir / f"{chain_key}.gbw"
        if gbw_file.exists():
            artifacts["gbw"] = str(gbw_file)

        return ORCAStepResult(
            step_ulid=step.meta.id,
            success=success,
            metrics=metrics,
            artifacts=artifacts,
            error=error_msg,
        )

    def run_step_with_chain(
        self,
        target_step,
        chain_steps: List[Any],
        calculation_raw_dir: Path,
        structure_ulid: Optional[str] = None,
        project_root: Optional[Path] = None,
    ) -> "StepResult":
        """
        Run an ORCA dependency chain.
        
        This method adapts the ORCA chain execution model to match the
        pyscf_engine.run_step_with_chain() interface used by handlers.
        
        Args:
            target_step: Target Step object
            chain_steps: List of Step objects in dependency order (from root to target)
            calculation_raw_dir: Base working directory (calc/raw/)
            structure_ulid: Structure resource ULID (for Molecule loading)
            project_root: Project root path (for structure resolution)
            
        Returns:
            StepResult for the target step
        """
        import time
        from quantumvitas.engine.base import StepResult
        from quantumvitas.engine.qc_engine_base import QCChain, detect_chains
        from quantumvitas.io.structure_io import read_structure
        from quantumvitas.core.resolution import require_structure
        from pymatgen.core import Molecule as PMGMolecule
        
        start_time = time.time()
        calculation_raw_dir = Path(calculation_raw_dir)
        
        # 1. Validate inputs
        if not structure_ulid:
            return StepResult(
                step_type="orca_relax",
                input_file=calculation_raw_dir / "chain.inp",
                success=False,
                error="Structure ID is required for ORCA chain execution",
                execution_time=time.time() - start_time,
            )
        if not project_root:
            return StepResult(
                step_type="orca_relax",
                input_file=calculation_raw_dir / "chain.inp",
                success=False,
                error="Project root is required for structure resolution",
                execution_time=time.time() - start_time,
            )
        
        # 2. Load Molecule
        try:
            structure_resolved = require_structure(project_root, structure_ulid)
            structure_path = structure_resolved.absolute_path
            molecule = read_structure(structure_path)
            
            if not isinstance(molecule, PMGMolecule):
                return StepResult(
                    step_type="orca_relax",
                    input_file=calculation_raw_dir / "chain.inp",
                    success=False,
                    error=f"Expected Molecule for ORCA, got {type(molecule)}",
                    execution_time=time.time() - start_time,
                )
        except Exception as e:
            return StepResult(
                step_type="orca_relax",
                input_file=calculation_raw_dir / "chain.inp",
                success=False,
                error=f"Failed to load molecule: {e}",
                execution_time=time.time() - start_time,
            )
        
        # 3. Build QCChain from chain_steps
        # For ORCA, we detect chains from steps (SCF root + downstream)
        # detect_chains expects steps to have public_type attribute
        # We need to add it from registry based on step_type
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()
        
        # Add public_type to steps for detect_chains
        # Also load parameters from step.yaml if not already in step object
        steps_with_public_type = []
        for step in chain_steps:
            # Get public_type from registry
            step_type = getattr(step, 'step_type', None)
            if not step_type:
                # Try to read from step.yaml
                if hasattr(step, 'meta') and hasattr(step.meta, 'path') and step.meta.path:
                    step_yaml_path = project_root / step.meta.path
                    if step_yaml_path.exists():
                        import yaml
                        step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
                        step_type = step_data.get("step_type")
            
            if step_type:
                spec = registry.get(step_type)
                step_type_gen = spec.step_type_gen if spec else step_type
                
                # Load parameters from step.yaml if not in step object
                parameters = {}
                if hasattr(step, 'parameters'):
                    parameters = step.parameters.copy() if isinstance(step.parameters, dict) else step.parameters
                elif hasattr(step, 'meta') and hasattr(step.meta, 'path') and step.meta.path:
                    step_yaml_path = project_root / step.meta.path
                    if step_yaml_path.exists():
                        import yaml
                        step_data = yaml.safe_load(step_yaml_path.read_text()) or {}
                        parameters = step_data.get("parameters", {})
                
                # Create a wrapper object with step_type_gen and parameters
                class StepWrapper:
                    def __init__(self, step, step_type_gen, step_type_spec, parameters):
                        self.step = step
                        self.id = step.meta.id
                        self.step_type_gen = step_type_gen
                        self.step_type_spec = step_type_spec
                        self.parameters = parameters
                        # Forward other attributes
                        if hasattr(step, 'options'):
                            self.options = step.options
                
                steps_with_public_type.append(StepWrapper(step, step_type_gen, step_type, parameters))
            else:
                # No step_type, skip this step
                continue
        
        chains = detect_chains(steps_with_public_type)
        
        # If no chains detected (e.g., relax step without SCF root),
        # create a single-step chain with the first step as root
        if not chains:
            if not steps_with_public_type:
                return StepResult(
                    step_type="orca_relax",
                    input_file=calculation_raw_dir / "chain.inp",
                    success=False,
                    error="No valid steps provided",
                    execution_time=time.time() - start_time,
                )
            # Create a single-step chain for relax (or other non-SCF steps)
            from quantumvitas.engine.qc_engine_base import QCChain, derive_chain_key
            single_step = steps_with_public_type[0]
            chain = QCChain(scf_root=single_step, downstream=[], key="")
            chain.key = derive_chain_key(chain, chain_index=1)
        else:
            chain = chains[0]
        
        # Use wrapped steps directly - they have public_type and parameters
        # run_chain will use these wrapped steps which have all needed attributes
        
        # 4. Set up working directory
        # ORCA recipe sets job.working_dir to calc_raw_dir / namespace_folder (e.g., calc/raw/scf_ABCDEF/)
        # Handler passes this as calculation_raw_dir, so we use it directly
        working_dir = Path(calculation_raw_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # 5. Execute chain
        try:
            orca_results = self.run_chain(
                chain=chain,  # Use chain with wrapped steps (has public_type and parameters)
                working_dir=working_dir,
                molecule=molecule,
                fresh=True,  # Always fresh for explicit runs
            )
        except Exception as e:
            return StepResult(
                step_type="orca_relax",
                input_file=working_dir / f"{chain.key}.inp",
                success=False,
                error=f"ORCA chain execution failed: {e}",
                execution_time=time.time() - start_time,
            )
        
        # 6. Convert ORCAStepResult to StepResult
        # Find result for target step
        target_result = None
        for orca_result in orca_results:
            if orca_result.step_ulid == target_step.meta.id:
                target_result = orca_result
                break
        
        if target_result is None and orca_results:
            # Use last result if target not found explicitly
            target_result = orca_results[-1]
        
        if target_result is None:
            return StepResult(
                step_type="orca_relax",
                input_file=working_dir / f"{chain.key}.inp",
                success=False,
                error="No result found for target step",
                execution_time=time.time() - start_time,
            )
        
        # Store working_dir and chain_key in parsed_output for post-processing
        # chain_key is the full chain key (e.g., "chain01_relax") that matches actual file names
        parsed_output = {
            "working_dir": str(working_dir),
            "chain_key": chain.key,  # Full chain key (e.g., "chain01_relax")
            "metrics": target_result.metrics,
            "artifacts": target_result.artifacts,
        }
        
        return StepResult(
            step_type=target_step.step_type_spec or "orca_relax",
            input_file=Path(target_result.artifacts.get("input", working_dir / f"{chain.key}.inp")),
            output_file=Path(target_result.artifacts.get("output", working_dir / f"{chain.key}.out")),
            success=target_result.success,
            error=target_result.error,
            execution_time=time.time() - start_time,
            parsed_output=parsed_output,
        )


# Factory function for engine registry
def create_orca_engine(config: Optional[ORCAEngineConfig] = None) -> ORCAEngine:
    """Create ORCA engine instance."""
    return ORCAEngine(config=config)
