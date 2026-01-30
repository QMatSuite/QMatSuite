"""
Regression tests for step type normalization (machine_type → public_type).

These tests guard against the regression fixed in commit:
"Fix: convert machine_type to public_type for step type lookups"

The original bug:
- Step YAML stores machine_type (e.g., 'qe_bands')
- EXECUTABLE_MAP and other lookup maps use public_type keys (e.g., 'bands')
- Without normalization, lookup failed and defaulted to pw.x instead of bands.x

See: docs/dev/plan-remove-steptype-enum.md
"""

import pytest
from pathlib import Path


class TestExecutableResolution:
    """Test that QE executable is correctly resolved from machine_type."""
    
    def test_qe_bands_machine_type_resolves_to_bands_x(self):
        """
        Regression test: qe_bands (machine_type) must resolve to bands.x, not pw.x.
        
        This was the original bug: EXECUTABLE_MAP.get("qe_bands", "pw.x") returned
        "pw.x" because "qe_bands" was not a key (only "bands" was).
        """
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.workflow.registry import normalize_step_type_to_gen
        
        # Test normalization
        assert normalize_step_type_to_gen("qe_bands") == "bands"
        
        # Test EXECUTABLE_MAP lookup with normalized type
        step_type_public = normalize_step_type_to_gen("qe_bands")
        executable = QuantumEspressoEngine.EXECUTABLE_MAP.get(step_type_public, "pw.x")
        
        assert executable == "bands.x", (
            f"Expected 'bands.x' for machine_type='qe_bands', got '{executable}'. "
            "This regression breaks bands.x post-processing."
        )
    
    def test_qe_dos_machine_type_resolves_to_dos_x(self):
        """Verify qe_dos (machine_type) resolves to dos.x."""
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.workflow.registry import normalize_step_type_to_gen
        
        step_type_public = normalize_step_type_to_gen("qe_dos")
        executable = QuantumEspressoEngine.EXECUTABLE_MAP.get(step_type_public, "pw.x")
        
        assert executable == "dos.x"
    
    def test_qe_scf_machine_type_resolves_to_pw_x(self):
        """Verify qe_scf (machine_type) resolves to pw.x (as expected)."""
        from quantumvitas.core.engines.qe import QuantumEspressoEngine
        from quantumvitas.workflow.registry import normalize_step_type_to_gen
        
        step_type_public = normalize_step_type_to_gen("qe_scf")
        executable = QuantumEspressoEngine.EXECUTABLE_MAP.get(step_type_public, "pw.x")
        
        assert executable == "pw.x"


class TestBandsInputGeneration:
    """Test that bands.x input file is correctly generated."""
    
    def test_bands_input_has_no_control_namelist(self):
        """
        Regression test: bands.x input must NOT contain &CONTROL namelist.
        
        bands.x only uses &BANDS namelist. Adding &CONTROL causes QE to fail with:
        "bad line in namelist &control"
        """
        from quantumvitas.calculation.structure_steps import (
            _generate_postprocessing_input,
            StructureStepSpec,
        )
        from quantumvitas.core.resources import ResourceMeta, generate_resource_id, slugify
        
        # Create minimal metadata
        meta = ResourceMeta(ulid=generate_resource_id(),
            name="test_bands",
            slug=slugify("test_bands"),
            path="test/test_bands.step.yaml",
            kind="step",
        )
        
        # Create a minimal bands step spec (machine_type = qe_bands)
        spec = StructureStepSpec(
            meta=meta,
            structure="si",  # Legacy selector field
            step_type_spec="qe_bands",  # Machine type
            parameters={
                "BANDS": {
                    "prefix": "si",
                    "outdir": "./outdir",
                    "filband": "si.bands.dat",
                }
            },
        )
        
        # Generate bands.x input
        qe_input, _ = _generate_postprocessing_input(spec, extra_overrides=None)
        
        # Verify no &CONTROL namelist
        control_namelist = qe_input.get_namelist("control")
        assert control_namelist is None, (
            "bands.x input should NOT contain &CONTROL namelist. "
            "This regression causes bands.x to fail with 'bad line in namelist &control'."
        )
        
        # Verify &BANDS namelist exists
        bands_namelist = qe_input.get_namelist("bands")
        assert bands_namelist is not None, "bands.x input must contain &BANDS namelist"
        
        # Verify module is BANDS
        from quantumvitas.io.model import QEModule
        assert qe_input.module == QEModule.BANDS


class TestNormalizationSSOT:
    """Test that normalization uses the centralized SSOT."""
    
    def test_normalize_function_exists_in_registry(self):
        """Verify normalize_step_type_to_gen is the SSOT in registry module."""
        from quantumvitas.workflow.registry import normalize_step_type_to_gen
        
        # Basic functionality test
        assert normalize_step_type_to_gen("qe_bands") == "bands"
        assert normalize_step_type_to_gen("bands") == "bands"
        assert normalize_step_type_to_gen("QE_BANDS") == "bands"
    
    def test_structure_steps_uses_registry_normalize(self):
        """Verify structure_steps imports from registry, not local copy."""
        from quantumvitas.calculation import structure_steps
        from quantumvitas.workflow import registry
        
        # The local _normalize_step_type_to_gen should be the registry's function
        # (imported with alias)
        assert structure_steps._normalize_step_type_to_gen is registry.normalize_step_type_to_gen

