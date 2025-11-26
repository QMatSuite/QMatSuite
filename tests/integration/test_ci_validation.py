"""Validation helpers to ensure CI tests work correctly.

This module can be executed directly (``python -m tests.integration.test_ci_validation``)
*after* the package is importable (e.g. via ``pip install -e .`` or
appropriate ``PYTHONPATH``).
"""

import sys
from pathlib import Path


def test_imports() -> None:
    """Test that core imports work."""
    from quantumvitas.io import QEInputParser, QEInputGenerator

    _ = QEInputParser, QEInputGenerator  # silence linters
    print("✅ Core imports work")


def test_basic_parsing() -> None:
    """Test basic parsing (CI-friendly)."""
    from quantumvitas.io import QEInputParser

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
"""
    qe_input = QEInputParser.parse_string(content)
    assert qe_input.get_namelist("control") is not None
    assert qe_input.get_namelist("system") is not None
    print("✅ Basic parsing works")


def test_stats_file() -> None:
    """Test that stats file can be loaded (if present)."""
    stats_file = Path(__file__).parent.parent.parent / "extended-tests" / "pw_test_stats.json"
    if stats_file.exists():
        import json

        with open(stats_file) as f:
            data = json.load(f)
        selected = data.get("selected_ci_tests", [])
        if selected:
            print(f"✅ Stats file loaded: {len(selected)} tests")
            print(
                f"   First test: {selected[0]['category']}"
                f"/{selected[0]['test_file']}"
            )
        else:
            print("⚠️  Stats file exists but no selected tests")
    else:
        print("⚠️  Stats file not found (QE tests may skip in some environments)")


def main() -> int:
    """Run all validation checks and print a summary."""
    print("=" * 60)
    print("CI Test Validation")
    print("=" * 60)
    print()

    results = []
    all_passed = True

    for name, func in [
        ("Imports", test_imports),
        ("Basic Parsing", test_basic_parsing),
        ("Stats File", test_stats_file),
    ]:
        try:
            func()
            results.append((name, True))
        except Exception as exc:  # pragma: no cover - diagnostic output only
            print(f"❌ {name} error: {exc}")
            results.append((name, False))
            all_passed = False

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s}: {status}")

    print()
    if all_passed:
        print("✅ All validations passed - CI tests should work")
        return 0

    print("❌ Some validations failed")
    return 1


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())

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