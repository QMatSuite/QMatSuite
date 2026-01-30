"""
Tests for daemon QE UI parameters command.
"""

import pytest

from quantumvitas.daemon.server import QVDaemon


class TestDaemonQEUIParameters:
    """Tests for list_qe_ui_parameters daemon command."""
    
    def test_list_qe_ui_parameters_pw_scf(self):
        """Test fetching UI parameters for pw/scf."""
        daemon = QVDaemon()
        payload = {"module": "pw", "step_type_gen": "scf"}
        
        result = daemon._handle_list_qe_ui_parameters(payload)
        
        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0
        
        # Check structure of first parameter
        first_param = result["parameters"][0]
        assert "namelist" in first_param
        assert "name" in first_param
        assert "label" in first_param
        assert "type" in first_param
        assert first_param["namelist"] in ["SYSTEM", "ELECTRONS", "CONTROL"]
    
    def test_list_qe_ui_parameters_pw_nscf(self):
        """Test fetching UI parameters for pw/nscf."""
        daemon = QVDaemon()
        payload = {"module": "pw", "step_type_gen": "nscf"}
        
        result = daemon._handle_list_qe_ui_parameters(payload)
        
        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0
    
    def test_list_qe_ui_parameters_bands_bands(self):
        """Test fetching UI parameters for bands/bands."""
        daemon = QVDaemon()
        payload = {"module": "bands", "step_type_gen": "bands"}
        
        result = daemon._handle_list_qe_ui_parameters(payload)
        
        assert "parameters" in result
        assert isinstance(result["parameters"], list)
        assert len(result["parameters"]) > 0
        
        # Bands module should have BANDS namelist parameters
        bands_params = [p for p in result["parameters"] if p["namelist"] == "BANDS"]
        assert len(bands_params) > 0
    
    def test_list_qe_ui_parameters_nonexistent_module(self):
        """Test that nonexistent module raises error."""
        daemon = QVDaemon()
        payload = {"module": "nonexistent", "step_type_gen": "scf"}
        
        with pytest.raises(ValueError, match="Unknown module"):
            daemon._handle_list_qe_ui_parameters(payload)
    
    def test_list_qe_ui_parameters_missing_module(self):
        """Test that missing module raises error."""
        daemon = QVDaemon()
        payload = {"step_type_gen": "scf"}
        
        with pytest.raises(ValueError, match="'module' is required"):
            daemon._handle_list_qe_ui_parameters(payload)
    
    def test_list_qe_ui_parameters_missing_step_type(self):
        """Test that missing step_type raises error."""
        daemon = QVDaemon()
        payload = {"module": "pw"}

        with pytest.raises(ValueError, match="'step_type_gen' is required"):
            daemon._handle_list_qe_ui_parameters(payload)
    
    def test_list_qe_ui_parameters_parameters_exist_in_qe_params(self):
        """Test that all returned parameter names exist in qe_module_parameters.json."""
        from quantumvitas.data import get_module_param_sections
        
        daemon = QVDaemon()
        payload = {"module": "pw", "step_type_gen": "scf"}
        
        result = daemon._handle_list_qe_ui_parameters(payload)
        
        # Get all valid parameters for pw module
        sections = get_module_param_sections("pw")
        all_valid_params = set()
        for param_list in sections.values():
            all_valid_params.update(param.lower() for param in param_list)
        
        # Check each UI parameter exists
        for param in result["parameters"]:
            param_name = param["name"].lower()
            assert param_name in all_valid_params, \
                f"UI parameter '{param['name']}' not found in qe_module_parameters.json"
            
            # Check it's in the claimed namelist
            section_name = f"&{param['namelist'].upper()}"
            assert section_name in sections, \
                f"Namelist '{param['namelist']}' not found for module 'pw'"
            
            assert param["name"] in sections[section_name], \
                f"Parameter '{param['name']}' not in namelist '{param['namelist']}'"
