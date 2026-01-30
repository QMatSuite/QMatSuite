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
        # step_factory.py should write step_type_spec (SPEC layer), not bare step_type
        count = rg_count(r'"step_type":', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py writes bare 'step_type' (should use step_type_spec)"

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
        # Check for old .public_type attribute (should use .step_type_gen now)
        count = rg_count(r"\.public_type\b", "src/quantumvitas/workflow/registry.py")
        assert count == 0, "registry.py still uses .public_type (should use .step_type_gen)"

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


class TestGenSpecBoundary:
    """GEN/SPEC boundary invariants."""

    def test_presets_map_spec_to_gen(self):
        """Presets must map step_type_spec to step_type_gen for variant lookup."""
        # Presets should have mapping logic (checking spec.step_type_gen)
        count = rg_count(r"spec\.step_type_gen", "src/quantumvitas/presets/")
        assert count > 0, "Presets missing step_type_spec→step_type_gen mapping"

    def test_templates_use_gen_for_workflow(self):
        """Workflow templates must use step_type_gen for workflow detection."""
        count = rg_count(r"step_type_gen", "src/quantumvitas/workflow/templates.py")
        assert count > 0, "templates.py missing step_type_gen usage"

    def test_registry_provides_both_mappings(self):
        """Registry must provide both gen→spec and spec→gen mappings."""
        # gen→spec mapping
        gen_to_spec = rg_count(r"step_type_gen.*step_type_spec", "src/quantumvitas/workflow/registry.py")
        assert gen_to_spec > 0, "Registry missing gen→spec mapping"

    def test_step_factory_writes_spec_to_yaml(self):
        """step_factory must write step_type_spec (not gen) to step.yaml."""
        # Check for step_type_spec being written in factory
        count = rg_count(r'"step_type_spec":', "src/quantumvitas/workflow/step_factory.py")
        assert count > 0, "step_factory not writing step_type_spec to YAML"


class TestYamlSpecOnly:
    """YAML files must not contain step_type_gen."""

    def test_no_step_type_gen_in_demo_yaml(self):
        count = rg_count(r"step_type_gen:", "resources/demo_projects/")
        assert count == 0, "Demo YAML files contain step_type_gen"

    def test_no_bare_step_type_in_golden(self):
        # Check for bare "step_type": or "type": (should use step_type_spec/step_type_gen)
        count = rg_count(r'"step_type":', "tests/fixtures/golden_0873ebf/daemon/")
        assert count == 0, "Golden fixtures have bare step_type (should use step_type_spec/step_type_gen)"


class TestIdentityFieldsRenamed:
    """Resource identity fields must use *_ulid naming."""

    def test_no_step_id_in_models(self):
        # Check for step_id as a field name or in dict keys, but allow in comments/strings
        count = rg_count(r"step_id\s*[:=]", "src/quantumvitas/core/models.py")
        assert count == 0, "models.py still has step_id as field or dict key"

    def test_no_meta_id_in_factory(self):
        # Check for legacy "id": pattern (should use "ulid": now)
        count = rg_count(r'"id":\s*step', "src/quantumvitas/workflow/step_factory.py")
        assert count == 0, "step_factory.py still writes meta.id (should use ulid)"


class TestMetaIdProhibited:
    """
    HARD GATE: .meta.id access is PROHIBITED.

    All resources must use .meta.ulid, never .meta.id.
    This ensures consistent ULID-based identity throughout the codebase.
    """

    def test_no_meta_id_access_in_src(self):
        """Production code must use .meta.ulid, not .meta.id"""
        count = rg_count(r"\.meta\.id\b", "src/")
        assert count == 0, (
            "VIOLATION: Found .meta.id access in src/. "
            "All resources must use .meta.ulid instead."
        )

    def test_no_meta_id_access_in_tools(self):
        """Tools must use .meta.ulid, not .meta.id"""
        count = rg_count(r"\.meta\.id\b", "tools/")
        assert count == 0, (
            "VIOLATION: Found .meta.id access in tools/. "
            "All resources must use .meta.ulid instead."
        )

    def test_no_meta_id_access_in_tests(self):
        """Tests must use .meta.ulid, not .meta.id (except in comments/docs)"""
        # Allow .meta.id in test comments/docstrings but not as actual code
        # We check for actual attribute access pattern
        base_dir = Path(__file__).parent.parent.parent
        cmd = ["rg", r"\.meta\.id\b", "tests/", "-l"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=base_dir)
        files_with_violations = [l for l in result.stdout.strip().split("\n") if l]

        # Filter out this gate file itself (it documents the pattern)
        files_with_violations = [
            f for f in files_with_violations
            if "test_gen_spec_convergence_gate.py" not in f
        ]

        # For each file, check if it's actual code or just documentation
        actual_violations = []
        for file_path in files_with_violations:
            # Skip files that only mention .meta.id in comments/strings
            full_path = base_dir / file_path
            if full_path.exists():
                content = full_path.read_text()
                # Check for actual attribute access (not in comments/strings)
                import re
                # Find lines with .meta.id that aren't comments or doc strings
                for lineno, line in enumerate(content.split('\n'), 1):
                    stripped = line.strip()
                    if '.meta.id' in line and not stripped.startswith('#') and not stripped.startswith('"') and not stripped.startswith("'"):
                        # Check if it's an actual access pattern (e.g., obj.meta.id)
                        if re.search(r'\w+\.meta\.id\b', line):
                            actual_violations.append(f"{file_path}:{lineno}")

        assert len(actual_violations) == 0, (
            f"VIOLATION: Found .meta.id access in test code:\n" +
            "\n".join(f"  - {v}" for v in actual_violations[:10]) +
            ("\n  ... and more" if len(actual_violations) > 10 else "")
        )

