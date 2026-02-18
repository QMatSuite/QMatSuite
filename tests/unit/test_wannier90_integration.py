"""
Tests for Wannier90 integration.

Tests step type registration, .win file generation, and runner logic.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from quantumvitas.workflow.registry import StepTypeRegistry
from quantumvitas.io.wannier90_input import (
    Wannier90Input,
    Pw2Wannier90Input,
    generate_kpoints_from_mp_grid,
)


class TestStepTypeRegistration:
    """Test that Wannier90 step types are properly registered.

    Uses get_for_engine(gen_type, engine) per constitution: registry.get() takes GEN only.
    """

    def test_wannierprep_in_registry(self):
        """wannierprep should be in step type registry."""
        registry = StepTypeRegistry()
        spec = registry.get_for_engine("wannierprep", "w90")
        assert spec is not None
        assert spec.step_type_gen == "wannierprep"
        assert spec.executable == "wannier90.x"
        assert spec.engine == "w90"

    def test_pw2wannier_in_registry(self):
        """pw2wannier should be in step type registry."""
        registry = StepTypeRegistry()
        spec = registry.get_for_engine("pw2wannier", "qe")
        assert spec is not None
        assert spec.step_type_gen == "pw2wannier"
        assert spec.executable == "pw2wannier90.x"
        assert spec.engine == "qe"

    def test_wannier_in_registry(self):
        """wannier should be in step type registry."""
        registry = StepTypeRegistry()
        spec = registry.get_for_engine("wannier", "w90")
        assert spec is not None
        assert spec.step_type_gen == "wannier"
        assert spec.executable == "wannier90.x"
        assert spec.engine == "w90"


class TestWannier90Input:
    """Test .win file generation and parsing."""
    
    def test_basic_win_generation(self):
        """Test basic .win file generation."""
        win = Wannier90Input(
            seedname="diamond",
            num_wann=4,
            num_iter=20,
            mp_grid=[4, 4, 4],
        )
        
        content = win.to_string()
        
        assert "num_wann        = 4" in content
        assert "num_iter        = 20" in content
        assert "mp_grid : 4 4 4" in content
    
    def test_win_with_atoms_frac(self):
        """Test .win with atoms_frac block."""
        win = Wannier90Input(
            num_wann=4,
            atoms_frac=[
                ["C", -0.125, -0.125, -0.125],
                ["C", 0.125, 0.125, 0.125],
            ],
        )
        
        content = win.to_string()
        
        assert "begin atoms_frac" in content
        assert "end atoms_frac" in content
        assert "C" in content
    
    def test_win_with_projections(self):
        """Test .win with projections block."""
        win = Wannier90Input(
            num_wann=4,
            projections_block="""f=0.0,0.0,0.0:s
f=0.0,0.0,0.5:s
f=0.0,0.5,0.0:s
f=0.5,0.0,0.0:s""",
        )
        
        content = win.to_string()
        
        assert "begin projections" in content
        assert "end projections" in content
        assert "f=0.0,0.0,0.0:s" in content
    
    def test_win_with_unit_cell(self):
        """Test .win with unit_cell_cart block."""
        win = Wannier90Input(
            num_wann=4,
            unit_cell_cart=[
                [-1.613990, 0.000000, 1.613990],
                [0.000000, 1.613990, 1.613990],
                [-1.613990, 1.613990, 0.000000],
            ],
        )
        
        content = win.to_string()
        
        assert "begin unit_cell_cart" in content
        assert "end unit_cell_cart" in content
        assert "-1.613990" in content
    
    def test_win_with_kpoints(self):
        """Test .win with explicit kpoints block."""
        kpoints = generate_kpoints_from_mp_grid([2, 2, 2])
        win = Wannier90Input(
            num_wann=4,
            mp_grid=[2, 2, 2],
            kpoints=kpoints,
        )
        
        content = win.to_string()
        
        assert "begin kpoints" in content
        assert "end kpoints" in content
        assert len(kpoints) == 8  # 2x2x2 = 8 k-points
    
    def test_win_parse_roundtrip(self):
        """Test parsing and re-generating .win file."""
        original = Wannier90Input(
            seedname="test",
            num_wann=4,
            num_bands=8,
            num_iter=100,
            mp_grid=[4, 4, 4],
            atoms_frac=[
                ["Si", 0.0, 0.0, 0.0],
                ["Si", 0.25, 0.25, 0.25],
            ],
        )
        
        content = original.to_string()
        parsed = Wannier90Input.from_string(content)
        
        assert parsed.num_wann == 4
        assert parsed.num_bands == 8
        assert parsed.num_iter == 100
        assert parsed.mp_grid == [4, 4, 4]
        assert len(parsed.atoms_frac) == 2
    
    def test_win_with_plotting_options(self):
        """Test .win with wannier_plot options."""
        win = Wannier90Input(
            num_wann=4,
            wannier_plot=True,
            wannier_plot_supercell=3,
        )
        
        content = win.to_string()
        
        assert "wannier_plot = .true." in content
        assert "wannier_plot_supercell = 3" in content


class TestPw2Wannier90Input:
    """Test .pw2wan file generation and parsing."""
    
    def test_basic_pw2wan_generation(self):
        """Test basic .pw2wan file generation."""
        pw2wan = Pw2Wannier90Input(
            seedname="diamond",
            prefix="di",
            outdir="./",
        )
        
        content = pw2wan.to_string()
        
        assert "&inputpp" in content
        assert "seedname = 'diamond'" in content
        assert "prefix = 'di'" in content
        assert "outdir = './'" in content
        assert "/" in content  # End of namelist
    
    def test_pw2wan_with_write_options(self):
        """Test .pw2wan with write options."""
        pw2wan = Pw2Wannier90Input(
            seedname="test",
            prefix="pwscf",
            write_mmn=True,
            write_amn=True,
            write_unk=True,
        )
        
        content = pw2wan.to_string()
        
        assert "write_mmn = .true." in content
        assert "write_amn = .true." in content
        assert "write_unk = .true." in content
    
    def test_pw2wan_parse_roundtrip(self):
        """Test parsing and re-generating .pw2wan file."""
        original = Pw2Wannier90Input(
            seedname="diamond",
            prefix="di",
            outdir="./output",
            write_mmn=True,
            write_amn=True,
            write_unk=False,
            spin_component="none",
        )
        
        content = original.to_string()
        parsed = Pw2Wannier90Input.from_string(content)
        
        assert parsed.seedname == "diamond"
        assert parsed.prefix == "di"
        assert parsed.outdir == "./output"
        assert parsed.write_mmn is True
        assert parsed.write_amn is True
        assert parsed.write_unk is False


class TestKpointGeneration:
    """Test k-point grid generation."""
    
    def test_generate_2x2x2_grid(self):
        """Test 2x2x2 k-point grid generation."""
        kpoints = generate_kpoints_from_mp_grid([2, 2, 2])
        
        assert len(kpoints) == 8
        assert [0.0, 0.0, 0.0] in kpoints
        assert [0.5, 0.5, 0.5] in kpoints
    
    def test_generate_4x4x4_grid(self):
        """Test 4x4x4 k-point grid generation."""
        kpoints = generate_kpoints_from_mp_grid([4, 4, 4])
        
        assert len(kpoints) == 64
        assert [0.0, 0.0, 0.0] in kpoints
        assert [0.75, 0.75, 0.75] in kpoints


class TestEngineExecutableMap:
    """Test that W90 executables are in engine map."""
    
    def test_w90_executables_in_map(self):
        """Test W90 executables are in EXECUTABLE_MAP."""
        from quantumvitas.core.engines.qe import QuantumEspressoEngine

        assert "wannierprep" in QuantumEspressoEngine.EXECUTABLE_MAP
        assert "pw2wannier" in QuantumEspressoEngine.EXECUTABLE_MAP
        assert "wannier" in QuantumEspressoEngine.EXECUTABLE_MAP

        assert QuantumEspressoEngine.EXECUTABLE_MAP["wannierprep"] == "wannier90.x"
        assert QuantumEspressoEngine.EXECUTABLE_MAP["pw2wannier"] == "pw2wannier90.x"
        assert QuantumEspressoEngine.EXECUTABLE_MAP["wannier"] == "wannier90.x"


class TestDemoGeneration:
    """Test that Wannier90 demo was generated correctly."""
    
    @pytest.fixture
    def demo_path(self):
        """Path to the generated demo."""
        repo_root = Path(__file__).parent.parent.parent
        return repo_root / "resources" / "demo_projects" / "qe_diamond_wannier.yml"

    def test_demo_file_exists(self, demo_path):
        """Test that demo file was generated."""
        if not demo_path.exists():
            pytest.skip("Demo not generated yet")

        assert demo_path.exists()
        assert demo_path.suffix == ".yml"

    def test_demo_has_wannier_step(self, demo_path):
        """Test that demo has a w90_wannier step with expected parameters."""
        if not demo_path.exists():
            pytest.skip("Demo not generated yet")

        import yaml

        with open(demo_path) as f:
            demo = yaml.safe_load(f)

        assert "calculations" in demo
        assert len(demo["calculations"]) >= 1

        calc = demo["calculations"][0]
        assert "steps" in calc
        assert len(calc["steps"]) >= 1

        step_types = [s["step_type_spec"] for s in calc["steps"]]
        assert "w90_wannier" in step_types

    def test_demo_has_flat_w90_params(self, demo_path):
        """Test that demo W90 step has flat parameters (not namelist-wrapped)."""
        if not demo_path.exists():
            pytest.skip("Demo not generated yet")

        import yaml

        with open(demo_path) as f:
            demo = yaml.safe_load(f)

        calc = demo["calculations"][0]
        w90_step = None
        for step in calc["steps"]:
            if step["step_type_spec"] == "w90_wannier":
                w90_step = step
                break

        assert w90_step is not None
        params = w90_step.get("parameters", {})

        # Flat W90 parameters (not nested in namelists)
        assert "num_wann" in params
        assert isinstance(params["num_wann"], int)

