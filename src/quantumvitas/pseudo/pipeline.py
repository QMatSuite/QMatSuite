"""5-step pseudo library download-install pipeline.

Steps:
    1. RESOLVE  — map (library, variant, version) → ArchiveInfo; check installed/cached
    2. DOWNLOAD — GitHub → temp dir → verify SHA256 → move to seed cache
    3. EXTRACT  — seed → temp dir → handle tar.gz/tgz/tar/zip → flatten
    4. INSTALL  — copy UPFs + companions → library dir → write head.json
    5. VALIDATE — count UPFs > 0, spot-check sizes, verify head.json
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

from quantumvitas.core.paths import (
    home_pseudo_libraries_dir,
    home_pseudo_seeds_dir,
    tmp_downloads_dir,
)
from quantumvitas.core.pseudo_config import (
    compute_sha256,
    download_github_release_asset,
)
from quantumvitas.pseudo.registry import ArchiveInfo, PseudoRegistry

logger = logging.getLogger(__name__)

# UPF file extensions (case-insensitive matching during extraction)
_UPF_EXTENSIONS = {".upf"}


def _is_upf(name: str) -> bool:
    return Path(name).suffix.lower() in _UPF_EXTENSIONS


def _extract_archive(archive_path: Path, dest_dir: Path) -> int:
    """Extract UPF files from an archive into *dest_dir* (flat).

    Supports .tar.gz, .tgz, .tar, and .zip formats.
    Returns the number of UPF files extracted.
    """
    count = 0
    name = archive_path.name.lower()

    if name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.isfile() and _is_upf(member.name):
                    flat_name = Path(member.name).name
                    extracted = tar.extractfile(member)
                    if extracted:
                        (dest_dir / flat_name).write_bytes(extracted.read())
                        count += 1
    elif name.endswith(".tar"):
        with tarfile.open(archive_path, "r:") as tar:
            for member in tar.getmembers():
                if member.isfile() and _is_upf(member.name):
                    flat_name = Path(member.name).name
                    extracted = tar.extractfile(member)
                    if extracted:
                        (dest_dir / flat_name).write_bytes(extracted.read())
                        count += 1
    elif name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                if not info.is_dir() and _is_upf(info.filename):
                    flat_name = Path(info.filename).name
                    data = zf.read(info)
                    (dest_dir / flat_name).write_bytes(data)
                    count += 1
    else:
        raise ValueError(f"Unsupported archive format: {archive_path.name}")

    return count


def download_and_install(
    library: str = "sssp",
    variant: str = "",
    version: str = "latest",
) -> dict[str, Any]:
    """Run the full 5-step pipeline to download and install a pseudo library.

    Returns a result dict with ``success``, ``library_key``, ``variant``,
    ``version``, ``install_dir``, ``upf_count``, ``messages``, and ``errors``.
    """
    result: dict[str, Any] = {
        "success": False,
        "library_key": library,
        "variant": "",
        "version": "",
        "install_dir": "",
        "upf_count": 0,
        "messages": [],
        "errors": [],
    }

    # ---- STEP 1: RESOLVE ----
    try:
        registry = PseudoRegistry()
        info: ArchiveInfo = registry.resolve(library, variant, version)
    except (ValueError, FileNotFoundError) as exc:
        result["errors"].append(f"[RESOLVE] {exc}")
        return result

    result["library_key"] = info.library_key
    result["variant"] = info.variant
    result["version"] = info.version
    result["messages"].append(
        f"[RESOLVE] {info.library_key}/{info.variant}/{info.version} → "
        f"{info.filename} ({info.size_bytes / 1024 / 1024:.1f} MB)"
    )

    libraries_root = home_pseudo_libraries_dir()
    seeds_root = home_pseudo_seeds_dir()
    install_dir = libraries_root / info.dir_name / info.variant / info.version
    result["install_dir"] = str(install_dir)

    # Check if already installed
    if install_dir.exists():
        upfs = [f for f in install_dir.iterdir() if _is_upf(f.name)]
        head = install_dir / "head.json"
        if upfs and head.exists():
            result["success"] = True
            result["upf_count"] = len(upfs)
            result["messages"].append(
                f"[RESOLVE] Already installed ({len(upfs)} UPFs) at {install_dir}"
            )
            return result

    # Check if seed is cached
    seed_path = seeds_root / info.filename
    seed_cached = seed_path.exists() and compute_sha256(seed_path) == info.sha256

    # ---- STEP 2: DOWNLOAD ----
    if not seed_cached:
        dl_dir: Path | None = None
        try:
            dl_dir = tmp_downloads_dir() / f"pseudo_dl_{uuid.uuid4().hex[:12]}"
            dl_dir.mkdir(parents=True, exist_ok=True)
            dl_file = dl_dir / info.filename

            result["messages"].append(
                f"[DOWNLOAD] Downloading {info.filename} from GitHub..."
            )
            download_github_release_asset(
                asset_name=info.filename,
                output_path=dl_file,
                expected_size=info.size_bytes,
                expected_sha256=info.sha256,
            )
            result["messages"].append(
                f"[DOWNLOAD] Verified SHA256 {info.sha256[:16]}..."
            )

            # Move to seed cache
            seeds_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dl_file), str(seed_path))
            seed_cached = True
            result["messages"].append(f"[DOWNLOAD] Cached seed at {seed_path.name}")

            # Download companions (e.g. SSSP cutoffs JSON)
            for comp_name in info.companions:
                comp_seed = seeds_root / comp_name
                if comp_seed.exists():
                    continue
                comp_dl = dl_dir / comp_name
                try:
                    download_github_release_asset(
                        asset_name=comp_name,
                        output_path=comp_dl,
                    )
                    shutil.move(str(comp_dl), str(comp_seed))
                    result["messages"].append(
                        f"[DOWNLOAD] Companion {comp_name} cached"
                    )
                except Exception as exc:
                    result["messages"].append(
                        f"[DOWNLOAD] Warning: companion {comp_name} failed: {exc}"
                    )
        except Exception as exc:
            result["errors"].append(f"[DOWNLOAD] {exc}")
            return result
        finally:
            if dl_dir and dl_dir.exists():
                shutil.rmtree(dl_dir, ignore_errors=True)
    else:
        result["messages"].append("[DOWNLOAD] Seed already cached, skipping download")

    # ---- STEP 3: EXTRACT ----
    ext_dir: Path | None = None
    try:
        ext_dir = tmp_downloads_dir() / f"pseudo_ext_{uuid.uuid4().hex[:12]}"
        ext_dir.mkdir(parents=True, exist_ok=True)

        upf_count = _extract_archive(seed_path, ext_dir)
        if upf_count == 0:
            result["errors"].append(
                f"[EXTRACT] No UPF files found in {info.filename}"
            )
            return result
        result["messages"].append(f"[EXTRACT] Extracted {upf_count} UPF files")

    except Exception as exc:
        result["errors"].append(f"[EXTRACT] {exc}")
        return result

    # ---- STEP 4: INSTALL ----
    try:
        install_dir.mkdir(parents=True, exist_ok=True)

        # Copy UPFs from ext_dir to install_dir
        installed = 0
        for upf_file in ext_dir.iterdir():
            if _is_upf(upf_file.name):
                shutil.copy2(str(upf_file), str(install_dir / upf_file.name))
                installed += 1
        result["upf_count"] = installed

        # Copy companions (cutoffs JSON) if present
        for comp_name in info.companions:
            comp_seed = seeds_root / comp_name
            if comp_seed.exists():
                shutil.copy2(str(comp_seed), str(install_dir / comp_name))
                result["messages"].append(f"[INSTALL] Companion {comp_name} installed")

        # Write head.json (Windows-friendly, no symlinks)
        head_data = {
            "library_key": info.library_key,
            "dir_name": info.dir_name,
            "variant": info.variant,
            "version": info.version,
            "upf_count": installed,
            "source_archive": info.filename,
            "sha256": info.sha256,
        }
        head_path = install_dir / "head.json"
        head_path.write_text(json.dumps(head_data, indent=2))

        # Also write head.json at the library root (for resolution scanning)
        lib_root_head = libraries_root / info.dir_name / "head.json"
        lib_root_head.write_text(
            json.dumps(
                {"variant": info.variant, "version": info.version}, indent=2
            )
        )

        result["messages"].append(
            f"[INSTALL] {installed} UPFs → {install_dir}"
        )
    except Exception as exc:
        result["errors"].append(f"[INSTALL] {exc}")
        return result
    finally:
        if ext_dir and ext_dir.exists():
            shutil.rmtree(ext_dir, ignore_errors=True)

    # ---- STEP 5: VALIDATE ----
    try:
        upfs = [f for f in install_dir.iterdir() if _is_upf(f.name)]
        if len(upfs) == 0:
            result["errors"].append("[VALIDATE] No UPF files in install directory")
            return result

        # Spot-check: at least 3 files > 1KB (or all if fewer)
        check_files = upfs[:3] if len(upfs) >= 3 else upfs
        for f in check_files:
            if f.stat().st_size < 1024:
                result["messages"].append(
                    f"[VALIDATE] Warning: {f.name} is only {f.stat().st_size} bytes"
                )

        if not head_path.exists():
            result["errors"].append("[VALIDATE] head.json missing after install")
            return result

        result["messages"].append(
            f"[VALIDATE] OK — {len(upfs)} UPFs, head.json present"
        )
    except Exception as exc:
        result["errors"].append(f"[VALIDATE] {exc}")
        return result

    result["success"] = True
    return result
