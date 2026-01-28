"""
Gate 0.5: Nested accessors must not return legacy/vault objects

Ensures that QVService nested accessors (analysis/structure/calculation/etc)
return objects from canonical API modules, not legacy/vault.
"""

import tempfile
from pathlib import Path

import pytest

from quantumvitas.api import QVService


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """Create a minimal project for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Create minimal project.qv.yml
    project_file = project_root / "project.qv.yml"
    project_file.write_text("name: test_project\n")
    
    return project_root


def test_nested_accessors_not_legacy(minimal_project: Path):
    """Ensure nested accessors return canonical API objects, not legacy/vault."""
    svc = QVService(minimal_project)
    
    # Test all nested accessors
    accessors = [
        ("analysis", svc.analysis),
        ("structure", svc.structure),
        ("calculation", svc.calculation),
        ("run", svc.run),
        ("project", svc.project),
        ("engine", svc.engine),
        ("history", svc.history),
    ]
    
    # Check for pseudo/preset if they exist
    if hasattr(svc, "pseudo"):
        accessors.append(("pseudo", svc.pseudo))
    if hasattr(svc, "preset"):
        accessors.append(("preset", svc.preset))
    
    violations = []
    forbidden_modules = [
        "quantumvitas._api_legacy",
        "quantumvitas.api_legacy",
        "quantumvitas._vault",
    ]
    
    for name, obj in accessors:
        if obj is None:
            continue
        
        obj_module = obj.__class__.__module__
        
        for forbidden in forbidden_modules:
            if forbidden in obj_module:
                violations.append({
                    "accessor": name,
                    "module": obj_module,
                    "forbidden": forbidden,
                })
    
    if violations:
        error_msg = "ERROR: Nested accessors returning legacy/vault objects:\n"
        for violation in violations:
            error_msg += (
                f"  - {violation['accessor']}: module '{violation['module']}' "
                f"contains forbidden '{violation['forbidden']}'\n"
            )
        error_msg += "\nAll nested accessors must return objects from quantumvitas.api.* modules."
        assert False, error_msg

