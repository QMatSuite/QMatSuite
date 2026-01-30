"""Unit tests for QC chain token and namespace semantics.

Tests the stable token mapping and subchain basename generation
for QC chains (ORCA, PySCF).

Per docs/plans/orca_execution_mvp_plan.md:
- Stable tokens: scf→s, td→t, mp2→m2, freq→f, nmr→n
- Tokens are IMMUTABLE once published
- Subchain basenames: s, s_t, s_m2, s_m2_n (joined by _)
- Chain namespace folder: scf_<suffix> from SCF root ULID
"""
import pytest


class TestPublicTypeTokens:
    """Tests for stable token mapping (immutable contract)."""

    def test_token_mapping_exists(self):
        """PUBLIC_TYPE_TOKENS constant should exist."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert isinstance(PUBLIC_TYPE_TOKENS, dict)
        assert len(PUBLIC_TYPE_TOKENS) >= 6  # At least scf, hf, td, mp2, freq, nmr

    def test_scf_token_is_s(self):
        """scf token MUST be 's' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["scf"] == "s"

    def test_hf_token_is_h(self):
        """hf token MUST be 'h' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["hf"] == "h"

    def test_td_token_is_t(self):
        """td token MUST be 't' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["td"] == "t"

    def test_mp2_token_is_m2(self):
        """mp2 token MUST be 'm2' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["mp2"] == "m2"

    def test_freq_token_is_f(self):
        """freq token MUST be 'f' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["freq"] == "f"

    def test_nmr_token_is_n(self):
        """nmr token MUST be 'n' (immutable contract)."""
        from quantumvitas.workflow.registry import PUBLIC_TYPE_TOKENS

        assert PUBLIC_TYPE_TOKENS["nmr"] == "n"


class TestGetTokenForPublicType:
    """Tests for get_token_for_public_type function."""

    def test_get_scf_token(self):
        """Get token for scf returns 's'."""
        from quantumvitas.workflow.registry import get_token_for_public_type

        assert get_token_for_public_type("scf") == "s"

    def test_get_td_token(self):
        """Get token for td returns 't'."""
        from quantumvitas.workflow.registry import get_token_for_public_type

        assert get_token_for_public_type("td") == "t"

    def test_case_insensitive(self):
        """Token lookup should be case-insensitive."""
        from quantumvitas.workflow.registry import get_token_for_public_type

        assert get_token_for_public_type("SCF") == "s"
        assert get_token_for_public_type("Td") == "t"
        assert get_token_for_public_type("MP2") == "m2"

    def test_unknown_type_raises(self):
        """Unknown public_type should raise ValueError."""
        from quantumvitas.workflow.registry import get_token_for_public_type

        with pytest.raises(ValueError, match="No stable token defined"):
            get_token_for_public_type("unknown_type")


class TestGenerateSubchainBasename:
    """Tests for subchain basename generation."""

    def test_single_scf(self):
        """Single SCF step produces 's'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["scf"]) == "s"

    def test_single_hf(self):
        """Single HF step produces 'h'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["hf"]) == "h"

    def test_scf_td_chain(self):
        """SCF + TD chain produces 's_t'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["scf", "td"]) == "s_t"

    def test_scf_mp2_chain(self):
        """SCF + MP2 chain produces 's_m2'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["scf", "mp2"]) == "s_m2"

    def test_hf_td_chain(self):
        """HF + TD chain produces 'h_t'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["hf", "td"]) == "h_t"

    def test_three_step_chain(self):
        """SCF + MP2 + NMR chain produces 's_m2_n'."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        assert generate_subchain_basename(["scf", "mp2", "nmr"]) == "s_m2_n"

    def test_empty_raises(self):
        """Empty public_types list should raise ValueError."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        with pytest.raises(ValueError, match="cannot be empty"):
            generate_subchain_basename([])

    def test_unknown_type_raises(self):
        """Unknown type in list should raise ValueError."""
        from quantumvitas.workflow.registry import generate_subchain_basename

        with pytest.raises(ValueError, match="No stable token defined"):
            generate_subchain_basename(["scf", "unknown"])


class TestChainNamespaceFolder:
    """Tests for chain namespace folder generation."""

    def test_basic_namespace(self):
        """Basic namespace folder generation."""
        from quantumvitas.workflow.registry import get_chain_namespace_folder

        result = get_chain_namespace_folder("01HY2Q9W8A1234ABCDEF")
        assert result == "scf_ABCDEF"

    def test_uses_last_six_chars(self):
        """Namespace uses last 6 characters of ULID."""
        from quantumvitas.workflow.registry import get_chain_namespace_folder

        # Different ULIDs with same suffix should produce same namespace
        assert get_chain_namespace_folder("XXXXXXXXXXXXXXX123456") == "scf_123456"
        assert get_chain_namespace_folder("YYYYYYYYYYYYYY123456") == "scf_123456"

    def test_different_suffixes(self):
        """Different suffixes produce different namespaces."""
        from quantumvitas.workflow.registry import get_chain_namespace_folder

        ns1 = get_chain_namespace_folder("01HY2Q9W8A1234AAAAAA")
        ns2 = get_chain_namespace_folder("01HY2Q9W8A1234BBBBBB")
        assert ns1 != ns2
        assert ns1 == "scf_AAAAAA"
        assert ns2 == "scf_BBBBBB"

    def test_short_ulid_raises(self):
        """ULID shorter than 6 characters should raise ValueError."""
        from quantumvitas.workflow.registry import get_chain_namespace_folder

        with pytest.raises(ValueError, match="ULID too short"):
            get_chain_namespace_folder("12345")

    def test_exact_six_chars(self):
        """Exactly 6 characters should work."""
        from quantumvitas.workflow.registry import get_chain_namespace_folder

        result = get_chain_namespace_folder("ABCDEF")
        assert result == "scf_ABCDEF"


class TestStepTypeSpecToken:
    """Tests for token field in StepTypeSpec."""

    def test_pyscf_scf_has_token(self):
        """pyscf_scf step type should have token 's'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("pyscf_scf")
        assert spec is not None
        assert spec.token == "s"

    def test_pyscf_mp2_has_token(self):
        """pyscf_mp2 step type should have token 'm2'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("pyscf_mp2")
        assert spec is not None
        assert spec.token == "m2"

    def test_pyscf_td_has_token(self):
        """pyscf_td step type should have token 't'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("pyscf_td")
        assert spec is not None
        assert spec.token == "t"

    def test_orca_scf_has_token(self):
        """orca_scf step type should have token 's'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("orca_scf")
        assert spec is not None
        assert spec.token == "s"

    def test_orca_hf_has_token(self):
        """orca_hf step type should have token 'h'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("orca_hf")
        assert spec is not None
        assert spec.token == "h"

    def test_orca_td_has_token(self):
        """orca_td step type should have token 't'."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("orca_td")
        assert spec is not None
        assert spec.token == "t"

    def test_qe_steps_no_token(self):
        """QE step types should have no token (None)."""
        from quantumvitas.workflow.registry import get_registry

        reg = get_registry()
        spec = reg.get("qe_scf")
        assert spec is not None
        assert spec.token is None  # QE steps don't use tokens


class TestTokenConsistency:
    """Tests for consistency between PUBLIC_TYPE_TOKENS and StepTypeSpec.token."""

    def test_tokens_match_mapping(self):
        """StepTypeSpec.token values should match PUBLIC_TYPE_TOKENS."""
        from quantumvitas.workflow.registry import (
            get_registry,
            PUBLIC_TYPE_TOKENS,
        )

        reg = get_registry()

        # Check PySCF step types
        for machine_type in ["pyscf_scf", "pyscf_mp2", "pyscf_td"]:
            spec = reg.get(machine_type)
            if spec and spec.token:
                expected_token = PUBLIC_TYPE_TOKENS.get(spec.step_type_gen)
                assert spec.token == expected_token, (
                    f"{machine_type}: token '{spec.token}' != expected '{expected_token}'"
                )

        # Check ORCA step types
        for machine_type in ["orca_scf", "orca_hf", "orca_td"]:
            spec = reg.get(machine_type)
            if spec and spec.token:
                expected_token = PUBLIC_TYPE_TOKENS.get(spec.step_type_gen)
                assert spec.token == expected_token, (
                    f"{machine_type}: token '{spec.token}' != expected '{expected_token}'"
                )
