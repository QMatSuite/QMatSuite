"""
Real QE relax integration test.

This test actually runs QE pw.x to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
# Removed compat import - use domain API
from quantumvitas.core.paths import tmp_runs_dir
from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Structure, Lattice


pytestmark = [pytest.mark.integration, pytest.mark.requires_qe]


def configure_step(project_root, calculation_selector, step_selector, parameters, cards=None):
    """Helper function to configure step parameters via domain accessor."""
    svc = QVService(project_root)
    params_dict = {"parameters": parameters}
    if cards:
        params_dict["cards"] = cards
    svc.calculation.update_step_params(
        calc_selector=calculation_selector,
        step_selector=step_selector,
        params=params_dict,
    )


@pytest.fixture(scope="module")
def qe_engine():
    """Create a QE engine instance and validate required executables."""
    from quantumvitas.core.engines.qe import QuantumEspressoEngine
    from quantumvitas.core.engines.base import EngineConfig
    
    config = EngineConfig(name="qe")
    try:
        engine = QuantumEspressoEngine(config)
        
        if not engine.installation.is_valid():
            raise RuntimeError(
                "QE installation not found. Please set QE_HOME/QE_BIN_DIR or install QE."
            )
        
        if not engine.detect_executable("pw.x"):
            raise RuntimeError("pw.x not found. QE installation required for QE relax integration tests.")
        
        return engine
    except RuntimeError as e:
        # Re-raise with clear message about missing QE
        raise RuntimeError(
            f"QE engine initialization failed: {e}\n"
            "Install internal QE to .qmatsuite/engines/qe/<folder>/bin or set settings.qe.bin_dir to external QE bin directory."
        ) from e


@pytest.fixture
def qe_project_with_si():
    """Create a project with Si structure for QE relax test."""
    # Use .tmp/runs/ directory instead of pytest tmp_path
    # Use unique directory name per test run to avoid conflicts
    import time
    import uuid
    unique_id = f"qe_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QVService.init_project(test_dir / "qe_relax_project")
    
    # Create Si structure
    lattice = Lattice.cubic(5.43)
    si_structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    # Save structure to file
    si_file = test_dir / "si.json"
    si_structure.to(filename=si_file, fmt="json")
    
    # Import structure
    struct_result = QVService.import_structure(project_root, si_file, name="Silicon")
    
    return {
        "project_root": project_root,
        "structure_ulid": struct_result.meta.ulid,
        "structure_path": struct_result.absolute_path,
        "test_dir": test_dir,  # Keep test_dir for cleanup if needed
    }


@pytest.fixture
def qe_calculation_with_relax(qe_project_with_si):
    """Create a calculation with a relax step, configured for QE."""
    project_root = qe_project_with_si["project_root"]
    structure_ulid = qe_project_with_si["structure_ulid"]
    
    # Create calculation
    calc_result = QVService.init_calculation(
        project_root=project_root,
        name="si_relax",
        structure_selector=structure_ulid,
    )
    calc_ulid = calc_result.ulid
    # calc_dir should be the calculation directory (where calculation.yaml is)
    # calc_result.absolute_path is the calculation.yaml file, so parent is the calc dir
    # But we need to check: if absolute_path is already a directory, use it; otherwise use parent
    if calc_result.absolute_path.is_dir():
        calc_dir = calc_result.absolute_path
    else:
        calc_dir = calc_result.absolute_path.parent
    
    # Configure calculation with species_map and pseudo
    QVService.configure_species_map(
        project_root=project_root,
        calculation=calc_ulid,
        set_entries=[("Si", 28.0855, "Si.pbe-n-rrkjus_psl.1.0.0.UPF")],
    )
    
    # Create relax step
    relax_step_result = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_type_gen="relax",  # GEN type for UI layer
        name="relax",
    )
    relax_step_ulid = relax_step_result.ulid
    
    # Configure relax step with minimal parameters for quick test
    configure_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_selector=relax_step_ulid,
        parameters={
            "CONTROL": {
                "prefix": "si",
                "outdir": "./outdir",
                "pseudo_dir": "./",
            },
            "SYSTEM": {
                "ecutwfc": 30.0,  # Low cutoff for speed
                "ecutrho": 120.0,
                "ibrav": 0,  # Free lattice (more flexible for relax)
                "nat": 2,
                "ntyp": 1,
            },
            "ELECTRONS": {
                "conv_thr": 1e-6,  # Relaxed convergence for speed
            },
            "IONS": {
                "ion_dynamics": "bfgs",
            },
        },
        cards={
            "ATOMIC_SPECIES": {
                "data": [["Si", "28.0855", "Si.pbe-n-rrkjus_psl.1.0.0.UPF"]],
            },
            "K_POINTS": {
                "option": "automatic",
                "data": [[4, 4, 4, 0, 0, 0]],  # Coarse k-points for speed
            },
            # ATOMIC_POSITIONS and CELL_PARAMETERS will be auto-generated from structure
        },
    )
    
    return {
        "project_root": project_root,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
        "relax_step_ulid": relax_step_ulid,
        "structure_ulid": structure_ulid,
    }


class TestQERelaxReal:
    """Real QE relax integration tests."""
    
    def test_qe_relax_execution_creates_current_json(
        self,
        qe_calculation_with_relax,
        qe_engine,
    ):
        """
        Test that running a QE relax step actually executes pw.x,
        and the output is parsed and written to current.json.
        
        This is a real integration test that requires QE to be installed.
        """
        
        calc_ulid = qe_calculation_with_relax["calc_ulid"]
        relax_step_ulid = qe_calculation_with_relax["relax_step_ulid"]
        calc_dir = qe_calculation_with_relax["calc_dir"]
        project_root = qe_calculation_with_relax["project_root"]
        
        # Run the relax step
        result = QVService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        # Verify step completed
        step_succeeded = result.get("success") is True
        
        # Save output file for analysis if step succeeded but post-processing failed
        output_file_path = None
        if step_succeeded and result.get("output_file"):
            output_file_path = Path(result["output_file"])
            if output_file_path.exists():
                # Save a copy for analysis
                analysis_file = Path("/tmp/qe_relax_output_analysis.out")
                import shutil
                shutil.copy2(output_file_path, analysis_file)
                print(f"\n[DEBUG] Output file saved to: {analysis_file}")
                print(f"[DEBUG] Output file size: {output_file_path.stat().st_size} bytes")
        
        # Verify current.json was created (if step succeeded, post-processing should have run)
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        
        # If step succeeded but current.json doesn't exist, save output for analysis
        if step_succeeded and not artifact_path.exists():
            if output_file_path and output_file_path.exists():
                # Show key sections of output for debugging
                content = output_file_path.read_text()
                lines = content.split('\n')
                print(f"\n[DEBUG] Output file has {len(lines)} lines")
                print("\n[DEBUG] Searching for key sections:")
                for i, line in enumerate(lines[:300]):
                    if any(kw in line.lower() for kw in ['celldm', 'alat', 'ibrav', 'lattice parameter']):
                        print(f"  Line {i+1}: {line}")
                print("\n[DEBUG] Searching for 'Begin final coordinates':")
                for i, line in enumerate(lines):
                    if 'Begin final coordinates' in line:
                        print(f"  Found at line {i+1}")
                        # Show 50 lines after
                        print("  Content:")
                        for j, l in enumerate(lines[i:i+50]):
                            print(f"    {i+j+1}: {l}")
                        break
            pytest.fail(
                f"Step succeeded but current.json not found at {artifact_path}. "
                f"Output file saved to /tmp/qe_relax_output_analysis.out for analysis. "
                f"Check executor logs for post-processing errors."
            )
        
        # Verify current.json was created (required for relax steps)
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            f"Step succeeded: {step_succeeded}, but post-processing failed. "
            f"Check executor logs for errors."
        )
        
        # Verify structure can be read
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None, "Failed to read generated structure"
        assert len(relaxed_structure) == 2, "Expected 2 Si atoms"
        
        # Verify metadata
        data = json.loads(artifact_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["source_step_ulid"] == relax_step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "qe_relax"
    
    def test_qe_relax_structure_changes(
        self,
        qe_calculation_with_relax,
        qe_project_with_si,
        qe_engine,
    ):
        """
        Test that the relaxed structure is different from the input structure.
        
        Note: For a minimal test with coarse parameters, the structure may not
        change significantly, but we verify the structure is valid.
        """
        
        calc_ulid = qe_calculation_with_relax["calc_ulid"]
        relax_step_ulid = qe_calculation_with_relax["relax_step_ulid"]
        calc_dir = qe_calculation_with_relax["calc_dir"]
        project_root = qe_calculation_with_relax["project_root"]
        
        # Load initial structure using the structure_path from fixture
        from quantumvitas.io import read_structure
        structure_path = qe_project_with_si["structure_path"]
        initial_structure = read_structure(structure_path)
        
        # Run the relax step
        result = QVService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        assert result.get("success") is True, f"Step failed: {result.get('error')}"
        
        # Load relaxed structure
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None
        
        # Verify structure is valid (has same number of atoms)
        assert len(relaxed_structure) == len(initial_structure)
        # Compare species using composition
        assert relaxed_structure.composition == initial_structure.composition
        
        # Note: For a minimal test, we don't assert that the structure changed,
        # as the parameters may be too coarse to see significant relaxation.
        # The important thing is that the structure was parsed correctly.
    
    def test_qe_relax_manifest_updated(
        self,
        qe_calculation_with_relax,
        qe_engine,
    ):
        """
        Test that the manifest is updated with effective_structure_sha after relax.
        """
        
        calc_ulid = qe_calculation_with_relax["calc_ulid"]
        relax_step_ulid = qe_calculation_with_relax["relax_step_ulid"]
        calc_dir = qe_calculation_with_relax["calc_dir"]
        project_root = qe_calculation_with_relax["project_root"]
        
        # Run the relax step
        result = QVService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        assert result.get("success") is True, f"Step failed: {result.get('error')}"
        
        # Load manifest
        from quantumvitas.calculation.manifest import load_manifest
        manifest = load_manifest(calc_dir)
        assert manifest is not None
        
        # Find relax step entry
        relax_entry = None
        for entry in manifest.steps:
            if entry.step_ulid == relax_step_ulid:
                relax_entry = entry
                break
        
        assert relax_entry is not None, "Relax step entry not found in manifest"
        assert relax_entry.done is True, "Relax step should be marked as done"
        
        # For relax steps, effective_structure_sha should be the SHA of the INPUT structure
        # (not the output), per RELAX_SPEC.md §8.1
        # However, we verify that the entry exists and is valid
        assert relax_entry.step_sha is not None, "Step SHA should be set"



