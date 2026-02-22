"""
QE Seed Management.

This module handles QE seed archives for offline installation and disaster recovery.
Seeds are stored under .qmatsuite/seeds/qe/<seed_id>/.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tarfile
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, Any

from qmatsuite.core.paths import (
    home_qe_seeds_dir,
    home_qe_engines_dir,
    tmp_downloads_dir,
    tmp_unpack_dir,
)

logger = logging.getLogger(__name__)


@dataclass
class QESeedManifest:
    """QE seed manifest."""
    seed_id: str
    engine_id: str
    archive_filename: str
    sha256: str
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QESeedManifest:
        """Create from dictionary."""
        return cls(**data)


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_seed_dir(seed_id: str) -> Path:
    """Get directory for a specific seed."""
    seeds_dir = home_qe_seeds_dir()
    seed_dir = seeds_dir / seed_id
    seed_dir.mkdir(parents=True, exist_ok=True)
    return seed_dir


def get_seed_manifest_path(seed_id: str) -> Path:
    """Get path to seed manifest file."""
    seed_dir = get_seed_dir(seed_id)
    return seed_dir / "manifest.json"


def load_seed_manifest(seed_id: str) -> Optional[QESeedManifest]:
    """Load seed manifest."""
    manifest_path = get_seed_manifest_path(seed_id)
    if not manifest_path.exists():
        return None
    
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return QESeedManifest.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to load seed manifest {seed_id}: {e}")
        return None


def save_seed_manifest(manifest: QESeedManifest) -> None:
    """Save seed manifest."""
    manifest_path = get_seed_manifest_path(manifest.seed_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)


def verify_seed_archive(archive_path: Path, expected_sha256: str) -> bool:
    """Verify seed archive SHA256."""
    actual_sha256 = calculate_sha256(archive_path)
    return actual_sha256 == expected_sha256


def install_engine_from_seed(
    seed_id: str,
    engine_id: Optional[str] = None,
) -> Path:
    """
    Install QE engine from seed.
    
    Args:
        seed_id: Seed ID
        engine_id: Optional engine ID (defaults to seed's engine_id)
        
    Returns:
        Path to installed engine directory
        
    Raises:
        FileNotFoundError: If seed not found
        ValueError: If verification fails
    """
    manifest = load_seed_manifest(seed_id)
    if not manifest:
        raise FileNotFoundError(f"Seed manifest not found for seed_id: {seed_id}")
    
    if engine_id is None:
        engine_id = manifest.engine_id
    
    seed_dir = get_seed_dir(seed_id)
    archive_path = seed_dir / manifest.archive_filename
    
    if not archive_path.exists():
        raise FileNotFoundError(f"Seed archive not found: {archive_path}")
    
    # Verify archive
    if not verify_seed_archive(archive_path, manifest.sha256):
        raise ValueError(f"Seed archive verification failed for {seed_id}")
    
    # Extract to temporary directory first
    unpack_dir = tmp_unpack_dir() / f"qe_install_{engine_id}"
    unpack_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Extract archive
        if archive_path.suffix in [".gz", ".bz2", ".xz"] or ".tar" in archive_path.suffixes:
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(unpack_dir)
        elif archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(unpack_dir)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
        
        # Find the extracted QE installation (look for bin/pw.x)
        extracted_root = None
        for root_dir in unpack_dir.iterdir():
            if (root_dir / "bin" / "pw.x").exists() or (root_dir / "bin" / "pw.x.exe").exists():
                extracted_root = root_dir
                break
        
        if not extracted_root:
            raise ValueError(f"Could not find QE installation in extracted archive")
        
        # Install to engines directory
        engines_dir = home_qe_engines_dir()
        engine_dir = engines_dir / engine_id
        if engine_dir.exists():
            shutil.rmtree(engine_dir)
        
        shutil.move(str(extracted_root), str(engine_dir))
        
        logger.info(f"Installed QE engine {engine_id} from seed {seed_id}")
        return engine_dir
    
    finally:
        # Cleanup temporary extraction directory
        if unpack_dir.exists():
            shutil.rmtree(unpack_dir, ignore_errors=True)


def save_downloaded_seed(
    archive_path: Path,
    seed_id: str,
    engine_id: str,
    source_url: Optional[str] = None,
) -> QESeedManifest:
    """
    Save a downloaded archive as a seed.
    
    Args:
        archive_path: Path to downloaded archive
        seed_id: Seed ID
        engine_id: Engine ID
        source_url: Optional source URL
        
    Returns:
        QESeedManifest for the saved seed
    """
    # Calculate SHA256
    sha256 = calculate_sha256(archive_path)
    
    # Copy to seed directory
    seed_dir = get_seed_dir(seed_id)
    seed_archive_path = seed_dir / archive_path.name
    
    if seed_archive_path.exists():
        # Verify it's the same file
        existing_sha256 = calculate_sha256(seed_archive_path)
        if existing_sha256 != sha256:
            raise ValueError(f"Seed archive already exists with different SHA256: {seed_id}")
        logger.debug(f"Seed archive already exists: {seed_archive_path}")
    else:
        shutil.copy2(archive_path, seed_archive_path)
    
    # Create manifest
    from datetime import datetime
    manifest = QESeedManifest(
        seed_id=seed_id,
        engine_id=engine_id,
        archive_filename=archive_path.name,
        sha256=sha256,
        source_url=source_url,
        created_at=datetime.utcnow().isoformat(),
    )
    
    save_seed_manifest(manifest)
    logger.info(f"Saved seed {seed_id} to {seed_dir}")
    
    return manifest

