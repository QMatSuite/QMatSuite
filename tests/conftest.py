"""Pytest configuration and fixtures for quick tests.

Quick tests are fast, focused tests that run in CI.
Imports assume `quantumvitas` is importable (e.g. via `pip install -e .`
or `PYTHONPATH=src`).
"""

from pathlib import Path

import pytest


@pytest.fixture
def project_root_path() -> Path:
    """Return project root path."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_input_file(project_root_path: Path):
    """Return path to a sample QE input file for testing.

    Prefer a small local CI test file; fall back to tutorial examples only
    if they have already been downloaded.
    """
    project_root = project_root_path

    # Prefer local CI test data
    local_test_file = (
        project_root
        / "tests"
        / "integration"
        / "ci_test_data"
        / "pw_scf"
        / "scf-cg.in"
    )
    if local_test_file.exists():
        return local_test_file

    # Fallback: use tutorial examples if already downloaded (do not auto-download)
    tutorial_dir = project_root / "temp" / "downloads" / "qe_tutorial_examples"
    if tutorial_dir.exists() and (tutorial_dir / ".git").exists():
        example_file = tutorial_dir / "0_Si_scf" / "si.scf.in"
        if example_file.exists():
            return example_file

    # Nothing suitable found
    return None


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "quick: Quick tests that run in CI")


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    """Automatically mark tests based on their location."""
    for item in items:
        path_str = str(item.fspath)
        if "tests/" in path_str and "extended-tests" not in path_str:
            item.add_marker(pytest.mark.quick)
        if "extended-tests" in path_str:
            item.add_marker(pytest.mark.extended)


@pytest.fixture(autouse=True)
def cleanup_temp_outdir(project_root_path: Path):
    """Automatically clean up temp/outdir after each test."""
    import shutil

    temp_outdir = project_root_path / "temp" / "outdir"

    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass

    yield

    if temp_outdir.exists():
        try:
            shutil.rmtree(temp_outdir)
        except Exception:
            pass

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