"""Unit tests for LAMMPS writer (template rendering)."""

import pytest
from pathlib import Path

from quantumvitas.engine.lammps_writer import (
    render_lammps_template,
    get_template_for_step_type,
    build_template_context,
)


class TestLammpsTemplateRendering:
    """Test LAMMPS template rendering."""
    
    def test_render_minimize_template(self):
        """Test rendering minimize template."""
        context = {
            "step_type_gen": "lammps_relax",
            "step_ulid": "test123",
            "units": "metal",
            "atom_style": "atomic",
            "pair_style_block": "pair_style lj/cut 2.5\npair_coeff 1 1 1.0 1.0 2.5",
            "energy_tolerance": 1.0e-6,
            "force_tolerance": 1.0e-8,
            "max_iterations": 1000,
            "max_evaluations": 10000,
            "thermo_frequency": 100,
            "dump_frequency": 1000,
            "dump_trajectory": True,
        }
        
        script = render_lammps_template("minimize.in.j2", context)
        assert "units metal" in script
        assert "atom_style atomic" in script
        assert "pair_style lj/cut" in script
        assert "minimize" in script
        print("✓ Minimize template renders correctly")
    
    def test_render_md_nvt_template(self):
        """Test rendering NVT MD template."""
        context = {
            "step_type_gen": "lammps_md",
            "step_ulid": "test456",
            "units": "metal",
            "atom_style": "atomic",
            "pair_style_block": "pair_style eam\npair_coeff * * potentials/Cu_u3.eam Cu",
            "ensemble": "nvt",
            "temperature": 300.0,
            "n_steps": 1000,
            "timestep": 0.001,
            "thermo_frequency": 100,
            "dump_frequency": 100,
            "dump_trajectory": True,
        }
        
        script = render_lammps_template("md_nvt.in.j2", context)
        assert "units metal" in script
        assert "fix thermostat all nvt" in script
        assert "run 1000" in script
        print("✓ NVT MD template renders correctly")
    
    def test_get_template_for_step_type(self):
        """Test template selection by step type."""
        assert get_template_for_step_type("lammps_relax") == "minimize.in.j2"
        assert get_template_for_step_type("lammps_md") == "md_nvt.in.j2"
        print("✓ Template selection works")

