"""Tests for GUI scanner output validation."""

import json
import pytest
from pathlib import Path

GUI_METHODS_TXT = Path(__file__).parent.parent.parent / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.txt"
GUI_METHODS_JSON = Path(__file__).parent.parent.parent / "gui" / "tests" / "e2e" / "tools" / "gui_rpc_methods.json"


def test_gui_methods_file_exists():
    """GUI methods file exists and is non-empty."""
    if not GUI_METHODS_TXT.exists():
        pytest.skip("GUI methods file not found. Run scan_gui_rpc_methods.py first.")
    
    content = GUI_METHODS_TXT.read_text()
    assert len(content.strip()) > 0, "GUI methods file is empty"


def test_gui_methods_are_valid_strings():
    """All listed methods are strings without spaces."""
    if not GUI_METHODS_TXT.exists():
        pytest.skip("GUI methods file not found. Run scan_gui_rpc_methods.py first.")
    
    methods = [line.strip() for line in GUI_METHODS_TXT.read_text().splitlines() if line.strip()]
    
    assert len(methods) > 0, "No methods found in file"
    
    for method in methods:
        assert isinstance(method, str), f"Method must be string: {method}"
        assert " " not in method, f"Method must not contain spaces: {method}"
        assert len(method) > 0, "Method must not be empty"


def test_gui_methods_json_structure():
    """GUI methods JSON has correct structure."""
    if not GUI_METHODS_JSON.exists():
        pytest.skip("GUI methods JSON not found. Run scan_gui_rpc_methods.py first.")
    
    with open(GUI_METHODS_JSON) as f:
        data = json.load(f)
    
    assert "methods" in data
    assert isinstance(data["methods"], list)
    assert len(data["methods"]) > 0
    
    assert "extracted_from_patterns" in data
    assert isinstance(data["extracted_from_patterns"], list)
    
    assert "file_count_scanned" in data
    assert isinstance(data["file_count_scanned"], int)


def test_gui_methods_txt_json_consistency():
    """Text and JSON files contain the same methods."""
    if not GUI_METHODS_TXT.exists() or not GUI_METHODS_JSON.exists():
        pytest.skip("GUI methods files not found. Run scan_gui_rpc_methods.py first.")
    
    txt_methods = set(line.strip() for line in GUI_METHODS_TXT.read_text().splitlines() if line.strip())
    
    with open(GUI_METHODS_JSON) as f:
        json_data = json.load(f)
    json_methods = set(json_data["methods"])
    
    assert txt_methods == json_methods, "Text and JSON files have different methods"



