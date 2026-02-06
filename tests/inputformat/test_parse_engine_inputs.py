"""Tests for the parse_engine_inputs orchestrator.

Uses mock parsers — no real engine code. Tests the orchestrator's
content_role dispatch, multi-file merging, diagnostics, and error handling.
"""

from __future__ import annotations

import pytest

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    SSOTMappingSpec,
)
from quantumvitas.inputformat.parser import (
    Diagnostic,
    ParseResult,
    parse_engine_inputs,
)


# ──────────────────────────────────────────────────────────────────────────
# Mock parsers
# ──────────────────────────────────────────────────────────────────────────


def _mock_params_parser(text: str) -> dict:
    """Mock parser for parameters content_role."""
    return {"ENCUT": 300, "ISMEAR": 0}


def _mock_structure_parser(text: str) -> dict:
    """Mock parser for structure content_role."""
    return {
        "lattice": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]],
        "species": ["Si", "Si"],
        "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        "comment": "Si diamond",
    }


def _mock_kpoints_parser(text: str) -> dict:
    """Mock parser for kpoints content_role."""
    return {"mode": "automatic", "mesh": [4, 4, 4], "shift": [0, 0, 0]}


def _mock_combined_parser(text: str) -> dict:
    """Mock parser for combined content_role."""
    return {
        "params": {"ecut": 30, "ngkpt": [4, 4, 4]},
        "structure": {
            "lattice": [[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]],
            "species": ["Si", "Si"],
            "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        },
    }


# ──────────────────────────────────────────────────────────────────────────
# Orchestrator tests
# ──────────────────────────────────────────────────────────────────────────


class TestParseEngineInputs:
    """Core orchestrator behaviour with mock parsers."""

    def test_basic_multi_file_parse(self, tmp_path):
        """Three files parsed and merged into single ParseResult."""
        (tmp_path / "PARAMS").write_text("mock")
        (tmp_path / "STRUCT").write_text("mock")
        (tmp_path / "KPTS").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="PARAMS",
                    content_role="parameters",
                    custom_writer=None,
                    custom_parser=_mock_params_parser,
                ),
                InputFileSpec(
                    filename="STRUCT",
                    content_role="structure",
                    custom_writer=None,
                    custom_parser=_mock_structure_parser,
                ),
                InputFileSpec(
                    filename="KPTS",
                    content_role="kpoints",
                    custom_writer=None,
                    custom_parser=_mock_kpoints_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)

        assert result.params["ENCUT"] == 300
        assert result.params["ISMEAR"] == 0
        assert result.params["kpoints"]["mode"] == "automatic"
        assert result.structure is not None
        assert result.structure["species"] == ["Si", "Si"]
        assert result.diagnostics == []

    def test_parameters_role_merges(self, tmp_path):
        """Parameters content_role merges into result.params."""
        (tmp_path / "PARAMS").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="PARAMS",
                    content_role="parameters",
                    custom_parser=_mock_params_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params == {"ENCUT": 300, "ISMEAR": 0}
        assert result.structure is None

    def test_structure_role_sets_structure(self, tmp_path):
        """Structure content_role sets result.structure."""
        (tmp_path / "STRUCT").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="STRUCT",
                    content_role="structure",
                    custom_parser=_mock_structure_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.structure is not None
        assert result.structure["species"] == ["Si", "Si"]
        assert result.params == {}

    def test_kpoints_role_injects(self, tmp_path):
        """Kpoints content_role injects into result.params['kpoints']."""
        (tmp_path / "KPTS").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="KPTS",
                    content_role="kpoints",
                    custom_parser=_mock_kpoints_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert "kpoints" in result.params
        assert result.params["kpoints"]["mesh"] == [4, 4, 4]

    def test_combined_role_merges_both(self, tmp_path):
        """Combined content_role updates both params and structure."""
        (tmp_path / "input.dat").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="input.dat",
                    content_role="combined",
                    custom_parser=_mock_combined_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["ecut"] == 30
        assert result.params["ngkpt"] == [4, 4, 4]
        assert result.structure is not None
        assert result.structure["species"] == ["Si", "Si"]

    def test_missing_required_file_raises(self, tmp_path):
        """Missing non-optional file raises FileNotFoundError."""
        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="MISSING",
                    content_role="parameters",
                    custom_parser=_mock_params_parser,
                ),
            ),
        )

        with pytest.raises(FileNotFoundError, match="MISSING"):
            parse_engine_inputs(spec, tmp_path)

    def test_missing_optional_file_skipped(self, tmp_path):
        """Missing optional file produces info diagnostic and is skipped."""
        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="OPTIONAL",
                    content_role="parameters",
                    optional=True,
                    custom_parser=_mock_params_parser,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params == {}
        assert len(result.diagnostics) == 1
        assert result.diagnostics[0].level == "info"
        assert result.diagnostics[0].code == "optional_file_missing"

    def test_no_custom_parser_raises(self, tmp_path):
        """NotImplementedError when custom_parser is None."""
        (tmp_path / "FILE").write_text("mock")

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="FILE",
                    content_role="parameters",
                    custom_parser=None,
                ),
            ),
        )

        with pytest.raises(NotImplementedError, match="No custom_parser"):
            parse_engine_inputs(spec, tmp_path)

    def test_empty_spec_returns_empty_result(self, tmp_path):
        """Spec with no input_files returns empty ParseResult."""
        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params == {}
        assert result.structure is None
        assert result.diagnostics == []

    def test_multi_parameters_files_merge(self, tmp_path):
        """Two parameters files merge their dicts (second wins on conflict)."""
        (tmp_path / "PARAMS1").write_text("mock")
        (tmp_path / "PARAMS2").write_text("mock")

        def _parser_a(text: str) -> dict:
            return {"KEY_A": 1, "SHARED": "from_a"}

        def _parser_b(text: str) -> dict:
            return {"KEY_B": 2, "SHARED": "from_b"}

        spec = EngineInputSpec(
            engine_family="mock",
            syntax_family="mock",
            input_files=(
                InputFileSpec(
                    filename="PARAMS1",
                    content_role="parameters",
                    custom_parser=_parser_a,
                ),
                InputFileSpec(
                    filename="PARAMS2",
                    content_role="parameters",
                    custom_parser=_parser_b,
                ),
            ),
        )

        result = parse_engine_inputs(spec, tmp_path)
        assert result.params["KEY_A"] == 1
        assert result.params["KEY_B"] == 2
        assert result.params["SHARED"] == "from_b"  # second wins


# ──────────────────────────────────────────────────────────────────────────
# Type tests
# ──────────────────────────────────────────────────────────────────────────


class TestDiagnostic:
    """Diagnostic dataclass behaviour."""

    def test_diagnostic_frozen(self):
        d = Diagnostic(level="warning", message="test", file="foo.in")
        with pytest.raises(AttributeError):
            d.level = "error"  # type: ignore[misc]

    def test_diagnostic_defaults(self):
        d = Diagnostic(level="info", message="msg", file="f.in")
        assert d.line is None
        assert d.code == ""


class TestParseResult:
    """ParseResult dataclass behaviour."""

    def test_parse_result_defaults(self):
        r = ParseResult()
        assert r.params == {}
        assert r.structure is None
        assert r.diagnostics == []
