"""
Unit tests for demo schema validation.

Validates that generated demo YAML files comply with schema rules:
- No parameters.k_points (K_POINTS must be in cards)
- No step-level pseudopot fields (only in calculation-level species_map)
- No step-level prefix/outdir (injected from calculation.meta.slug)
"""

import pytest
from pathlib import Path
import yaml

from quantumvitas.core.resources import get_resources_dir


# Repo root for finding demo projects
DEMO_PROJECTS_DIR = get_resources_dir() / "demo_projects"


def get_all_demo_yamls():
    """Get all demo YAML files."""
    if not DEMO_PROJECTS_DIR.exists():
        pytest.skip(f"Demo projects directory not found: {DEMO_PROJECTS_DIR}")
    
    demo_files = list(DEMO_PROJECTS_DIR.glob("*.yml"))
    if not demo_files:
        pytest.skip("No demo YAML files found")
    
    return demo_files


@pytest.mark.parametrize("demo_file", get_all_demo_yamls(), ids=lambda p: p.name)
def test_no_parameters_k_points(demo_file: Path):
    """Test that no demo has k_points in parameters section."""
    data = yaml.safe_load(demo_file.read_text())
    if not data:
        pytest.skip(f"Empty or invalid YAML: {demo_file.name}")
    
    calculations = data.get("calculations", [])
    if not calculations:
        pytest.skip(f"No calculations in demo: {demo_file.name}")
    
    violations = []
    for calc_idx, calc in enumerate(calculations):
        steps = calc.get("steps", [])
        for step_idx, step in enumerate(steps):
            parameters = step.get("parameters", {})
            
            # Check all parameter sections for k_points
            for section_name, section_params in parameters.items():
                if isinstance(section_params, dict):
                    if "k_points" in section_params or "kpoints" in section_params:
                        violations.append(
                            f"Calc {calc_idx}, Step {step_idx}: "
                            f"Found k_points/kpoints in parameters.{section_name}"
                        )
    
    if violations:
        pytest.fail(
            f"Found k_points in parameters (should be in cards.K_POINTS):\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


@pytest.mark.parametrize("demo_file", get_all_demo_yamls(), ids=lambda p: p.name)
def test_no_step_level_pseudopot_fields(demo_file: Path):
    """Test that no demo has pseudopot fields in step-level species_overrides."""
    data = yaml.safe_load(demo_file.read_text())
    if not data:
        pytest.skip(f"Empty or invalid YAML: {demo_file.name}")
    
    calculations = data.get("calculations", [])
    if not calculations:
        pytest.skip(f"No calculations in demo: {demo_file.name}")
    
    violations = []
    pseudo_fields = {"pseudopot", "pseudo_basename", "pseudo_sha256", "pseudo_sha_family"}
    
    for calc_idx, calc in enumerate(calculations):
        steps = calc.get("steps", [])
        for step_idx, step in enumerate(steps):
            species_overrides = step.get("species_overrides", {})
            
            # Check all species in species_overrides
            for element, override in species_overrides.items():
                if isinstance(override, dict):
                    for field in pseudo_fields:
                        if field in override:
                            violations.append(
                                f"Calc {calc_idx}, Step {step_idx}, Element {element}: "
                                f"Found {field} in step-level species_overrides "
                                f"(should only be in calculation-level species_map)"
                            )
    
    if violations:
        pytest.fail(
            f"Found pseudopot fields in step-level species_overrides:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


@pytest.mark.parametrize("demo_file", get_all_demo_yamls(), ids=lambda p: p.name)
def test_no_step_level_prefix_outdir(demo_file: Path):
    """Test that no demo has prefix/outdir in step parameters."""
    data = yaml.safe_load(demo_file.read_text())
    if not data:
        pytest.skip(f"Empty or invalid YAML: {demo_file.name}")
    
    calculations = data.get("calculations", [])
    if not calculations:
        pytest.skip(f"No calculations in demo: {demo_file.name}")
    
    violations = []
    
    for calc_idx, calc in enumerate(calculations):
        steps = calc.get("steps", [])
        for step_idx, step in enumerate(steps):
            parameters = step.get("parameters", {})
            
            # Check all parameter sections for prefix/outdir
            for section_name, section_params in parameters.items():
                if isinstance(section_params, dict):
                    if "prefix" in section_params:
                        violations.append(
                            f"Calc {calc_idx}, Step {step_idx}: "
                            f"Found prefix in parameters.{section_name} "
                            f"(should be injected from calculation.meta.slug)"
                        )
                    if "outdir" in section_params:
                        violations.append(
                            f"Calc {calc_idx}, Step {step_idx}: "
                            f"Found outdir in parameters.{section_name} "
                            f"(should be injected from calculation.meta.slug)"
                        )
    
    if violations:
        pytest.fail(
            f"Found prefix/outdir in step parameters:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


@pytest.mark.parametrize("demo_file", get_all_demo_yamls(), ids=lambda p: p.name)
def test_k_points_in_cards_when_present(demo_file: Path):
    """Test that K_POINTS is in cards section when k-points are needed."""
    data = yaml.safe_load(demo_file.read_text())
    if not data:
        pytest.skip(f"Empty or invalid YAML: {demo_file.name}")
    
    calculations = data.get("calculations", [])
    if not calculations:
        pytest.skip(f"No calculations in demo: {demo_file.name}")
    
    # Steps that typically require K_POINTS
    steps_requiring_kpoints = {"scf", "nscf", "relax", "vc-relax", "bands", "bands_pw"}
    
    warnings = []
    for calc_idx, calc in enumerate(calculations):
        steps = calc.get("steps", [])
        for step_idx, step in enumerate(steps):
            step_type = step.get("step_type_spec", "").lower()
            
            if step_type in steps_requiring_kpoints:
                cards = step.get("cards", {})
                if "K_POINTS" not in cards and "k_points" not in cards:
                    # This is a warning, not an error (some steps might not have K_POINTS set)
                    warnings.append(
                        f"Calc {calc_idx}, Step {step_idx} ({step_type}): "
                        f"Expected K_POINTS in cards but not found"
                    )
    
    # Log warnings but don't fail (some steps might legitimately not have K_POINTS)
    if warnings:
        import warnings as py_warnings
        for w in warnings:
            py_warnings.warn(w, UserWarning)


@pytest.mark.parametrize("demo_file", get_all_demo_yamls(), ids=lambda p: p.name)
def test_calculation_species_map_complete(demo_file: Path):
    """Test that calculation-level species_map has complete pseudo triplets when present."""
    data = yaml.safe_load(demo_file.read_text())
    if not data:
        pytest.skip(f"Empty or invalid YAML: {demo_file.name}")
    
    calculations = data.get("calculations", [])
    if not calculations:
        pytest.skip(f"No calculations in demo: {demo_file.name}")
    
    violations = []
    for calc_idx, calc in enumerate(calculations):
        species_map = calc.get("species_map", {})
        
        if not species_map:
            continue  # No species_map is OK (some demos might not need pseudos)
        
        for element, entry in species_map.items():
            if not isinstance(entry, dict):
                continue
            
            # Check for pseudo filename (either pseudopot or pseudo_basename)
            pseudo_filename = entry.get("pseudo_basename") or entry.get("pseudopot")
            if not pseudo_filename:
                violations.append(
                    f"Calc {calc_idx}, Element {element}: "
                    f"Missing pseudo filename in species_map"
                )
                continue
            
            # Check for sha256
            sha256 = entry.get("pseudo_sha256")
            if not sha256:
                violations.append(
                    f"Calc {calc_idx}, Element {element}: "
                    f"Missing pseudo_sha256 in species_map"
                )
            elif not isinstance(sha256, str) or len(sha256) != 64:
                violations.append(
                    f"Calc {calc_idx}, Element {element}: "
                    f"Invalid pseudo_sha256 (must be 64 hex chars): {sha256[:20]}..."
                )
            
            # Check for sha_family
            sha_family = entry.get("pseudo_sha_family")
            if not sha_family:
                violations.append(
                    f"Calc {calc_idx}, Element {element}: "
                    f"Missing pseudo_sha_family in species_map"
                )
            elif not isinstance(sha_family, str) or len(sha_family) != 64:
                violations.append(
                    f"Calc {calc_idx}, Element {element}: "
                    f"Invalid pseudo_sha_family (must be 64 hex chars): {sha_family[:20]}..."
                )
    
    if violations:
        pytest.fail(
            f"Invalid species_map in demos:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )
