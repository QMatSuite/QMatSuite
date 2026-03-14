"""Real engine installation integration tests.

These tests perform actual network operations and/or install engines.
They are gated by explicit environment variables and pytest marks.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
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
    try:
        with urllib.request.urlopen(api_url, context=_ssl_context(), timeout=30) as resp:
            releases = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        pytest.skip(f"GitHub API unavailable: {e}")

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

    try:
        with urllib.request.urlopen(checksums_url, context=_ssl_context(), timeout=30) as resp:
            text = resp.read().decode()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        pytest.skip(f"checksums.txt download failed: {e}")

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


@pytest.mark.integration
@pytest.mark.network
def test_xtb_conda_install_full_pipeline(tmp_path, monkeypatch) -> None:
    """Install xTB via conda, assert key executables exist, then uninstall and assert removal.

    Uses tmp_path (fresh per-run, pytest keeps last 3) so the install dir
    survives the test for post-failure inspection.
    """
    import subprocess

    from qmatsuite.api.engines import install_engine, uninstall_engine

    monkeypatch.setenv("QMATSUITE_HOME", str(tmp_path))

    events: list[dict] = []

    def recorder(**kw):
        events.append(kw)

    result = install_engine("xtb", source="conda", on_progress=recorder)
    installation = result["installation"]
    install_id = installation.get("id") or installation.get("installation_id")

    # ── Post-install: micromamba bootstrap ──────────────────────────────────
    micromamba_bin = tmp_path / "micromamba" / "bin"
    assert micromamba_bin.exists(), f"micromamba bin dir not found (tmp: {tmp_path})"

    # ── Post-install: registry entry ─────────────────────────────────────────
    engines_json = tmp_path / "config" / "engines.json"
    assert engines_json.exists(), f"engines.json not written (tmp: {tmp_path})"

    # ── Post-install: progress events ────────────────────────────────────────
    stages = [e.get("stage") for e in events if "stage" in e]
    assert len(stages) > 0, "No progress stage events received"

    # ── Post-install: xtb binary exists and is executable ────────────────────
    install_path = installation.get("path")
    assert install_path, f"installation dict missing 'path': {installation}"
    xtb_bin = os.path.join(install_path, "xtb")
    assert os.path.isfile(xtb_bin), (
        f"xtb binary not found at {xtb_bin} (install_path={install_path})"
    )
    assert os.access(xtb_bin, os.X_OK), f"xtb binary is not executable: {xtb_bin}"

    # ── Post-install: xtb --version succeeds ─────────────────────────────────
    proc = subprocess.run(
        [xtb_bin, "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0 or "version" in (proc.stdout + proc.stderr).lower(), (
        f"xtb --version failed (rc={proc.returncode}):\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )

    # ── Uninstall ─────────────────────────────────────────────────────────────
    assert install_id, f"No installation id in result: {installation}"
    uninstall_result = uninstall_engine("xtb", install_id)
    assert uninstall_result.get("removed") is True, f"Unexpected uninstall result: {uninstall_result}"

    # ── Post-uninstall: xtb binary is gone ───────────────────────────────────
    assert not os.path.exists(xtb_bin), (
        f"xtb binary still exists after uninstall: {xtb_bin}"
    )

    # ── Post-uninstall: registry entry is removed ────────────────────────────
    import json as _json

    with open(engines_json) as f:
        registry_data = _json.load(f)
    xtb_installs = registry_data.get("engines", {}).get("xtb", {}).get("installations", [])
    ids_remaining = [e.get("id") for e in xtb_installs]
    assert install_id not in ids_remaining, (
        f"Installation '{install_id}' still listed in engines.json after uninstall. "
        f"Remaining: {ids_remaining}"
    )
