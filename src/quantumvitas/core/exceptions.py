"""
Core exceptions for QuantumVITAS.

These exceptions are raised when operations cannot proceed due to
project structure issues, missing resources, or legacy schema incompatibility.
"""

from pathlib import Path


class LegacyProjectError(Exception):
    """
    Raised when a legacy QuantumVITAS project is detected.
    
    Legacy projects use pre-DAG workflow layouts (e.g., structure/step_file fields
    instead of structure_id/step_id ULIDs). These must be migrated using the
    migration script before they can be used with the current codebase.
    
    Attributes:
        project_root: Path to the project root where the legacy project was detected
    """
    
    def __init__(self, project_root: Path, message: str = ""):
        self.project_root = Path(project_root).resolve()
        if not message:
            message = (
                f"Legacy QuantumVITAS project detected at {self.project_root}. "
                f"This project uses pre-DAG workflow layout (structure/step_file fields). "
                f"Please run the migration script to upgrade it to the DAG + ULID model. "
                f"See docs or run: python -m quantumvitas.legacy.migrate <project_root>"
            )
        super().__init__(message)
