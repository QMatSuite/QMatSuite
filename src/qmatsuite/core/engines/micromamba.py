"""Micromamba binary management and environment lifecycle helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import shutil
import ssl
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import certifi

from qmatsuite.core.paths import get_app_data_dir

logger = logging.getLogger(__name__)

MICROMAMBA_REPO_OWNER = "mamba-org"
MICROMAMBA_REPO_NAME = "micromamba-releases"
MICROMAMBA_RELEASE_TAG = "2.5.0-2"


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _micromamba_root(app_data_dir: Path) -> Path:
    return app_data_dir / "micromamba"


def _micromamba_bin_dir(app_data_dir: Path) -> Path:
    return _micromamba_root(app_data_dir) / "bin"


def _micromamba_binary_path(app_data_dir: Path) -> Path:
    name = "micromamba.exe" if platform.system() == "Windows" else "micromamba"
    return _micromamba_bin_dir(app_data_dir) / name


def _platform_asset() -> Tuple[str, str]:
    """Return (asset_name, checksum_asset_name) for the current platform."""
    system = platform.system()
    machine = platform.machine().lower()

    if system == "Darwin":
        if machine in {"arm64", "aarch64"}:
            return "micromamba-osx-arm64", "micromamba-osx-arm64.sha256"
        if machine in {"x86_64", "amd64"}:
            return "micromamba-osx-64", "micromamba-osx-64.sha256"
        raise RuntimeError(f"Unsupported macOS architecture for micromamba: {machine}")

    if system == "Linux":
        if machine in {"x86_64", "amd64"}:
            return "micromamba-linux-64", "micromamba-linux-64.sha256"
        if machine in {"arm64", "aarch64"}:
            return "micromamba-linux-aarch64", "micromamba-linux-aarch64.sha256"
        raise RuntimeError(f"Unsupported Linux architecture for micromamba: {machine}")

    if system == "Windows":
        if machine in {"x86_64", "amd64"}:
            return "micromamba-win-64.exe", "micromamba-win-64.sha256"
        raise RuntimeError(f"Unsupported Windows architecture for micromamba: {machine}")

    raise RuntimeError(f"Unsupported platform for micromamba: {system}/{machine}")


def _asset_url(asset_name: str) -> str:
    return (
        f"https://github.com/{MICROMAMBA_REPO_OWNER}/{MICROMAMBA_REPO_NAME}"
        f"/releases/download/{MICROMAMBA_RELEASE_TAG}/{asset_name}"
    )


def _download_binary(url: str, output_path: Path, on_progress=None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, context=_ssl_context(), timeout=120) as response:
        total = None
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                total = int(content_length)
            except (ValueError, TypeError):
                pass

        downloaded = 0
        chunk_size = 65536  # 64 KB
        with output_path.open("wb") as fh:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(bytes_downloaded=downloaded, bytes_total=total)


def _download_text(url: str) -> str:
    with urllib.request.urlopen(url, context=_ssl_context(), timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")


def _compute_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _parse_sha256(text: str) -> str:
    # Supports both "<hash>" and "<hash> <filename>" formats.
    token = (text or "").strip().split()[0]
    if len(token) != 64:
        raise RuntimeError(f"Invalid SHA256 checksum payload: {text!r}")
    return token.lower()


def _adhoc_sign_macos(binary_path: Path) -> None:
    if platform.system() != "Darwin":
        return

    try:
        result = subprocess.run(
            ["codesign", "--force", "--sign", "-", str(binary_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("codesign not found; skipping ad-hoc signing for %s", binary_path)
        return
    except Exception as exc:
        logger.warning("codesign failed for %s: %s", binary_path, exc)
        return

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        logger.warning("codesign returned %s for %s: %s", result.returncode, binary_path, stderr)


def ensure_micromamba(app_data_dir: Optional[Path] = None, on_progress=None) -> Path:
    """
    Ensure micromamba binary is available; download + verify when missing.

    Returns:
        Path to the micromamba executable.
    """
    app_dir = Path(app_data_dir or get_app_data_dir()).expanduser().resolve()
    micromamba_path = _micromamba_binary_path(app_dir)
    if micromamba_path.is_file():
        return micromamba_path

    bin_dir = micromamba_path.parent
    bin_dir.mkdir(parents=True, exist_ok=True)

    asset_name, checksum_asset = _platform_asset()
    binary_url = _asset_url(asset_name)
    checksum_url = _asset_url(checksum_asset)

    download_path = bin_dir / f".{asset_name}.download"
    staged_path = bin_dir / f".{micromamba_path.name}.staged"

    if on_progress:
        on_progress(stage="Downloading micromamba")

    try:
        _download_binary(binary_url, download_path, on_progress=on_progress)
        checksum_text = _download_text(checksum_url)
        expected_sha256 = _parse_sha256(checksum_text)
        actual_sha256 = _compute_sha256(download_path)
        if actual_sha256.lower() != expected_sha256:
            raise RuntimeError(
                "Micromamba SHA256 verification failed "
                f"(expected {expected_sha256}, got {actual_sha256})"
            )

        download_path.replace(staged_path)
        if platform.system() != "Windows":
            staged_path.chmod(0o755)
        _adhoc_sign_macos(staged_path)
        staged_path.replace(micromamba_path)

    finally:
        for candidate in (download_path, staged_path):
            if candidate.exists():
                try:
                    candidate.unlink()
                except Exception:
                    pass

    return micromamba_path


def run_micromamba(
    cmd: List[str],
    app_data_dir: Path,
    timeout: int = 900,
    on_progress: Optional[Callable[..., None]] = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a micromamba command with `MAMBA_ROOT_PREFIX` configured.

    Args:
        cmd: micromamba subcommand and arguments.
        app_data_dir: Application data directory.
        timeout: Subprocess timeout in seconds (default 900).
        on_progress: Optional callback receiving ``log_line=`` kwargs.
    """
    app_dir = Path(app_data_dir).expanduser().resolve()
    micromamba_exe = ensure_micromamba(app_dir, on_progress=on_progress)
    root_prefix = _micromamba_root(app_dir)
    root_prefix.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["MAMBA_ROOT_PREFIX"] = str(root_prefix)
    env.setdefault("MAMBA_NO_RC", "true")

    full_cmd = [str(micromamba_exe), "-r", str(root_prefix), *cmd]

    if on_progress is not None:
        # Popen + reader-thread: allows streaming output while respecting timeout.
        check = kwargs.pop("check", True)
        # Remove kwargs that conflict with Popen streaming
        kwargs.pop("capture_output", None)
        kwargs.pop("text", None)

        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            **kwargs,
        )
        output_lines: List[str] = []

        def reader():
            assert process.stdout is not None
            for line in process.stdout:
                stripped = line.rstrip("\n")
                output_lines.append(stripped)
                if on_progress:
                    on_progress(log_line=stripped)
            process.stdout.close()

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError(
                f"micromamba timed out after {timeout}s: {' '.join(cmd)}"
            )

        reader_thread.join(timeout=5)

        if check and returncode != 0:
            raise subprocess.CalledProcessError(
                returncode, full_cmd, output="\n".join(output_lines), stderr=""
            )

        return subprocess.CompletedProcess(
            full_cmd, returncode, stdout="\n".join(output_lines), stderr=""
        )

    # Fallback: simple subprocess.run for callers without on_progress
    kwargs.setdefault("check", True)
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)

    try:
        return subprocess.run(full_cmd, env=env, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"micromamba timed out after {timeout}s: {' '.join(cmd)}"
        ) from exc


def create_env(
    env_name: str,
    packages: List[str],
    channels: List[str],
    app_data_dir: Path,
    timeout: int = 900,
    on_progress: Optional[Callable[..., None]] = None,
) -> Path:
    """Create a new micromamba environment and return its path."""
    if not env_name.strip():
        raise ValueError("env_name is required")
    if not packages:
        raise ValueError("packages must not be empty")

    cmd = ["create", "--yes", "--name", env_name]
    for channel in channels:
        if channel:
            cmd.extend(["-c", channel])
    cmd.extend(packages)

    run_micromamba(cmd, app_data_dir, timeout=timeout, on_progress=on_progress)
    return _micromamba_root(app_data_dir) / "envs" / env_name


def remove_env(env_name: str, app_data_dir: Path, timeout: int = 120) -> None:
    """Remove a micromamba environment by name."""
    if not env_name.strip():
        raise ValueError("env_name is required")
    run_micromamba(["env", "remove", "--yes", "--name", env_name], app_data_dir, timeout=timeout)


def list_envs(app_data_dir: Path) -> List[Dict[str, str]]:
    """List micromamba environments as {name, path} objects."""
    result = run_micromamba(["env", "list", "--json"], app_data_dir)
    payload = json.loads(result.stdout or "{}")
    env_paths = payload.get("envs") if isinstance(payload, dict) else None
    if not isinstance(env_paths, list):
        return []

    out: List[Dict[str, str]] = []
    for raw in env_paths:
        path = Path(str(raw))
        out.append({"name": path.name, "path": str(path)})
    return out


__all__ = [
    "MICROMAMBA_RELEASE_TAG",
    "ensure_micromamba",
    "run_micromamba",
    "create_env",
    "remove_env",
    "list_envs",
]
