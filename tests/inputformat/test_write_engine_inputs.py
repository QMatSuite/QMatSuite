"""Tests for the write_engine_inputs orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
    ResourceRefSpec,
    SSOTMappingSpec,
)
from quantumvitas.inputformat.writer import write_engine_inputs


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

SAMPLE_PARAMS = {
    "ENCUT": 300,
    "ISMEAR": 0,
    "SIGMA": 0.05,
    "kpoints": {"grid": [4, 4, 4], "shift": [0, 0, 0]},
}

SAMPLE_STRUCTURE = {
    "lattice": [
        [5.43, 0.0, 0.0],
        [0.0, 5.43, 0.0],
        [0.0, 0.0, 5.43],
    ],
    "species": ["Si", "Si"],
    "frac_coords": [
        [0.0, 0.0, 0.0],
        [0.25, 0.25, 0.25],
    ],
    "comment": "Si diamond",
}


def _params_writer(params):
    """Mock writer for parameters file."""
    lines = []
    for k, v in sorted(params.items()):
        if isinstance(v, dict):
            continue
        lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"


def _structure_writer(structure):
    """Mock writer for structure file."""
    lines = [structure.get("comment", "")]
    for sp, fc in zip(structure["species"], structure["frac_coords"]):
        lines.append(f"{sp}  {fc[0]:.4f}  {fc[1]:.4f}  {fc[2]:.4f}")
    return "\n".join(lines) + "\n"


def _kpoints_writer(params):
    """Mock writer for kpoints file."""
    kp = params.get("kpoints", {})
    grid = kp.get("grid", [1, 1, 1])
    return f"Automatic\n0\nGamma\n{grid[0]} {grid[1]} {grid[2]}\n"


def _combined_writer(fragment):
    """Mock writer for combined file."""
    params = fragment.get("params") or {}
    structure = fragment.get("structure") or {}
    lines = ["# Combined input"]
    for k, v in sorted(params.items()):
        if isinstance(v, dict):
            continue
        lines.append(f"{k} = {v}")
    if structure:
        lines.append(f"# Structure: {structure.get('comment', '')}")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────


class TestWriteEngineInputs:
    """Tests for the write_engine_inputs orchestrator."""

    def test_basic_multi_file_write(self, tmp_path):
        """Test writing multiple files with different content_roles."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
            input_files=(
                InputFileSpec(
                    filename="PARAMS",
                    content_role="parameters",
                    custom_writer=_params_writer,
                ),
                InputFileSpec(
                    filename="STRUCT",
                    content_role="structure",
                    custom_writer=_structure_writer,
                ),
                InputFileSpec(
                    filename="KPOINTS",
                    content_role="kpoints",
                    custom_writer=_kpoints_writer,
                ),
            ),
        )

        written = write_engine_inputs(
            spec, tmp_path, params=SAMPLE_PARAMS, structure=SAMPLE_STRUCTURE,
        )

        assert len(written) == 3
        assert all(p.exists() for p in written)
        assert all(p.stat().st_size > 0 for p in written)

        # Check filenames
        names = [p.name for p in written]
        assert names == ["PARAMS", "STRUCT", "KPOINTS"]

        # Check parameters content
        params_text = (tmp_path / "PARAMS").read_text()
        assert "ENCUT = 300" in params_text
        assert "ISMEAR = 0" in params_text

        # Check structure content
        struct_text = (tmp_path / "STRUCT").read_text()
        assert "Si diamond" in struct_text
        assert "Si" in struct_text

        # Check kpoints content
        kp_text = (tmp_path / "KPOINTS").read_text()
        assert "4 4 4" in kp_text

    def test_combined_content_role(self, tmp_path):
        """Test combined content_role passes both params and structure."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="keyword-block",
            input_files=(
                InputFileSpec(
                    filename="input.gjf",
                    content_role="combined",
                    custom_writer=_combined_writer,
                ),
            ),
        )

        written = write_engine_inputs(
            spec, tmp_path, params=SAMPLE_PARAMS, structure=SAMPLE_STRUCTURE,
        )

        assert len(written) == 1
        content = written[0].read_text()
        assert "ENCUT = 300" in content
        assert "Si diamond" in content

    def test_optional_file_skipped_when_no_data(self, tmp_path):
        """Test that optional files are skipped when their data is None."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
            input_files=(
                InputFileSpec(
                    filename="PARAMS",
                    content_role="parameters",
                    custom_writer=_params_writer,
                ),
                InputFileSpec(
                    filename="OPTIONAL_STRUCT",
                    content_role="structure",
                    optional=True,
                    custom_writer=_structure_writer,
                ),
            ),
        )

        # No structure provided — optional file should be skipped
        written = write_engine_inputs(
            spec, tmp_path, params=SAMPLE_PARAMS, structure=None,
        )

        assert len(written) == 1
        assert written[0].name == "PARAMS"
        assert not (tmp_path / "OPTIONAL_STRUCT").exists()

    def test_optional_file_written_when_data_present(self, tmp_path):
        """Test that optional files ARE written when their data is present."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
            input_files=(
                InputFileSpec(
                    filename="OPTIONAL_STRUCT",
                    content_role="structure",
                    optional=True,
                    custom_writer=_structure_writer,
                ),
            ),
        )

        written = write_engine_inputs(
            spec, tmp_path, params=None, structure=SAMPLE_STRUCTURE,
        )

        assert len(written) == 1
        assert written[0].name == "OPTIONAL_STRUCT"

    def test_empty_input_files(self, tmp_path):
        """Test spec with no input_files returns empty list."""
        spec = EngineInputSpec(
            engine_family="pyscf",
            syntax_family="python-script",
            input_files=(),
        )

        written = write_engine_inputs(spec, tmp_path)
        assert written == []

    def test_workdir_created(self, tmp_path):
        """Test that workdir is created if it doesn't exist."""
        deep_dir = tmp_path / "a" / "b" / "c"
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
            input_files=(
                InputFileSpec(
                    filename="test.in",
                    content_role="parameters",
                    custom_writer=_params_writer,
                ),
            ),
        )

        written = write_engine_inputs(
            spec, deep_dir, params=SAMPLE_PARAMS,
        )

        assert deep_dir.is_dir()
        assert len(written) == 1

    def test_no_custom_writer_raises(self, tmp_path):
        """Test that missing custom_writer raises NotImplementedError."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
            input_files=(
                InputFileSpec(
                    filename="test.in",
                    content_role="parameters",
                    # No custom_writer
                ),
            ),
        )

        with pytest.raises(NotImplementedError, match="No custom_writer"):
            write_engine_inputs(spec, tmp_path, params=SAMPLE_PARAMS)

    def test_invalid_content_role_raises(self):
        """Test that invalid content_role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid content_role"):
            InputFileSpec(
                filename="test.in",
                content_role="invalid_role",
            )


class TestInputFileSpec:
    """Tests for InputFileSpec validation."""

    def test_valid_content_roles(self):
        """Test all valid content_roles are accepted."""
        for role in ("parameters", "structure", "kpoints", "combined"):
            spec = InputFileSpec(filename="test", content_role=role)
            assert spec.content_role == role

    def test_frozen(self):
        """Test that InputFileSpec is frozen (immutable)."""
        spec = InputFileSpec(filename="test", content_role="parameters")
        with pytest.raises(AttributeError):
            spec.filename = "other"


class TestEngineInputSpec:
    """Tests for EngineInputSpec."""

    def test_frozen(self):
        """Test that EngineInputSpec is frozen."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
        )
        with pytest.raises(AttributeError):
            spec.engine_family = "other"

    def test_defaults(self):
        """Test default values."""
        spec = EngineInputSpec(
            engine_family="test",
            syntax_family="flat-keyval",
        )
        assert spec.input_files == ()
        assert spec.resource_refs == ()
        assert isinstance(spec.ssot_mapping, SSOTMappingSpec)


class TestResourceRefSpec:
    """Tests for ResourceRefSpec."""

    def test_defaults(self):
        """Test default values."""
        ref = ResourceRefSpec(name="potcar")
        assert ref.staging_policy == "copy"
        assert ref.source == ""
        assert ref.description == ""
