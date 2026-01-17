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
    step_id: str
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
    ):
        """
        Initialize ORCA engine.

        Args:
            orca_bin: Path to ORCA binary (optional, auto-resolved)
            config: Engine configuration
        """
        self.config = config or ORCAEngineConfig()

        if orca_bin:
            # Use provided path
            if orca_bin.is_dir():
                self.orca_dir = orca_bin
                self.orca_binary = orca_bin / "orca"
            else:
                self.orca_binary = orca_bin
                self.orca_dir = orca_bin.parent
        elif self.config.orca_bin:
            # Use config path
            if self.config.orca_bin.is_dir():
                self.orca_dir = self.config.orca_bin
                self.orca_binary = self.config.orca_bin / "orca"
            else:
                self.orca_binary = self.config.orca_bin
                self.orca_dir = self.config.orca_bin.parent
        else:
            # Auto-resolve
            from quantumvitas.core.engines.orca_resolver import resolve_orca_bin_dir
            self.orca_dir = resolve_orca_bin_dir()
            self.orca_binary = self.orca_dir / "orca"

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
            "orca_mp2",  # Future
            "orca_opt",  # Future
            "orca_freq",  # Future
        ]

    def _build_command(self, input_file: Path) -> List[str]:
        """Build ORCA command line."""
        return [str(self.orca_binary), str(input_file)]

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
        """
        from quantumvitas.engines.orca.input_compiler import ORCAInputCompiler
        from quantumvitas.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_energy,
            get_tddft_excitations,
            is_converged,
        )

        start_time = time.time()

        # Ensure working directory exists
        working_dir.mkdir(parents=True, exist_ok=True)

        # 1. Compile chain to input file
        compiler = ORCAInputCompiler()
        input_content = compiler.compile(
            chain,
            molecule,
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

        if step.public_type in ("scf", "hf", "dft"):
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

        elif step.public_type == "td":
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
            step_id=step.id,
            success=success,
            metrics=metrics,
            artifacts=artifacts,
            error=error_msg,
        )


# Factory function for engine registry
def create_orca_engine(config: Optional[ORCAEngineConfig] = None) -> ORCAEngine:
    """Create ORCA engine instance."""
    return ORCAEngine(config=config)
