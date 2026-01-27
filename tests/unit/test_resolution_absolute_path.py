"""
Test that ResolvedResource.absolute_path is correct for calculations.

This test ensures that when resolving a calculation by slug (e.g., "wf"),
the absolute_path points to the correct calculation.yaml file
(e.g., calculations/wf/calculation.yaml, not calculations/calculation.yaml).
"""

import pytest
import yaml
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.core.resources import ResourceMeta, generate_resource_id


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """Create a minimal project with one calculation."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # Create project.qv.yml with calculation entry
    calc_id = generate_resource_id()
    calc_slug = "wf"
    calc_path = f"calculations/{calc_slug}"
    
    project_config = {
        "calculations": [
            {
                "id": calc_id,
                "name": "wf",
                "slug": calc_slug,
                "path": calc_path,
            }
        ]
    }
    
    (project_root / "project.qv.yml").write_text(yaml.safe_dump(project_config, sort_keys=False))
    
    # Create calculation directory and calculation.yaml
    calc_dir = project_root / "calculations" / calc_slug
    calc_dir.mkdir(parents=True)
    
    calc_yaml_path = calc_dir / "calculation.yaml"
    calc_yaml_data = {
        "meta": {
            "id": calc_id,
            "name": "wf",
            "slug": calc_slug,
            "path": calc_path,
            "kind": "calculation",
        },
        "mode": "normal",
        "steps": [],
    }
    
    calc_yaml_path.write_text(yaml.safe_dump(calc_yaml_data, sort_keys=False))
    
    return project_root


def test_require_calculation_ref_absolute_path(minimal_project: Path):
    """Test that require_calculation_ref returns correct absolute_path.

    The absolute_path should point to the calculation.yaml file, not the directory.
    This matches the contract expected by CLI code which does:
    calc_dir = calculation_resolved.absolute_path.parent
    """
    from quantumvitas.api import get_service
    svc = get_service(minimal_project)

    # Resolve calculation by slug using domain API
    resolved = svc.calculation.require_ref("wf")
    
    # The absolute_path should point to the calculation directory
    # (most code expects this and uses absolute_path directly as a directory)
    expected_dir_path = minimal_project / "calculations" / "wf"
    
    assert resolved.absolute_path == expected_dir_path, (
        f"Expected absolute_path to be {expected_dir_path}, "
        f"but got {resolved.absolute_path}"
    )
    
    # Verify the directory actually exists
    assert resolved.absolute_path.exists(), (
        f"absolute_path {resolved.absolute_path} does not exist"
    )
    assert resolved.absolute_path.is_dir(), (
        f"absolute_path {resolved.absolute_path} is not a directory"
    )
    
    # Verify the calculation.yaml file exists in the directory
    calc_yaml = resolved.absolute_path / "calculation.yaml"
    assert calc_yaml.exists(), (
        f"calculation.yaml file {calc_yaml} does not exist in directory {resolved.absolute_path}"
    )
    
    # Verify meta information
    assert resolved.meta.slug == "wf"
    assert resolved.meta.id is not None
    assert resolved.meta.path == "calculations/wf"
    
    # Verify directory structure
    assert resolved.absolute_path.name == "wf"
    assert resolved.absolute_path.parent.name == "calculations"
    assert resolved.absolute_path.parent.parent == minimal_project

