"""Unit tests for CP2K engine."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import time

from qmatsuite.engine.cp2k_engine import Cp2kEngine
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.engine.base import EngineConfig
from qmatsuite.workflow.registry import get_registry
from qmatsuite.execution.latest_selector import find_latest_by_mtime
from qmatsuite.execution.preflight import PreflightChecker, PreflightRequirement


class TestCp2kEngine:
    """Test Cp2kEngine class."""
    
    def test_engine_name(self):
        """Test engine name is correct."""
        engine = Cp2kEngine()
        assert engine.name == "cp2k"
    
    def test_supported_presets(self):
        """Test supported_presets returns correct values."""
        engine = Cp2kEngine()
        presets = engine.supported_presets
        assert isinstance(presets, list)
        assert "precision" in presets
        assert "magnetism" in presets
    
    def test_materialize_inputs_implemented(self):
        """Test materialize_inputs is implemented."""
        engine = Cp2kEngine()
        assert hasattr(engine, 'materialize_inputs')
        assert callable(engine.materialize_inputs)
    
    def test_run_step_implemented(self):
        """Test run_step is implemented."""
        engine = Cp2kEngine()
        assert hasattr(engine, 'run_step')
        assert callable(engine.run_step)


class TestCp2kEngineRegistry:
    """Test CP2K engine registration."""
    
    def test_cp2k_in_default_registry(self):
        """Test CP2K engine is in default registry."""
        registry = create_default_registry()
        assert registry.has("cp2k")
        assert "cp2k" in registry.list_engines()
    
    def test_get_cp2k_engine(self):
        """Test getting CP2K engine from registry."""
        registry = create_default_registry()
        engine = registry.get("cp2k")
        assert isinstance(engine, Cp2kEngine)
        assert engine.name == "cp2k"


class TestCp2kStepTypes:
    """Test CP2K step type registration.

    Uses get_for_engine(gen_type, engine) per constitution: registry.get() takes GEN only.
    """

    def test_cp2k_scf_registered(self):
        """Test cp2k_scf step type is registered."""
        registry = get_registry()
        spec = registry.get_for_engine("scf", "cp2k")
        assert spec is not None
        assert spec.engine == "cp2k"
        assert spec.step_type_spec == "cp2k_scf"
        assert spec.step_type_gen == "scf"
        assert spec.supports_incremental_skip is True

    def test_cp2k_relax_registered(self):
        """Test cp2k_relax step type is registered."""
        registry = get_registry()
        spec = registry.get_for_engine("relax", "cp2k")
        assert spec is not None
        assert spec.engine == "cp2k"
        assert spec.step_type_spec == "cp2k_relax"
        assert spec.step_type_gen == "relax"
        assert spec.is_structure_transform is True
        assert spec.supports_incremental_skip is True

    def test_cp2k_md_registered(self):
        """Test cp2k_md step type is registered."""
        registry = get_registry()
        spec = registry.get_for_engine("md", "cp2k")
        assert spec is not None
        assert spec.engine == "cp2k"
        assert spec.step_type_spec == "cp2k_md"
        assert spec.step_type_gen == "md"
        assert spec.supports_incremental_skip is False  # CRITICAL: MD skip disabled
    
    def test_list_cp2k_step_types(self):
        """Test listing CP2K step types."""
        registry = get_registry()
        cp2k_types = registry.list_by_engine_machine("cp2k")
        assert "cp2k_scf" in cp2k_types
        assert "cp2k_relax" in cp2k_types
        assert "cp2k_md" in cp2k_types


class TestFindLatestByMtime:
    """Test mtime-based selection for artifacts."""
    
    def test_find_latest_by_mtime_single_file(self, tmp_path):
        """Test finding single file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        result = find_latest_by_mtime(tmp_path, "test.txt")
        assert result == test_file
    
    def test_find_latest_by_mtime_multiple_files(self, tmp_path):
        """Test finding latest file by mtime."""
        # Create files with delays to ensure different mtimes
        file1 = tmp_path / "cp2k_calc-1.restart"
        file1.write_text("old")
        time.sleep(0.01)  # Small delay
        
        file2 = tmp_path / "cp2k_calc-5.restart"
        file2.write_text("newer")
        time.sleep(0.01)
        
        file3 = tmp_path / "cp2k_calc-10.restart"
        file3.write_text("newest")
        
        result = find_latest_by_mtime(tmp_path, "cp2k_calc-*.restart")
        assert result == file3  # Should be the newest by mtime
    
    def test_find_latest_by_mtime_no_matches(self, tmp_path):
        """Test finding latest when no matches."""
        result = find_latest_by_mtime(tmp_path, "nonexistent-*.txt")
        assert result is None
    
    def test_find_latest_by_mtime_pattern(self, tmp_path):
        """Test finding latest with glob pattern."""
        file1 = tmp_path / "cp2k_calc-pos-1.xyz"
        file1.write_text("traj1")
        time.sleep(0.01)
        
        file2 = tmp_path / "cp2k_calc-pos-2.xyz"
        file2.write_text("traj2")
        
        result = find_latest_by_mtime(tmp_path, "cp2k_calc-pos-*.xyz")
        assert result == file2


class TestPreflightChecker:
    """Test preflight requirement checking."""
    
    def test_preflight_check_passes(self, tmp_path):
        """Test preflight check when artifact exists."""
        from qmatsuite.execution.preflight import PreflightChecker, PreflightRequirement
        
        # Create step directory and artifact file
        step_dir = tmp_path / "test123"
        step_dir.mkdir()
        artifact_file = step_dir / "cp2k_calc-RESTART.wfn"
        artifact_file.write_text("dummy")
        
        # Create mock calculation
        mock_calc = MagicMock()
        mock_calc.io.raw_dir = tmp_path
        mock_calc.steps = []
        
        # Create mock step
        mock_step = MagicMock()
        mock_step.meta.ulid = "test123"
        mock_step.meta = MagicMock()
        mock_step.meta.ulid = "test123"
        
        # Create requirement
        req = PreflightRequirement(
            artifact_type="wfn",
            pattern="cp2k_calc-RESTART.wfn",
            source_step="test123",
            required=True,
            message="WFN file required",
        )
        
        checker = PreflightChecker()
        errors = checker.check([req], mock_calc, mock_step)
        assert len(errors) == 0
    
    def test_preflight_check_fails_missing(self, tmp_path):
        """Test preflight check fails when artifact missing."""
        from qmatsuite.execution.preflight import PreflightChecker, PreflightRequirement
        
        mock_calc = MagicMock()
        mock_calc.io.raw_dir = tmp_path
        mock_calc.steps = []
        
        mock_step = MagicMock()
        mock_step.meta.ulid = "test123"
        mock_step.meta = MagicMock()
        mock_step.meta.ulid = "test123"
        
        req = PreflightRequirement(
            artifact_type="wfn",
            pattern="cp2k_calc-RESTART.wfn",
            source_step="test123",
            required=True,
            message="WFN file required in {source_dir}",
        )
        
        checker = PreflightChecker()
        errors = checker.check([req], mock_calc, mock_step)
        assert len(errors) == 1
        assert "WFN file required" in errors[0].message


class TestCp2kInputGeneration:
    """Test CP2K input file generation."""
    
    def test_cp2k_input_generation_with_cell(self, tmp_path):
        """Test input file generation includes CELL print."""
        from qmatsuite.engine.cp2k_writer import write_cp2k_input
        from qmatsuite.calculation.structure_steps import StructureStepSpec
        from qmatsuite.core.resources import ResourceMeta
        from pymatgen.core import Structure, Lattice
        
        # Create simple structure
        lattice = Lattice.cubic(5.431)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        # Create step spec for relax
        step_spec = StructureStepSpec(
            meta=ResourceMeta(ulid="test123",
                name="test",
                slug="test",
                kind="step",
                path=tmp_path / "test.step.yaml",
            ),
            structure="test",
            step_type_spec="cp2k_relax",
            parameters={
                "functional": "PBE",
                "cutoff": 300,
            },
        )
        
        output_path = tmp_path / "input.inp"
        write_cp2k_input(step_spec, structure, output_path)
        
        content = output_path.read_text()
        
        # Check for required sections
        assert "&GLOBAL" in content
        assert "PROJECT cp2k_calc" in content
        assert "RUN_TYPE GEO_OPT" in content
        assert "&MOTION" in content
        assert "&CELL" in content  # CRITICAL: CELL print must be present
        assert "&END CELL" in content
        assert "&FORCE_EVAL" in content
        assert "&SUBSYS" in content
    
    def test_cp2k_input_scf_no_motion(self, tmp_path):
        """Test SCF input doesn't have MOTION section."""
        from qmatsuite.engine.cp2k_writer import write_cp2k_input
        from qmatsuite.calculation.structure_steps import StructureStepSpec
        from qmatsuite.core.resources import ResourceMeta
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.431)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        step_spec = StructureStepSpec(
            meta=ResourceMeta(ulid="test123",
                name="test",
                slug="test",
                kind="step",
                path=tmp_path / "test.step.yaml",
            ),
            structure="test",
            step_type_spec="cp2k_scf",
            parameters={"functional": "PBE"},
        )
        
        output_path = tmp_path / "input.inp"
        write_cp2k_input(step_spec, structure, output_path)
        
        content = output_path.read_text()
        assert "RUN_TYPE ENERGY_FORCE" in content
        assert "&MOTION" not in content  # SCF should not have MOTION
    
    def test_cp2k_input_md_has_cell(self, tmp_path):
        """Test MD input has CELL print."""
        from qmatsuite.engine.cp2k_writer import write_cp2k_input
        from qmatsuite.calculation.structure_steps import StructureStepSpec
        from qmatsuite.core.resources import ResourceMeta
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.431)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        step_spec = StructureStepSpec(
            meta=ResourceMeta(ulid="test123",
                name="test",
                slug="test",
                kind="step",
                path=tmp_path / "test.step.yaml",
            ),
            structure="test",
            step_type_spec="cp2k_md",
            parameters={
                "functional": "PBE",
                "ensemble": "NVT",
                "steps": 10,
            },
        )
        
        output_path = tmp_path / "input.inp"
        write_cp2k_input(step_spec, structure, output_path)
        
        content = output_path.read_text()
        assert "RUN_TYPE MD" in content
        assert "&MOTION" in content
        assert "&MD" in content
        assert "&CELL" in content  # CRITICAL: CELL print for MD
        assert "MD 1" in content  # CELL print frequency


class TestCp2kParser:
    """Test CP2K parser functions."""
    
    def test_parse_cp2k_cell(self, tmp_path):
        """Test parsing cell file."""
        from qmatsuite.engine.cp2k_parser import parse_cp2k_cell
        
        cell_file = tmp_path / "test.cell"
        cell_file.write_text("""#  Step   Time [fs]       Ax [Angstrom]       Ay [Angstrom]       Az [Angstrom]       Bx [Angstrom]       By [Angstrom]       Bz [Angstrom]       Cx [Angstrom]       Cy [Angstrom]       Cz [Angstrom]      Volume [Angstrom^3]
       1       0.000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000           160.1914779910
       2       0.000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000        0.0000000000        0.0000000000        0.0000000000        5.4310000000           160.1914779910
""")
        
        data = parse_cp2k_cell(cell_file)
        assert len(data) == 2
        assert data[0]["step"] == 1
        assert data[0]["time_fs"] == 0.0
        assert len(data[0]["A"]) == 3
        assert data[0]["A"][0] == 5.431
    
    def test_parse_cp2k_ener(self, tmp_path):
        """Test parsing energy file."""
        from qmatsuite.engine.cp2k_parser import parse_cp2k_ener
        
        ener_file = tmp_path / "test.ener"
        ener_file.write_text("""#   Step   Time[fs]       Kin.[a.u.]   Temp[K]     Pot.[a.u.]   Cons Qty[a.u.]   CPU[s]
      0      0.000000    0.000000000    0.00     -17.157456789   -17.157456789    1.234
      1      0.500000    0.001234567  156.78     -17.158234567   -17.156999999    2.345
""")
        
        data = parse_cp2k_ener(ener_file)
        assert len(data) == 2
        assert data[0]["step"] == 0
        assert data[0]["time_fs"] == 0.0
        assert data[0]["temp_K"] == 0.0
        assert data[1]["temp_K"] == 156.78
    
    def test_parse_cp2k_xyz_comment(self):
        """Test parsing XYZ comment line."""
        from qmatsuite.engine.cp2k_parser import parse_cp2k_xyz_comment
        
        comment = " i =        5, E =      -17.12345678"
        result = parse_cp2k_xyz_comment(comment)
        assert result["iteration"] == 5
        assert result["energy"] == -17.12345678

