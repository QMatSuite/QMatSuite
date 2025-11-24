"""
Integration test for 7_Si_bandStructure workflow from CI test data.

This test validates the SCF -> NSCF -> Bands -> bands.x workflow using files
from tests/integration/ci_test_data/7_Si_bandStructure/ and actually runs QE calculations.
"""

import pytest
from pathlib import Path
import sys
import os
import tempfile
import shutil
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "extended-tests" / "utils"))

from quantumvitas.core.engines.qe_input import (
    QEInputParser, QEInputGenerator, QEInput, QENamelist, QECard, QECardType
)
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
# Removed: run_input_roundtrip_execution, set_outdir_to_temp, set_pseudo_dir_to_temp
# Now using run_and_verify_step_with_assert from tests.core
from tests.core.thresholds import get_fermi_energy_tolerance
from tests.core.qe_test_utils import parse_jobconfig
from tests.core import run_and_verify_step_with_assert
import re


class TestSiBandsWorkflow:
    """Test SCF -> NSCF -> Bands -> bands.x workflow using 7_Si_bandStructure examples."""
    
    @pytest.fixture
    def test_data_dir(self):
        """Get path to ci_test_data directory."""
        project_root = Path(__file__).parent.parent.parent
        ci_test_data_dir = project_root / "tests" / "integration" / "ci_test_data"
        if not ci_test_data_dir.exists():
            pytest.skip(f"CI test data not found: {ci_test_data_dir}")
        return ci_test_data_dir
    
    @pytest.fixture
    def si_bands_dir(self, test_data_dir):
        """Get path to 7_Si_bandStructure test data directory."""
        si_bands_dir = test_data_dir / "7_Si_bandStructure"
        if not si_bands_dir.exists():
            pytest.skip(f"7_Si_bandStructure test data not found: {si_bands_dir}")
        return si_bands_dir
    
    @pytest.fixture
    def qe_engine(self):
        """Create QE engine instance."""
        config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(config)
        if not engine.detect_executable("pw.x"):
            pytest.skip("pw.x not found. QE installation required.")
        if not engine.detect_executable("bands.x"):
            pytest.skip("bands.x not found. QE installation required.")
        return engine
    
    def test_parse_scf_input(self, si_bands_dir):
        """Test parsing SCF input file."""
        scf_file = si_bands_dir / "si.0_scf.in"
        assert scf_file.exists(), f"SCF file not found: {scf_file}"
        
        scf_input = QEInputParser.parse_file(scf_file)
        assert scf_input is not None
        
        # Verify control namelist
        control = scf_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'scf'
        
        # Verify system namelist
        system = scf_input.get_namelist('system')
        assert system is not None
        assert system.get('ibrav') == 2
        assert system.get('nat') == 2
        assert system.get('ntyp') == 1
        ecutwfc = system.get('ecutwfc')
        assert ecutwfc is not None, "ecutwfc should be present"
        assert ecutwfc > 0, f"ecutwfc should be positive, got {ecutwfc}"
        
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
    
    def test_parse_nscf_input(self, si_bands_dir):
        """Test parsing NSCF input file."""
        nscf_file = si_bands_dir / "si.1_nscf.in"
        assert nscf_file.exists(), f"NSCF file not found: {nscf_file}"
        
        nscf_input = QEInputParser.parse_file(nscf_file)
        assert nscf_input is not None
        
        # Verify control namelist
        control = nscf_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'nscf'
        
        # Verify system namelist
        system = nscf_input.get_namelist('system')
        assert system is not None
        assert system.get('ibrav') == 2
        assert system.get('nat') == 2
        assert system.get('ntyp') == 1
    
    def test_parse_bands_input(self, si_bands_dir):
        """Test parsing bands input file."""
        bands_file = si_bands_dir / "si.2_bands.in"
        assert bands_file.exists(), f"Bands file not found: {bands_file}"
        
        bands_input = QEInputParser.parse_file(bands_file)
        assert bands_input is not None
        
        # Verify control namelist
        control = bands_input.get_namelist('control')
        assert control is not None
        assert control.get('calculation') == 'bands'
    
    def test_parse_bands_pp_input(self, si_bands_dir):
        """Test parsing bands.x post-processing input file."""
        bands_pp_file = si_bands_dir / "si.3_bands.pp.in"
        assert bands_pp_file.exists(), f"Bands PP file not found: {bands_pp_file}"
        
        bands_pp_input = QEInputParser.parse_file(bands_pp_file)
        assert bands_pp_input is not None
        
        # Verify bands namelist
        bands_namelist = bands_pp_input.get_namelist('bands')
        assert bands_namelist is not None
    
    def test_workflow_prefix_consistency(self, si_bands_dir):
        """Test that all workflow steps are consistent."""
        scf_file = si_bands_dir / "si.0_scf.in"
        nscf_file = si_bands_dir / "si.1_nscf.in"
        bands_file = si_bands_dir / "si.2_bands.in"
        
        scf_input = QEInputParser.parse_file(scf_file)
        nscf_input = QEInputParser.parse_file(nscf_file)
        bands_input = QEInputParser.parse_file(bands_file)
        
        # All should have the same prefix
        scf_prefix = scf_input.get_namelist('control').get('prefix', 'pwscf')
        nscf_prefix = nscf_input.get_namelist('control').get('prefix', 'pwscf')
        bands_prefix = bands_input.get_namelist('control').get('prefix', 'pwscf')
        
        assert scf_prefix == nscf_prefix == bands_prefix, \
            f"Prefix mismatch: SCF={scf_prefix}, NSCF={nscf_prefix}, Bands={bands_prefix}"
    
    def test_roundtrip_generation(self, si_bands_dir, tmp_path):
        """Test roundtrip parsing and generation."""
        scf_file = si_bands_dir / "si.0_scf.in"
        generated_scf = tmp_path / "si.0_scf_generated.in"
        
        scf_input = QEInputParser.parse_file(scf_file)
        QEInputGenerator.write_file(scf_input, generated_scf)
        assert generated_scf.exists()
        
        nscf_file = si_bands_dir / "si.1_nscf.in"
        generated_nscf = tmp_path / "si.1_nscf_generated.in"
        
        nscf_input = QEInputParser.parse_file(nscf_file)
        QEInputGenerator.write_file(nscf_input, generated_nscf)
        assert generated_nscf.exists()
        
        bands_file = si_bands_dir / "si.2_bands.in"
        generated_bands = tmp_path / "si.2_bands_generated.in"
        
        bands_input = QEInputParser.parse_file(bands_file)
        QEInputGenerator.write_file(bands_input, generated_bands)
        assert generated_bands.exists()
        
        bands_pp_file = si_bands_dir / "si.3_bands.pp.in"
        generated_bands_pp = tmp_path / "si.3_bands.pp_generated.in"
        
        bands_pp_input = QEInputParser.parse_file(bands_pp_file)
        QEInputGenerator.write_file(bands_pp_input, generated_bands_pp)
        assert generated_bands_pp.exists()
    
    def test_workflow_sequence(self, si_bands_dir, test_data_dir):
        """Test that workflow files are in correct sequence from jobconfig."""
        # Parse jobconfig to get workflow order
        jobconfig_path = test_data_dir / "jobconfig"
        if not jobconfig_path.exists():
            pytest.skip(f"jobconfig file not found: {jobconfig_path}")
        
        all_tests = parse_jobconfig(jobconfig_path, "")
        category = "7_Si_bandStructure"
        
        if category not in all_tests:
            pytest.skip(f"Category '{category}' not found in jobconfig")
        
        test_files = all_tests[category]
        
        # Build file paths from jobconfig
        files = [si_bands_dir / input_file for input_file, args in test_files]
        
        # Verify all files exist and are in correct sequence
        for file in files:
            assert file.exists(), f"Workflow file not found: {file}"
        
        # Verify calculation types are correct sequence
        scf_input = QEInputParser.parse_file(files[0])
        nscf_input = QEInputParser.parse_file(files[1])
        bands_input = QEInputParser.parse_file(files[2])
        
        assert scf_input.get_namelist('control').get('calculation') == 'scf'
        assert nscf_input.get_namelist('control').get('calculation') == 'nscf'
        assert bands_input.get_namelist('control').get('calculation') == 'bands'
    
    def test_structure_consistency(self, si_bands_dir):
        """Test that structure is consistent across workflow steps."""
        scf_file = si_bands_dir / "si.0_scf.in"
        nscf_file = si_bands_dir / "si.1_nscf.in"
        bands_file = si_bands_dir / "si.2_bands.in"
        
        scf_input = QEInputParser.parse_file(scf_file)
        nscf_input = QEInputParser.parse_file(nscf_file)
        bands_input = QEInputParser.parse_file(bands_file)
        
        scf_system = scf_input.get_namelist('system')
        nscf_system = nscf_input.get_namelist('system')
        bands_system = bands_input.get_namelist('system')
        
        # All should have the same structure
        assert scf_system.get('ibrav') == nscf_system.get('ibrav') == bands_system.get('ibrav')
        assert scf_system.get('nat') == nscf_system.get('nat') == bands_system.get('nat')
        assert scf_system.get('ntyp') == nscf_system.get('ntyp') == bands_system.get('ntyp')
    
    def test_run_scf_calculation(self, si_bands_dir, qe_engine, tmp_path):
        """Test running SCF calculation."""
        project_root = Path(__file__).parent.parent.parent
        
        scf_file = si_bands_dir / "si.0_scf.in"
        
        # Retry mechanism for intermittent buffer overflow errors
        max_retries = 3
        scf_result = None
        
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying SCF calculation (attempt {attempt + 1}/{max_retries}) after {wait_time}s wait...")
                time.sleep(wait_time)
                # Clean up partial files
                for f in tmp_path.glob("*.out"):
                    try:
                        f.unlink()
                    except:
                        pass
            
            try:
                scf_reference = si_bands_dir / "reference_out" / "si.0_scf.out"
                scf_result = run_and_verify_step_with_assert(
                    input_file=scf_file,
                    qe_engine=qe_engine,
                    working_dir=tmp_path,
                    reference_file=scf_reference,
                    category="7_Si_bandStructure",
                    timeout=300,
                    project_root=project_root
                )
                break  # Success
            except AssertionError as e:
                error_msg = str(e)
                if ('buffer overflow' in error_msg.lower() or 'SIGABRT' in error_msg or 'MPI_ABORT' in error_msg) and attempt < max_retries - 1:
                    continue  # Retry
                else:
                    raise  # Non-retryable error or last attempt
        
        assert scf_result.success, f"SCF failed: {scf_result.error}"
        print(f"✓ SCF completed and verified: {scf_result.step_type}")
    
    def test_run_nscf_calculation(self, si_bands_dir, qe_engine, tmp_path):
        """Test running NSCF calculation."""
        project_root = Path(__file__).parent.parent.parent
        
        # First run SCF to generate .save directory
        scf_file = si_bands_dir / "si.0_scf.in"
        scf_reference = si_bands_dir / "reference_out" / "si.0_scf.out"
        
        scf_result = run_and_verify_step_with_assert(
            input_file=scf_file,
            qe_engine=qe_engine,
            working_dir=tmp_path,
            reference_file=scf_reference,
            category="7_Si_bandStructure",
            timeout=300,
            project_root=project_root
        )
        assert scf_result.success, f"SCF must succeed first: {scf_result.error}"
        
        # Small delay to ensure file system synchronization
        time.sleep(0.5)
        
        # Verify that .save directory exists
        temp_outdir = project_root / "temp" / "outdir"
        save_dir = temp_outdir / "si.save"
        if not save_dir.exists():
            working_save = tmp_path / "si.save"
            if working_save.exists():
                import shutil
                shutil.copytree(working_save, save_dir, dirs_exist_ok=True)
        
        # Now run NSCF
        nscf_file = si_bands_dir / "si.1_nscf.in"
        nscf_reference = si_bands_dir / "reference_out" / "si.1_nscf.out"
        
        max_retries = 3
        nscf_result = None
        
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying NSCF calculation (attempt {attempt + 1}/{max_retries}) after {wait_time}s wait...")
                time.sleep(wait_time)
            
            try:
                nscf_result = run_and_verify_step_with_assert(
                    input_file=nscf_file,
                    qe_engine=qe_engine,
                    working_dir=tmp_path,
                    reference_file=nscf_reference,
                    category="7_Si_bandStructure",
                    timeout=300,
                    project_root=project_root
                )
                break  # Success
            except AssertionError as e:
                error_msg = str(e)
                if ('buffer overflow' in error_msg.lower() or 'SIGABRT' in error_msg or 'MPI_ABORT' in error_msg) and attempt < max_retries - 1:
                    continue  # Retry
                else:
                    raise  # Non-retryable error or last attempt
        
        assert nscf_result.success, f"NSCF failed: {nscf_result.error}"
        print(f"✓ NSCF completed and verified: {nscf_result.step_type}")
    
    def test_run_full_workflow(self, si_bands_dir, qe_engine, test_data_dir, tmp_path):
        """Test running full SCF -> NSCF -> Bands -> bands.x workflow using jobconfig."""
        project_root = Path(__file__).parent.parent.parent
        
        # Parse jobconfig to get workflow order
        jobconfig_path = test_data_dir / "jobconfig"
        if not jobconfig_path.exists():
            raise RuntimeError(
                f"jobconfig file not found: {jobconfig_path}. "
                f"Reason: jobconfig file is required to determine workflow order."
            )
        
        all_tests = parse_jobconfig(jobconfig_path, "")
        category = "7_Si_bandStructure"
        
        if category not in all_tests:
            raise RuntimeError(
                f"Category '{category}' not found in jobconfig. "
                f"Reason: The category '{category}' is not defined in the jobconfig file. "
                f"Available categories: {list(all_tests.keys())}"
            )
        
        test_files = all_tests[category]
        if not test_files:
            raise RuntimeError(
                f"No test files found for category '{category}'. "
                f"Reason: Category '{category}' exists in jobconfig but has no test files defined."
            )
        
        # Get workflow files from jobconfig
        scf_file = si_bands_dir / test_files[0][0]  # si.0_scf.in
        nscf_file = si_bands_dir / test_files[1][0]  # si.1_nscf.in
        bands_file = si_bands_dir / test_files[2][0]  # si.2_bands.in
        bands_pp_file = si_bands_dir / test_files[3][0]  # si.3_bands.pp.in
        
        # Verify we have the expected files
        assert scf_file.name == "si.0_scf.in", f"Expected si.0_scf.in, got {scf_file.name}"
        assert nscf_file.name == "si.1_nscf.in", f"Expected si.1_nscf.in, got {nscf_file.name}"
        assert bands_file.name == "si.2_bands.in", f"Expected si.2_bands.in, got {bands_file.name}"
        assert bands_pp_file.name == "si.3_bands.pp.in", f"Expected si.3_bands.pp.in, got {bands_pp_file.name}"
        
        # Retry mechanism for intermittent buffer overflow errors
        max_retries = 3
        
        # Step 1: Run SCF with retry
        scf_result = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying SCF calculation (attempt {attempt + 1}/{max_retries}) after {wait_time}s wait...")
                time.sleep(wait_time)
                # Clean up partial files
                for f in tmp_path.glob("*.out"):
                    try:
                        f.unlink()
                    except:
                        pass
            
            try:
                scf_reference = si_bands_dir / "reference_out" / "si.0_scf.out"
                scf_result = run_and_verify_step_with_assert(
                    input_file=scf_file,
                    qe_engine=qe_engine,
                    working_dir=tmp_path,
                    reference_file=scf_reference,
                    category="7_Si_bandStructure",
                    timeout=300,
                    project_root=project_root
                )
                break  # Success
            except AssertionError as e:
                error_msg = str(e)
                if ('buffer overflow' in error_msg.lower() or 'SIGABRT' in error_msg or 'MPI_ABORT' in error_msg) and attempt < max_retries - 1:
                    continue  # Retry
                else:
                    raise  # Non-retryable error or last attempt
        
        assert scf_result.success, f"SCF failed: {scf_result.error}"
        print(f"✓ SCF completed and verified: {scf_result.step_type}")
        
        # Small delay to ensure file system synchronization
        time.sleep(0.5)
        
        # Verify that .save directory exists
        temp_outdir = project_root / "temp" / "outdir"
        save_dir = temp_outdir / "si.save"
        if not save_dir.exists():
            working_save = tmp_path / "si.save"
            if working_save.exists():
                import shutil
                shutil.copytree(working_save, save_dir, dirs_exist_ok=True)
        
        # Step 2: Run NSCF with retry
        nscf_reference = si_bands_dir / "reference_out" / "si.1_nscf.out"
        nscf_result = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying NSCF calculation (attempt {attempt + 1}/{max_retries}) after {wait_time}s wait...")
                time.sleep(wait_time)
            
            try:
                nscf_result = run_and_verify_step_with_assert(
                    input_file=nscf_file,
                    qe_engine=qe_engine,
                    working_dir=tmp_path,
                    reference_file=nscf_reference,
                    category="7_Si_bandStructure",
                    timeout=300,
                    project_root=project_root
                )
                break  # Success
            except AssertionError as e:
                error_msg = str(e)
                if ('buffer overflow' in error_msg.lower() or 'SIGABRT' in error_msg or 'MPI_ABORT' in error_msg) and attempt < max_retries - 1:
                    continue  # Retry
                else:
                    raise  # Non-retryable error or last attempt
        
        assert nscf_result.success, f"NSCF failed: {nscf_result.error}"
        print(f"✓ NSCF completed and verified: {nscf_result.step_type}")
        
        time.sleep(0.5)
        
        # Step 3: Run Bands calculation (no reference file, just check JOB DONE)
        bands_result = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = 2 ** attempt
                print(f"Retrying Bands calculation (attempt {attempt + 1}/{max_retries}) after {wait_time}s wait...")
                time.sleep(wait_time)
            
            try:
                bands_result = run_and_verify_step_with_assert(
                    input_file=bands_file,
                    qe_engine=qe_engine,
                    working_dir=tmp_path,
                    reference_file=None,  # No reference for bands calculation
                    category="7_Si_bandStructure",
                    timeout=300,
                    project_root=project_root
                )
                break  # Success
            except AssertionError as e:
                error_msg = str(e)
                if ('buffer overflow' in error_msg.lower() or 'SIGABRT' in error_msg or 'MPI_ABORT' in error_msg) and attempt < max_retries - 1:
                    continue  # Retry
                else:
                    raise  # Non-retryable error or last attempt
        
        assert bands_result.success, f"Bands failed: {bands_result.error}"
        print(f"✓ Bands completed and verified: {bands_result.step_type}")
        
        time.sleep(0.5)
        
        # Step 4: Run bands.x post-processing
        bands_pp_file_path = si_bands_dir / "si.3_bands.pp.in"
        
        # Parse bands.x input to get parameters
        bands_pp_input = QEInputParser.parse_file(bands_pp_file_path)
        bands_namelist = bands_pp_input.get_namelist("bands")
        
        # Get outdir from temp
        temp_outdir = project_root / "temp" / "outdir"
        temp_outdir.mkdir(parents=True, exist_ok=True)
        
        # Create bands.x input file manually
        prefix = "si"  # Default prefix
        bands_pp_input_content = f"""&bands
    prefix='{prefix}'
    outdir='{temp_outdir.absolute()}'
    filband='{bands_namelist.get("filband", "si.bands.dat")}'
/
"""
        generated_bands_pp = tmp_path / "si.3_bands.pp.in"
        generated_bands_pp.write_text(bands_pp_input_content)
        
        # Run bands.x directly
        import subprocess
        
        # Build command for bands.x (without input file flag, will use stdin redirection)
        bands_executable = qe_engine.get_executable_path("bands.x")
        if not bands_executable or not Path(bands_executable).exists():
            pytest.skip("bands.x not found")
        
        command = [str(bands_executable)]  # No -inp flag, will use stdin redirection
        
        # Set environment
        temp_pseudo_dir = project_root / "temp" / "pseudo"
        temp_pseudo_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env['ESPRESSO_PSEUDO'] = str(temp_pseudo_dir.absolute())
        env['OMP_NUM_THREADS'] = '1'
        
        # Run bands.x with stdin redirection (bands.x < input.in)
        try:
            with open(generated_bands_pp, 'r') as stdin_file:
                result_bands_pp = subprocess.run(
                    command,
                    cwd=tmp_path,
                    stdin=stdin_file,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    env=env
                )
            
            # Write output
            stdout_file = tmp_path / "bands_pp_stdout.txt"
            stdout_file.write_text(result_bands_pp.stdout)
            
            # Save bands.x output to temp/test_outputs for debugging
            try:
                temp_output_dir = project_root / "temp" / "test_outputs" / "7_Si_bandStructure"
                temp_output_dir.mkdir(parents=True, exist_ok=True)
                bands_pp_output_file = temp_output_dir / "si.3_bands.pp_step4.out"
                bands_pp_output_file.write_text(result_bands_pp.stdout)
                print(f"✓ bands.x output saved to: {bands_pp_output_file}")
            except Exception as e:
                print(f"Warning: Failed to save bands.x output to temp/test_outputs: {e}")
            
            # Check if successful
            assert result_bands_pp.returncode == 0, f"bands.x failed with return code {result_bands_pp.returncode}\n{result_bands_pp.stderr}"
            assert len(result_bands_pp.stdout) > 100, "bands.x calculation should produce output"
            
            # Check if bands data file was created
            if bands_namelist and bands_namelist.get("filband"):
                bands_data_file = tmp_path / bands_namelist.get("filband")
                if bands_data_file.exists():
                    print(f"✓ Bands data file created: {bands_data_file.name}")
                    # Also save bands data file to temp/test_outputs
                    try:
                        bands_data_output_file = temp_output_dir / bands_data_file.name
                        shutil.copy2(bands_data_file, bands_data_output_file)
                        print(f"✓ Bands data file saved to: {bands_data_output_file}")
                    except Exception as e:
                        print(f"Warning: Failed to save bands data file to temp/test_outputs: {e}")
            
            print(f"✓ bands.x completed")
        except subprocess.TimeoutExpired:
            pytest.fail("bands.x calculation timed out")
        except Exception as e:
            pytest.fail(f"bands.x calculation failed: {e}")
        
        # Verify all steps succeeded
        assert scf_result.success, "SCF must succeed"
        assert nscf_result.success, "NSCF must succeed"
        assert bands_result.success, "Bands must succeed"
        
        # Clean up temp/outdir
        temp_outdir = project_root / "temp" / "outdir"
        if temp_outdir.exists():
            try:
                shutil.rmtree(temp_outdir)
            except Exception:
                pass  # Ignore cleanup errors

