"""
Gate tests for GEN/SPEC vocabulary convergence.
These tests enforce vocabulary invariants and must pass.
"""
import subprocess
from pathlib import Path

import pytest


def rg_count(pattern: str, path: str) -> int:
    """Run ripgrep and return match count."""
    base_dir = Path(__file__).parent.parent.parent
    cmd = ["rg", pattern, path]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=base_dir)
    lines = [l for l in result.stdout.strip().split("\n") if l]
    return len(lines)


class TestBannedStepTypeVocabulary:
    """Step-type vocabulary must use only step_type_spec/step_type_gen."""

    def test_no_bare_step_type_in_step_factory(self):
        count = rg_count(r'"step_type":', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py writes bare 'step_type'"

    def test_no_bare_type_field_in_models(self):
        count = rg_count(r'self\.type\b', "src/quantumvitas/core/models.py")
        assert count == 0, "models.py has self.type"

    def test_no_type_dict_key_in_models(self):
        count = rg_count(r'd\["type"\]', "src/quantumvitas/core/models.py")
        assert count == 0, "models.py writes d['type']"

    def test_no_second_truth_mapping(self):
        count = rg_count(r"_map_step_type_to_v0", "src/quantumvitas/daemon/")
        assert count == 0, "Hardcoded mapping table exists in daemon"

    def test_no_machine_type_in_registry(self):
        count = rg_count(r"\.machine_type\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses .machine_type"

    def test_no_public_type_in_registry(self):
        count = rg_count(r"\.public_type\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses .public_type"

    def test_no_spec_id_in_registry(self):
        count = rg_count(r"spec\.id\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses spec.id"


class TestCanonicalQERecipe:
    """QERecipe must have single canonical definition."""

    def test_single_qerecipe_class(self):
        result = subprocess.run(
            ["rg", "-l", "^class QERecipe", "src/quantumvitas/"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent.parent
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        assert len(files) == 1, f"QERecipe defined in multiple files: {files}"
        assert "drivers/qe/recipe.py" in files[0], f"QERecipe not in canonical location: {files}"


class TestRequiredVocabulary:
    """Required vocabulary must be present."""

    def test_step_type_spec_in_factory(self):
        count = rg_count(r'"step_type_spec":', "src/quantumvitas/workflow/step_factory.py")
        assert count > 0, "step_factory.py missing step_type_spec"

    def test_meta_ulid_in_factory(self):
        count = rg_count(r'"ulid":', "src/quantumvitas/workflow/step_factory.py")
        assert count > 0, "step_factory.py missing meta.ulid"

    def test_api_facade_exists(self):
        count = rg_count(r"def get_step_type_gen", "src/quantumvitas/api/")
        assert count > 0, "API missing get_step_type_gen facade"

    def test_registry_has_step_type_spec_field(self):
        count = rg_count(r"step_type_spec:\s*str", "src/quantumvitas/workflow/registry.py")
        assert count > 0, "StepTypeSpec missing step_type_spec field"

    def test_registry_has_step_type_gen_field(self):
        count = rg_count(r"step_type_gen:\s*str", "src/quantumvitas/workflow/registry.py")
        assert count > 0, "StepTypeSpec missing step_type_gen field"


class TestYamlSpecOnly:
    """YAML files must not contain step_type_gen."""

    def test_no_step_type_gen_in_demo_yaml(self):
        count = rg_count(r"step_type_gen:", "resources/demo_projects/")
        assert count == 0, "Demo YAML files contain step_type_gen"

    def test_no_bare_step_type_in_golden(self):
        count = rg_count(r'"step_type":', "tests/fixtures/golden_0873ebf/daemon/")
        assert count == 0, "Golden fixtures have bare step_type"


class TestIdentityFieldsRenamed:
    """Resource identity fields must use *_ulid naming."""

    def test_no_step_id_in_models(self):
        # Check for step_id as a field name or in dict keys, but allow in comments/strings
        count = rg_count(r"step_id\s*[:=]", "src/quantumvitas/core/models.py")
        assert count == 0, "models.py still has step_id as field or dict key"

    def test_no_meta_id_in_factory(self):
        # Check specifically for "id": in meta context
        count = rg_count(r'"id":\s*step_id', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py still writes meta.id"

