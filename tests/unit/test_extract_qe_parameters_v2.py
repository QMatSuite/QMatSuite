"""
Tests for the v2 QE parameter extractor.
"""

import json
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Add tools directory to path for imports
tools_dir = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(tools_dir))

# Import extractor functions for testing
try:
    from extract_qe_parameters_v2 import (
        extract_parameter_metadata_from_table,
        extract_toc_parameters,
        parse_module_doc,
    )
except ImportError as e:
    pytest.skip(f"Could not import extract_qe_parameters_v2: {e}", allow_module_level=True)


class TestExtractQEParametersV2:
    """Tests for v2 parameter extraction."""
    
    def test_extract_toc_parameters_pw(self):
        """Test that ToC extraction finds CONTROL and SYSTEM sections."""
        # Use cached HTML if available, or skip if not
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        html_content = html_path.read_text(encoding="utf-8")
        toc = extract_toc_parameters(html_content)
        
        assert "&CONTROL" in toc
        assert "&SYSTEM" in toc
        assert "calculation" in toc["&CONTROL"]
        assert "ecutwfc" in toc["&SYSTEM"]
    
    def test_parse_module_doc_pw_structure(self):
        """Test that pw module parsing produces correct v2 structure."""
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        result = parse_module_doc("pw", html_path, verbose=False)
        
        assert "doc_url" in result
        assert "parameters" in result
        assert len(result["parameters"]) > 0
        
        # Check a known parameter
        calc_key = "&CONTROL.calculation"
        assert calc_key in result["parameters"]
        
        calc_param = result["parameters"][calc_key]
        assert calc_param["namelist"] == "&CONTROL"
        assert calc_param["name"] == "calculation"
        assert calc_param["type"] == "CHARACTER"
        assert calc_param["default"] is not None  # Should have a default
        assert calc_param["enum"] is not None  # Should have enum values
        assert len(calc_param["enum"]) > 0
        assert "'scf'" in calc_param["default"] or "scf" in str(calc_param["default"])
        
        # Check description exists
        assert calc_param["description"] is not None
        assert len(calc_param["description"]) > 0
    
    def test_parse_module_doc_parameter_metadata(self):
        """Test that parameter metadata includes all required fields."""
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        result = parse_module_doc("pw", html_path, verbose=False)
        
        # Check a few different parameters
        test_params = [
            "&CONTROL.calculation",  # CHARACTER with enum
            "&SYSTEM.ecutwfc",  # REAL with default
            "&CONTROL.restart_mode",  # CHARACTER with enum
        ]
        
        for key in test_params:
            if key in result["parameters"]:
                param = result["parameters"][key]
                assert "namelist" in param
                assert "name" in param
                assert "type" in param
                # default, enum, description can be None, but keys must exist
                assert "default" in param
                assert "enum" in param
                assert "description" in param
    
    def test_extract_parameter_metadata_from_table_structure(self):
        """Test parsing a single parameter table."""
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        
        # Find the calculation parameter table
        tables = soup.find_all("table")
        calculation_table = None
        for table in tables:
            th = table.find("th")
            if th and th.get_text(strip=True) == "calculation":
                calculation_table = table
                break
        
        if not calculation_table:
            pytest.skip("Could not find calculation parameter table in HTML")
        
        meta_list = extract_parameter_metadata_from_table(calculation_table)
        assert meta_list is not None
        assert len(meta_list) > 0
        meta = meta_list[0]  # Function now returns a list
        assert meta["name"] == "calculation"
        assert meta["type"] == "CHARACTER"
        assert meta["default"] is not None
        assert meta["enum"] is not None
        assert len(meta["enum"]) > 0
        assert "scf" in meta["enum"]
    
    def test_celldm_indexing_metadata(self):
        """Test that celldm parameter has correct indexing metadata."""
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        result = parse_module_doc("pw", html_path, verbose=False)
        
        # Check celldm parameter
        celldm_key = "&SYSTEM.celldm"
        assert celldm_key in result["parameters"], f"celldm not found. Available keys: {list(result['parameters'].keys())[:10]}"
        
        celldm_param = result["parameters"][celldm_key]
        assert celldm_param["name"] == "celldm"  # v1-style base name
        assert celldm_param["type"] == "REAL"
        assert "indexing" in celldm_param
        
        indexing = celldm_param["indexing"]
        assert indexing["kind"] == "bounded"
        assert indexing["index_name"] == "i"
        assert indexing["start"] == 1
        assert indexing["end"] == 6
        assert indexing["keyword_pattern"] == "celldm({i})"
    
    def test_parameter_names_match_v1(self):
        """Test that parameter names match v1 style (base names, not expanded)."""
        html_path = Path(__file__).parent.parent.parent / "temp" / "qe_docs" / "INPUT_PW.html"
        if not html_path.exists():
            pytest.skip(f"INPUT_PW.html not found at {html_path}")
        
        result = parse_module_doc("pw", html_path, verbose=False)
        
        # Check that array parameters use base names
        params = result["parameters"]
        
        # celldm should be stored as "celldm", not "celldm(1)", "celldm(2)", etc.
        assert "&SYSTEM.celldm" in params
        assert params["&SYSTEM.celldm"]["name"] == "celldm"
        
        # Should NOT have celldm(1), celldm(2), etc. as separate entries
        celldm_expanded = [k for k in params.keys() if "celldm" in k.lower() and "(" in k]
        assert len(celldm_expanded) == 0, f"Found expanded celldm parameters: {celldm_expanded}"
