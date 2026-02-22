#!/usr/bin/env python3
"""
Download and install pseudo library identification metadata bundle.

This script downloads PSEUDO_FILE_INDEX.json and MANIFEST_PSEUDO_SEED.json
from a GitHub release, verifies checksums, and installs them into
src/quantumvitas/resources/pseudo_libinfo/<tag>/ with a CURRENT pointer file.

Usage:
    python tools/build_pseudo_libinfo_bundle.py --tag assets-2025-12-26
"""

import argparse
import hashlib
import json
import shutil
import ssl
import sys
from pathlib import Path
from typing import Dict, Optional

import certifi


def get_ssl_context() -> ssl.SSLContext:
    """Get SSL context with certifi CA bundle."""
    return ssl.create_default_context(cafile=certifi.where())


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file (raw bytes)."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def download_file(url: str, output_path: Path) -> None:
    """Download a file from URL to output_path."""
    import urllib.request
    import urllib.error
    import socket
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        socket.setdefaulttimeout(120)
        with urllib.request.urlopen(url, context=get_ssl_context()) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            with open(output_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        socket.setdefaulttimeout(None)
    except urllib.error.URLError as e:
        socket.setdefaulttimeout(None)
        raise Exception(f"Failed to download from {url}: {e}") from e
    except Exception as e:
        socket.setdefaulttimeout(None)
        raise Exception(f"Failed to download {url}: {e}") from e


def find_repo_root() -> Path:
    """Find repository root (containing pyproject.toml and src/quantumvitas)."""
    current = Path(__file__).parent.parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() and (current / "src" / "quantumvitas").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root (pyproject.toml + src/quantumvitas)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and install pseudo library identification metadata bundle"
    )
    parser.add_argument(
        "--tag",
        default="assets-2025-12-26",
        help="Release tag (default: assets-2025-12-26)",
    )
    args = parser.parse_args()
    
    tag = args.tag
    repo_root = find_repo_root()
    resources_root = repo_root / "src" / "quantumvitas" / "resources"
    
    # URLs
    base_url = f"https://github.com/QMatSuite/qmatsuite-assets/releases/download/{tag}"
    index_url = f"{base_url}/PSEUDO_FILE_INDEX.json"
    manifest_url = f"{base_url}/MANIFEST_PSEUDO_SEED.json"
    
    # Directories
    temp_download_dir = repo_root / "temp" / "pseudo_libinfo_download" / tag
    bundle_dir = resources_root / "pseudo_libinfo" / tag
    current_file = resources_root / "pseudo_libinfo" / "CURRENT"
    
    print(f"Downloading pseudo libinfo bundle for tag: {tag}")
    print(f"Repository root: {repo_root}")
    print(f"Resources root: {resources_root}")
    print(f"Bundle directory: {bundle_dir}")
    
    # Download files to temp directory
    temp_download_dir.mkdir(parents=True, exist_ok=True)
    index_temp = temp_download_dir / "PSEUDO_FILE_INDEX.json"
    manifest_temp = temp_download_dir / "MANIFEST_PSEUDO_SEED.json"
    
    print(f"\nDownloading PSEUDO_FILE_INDEX.json...")
    try:
        download_file(index_url, index_temp)
        print(f"  ✓ Downloaded {index_temp.stat().st_size} bytes")
    except Exception as e:
        print(f"  ✗ Failed: {e}", file=sys.stderr)
        return 1
    
    print(f"\nDownloading MANIFEST_PSEUDO_SEED.json...")
    try:
        download_file(manifest_url, manifest_temp)
        print(f"  ✓ Downloaded {manifest_temp.stat().st_size} bytes")
    except Exception as e:
        print(f"  ✗ Failed: {e}", file=sys.stderr)
        return 1
    
    # Load and validate index
    print(f"\nValidating downloaded files...")
    try:
        with open(index_temp, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except Exception as e:
        print(f"  ✗ Failed to parse PSEUDO_FILE_INDEX.json: {e}", file=sys.stderr)
        return 1
    
    # Check manifest sha256 from index
    source_manifest = index_data.get("source_manifest", {})
    expected_manifest_sha256 = source_manifest.get("sha256")
    expected_manifest_path = source_manifest.get("path")
    
    if not expected_manifest_sha256:
        print(f"  ✗ PSEUDO_FILE_INDEX.json missing source_manifest.sha256", file=sys.stderr)
        return 1
    
    if expected_manifest_path != "MANIFEST_PSEUDO_SEED.json":
        print(
            f"  ✗ PSEUDO_FILE_INDEX.json source_manifest.path mismatch: "
            f"expected 'MANIFEST_PSEUDO_SEED.json', got {expected_manifest_path!r}",
            file=sys.stderr
        )
        return 1
    
    # Compute manifest sha256 and verify
    computed_manifest_sha256 = compute_sha256(manifest_temp)
    if computed_manifest_sha256 != expected_manifest_sha256:
        print(
            f"  ✗ Manifest SHA256 mismatch:\n"
            f"    Expected: {expected_manifest_sha256}\n"
            f"    Got:      {computed_manifest_sha256}",
            file=sys.stderr
        )
        return 1
    
    print(f"  ✓ Manifest SHA256 matches: {computed_manifest_sha256[:16]}...")
    
    # Compute SHA256SUMS.txt
    index_sha256 = compute_sha256(index_temp)
    manifest_sha256 = compute_sha256(manifest_temp)
    
    sha256sums_content = f"{index_sha256}  PSEUDO_FILE_INDEX.json\n{manifest_sha256}  MANIFEST_PSEUDO_SEED.json\n"
    
    # Install files to bundle directory
    print(f"\nInstalling files to {bundle_dir}...")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    index_final = bundle_dir / "PSEUDO_FILE_INDEX.json"
    manifest_final = bundle_dir / "MANIFEST_PSEUDO_SEED.json"
    sha256sums_final = bundle_dir / "SHA256SUMS.txt"
    
    shutil.copy2(index_temp, index_final)
    shutil.copy2(manifest_temp, manifest_final)
    
    with open(sha256sums_final, "w", encoding="utf-8") as f:
        f.write(sha256sums_content)
    
    print(f"  ✓ Installed PSEUDO_FILE_INDEX.json")
    print(f"  ✓ Installed MANIFEST_PSEUDO_SEED.json")
    print(f"  ✓ Created SHA256SUMS.txt")
    
    # Verify SHA256SUMS.txt after writing
    print(f"\nVerifying SHA256SUMS.txt...")
    with open(sha256sums_final, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    if len(lines) != 2:
        print(f"  ✗ SHA256SUMS.txt has {len(lines)} lines, expected 2", file=sys.stderr)
        return 1
    
    sha256sums_dict: Dict[str, str] = {}
    for line in lines:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            print(f"  ✗ Invalid SHA256SUMS.txt line: {line!r}", file=sys.stderr)
            return 1
        sha256sums_dict[parts[1]] = parts[0]
    
    # Verify each file
    for filename, expected_sha in sha256sums_dict.items():
        file_path = bundle_dir / filename
        if not file_path.exists():
            print(f"  ✗ File listed in SHA256SUMS.txt not found: {filename}", file=sys.stderr)
            return 1
        computed_sha = compute_sha256(file_path)
        if computed_sha != expected_sha:
            print(
                f"  ✗ SHA256 mismatch for {filename}:\n"
                f"    Expected: {expected_sha}\n"
                f"    Got:      {computed_sha}",
                file=sys.stderr
            )
            return 1
    
    print(f"  ✓ SHA256SUMS.txt verified")
    
    # Write CURRENT pointer
    with open(current_file, "w", encoding="utf-8") as f:
        f.write(f"{tag}\n")
    
    print(f"  ✓ Updated CURRENT -> {tag}")
    
    # Report
    print(f"\n✓ Successfully installed pseudo libinfo bundle")
    print(f"\nSummary:")
    print(f"  Tag: {tag}")
    print(f"  Bundle directory: {bundle_dir}")
    print(f"  PSEUDO_FILE_INDEX.json SHA256: {index_sha256[:16]}...")
    print(f"  MANIFEST_PSEUDO_SEED.json SHA256: {manifest_sha256[:16]}...")
    print(f"  CURRENT pointer: {current_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
