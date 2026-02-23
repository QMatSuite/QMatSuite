"""Build a zstd-compressed runtime archive from an existing environment prefix.

Expected environment variables:
  RUNTIME_ENV_PREFIX: path to the environment directory to archive
  RUNTIME_PLATFORM: platform suffix used in default archive name
  RUNTIME_ARCHIVE: optional explicit output archive path
"""

from __future__ import annotations

import os
import tarfile
from pathlib import Path

try:
    import zstandard as zstd
except ImportError as exc:  # pragma: no cover - CI/runtime setup guard
    raise SystemExit("zstandard is required: pip install zstandard") from exc


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def main() -> int:
    env_prefix = os.environ.get("RUNTIME_ENV_PREFIX", "").strip()
    if not env_prefix:
        raise SystemExit("RUNTIME_ENV_PREFIX is required")

    env_dir = Path(env_prefix).resolve()
    if not env_dir.is_dir():
        raise SystemExit(f"Environment path does not exist: {env_dir}")

    platform_name = os.environ.get("RUNTIME_PLATFORM", "runtime").strip() or "runtime"
    archive_name = os.environ.get("RUNTIME_ARCHIVE", "").strip() or f"runtime-{platform_name}.tar.zst"
    out_path = Path(archive_name).resolve()

    tmp_tar = out_path.with_suffix("")
    if tmp_tar.suffix == ".zst":
        tmp_tar = tmp_tar.with_suffix("")
    tmp_tar = tmp_tar.with_suffix(".tar")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    uncompressed_size = _dir_size_bytes(env_dir)

    with tarfile.open(tmp_tar, "w") as tf:
        tf.add(env_dir, arcname=".")

    cctx = zstd.ZstdCompressor(level=19, threads=-1)
    with tmp_tar.open("rb") as src, out_path.open("wb") as dst:
        cctx.copy_stream(src, dst)

    tmp_tar.unlink(missing_ok=True)

    compressed_size = out_path.stat().st_size
    print(f"runtime env: {env_dir}")
    print(f"archive: {out_path}")
    print(f"uncompressed bytes: {uncompressed_size}")
    print(f"compressed bytes: {compressed_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
