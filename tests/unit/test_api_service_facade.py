"""
Tests for API service facade methods.

These tests verify API methods work without requiring engines.
They test the instance-based API (QVService(project_root)).
"""

import os
import pytest
from pathlib import Path

from quantumvitas.api import QVService, QVServiceError


class TestAPIServiceFacade:
    """Test that API facade instance methods work correctly."""

    @pytest.fixture
    def demo_project(self, tmp_path):
        """Create a minimal demo project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        # Create minimal project.qv.yml
        (project_root / "project.qv.yml").write_text("""project:
  name: test_project
  meta:
    id: 01ARZ3NDEKTSV4RRFFQ69G5FAV
    name: test_project
    slug: test-project
    path: "."
    kind: project
structures: []
calculations: []
""")
        
        # Create standard directories
        (project_root / "structures").mkdir()
        (project_root / "calculations").mkdir()
        (project_root / "pseudo").mkdir()
        (project_root / "trash").mkdir()
        
        return project_root

    def test_service_initialization(self, demo_project):
        """QVService can be initialized with project_root."""
        svc = QVService(demo_project)
        assert svc.project_root == demo_project.resolve()

    def test_service_initialization_fails_for_non_project(self, tmp_path):
        """QVService raises error for non-project directory."""
        non_project = tmp_path / "not_a_project"
        non_project.mkdir()
        
        with pytest.raises(QVServiceError, match="Not a project"):
            QVService(non_project)

    def test_load_project_config(self, demo_project):
        """API can load project config."""
        svc = QVService(demo_project)
        config = svc.load_project_config()
        assert "project" in config
        assert config["project"]["name"] == "test_project"

    def test_build_resource_index(self, demo_project):
        """API can build resource index."""
        svc = QVService(demo_project)
        index = svc.build_resource_index()
        assert index is not None
        # Index should be empty for a project with no resources
        assert len(index.by_id) == 0

    def test_detect_context(self, demo_project):
        """API can detect context from cwd."""
        svc = QVService(demo_project)
        
        # Change to project dir
        old_cwd = os.getcwd()
        try:
            os.chdir(demo_project)
            ctx = svc.detect_context()
            # Should detect project root at minimum
            assert ctx is not None
            assert ctx["project_root"] == demo_project.resolve()
            assert ctx["is_project"] is True
        finally:
            os.chdir(old_cwd)

    def test_detect_context_with_cwd(self, demo_project):
        """API can detect context from specified cwd."""
        svc = QVService(demo_project)
        
        # Test with explicit cwd
        ctx = svc.detect_context(cwd=demo_project)
        assert ctx is not None
        assert ctx["project_root"] == demo_project.resolve()
        assert ctx["is_project"] is True

    def test_list_calculations_empty(self, demo_project):
        """API can list calculations (empty project)."""
        # Use static method (instance methods removed to avoid conflicts with static methods)
        calcs = QVService.list_calculations(demo_project)
        assert isinstance(calcs, list)
        assert len(calcs) == 0

    def test_list_steps_empty(self, demo_project):
        """API can list steps (empty calculation)."""
        # Create a minimal calculation
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        # Update project config
        import yaml
        svc = QVService(demo_project)
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        # List steps (should be empty) - use static method
        steps = QVService.list_steps(demo_project, "test-calc")
        assert isinstance(steps, list)
        assert len(steps) == 0

    def test_resolve_calculation_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent calculation."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Failed to resolve calculation"):
            svc.resolve_calculation_ref("nonexistent")

    def test_resolve_structure_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent structure."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Failed to resolve structure"):
            svc.resolve_structure_ref("nonexistent")

    def test_resolve_step_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent step."""
        svc = QVService(demo_project)
        
        # Create a minimal calculation first
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        import yaml
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        with pytest.raises(QVServiceError, match="Failed to resolve step"):
            svc.resolve_step_ref("test-calc", "nonexistent")

    def test_api_importable(self):
        """API module is importable."""
        from quantumvitas.api import QVService, QVServiceError
        assert QVService is not None
        assert QVServiceError is not None

    def test_instance_methods_exist(self, demo_project):
        """All required instance methods exist."""
        svc = QVService(demo_project)
        
        # Check that all required methods exist
        assert hasattr(svc, "detect_context")
        assert hasattr(svc, "load_project_config")
        assert hasattr(svc, "build_resource_index")
        assert hasattr(svc, "resolve_calculation_ref")
        assert hasattr(svc, "resolve_step_ref")
        assert hasattr(svc, "resolve_structure_ref")
        # list_calculations and list_steps are static methods (not instance methods)
        assert hasattr(QVService, "list_calculations")
        assert hasattr(QVService, "list_steps")
        
        # Check they are callable
        assert callable(svc.detect_context)
        assert callable(svc.load_project_config)
        assert callable(svc.build_resource_index)
        assert callable(svc.resolve_calculation_ref)
        assert callable(svc.resolve_step_ref)
        assert callable(svc.resolve_structure_ref)
        # New Chunk 1 wrappers
        assert hasattr(svc, "require_calculation_ref")
        assert hasattr(svc, "require_structure_ref")
        assert hasattr(svc, "require_step_ref")
        assert hasattr(svc, "make_structure_selector_resolver_ref")
        assert callable(svc.require_calculation_ref)
        assert callable(svc.require_structure_ref)
        assert callable(svc.require_step_ref)
        assert callable(svc.make_structure_selector_resolver_ref)
        assert callable(QVService.list_calculations)
        assert callable(QVService.list_steps)

    def test_require_calculation_ref_not_found(self, demo_project):
        """require_calculation_ref raises QVServiceError for non-existent calculation."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Calculation.*not found"):
            svc.require_calculation_ref("nonexistent")

    def test_require_structure_ref_not_found(self, demo_project):
        """require_structure_ref raises QVServiceError for non-existent structure."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Structure.*not found"):
            svc.require_structure_ref("nonexistent")

    def test_require_step_ref_not_found(self, demo_project):
        """require_step_ref raises QVServiceError for non-existent step."""
        svc = QVService(demo_project)
        
        # Create a minimal calculation first
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        import yaml
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        with pytest.raises(QVServiceError, match="Step.*not found"):
            svc.require_step_ref("test-calc", "nonexistent")

    def test_make_structure_selector_resolver_ref(self, demo_project):
        """make_structure_selector_resolver_ref returns a callable resolver."""
        svc = QVService(demo_project)
        
        resolver = svc.make_structure_selector_resolver_ref()
        assert callable(resolver)
        
        # Resolver should raise error for non-existent structure
        with pytest.raises(Exception):  # May be ResourceNotFoundError or QVServiceError
            resolver("nonexistent")

    def test_generate_resource_id(self, demo_project):
        """generate_resource_id generates unique IDs."""
        # Test static method
        id1 = QVService.generate_resource_id()
        id2 = QVService.generate_resource_id()
        
        assert isinstance(id1, str)
        assert isinstance(id2, str)
        assert len(id1) > 0
        assert len(id2) > 0
        # IDs should be unique
        assert id1 != id2
        
        # Test instance method (should also work)
        svc = QVService(demo_project)
        id3 = svc.generate_resource_id()
        assert isinstance(id3, str)
        assert len(id3) > 0
        # Should also be unique
        assert id3 != id1
        assert id3 != id2

    def test_ensure_relative_path(self, demo_project):
        """ensure_relative_path converts absolute paths to relative."""
        # Test static method
        abs_path = demo_project / "structures" / "test.json"
        rel_path = QVService.ensure_relative_path(abs_path, base=demo_project)
        
        assert isinstance(rel_path, str)
        assert not Path(rel_path).is_absolute()
        assert "structures" in rel_path
        
        # Test with already relative path
        rel_path2 = QVService.ensure_relative_path("structures/test.json", base=demo_project)
        assert isinstance(rel_path2, str)
        
        # Test instance method
        svc = QVService(demo_project)
        rel_path3 = svc.ensure_relative_path(abs_path, base=demo_project)
        assert isinstance(rel_path3, str)
        assert not Path(rel_path3).is_absolute()

    def test_generate_unique_name_and_slug(self):
        """generate_unique_name_and_slug generates unique names and slugs."""
        # Test static method
        name1, slug1 = QVService.generate_unique_name_and_slug(
            kind="structure",
            preferred_name="test",
            existing_slugs=[]
        )
        
        assert isinstance(name1, str)
        assert isinstance(slug1, str)
        assert name1 == "test"
        assert slug1 == "test"
        
        # Test with existing slug (should generate unique)
        name2, slug2 = QVService.generate_unique_name_and_slug(
            kind="structure",
            preferred_name="test",
            existing_slugs=["test"]
        )
        
        assert name2 != "test" or slug2 != "test"  # Should be unique
        assert isinstance(name2, str)
        assert isinstance(slug2, str)
    
    def test_read_structure(self, tmp_path):
        """read_structure reads structure files."""
        from pymatgen.core import Structure, Lattice
        
        # Create a simple structure file (CIF format)
        structure = Structure(Lattice.cubic(4.0), ["Si"], [[0, 0, 0]])
        cif_file = tmp_path / "test.cif"
        structure.to(filename=str(cif_file), fmt="cif")
        
        # Test static method
        read_struct = QVService.read_structure(cif_file)
        assert isinstance(read_struct, Structure)
        assert len(read_struct) == 1
        
        # Test instance method (should also work)
        svc = QVService.generate_resource_id()  # Just need a valid call
        # Actually, read_structure doesn't need project_root, so static is fine
    
    def test_write_structure(self, tmp_path):
        """write_structure writes structure files."""
        from pymatgen.core import Structure, Lattice
        
        structure = Structure(Lattice.cubic(4.0), ["Si"], [[0, 0, 0]])
        output_file = tmp_path / "output.cif"
        
        # Test static method
        QVService.write_structure(structure, output_file)
        
        assert output_file.exists()
        # Verify we can read it back
        read_struct = QVService.read_structure(output_file)
        assert isinstance(read_struct, Structure)
        assert len(read_struct) == 1
    
    def test_write_structure_argument_order(self, tmp_path, monkeypatch):
        """Regression test: write_structure must be called with (structure, filepath) order.
        
        This test ensures the wrapper calls the underlying function with correct argument order.
        It would catch bugs where arguments are swapped (e.g., write_structure(filepath, structure)).
        """
        from pymatgen.core import Structure, Lattice
        from unittest.mock import patch, MagicMock
        
        structure = Structure(Lattice.cubic(4.0), ["Si"], [[0, 0, 0]])
        output_file = tmp_path / "output.cif"
        
        # Mock the underlying function to verify argument order
        mock_write = MagicMock()
        
        # Patch the underlying function
        with patch('quantumvitas.io.write_structure', mock_write):
            QVService.write_structure(structure, output_file)
        
        # Verify the wrapper called the underlying function with correct order: (structure, filepath)
        assert mock_write.call_count == 1
        call_args = mock_write.call_args
        args = call_args[0]
        kwargs = call_args[1]
        
        # First arg should be the structure object (has .sites attribute)
        assert hasattr(args[0], 'sites'), f"First arg should be Structure, got {type(args[0])}"
        # Second arg should be the filepath (Path object)
        assert isinstance(args[1], Path), f"Second arg should be Path, got {type(args[1])}"
        assert args[1] == output_file
    
    def test_qe_model_enums_re_exported(self):
        """Test that QECardType and QEModule are re-exported from quantumvitas.api."""
        from quantumvitas.api import QECardType, QEModule
        
        # Verify they are the same classes as from the original module
        from quantumvitas.io.model import QECardType as OriginalQECardType, QEModule as OriginalQEModule
        
        assert QECardType is OriginalQECardType
        assert QEModule is OriginalQEModule
        
        # Verify enum values work
        assert QECardType.ATOMIC_SPECIES.value == "ATOMIC_SPECIES"
        assert QEModule.PW.value == "pw"
        assert QEModule.BANDS.value == "bands"
    
    def test_qe_parser_re_exported(self):
        """Test that QEInputParser is re-exported from quantumvitas.api."""
        from quantumvitas.api import QEInputParser
        
        # Verify it is the same class as from the original module
        from quantumvitas.io.parser.qe_parser import QEInputParser as OriginalQEInputParser
        
        assert QEInputParser is OriginalQEInputParser
        
        # Verify it has the expected class method
        assert hasattr(QEInputParser, 'parse_file')
        assert hasattr(QEInputParser, 'parse_string')
    
    def test_write_qe_input_file(self, tmp_path):
        """write_qe_input_file writes QE input files."""
        from quantumvitas.drivers.qe.io.model import QEInput, QENamelist, QECard, QECardType
        
        # Create minimal QE input
        control = QENamelist(name="CONTROL", parameters={"calculation": "scf"})
        system = QENamelist(name="SYSTEM", parameters={"ibrav": 0, "nat": 1, "ntyp": 1})
        atomic_species = QECard(
            card_type=QECardType.ATOMIC_SPECIES,
            option=None,
            data=[["Si", 28.085, "Si.pbe-n-rrkjus_psl.1.0.0.UPF"]]
        )
        qe_input = QEInput(namelists=[control, system], cards=[atomic_species])
        
        output_file = tmp_path / "test.pw.in"
        
        # Test static method
        QVService.write_qe_input_file(qe_input, output_file)
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "CONTROL" in content
        assert "calculation" in content
    
    def test_parse_scf_output_wrapper(self, tmp_path):
        """Test that parse_scf_output wrapper works."""
        from quantumvitas.analysis.parsers import SCFResult
        
        # Create a minimal SCF output file
        scf_file = tmp_path / "scf.out"
        scf_file.write_text("""
!    total energy              =     -100.12345678 Ry
     Fermi energy is    5.6789 ev
""")
        
        result = QVService.parse_scf_output(scf_file)
        assert isinstance(result, SCFResult)
        assert result.total_energy is not None
    
    def test_parse_dos_data_wrapper(self, tmp_path):
        """Test that parse_dos_data wrapper works."""
        from quantumvitas.analysis.parsers import DOSData
        
        # Create a minimal DOS file
        dos_file = tmp_path / "dos.dat"
        dos_file.write_text("""
#  E (eV)   dos(E)     Int dos(E) EFermi =    5.6789 eV
  0.0  1.0  0.0
  1.0  2.0  1.0
""")
        
        result = QVService.parse_dos_data(dos_file)
        assert isinstance(result, DOSData)
        assert len(result.energies) > 0
    
    def test_parse_bands_gnu_wrapper(self, tmp_path):
        """Test that parse_bands_gnu wrapper works."""
        from quantumvitas.analysis.parsers import BandStructureData
        
        # Create a minimal bands.dat.gnu file
        bands_file = tmp_path / "bands.dat.gnu"
        bands_file.write_text("""
0.0  0.0
0.1  0.1

0.0  0.2
0.1  0.3
""")
        
        result = QVService.parse_bands_gnu(bands_file)
        assert isinstance(result, BandStructureData)
        assert result.n_bands > 0
    
    def test_dos_data_re_exported(self):
        """Test that DOSData is re-exported from quantumvitas.api."""
        from quantumvitas.api import DOSData
        
        # Verify it is the same class as from the original module
        from quantumvitas.analysis.parsers import DOSData as OriginalDOSData
        
        assert DOSData is OriginalDOSData
        
        # Verify it can be instantiated
        dos_data = DOSData(
            energies=[0.0, 1.0],
            dos=[1.0, 2.0],
            idos=[0.0, 1.0],
            fermi_energy=0.5
        )
        assert dos_data.fermi_energy == 0.5
    
    def test_plot_dos_wrapper(self, tmp_path, monkeypatch):
        """Test that plot_dos wrapper works."""
        from quantumvitas.analysis.parsers import DOSData
        import numpy as np
        
        # Create minimal DOS data
        dos_data = DOSData(
            energies=np.array([0.0, 1.0, 2.0]),
            dos=np.array([1.0, 2.0, 1.5]),
            idos=np.array([0.0, 1.0, 2.0]),
            fermi_energy=1.0
        )
        
        # Call wrapper - should return (fig, ax) tuple
        fig, ax = QVService.plot_dos(dos_data, shift_fermi=False)
        assert fig is not None
        assert ax is not None
    
    def test_plot_bands_wrapper(self, tmp_path, monkeypatch):
        """Test that plot_bands wrapper works."""
        from quantumvitas.analysis.parsers import BandStructureData
        import numpy as np
        
        # Create minimal band data
        band_data = BandStructureData(
            k_distances=np.array([0.0, 1.0]),
            energies=np.array([[0.0, 1.0], [0.5, 1.5]]),
            fermi_energy=1.0,
            high_symmetry_points=[]
        )
        
        # Call wrapper - should return (fig, ax) tuple
        fig, ax = QVService.plot_bands(band_data, shift_fermi=False)
        assert fig is not None
        assert ax is not None
    
    def test_plot_scf_convergence_wrapper(self, tmp_path, monkeypatch):
        """Test that plot_scf_convergence wrapper works."""
        from quantumvitas.analysis.parsers import SCFResult, SCFIteration
        
        # Create minimal SCF result
        scf_result = SCFResult(
            iterations=[
                SCFIteration(iteration=1, total_energy=-100.0, scf_accuracy=1e-3),
                SCFIteration(iteration=2, total_energy=-100.1, scf_accuracy=1e-5),
            ],
            converged=True,
            total_energy=-100.1,
            fermi_energy=5.0
        )
        
        # Call wrapper - should return (fig, ax) tuple
        fig, ax = QVService.plot_scf_convergence(scf_result)
        assert fig is not None
        assert ax is not None
    
    def test_save_figure_wrapper(self, tmp_path):
        """Test that save_figure wrapper works."""
        import matplotlib.pyplot as plt
        
        # Create a minimal figure
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [0, 1, 2])
        
        # Save using wrapper
        output_file = tmp_path / "test_plot.png"
        saved_paths = QVService.save_figure(fig, output_file)
        
        assert len(saved_paths) > 0
        assert output_file.exists()
        
        plt.close(fig)
    
    def test_structure_step_spec_re_exported(self):
        """Test that StructureStepSpec is re-exported from quantumvitas.api."""
        from quantumvitas.api import StructureStepSpec
        
        # Verify it is the same class as from the original module
        from quantumvitas.calculation.structure_steps import StructureStepSpec as OriginalStructureStepSpec
        
        assert StructureStepSpec is OriginalStructureStepSpec
        
        # Verify it has the expected class method
        assert hasattr(StructureStepSpec, 'from_yaml')
    
    def test_generate_qe_input_from_structure_wrapper(self, tmp_path):
        """Test that generate_qe_input_from_structure wrapper works."""
        from pymatgen.core import Structure, Lattice
        
        # Create a minimal structure
        structure = Structure(Lattice.cubic(4.0), ["Si"], [[0, 0, 0]])
        
        # Call wrapper
        qe_input = QVService.generate_qe_input_from_structure(structure, "scf")
        assert qe_input is not None
        assert hasattr(qe_input, 'get_namelist')
    
    def test_generate_qe_input_from_spec_wrapper(self, tmp_path):
        """Test that generate_qe_input_from_spec wrapper works."""
        from pymatgen.core import Structure, Lattice
        from quantumvitas.api import StructureStepSpec
        from quantumvitas.core.resources import ResourceMeta, generate_resource_id
        
        # Create a minimal structure
        structure = Structure(Lattice.cubic(4.0), ["Si"], [[0, 0, 0]])
        
        # Create a minimal spec with species_overrides
        spec = StructureStepSpec(
            meta=ResourceMeta(
                id=generate_resource_id(),
                name="test_step",
                slug="test-step",
                path="steps/test-step",
                kind="step",
            ),
            structure="test",
            step_type="scf",
            species_overrides={"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "mass": 28.085}},
        )
        
        # Call wrapper with species_map
        species_map = {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF", "mass": 28.085}}
        qe_input, overrides = QVService.generate_qe_input_from_spec(
            structure, spec, species_map=species_map
        )
        assert qe_input is not None
        assert isinstance(overrides, list)
    
    def test_materialize_step_spec_wrapper(self, monkeypatch, tmp_path):
        """Test that materialize_step_spec wrapper passes through to underlying function."""
        from pathlib import Path
        from quantumvitas.api import QVService
        
        # Track calls to the underlying function
        called = {}
        
        def fake_materialize_step_spec(
            spec,
            *,
            output_dir,
            spec_path=None,
            calculation_dir=None,
            project=None,
            input_name=None,
            project_root=None,
        ):
            """Fake implementation that records arguments and returns sentinel values."""
            called["spec"] = spec
            called["output_dir"] = output_dir
            called["spec_path"] = spec_path
            called["calculation_dir"] = calculation_dir
            called["project"] = project
            called["input_name"] = input_name
            called["project_root"] = project_root
            # Return sentinel values to verify wrapper returns them
            fake_input_path = Path(output_dir) / "fake_input.in"
            fake_spec = {"sentinel": True, "meta": {"id": "test"}}
            return fake_input_path, fake_spec
        
        # Mock the underlying function
        import quantumvitas.calculation.structure_steps as structure_steps_module
        monkeypatch.setattr(
            structure_steps_module,
            "materialize_step_spec",
            fake_materialize_step_spec,
        )
        
        # Create minimal test files
        step_dir = tmp_path / "steps" / "test_step"
        step_dir.mkdir(parents=True)
        step_yaml = step_dir / "step.yaml"
        step_yaml.write_text("meta: {}\n")  # Minimal content, won't be parsed by fake
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Call wrapper
        generated_input, materialized_spec = QVService.materialize_step_spec(
            spec=str(step_yaml),
            output_dir=output_dir,
            calculation_dir=calc_dir,
            project_root=tmp_path,
        )
        
        # Verify wrapper returned what underlying function returned
        assert generated_input == output_dir / "fake_input.in"
        assert materialized_spec == {"sentinel": True, "meta": {"id": "test"}}
        
        # Verify wrapper passed through arguments correctly
        assert called["spec"] == str(step_yaml)
        assert Path(called["output_dir"]) == output_dir
        assert called["calculation_dir"] == calc_dir
        assert Path(called["project_root"]) == tmp_path
    
    def test_find_calculation_raw_dir_wrapper(self, tmp_path):
        """Test that find_calculation_raw_dir wrapper works."""
        from pathlib import Path
        from quantumvitas.api import QVService
        
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Call wrapper
        raw_dir = QVService.find_calculation_raw_dir(calc_dir)
        
        # Verify it returns the expected path
        assert raw_dir == calc_dir / "raw"
        
        # Test with custom working_dir_name
        raw_dir_custom = QVService.find_calculation_raw_dir(calc_dir, working_dir_name="work")
        assert raw_dir_custom == calc_dir / "work"
    
    def test_find_calculation_results_dir_wrapper(self, tmp_path):
        """Test that find_calculation_results_dir wrapper works."""
        from pathlib import Path
        from quantumvitas.api import QVService
        
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        # Call wrapper
        results_dir = QVService.find_calculation_results_dir(calc_dir)
        
        # Verify it returns the expected path
        assert results_dir == calc_dir / "results"
        
        # Test with custom results_dir_name
        results_dir_custom = QVService.find_calculation_results_dir(calc_dir, results_dir_name="output")
        assert results_dir_custom == calc_dir / "output"
    
    def test_find_band_analysis_files_wrapper(self, monkeypatch, tmp_path):
        """Test that find_band_analysis_files wrapper works."""
        from pathlib import Path
        from quantumvitas.api import QVService, BandAnalysisFiles
        
        # Track calls to the underlying function
        called = {}
        
        def fake_find_band_analysis_files(directory, prefix=None):
            """Fake implementation that records arguments and returns sentinel values."""
            called["directory"] = directory
            called["prefix"] = prefix
            # Return a fake BandAnalysisFiles instance
            result = BandAnalysisFiles()
            result.bands_gnu = directory / "test.bands.dat.gnu"
            return result
        
        # Mock the underlying function
        import quantumvitas.calculation.naming as naming_module
        monkeypatch.setattr(
            naming_module,
            "find_band_analysis_files",
            fake_find_band_analysis_files,
        )
        
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        
        # Call wrapper
        found_files = QVService.find_band_analysis_files(search_dir)
        
        # Verify wrapper returned what underlying function returned
        assert isinstance(found_files, BandAnalysisFiles)
        assert found_files.bands_gnu == search_dir / "test.bands.dat.gnu"
        
        # Verify wrapper passed through arguments correctly
        assert Path(called["directory"]) == search_dir
        assert called["prefix"] is None
        
        # Test with prefix
        found_files_with_prefix = QVService.find_band_analysis_files(search_dir, prefix="test")
        assert called["prefix"] == "test"
    
    def test_get_default_step_params_wrapper(self):
        """Test that get_default_step_params wrapper works."""
        from quantumvitas.api import QVService
        
        # Test with a known step type
        defaults = QVService.get_default_step_params("scf")
        
        # Verify it returns a dict with expected keys
        assert isinstance(defaults, dict)
        assert "parameters" in defaults
        assert "cards" in defaults
        assert "species_overrides" in defaults
        
        # Verify it has some expected content for scf
        assert "CONTROL" in defaults["parameters"]
        assert defaults["parameters"]["CONTROL"]["calculation"] == "scf"
        
        # Test with unknown step type (should return empty dicts)
        unknown_defaults = QVService.get_default_step_params("unknown_step_type")
        assert isinstance(unknown_defaults, dict)
        assert "parameters" in unknown_defaults
    
    def test_configure_species_map_wrapper(self, monkeypatch, tmp_path):
        """Test that configure_species_map wrapper works by mocking underlying call."""
        from quantumvitas.api import QVService
        import quantumvitas.calculation.species_config as species_config_module

        # Track calls to the underlying function
        called = {}
        fake_species_map = {
            "Si": {"mass": 28.0855, "pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"},
            "O": {"mass": 15.999, "pseudopot": "O.pbe-n-rrkjus_psl.1.0.0.UPF"},
        }

        def fake_configure_species_map(
            project_root, calculation, *, from_qe_input=None, set_entries=None, merge=True
        ):
            called["project_root"] = project_root
            called["calculation"] = calculation
            called["from_qe_input"] = from_qe_input
            called["set_entries"] = set_entries
            called["merge"] = merge
            return fake_species_map

        # Mock the underlying function
        monkeypatch.setattr(
            species_config_module,
            "configure_species_map",
            fake_configure_species_map,
        )

        # Create minimal project structure
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text("project:\n  name: test\nstructures: []\ncalculations: []\n")

        # Call wrapper
        result = QVService.configure_species_map(
            project_root=project_root,
            calculation="test_calc",
            from_qe_input=None,
            set_entries=[("Si", 28.0855, "Si.pbe-n-rrkjus_psl.1.0.0.UPF")],
            merge=True,
        )

        # Assertions
        assert result == fake_species_map
        assert called["project_root"] == project_root.resolve()
        assert called["calculation"] == "test_calc"
        assert called["from_qe_input"] is None
        assert called["set_entries"] == [("Si", 28.0855, "Si.pbe-n-rrkjus_psl.1.0.0.UPF")]
        assert called["merge"] is True
    
    def test_configure_species_map_wrapper_raises_qvservice_error(self, monkeypatch, tmp_path):
        """Test that configure_species_map wrapper converts ValueError to QVServiceError."""
        from quantumvitas.api import QVService, QVServiceError
        import quantumvitas.calculation.species_config as species_config_module

        def fake_configure_species_map(*args, **kwargs):
            raise ValueError("Calculation not found")

        monkeypatch.setattr(
            species_config_module,
            "configure_species_map",
            fake_configure_species_map,
        )

        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text("project:\n  name: test\nstructures: []\ncalculations: []\n")

        with pytest.raises(QVServiceError, match="Calculation not found"):
            QVService.configure_species_map(
                project_root=project_root,
                calculation="nonexistent",
                set_entries=[("Si", 28.0855, "Si.UPF")],
            )
    
    def test_detect_runtime_control_keys_wrapper(self):
        """Test that detect_runtime_control_keys wrapper works."""
        parameters = {
            "CONTROL": {
                "prefix": "test",
                "outdir": "/tmp",
            },
            "SYSTEM": {
                "ecutwfc": 30.0,
            },
        }
        
        keys = QVService.detect_runtime_control_keys(parameters)
        assert isinstance(keys, list)
        assert "prefix" in keys
        assert "outdir" in keys
    
    def test_parameter_override_re_export(self):
        """Test that ParameterOverride is re-exported from api."""
        from quantumvitas.api import ParameterOverride
        
        # Test that we can create a ParameterOverride
        override = ParameterOverride(
            name="ecutwfc",
            value=30.0,
            section="SYSTEM",
        )
        assert override.name == "ecutwfc"
    
    def test_step_re_export(self):
        """Test that Step is re-exported from quantumvitas.api."""
        from quantumvitas.api import Step
        from quantumvitas.api import ResourceMeta, StepMode
        
        # Verify it is the same class as from the original module
        from quantumvitas.calculation.step import Step as OriginalStep
        
        assert Step is OriginalStep
        
        # Verify it can be instantiated (requires meta and input_file)
        meta = ResourceMeta(
            id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            name="test_step",
            slug="test-step",
            path="steps/test_step",
            kind="step",
        )
        step = Step(
            meta=meta,
            input_file=Path("/tmp/test.in"),
            engine="qe",
            step_type="scf",
            mode=StepMode.NORMAL,
        )
        assert step.meta == meta
        assert step.input_file == Path("/tmp/test.in")
        assert step.engine == "qe"
        assert step.step_type == "scf"
    
    def test_calculation_re_export(self):
        """Test that Calculation class is re-exported from api."""
        from quantumvitas.api import Calculation
        from quantumvitas.calculation.calculation import Calculation as OriginalCalculation
        
        # Test that it's the same class
        assert Calculation is OriginalCalculation
        
        # Test that it has the from_yaml classmethod
        assert hasattr(Calculation, "from_yaml")
        assert callable(Calculation.from_yaml)
    
    def test_generate_kpath_wrapper(self, monkeypatch):
        """Test that generate_kpath wrapper works by mocking underlying call."""
        from quantumvitas.api import QVService
        import quantumvitas.analysis.kpath as kpath_module
        
        # Track calls to the underlying function
        called = {}
        
        # Create a fake KPathResult-like object
        class FakeKPathResult:
            def __init__(self):
                self.segments = []
                self.labels = ["Γ", "X"]
                self.coords = [(0, 0, 0), (0.5, 0, 0)]
                self.lattice_type = "cubic"
                self.spacegroup_symbol = "Fm-3m"
                self.spacegroup_number = 225
        
        fake_result = FakeKPathResult()
        
        def fake_generate_kpath(structure, points_per_segment=20, path_type="hinuma"):
            called["structure"] = structure
            called["points_per_segment"] = points_per_segment
            called["path_type"] = path_type
            return fake_result
        
        # Mock the underlying function
        monkeypatch.setattr(kpath_module, "generate_kpath", fake_generate_kpath)
        
        # Create a minimal fake structure (just needs to be an object)
        fake_structure = type("FakeStructure", (), {})()
        
        # Call wrapper
        result = QVService.generate_kpath(
            structure=fake_structure,
            points_per_segment=30,
            path_type="seekpath",
        )
        
        # Assertions
        assert result == fake_result
        assert called["structure"] == fake_structure
        assert called["points_per_segment"] == 30
        assert called["path_type"] == "seekpath"
    
    def test_generate_kpath_wrapper_raises_qvservice_error(self, monkeypatch):
        """Test that generate_kpath wrapper converts exceptions to QVServiceError."""
        from quantumvitas.api import QVService, QVServiceError
        import quantumvitas.analysis.kpath as kpath_module
        
        def fake_generate_kpath(*args, **kwargs):
            raise RuntimeError("pymatgen not available")
        
        monkeypatch.setattr(kpath_module, "generate_kpath", fake_generate_kpath)
        
        fake_structure = type("FakeStructure", (), {})()
        
        with pytest.raises(QVServiceError, match="pymatgen not available"):
            QVService.generate_kpath(fake_structure)
    
    def test_needs_alat_preservation_wrapper(self, monkeypatch):
        """Test that needs_alat_preservation wrapper works by mocking underlying call."""
        from quantumvitas.api import QVService
        import quantumvitas.calculation.importers as importers_module
        
        # Track calls to the underlying function
        called = {}
        
        def fake_needs_alat_preservation(qe_input):
            called["qe_input"] = qe_input
            return True
        
        # Mock the underlying function
        monkeypatch.setattr(importers_module, "_needs_alat_preservation", fake_needs_alat_preservation)
        
        # Create a minimal fake QEInput (just needs to be an object)
        fake_qe_input = type("FakeQEInput", (), {})()
        
        # Call wrapper
        result = QVService.needs_alat_preservation(fake_qe_input)
        
        # Assertions
        assert result is True
        assert called["qe_input"] == fake_qe_input
    
    def test_extract_alat_bohr_wrapper(self, monkeypatch):
        """Test that extract_alat_bohr wrapper works by mocking underlying call."""
        from quantumvitas.api import QVService
        import quantumvitas.calculation.importers as importers_module
        
        # Track calls to the underlying function
        called = {}
        fake_alat = 10.5
        
        def fake_extract_alat_bohr(qe_input):
            called["qe_input"] = qe_input
            return fake_alat
        
        # Mock the underlying function
        monkeypatch.setattr(importers_module, "_extract_alat_bohr", fake_extract_alat_bohr)
        
        # Create a minimal fake QEInput (just needs to be an object)
        fake_qe_input = type("FakeQEInput", (), {})()
        
        # Call wrapper
        result = QVService.extract_alat_bohr(fake_qe_input)
        
        # Assertions
        assert result == fake_alat
        assert called["qe_input"] == fake_qe_input
    
    def test_build_step_spec_from_qe_input_wrapper(self, monkeypatch, tmp_path):
        """Test that build_step_spec_from_qe_input wrapper works by mocking underlying call."""
        from pathlib import Path
        from quantumvitas.api import QVService
        import quantumvitas.calculation.importers as importers_module
        
        # Track calls to the underlying function
        called = {}
        
        # Create a fake StepImportResult-like object
        class FakeStepImportResult:
            def __init__(self):
                self.step_id = "test_step_123"
                self.structure_id = "test_struct_456"
                self.step_type = "scf"
                self.parameters = {"SYSTEM": {"ecutwfc": 30.0}}
                self.spec = None  # Would be StructureStepSpec in real usage
                self.spec_path = Path("/fake/step.yaml")
                self.structure_path = Path("/fake/structure.json")
        
        fake_result = FakeStepImportResult()
        
        def fake_build_step_spec_from_qe_input(
            input_file,
            *,
            destination_dir,
            structure_dir=None,
            step_id=None,
            structure_id=None,
            reference_structure_by="path",
            apply_defaults=False,
        ):
            called["input_file"] = input_file
            called["destination_dir"] = destination_dir
            called["structure_dir"] = structure_dir
            called["step_id"] = step_id
            called["structure_id"] = structure_id
            called["reference_structure_by"] = reference_structure_by
            called["apply_defaults"] = apply_defaults
            return fake_result
        
        # Mock the underlying function
        monkeypatch.setattr(importers_module, "build_step_spec_from_qe_input", fake_build_step_spec_from_qe_input)
        
        # Create test paths
        input_file = tmp_path / "test.in"
        input_file.write_text("&CONTROL\n  calculation = 'scf'\n/\n")
        destination_dir = tmp_path / "dest"
        destination_dir.mkdir()
        structure_dir = tmp_path / "structures"
        structure_dir.mkdir()
        
        # Call wrapper
        result = QVService.build_step_spec_from_qe_input(
            input_file=input_file,
            destination_dir=destination_dir,
            structure_dir=structure_dir,
            step_id="custom_step",
            structure_id="custom_struct",
            reference_structure_by="id",
            apply_defaults=True,
        )
        
        # Assertions
        assert result == fake_result
        assert result.step_id == "test_step_123"
        assert called["input_file"] == input_file
        assert called["destination_dir"] == destination_dir
        assert called["structure_dir"] == structure_dir
        assert called["step_id"] == "custom_step"
        assert called["structure_id"] == "custom_struct"
        assert called["reference_structure_by"] == "id"
        assert called["apply_defaults"] is True
    
    def test_visualize_structure_direct_wrapper(self, monkeypatch):
        """Test that visualize_structure_direct wrapper works by mocking underlying call."""
        from pathlib import Path
        from quantumvitas.api import QVService
        import quantumvitas.analysis.structure_viz as structure_viz_module
        from pymatgen.core import Structure, Lattice
        
        # Track calls to the underlying function
        called = {}
        
        # Create a fake StructureVisualizationResult-like object
        class FakeStructureVisualizationResult:
            def __init__(self):
                self.output_path = Path("/fake/output.png")
                self.n_atoms = 8
                self.n_bonds = 12
                self.supercell = (2, 2, 2)
                self.repeat_boundary = True
        
        fake_result = FakeStructureVisualizationResult()
        
        def fake_visualize_structure(
            structure,
            output_path=None,
            supercell=(1, 1, 1),
            repeat_boundary=False,
            show=False,
            plot_format="png",
            **kwargs,
        ):
            called["structure"] = structure
            called["output_path"] = output_path
            called["supercell"] = supercell
            called["repeat_boundary"] = repeat_boundary
            called["show"] = show
            called["plot_format"] = plot_format
            called["kwargs"] = kwargs
            return fake_result
        
        # Mock the underlying function
        monkeypatch.setattr(structure_viz_module, "visualize_structure", fake_visualize_structure)
        
        # Create a minimal fake structure
        fake_structure = Structure(Lattice.cubic(4), ["Si"], [[0, 0, 0]])
        fake_output_path = Path("/fake/output.png")
        fake_supercell = (2, 2, 2)
        
        # Call wrapper
        result = QVService.visualize_structure_direct(
            structure=fake_structure,
            output_path=fake_output_path,
            supercell=fake_supercell,
            repeat_boundary=True,
            show=False,
            plot_format="svg",
            extra_option="test",
        )
        
        # Assertions
        assert result == fake_result
        assert called["structure"] == fake_structure
        assert called["output_path"] == fake_output_path
        assert called["supercell"] == fake_supercell
        assert called["repeat_boundary"] is True
        assert called["show"] is False
        assert called["plot_format"] == "svg"
        assert called["kwargs"]["extra_option"] == "test"
    
    def test_apply_card_overrides_to_qe_input_wrapper(self):
        """Test that apply_card_overrides_to_qe_input wrapper works."""
        from quantumvitas.api import QVService
        from quantumvitas.io.parser.qe_parser import QEInputParser
        
        # Create a minimal QE input
        input_text = """&CONTROL
  calculation = 'scf'
/
&SYSTEM
  ecutwfc = 30.0
/
ATOMIC_SPECIES
 Si  28.085  Si.UPF
ATOMIC_POSITIONS
 Si  0.0  0.0  0.0
K_POINTS
 1 1
 0.0 0.0 0.0 1.0
"""
        qe_input = QEInputParser.parse_string(input_text)
        
        # Apply card overrides
        overrides = {
            "K_POINTS": {
                "option": "automatic",
                "kpoints": [[4, 4, 4, 0, 0, 0]],
            }
        }
        
        # Should not raise
        QVService.apply_card_overrides_to_qe_input(qe_input, overrides)
        
        # Verify override was applied (check that K_POINTS card exists)
        k_points_cards = [c for c in qe_input.cards if c.card_type.name == "K_POINTS"]
        assert len(k_points_cards) > 0
    
    def test_apply_species_overrides_to_qe_input_wrapper(self):
        """Test that apply_species_overrides_to_qe_input wrapper works."""
        from quantumvitas.api import QVService
        from quantumvitas.io.parser.qe_parser import QEInputParser
        
        # Create a minimal QE input
        input_text = """&CONTROL
  calculation = 'scf'
/
&SYSTEM
  ecutwfc = 30.0
/
ATOMIC_SPECIES
 Si  28.085  Si.UPF
ATOMIC_POSITIONS
 Si  0.0  0.0  0.0
K_POINTS
 1 1
 0.0 0.0 0.0 1.0
"""
        qe_input = QEInputParser.parse_string(input_text)
        
        # Apply species overrides
        overrides = {
            "Si": {
                "pseudo": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
            }
        }
        
        # Should not raise
        QVService.apply_species_overrides_to_qe_input(qe_input, overrides)
    
    def test_detect_project_root_wrapper(self, demo_project):
        """Test that detect_project_root wrapper works."""
        from quantumvitas.api import QVService
        
        # Should detect project root
        detected = QVService.detect_project_root(start=demo_project)
        assert detected == demo_project.resolve()
        
        # Should return None for non-project directory
        non_project = demo_project.parent / "non_project"
        non_project.mkdir()
        detected = QVService.detect_project_root(start=non_project)
        assert detected is None

