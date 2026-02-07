"""xTB execution fixtures."""

from __future__ import annotations

import shutil

import pytest


@pytest.fixture(scope="session")
def xtb_binary() -> str | None:
    return shutil.which("xtb")


@pytest.fixture(scope="session")
def xtb_available(xtb_binary: str | None) -> bool:
    return xtb_binary is not None
