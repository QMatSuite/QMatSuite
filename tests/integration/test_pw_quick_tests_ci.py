"""CI-friendly quick tests for PW module.

Parsing tests do not require QE; execution tests run pw.x if available.
Tests assume `quantumvitas` is importable (e.g. via `pip install -e .`
or `PYTHONPATH=src`).
"""

from pathlib import Path

import pytest

from quantumvitas.io import QEInputParser, QEInputGenerator
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from tests.core import run_and_verify_step_with_assert
from tests.core.qe_step_runner import get_default_working_dir
from tests.core.test_data import load_test_cases


pytestmark = pytest.mark.quick


class TestPWQuickParsing:
    """Quick parsing tests that don't require QE installation."""

    def test_parse_basic_scf(self):
        content = """&control
    calculation = 'scf'
    prefix = 'test'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
ATOMIC_SPECIES
Si 28.085 Si.pbe-n-rrkjus.UPF
ATOMIC_POSITIONS alat
Si 0.0 0.0 0.0
Si 0.25 0.25 0.25
K_POINTS gamma
"""
        qe_input = QEInputParser.parse_string(content)
        assert qe_input.get_namelist("control") is not None
        assert qe_input.get_namelist("system") is not None

    def test_generate_basic_input(self):
        content = """&control
    calculation = 'scf'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
"""
        qe_input = QEInputParser.parse_string(content)
        generated = QEInputGenerator.generate(qe_input)
        assert "&control" in generated
        assert "calculation = 'scf'" in generated
        assert "&system" in generated
        assert "ecutwfc = 30.0" in generated

    def test_roundtrip_parsing(self):
        original = """&control
    calculation = 'scf'
    prefix = 'si'
/
&system
    ibrav = 0
    nat = 2
    ntyp = 1
    ecutwfc = 30.0
/
"""
        qe_input1 = QEInputParser.parse_string(original)
        generated = QEInputGenerator.generate(qe_input1)
        qe_input2 = QEInputParser.parse_string(generated)

        control1 = qe_input1.get_namelist("control")
        control2 = qe_input2.get_namelist("control")
        assert control1.get("calculation") == control2.get("calculation")
        assert control1.get("prefix") == control2.get("prefix")

        system1 = qe_input1.get_namelist("system")
        system2 = qe_input2.get_namelist("system")
        assert system1.get("ecutwfc") == system2.get("ecutwfc")


class TestPWQuickExecution:
    """Quick PW execution tests that run QE if available."""

    @pytest.fixture(scope="module")
    def qe_engine(self) -> QuantumEspressoEngine:
        config = EngineConfig(name="qe")
        engine = QuantumEspressoEngine(config)
        if not engine.detect_executable("pw.x"):
            raise RuntimeError("pw.x not found. QE installation required.")
        return engine

    @pytest.fixture(scope="module")
    def ci_test_data_dir(self) -> Path:
        project_root = Path(__file__).parent.parent.parent
        ci_test_data = project_root / "tests" / "data"
        if not ci_test_data.exists():
            pytest.skip(f"CI test data not found: {ci_test_data}")
        return ci_test_data

    @pytest.fixture(scope="module")
    def pw_test_cases(self, ci_test_data_dir: Path):
        folder = ci_test_data_dir / "pw_single_tests"
        if not folder.exists():
            pytest.skip(f"PW test folder not found: {folder}")
        return load_test_cases(folder, ci_root=ci_test_data_dir)

    def test_pw_quick_execution(
        self,
        qe_engine: QuantumEspressoEngine,
        ci_test_data_dir: Path,
        pw_test_cases,
    ):
        """
        Run quick PW tests from CI test data using standardized step execution.

        Step type and executable are auto-detected from the QE input via
        `run_and_verify_step_with_assert`, so no executable map is required.
        """
        results = []
        project_root = Path(__file__).parent.parent.parent

        pw_folder = ci_test_data_dir / "pw_single_tests"
        for case in pw_test_cases:
            input_file = case.input_path
            category = pw_folder.name
            test_name = input_file.name

            test_name_slug = test_name.replace(".in", "").replace("/", "_")
            test_working_dir = get_default_working_dir(
                project_root, category, test_name_slug
            )

            try:
                # Don't pass repo_root as project_root - use None for standalone mode
                step_result = run_and_verify_step_with_assert(
                    input_file=input_file,
                    qe_engine=qe_engine,
                    working_dir=test_working_dir,
                    reference_file=None,
                    category=category,
                    timeout=300,
                    project_root=None,  # Use None - pseudo_dir will be working_dir/pseudo
                )
                results.append(
                    {
                        "test": f"{category}/{test_name}",
                        "success": step_result.success,
                        "error": step_result.error,
                        "message": f"Step {step_result.step_type} completed",
                    }
                )
            except AssertionError as e:
                results.append(
                    {
                        "test": f"{category}/{test_name}",
                        "success": False,
                        "error": str(e),
                        "message": "Verification failed",
                    }
                )

        passed = sum(1 for r in results if r["success"])
        failed = len(results) - passed

        print("\n" + "=" * 60)
        print("PW Quick Tests Summary")
        print("=" * 60)
        print(f"Total tests: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print("\nDetails:")
        for r in results:
            status = "✓ PASS" if r["success"] else "✗ FAIL"
            print(f"  {status}: {r['test']}")
            if not r["success"] and r["error"]:
                print(f"    Error: {r['error']}")

        assert passed > 0, f"All {len(results)} PW tests failed. Check errors above."

        if failed > 0:
            print(f"\n⚠️  Warning: {failed} test(s) failed. Possible reasons include:")
            print("  1. Missing pseudopotentials")
            print("  2. System resource constraints")
            print("  3. QE binary issues")

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