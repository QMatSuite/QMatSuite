"""
Integration tests for step slug consistency.

These tests verify that step.meta.slug is consistent between:
1. The YAML file on disk (authoritative source)
2. The in-memory Step/ResolvedResource object returned by QVService/require_step
3. ResourceIndex entries

This is a constitutional requirement: YAML is the single source of truth.
"""
import yaml
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.core.resolution import require_step, build_resource_index
from quantumvitas.core.models import load_calculation
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.yaml_io import save_yaml_doc


@pytest.fixture
def lammps_project(tmp_path: Path):
    """Create a minimal LAMMPS project for testing step creation."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Init project
    QVService.init_project(target_dir=project_root, name="test")
    
    # Create structure
    structure_path = project_root / "structures" / "test.json"
    structure_path.parent.mkdir(parents=True, exist_ok=True)
    from pymatgen.core import Structure, Lattice
    s = Structure(Lattice.cubic(3.0), ["Ar"], [[0, 0, 0]])
    s.to(filename=structure_path, fmt="json")
    
    # Import structure
    struct_result = QVService.import_structure(project_root, structure_path)
    
    # Init calculation
    calc_result = QVService(project_root).project.init_calculation(
        name="test_calc",
        structure_selector=struct_result.meta.ulid,
    )
    
    # Configure for LAMMPS
    calc_path = calc_result.absolute_path / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    save_yaml_doc(CalcDoc(calc_model.to_dict()), calc_path)
    
    return {
        "project_root": project_root,
        "calc_id": calc_result.meta.ulid,
        "calc_dir": calc_result.absolute_path,
    }


def test_step_slug_uniqueness_and_consistency(lammps_project):
    """
    Test that multiple steps with the same step_type get unique slugs,
    and that returned objects match YAML files exactly.

    Constitutional requirement: meta.slug must match YAML.
    """
    project_root = lammps_project["project_root"]
    calc_id = lammps_project["calc_id"]
    calc_dir = lammps_project["calc_dir"]
    steps_dir = calc_dir / "steps"

    # Create two MD steps (same step_type) using domain API
    svc = QVService(project_root)
    s1 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")
    s2 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")

    # === Assertion 1: IDs are unique ===
    assert s1.step_ulid != s2.step_ulid, f"ULID collision: {s1.step_ulid}"

    # === Assertion 2: Slugs are unique ===
    assert s1.meta.slug != s2.meta.slug, (
        f"Slug collision: s1.slug={s1.meta.slug}, s2.slug={s2.meta.slug}"
    )

    # === Assertion 3: Expected slug pattern ===
    assert s1.meta.slug == "md", f"Expected first slug 'md', got '{s1.meta.slug}'"
    assert s2.meta.slug == "md-1", f"Expected second slug 'md-1', got '{s2.meta.slug}'"

    # === Assertion 4: Verify YAML files match returned objects ===
    yaml_file_1 = steps_dir / "md.step.yaml"
    yaml_file_2 = steps_dir / "md-1.step.yaml"

    assert yaml_file_1.exists(), f"Expected {yaml_file_1} to exist"
    assert yaml_file_2.exists(), f"Expected {yaml_file_2} to exist"

    with open(yaml_file_1) as f:
        data_1 = yaml.safe_load(f)
    with open(yaml_file_2) as f:
        data_2 = yaml.safe_load(f)

    # YAML meta.slug must match returned object meta.slug (constitutional)
    assert data_1["meta"]["slug"] == s1.meta.slug, (
        f"YAML-object mismatch: YAML slug={data_1['meta']['slug']}, object slug={s1.meta.slug}"
    )
    assert data_2["meta"]["slug"] == s2.meta.slug, (
        f"YAML-object mismatch: YAML slug={data_2['meta']['slug']}, object slug={s2.meta.slug}"
    )

    # YAML meta.id must match returned object step_id
    assert data_1["meta"]["ulid"] == s1.step_ulid
    assert data_2["meta"]["ulid"] == s2.step_ulid


def test_require_step_by_ulid_returns_correct_slug(lammps_project):
    """
    Test that require_step(selector=ULID) returns a Step with meta.slug
    matching the YAML file, not a re-computed slug from name.
    """
    project_root = lammps_project["project_root"]
    calc_id = lammps_project["calc_id"]
    calc_dir = lammps_project["calc_dir"]

    # Create two MD steps using domain API
    svc = QVService(project_root)
    s1 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")
    s2 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")

    # Look up s2 by its ULID
    s2_by_id = require_step(project_root, calc_id, s2.step_ulid)

    # Slug must match YAML, not be re-computed as "md"
    assert s2_by_id.meta.slug == "md-1", (
        f"require_step(ULID) returned wrong slug: expected 'md-1', got '{s2_by_id.meta.slug}'"
    )
    assert s2_by_id.meta.ulid == s2.step_ulid


def test_require_step_by_slug_returns_correct_step(lammps_project):
    """
    Test that require_step(selector=slug) returns the correct step,
    not a different one with similar name.
    """
    project_root = lammps_project["project_root"]
    calc_id = lammps_project["calc_id"]

    # Create two MD steps using domain API
    svc = QVService(project_root)
    s1 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")
    s2 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")

    # Look up by slug
    s1_by_slug = require_step(project_root, calc_id, "md")
    s2_by_slug = require_step(project_root, calc_id, "md-1")

    # Must return correct steps
    assert s1_by_slug.meta.ulid == s1.step_ulid, (
        f"Slug 'md' returned wrong step: expected {s1.step_ulid}, got {s1_by_slug.meta.ulid}"
    )
    assert s2_by_slug.meta.ulid == s2.step_ulid, (
        f"Slug 'md-1' returned wrong step: expected {s2.step_ulid}, got {s2_by_slug.meta.ulid}"
    )


def test_resource_index_matches_yaml(lammps_project):
    """
    Test that ResourceIndex entries match YAML files.
    """
    project_root = lammps_project["project_root"]
    calc_id = lammps_project["calc_id"]
    calc_dir = lammps_project["calc_dir"]
    steps_dir = calc_dir / "steps"

    # Create steps using domain API
    svc = QVService(project_root)
    s1 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")
    s2 = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md")

    # Build fresh index
    index = build_resource_index(project_root)

    # Check index entries match YAML
    for step_file in steps_dir.glob("*.step.yaml"):
        with open(step_file) as f:
            data = yaml.safe_load(f)
        yaml_id = data["meta"]["ulid"]
        yaml_slug = data["meta"]["slug"]

        # Index should have this entry
        assert yaml_id in index.by_id, f"Step {yaml_id} not in index"

        index_meta = index.by_id[yaml_id]
        assert index_meta.slug == yaml_slug, (
            f"Index slug mismatch for {yaml_id}: "
            f"YAML slug={yaml_slug}, index slug={index_meta.slug}"
        )


def test_three_steps_same_type(lammps_project):
    """
    Test that creating 3+ steps of the same type produces correct slugs.
    """
    project_root = lammps_project["project_root"]
    calc_id = lammps_project["calc_id"]

    # Create three MD steps using domain API
    svc = QVService(project_root)
    steps = [svc.calculation.add_step(calc_selector=calc_id, step_type_gen="md") for _ in range(3)]

    # Verify IDs are unique
    ids = [s.step_ulid for s in steps]
    assert len(ids) == len(set(ids)), f"ID collision detected: {ids}"

    # Verify slugs are unique and follow pattern
    slugs = [s.meta.slug for s in steps]
    assert len(slugs) == len(set(slugs)), f"Slug collision detected: {slugs}"

    expected_slugs = ["md", "md-1", "md-2"]
    assert slugs == expected_slugs, f"Expected {expected_slugs}, got {slugs}"

