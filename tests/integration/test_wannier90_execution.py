"""
Integration tests for Wannier90 workflow execution.

These tests verify the complete Wannier90 workflow:
1. Parse original .win/.scf/.nscf/.pw2wan files
2. Generate (roundtrip) them through our internal representation
3. Execute SCF → NSCF → w90_preproc → pw2wannier90 → w90_run
4. Validate output files and spread values match expected results

Test examples:
- Example05: Diamond valence bands (4 MLWFs)
- Example06: Copper Fermi surface (7 MLWFs with disentanglement)
- Example16: Silicon Boltzmann transport (8 MLWFs with disentanglement)

Reference: .qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/doc/solution_booklet/
"""

from __future__ import annotations

import os
import pytest
import shutil
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent / "data" / "wannier90_examples"
EXAMPLE05_DIR = TEST_DATA_DIR / "example05"
EXAMPLE06_DIR = TEST_DATA_DIR / "example06"
EXAMPLE16_DIR = TEST_DATA_DIR / "example16"
PSEUDO_DIR = TEST_DATA_DIR / "pseudo"


def get_qe_bin_dir() -> Optional[Path]:
    """Get QE bin directory from managed engine."""
    repo_root = Path(__file__).parent.parent.parent
    qe_bin = repo_root / ".qmatsuite" / "engines" / "qe" / "q-e-qe-7.5" / "bin"
    if qe_bin.exists():
        return qe_bin
    return None


def check_executable_exists(exe_name: str) -> bool:
    """Check if a QE executable exists."""
    qe_bin = get_qe_bin_dir()
    if qe_bin is None:
        return False
    exe_path = qe_bin / exe_name
    return exe_path.exists() and os.access(exe_path, os.X_OK)


# Skip markers
requires_qe = pytest.mark.skipif(
    not check_executable_exists("pw.x"),
    reason="QE executables not available"
)
requires_wannier90 = pytest.mark.skipif(
    not check_executable_exists("wannier90.x"),
    reason="Wannier90 executables not available"
)
requires_pw2wannier90 = pytest.mark.skipif(
    not check_executable_exists("pw2wannier90.x"),
    reason="pw2wannier90 executable not available"
)


class TestWannier90Roundtrip:
    """Test parsing and regenerating Wannier90 input files."""
    
    def test_parse_diamond_win(self):
        """Test parsing diamond.win from example05."""
        from quantumvitas.io.wannier90_input import Wannier90Input
        
        win_path = EXAMPLE05_DIR / "diamond.win"
        assert win_path.exists(), f"Test data not found: {win_path}"
        
        win = Wannier90Input.from_file(win_path)
        
        # Check parsed values
        assert win.num_wann == 4
        assert win.num_iter == 20
        assert win.mp_grid == [4, 4, 4]
        assert len(win.atoms_frac) == 2
        assert len(win.unit_cell_cart) == 3
        assert len(win.kpoints) == 64
        assert "f=0.0,0.0,0.0:s" in win.projections_block
    
    def test_parse_copper_win(self):
        """Test parsing copper.win from example06."""
        from quantumvitas.io.wannier90_input import Wannier90Input
        
        win_path = EXAMPLE06_DIR / "copper.win"
        assert win_path.exists()
        
        win = Wannier90Input.from_file(win_path)
        
        # Copper has disentanglement parameters
        assert win.num_wann == 7
        assert win.num_bands == 12
        assert "dis_win_max" in win.extra_parameters
        assert "dis_froz_max" in win.extra_parameters
        assert len(win.atoms_frac) == 1  # Single Cu atom
    
    def test_parse_silicon_win(self):
        """Test parsing Si.win from example16."""
        from quantumvitas.io.wannier90_input import Wannier90Input
        
        win_path = EXAMPLE16_DIR / "Si.win"
        assert win_path.exists()
        
        win = Wannier90Input.from_file(win_path)
        
        # Silicon with BoltzWann
        assert win.num_wann == 8
        assert win.num_bands == 12
        assert len(win.atoms_frac) == 2  # 2 Si atoms
        assert "Si : sp3" in win.projections_block or "Si:sp3" in win.projections_block.replace(" ", "")
    
    def test_roundtrip_diamond_win(self, tmp_path):
        """Test roundtrip: parse diamond.win, regenerate, compare."""
        from quantumvitas.io.wannier90_input import Wannier90Input
        
        # Parse original
        original_path = EXAMPLE05_DIR / "diamond.win"
        win = Wannier90Input.from_file(original_path)
        
        # Generate to new file
        output_path = tmp_path / "diamond.win"
        win.write(output_path)
        
        # Re-parse
        win2 = Wannier90Input.from_file(output_path)
        
        # Compare key fields
        assert win2.num_wann == win.num_wann
        assert win2.num_iter == win.num_iter
        assert win2.mp_grid == win.mp_grid
        assert len(win2.atoms_frac) == len(win.atoms_frac)
        assert len(win2.kpoints) == len(win.kpoints)
    
    def test_roundtrip_copper_win(self, tmp_path):
        """Test roundtrip for copper.win (with disentanglement)."""
        from quantumvitas.io.wannier90_input import Wannier90Input
        
        original_path = EXAMPLE06_DIR / "copper.win"
        win = Wannier90Input.from_file(original_path)
        
        output_path = tmp_path / "copper.win"
        win.write(output_path)
        
        win2 = Wannier90Input.from_file(output_path)
        
        assert win2.num_wann == win.num_wann
        assert win2.num_bands == win.num_bands
        # Disentanglement params should be preserved
        assert "dis_win_max" in win2.extra_parameters
    
    def test_parse_pw2wan(self):
        """Test parsing .pw2wan files."""
        from quantumvitas.io.wannier90_input import Pw2Wannier90Input
        
        pw2wan_path = EXAMPLE05_DIR / "diamond.pw2wan"
        pw2wan = Pw2Wannier90Input.from_file(pw2wan_path)
        
        assert pw2wan.seedname == "diamond"
        assert pw2wan.prefix == "di"
        assert pw2wan.write_mmn is True
        assert pw2wan.write_amn is True
    
    def test_roundtrip_pw2wan(self, tmp_path):
        """Test roundtrip for .pw2wan files."""
        from quantumvitas.io.wannier90_input import Pw2Wannier90Input
        
        original_path = EXAMPLE05_DIR / "diamond.pw2wan"
        pw2wan = Pw2Wannier90Input.from_file(original_path)
        
        output_path = tmp_path / "diamond.pw2wan"
        pw2wan.write(output_path)
        
        pw2wan2 = Pw2Wannier90Input.from_file(output_path)
        
        assert pw2wan2.seedname == pw2wan.seedname
        assert pw2wan2.prefix == pw2wan.prefix
        assert pw2wan2.write_mmn == pw2wan.write_mmn


class Wannier90WorkflowRunner:
    """
    Helper class to run a complete Wannier90 workflow.
    
    Steps:
    1. pw.x scf
    2. pw.x nscf
    3. wannier90.x -pp seedname
    4. pw2wannier90.x < seedname.pw2wan
    5. wannier90.x seedname
    """
    
    def __init__(self, work_dir: Path, qe_bin: Path, pseudo_dir: Path):
        self.work_dir = work_dir
        self.qe_bin = qe_bin
        self.pseudo_dir = pseudo_dir
    
    def run_command(
        self, 
        command: List[str], 
        stdin_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
        timeout: int = 300
    ) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        env = os.environ.copy()
        env["ESPRESSO_PSEUDO"] = str(self.pseudo_dir)
        env["OMP_NUM_THREADS"] = "1"
        
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
                        cwd=str(self.work_dir),
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
                    cwd=str(self.work_dir),
                    env=env,
                    timeout=timeout,
                    text=True
                )
                stdout = result.stdout
        finally:
            if stdin_handle:
                stdin_handle.close()
        
        return result.returncode, stdout, result.stderr
    
    def run_scf(self, input_file: Path) -> bool:
        """Run pw.x SCF calculation."""
        output_file = self.work_dir / f"{input_file.stem}.out"
        pw_x = self.qe_bin / "pw.x"
        
        returncode, stdout, stderr = self.run_command(
            [str(pw_x)],
            stdin_file=input_file,
            output_file=output_file,
        )
        
        # Check for JOB DONE
        if output_file.exists():
            content = output_file.read_text()
            if "JOB DONE" in content:
                return True
        
        print(f"SCF failed. stderr: {stderr}")
        return False
    
    def run_nscf(self, input_file: Path) -> bool:
        """Run pw.x NSCF calculation."""
        output_file = self.work_dir / f"{input_file.stem}.out"
        pw_x = self.qe_bin / "pw.x"
        
        returncode, stdout, stderr = self.run_command(
            [str(pw_x)],
            stdin_file=input_file,
            output_file=output_file,
        )
        
        if output_file.exists():
            content = output_file.read_text()
            if "JOB DONE" in content:
                return True
        
        print(f"NSCF failed. stderr: {stderr}")
        return False
    
    def run_w90_preproc(self, seedname: str) -> bool:
        """Run wannier90.x -pp seedname."""
        wannier90_x = self.qe_bin / "wannier90.x"
        
        returncode, stdout, stderr = self.run_command(
            [str(wannier90_x), "-pp", seedname],
        )
        
        # Check for .nnkp file
        nnkp_file = self.work_dir / f"{seedname}.nnkp"
        if nnkp_file.exists():
            return True
        
        print(f"w90_preproc failed. returncode={returncode}, stderr: {stderr}")
        return False
    
    def run_pw2wannier90(self, input_file: Path) -> bool:
        """Run pw2wannier90.x."""
        output_file = self.work_dir / f"{input_file.stem}.out"
        pw2wannier90_x = self.qe_bin / "pw2wannier90.x"
        
        returncode, stdout, stderr = self.run_command(
            [str(pw2wannier90_x)],
            stdin_file=input_file,
            output_file=output_file,
        )
        
        # Check for success (look for output files)
        seedname = input_file.stem.replace(".pw2wan", "")
        # Get seedname from pw2wan file
        from quantumvitas.io.wannier90_input import Pw2Wannier90Input
        pw2wan = Pw2Wannier90Input.from_file(input_file)
        seedname = pw2wan.seedname
        
        mmn_file = self.work_dir / f"{seedname}.mmn"
        amn_file = self.work_dir / f"{seedname}.amn"
        
        if mmn_file.exists() and amn_file.exists():
            return True
        
        print(f"pw2wannier90 failed. returncode={returncode}, stderr: {stderr}")
        return False
    
    def run_w90(self, seedname: str) -> bool:
        """Run wannier90.x seedname (main optimization)."""
        wannier90_x = self.qe_bin / "wannier90.x"
        
        returncode, stdout, stderr = self.run_command(
            [str(wannier90_x), seedname],
        )
        
        # Check for .wout file with Final State
        wout_file = self.work_dir / f"{seedname}.wout"
        if wout_file.exists():
            content = wout_file.read_text()
            if "Final State" in content:
                return True
        
        print(f"w90 failed. returncode={returncode}, stderr: {stderr}")
        return False
    
    def extract_final_spread(self, seedname: str) -> Optional[float]:
        """Extract Final Spread from .wout file."""
        wout_file = self.work_dir / f"{seedname}.wout"
        if not wout_file.exists():
            return None
        
        content = wout_file.read_text()
        # Look for "Final Spread (Ang^2)       Omega Total  =     X.XXXXX"
        match = re.search(r"Final Spread.*Omega Total\s*=\s*([\d.]+)", content)
        if match:
            return float(match.group(1))
        return None
    
    def extract_wf_centers(self, seedname: str) -> List[Tuple[float, float, float, float]]:
        """Extract WF centers and spreads from Final State in .wout file."""
        wout_file = self.work_dir / f"{seedname}.wout"
        if not wout_file.exists():
            return []
        
        content = wout_file.read_text()
        centers = []
        
        # Find the Final State section
        final_state_match = re.search(r"Final State(.*?)(?:Sum of centres|Spreads)", content, re.DOTALL)
        if not final_state_match:
            return []
        
        final_state_section = final_state_match.group(1)
        
        # Look for "WF centre and spread    N  ( X, Y, Z )     spread"
        pattern = r"WF centre and spread\s+\d+\s+\(\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\s*\)\s+([\d.]+)"
        for match in re.finditer(pattern, final_state_section):
            x, y, z, spread = float(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))
            centers.append((x, y, z, spread))
        
        return centers


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestWannier90Example05:
    """
    Integration test for Example05: Diamond valence bands.
    
    Expected results (from solution booklet):
    - 4 MLWFs with sp³ character
    - Final Spread ≈ 2.32 Ang²
    - Each WF spread ≈ 0.58 Ang²
    """
    
    @pytest.fixture
    def work_dir(self, tmp_path):
        """Create working directory with all input files."""
        work_dir = tmp_path / "example05"
        work_dir.mkdir()
        
        # Copy input files
        for f in ["diamond.scf", "diamond.nscf", "diamond.pw2wan", "diamond.win"]:
            shutil.copy(EXAMPLE05_DIR / f, work_dir / f)
        
        # Fix pseudo_dir in input files to use absolute path
        for f in ["diamond.scf", "diamond.nscf"]:
            content = (work_dir / f).read_text()
            content = content.replace("../../pseudo/", str(PSEUDO_DIR) + "/")
            (work_dir / f).write_text(content)
        
        return work_dir
    
    def test_full_workflow(self, work_dir):
        """Run the complete diamond Wannier90 workflow."""
        qe_bin = get_qe_bin_dir()
        runner = Wannier90WorkflowRunner(work_dir, qe_bin, PSEUDO_DIR)
        
        # Step 1: SCF
        assert runner.run_scf(work_dir / "diamond.scf"), "SCF failed"
        
        # Step 2: NSCF
        assert runner.run_nscf(work_dir / "diamond.nscf"), "NSCF failed"
        
        # Step 3: w90 preprocessing
        assert runner.run_w90_preproc("diamond"), "w90_preproc failed"
        
        # Check .nnkp was created
        assert (work_dir / "diamond.nnkp").exists(), ".nnkp not created"
        
        # Step 4: pw2wannier90
        assert runner.run_pw2wannier90(work_dir / "diamond.pw2wan"), "pw2wannier90 failed"
        
        # Check output files
        assert (work_dir / "diamond.mmn").exists(), ".mmn not created"
        assert (work_dir / "diamond.amn").exists(), ".amn not created"
        
        # Step 5: wannier90 main
        assert runner.run_w90("diamond"), "w90_run failed"
        
        # Check .wout
        assert (work_dir / "diamond.wout").exists(), ".wout not created"
        
        # Validate results
        final_spread = runner.extract_final_spread("diamond")
        assert final_spread is not None, "Could not extract final spread"
        
        # Expected: ~2.32 Ang² (allow 10% tolerance)
        assert 2.0 < final_spread < 2.6, f"Unexpected final spread: {final_spread}"
        
        # Check WF centers
        centers = runner.extract_wf_centers("diamond")
        assert len(centers) == 4, f"Expected 4 WFs, got {len(centers)}"
        
        # Each WF should have spread ~0.58 Ang²
        for i, (x, y, z, spread) in enumerate(centers):
            assert 0.4 < spread < 0.8, f"WF {i+1} spread {spread} out of expected range"


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestWannier90Example06:
    """
    Integration test for Example06: Copper Fermi surface.
    
    Expected results:
    - 7 MLWFs (5d + 2s)
    - Disentanglement required
    - Fermi energy ~12.93 eV
    """
    
    @pytest.fixture
    def work_dir(self, tmp_path):
        """Create working directory with all input files."""
        work_dir = tmp_path / "example06"
        work_dir.mkdir()
        
        # Copy input files
        for f in ["copper.scf", "copper.nscf", "copper.pw2wan", "copper.win"]:
            shutil.copy(EXAMPLE06_DIR / f, work_dir / f)
        
        # Fix pseudo_dir in input files
        for f in ["copper.scf", "copper.nscf"]:
            content = (work_dir / f).read_text()
            content = content.replace("../../pseudo/", str(PSEUDO_DIR) + "/")
            (work_dir / f).write_text(content)
        
        return work_dir
    
    def test_full_workflow(self, work_dir):
        """Run the complete copper Wannier90 workflow."""
        qe_bin = get_qe_bin_dir()
        runner = Wannier90WorkflowRunner(work_dir, qe_bin, PSEUDO_DIR)
        
        # Step 1: SCF
        assert runner.run_scf(work_dir / "copper.scf"), "SCF failed"
        
        # Step 2: NSCF
        assert runner.run_nscf(work_dir / "copper.nscf"), "NSCF failed"
        
        # Step 3: w90 preprocessing
        assert runner.run_w90_preproc("copper"), "w90_preproc failed"
        assert (work_dir / "copper.nnkp").exists()
        
        # Step 4: pw2wannier90
        assert runner.run_pw2wannier90(work_dir / "copper.pw2wan"), "pw2wannier90 failed"
        assert (work_dir / "copper.mmn").exists()
        assert (work_dir / "copper.amn").exists()
        
        # Step 5: wannier90 main
        assert runner.run_w90("copper"), "w90_run failed"
        assert (work_dir / "copper.wout").exists()
        
        # Validate: Check disentanglement converged
        wout_content = (work_dir / "copper.wout").read_text()
        assert "Final State" in wout_content
        
        # Check we got 7 WFs
        centers = runner.extract_wf_centers("copper")
        assert len(centers) == 7, f"Expected 7 WFs, got {len(centers)}"


@requires_qe
@requires_wannier90
@requires_pw2wannier90
class TestWannier90Example16:
    """
    Integration test for Example16: Silicon Boltzmann transport.
    
    Expected results:
    - 8 MLWFs (sp³ for each Si atom)
    - Disentanglement required
    """
    
    @pytest.fixture
    def work_dir(self, tmp_path):
        """Create working directory with all input files."""
        work_dir = tmp_path / "example16"
        work_dir.mkdir()
        
        # Copy input files
        for f in ["Si.scf", "Si.nscf", "Si.pw2wan", "Si.win"]:
            shutil.copy(EXAMPLE16_DIR / f, work_dir / f)
        
        # Fix pseudo_dir in input files
        for f in ["Si.scf", "Si.nscf"]:
            content = (work_dir / f).read_text()
            content = content.replace("../../pseudo/", str(PSEUDO_DIR) + "/")
            (work_dir / f).write_text(content)
        
        return work_dir
    
    def test_full_workflow(self, work_dir):
        """Run the complete silicon Wannier90 workflow."""
        qe_bin = get_qe_bin_dir()
        runner = Wannier90WorkflowRunner(work_dir, qe_bin, PSEUDO_DIR)
        
        # Step 1: SCF
        assert runner.run_scf(work_dir / "Si.scf"), "SCF failed"
        
        # Step 2: NSCF
        assert runner.run_nscf(work_dir / "Si.nscf"), "NSCF failed"
        
        # Step 3: w90 preprocessing
        assert runner.run_w90_preproc("Si"), "w90_preproc failed"
        assert (work_dir / "Si.nnkp").exists()
        
        # Step 4: pw2wannier90
        assert runner.run_pw2wannier90(work_dir / "Si.pw2wan"), "pw2wannier90 failed"
        assert (work_dir / "Si.mmn").exists()
        assert (work_dir / "Si.amn").exists()
        
        # Step 5: wannier90 main
        assert runner.run_w90("Si"), "w90_run failed"
        assert (work_dir / "Si.wout").exists()
        
        # Validate: Check optimization converged
        wout_content = (work_dir / "Si.wout").read_text()
        assert "Final State" in wout_content
        
        # Check we got 8 WFs
        centers = runner.extract_wf_centers("Si")
        assert len(centers) == 8, f"Expected 8 WFs, got {len(centers)}"


class TestQEInputRoundtrip:
    """Test QE input file parsing and regeneration."""
    
    def test_parse_scf_input(self):
        """Test parsing SCF input files."""
        from quantumvitas.io import QEInputParser
        
        scf_path = EXAMPLE05_DIR / "diamond.scf"
        qe_input = QEInputParser.parse_file(scf_path)
        
        # Check namelists
        control = qe_input.get_namelist("control")
        assert control is not None
        assert control.parameters.get("calculation") == "scf"
        
        system = qe_input.get_namelist("system")
        assert system is not None
        assert system.parameters.get("ecutwfc") == 40.0
    
    def test_parse_nscf_input(self):
        """Test parsing NSCF input files with explicit k-points."""
        from quantumvitas.io import QEInputParser
        from quantumvitas.io.model import QECardType
        
        nscf_path = EXAMPLE05_DIR / "diamond.nscf"
        qe_input = QEInputParser.parse_file(nscf_path)
        
        # Check calculation type
        control = qe_input.get_namelist("control")
        assert control.parameters.get("calculation") == "nscf"
        
        # Check k-points card
        kpoints_card = qe_input.get_card(QECardType.K_POINTS)
        assert kpoints_card is not None
        # Data includes count line [64] plus 64 k-points = 65 entries
        assert len(kpoints_card.data) == 65  # count line + 4x4x4 grid


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

