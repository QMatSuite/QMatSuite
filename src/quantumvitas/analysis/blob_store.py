"""
Blob storage manager for volume data.

Manages binary blob storage with security allowlist via index.json.
Blobs are stored as raw float32 little-endian (.f32 files).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, Optional

import numpy as np


class BlobStoreError(Exception):
    """Error in blob store operations."""
    pass


class BlobStore:
    """
    Manages blob_id → path mapping with security allowlist.
    
    Storage structure:
        <calc_dir>/analysis/blobs/
          ├── index.json          (blob_id → relative_path mapping)
          ├── <blob_id>.f32       (binary float32 data)
          └── <blob_id>_preview.f32
    """
    
    def __init__(self, calc_dir: Path):
        """
        Initialize blob store for a calculation directory.
        
        Args:
            calc_dir: Calculation directory (must be absolute path)
        """
        self.calc_dir = Path(calc_dir).resolve()
        self.blobs_dir = self.calc_dir / "analysis" / "blobs"
        self.index_path = self.blobs_dir / "index.json"
        self._index: Dict[str, str] = {}
        self._load_index()
    
    def _load_index(self) -> None:
        """Load index.json if it exists."""
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text())
                self._index = data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError):
                self._index = {}
        else:
            self._index = {}
    
    def _save_index(self) -> None:
        """Save index.json to disk."""
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self._index, indent=2))
    
    def _validate_relative_path(self, relative_path: str) -> None:
        """
        Validate that relative_path is safe (no path traversal).
        
        Args:
            relative_path: Relative path to validate
            
        Raises:
            BlobStoreError: If path contains traversal or is absolute
        """
        if ".." in relative_path:
            raise BlobStoreError(f"Path traversal detected in relative_path: {relative_path}")
        if Path(relative_path).is_absolute():
            raise BlobStoreError(f"Absolute path not allowed: {relative_path}")
    
    def register_blob(
        self,
        data: np.ndarray,
        blob_id: Optional[str] = None,
        suffix: str = "",
    ) -> str:
        """
        Register a new blob and write to disk.
        
        Args:
            data: numpy array (must be float32-compatible)
            blob_id: Optional blob ID (generated if None)
            suffix: Optional suffix for filename (e.g., "_preview")
            
        Returns:
            blob_id (str)
            
        Raises:
            BlobStoreError: If blob_id already exists or path validation fails
        """
        if blob_id is None:
            blob_id = str(uuid.uuid4())
        
        # Generate filename
        filename = f"{blob_id}{suffix}.f32"
        relative_path = filename
        
        # Validate path
        self._validate_relative_path(relative_path)
        
        # Check if blob_id already exists
        if blob_id in self._index:
            raise BlobStoreError(f"Blob ID already exists: {blob_id}")
        
        # Ensure data is float32
        data_f32 = np.asarray(data, dtype=np.float32)
        
        # Write binary file
        blob_path = self.blobs_dir / filename
        self.blobs_dir.mkdir(parents=True, exist_ok=True)
        
        # Write raw float32 little-endian
        data_f32.tofile(str(blob_path))
        
        # Register in index
        self._index[blob_id] = relative_path
        self._save_index()
        
        return blob_id
    
    def get_blob_path(self, blob_id: str) -> Optional[Path]:
        """
        Get the absolute path for a blob_id.
        
        Args:
            blob_id: Blob ID to lookup
            
        Returns:
            Absolute path to blob file, or None if not found
            
        Raises:
            BlobStoreError: If path traversal detected or blob not in allowlist
        """
        if blob_id not in self._index:
            return None
        
        relative_path = self._index[blob_id]
        
        # Validate path (should already be validated, but double-check)
        self._validate_relative_path(relative_path)
        
        # Resolve absolute path
        blob_path = (self.blobs_dir / relative_path).resolve()
        
        # Security check: ensure resolved path is within blobs_dir
        try:
            blob_path.relative_to(self.blobs_dir.resolve())
        except ValueError:
            raise BlobStoreError(f"Path traversal detected: {relative_path} resolves outside blobs_dir")
        
        if not blob_path.exists():
            return None
        
        return blob_path
    
    def validate_blob_id(self, blob_id: str) -> bool:
        """
        Check if blob_id exists in allowlist.
        
        Args:
            blob_id: Blob ID to validate
            
        Returns:
            True if blob_id exists in index
        """
        return blob_id in self._index
    
    def read_blob(self, blob_id: str) -> Optional[np.ndarray]:
        """
        Read blob data from disk.
        
        Args:
            blob_id: Blob ID to read
            
        Returns:
            numpy array (float32), or None if not found
        """
        blob_path = self.get_blob_path(blob_id)
        if blob_path is None:
            return None
        
        # Read raw float32
        data = np.fromfile(str(blob_path), dtype=np.float32)
        return data
    
    def get_blob_size(self, blob_id: str) -> Optional[int]:
        """
        Get blob file size in bytes.
        
        Args:
            blob_id: Blob ID
            
        Returns:
            File size in bytes, or None if not found
        """
        blob_path = self.get_blob_path(blob_id)
        if blob_path is None or not blob_path.exists():
            return None
        return blob_path.stat().st_size

