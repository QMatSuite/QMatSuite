"""Authoring roundtrip test configuration."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integrity: Demo integrity tests (run separately)")
