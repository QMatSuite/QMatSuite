"""Unit tests for core.engines.micromamba."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from quantumvitas.core.engines import micromamba


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    ("system_name", "machine_name", "expected_asset"),
    [
        ("Darwin", "arm64", "micromamba-osx-arm64"),
        ("Darwin", "x86_64", "micromamba-osx-64"),
        ("Linux", "x86_64", "micromamba-linux-64"),
        ("Windows", "AMD64", "micromamba-win-64.exe"),
    ],
)
def test_platform_asset_detection(
    monkeypatch: pytest.MonkeyPatch,
    system_name: str,
    machine_name: str,
    expected_asset: str,
) -> None:
    monkeypatch.setattr(micromamba.platform, "system", lambda: system_name)
    monkeypatch.setattr(micromamba.platform, "machine", lambda: machine_name)
    asset, _checksum = micromamba._platform_asset()
    assert asset == expected_asset


def test_ensure_micromamba_downloads_and_verifies_sha256(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"micromamba-test-binary"

    monkeypatch.setattr(micromamba, "_platform_asset", lambda: ("micromamba-linux-64", "micromamba-linux-64.sha256"))
    monkeypatch.setattr(micromamba.platform, "system", lambda: "Linux")

    def fake_download(_url: str, output_path: Path) -> None:
        output_path.write_bytes(payload)

    monkeypatch.setattr(micromamba, "_download_binary", fake_download)
    monkeypatch.setattr(micromamba, "_download_text", lambda _url: _sha256_bytes(payload))

    exe = micromamba.ensure_micromamba(tmp_path)
    assert exe.is_file()
    assert exe.read_bytes() == payload
    assert os.access(exe, os.X_OK)


def test_ensure_micromamba_atomic_on_checksum_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"bad-payload"

    monkeypatch.setattr(micromamba, "_platform_asset", lambda: ("micromamba-linux-64", "micromamba-linux-64.sha256"))
    monkeypatch.setattr(micromamba.platform, "system", lambda: "Linux")
    monkeypatch.setattr(micromamba, "_download_binary", lambda _url, output_path: output_path.write_bytes(payload))
    monkeypatch.setattr(micromamba, "_download_text", lambda _url: "0" * 64)

    with pytest.raises(RuntimeError, match="SHA256"):
        micromamba.ensure_micromamba(tmp_path)

    final_path = tmp_path / "micromamba" / "bin" / "micromamba"
    assert not final_path.exists()

    leftovers = list((tmp_path / "micromamba" / "bin").glob(".*"))
    assert leftovers == []


def test_ensure_micromamba_calls_codesign_on_macos(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"macos-binary"
    recorded: list[list[str]] = []

    monkeypatch.setattr(micromamba, "_platform_asset", lambda: ("micromamba-osx-arm64", "micromamba-osx-arm64.sha256"))
    monkeypatch.setattr(micromamba.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(micromamba, "_download_binary", lambda _url, output_path: output_path.write_bytes(payload))
    monkeypatch.setattr(micromamba, "_download_text", lambda _url: _sha256_bytes(payload))

    def fake_run(cmd, **_kwargs):
        recorded.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(micromamba.subprocess, "run", fake_run)

    exe = micromamba.ensure_micromamba(tmp_path)
    assert exe.is_file()
    assert any(call[:4] == ["codesign", "--force", "--sign", "-"] for call in recorded)


def test_create_and_remove_env_delegate_to_run_micromamba(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd, _app_data_dir, **_kwargs):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"envs": []}', stderr="")

    monkeypatch.setattr(micromamba, "run_micromamba", fake_run)

    env_path = micromamba.create_env(
        env_name="xtb-6.7.1",
        packages=["xtb=6.7.1"],
        channels=["conda-forge"],
        app_data_dir=tmp_path,
    )
    assert env_path == tmp_path / "micromamba" / "envs" / "xtb-6.7.1"

    micromamba.remove_env("xtb-6.7.1", tmp_path)

    assert seen[0][:3] == ["create", "--yes", "--name"]
    assert seen[1][:4] == ["env", "remove", "--yes", "--name"]
