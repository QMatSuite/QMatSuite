"""Corpus validation harness for parser/writer coverage measurement.

Dev-only tool. NOT a product feature, NOT a CLI entry point.
Reads corpus files from a directory, runs parse/write/roundtrip, and
produces a CoverageReport.

This module has NO imports from drivers/, core/, engine/, or calculation/.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qmatsuite.inputformat.core import EngineInputSpec
from qmatsuite.inputformat.parser import Diagnostic, ParseResult, parse_engine_inputs
from qmatsuite.inputformat.writer import write_engine_inputs


@dataclass
class CoverageReport:
    """Aggregate coverage report for one engine corpus.

    Attributes:
        engine: Engine family name.
        total_files: Number of corpus entries processed.
        parse_success_rate: Fraction of entries that parsed without error.
        unrecognized_lines: Total unrecognized-line diagnostics across all entries.
        total_lines: Total input lines across all entries.
        worst_files: List of (filename, unrecognized_count) sorted worst-first.
        roundtrip_success_rate: Fraction of entries that pass write→re-parse comparison.
        errors: List of (filename, error_message) for entries that failed.
    """

    engine: str
    total_files: int = 0
    parse_success_rate: float = 0.0
    unrecognized_lines: int = 0
    total_lines: int = 0
    worst_files: list[tuple[str, int]] = field(default_factory=list)
    roundtrip_success_rate: float = 0.0
    errors: list[tuple[str, str]] = field(default_factory=list)


def run_corpus_harness(
    engine: str,
    spec: EngineInputSpec,
    corpus_dir: Path,
    file_glob: str = "*",
) -> CoverageReport:
    """Run full parse/write validation on a corpus of engine input files.

    For each file (or subdirectory for multi-file engines) in corpus_dir:
      1. Attempt parse via parse_engine_inputs.
      2. If parse succeeds and both params+structure are available,
         attempt write via write_engine_inputs.
      3. If write succeeds, re-parse the written output and compare.
      4. Record success/failure and diagnostic counts.

    Args:
        engine: Engine name (for the report).
        spec: EngineInputSpec with custom_parser and custom_writer wired.
        corpus_dir: Directory containing corpus files or subdirectories.
        file_glob: Glob pattern for discovering files in corpus_dir.
            For single-file engines: e.g., "*.abi", "*.inp".
            For multi-file engines: use "*" and the corpus_dir should
            contain subdirectories, each with the expected filenames.

    Returns:
        CoverageReport with aggregate statistics.
    """
    corpus_dir = Path(corpus_dir)
    report = CoverageReport(engine=engine)

    if not corpus_dir.exists():
        return report

    # Determine mode: single-file or multi-file (subdirectory) corpus
    multi_file = len(spec.input_files) > 1
    entries: list[Path] = []

    if multi_file:
        # Each subdirectory in corpus_dir is one calculation
        entries = sorted(p for p in corpus_dir.iterdir() if p.is_dir())
    else:
        # Each matching file in corpus_dir is one calculation
        entries = sorted(corpus_dir.glob(file_glob))
        entries = [p for p in entries if p.is_file()]

    report.total_files = len(entries)
    if report.total_files == 0:
        return report

    parse_successes = 0
    roundtrip_successes = 0
    unrecognized_counts: dict[str, int] = {}

    for entry in entries:
        entry_name = entry.name

        # Set up workdir for parsing
        if multi_file:
            workdir = entry
        else:
            # Create temp workdir with the corpus file renamed to spec filename
            workdir = _setup_single_file_workdir(entry, spec)

        # Count lines
        try:
            for file_spec in spec.input_files:
                fp = workdir / file_spec.filename
                if fp.exists():
                    report.total_lines += len(fp.read_text().splitlines())
        except Exception:
            pass

        # Step 1: Parse
        try:
            result = parse_engine_inputs(spec, workdir)
            parse_successes += 1
        except Exception as e:
            report.errors.append((entry_name, f"parse: {e}"))
            continue

        # Count unrecognized-line diagnostics
        unrec = sum(
            1 for d in result.diagnostics if d.code == "unrecognized_line"
        )
        if unrec > 0:
            unrecognized_counts[entry_name] = unrec

        # Step 2: Write (if we have enough data)
        if result.params or result.structure:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    write_engine_inputs(
                        spec, tmpdir_path,
                        params=result.params,
                        structure=result.structure,
                    )

                    # Step 3: Re-parse and compare
                    try:
                        result2 = parse_engine_inputs(spec, tmpdir_path)
                        if _results_match(result, result2):
                            roundtrip_successes += 1
                        else:
                            report.errors.append(
                                (entry_name, "roundtrip: semantic mismatch")
                            )
                    except Exception as e:
                        report.errors.append(
                            (entry_name, f"re-parse: {e}")
                        )
            except Exception as e:
                report.errors.append((entry_name, f"write: {e}"))
        else:
            # No data to write — still counts as roundtrip success (vacuous)
            roundtrip_successes += 1

        # Clean up temp workdir for single-file mode
        if not multi_file and workdir != entry:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)

    report.parse_success_rate = parse_successes / report.total_files
    report.roundtrip_success_rate = roundtrip_successes / max(parse_successes, 1)
    report.unrecognized_lines = sum(unrecognized_counts.values())
    report.worst_files = sorted(
        unrecognized_counts.items(), key=lambda x: -x[1]
    )

    return report


def _setup_single_file_workdir(
    corpus_file: Path, spec: EngineInputSpec
) -> Path:
    """Create a temp workdir with the corpus file renamed to spec filename.

    For single-file engines, the corpus file (e.g., "si_scf.abi") needs to
    be placed in a directory as the expected filename (e.g., "run.abi").
    """
    import shutil

    tmpdir = Path(tempfile.mkdtemp())
    target_filename = spec.input_files[0].filename
    shutil.copy(corpus_file, tmpdir / target_filename)
    return tmpdir


def _results_match(r1: ParseResult, r2: ParseResult, tol: float = 1e-6) -> bool:
    """Check if two ParseResults are semantically equivalent.

    Simple structural comparison with tolerance for floats.
    """
    if not _dicts_match(r1.params, r2.params, tol):
        return False

    if r1.structure is None and r2.structure is None:
        return True
    if r1.structure is None or r2.structure is None:
        return False
    return _dicts_match(r1.structure, r2.structure, tol)


def _dicts_match(d1: dict, d2: dict, tol: float) -> bool:
    """Recursively compare two dicts with tolerance for floats."""
    if set(d1.keys()) != set(d2.keys()):
        return False

    for key in d1:
        v1, v2 = d1[key], d2[key]
        if not _values_match(v1, v2, tol):
            return False

    return True


def _values_match(v1: Any, v2: Any, tol: float) -> bool:
    """Compare two values with tolerance for floats."""
    if isinstance(v1, float) and isinstance(v2, float):
        return abs(v1 - v2) < tol
    if isinstance(v1, dict) and isinstance(v2, dict):
        return _dicts_match(v1, v2, tol)
    if isinstance(v1, list) and isinstance(v2, list):
        if len(v1) != len(v2):
            return False
        return all(_values_match(a, b, tol) for a, b in zip(v1, v2))
    return v1 == v2
