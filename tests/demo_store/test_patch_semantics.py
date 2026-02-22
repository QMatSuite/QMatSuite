"""
Lock observed yamldoc patch semantics for authoring correctness.

These tests document the exact behavior of StepDoc.set(), .delete(),
and .apply_patch() so that the replay engine can rely on them.
"""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path


def _make_step_doc(data: dict):
    """Create a StepDoc from a dict."""
    from qmatsuite.core.yamldoc import StepDoc
    return StepDoc(data)


class TestSetReplacesLeaf:
    def test_set_overwrites_existing(self):
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf"}}})
        doc.set(["parameters", "CONTROL", "calculation"], "relax")
        assert doc.get(["parameters", "CONTROL", "calculation"]) == "relax"

    def test_set_creates_intermediate_dicts(self):
        doc = _make_step_doc({"parameters": {}})
        doc.set(["parameters", "NEW_SECTION", "key"], "value")
        assert doc.get(["parameters", "NEW_SECTION", "key"]) == "value"

    def test_set_rejects_dict_values(self):
        doc = _make_step_doc({"parameters": {}})
        with pytest.raises(Exception):
            doc.set(["parameters", "CONTROL"], {"calculation": "scf"})


class TestDeleteRemovesBranch:
    def test_delete_removes_leaf(self):
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf", "outdir": "./out"}}})
        result = doc.delete(["parameters", "CONTROL", "outdir"])
        assert result is True
        exported = doc.export_copy(["parameters", "CONTROL"])
        assert "outdir" not in exported

    def test_delete_removes_branch(self):
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf"}, "SYSTEM": {"ecutwfc": 50}}})
        result = doc.delete(["parameters", "CONTROL"])
        assert result is True
        exported = doc.export_copy(["parameters"])
        assert "CONTROL" not in exported
        assert "SYSTEM" in exported

    def test_delete_nonexistent_returns_false(self):
        doc = _make_step_doc({"parameters": {}})
        result = doc.delete(["parameters", "NONEXISTENT"])
        assert result is False


class TestApplyPatch:
    def test_none_deletes(self):
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf"}}})
        doc.apply_patch({"parameters": {"CONTROL": None}})
        exported = doc.export_copy(["parameters"])
        assert "CONTROL" not in exported

    def test_merge_preserves_existing(self):
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf"}}})
        doc.apply_patch({"parameters": {"CONTROL": {"outdir": "./out"}}})
        exported = doc.export_copy(["parameters", "CONTROL"])
        assert exported["calculation"] == "scf"
        assert exported["outdir"] == "./out"

    def test_merge_residue(self):
        """Keys in target NOT in patch persist (merge, not replace)."""
        doc = _make_step_doc({"parameters": {"CONTROL": {"calculation": "scf", "outdir": "./out"}}})
        # Patch only sets calculation, does NOT mention outdir
        doc.apply_patch({"parameters": {"CONTROL": {"calculation": "relax"}}})
        exported = doc.export_copy(["parameters", "CONTROL"])
        assert exported["calculation"] == "relax"
        assert exported["outdir"] == "./out"  # Still there — merge residue


class TestUpdateStepParamsIntegration:
    """Full round-trip through update_step_params-like operations."""

    def test_nested_none_deletes(self):
        doc = _make_step_doc({
            "parameters": {"CONTROL": {"calculation": "scf", "outdir": "./out"}},
            "cards": {},
        })
        # Simulate update_step_params with nested None
        params = {"parameters": {"CONTROL": {"outdir": None}}}
        for key, value in params.items():
            if value is not None:
                doc.apply_patch({key: value})
        exported = doc.export_copy(["parameters", "CONTROL"])
        assert "outdir" not in exported
        assert exported["calculation"] == "scf"

    def test_toplevel_none_is_noop(self):
        """Top-level None in update_step_params is skipped (not apply_patched)."""
        doc = _make_step_doc({
            "parameters": {"CONTROL": {"calculation": "scf"}},
        })
        params = {"parameters": None}
        for key, value in params.items():
            if value is not None:
                doc.apply_patch({key: value})
        # parameters should still be there
        exported = doc.export_copy(["parameters", "CONTROL"])
        assert exported["calculation"] == "scf"
