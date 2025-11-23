"""
Integration test for 4_Si_DOS workflow from CI test data.

This test validates the SCF -> NSCF -> DOS workflow using files
from tests/integration/ci_test_data/4_Si_DOS/ and actually runs QE calculations.
"""

import pytest
from pathlib import Path
import sys
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "extended-tests" / "utils"))

from quantumvitas.core.engines.qe_input import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType
)
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from test_qe_roundtrip_execution import test_input_roundtrip_execution, set_outdir_to_temp
from tests.core.thresholds import get_fermi_energy_tolerance
import re


class TestSiDOSWorkflow:
    """Test SCF -> NSCF -> DOS workflow using 4_Si_DOS examples."""
    
    @pytest.fixture
    def si_dos_dir(self):
        """Get path to 4_Si_DOS test data directory."""
        project_root = Path(__file__).parent.parent.parent
        ci_test_data_dir = project_root / "tests" / "integration" / "ci_test_data" / "4_Si_DOS"
        if not ci_test_data_dir.exists():
            pytest.skip(f"CI test data not found: {ci_test_data_dir}")
        return ci_test_data_dir
    
    @pytest.fixture
    def qe_engine(self):
        """Create QE engine instance."""
        config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(config)
        if not engine.detect_executable("pw.x"):
            pytest.skip("pw.x not found. QE installation required.")
        if not engine.detect_executable("dos.x"):
            pytest.skip("dos.x not found. QE installation required.")
        return engine
    
    def test_parse_scf_input(self, si_dos_dir):
        """Test parsing SCF input file."""
        scf_file = si_dos_dir / "si.1_scf.in"
        assert scf_file.exists(), f"SCF file not found: {scf_file}"
        
        scf_input = QEInputParser.parse_file(scf_file)
        assert scf_input is not None
        
        # Verify control namelist
        control = scf_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'scf'
        assert control.get('prefix') == 'si'
        assert control.get('restart_mode') == 'from_scratch'
        
        # Verify system namelist
        system = scf_input.get_namelist('system')
        assert system is not None
        assert system.get('ibrav') == 2
        assert system.get('nat') == 2
        assert system.get('ntyp') == 1
        assert system.get('ecutwfc') == 50
        
        # Verify atomic species card
        atomic_species = scf_input.get_card(QECardType.ATOMIC_SPECIES)
        assert atomic_species is not None
        assert len(atomic_species.data) >= 1
        assert atomic_species.data[0][0] == 'Si'
        
        # Verify atomic positions card
        atomic_pos = scf_input.get_card(QECardType.ATOMIC_POSITIONS)
        assert atomic_pos is not None
        assert len(atomic_pos.data) == 2  # 2 Si atoms
        
        # Verify k-points card
        k_points = scf_input.get_card(QECardType.K_POINTS)
        assert k_points is not None
    
    def test_parse_nscf_input(self, si_dos_dir):
        """Test parsing NSCF input file."""
        nscf_file = si_dos_dir / "si.2_nscf.in"
        assert nscf_file.exists(), f"NSCF file not found: {nscf_file}"
        
        nscf_input = QEInputParser.parse_file(nscf_file)
        assert nscf_input is not None
        
        # Verify control namelist
        control = nscf_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'nscf'
        assert control.get('prefix') == 'si'  # Same prefix as SCF
        
        # Verify system namelist
        system = nscf_input.get_namelist('system')
        assert system is not None
        assert system.get('occupations') == 'tetrahedra'  # NSCF-specific
        
        # Verify k-points (should be denser than SCF)
        k_points = nscf_input.get_card(QECardType.K_POINTS)
        assert k_points is not None
        # NSCF typically uses denser k-point grid
        k_values = k_points.data[0]
        assert int(k_values[0]) >= 8  # At least as dense as SCF
    
    def test_parse_dos_input(self, si_dos_dir):
        """Test parsing DOS input file."""
        dos_file = si_dos_dir / "si.3_dos.in"
        assert dos_file.exists(), f"DOS file not found: {dos_file}"
        
        dos_input = QEInputParser.parse_file(dos_file)
        assert dos_input is not None
        
        # DOS uses &DOS namelist, not &control
        dos_namelist = dos_input.get_namelist('dos')
        assert dos_namelist is not None, "DOS input should have &DOS namelist"
        
        # Verify DOS parameters
        assert dos_namelist.get('prefix') == 'si'  # Same prefix as SCF/NSCF
        assert dos_namelist.get('fildos') == 'si.dos.dat'
        assert dos_namelist.get('emin') == -9.0
        assert dos_namelist.get('emax') == 16.0
        
        # DOS input should not have control namelist
        control = dos_input.get_namelist('control')
        assert control is None, "DOS input should not have &control namelist"
    
    def test_workflow_prefix_consistency(self, si_dos_dir):
        """Test that all workflow steps use the same prefix."""
        # Parse all three files
        scf_file = si_dos_dir / "si.1_scf.in"
        nscf_file = si_dos_dir / "si.2_nscf.in"
        dos_file = si_dos_dir / "si.3_dos.in"
        
        scf_input = QEInputParser.parse_file(scf_file)
        nscf_input = QEInputParser.parse_file(nscf_file)
        dos_input = QEInputParser.parse_file(dos_file)
        
        # Extract prefixes
        scf_prefix = scf_input.get_namelist('control').get('prefix')
        nscf_prefix = nscf_input.get_namelist('control').get('prefix')
        dos_prefix = dos_input.get_namelist('dos').get('prefix')
        
        # All should use the same prefix
        assert scf_prefix == nscf_prefix == dos_prefix == 'si', \
            f"All workflow steps should use same prefix. Got: SCF={scf_prefix}, NSCF={nscf_prefix}, DOS={dos_prefix}"
    
    def test_roundtrip_generation(self, si_dos_dir, tmp_path):
        """Test roundtrip: parse -> generate -> re-parse."""
        # Test SCF
        scf_file = si_dos_dir / "si.1_scf.in"
        scf_input = QEInputParser.parse_file(scf_file)
        
        generated_scf = tmp_path / "si.1_scf_generated.in"
        QEInputGenerator.write_file(scf_input, generated_scf)
        assert generated_scf.exists()
        
        # Re-parse generated file
        scf_reparsed = QEInputParser.parse_file(generated_scf)
        assert scf_reparsed.get_namelist('control').get('calculation') == 'scf'
        assert scf_reparsed.get_namelist('control').get('prefix') == 'si'
        
        # Test NSCF
        nscf_file = si_dos_dir / "si.2_nscf.in"
        nscf_input = QEInputParser.parse_file(nscf_file)
        
        generated_nscf = tmp_path / "si.2_nscf_generated.in"
        QEInputGenerator.write_file(nscf_input, generated_nscf)
        assert generated_nscf.exists()
        
        # Re-parse generated file
        nscf_reparsed = QEInputParser.parse_file(generated_nscf)
        assert nscf_reparsed.get_namelist('control').get('calculation') == 'nscf'
        assert nscf_reparsed.get_namelist('control').get('prefix') == 'si'
        assert nscf_reparsed.get_namelist('system').get('occupations') == 'tetrahedra'
        
        # Test DOS
        dos_file = si_dos_dir / "si.3_dos.in"
        dos_input = QEInputParser.parse_file(dos_file)
        
        generated_dos = tmp_path / "si.3_dos_generated.in"
        QEInputGenerator.write_file(dos_input, generated_dos)
        assert generated_dos.exists()
        
        # Re-parse generated file
        dos_reparsed = QEInputParser.parse_file(generated_dos)
        dos_reparsed_namelist = dos_reparsed.get_namelist('dos')
        assert dos_reparsed_namelist is not None
        assert dos_reparsed_namelist.get('prefix') == 'si'
        assert dos_reparsed_namelist.get('fildos') == 'si.dos.dat'
    
    def test_workflow_sequence(self, si_dos_dir):
        """Test that workflow files are in correct sequence."""
        # Verify files exist in order
        files = [
            si_dos_dir / "si.1_scf.in",
            si_dos_dir / "si.2_nscf.in",
            si_dos_dir / "si.3_dos.in"
        ]
        
        for file in files:
            assert file.exists(), f"Workflow file not found: {file}"
        
        # Verify calculation types are correct sequence
        scf_input = QEInputParser.parse_file(files[0])
        nscf_input = QEInputParser.parse_file(files[1])
        dos_input = QEInputParser.parse_file(files[2])
        
        assert scf_input.get_namelist('control').get('calculation') == 'scf'
        assert nscf_input.get_namelist('control').get('calculation') == 'nscf'
        assert dos_input.get_namelist('dos') is not None  # DOS has &DOS, not &control
    
    def test_structure_consistency(self, si_dos_dir):
        """Test that SCF and NSCF use the same structure."""
        scf_file = si_dos_dir / "si.1_scf.in"
        nscf_file = si_dos_dir / "si.2_nscf.in"
        
        scf_input = QEInputParser.parse_file(scf_file)
        nscf_input = QEInputParser.parse_file(nscf_file)
        
        # Both should have same system parameters
        scf_system = scf_input.get_namelist('system')
        nscf_system = nscf_input.get_namelist('system')
        
        assert scf_system.get('ibrav') == nscf_system.get('ibrav')
        assert scf_system.get('nat') == nscf_system.get('nat')
        assert scf_system.get('ntyp') == nscf_system.get('ntyp')
        assert scf_system.get('ecutwfc') == nscf_system.get('ecutwfc')
        
        # Both should have same atomic species
        scf_species = scf_input.get_card(QECardType.ATOMIC_SPECIES)
        nscf_species = nscf_input.get_card(QECardType.ATOMIC_SPECIES)
        
        assert len(scf_species.data) == len(nscf_species.data)
        assert scf_species.data[0][0] == nscf_species.data[0][0]  # Same element
        
        # Both should have same atomic positions
        scf_pos = scf_input.get_card(QECardType.ATOMIC_POSITIONS)
        nscf_pos = nscf_input.get_card(QECardType.ATOMIC_POSITIONS)
        
        assert len(scf_pos.data) == len(nscf_pos.data)
        # Positions should be the same
        for i in range(len(scf_pos.data)):
            assert scf_pos.data[i] == nscf_pos.data[i]
    
    def test_run_scf_calculation(self, si_dos_dir, qe_engine, tmp_path):
        """Test running SCF calculation."""
        scf_file = si_dos_dir / "si.1_scf.in"
        assert scf_file.exists()
        
        # Parse and fix pseudo_dir before running
        scf_input = QEInputParser.parse_file(scf_file)
        control = scf_input.get_namelist("control")
        if control:
            # Set pseudo_dir to working directory where pseudos will be downloaded
            control.parameters["pseudo_dir"] = str(tmp_path)
        project_root = Path(__file__).parent.parent.parent
        set_outdir_to_temp(scf_input, project_root)
        
        # Write modified input to working directory
        modified_scf = tmp_path / "si.1_scf.in"
        QEInputGenerator.write_file(scf_input, modified_scf)
        
        # Run SCF calculation
        result = test_input_roundtrip_execution(
            input_file=modified_scf,
            qe_engine=qe_engine,
            timeout=120,
            working_dir=tmp_path,
            step_number="1"
        )
        
        assert result["parse_success"], f"Parse failed: {result.get('error')}"
        assert result["generate_success"], f"Generate failed: {result.get('error')}"
        assert result["run_success"], f"Run failed: {result.get('error')}"
        assert result["verify_success"], f"Verify failed: {result.get('message')}"
        
        # Check output file exists
        assert result.get("output_file") is not None
        output_file = Path(result["output_file"])
        assert output_file.exists(), "Output file should exist"
        
        # Check for JOB DONE
        output_content = output_file.read_text()
        assert "JOB DONE" in output_content, "Output should contain JOB DONE"
    
    def test_run_nscf_calculation(self, si_dos_dir, qe_engine, tmp_path):
        """Test running NSCF calculation (requires SCF output)."""
        project_root = Path(__file__).parent.parent.parent
        
        # First run SCF
        scf_file = si_dos_dir / "si.1_scf.in"
        scf_input = QEInputParser.parse_file(scf_file)
        control = scf_input.get_namelist("control")
        if control:
            control.parameters["pseudo_dir"] = str(tmp_path)
        set_outdir_to_temp(scf_input, project_root)
        modified_scf = tmp_path / "si.1_scf.in"
        QEInputGenerator.write_file(scf_input, modified_scf)
        
        scf_result = test_input_roundtrip_execution(
            input_file=modified_scf,
            qe_engine=qe_engine,
            timeout=120,
            working_dir=tmp_path,
            step_number="1"
        )
        assert scf_result["run_success"], "SCF must succeed before NSCF"
        
        # Then run NSCF
        nscf_file = si_dos_dir / "si.2_nscf.in"
        nscf_input = QEInputParser.parse_file(nscf_file)
        nscf_control = nscf_input.get_namelist("control")
        if nscf_control:
            nscf_control.parameters["pseudo_dir"] = str(tmp_path)
        set_outdir_to_temp(nscf_input, project_root)
        modified_nscf = tmp_path / "si.2_nscf.in"
        QEInputGenerator.write_file(nscf_input, modified_nscf)
        
        nscf_result = test_input_roundtrip_execution(
            input_file=modified_nscf,
            qe_engine=qe_engine,
            timeout=120,
            working_dir=tmp_path,
            step_number="2"
        )
        
        assert nscf_result["parse_success"], f"NSCF parse failed: {nscf_result.get('error')}"
        assert nscf_result["generate_success"], f"NSCF generate failed: {nscf_result.get('error')}"
        assert nscf_result["run_success"], f"NSCF run failed: {nscf_result.get('error')}"
        assert nscf_result["verify_success"], f"NSCF verify failed: {nscf_result.get('message')}"
        
        # Check output file
        assert nscf_result.get("output_file") is not None
        nscf_output = Path(nscf_result["output_file"])
        assert nscf_output.exists()
        
        # Check for JOB DONE
        nscf_content = nscf_output.read_text()
        assert "JOB DONE" in nscf_content, "NSCF output should contain JOB DONE"
        
        # Extract and compare Fermi energy with reference
        reference_out = si_dos_dir / "reference_out" / "si.2_nscf.out"
        if reference_out.exists():
            fermi_tolerance = get_fermi_energy_tolerance()  # 0.01 Ry
            
            # Extract Fermi energy from actual output
            fermi_patterns = [
                r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+ev",
                r"Fermi\s+energy\s*=\s*([-\d.]+)\s+Ry",
                r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+Ry",
            ]
            
            actual_fermi = None
            for pattern in fermi_patterns:
                match = re.search(pattern, nscf_content, re.IGNORECASE)
                if match:
                    try:
                        actual_fermi = float(match.group(1))
                        # Convert eV to Ry if needed (1 Ry = 13.6057 eV)
                        if "ev" in pattern.lower():
                            actual_fermi = actual_fermi / 13.6057
                        break
                    except ValueError:
                        continue
            
            # Extract Fermi energy from reference output
            reference_content = reference_out.read_text()
            reference_fermi = None
            for pattern in fermi_patterns:
                match = re.search(pattern, reference_content, re.IGNORECASE)
                if match:
                    try:
                        reference_fermi = float(match.group(1))
                        if "ev" in pattern.lower():
                            reference_fermi = reference_fermi / 13.6057
                        break
                    except ValueError:
                        continue
            
            # Compare Fermi energies
            if actual_fermi is not None and reference_fermi is not None:
                fermi_diff = abs(actual_fermi - reference_fermi)
                assert fermi_diff <= fermi_tolerance, \
                    f"Fermi energy mismatch: {actual_fermi:.8f} vs {reference_fermi:.8f} Ry " \
                    f"(diff: {fermi_diff:.2e}, tolerance: {fermi_tolerance:.2e})"
                print(f"✓ Fermi energy matches: {actual_fermi:.8f} Ry (diff: {fermi_diff:.2e})")
            elif actual_fermi is not None:
                print(f"⚠️  Fermi energy found in output ({actual_fermi:.8f} Ry) but not in reference")
            else:
                print("⚠️  Fermi energy not found in output")
    
    def test_run_full_workflow(self, si_dos_dir, qe_engine, tmp_path):
        """Test running full SCF -> NSCF -> DOS workflow."""
        project_root = Path(__file__).parent.parent.parent
        
        # Step 1: Run SCF
        scf_file = si_dos_dir / "si.1_scf.in"
        scf_input = QEInputParser.parse_file(scf_file)
        control = scf_input.get_namelist("control")
        if control:
            control.parameters["pseudo_dir"] = str(tmp_path)
        set_outdir_to_temp(scf_input, project_root)
        modified_scf = tmp_path / "si.1_scf.in"
        QEInputGenerator.write_file(scf_input, modified_scf)
        
        scf_result = test_input_roundtrip_execution(
            input_file=modified_scf,
            qe_engine=qe_engine,
            timeout=120,
            working_dir=tmp_path,
            step_number="1"
        )
        assert scf_result["run_success"], f"SCF failed: {scf_result.get('error')}"
        print(f"✓ SCF completed: {scf_result.get('message', 'OK')}")
        
        # Step 2: Run NSCF
        nscf_file = si_dos_dir / "si.2_nscf.in"
        nscf_input = QEInputParser.parse_file(nscf_file)
        nscf_control = nscf_input.get_namelist("control")
        if nscf_control:
            nscf_control.parameters["pseudo_dir"] = str(tmp_path)
        set_outdir_to_temp(nscf_input, project_root)
        modified_nscf = tmp_path / "si.2_nscf.in"
        QEInputGenerator.write_file(nscf_input, modified_nscf)
        
        nscf_result = test_input_roundtrip_execution(
            input_file=modified_nscf,
            qe_engine=qe_engine,
            timeout=120,
            working_dir=tmp_path,
            step_number="2"
        )
        assert nscf_result["run_success"], f"NSCF failed: {nscf_result.get('error')}"
        print(f"✓ NSCF completed: {nscf_result.get('message', 'OK')}")
        
        # Compare Fermi energy with reference
        reference_out = si_dos_dir / "reference_out" / "si.2_nscf.out"
        if reference_out.exists() and nscf_result.get("output_file"):
            nscf_output = Path(nscf_result["output_file"])
            if nscf_output.exists():
                fermi_tolerance = get_fermi_energy_tolerance()  # 0.01 Ry
                nscf_content = nscf_output.read_text()
                reference_content = reference_out.read_text()
                
                fermi_patterns = [
                    r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+ev",
                    r"Fermi\s+energy\s*=\s*([-\d.]+)\s+Ry",
                    r"the\s+Fermi\s+energy\s+is\s+([-\d.]+)\s+Ry",
                ]
                
                actual_fermi = None
                for pattern in fermi_patterns:
                    match = re.search(pattern, nscf_content, re.IGNORECASE)
                    if match:
                        try:
                            actual_fermi = float(match.group(1))
                            if "ev" in pattern.lower():
                                actual_fermi = actual_fermi / 13.6057
                            break
                        except ValueError:
                            continue
                
                reference_fermi = None
                for pattern in fermi_patterns:
                    match = re.search(pattern, reference_content, re.IGNORECASE)
                    if match:
                        try:
                            reference_fermi = float(match.group(1))
                            if "ev" in pattern.lower():
                                reference_fermi = reference_fermi / 13.6057
                            break
                        except ValueError:
                            continue
                
                if actual_fermi is not None and reference_fermi is not None:
                    fermi_diff = abs(actual_fermi - reference_fermi)
                    assert fermi_diff <= fermi_tolerance, \
                        f"Fermi energy mismatch: {actual_fermi:.8f} vs {reference_fermi:.8f} Ry " \
                        f"(diff: {fermi_diff:.2e}, tolerance: {fermi_tolerance:.2e})"
                    print(f"✓ Fermi energy matches: {actual_fermi:.8f} Ry (diff: {fermi_diff:.2e}, ref: {reference_fermi:.8f} Ry)")
                elif actual_fermi is not None:
                    print(f"⚠️  Fermi energy found ({actual_fermi:.8f} Ry) but not in reference")
                else:
                    print("⚠️  Fermi energy not found in output")
        
        # Step 3: Run DOS (using dos.x, not pw.x)
        dos_file = si_dos_dir / "si.3_dos.in"
        
        # Parse DOS input to get parameters
        dos_input = QEInputParser.parse_file(dos_file)
        dos_namelist = dos_input.get_namelist("dos")
        
        # Get outdir from temp
        temp_outdir = project_root / "temp" / "outdir"
        temp_outdir.mkdir(parents=True, exist_ok=True)
        
        # Create DOS input file manually (dos.x is sensitive to input format)
        # Use original format but with updated outdir
        dos_input_content = f"""&DOS
    prefix='{dos_namelist.get("prefix", "si")}'
    outdir='{temp_outdir.absolute()}'
    fildos='{dos_namelist.get("fildos", "si.dos.dat")}'
    emin={dos_namelist.get("emin", -9.0)}
    emax={dos_namelist.get("emax", 16.0)}
/
"""
        generated_dos = tmp_path / "si.3_dos.in"
        generated_dos.write_text(dos_input_content)
        
        # Run dos.x directly
        import subprocess
        import os
        
        # Build command for dos.x
        dos_executable = qe_engine.get_executable_path("dos.x")
        if not dos_executable or not Path(dos_executable).exists():
            pytest.skip("dos.x not found")
        
        command = [dos_executable, "-inp", str(generated_dos)]
        
        # Set environment
        env = os.environ.copy()
        env['ESPRESSO_PSEUDO'] = str(tmp_path)
        
        # Run dos.x
        try:
            result_dos = subprocess.run(
                command,
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )
            
            # Write output
            stdout_file = tmp_path / "dos_stdout.txt"
            stdout_file.write_text(result_dos.stdout)
            
            # Check if successful
            assert result_dos.returncode == 0, f"dos.x failed with return code {result_dos.returncode}\n{result_dos.stderr}"
            assert len(result_dos.stdout) > 100, "DOS calculation should produce output"
            
            # Check if DOS data file was created
            if dos_namelist and dos_namelist.get("fildos"):
                dos_data_file = tmp_path / dos_namelist.get("fildos")
                if dos_data_file.exists():
                    print(f"✓ DOS data file created: {dos_data_file.name}")
            
            print(f"✓ DOS completed")
        except subprocess.TimeoutExpired:
            pytest.fail("DOS calculation timed out")
        except Exception as e:
            pytest.fail(f"DOS calculation failed: {e}")
        
        # Verify all steps succeeded
        assert scf_result["run_success"], "SCF must succeed"
        assert nscf_result["run_success"], "NSCF must succeed"
        
        # Clean up temp/outdir
        temp_outdir = project_root / "temp" / "outdir"
        if temp_outdir.exists():
            try:
                shutil.rmtree(temp_outdir)
            except Exception:
                pass  # Ignore cleanup errors

