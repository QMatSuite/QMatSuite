"""
Core exceptions for QuantumVITAS.

These exceptions are raised when operations cannot proceed due to
project structure issues, missing resources, or legacy schema incompatibility.
"""

from pathlib import Path


class LegacyProjectError(Exception):
    """
    Raised when a legacy QuantumVITAS project is detected.
    
    Legacy projects use pre-DAG calculation layouts (e.g., structure/step_file fields
    instead of structure_ulid/step_ulid ULIDs). These must be migrated using the
    migration script before they can be used with the current codebase.
    
    Attributes:
        project_root: Path to the project root where the legacy project was detected
    """
    
    def __init__(self, project_root: Path, message: str = ""):
        self.project_root = Path(project_root).resolve()
        if not message:
            message = (
                f"Legacy QuantumVITAS project detected at {self.project_root}. "
                f"This project uses pre-DAG calculation layout (structure/step_file fields). "
                f"Please run the migration script to upgrade it to the DAG + ULID model. "
                f"See docs or run: python -m quantumvitas.legacy.migrate <project_root>"
            )
        super().__init__(message)


class MissingArtifactError(Exception):
    """
    Raised when a required generated artifact (e.g., relax output structure) is missing.
    
    This is a hard error - the system will not automatically re-run relax steps.
    The user must explicitly run the calculation from the beginning or run the relax step first.
    """
    pass


class UnsupportedStepError(Exception):
    """
    Raised when a generalized step is not supported by the engine family (0-mapping).
    
    Per VASP integration plan v2.0 Section 3.2: When run_step is called with a GEN step
    that maps to 0 for the calculation's engine family, this error is raised with a clear message.
    """
    pass
