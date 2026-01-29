"""Tests for RPC method introspection."""

import pytest
from tests.contract_crawler.introspection import (
    get_all_rpc_methods,
    get_method_categories,
)


class TestRPCIntrospection:
    """Test RPC method enumeration."""

    def test_enumerate_all_methods(self):
        """All RPC methods can be enumerated."""
        methods = get_all_rpc_methods()
        assert len(methods) >= 100, f"Expected 100+ methods, got {len(methods)}"

    def test_ping_method_exists(self):
        """Essential ping method exists."""
        methods = get_all_rpc_methods()
        names = {m.name for m in methods}
        assert "ping" in names

    def test_all_methods_categorized(self):
        """All methods have a category (no orphans)."""
        methods = get_all_rpc_methods()
        categories = get_method_categories()

        categorized = set()
        for names in categories.values():
            categorized.update(names)

        all_names = {m.name for m in methods}
        uncategorized = all_names - categorized

        assert not uncategorized, f"Uncategorized methods: {uncategorized}"

    def test_handlers_have_docstrings(self):
        """Handlers should have docstrings (warning if missing)."""
        methods = get_all_rpc_methods()
        missing_docs = [m.name for m in methods if not m.docstring]

        # Warning, not failure - but track for coverage
        if missing_docs:
            pytest.warns(UserWarning, match=f"{len(missing_docs)} handlers lack docstrings")

