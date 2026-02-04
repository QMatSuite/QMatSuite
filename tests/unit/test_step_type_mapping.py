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
        valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "qmcpack_", "psi4_", "gpaw_", "siesta_")

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
            assert spec.step_type_spec == key, (
                f"StepTypeSpec.machine_type '{spec.step_type_spec}' doesn't match "
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
            public_type = spec.step_type_gen

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
        expected_engines = {"qe", "pyscf", "orca", "vasp", "lammps", "cp2k"}

        for engine in expected_engines:
            assert engine in engines_with_steps, (
                f"Expected engine '{engine}' has no step types registered."
            )


class TestStepTypeRegistryLookup:
    """Test that registry lookup works correctly.

    Per constitution, registry.get() only accepts GEN types.
    For SPEC-based lookups, use get_for_engine(gen_type, engine) or _STEP_TYPES[spec].
    """

    def test_lookup_by_spec_type(self):
        """Registry can find step types using get_for_engine(gen, engine)."""
        registry = get_registry()

        # Test cases: (gen_type, engine, expected_spec_type)
        test_cases = [
            ("scf", "qe", "qe_scf"),
            ("scf", "pyscf", "pyscf_scf"),
            ("scf", "orca", "orca_scf"),
            ("wannier", "w90", "w90_wannier"),
        ]

        for gen_type, engine, expected_spec in test_cases:
            result = registry.get_for_engine(gen_type, engine)
            assert result is not None, f"Failed to lookup gen='{gen_type}' engine='{engine}'"
            assert result.step_type_spec == expected_spec, (
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
            assert result.step_type_gen == gen_type, (
                f"Lookup for '{gen_type}' returned wrong step_type_gen: '{result.step_type_gen}'"
            )

    def test_spec_type_preserved_in_registry(self):
        """Verify that SPEC step types are correctly stored and retrievable."""
        registry = get_registry()

        # Get all machine types
        machine_types = registry.list_all_machine()

        # All machine types should be SPEC format
        valid_prefixes = ("qe_", "w90_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "qmcpack_", "psi4_", "gpaw_", "siesta_")
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


class TestLegacyCodeRemoval:
    """Test that legacy execution paths have been removed (Constitution §C audit fix)."""

    def test_no_run_step_legacy_in_api(self):
        """Verify run_step_legacy() has been deleted from api.py."""
        from quantumvitas import api

        # run_step_legacy should not exist
        assert not hasattr(api.QVService, 'run_step_legacy'), (
            "run_step_legacy() still exists in QVService. "
            "Constitution §C requires removing legacy execution paths."
        )

    def test_no_legacy_fallback_in_runner(self):
        """Verify legacy execution loop fallback has been removed from runner.py."""
        import inspect
        from quantumvitas.calculation.runner import CalculationRunner

        # Get the source code of the run() method
        source = inspect.getsource(CalculationRunner.run)

        # Check that the legacy fallback comment is not present
        assert "LEGACY EXECUTION LOOP" not in source, (
            "Legacy execution loop fallback still present in runner.py. "
            "Constitution §C requires removing legacy execution paths."
        )

        # Check that fallback to legacy is not present
        assert "falling back to legacy" not in source.lower(), (
            "Legacy fallback logic still present in runner.py."
        )


class TestSpecTruthPreservation:
    """Test that SPEC step types are preserved in production paths (Constitution §B)."""

    def test_structure_step_spec_preserves_spec_type(self, tmp_path):
        """Loading step.yaml must preserve SPEC step_type_spec without normalization to GEN."""
        from quantumvitas.calculation.structure_steps import StructureStepSpec

        # Create a step.yaml with SPEC step_type_spec
        step_yaml = tmp_path / "test_step.yaml"
        step_yaml.write_text("""
meta:
  ulid: test123
  name: test-step
  path: test_step.yaml
step_type_spec: qe_scf
parameters:
  ecutwfc: 50
""")

        # Load the step spec
        spec = StructureStepSpec.from_yaml(step_yaml, resolve_structure_selector=None)

        # CRITICAL: step_type_spec MUST be SPEC format, not GEN
        assert spec.step_type_spec == "qe_scf", (
            f"StructureStepSpec.step_type_spec was normalized to '{spec.step_type_spec}' but "
            f"Constitution §B requires persisted SPEC truth. Expected 'qe_scf'."
        )

    def test_structure_step_spec_preserves_orca_spec_type(self, tmp_path):
        """Loading ORCA step.yaml must preserve SPEC step_type_spec."""
        from quantumvitas.calculation.structure_steps import StructureStepSpec

        step_yaml = tmp_path / "orca_step.yaml"
        step_yaml.write_text("""
meta:
  ulid: orca123
  name: orca-scf
  path: orca_step.yaml
step_type_spec: orca_scf
parameters:
  basis: def2-SVP
""")

        spec = StructureStepSpec.from_yaml(step_yaml, resolve_structure_selector=None)
        assert spec.step_type_spec == "orca_scf", (
            f"ORCA step_type_spec was normalized to '{spec.step_type_spec}'. Expected 'orca_scf'."
        )

    def test_sha_computation_uses_spec_type(self, tmp_path):
        """SHA computation must use SPEC step_type_spec (matching YAML content)."""
        from quantumvitas.calculation.hash_utils import compute_step_sha

        # Create step.yaml with SPEC type
        step_yaml = tmp_path / "step.yaml"
        step_yaml.write_text("""
step_type_spec: qe_scf
parameters:
  ecutwfc: 50
""")

        sha1 = compute_step_sha(step_yaml)

        # If we modify step_type_spec to different value, SHA should change
        step_yaml.write_text("""
step_type_spec: qe_nscf
parameters:
  ecutwfc: 50
""")

        sha2 = compute_step_sha(step_yaml)

        # SHA must differ because step_type_spec is different (qe_scf vs qe_nscf)
        assert sha1 != sha2, (
            "SHA computation normalized step_type_spec before hashing. "
            "Constitution §B requires SHA to be computed on SPEC types (matching YAML truth)."
        )

    def test_engine_family_from_step_uses_registry_not_prefix(self):
        """Engine family detection must use registry lookup, NOT prefix inference.

        Constitution §C requires explicit dispatch mapping. This test ensures
        that _get_engine_family_from_step uses registry lookup.
        """
        from quantumvitas.calculation.runner import _get_engine_family_from_step
        from unittest.mock import MagicMock

        # Create a mock step with a step_type that has GEN value (no prefix)
        mock_step = MagicMock()
        mock_step.step_type_spec= "scf"  # GEN type, no prefix

        # The registry has "scf" mapped to "qe" engine
        result = _get_engine_family_from_step(mock_step)

        # Should return "qe" from registry lookup, NOT None (which would happen
        # if we only looked at the string prefix)
        assert result == "qe", (
            f"Engine family detection returned '{result}' for step_type 'scf'. "
            f"Expected 'qe' from registry lookup. This suggests prefix inference "
            f"is being used instead of registry lookup."
        )

    def test_engine_family_for_pyscf_step(self):
        """Verify PySCF steps are correctly identified via registry."""
        from quantumvitas.calculation.runner import _get_engine_family_from_step
        from unittest.mock import MagicMock

        mock_step = MagicMock()
        mock_step.step_type_spec= "pyscf_scf"

        result = _get_engine_family_from_step(mock_step)
        assert result == "pyscf", f"Expected 'pyscf', got '{result}'"

    def test_engine_family_for_orca_step(self):
        """Verify ORCA steps are correctly identified via registry."""
        from quantumvitas.calculation.runner import _get_engine_family_from_step
        from unittest.mock import MagicMock

        mock_step = MagicMock()
        mock_step.step_type_spec= "orca_scf"

        result = _get_engine_family_from_step(mock_step)
        assert result == "orca", f"Expected 'orca', got '{result}'"


class TestRelaxStepTypeConfiguration:
    """Test that relax step types have correct configuration for structure transforms."""

    def test_relax_step_types_have_is_structure_transform_true(self):
        """All relax step types must have is_structure_transform=True."""
        relax_step_types = ["qe_relax"]
        
        for step_type in relax_step_types:
            spec = _STEP_TYPES.get(step_type)
            assert spec is not None, f"Missing expected relax step type: {step_type}"
            assert getattr(spec, 'is_structure_transform', False) is True, (
                f"Relax step type '{step_type}' must have is_structure_transform=True. "
                f"Current value: {getattr(spec, 'is_structure_transform', 'missing')}"
            )

    def test_relax_step_types_do_not_produce_charge_density(self):
        """All relax step types must have produces_charge_density=False."""
        relax_step_types = ["qe_relax"]
        
        for step_type in relax_step_types:
            spec = _STEP_TYPES.get(step_type)
            assert spec is not None, f"Missing expected relax step type: {step_type}"
            assert spec.produces_charge_density is False, (
                f"Relax step type '{step_type}' must have produces_charge_density=False. "
                f"Relax steps do NOT produce reusable electronic state. "
                f"Current value: {spec.produces_charge_density}"
            )

    def test_only_relax_is_gen_public_type(self):
        """Only 'relax' should be the GEN step public type for structure transforms."""
        registry = get_registry()
        gen_public_types = set()
        for spec in _STEP_TYPES.values():
            if getattr(spec, 'is_structure_transform', False):
                gen_public_types.add(spec.step_type_gen)
        
        # Should only contain "relax"
        assert gen_public_types == {"relax"}, (
            f"Expected only 'relax' as GEN public type for structure transforms, "
            f"but found: {gen_public_types}. "
            f"vc-relax, opt, geomopt should not exist as separate public types."
        )

    def test_qe_vc_relax_does_not_exist(self):
        """qe_vc_relax should not exist as a separate step type."""
        registry = get_registry()
        assert registry.get("qe_vc_relax") is None, (
            "qe_vc_relax should not exist. VC-relax should be controlled via "
            "qe_relax with parameters.CONTROL.calculation='vc-relax' option."
        )
        assert registry.get("vc-relax") is None, (
            "vc-relax should not exist as a public type. Use 'relax' instead."
        )

    def test_orca_relax_exists(self):
        """orca_relax should be registered."""
        registry = get_registry()
        # Use get_for_engine per constitution: registry.get() takes GEN only
        spec = registry.get_for_engine("relax", "orca")
        assert spec is not None, "orca_relax should be registered"
        assert spec.engine == "orca"
        assert spec.step_type_gen == "relax", f"Expected public_type='relax', got '{spec.step_type_gen}'"
        assert spec.is_structure_transform is True, "orca_relax should have is_structure_transform=True"

    def test_pyscf_relax_exists(self):
        """pyscf_relax should be registered."""
        registry = get_registry()
        # Use get_for_engine per constitution: registry.get() takes GEN only
        spec = registry.get_for_engine("relax", "pyscf")
        assert spec is not None, "pyscf_relax should be registered"
        assert spec.engine == "pyscf"
        assert spec.step_type_gen == "relax", f"Expected public_type='relax', got '{spec.step_type_gen}'"
        assert spec.is_structure_transform is True, "pyscf_relax should have is_structure_transform=True"
