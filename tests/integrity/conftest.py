"""Integrity test suite configuration.

These tests are excluded from default pytest collection (C4 constraint).
Run explicitly: python -m pytest tests/integrity/backend/ -v --tb=short
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integrity: Demo integrity tests (run separately)")
