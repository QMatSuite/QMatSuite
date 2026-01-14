"""
Unit tests for step type registry mapping completeness and correctness.

Per engine_recipes_jobgraph_plan.md (Constitution §C):
- Every registered SPEC step type must map to exactly one engine member.
- Mapping keys set must equal the registered SPEC step types set.
- If anyone adds a step type and forgets mapping, tests must fail.

SPEC = Machine step type (e.g., "qe_scf", "pyscf_mp2", "orca_td")
GEN = Public/generalized step type (e.g., "scf", "mp2", "td")
"""

import pytest
from quantumvitas.workflow.registry import get_registry, _STEP_TYPES


class TestStepTypeMappingCompleteness:
    """Test that step type registry mappings are complete and correct."""

    def test_all_keys_are_spec_step_types(self):
        """Every key in _STEP_TYPES must be a SPEC step type (engine-prefixed)."""
        # Define valid prefixes for SPEC step types
        valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_")

        for key in _STEP_TYPES.keys():
            # Each key should start with an engine prefix
            assert any(key.startswith(prefix) for prefix in valid_prefixes), (
                f"Key '{key}' is not a valid SPEC step type. "
                f"SPEC step types must start with one of: {valid_prefixes}"
            )

    def test_every_spec_has_non_empty_engine(self):
        """Every StepTypeSpec must have a non-empty engine field."""
        for key, spec in _STEP_TYPES.items():
            assert spec.engine, (
                f"StepTypeSpec for '{key}' has empty engine field. "
                f"All step types must be mapped to an engine."
            )

    def test_machine_type_matches_dict_key(self):
        """Every StepTypeSpec.machine_type must match its dict key."""
        for key, spec in _STEP_TYPES.items():
            assert spec.machine_type == key, (
                f"StepTypeSpec.machine_type '{spec.machine_type}' doesn't match "
                f"dict key '{key}'. They must be identical."
            )

    def test_no_duplicate_engine_public_type_combinations(self):
        """
        Within each engine, no two step types should have the same public_type.

        This enforces the Constitution §A rule: GEN→SPEC mapping must be 0-1
        per engine family (supported or not; if supported then unique).
        """
        # Build map: engine -> {public_type -> machine_type}
        engine_public_map: dict[str, dict[str, str]] = {}

        for key, spec in _STEP_TYPES.items():
            engine = spec.engine
            public_type = spec.public_type

            if engine not in engine_public_map:
                engine_public_map[engine] = {}

            if public_type in engine_public_map[engine]:
                existing = engine_public_map[engine][public_type]
                pytest.fail(
                    f"Duplicate public_type '{public_type}' in engine '{engine}': "
                    f"both '{existing}' and '{key}' claim it. "
                    f"Each GEN type must map to at most one SPEC type per engine."
                )

            engine_public_map[engine][public_type] = key

    def test_all_registered_engines_have_step_types(self):
        """All engines referenced in step types should have at least one step type."""
        engines_with_steps = set(spec.engine for spec in _STEP_TYPES.values())

        # Known engines that should have step types
        expected_engines = {"qe", "pyscf", "orca"}

        for engine in expected_engines:
            assert engine in engines_with_steps, (
                f"Expected engine '{engine}' has no step types registered."
            )


class TestStepTypeRegistryLookup:
    """Test that registry lookup works correctly for both SPEC and GEN types."""

    def test_lookup_by_spec_type(self):
        """Registry should find step types when looking up by SPEC (machine_type)."""
        registry = get_registry()

        # Sample SPEC step types
        spec_types = ["qe_scf", "pyscf_scf", "orca_scf", "w90_run"]

        for spec_type in spec_types:
            result = registry.get(spec_type)
            assert result is not None, f"Failed to lookup SPEC type '{spec_type}'"
            assert result.machine_type == spec_type, (
                f"Lookup for '{spec_type}' returned wrong machine_type: '{result.machine_type}'"
            )

    def test_lookup_by_gen_type(self):
        """Registry should find step types when looking up by GEN (public_type)."""
        registry = get_registry()

        # Sample GEN step types - these might match multiple engines
        # but registry.get() should return ONE result
        gen_types = ["scf", "nscf", "dos", "bands"]

        for gen_type in gen_types:
            result = registry.get(gen_type)
            assert result is not None, f"Failed to lookup GEN type '{gen_type}'"
            assert result.public_type == gen_type, (
                f"Lookup for '{gen_type}' returned wrong public_type: '{result.public_type}'"
            )

    def test_spec_type_preserved_in_registry(self):
        """Verify that SPEC step types are correctly stored and retrievable."""
        registry = get_registry()

        # Get all machine types
        machine_types = registry.list_all_machine()

        # All machine types should be SPEC format
        valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_")
        for mt in machine_types:
            assert any(mt.startswith(prefix) for prefix in valid_prefixes), (
                f"Machine type '{mt}' is not in SPEC format. "
                f"Expected prefix from: {valid_prefixes}"
            )


class TestStepTypeTokensCompleteness:
    """Test that stable tokens are defined where needed."""

    def test_qc_step_types_have_tokens(self):
        """QC step types (ORCA, PySCF) that can be in chains should have tokens."""
        # These step types can appear in QC chains and need stable tokens
        qc_chain_types = [
            "pyscf_scf", "pyscf_mp2", "pyscf_td",
            "orca_scf", "orca_hf", "orca_td",
        ]

        for spec_type in qc_chain_types:
            spec = _STEP_TYPES.get(spec_type)
            assert spec is not None, f"Missing expected QC step type: {spec_type}"
            assert spec.token is not None, (
                f"QC step type '{spec_type}' has no token defined. "
                f"Tokens are required for subchain basename generation."
            )

    def test_token_uniqueness_within_engine(self):
        """Tokens should be unique within each engine to avoid filename collisions."""
        # Build map: engine -> {token -> machine_type}
        engine_token_map: dict[str, dict[str, str]] = {}

        for key, spec in _STEP_TYPES.items():
            if spec.token is None:
                continue

            engine = spec.engine
            token = spec.token

            if engine not in engine_token_map:
                engine_token_map[engine] = {}

            if token in engine_token_map[engine]:
                existing = engine_token_map[engine][token]
                pytest.fail(
                    f"Duplicate token '{token}' in engine '{engine}': "
                    f"both '{existing}' and '{key}' use it. "
                    f"Tokens must be unique within an engine."
                )

            engine_token_map[engine][token] = key
