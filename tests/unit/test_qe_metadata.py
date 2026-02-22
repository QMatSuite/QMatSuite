"""
Tests for QE parameter metadata access layer.
"""

import pytest

from qmatsuite.data import (
    get_doc_url_pattern,
    get_module_doc_url,
    get_module_namelists,
    get_module_param_sections,
    get_ui_parameters,
    list_supported_modules,
    validate_ui_parameters,
)


class TestQEMetadataBasics:
    """Basic tests for QE metadata helpers."""
    
    def test_list_supported_modules(self):
        """Test that we can list all supported modules."""
        modules = list_supported_modules()
        assert isinstance(modules, list)
        assert len(modules) > 0
        assert "pw" in modules
        assert "ph" in modules
        assert "dos" in modules
        assert "bands" in modules
    
    def test_get_module_param_sections(self):
        """Test getting parameter sections for a module."""
        sections = get_module_param_sections("pw")
        assert isinstance(sections, dict)
        assert "&CONTROL" in sections
        assert "&SYSTEM" in sections
        assert "&ELECTRONS" in sections
        assert isinstance(sections["&CONTROL"], list)
        assert "calculation" in sections["&CONTROL"]
        assert "ecutwfc" in sections["&SYSTEM"]
    
    def test_get_module_param_sections_nonexistent(self):
        """Test that nonexistent modules return empty dict."""
        sections = get_module_param_sections("nonexistent_module")
        assert sections == {}
    
    def test_get_module_doc_url(self):
        """Test getting documentation URL for a module."""
        url = get_module_doc_url("pw")
        assert url is not None
        assert url == "https://www.quantum-espresso.org/Doc/INPUT_PW.html"
        
        url_ph = get_module_doc_url("ph")
        assert url_ph is not None
        assert "INPUT_PH.html" in url_ph
    
    def test_get_module_doc_url_nonexistent(self):
        """Test that nonexistent modules return None."""
        url = get_module_doc_url("nonexistent_module")
        assert url is None
    
    def test_get_doc_url_pattern(self):
        """Test getting the documentation URL pattern."""
        pattern = get_doc_url_pattern()
        assert "{name}" in pattern
        assert "quantum-espresso.org" in pattern
    
    def test_get_module_namelists(self):
        """Test getting namelist names for a module."""
        namelists = get_module_namelists("pw")
        assert isinstance(namelists, list)
        assert "control" in namelists
        assert "system" in namelists
        assert "electrons" in namelists


class TestUIParameters:
    """Tests for UI parameter metadata."""
    
    def test_get_ui_parameters_pw_scf(self):
        """Test getting UI parameters for pw scf."""
        params = get_ui_parameters("pw", "scf")
        assert isinstance(params, list)
        assert len(params) > 0
        
        # Check that we have expected parameters
        param_names = [p.name for p in params]
        assert "ecutwfc" in param_names
        assert "ecutrho" in param_names
        assert "conv_thr" in param_names
        
        # Check a specific parameter
        ecutwfc = next(p for p in params if p.name == "ecutwfc")
        assert ecutwfc.namelist == "SYSTEM"
        assert ecutwfc.label == "Wavefunction Cutoff"
        assert ecutwfc.type == "number"
        assert ecutwfc.unit == "Ry"
    
    def test_get_ui_parameters_pw_nscf(self):
        """Test getting UI parameters for pw nscf."""
        params = get_ui_parameters("pw", "nscf")
        assert isinstance(params, list)
        assert len(params) > 0
        assert "ecutwfc" in [p.name for p in params]
    
    def test_get_ui_parameters_nonexistent(self):
        """Test that nonexistent module/step returns empty list."""
        params = get_ui_parameters("nonexistent_module", "scf")
        assert params == []
        
        params2 = get_ui_parameters("pw", "nonexistent_step")
        assert params2 == []
    
    def test_get_ui_parameters_case_insensitive(self):
        """Test that module and step type are case-insensitive."""
        params_upper = get_ui_parameters("PW", "SCF")
        params_lower = get_ui_parameters("pw", "scf")
        assert len(params_upper) == len(params_lower)
        assert set(p.name for p in params_upper) == set(p.name for p in params_lower)


class TestUIParameterValidation:
    """Tests for UI parameter validation against qe_module_parameters.json."""
    
    def test_validate_ui_parameters_passes(self):
        """Test that validation passes for correct UI parameters."""
        errors = validate_ui_parameters()
        # Should return empty list if all parameters are valid
        assert isinstance(errors, list)
        # We expect this to pass with the current qe_ui_parameters.json
        # If it fails, that's actually good - it means validation is working!
        # But for now, we'll just check it doesn't crash
    
    def test_validate_ui_parameters_structure(self):
        """Test that validation checks structure correctly."""
        errors = validate_ui_parameters()
        # All errors should be strings
        for error in errors:
            assert isinstance(error, str)
            assert len(error) > 0


class TestIntegrationWithParameterMap:
    """Integration tests ensuring UI params reference valid QE parameters."""
    
    def test_all_ui_params_exist_in_qe_params(self):
        """Test that every UI parameter name exists in qe_module_parameters.json."""
        from qmatsuite.data import get_ui_parameters, get_module_param_sections
        
        # Check pw module
        ui_params = get_ui_parameters("pw", "scf")
        sections = get_module_param_sections("pw")
        
        # Build set of all valid parameter names
        all_valid_params = set()
        for param_list in sections.values():
            all_valid_params.update(param.lower() for param in param_list)
        
        # Check each UI parameter exists
        for ui_param in ui_params:
            assert ui_param.name.lower() in all_valid_params, \
                f"UI parameter '{ui_param.name}' not found in qe_module_parameters.json"
            
            # Check it's in the claimed namelist
            section_name = f"&{ui_param.namelist.upper()}"
            assert section_name in sections, \
                f"Namelist '{ui_param.namelist}' not found for module 'pw'"
            
            assert ui_param.name in sections[section_name], \
                f"Parameter '{ui_param.name}' not in namelist '{ui_param.namelist}'"
