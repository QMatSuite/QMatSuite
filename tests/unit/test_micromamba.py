"""Unit tests for core.engines.micromamba."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from qmatsuite.core.engines import micromamba


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

    def fake_download(_url: str, output_path: Path, on_progress=None) -> None:
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
    monkeypatch.setattr(micromamba, "_download_binary", lambda _url, output_path, on_progress=None: output_path.write_bytes(payload))
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
    monkeypatch.setattr(micromamba, "_download_binary", lambda _url, output_path, on_progress=None: output_path.write_bytes(payload))
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


# ---- Fix 3: timeout tests ----


def test_run_micromamba_passes_timeout_to_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_micromamba passes timeout= to subprocess.run."""
    fake_exe = tmp_path / "bin" / "micromamba"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_text("#!/bin/sh\necho ok")
    fake_exe.chmod(0o755)
    monkeypatch.setattr(micromamba, "ensure_micromamba", lambda *a, **kw: fake_exe)

    captured: dict = {}

    def spy_run(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(micromamba.subprocess, "run", spy_run)

    micromamba.run_micromamba(["env", "list"], tmp_path, timeout=900)
    assert captured["timeout"] == 900


def test_run_micromamba_raises_on_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_micromamba re-raises TimeoutExpired as RuntimeError."""
    fake_exe = tmp_path / "bin" / "micromamba"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_text("#!/bin/sh\necho ok")
    fake_exe.chmod(0o755)
    monkeypatch.setattr(micromamba, "ensure_micromamba", lambda *a, **kw: fake_exe)

    def exploding_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="micromamba", timeout=900)

    monkeypatch.setattr(micromamba.subprocess, "run", exploding_run)

    with pytest.raises(RuntimeError, match="timed out after 900s"):
        micromamba.run_micromamba(["create", "--yes"], tmp_path, timeout=900)


def test_create_env_passes_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_env forwards timeout to run_micromamba."""
    captured: dict = {}

    def fake_run(cmd, app_data_dir, timeout=900, **kwargs):
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(micromamba, "run_micromamba", fake_run)

    micromamba.create_env("test-env", ["xtb"], ["conda-forge"], tmp_path, timeout=600)
    assert captured["timeout"] == 600


# ---- Fix 1: progress callback tests ----


def test_download_binary_progress_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """micromamba._download_binary fires on_progress with bytes_downloaded/bytes_total."""
    fake_data = b"x" * 200_000

    class FakeResponse:
        class headers:
            @staticmethod
            def get(key):
                if key == "Content-Length":
                    return str(len(fake_data))
                return None

        def read(self, size=-1):
            chunk = self._remaining[:size]
            self._remaining = self._remaining[size:]
            return chunk

        def __enter__(self):
            self._remaining = fake_data
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        micromamba.urllib.request, "urlopen",
        lambda url, context=None, timeout=None: FakeResponse(),
    )

    events: list[dict] = []
    out = tmp_path / "download.bin"
    micromamba._download_binary("https://example.com/file", out, on_progress=lambda **kw: events.append(kw))

    assert out.read_bytes() == fake_data
    assert len(events) > 0
    assert events[-1]["bytes_downloaded"] == len(fake_data)
    assert events[-1]["bytes_total"] == len(fake_data)
