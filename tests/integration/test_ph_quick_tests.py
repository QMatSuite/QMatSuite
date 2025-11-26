"""
Quick integration tests for PH module.

These tests run selected PH workflows using local CI test data.
They assume `quantumvitas` is importable (e.g. via `pip install -e .` or
`PYTHONPATH=src`).
"""

from pathlib import Path
from typing import Dict, Any, List

import pytest

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.io import QEInputParser, QEInputGenerator
from tests.core.qe_test_utils import parse_jobconfig
from tests.core.qe_step_runner import run_and_verify_step_with_assert, get_default_working_dir


pytestmark = [pytest.mark.quick, pytest.mark.requires_qe]

PH_CI_TESTS: List[Dict[str, Any]] = [
    {"category": "ph_1d", "description": "1D phonon calculation"},
    {"category": "ph_2d", "description": "2D phonon calculation"},
]


@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    """Create a QE engine instance and validate required executables."""
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)

    if not engine.installation.is_valid():
        raise RuntimeError(
            "QE installation not found. Please set QE_HOME/QE_BIN_DIR or install QE."
        )

    required = ["pw.x", "ph.x"]
    missing = [exe for exe in required if not engine.detect_executable(exe)]
    if missing:
        raise RuntimeError(
            "Required QE executables not found: " + ", ".join(missing)
        )

    return engine


@pytest.fixture(scope="module")
def test_data_dir() -> Path:
    """Return local CI test data directory (no dependency on QE test-suite)."""
    root = Path(__file__).parent
    ci_data = root / "ci_test_data"
    if not ci_data.exists():
        raise RuntimeError(f"CI test data not found: {ci_data}")
    if not (ci_data / "ph_1d").exists():
        raise RuntimeError(f"PH data not found: {ci_data / 'ph_1d'}")
    return ci_data


class TestPHQuickTests:
    """Quick PH tests (pw.x -> ph.x -> q2r.x -> matdyn.x workflows)."""

    @pytest.mark.parametrize("test_info", PH_CI_TESTS)
    def test_ph_quick(self, test_info, qe_engine, test_data_dir):
        """
        Run a quick PH workflow using local CI test data.

        Step logic and executable selection are handled centrally by
        `run_and_verify_step_with_assert`, which auto-detects the step type
        from the QE input.
        """
        category = test_info["category"]

        category_dir = test_data_dir / category
        if not category_dir.exists():
            raise RuntimeError(f"Category directory not found: {category_dir}")

        jobconfig_path = test_data_dir / "jobconfig"
        if not jobconfig_path.exists():
            raise RuntimeError(f"jobconfig file not found: {jobconfig_path}")

        all_tests = parse_jobconfig(jobconfig_path, "ph_")
        if category not in all_tests:
            raise RuntimeError(
                f"Category '{category}' not found in jobconfig. "
                f"Available: {list(all_tests.keys())}"
            )

        test_files = all_tests[category]
        if not test_files:
            raise RuntimeError(f"No test files defined for category '{category}'")

        project_root = Path(__file__).parent.parent.parent
        working_dir = get_default_working_dir(project_root, category)

        failed_steps = []
        for i, (input_name, _args) in enumerate(test_files):
            input_path = category_dir / input_name
            if not input_path.exists():
                pytest.fail(f"Input file not found: {input_path}")

            # Optional reference output
            reference_file = None
            ref_dir = category_dir / "reference_out"
            if ref_dir.exists():
                ref_path = ref_dir / f"{input_path.stem}.out"
                if ref_path.exists():
                    reference_file = ref_path

            try:
                run_and_verify_step_with_assert(
                    input_file=input_path,
                    qe_engine=qe_engine,
                    working_dir=working_dir,
                    reference_file=reference_file,
                    category=category,
                    timeout=300,
                    step_index=i + 1,
                )
            except AssertionError as e:
                failed_steps.append(
                    f"{input_name} (step {i + 1}/{len(test_files)}): {e}"
                )
                break

        if failed_steps:
            pytest.fail(
                f"PH test category '{category}' failed: "
                f"{len(failed_steps)}/{len(test_files)} steps failed.\n"
                + "\n".join(failed_steps)
            )


@pytest.mark.quick
def test_ph_basic_parsing():
    """Basic PH input parsing/generation test without QE installation."""
    content = """&inputph
    tr2_ph = 1.0d-12
    prefix = 'test'
    outdir = './'
/
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("inputph") is not None

    generated = QEInputGenerator.generate(qe_input)
    assert "&inputph" in generated
    assert "tr2_ph" in generated

{
  "cells": [],
  "metadata": {
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 2
}