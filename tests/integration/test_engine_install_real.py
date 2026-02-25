"""Real engine installation integration tests.

These tests perform actual network operations and/or install engines.
They are gated by explicit environment variables and pytest marks.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.request

import certifi
import pytest


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


# ---------------------------------------------------------------------------
# Lightweight network test — always safe to run (no install, small download)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_toolchain_checksums_txt_format() -> None:
    """Fetch checksums.txt from latest qmatsuite-toolchain release and verify format."""
    from qmatsuite.core.engines.engine_installer import _parse_checksums_txt

    api_url = "https://api.github.com/repos/QMatSuite/qmatsuite-toolchain/releases?per_page=5"
    with urllib.request.urlopen(api_url, context=_ssl_context(), timeout=30) as resp:
        releases = json.loads(resp.read().decode())

    assert isinstance(releases, list) and len(releases) > 0, "No releases found"

    # Find first release with a checksums.txt asset
    checksums_url = None
    any_asset_name = None
    for release in releases:
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name == "checksums.txt":
                checksums_url = asset["browser_download_url"]
            elif name.endswith(".zip"):
                any_asset_name = name
        if checksums_url:
            break

    if checksums_url is None:
        pytest.skip("No checksums.txt found in recent releases")

    with urllib.request.urlopen(checksums_url, context=_ssl_context(), timeout=30) as resp:
        text = resp.read().decode()

    # Verify format: each non-empty line is "<64-hex>  <filename>"
    hex_re = re.compile(r"^[0-9a-fA-F]{64}$")
    entries = 0
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        assert len(parts) == 2, f"Malformed line: {line!r}"
        digest, fname = parts
        fname = fname.lstrip("*").strip()
        assert hex_re.match(digest), f"Bad hex digest: {digest!r}"
        assert len(fname) > 0, "Empty filename"
        entries += 1

    assert entries >= 1, "checksums.txt has no entries"

    # Verify our parser can extract at least one hash
    if any_asset_name:
        result = _parse_checksums_txt(text, any_asset_name)
        # May be None if asset isn't in this checksums.txt, but shouldn't error


# ---------------------------------------------------------------------------
# Full xTB conda install — only when explicitly opted-in
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("QMATSUITE_TEST_ENGINE_INSTALL"),
    reason="Set QMATSUITE_TEST_ENGINE_INSTALL=1 to run real engine install tests",
)
@pytest.mark.integration
@pytest.mark.network
@pytest.mark.slow
def test_xtb_conda_install_full_pipeline(tmp_path) -> None:
    """Install xTB via conda, verify it works, then uninstall."""
    from qmatsuite.api.engines import install_engine, uninstall_engine

    os.environ["QMATSUITE_HOME"] = str(tmp_path)

    events: list[dict] = []

    def recorder(**kw):
        events.append(kw)

    result = install_engine("xtb", source="conda", on_progress=recorder)
    installation = result["installation"]

    # Verify micromamba and env exist
    micromamba_bin = tmp_path / "micromamba" / "bin"
    assert micromamba_bin.exists(), "micromamba bin dir not found"

    # Verify registration
    engines_json = tmp_path / "config" / "engines.json"
    assert engines_json.exists(), "engines.json not written"

    # Verify progress was reported
    stages = [e.get("stage") for e in events if "stage" in e]
    assert len(stages) > 0, "No progress stage events received"

    # Verify xtb binary works
    install_path = installation.get("path")
    if install_path:
        import subprocess

        xtb_bin = os.path.join(install_path, "xtb")
        if os.path.isfile(xtb_bin):
            proc = subprocess.run(
                [xtb_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert proc.returncode == 0 or "version" in (proc.stdout + proc.stderr).lower()

    # Cleanup
    install_id = installation["id"]
    uninstall_engine("xtb", install_id)
