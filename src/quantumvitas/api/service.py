"""
QVService: Main API service class.

This module provides the QVService class which is the primary entry point
for all API operations.
"""

from __future__ import annotations

from pathlib import Path


class QVService:
    """
    Service layer for QuantumVITAS operations.
    
    This is a stub for PR0.
    The full implementation will be migrated from api.py in subsequent PRs.
    """
    
    def __init__(self, project_root: Path):
        """
        Initialize QVService with a project root.
        
        Args:
            project_root: Path to project root (directory containing project.qv.yml)
        """
        self.project_root = Path(project_root).resolve()
        # Stub: minimal validation
        if not (self.project_root / "project.qv.yml").exists():
            raise ValueError(f"Not a project: {self.project_root}")

