"""Tests for deterministic ULID generation."""

from quantumvitas.demo_store.ulid_seed import deterministic_ulid


class TestDeterministicUlid:
    def test_determinism(self):
        """Same inputs must produce same output."""
        a = deterministic_ulid("vasp_si_scf", "project")
        b = deterministic_ulid("vasp_si_scf", "project")
        assert a == b

    def test_different_slugs_differ(self):
        """Different demo_slugs must produce different ULIDs."""
        a = deterministic_ulid("vasp_si_scf", "project")
        b = deterministic_ulid("qe_si_scf", "project")
        assert a != b

    def test_different_components_differ(self):
        """Different components must produce different ULIDs."""
        a = deterministic_ulid("vasp_si_scf", "project")
        b = deterministic_ulid("vasp_si_scf", "structure:si")
        assert a != b

    def test_ulid_format(self):
        """Output must be 26 characters, Crockford Base32."""
        ulid = deterministic_ulid("test", "component")
        assert len(ulid) == 26
        assert ulid[:3] == "01K"
        valid_chars = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        assert all(c in valid_chars for c in ulid)
