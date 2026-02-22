"""Tests for the corpus validation harness.

Uses mock specs and small corpus directories to verify harness behaviour.
"""

from __future__ import annotations

import pytest

from qmatsuite.inputformat.core import (
    EngineInputSpec,
    InputFileSpec,
)
from qmatsuite.inputformat.harness import CoverageReport, run_corpus_harness


# ──────────────────────────────────────────────────────────────────────────
# Mock writers/parsers
# ──────────────────────────────────────────────────────────────────────────


def _mock_writer(fragment):
    """Simple writer: dump params as key=value lines."""
    if isinstance(fragment, dict):
        return "\n".join(f"{k} = {v}" for k, v in sorted(fragment.items())) + "\n"
    return ""


def _mock_parser(text):
    """Simple parser: read key=value lines."""
    result = {}
    for line in text.strip().splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            try:
                result[key] = int(val)
            except ValueError:
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = val
    return result


def _failing_parser(text):
    """Parser that always raises."""
    raise ValueError("Intentional parse failure")


def _mock_spec():
    """Return a simple mock EngineInputSpec with parser+writer."""
    return EngineInputSpec(
        engine_family="mock",
        syntax_family="mock",
        input_files=(
            InputFileSpec(
                filename="input.dat",
                content_role="parameters",
                custom_writer=_mock_writer,
                custom_parser=_mock_parser,
            ),
        ),
    )


def _failing_spec():
    """Return a spec with a failing parser."""
    return EngineInputSpec(
        engine_family="mock",
        syntax_family="mock",
        input_files=(
            InputFileSpec(
                filename="input.dat",
                content_role="parameters",
                custom_writer=_mock_writer,
                custom_parser=_failing_parser,
            ),
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────


class TestCorpusHarness:
    """Core harness behaviour."""

    def test_empty_corpus(self, tmp_path):
        """Empty directory returns 0 total_files."""
        report = run_corpus_harness("mock", _mock_spec(), tmp_path, "*.dat")
        assert report.total_files == 0
        assert report.parse_success_rate == 0.0
        assert report.roundtrip_success_rate == 0.0

    def test_nonexistent_corpus_dir(self, tmp_path):
        """Non-existent directory returns empty report."""
        report = run_corpus_harness("mock", _mock_spec(), tmp_path / "nope", "*.dat")
        assert report.total_files == 0

    def test_single_file_success(self, tmp_path):
        """One parseable file -> 100% success."""
        (tmp_path / "test.dat").write_text("ENCUT = 300\nISMEAR = 0\n")

        report = run_corpus_harness("mock", _mock_spec(), tmp_path, "*.dat")

        assert report.total_files == 1
        assert report.parse_success_rate == 1.0
        assert report.roundtrip_success_rate == 1.0
        assert report.errors == []

    def test_multiple_files(self, tmp_path):
        """Multiple files all parse."""
        for i in range(3):
            (tmp_path / f"test{i}.dat").write_text(f"KEY{i} = {i}\n")

        report = run_corpus_harness("mock", _mock_spec(), tmp_path, "*.dat")

        assert report.total_files == 3
        assert report.parse_success_rate == 1.0
        assert report.roundtrip_success_rate == 1.0

    def test_parse_failure_counted(self, tmp_path):
        """File that raises during parse reduces parse_success_rate."""
        (tmp_path / "good.dat").write_text("KEY = 1\n")
        (tmp_path / "bad.dat").write_text("KEY = 2\n")

        # Use a spec where parser always fails for the second file
        report = run_corpus_harness("mock", _failing_spec(), tmp_path, "*.dat")

        assert report.total_files == 2
        assert report.parse_success_rate == 0.0  # both fail
        assert len(report.errors) == 2

    def test_worst_files_empty_when_no_unrecognized(self, tmp_path):
        """No unrecognized lines -> empty worst_files."""
        (tmp_path / "test.dat").write_text("ENCUT = 300\n")

        report = run_corpus_harness("mock", _mock_spec(), tmp_path, "*.dat")
        assert report.worst_files == []
        assert report.unrecognized_lines == 0

    def test_report_engine_name(self, tmp_path):
        """Report carries the engine name."""
        report = run_corpus_harness("vasp", _mock_spec(), tmp_path, "*.dat")
        assert report.engine == "vasp"

    def test_total_lines_counted(self, tmp_path):
        """Total input lines are counted."""
        (tmp_path / "a.dat").write_text("K1 = 1\nK2 = 2\nK3 = 3\n")
        (tmp_path / "b.dat").write_text("K4 = 4\n")

        report = run_corpus_harness("mock", _mock_spec(), tmp_path, "*.dat")
        assert report.total_lines == 4  # 3 + 1


class TestCoverageReport:
    """CoverageReport defaults."""

    def test_defaults(self):
        r = CoverageReport(engine="test")
        assert r.total_files == 0
        assert r.parse_success_rate == 0.0
        assert r.roundtrip_success_rate == 0.0
        assert r.unrecognized_lines == 0
        assert r.worst_files == []
        assert r.errors == []


class TestHarnessWithRealEngine:
    """Test harness with a real engine spec (VASP curated samples)."""

    def test_vasp_curated_samples(self, tmp_path):
        """Run harness on VASP curated samples directory."""
        from qmatsuite.drivers.vasp.inputspec import get_vasp_input_spec
        import shutil

        spec = get_vasp_input_spec()
        samples_dir = tmp_path / "corpus" / "si_scf"
        samples_dir.mkdir(parents=True)

        # Copy curated samples
        vasp_samples = (
            __import__("pathlib").Path(__file__).parent / "samples" / "vasp"
        )
        shutil.copy(vasp_samples / "si_scf" / "INCAR", samples_dir / "INCAR")
        shutil.copy(vasp_samples / "si_scf" / "POSCAR", samples_dir / "POSCAR")
        shutil.copy(vasp_samples / "si_scf" / "KPOINTS", samples_dir / "KPOINTS")

        corpus_dir = tmp_path / "corpus"
        report = run_corpus_harness("vasp", spec, corpus_dir)

        assert report.total_files == 1
        assert report.parse_success_rate == 1.0
        assert report.roundtrip_success_rate == 1.0
        assert report.errors == []
