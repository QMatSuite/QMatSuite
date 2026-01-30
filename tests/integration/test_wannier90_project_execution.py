"""
Integration tests for Wannier90 workflow execution via proper project framework.

These tests:
1. Create real QMatSuite projects in .tmp/runs/
2. Copy original example input files to project/calculations/.../raw/
3. Copy pseudos to project/pseudo/
4. Run the complete Wannier90 workflow through subprocess (like the engine does)
5. Validate output values match expected results from solution booklet
6. Do NOT delete test directories - user can inspect results

Test examples:
- Example05 Diamond: 4 MLWFs, Final Spread ≈ 2.32 Ang²
- Example06 Copper: 7 MLWFs with disentanglement  
- Example16 Silicon: 8 MLWFs with disentanglement

Expected values from: .qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/doc/solution_booklet/
"""

from __future__ import annotations

import os
import pytest
import shutil
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import yaml

from quantumvitas.core.paths import get_repo_root, tmp_runs_dir


# Get repo root and paths
REPO_ROOT = get_repo_root()
QE_BIN_DIR = REPO_ROOT / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "bin"
EXAMPLE_ROOT = REPO_ROOT / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "external" / "wannier90" / "examples"
PSEUDO_SOURCE = REPO_ROOT / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "external" / "wannier90" / "pseudo"


def check_executable_exists(exe_name: str) -> bool:
    """Check if a QE executable exists in managed engine."""
    exe_path = QE_BIN_DIR / exe_name
    return exe_path.exists() and os.access(exe_path, os.X_OK)


# Skip markers for CI without engines
requires_qe = pytest.mark.skipif(
    not check_executable_exists("pw.x"),
    reason="QE executables not available in .qmatsuite/engines/qe/..."
)
requires_wannier90 = pytest.mark.skipif(
    not check_executable_exists("wannier90.x"),
    reason="Wannier90 executables not available in .qmatsuite/engines/qe/..."
)
requires_pw2wannier90 = pytest.mark.skipif(
    not check_executable_exists("pw2wannier90.x"),
    reason="pw2wannier90 executable not available in .qmatsuite/engines/qe/..."
)


class Wannier90ProjectTest:
    """
    Create and run Wannier90 workflow in proper project structure.
    
    Directory structure:
        .tmp/runs/wannier90_{name}/
            project.yaml
            pseudo/
                {element}.UPF
            structures/
                {name}.yaml
            calculations/
                {name}_w90/
                    calculation.yaml
                    raw/
                        {seed}.scf
                        {seed}.nscf
                        {seed}.win
                        {seed}.pw2wan
                        {seed}.scf.out  (generated)
                        {seed}.nscf.out (generated)
                        {seed}.wout     (generated)
                        ...
    """
    
    def __init__(self, name: str, example_dir: str, seedname: str, prefix: str, pseudo_name: str, element: str):
        self.name = name
        self.example_dir = EXAMPLE_ROOT / example_dir
        self.seedname = seedname
        self.prefix = prefix
        self.pseudo_name = pseudo_name
        self.element = element
        
        # Create project in .tmp/runs/
        self.project_root = tmp_runs_dir() / f"wannier90_{name}"
        self.pseudo_dir = self.project_root / "pseudo"
        self.calc_dir = self.project_root / "calculations" / f"{name}_w90"
        self.raw_dir = self.calc_dir / "raw"
        
        # QE executables - MUST use managed engine paths
        self.pw_x = QE_BIN_DIR / "pw.x"
        self.wannier90_x = QE_BIN_DIR / "wannier90.x"
        self.pw2wannier90_x = QE_BIN_DIR / "pw2wannier90.x"
    
    def setup_project(self) -> Path:
        """Create project structure and copy input files."""
        # Clean up previous run at START (not at end - so user can inspect results)
        if self.project_root.exists():
            shutil.rmtree(self.project_root)
        
        # Create directories
        self.project_root.mkdir(parents=True)
        self.pseudo_dir.mkdir()
        self.raw_dir.mkdir(parents=True)
        
        # Copy pseudo from wannier90 distribution (NOT from PATH lookup)
        pseudo_src = PSEUDO_SOURCE / self.pseudo_name
        pseudo_dst = self.pseudo_dir / self.pseudo_name
        if pseudo_src.exists():
            shutil.copy(pseudo_src, pseudo_dst)
        else:
            raise FileNotFoundError(f"Pseudo not found: {pseudo_src}")
        
        # Copy example input files and modify paths
        for f in [f"{self.seedname}.scf", f"{self.seedname}.nscf", f"{self.seedname}.pw2wan", f"{self.seedname}.win"]:
            src = self.example_dir / f
            if not src.exists():
                raise FileNotFoundError(f"Example file not found: {src}")
            
            content = src.read_text()
            # Fix paths for project structure
            content = content.replace("../../pseudo/", str(self.pseudo_dir) + "/")
            content = content.replace("outdir='./'", f"outdir='{self.raw_dir}/'")
            content = content.replace("outdir = './'", f"outdir = '{self.raw_dir}/'")
            
            dst = self.raw_dir / f
            dst.write_text(content)
        
        # Create minimal project.yaml
        project_yaml = self.project_root / "project.yaml"
        project_yaml.write_text(f"""
name: {self.name}_wannier90
created: "2026-01-02"
""")
        
        # Create minimal calculation.yaml
        calc_yaml = self.calc_dir / "calculation.yaml"
        calc_yaml.write_text(f"""
meta:
  name: {self.name}_w90
structure_ulid: {self.name}
working_dir: raw
species_map:
  {self.element}:
    mass: 28.0
    pseudopot: {self.pseudo_name}
steps: []
""")
        
        return self.project_root
    
    def run_command(
        self,
        command: List[str],
        stdin_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
        timeout: int = 300,
    ) -> Tuple[int, str, str]:
        """
        Run a command using subprocess.
        
        Critically:
        - Uses full path to executable from managed engine (NO PATH lookup)
        - Sets ESPRESSO_PSEUDO to project/pseudo/
        - Sets working directory to raw/
        """
        env = os.environ.copy()
        env["ESPRESSO_PSEUDO"] = str(self.pseudo_dir)
        env["OMP_NUM_THREADS"] = "1"
        # Remove any existing QE paths from PATH to ensure we use managed engine
        env["PATH"] = os.pathsep.join([
            p for p in env.get("PATH", "").split(os.pathsep)
            if "espresso" not in p.lower() and "qe" not in p.lower()
        ])
        
        stdin_handle = None
        if stdin_file:
            stdin_handle = open(stdin_file, 'r')
        
        try:
            if output_file:
                with open(output_file, 'w') as out_f:
                    result = subprocess.run(
                        command,
                        stdin=stdin_handle,
                        stdout=out_f,
                        stderr=subprocess.PIPE,
                        cwd=str(self.raw_dir),
                        env=env,
                        timeout=timeout,
                        text=True
                    )
                stdout = output_file.read_text() if output_file.exists() else ""
            else:
                result = subprocess.run(
                    command,
                    stdin=stdin_handle,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(self.raw_dir),
                    env=env,
                    timeout=timeout,
                    text=True
                )
                stdout = result.stdout
        finally:
            if stdin_handle:
                stdin_handle.close()
        
        return result.returncode, stdout, result.stderr
    
    def run_scf(self) -> bool:
        """Run pw.x SCF calculation using managed engine executable."""
        input_file = self.raw_dir / f"{self.seedname}.scf"
        output_file = self.raw_dir / f"{self.seedname}.scf.out"
        
        # Use full path to pw.x from managed engine - NOT from PATH
        command = [str(self.pw_x)]
        
        returncode, stdout, stderr = self.run_command(
            command,
            stdin_file=input_file,
            output_file=output_file,
        )
        
        if output_file.exists() and "JOB DONE" in output_file.read_text():
            return True
        
        print(f"SCF failed. stderr: {stderr[:500]}")
        return False
    
    def run_nscf(self) -> bool:
        """Run pw.x NSCF calculation."""
        input_file = self.raw_dir / f"{self.seedname}.nscf"
        output_file = self.raw_dir / f"{self.seedname}.nscf.out"
        
        command = [str(self.pw_x)]
        
        returncode, stdout, stderr = self.run_command(
            command,
            stdin_file=input_file,
            output_file=output_file,
        )
        
        if output_file.exists() and "JOB DONE" in output_file.read_text():
            return True
        
        print(f"NSCF failed. stderr: {stderr[:500]}")
        return False
    
    def run_w90_preproc(self) -> bool:
        """Run wannier90.x -pp (preprocessing) - no stdin, uses seedname arg."""
        # wannier90.x -pp seedname (reads seedname.win, writes seedname.nnkp)
        command = [str(self.wannier90_x), "-pp", self.seedname]
        
        returncode, stdout, stderr = self.run_command(command)
        
        nnkp_file = self.raw_dir / f"{self.seedname}.nnkp"
        if nnkp_file.exists():
            return True
        
        print(f"w90_preproc failed. returncode={returncode}, stderr: {stderr[:500]}")
        return False
    
    def run_pw2wannier90(self) -> bool:
        """Run pw2wannier90.x with stdin from .pw2wan file."""
        input_file = self.raw_dir / f"{self.seedname}.pw2wan"
        output_file = self.raw_dir / f"{self.seedname}.pw2wan.out"
        
        # pw2wannier90.x reads from stdin (like pw.x)
        command = [str(self.pw2wannier90_x)]
        
        returncode, stdout, stderr = self.run_command(
            command,
            stdin_file=input_file,
            output_file=output_file,
        )
        
        mmn_file = self.raw_dir / f"{self.seedname}.mmn"
        amn_file = self.raw_dir / f"{self.seedname}.amn"
        
        if mmn_file.exists() and amn_file.exists():
            return True
        
        print(f"pw2wannier90 failed. returncode={returncode}, stderr: {stderr[:500]}")
        return False
    
    def run_w90(self) -> bool:
        """Run wannier90.x main (no -pp) - reads .win/.mmn/.amn, writes .wout."""
        # wannier90.x seedname (reads from seedname.win, seedname.mmn, seedname.amn)
        command = [str(self.wannier90_x), self.seedname]
        
        returncode, stdout, stderr = self.run_command(command)
        
        wout_file = self.raw_dir / f"{self.seedname}.wout"
        if wout_file.exists() and "Final State" in wout_file.read_text():
            return True
        
        print(f"w90_run failed. returncode={returncode}, stderr: {stderr[:500]}")
        return False
    
    def run_full_workflow(self) -> bool:
        """Run complete SCF → NSCF → w90_preproc → pw2wannier90 → w90_run workflow."""
        steps = [
            ("SCF", self.run_scf),
            ("NSCF", self.run_nscf),
            ("w90_preproc", self.run_w90_preproc),
            ("pw2wannier90", self.run_pw2wannier90),
            ("w90_run", self.run_w90),
        ]
        
        for name, fn in steps:
            print(f"  Running {name}...")
            if not fn():
                print(f"  ✗ {name} FAILED")
                return False
            print(f"  ✓ {name} done")
        
        return True
    
    def extract_results(self) -> Dict[str, Any]:
        """Extract results from .wout file."""
        wout_file = self.raw_dir / f"{self.seedname}.wout"
        if not wout_file.exists():
            return {}
        
        content = wout_file.read_text()
        results = {}
        
        # Extract Final Spread
        match = re.search(r"Final Spread.*Omega Total\s*=\s*([\d.]+)", content)
        if match:
            results["final_spread"] = float(match.group(1))
        
        # Extract WF centers from Final State section only
        final_state_match = re.search(r"Final State(.*?)(?:Sum of centres|Spreads)", content, re.DOTALL)
        if final_state_match:
            centers = []
            pattern = r"WF centre and spread\s+\d+\s+\(\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\s*\)\s+([\d.]+)"
            for m in re.finditer(pattern, final_state_match.group(1)):
                centers.append({
                    "x": float(m.group(1)),
                    "y": float(m.group(2)),
                    "z": float(m.group(3)),
                    "spread": float(m.group(4)),
                })
            results["wf_centers"] = centers
            results["num_wann"] = len(centers)
        
        return results


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestDiamondWannier90:
    """
    Test Example05: Diamond valence bands.
    
    Expected results (from solution_booklet/Example5.tex):
    - 4 MLWFs (σ-bonding sp³ orbitals)
    - Final Spread: 2.32 Ang² (Omega Total)
    - Each WF spread: ~0.58 Ang²
    """
    
    EXPECTED_NUM_WANN = 4
    EXPECTED_SPREAD_MIN = 2.0
    EXPECTED_SPREAD_MAX = 2.6
    EXPECTED_WF_SPREAD_MIN = 0.4
    EXPECTED_WF_SPREAD_MAX = 0.8
    
    @pytest.fixture
    def project(self):
        """Set up Diamond project."""
        p = Wannier90ProjectTest(
            name="diamond",
            example_dir="example05",
            seedname="diamond",
            prefix="di",
            pseudo_name="C.pz-vbc.UPF",
            element="C",
        )
        p.setup_project()
        return p
    
    def test_executables_from_managed_engine(self, project):
        """Verify executables come from managed engine, not PATH."""
        # This is critical - we must NOT use PATH fallback
        assert project.pw_x.exists(), f"pw.x not found at {project.pw_x}"
        assert project.wannier90_x.exists(), f"wannier90.x not found at {project.wannier90_x}"
        assert project.pw2wannier90_x.exists(), f"pw2wannier90.x not found at {project.pw2wannier90_x}"
        
        # Verify they are in the managed engine directory
        assert ".qmatsuite/engines/qe" in str(project.pw_x)
        assert ".qmatsuite/engines/qe" in str(project.wannier90_x)
        assert ".qmatsuite/engines/qe" in str(project.pw2wannier90_x)
    
    def test_project_structure(self, project):
        """Verify project structure is correct."""
        assert project.project_root.exists()
        assert project.pseudo_dir.exists()
        assert project.raw_dir.exists()
        assert (project.pseudo_dir / "C.pz-vbc.UPF").exists()
        assert (project.raw_dir / "diamond.scf").exists()
        assert (project.raw_dir / "diamond.nscf").exists()
        assert (project.raw_dir / "diamond.win").exists()
        assert (project.raw_dir / "diamond.pw2wan").exists()
    
    def test_full_workflow_and_results(self, project):
        """Run full workflow and validate results against expected values."""
        print(f"\nProject: {project.project_root}")
        
        # Run workflow
        success = project.run_full_workflow()
        assert success, "Workflow failed"
        
        # Verify all output files exist in raw/
        assert (project.raw_dir / "diamond.scf.out").exists()
        assert (project.raw_dir / "diamond.nscf.out").exists()
        assert (project.raw_dir / "diamond.nnkp").exists()
        assert (project.raw_dir / "diamond.mmn").exists()
        assert (project.raw_dir / "diamond.amn").exists()
        assert (project.raw_dir / "diamond.wout").exists()
        
        # Extract and validate results
        results = project.extract_results()
        
        # Validate number of Wannier functions
        assert results.get("num_wann") == self.EXPECTED_NUM_WANN, \
            f"Expected {self.EXPECTED_NUM_WANN} WFs, got {results.get('num_wann')}"
        
        # Validate total spread (expected ~2.32, allow tolerance)
        spread = results.get("final_spread", 0)
        assert self.EXPECTED_SPREAD_MIN < spread < self.EXPECTED_SPREAD_MAX, \
            f"Final spread {spread} not in expected range [{self.EXPECTED_SPREAD_MIN}, {self.EXPECTED_SPREAD_MAX}]"
        
        # Validate individual WF spreads
        for i, wf in enumerate(results.get("wf_centers", [])):
            assert self.EXPECTED_WF_SPREAD_MIN < wf["spread"] < self.EXPECTED_WF_SPREAD_MAX, \
                f"WF {i+1} spread {wf['spread']} not in expected range"
        
        print(f"\n✓ Diamond test PASSED")
        print(f"  Final Spread: {spread:.4f} Ang²")
        print(f"  Num Wannier Functions: {results.get('num_wann')}")


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestCopperWannier90:
    """
    Test Example06: Copper Fermi surface.
    
    Expected results (from solution_booklet/Example6.tex):
    - 7 MLWFs (5d + 2s)
    - Disentanglement with dis_win_max, dis_froz_max
    - Fermi energy ~12.93 eV
    """
    
    EXPECTED_NUM_WANN = 7
    
    @pytest.fixture
    def project(self):
        """Set up Copper project."""
        p = Wannier90ProjectTest(
            name="copper",
            example_dir="example06",
            seedname="copper",
            prefix="cu",
            pseudo_name="Cu.pz-n-van_ak.UPF",
            element="Cu",
        )
        p.setup_project()
        return p
    
    def test_full_workflow_and_results(self, project):
        """Run full workflow and validate results."""
        print(f"\nProject: {project.project_root}")
        
        success = project.run_full_workflow()
        assert success, "Workflow failed"
        
        results = project.extract_results()
        
        # Validate number of Wannier functions (7 = 5d + 2s)
        assert results.get("num_wann") == self.EXPECTED_NUM_WANN, \
            f"Expected {self.EXPECTED_NUM_WANN} WFs, got {results.get('num_wann')}"
        
        print(f"\n✓ Copper test PASSED")
        print(f"  Num Wannier Functions: {results.get('num_wann')}")


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestSiliconWannier90:
    """
    Test Example16: Silicon Boltzmann transport.
    
    Expected results (from solution_booklet/Example16.tex):
    - 8 MLWFs (sp³ × 2 Si atoms)
    - Disentanglement with dis_win_max, dis_froz_max
    """
    
    EXPECTED_NUM_WANN = 8
    
    @pytest.fixture
    def project(self):
        """Set up Silicon project."""
        p = Wannier90ProjectTest(
            name="silicon",
            example_dir="example16-withqe",
            seedname="Si",
            prefix="si",
            pseudo_name="Si.pbe-n-van.UPF",
            element="Si",
        )
        p.setup_project()
        return p
    
    def test_full_workflow_and_results(self, project):
        """Run full workflow and validate results."""
        print(f"\nProject: {project.project_root}")
        
        success = project.run_full_workflow()
        assert success, "Workflow failed"
        
        results = project.extract_results()
        
        # Validate number of Wannier functions (8 = sp³ × 2 atoms)
        assert results.get("num_wann") == self.EXPECTED_NUM_WANN, \
            f"Expected {self.EXPECTED_NUM_WANN} WFs, got {results.get('num_wann')}"
        
        print(f"\n✓ Silicon test PASSED")
        print(f"  Num Wannier Functions: {results.get('num_wann')}")


class TestProjectFilesAfterRun:
    """Test that project files are properly organized after a run."""
    
    @requires_qe
    @requires_wannier90
    @requires_pw2wannier90
    def test_diamond_files_in_raw(self):
        """Verify all input/output files are in raw/ directory."""
        p = Wannier90ProjectTest(
            name="diamond_structure",
            example_dir="example05",
            seedname="diamond",
            prefix="di",
            pseudo_name="C.pz-vbc.UPF",
            element="C",
        )
        p.setup_project()
        
        success = p.run_full_workflow()
        assert success
        
        # All input files should be in raw/
        input_files = ["diamond.scf", "diamond.nscf", "diamond.win", "diamond.pw2wan"]
        for f in input_files:
            assert (p.raw_dir / f).exists(), f"Input file {f} not in raw/"
        
        # All output files should be in raw/
        output_files = [
            "diamond.scf.out",
            "diamond.nscf.out",
            "diamond.nnkp",
            "diamond.mmn",
            "diamond.amn",
            "diamond.eig",
            "diamond.wout",
            "diamond.chk",
        ]
        for f in output_files:
            path = p.raw_dir / f
            assert path.exists(), f"Output file {f} not in raw/"
        
        # Pseudo should be in project/pseudo/
        assert (p.pseudo_dir / "C.pz-vbc.UPF").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
