"""Tests for MCP import_structure tool — CIF/POSCAR inline and file import.

Covers the CIF inline import bug (double-encoded newlines) and validates
all four code paths: {CIF, POSCAR} x {inline, file} for three structures
(Si diamond, FCC Al, BCC Fe).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from qmatsuite.api import QMSService

# ---------------------------------------------------------------------------
# Unwrap the FunctionTool to get the bare callable
# ---------------------------------------------------------------------------
from qmatsuite.mcp.tools.import_structure import import_structure as _tool, _unescape_content

_import_structure = _tool.fn


# ---------------------------------------------------------------------------
# Test structures
# ---------------------------------------------------------------------------

def _si_diamond() -> Structure:
    return Structure(
        Lattice.cubic(5.431),
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )


def _fcc_al() -> Structure:
    return Structure(Lattice.cubic(4.05), ["Al"], [[0.0, 0.0, 0.0]])


def _bcc_fe() -> Structure:
    return Structure(Lattice.cubic(2.87), ["Fe"], [[0.0, 0.0, 0.0]])


STRUCTURES = {
    "Si_diamond": _si_diamond,
    "FCC_Al": _fcc_al,
    "BCC_Fe": _bcc_fe,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_project(tmp_path, monkeypatch):
    """Create a fresh QMS project and patch MCP project context."""
    project_root = QMSService.init_project(tmp_path / "project")
    from qmatsuite.mcp import project as mcp_mod
    monkeypatch.setattr(mcp_mod, "_project_root_override", project_root)
    return project_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_success(result: dict, expected_formula: str | None = None):
    assert result["status"] == "success", (
        f"Expected success, got: {result.get('error_type')}: {result.get('message')}"
    )
    data = result["data"]
    assert "structure_ulid" in data
    assert data["n_atoms"] > 0
    if expected_formula:
        assert data["formula"] == expected_formula


# ---------------------------------------------------------------------------
# Unit tests for _unescape_content
# ---------------------------------------------------------------------------

class TestUnescapeContent:
    def test_literal_backslash_n_decoded(self):
        raw = "line1\\nline2\\nline3"
        assert _unescape_content(raw) == "line1\nline2\nline3"

    def test_real_newlines_untouched(self):
        raw = "line1\nline2\nline3"
        assert _unescape_content(raw) == raw

    def test_mixed_real_and_literal_untouched(self):
        """If real newlines exist, literal \\n should be left alone."""
        raw = "line1\nline2\\nline3"
        assert _unescape_content(raw) == raw

    def test_crlf_literal_decoded(self):
        raw = "line1\\r\\nline2\\r\\nline3"
        assert _unescape_content(raw) == "line1\r\nline2\r\nline3"

    def test_tab_literal_decoded(self):
        raw = "col1\\tcol2\\nrow2"
        assert _unescape_content(raw) == "col1\tcol2\nrow2"

    def test_empty_string(self):
        assert _unescape_content("") == ""

    def test_no_escapes(self):
        raw = "just plain text"
        assert _unescape_content(raw) == raw


# ---------------------------------------------------------------------------
# CIF inline import tests
# ---------------------------------------------------------------------------

class TestCIFInlineImport:
    """CIF content passed as file_content string."""

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_cif_inline_real_newlines(self, mcp_project, name, factory):
        struct = factory()
        cif_text = struct.to(fmt="cif")
        result = _import_structure(file_content=cif_text, format="cif")
        _assert_success(result)

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_cif_inline_escaped_newlines(self, mcp_project, name, factory):
        """The original bug: literal \\n instead of real newlines."""
        struct = factory()
        cif_text = struct.to(fmt="cif")
        escaped = cif_text.replace("\n", "\\n")
        # Confirm the escaping actually removes real newlines
        assert "\n" not in escaped
        assert "\\n" in escaped
        result = _import_structure(file_content=escaped, format="cif")
        _assert_success(result)

    def test_cif_inline_crlf(self, mcp_project):
        cif_text = _si_diamond().to(fmt="cif").replace("\n", "\r\n")
        result = _import_structure(file_content=cif_text, format="cif")
        _assert_success(result, expected_formula="Si2")

    def test_cif_inline_handcrafted_with_symmetry(self, mcp_project):
        """Minimal hand-crafted CIF with Fd-3m symmetry (agent-style)."""
        cif = textwrap.dedent("""\
            data_Si
            _symmetry_space_group_name_H-M   'F d -3 m'
            _cell_length_a   5.431
            _cell_length_b   5.431
            _cell_length_c   5.431
            _cell_angle_alpha   90.000
            _cell_angle_beta   90.000
            _cell_angle_gamma   90.000

            loop_
            _atom_site_label
            _atom_site_type_symbol
            _atom_site_fract_x
            _atom_site_fract_y
            _atom_site_fract_z
            Si1 Si 0.00000 0.00000 0.00000
        """)
        result = _import_structure(file_content=cif, format="cif")
        _assert_success(result, expected_formula="Si8")

    def test_cif_inline_no_spacegroup(self, mcp_project):
        """CIF without space group tag (P1 implied)."""
        cif = textwrap.dedent("""\
            data_Fe
            _cell_length_a   2.87
            _cell_length_b   2.87
            _cell_length_c   2.87
            _cell_angle_alpha   90.0
            _cell_angle_beta   90.0
            _cell_angle_gamma   90.0

            loop_
            _atom_site_label
            _atom_site_type_symbol
            _atom_site_fract_x
            _atom_site_fract_y
            _atom_site_fract_z
            Fe1 Fe 0.0 0.0 0.0
        """)
        result = _import_structure(file_content=cif, format="cif")
        _assert_success(result, expected_formula="Fe1")


# ---------------------------------------------------------------------------
# CIF file import tests
# ---------------------------------------------------------------------------

class TestCIFFileImport:
    """CIF content written to a file, then imported via file_path."""

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_cif_file(self, mcp_project, tmp_path, name, factory):
        struct = factory()
        cif_path = tmp_path / f"{name.lower()}.cif"
        cif_path.write_text(struct.to(fmt="cif"))
        result = _import_structure(file_path=str(cif_path))
        _assert_success(result)


# ---------------------------------------------------------------------------
# POSCAR inline import tests
# ---------------------------------------------------------------------------

class TestPOSCARInlineImport:
    """POSCAR content passed as file_content string."""

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_poscar_inline(self, mcp_project, name, factory):
        struct = factory()
        poscar_text = struct.to(fmt="poscar")
        result = _import_structure(file_content=poscar_text, format="poscar")
        _assert_success(result)

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_poscar_inline_escaped_newlines(self, mcp_project, name, factory):
        """POSCAR with double-encoded newlines should also be fixed."""
        struct = factory()
        poscar_text = struct.to(fmt="poscar")
        escaped = poscar_text.replace("\n", "\\n")
        result = _import_structure(file_content=escaped, format="poscar")
        _assert_success(result)


# ---------------------------------------------------------------------------
# POSCAR file import tests
# ---------------------------------------------------------------------------

class TestPOSCARFileImport:
    """POSCAR content written to a file, then imported via file_path."""

    @pytest.mark.parametrize("name,factory", list(STRUCTURES.items()))
    def test_poscar_file(self, mcp_project, tmp_path, name, factory):
        struct = factory()
        poscar_path = tmp_path / f"{name.lower()}.vasp"
        poscar_path.write_text(struct.to(fmt="poscar"))
        result = _import_structure(file_path=str(poscar_path))
        _assert_success(result)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestImportErrors:
    def test_missing_input(self, mcp_project):
        result = _import_structure()
        assert result["status"] == "error"
        assert result["error_type"] == "missing_input"

    def test_file_not_found(self, mcp_project):
        result = _import_structure(file_path="/nonexistent/path.cif")
        assert result["status"] == "error"
        assert result["error_type"] == "not_found"

    def test_invalid_cif_content(self, mcp_project):
        result = _import_structure(file_content="not a real CIF file", format="cif")
        assert result["status"] == "error"
        assert result["error_type"] == "import_failed"

    def test_no_project(self, monkeypatch):
        from qmatsuite.mcp import project as mcp_mod
        monkeypatch.setattr(mcp_mod, "_project_root_override", None)
        monkeypatch.delenv("QMS_PROJECT_ROOT", raising=False)
        result = _import_structure(file_content="data_X\n", format="cif")
        assert result["status"] == "error"
        assert result["error_type"] == "no_project"
