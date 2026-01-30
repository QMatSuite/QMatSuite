"""
Unit tests for YamlDoc abstraction.

Tests cover:
- No reference leakage (mutation of returned values doesn't affect doc)
- Leaf-only get (raises on branch access)
- apply_patch correctness (nested patches, None = delete)
- List deep copy behavior
- Delete branch behavior
- Access control for StepDoc
"""

import copy
import pytest
from pathlib import Path
import tempfile

from quantumvitas.core.yamldoc import (
    YamlDoc,
    StepDoc,
    CalcDoc,
    ProjectDoc,
    MISSING,
    PathNotFoundError,
    BranchAccessError,
    AccessControlError,
    YamlDocError,
)
from quantumvitas.core.yaml_io import (
    load_yaml_doc,
    save_yaml_doc,
    load_step_doc,
    _load_yaml_raw,
    _save_yaml_raw,
)


# =============================================================================
# YamlDoc Core Tests
# =============================================================================


class TestYamlDocInit:
    """Test YamlDoc initialization and deep copy behavior."""
    
    def test_init_empty(self):
        """Empty doc initializes with empty dict."""
        doc = YamlDoc()
        assert doc.to_dict() == {}
    
    def test_init_with_data(self):
        """Doc stores provided data."""
        data = {"key": "value", "nested": {"a": 1}}
        doc = YamlDoc(data)
        assert doc.to_dict() == data
    
    def test_init_deep_copies_input(self):
        """Input data is deep copied, not referenced."""
        data = {"nested": {"a": 1, "list": [1, 2, 3]}}
        doc = YamlDoc(data)
        
        # Mutating original doesn't affect doc
        data["nested"]["a"] = 999
        data["nested"]["list"].append(4)
        
        assert doc.get(["nested", "a"]) == 1
        assert doc.get(["nested", "list"]) == [1, 2, 3]
    
    def test_snapshot_enabled_by_default(self):
        """Snapshot is stored by default."""
        doc = YamlDoc({"a": 1})
        assert doc.get_snapshot() == {"a": 1}
    
    def test_snapshot_disabled(self):
        """Snapshot can be disabled."""
        doc = YamlDoc({"a": 1}, snapshot=False)
        assert doc.get_snapshot() is None


class TestYamlDocGetLeaf:
    """Test get() for leaf values."""
    
    def test_get_scalar(self):
        """Get returns scalar values directly."""
        doc = YamlDoc({"a": 1, "b": "hello", "c": True, "d": 3.14})
        assert doc.get(["a"]) == 1
        assert doc.get(["b"]) == "hello"
        assert doc.get(["c"]) is True
        assert doc.get(["d"]) == 3.14
    
    def test_get_nested_scalar(self):
        """Get traverses nested dicts."""
        doc = YamlDoc({"level1": {"level2": {"value": 42}}})
        assert doc.get(["level1", "level2", "value"]) == 42
    
    def test_get_missing_raises(self):
        """Get raises PathNotFoundError for missing paths."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(PathNotFoundError):
            doc.get(["nonexistent"])
        
        with pytest.raises(PathNotFoundError):
            doc.get(["a", "deep", "path"])
    
    def test_get_missing_with_default(self):
        """Get returns default for missing paths."""
        doc = YamlDoc({"a": 1})
        assert doc.get(["nonexistent"], default=None) is None
        assert doc.get(["nonexistent"], default="default") == "default"
        assert doc.get(["nonexistent"], default=0) == 0
    
    def test_get_branch_raises(self):
        """Get raises BranchAccessError for dict values."""
        doc = YamlDoc({"branch": {"a": 1, "b": 2}})
        
        with pytest.raises(BranchAccessError) as exc_info:
            doc.get(["branch"])
        
        assert "export_copy" in str(exc_info.value)
    
    def test_get_root_raises(self):
        """Get with empty path raises BranchAccessError."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(BranchAccessError):
            doc.get([])


class TestYamlDocNoReferenceLeakage:
    """Test that returned values don't leak internal references."""
    
    def test_get_list_returns_copy(self):
        """Get returns deep copy of list values."""
        doc = YamlDoc({"items": [1, 2, 3]})
        
        items = doc.get(["items"])
        items.append(4)
        
        # Internal list unchanged
        assert doc.get(["items"]) == [1, 2, 3]
    
    def test_get_nested_list_returns_deep_copy(self):
        """Get returns deep copy of nested lists."""
        doc = YamlDoc({"matrix": [[1, 2], [3, 4]]})
        
        matrix = doc.get(["matrix"])
        matrix[0].append(99)
        
        # Internal list unchanged
        assert doc.get(["matrix"]) == [[1, 2], [3, 4]]
    
    def test_export_copy_returns_deep_copy(self):
        """export_copy returns deep copy."""
        doc = YamlDoc({"branch": {"a": 1, "list": [1, 2]}})
        
        branch = doc.export_copy(["branch"])
        branch["a"] = 999
        branch["list"].append(3)
        
        # Internal unchanged
        assert doc.get(["branch", "a"]) == 1
        assert doc.get(["branch", "list"]) == [1, 2]
    
    def test_to_dict_returns_deep_copy(self):
        """to_dict returns deep copy of entire document."""
        doc = YamlDoc({"nested": {"list": [1, 2]}})
        
        data = doc.to_dict()
        data["nested"]["list"].append(3)
        
        # Internal unchanged
        assert doc.get(["nested", "list"]) == [1, 2]
    
    def test_snapshot_returns_deep_copy(self):
        """get_snapshot returns deep copy."""
        doc = YamlDoc({"a": [1, 2]})
        
        snapshot = doc.get_snapshot()
        snapshot["a"].append(3)
        
        # Snapshot unchanged on subsequent call
        assert doc.get_snapshot() == {"a": [1, 2]}


class TestYamlDocListKeys:
    """Test list_keys() for branch navigation."""
    
    def test_list_keys_root(self):
        """list_keys with empty path lists root keys."""
        doc = YamlDoc({"a": 1, "b": 2, "c": 3})
        assert set(doc.list_keys()) == {"a", "b", "c"}
    
    def test_list_keys_nested(self):
        """list_keys traverses to nested dict."""
        doc = YamlDoc({"level1": {"x": 1, "y": 2, "z": 3}})
        assert set(doc.list_keys(["level1"])) == {"x", "y", "z"}
    
    def test_list_keys_nonexistent_raises(self):
        """list_keys raises for nonexistent path."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(PathNotFoundError):
            doc.list_keys(["nonexistent"])
    
    def test_list_keys_on_leaf_raises(self):
        """list_keys raises for non-dict path."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(BranchAccessError):
            doc.list_keys(["a"])


class TestYamlDocSet:
    """Test set() for value modification."""
    
    def test_set_new_key(self):
        """Set creates new key."""
        doc = YamlDoc()
        doc.set(["a"], 1)
        assert doc.get(["a"]) == 1
    
    def test_set_overwrite(self):
        """Set overwrites existing value."""
        doc = YamlDoc({"a": 1})
        doc.set(["a"], 2)
        assert doc.get(["a"]) == 2
    
    def test_set_creates_intermediate_dicts(self):
        """Set creates intermediate dicts as needed."""
        doc = YamlDoc()
        doc.set(["level1", "level2", "value"], 42)
        assert doc.get(["level1", "level2", "value"]) == 42
    
    def test_set_empty_path_raises(self):
        """Set with empty path raises."""
        doc = YamlDoc()
        
        with pytest.raises(YamlDocError):
            doc.set([], {"a": 1})
    
    def test_set_list_deep_copies(self):
        """Set deep copies list values."""
        doc = YamlDoc()
        lst = [1, 2, 3]
        doc.set(["items"], lst)
        
        lst.append(4)
        assert doc.get(["items"]) == [1, 2, 3]
    
    def test_set_dict_raises(self):
        """Set rejects dict values (use apply_patch instead)."""
        doc = YamlDoc()
        data = {"a": 1}
        
        with pytest.raises(YamlDocError) as exc_info:
            doc.set(["nested"], data)
        
        assert "apply_patch" in str(exc_info.value)


class TestYamlDocDelete:
    """Test delete() for value removal."""
    
    def test_delete_existing(self):
        """Delete removes existing key."""
        doc = YamlDoc({"a": 1, "b": 2})
        
        result = doc.delete(["a"])
        assert result is True
        assert not doc.has(["a"])
        assert doc.get(["b"]) == 2
    
    def test_delete_nonexistent(self):
        """Delete returns False for nonexistent key."""
        doc = YamlDoc({"a": 1})
        
        result = doc.delete(["nonexistent"])
        assert result is False
    
    def test_delete_nested(self):
        """Delete removes nested key."""
        doc = YamlDoc({"level1": {"a": 1, "b": 2}})
        
        doc.delete(["level1", "a"])
        
        assert not doc.has(["level1", "a"])
        assert doc.get(["level1", "b"]) == 2
    
    def test_delete_branch(self):
        """Delete removes entire branch."""
        doc = YamlDoc({"branch": {"a": 1, "b": 2}})
        
        doc.delete(["branch"])
        
        assert not doc.has(["branch"])
    
    def test_delete_root_raises(self):
        """Delete with empty path raises."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(YamlDocError):
            doc.delete([])


class TestYamlDocApplyPatch:
    """Test apply_patch() with Delete Semantics A."""
    
    def test_apply_patch_simple(self):
        """Apply patch sets values."""
        doc = YamlDoc({"a": 1})
        
        doc.apply_patch({"b": 2, "c": 3})
        
        assert doc.get(["a"]) == 1
        assert doc.get(["b"]) == 2
        assert doc.get(["c"]) == 3
    
    def test_apply_patch_nested(self):
        """Apply patch handles nested dicts."""
        doc = YamlDoc()
        
        doc.apply_patch({
            "SYSTEM": {
                "ecutwfc": 60,
                "ecutrho": 480,
            },
            "ELECTRONS": {
                "conv_thr": 1e-8,
            },
        })
        
        assert doc.get(["SYSTEM", "ecutwfc"]) == 60
        assert doc.get(["SYSTEM", "ecutrho"]) == 480
        assert doc.get(["ELECTRONS", "conv_thr"]) == 1e-8
    
    def test_apply_patch_none_deletes(self):
        """Delete Semantics A: None in patch deletes key."""
        doc = YamlDoc({"a": 1, "b": 2, "c": 3})
        
        doc.apply_patch({"a": None})
        
        assert not doc.has(["a"])
        assert doc.get(["b"]) == 2
        assert doc.get(["c"]) == 3
    
    def test_apply_patch_nested_delete(self):
        """Delete Semantics A: None deletes nested keys."""
        doc = YamlDoc({
            "SYSTEM": {"nspin": 2, "ecutwfc": 60},
        })
        
        doc.apply_patch({
            "SYSTEM": {
                "nspin": None,  # Delete
                "ecutrho": 480,  # Add
            },
        })
        
        assert not doc.has(["SYSTEM", "nspin"])
        assert doc.get(["SYSTEM", "ecutwfc"]) == 60
        assert doc.get(["SYSTEM", "ecutrho"]) == 480
    
    def test_apply_patch_with_base_path(self):
        """Apply patch respects base_path."""
        doc = YamlDoc({
            "parameters": {
                "SYSTEM": {"a": 1},
            },
        })
        
        doc.apply_patch(
            {"SYSTEM": {"b": 2}},
            base_path=["parameters"],
        )
        
        assert doc.get(["parameters", "SYSTEM", "a"]) == 1
        assert doc.get(["parameters", "SYSTEM", "b"]) == 2
    
    def test_apply_patch_overwrites(self):
        """Apply patch overwrites existing values."""
        doc = YamlDoc({"a": 1})
        
        doc.apply_patch({"a": 99})
        
        assert doc.get(["a"]) == 99

    def test_apply_patch_scan_token_replaces_scalar(self):
        """Scan token string replaces scalar leaf (regression test for parameter scan)."""
        doc = YamlDoc({
            "parameters": {
                "SYSTEM": {
                    "ecutrho": 320,
                },
            },
        })
        
        # Apply patch: replace scalar with scan token string
        doc.apply_patch({
            "parameters": {
                "SYSTEM": {
                    "ecutrho": "@scan:scan001",
                },
            },
        })
        
        # Assert scan token is set correctly
        result = doc.get(["parameters", "SYSTEM", "ecutrho"])
        assert result == "@scan:scan001"
    
    def test_apply_patch_scalar_replaces_scan_token(self):
        """Scalar replaces scan token string (reverse direction)."""
        doc = YamlDoc({
            "parameters": {
                "SYSTEM": {
                    "ecutrho": "@scan:scan001",
                },
            },
        })
        
        # Apply patch: replace scan token with scalar
        doc.apply_patch({
            "parameters": {
                "SYSTEM": {
                    "ecutrho": 330,
                },
            },
        })
        
        # Assert scalar is set correctly
        assert doc.get(["parameters", "SYSTEM", "ecutrho"]) == 330


class TestYamlDocHas:
    """Test has() for existence checks."""
    
    def test_has_existing(self):
        """has returns True for existing paths."""
        doc = YamlDoc({"a": 1, "nested": {"b": 2}})
        
        assert doc.has(["a"])
        assert doc.has(["nested"])
        assert doc.has(["nested", "b"])
    
    def test_has_nonexistent(self):
        """has returns False for nonexistent paths."""
        doc = YamlDoc({"a": 1})
        
        assert not doc.has(["nonexistent"])
        assert not doc.has(["a", "deep"])
    
    def test_contains_syntax(self):
        """path in doc syntax works."""
        doc = YamlDoc({"a": 1})
        
        assert ["a"] in doc
        assert ["nonexistent"] not in doc


class TestYamlDocSnapshot:
    """Test snapshot and Journal readiness features."""
    
    def test_snapshot_independent_of_changes(self):
        """Snapshot reflects initial state, not changes."""
        doc = YamlDoc({"a": 1})
        
        doc.set(["a"], 99)
        doc.set(["b"], 2)
        
        assert doc.get_snapshot() == {"a": 1}
        assert doc.to_dict() == {"a": 99, "b": 2}
    
    def test_commit_updates_snapshot(self):
        """commit_changes updates snapshot to current state."""
        doc = YamlDoc({"a": 1})
        
        doc.set(["a"], 99)
        result = doc.commit_changes()
        
        assert result == {"a": 99}
        assert doc.get_snapshot() == {"a": 99}
    
    def test_reset_to_snapshot(self):
        """reset_to_snapshot reverts to initial state."""
        doc = YamlDoc({"a": 1, "b": 2})
        
        doc.set(["a"], 99)
        doc.delete(["b"])
        
        doc.reset_to_snapshot()
        
        assert doc.to_dict() == {"a": 1, "b": 2}
    
    def test_reset_without_snapshot_raises(self):
        """reset_to_snapshot raises if snapshot disabled."""
        doc = YamlDoc({"a": 1}, snapshot=False)
        
        with pytest.raises(YamlDocError):
            doc.reset_to_snapshot()


# =============================================================================
# StepDoc Tests
# =============================================================================


class TestStepDocNormalization:
    """Test StepDoc section normalization."""
    
    def test_uppercase_namelist_sections(self):
        """Namelist sections are uppercased."""
        data = {
            "system": {"ecutwfc": 60},
            "electrons": {"conv_thr": 1e-8},
        }
        doc = StepDoc(data)
        
        assert doc.has(["SYSTEM"])
        assert doc.has(["ELECTRONS"])
        assert doc.get(["SYSTEM", "ecutwfc"]) == 60
    
    def test_set_normalizes_section(self):
        """set() normalizes section names."""
        doc = StepDoc()
        
        doc.set(["system", "ecutwfc"], 60)
        
        assert doc.has(["SYSTEM"])
        assert doc.get(["SYSTEM", "ecutwfc"]) == 60
    
    def test_alias_normalization(self):
        """Parameter aliases are normalized."""
        doc = StepDoc()
        
        doc.set(["SYSTEM", "smearing"], "gauss")
        
        assert doc.get(["SYSTEM", "smearing"]) == "gaussian"


class TestStepDocAccessControl:
    """Test StepDoc access control."""
    
    def test_no_access_control_allows_all(self):
        """Without access control, all writes allowed."""
        doc = StepDoc(access_control=False)
        
        doc.set(["meta", "id"], "test")
        doc.set(["parameters", "SYSTEM", "ecutwfc"], 60)
        
        assert doc.get(["meta", "id"]) == "test"
    
    def test_compiler_can_write_parameters(self):
        """Compiler can write to parameters."""
        doc = StepDoc(access_control=True, owner="compiler")
        
        doc.set(["parameters", "SYSTEM", "ecutwfc"], 60)
        
        assert doc.get(["parameters", "SYSTEM", "ecutwfc"]) == 60
    
    def test_compiler_can_write_cards(self):
        """Compiler can write to cards."""
        doc = StepDoc(access_control=True, owner="compiler")
        
        # Use apply_patch for nested dict values (set() rejects dicts)
        doc.apply_patch({"cards": {"K_POINTS": {"option": "automatic"}}})
        
        # Access via export_copy since it's a dict
        assert doc.export_copy(["cards", "K_POINTS"]) == {"option": "automatic"}
    
    def test_compiler_cannot_write_meta(self):
        """Compiler cannot write to meta."""
        doc = StepDoc(access_control=True, owner="compiler")
        
        with pytest.raises(AccessControlError):
            doc.set(["meta", "id"], "new_id")
    
    def test_detector_is_read_only(self):
        """Detector cannot write anything."""
        doc = StepDoc({"parameters": {"SYSTEM": {"a": 1}}}, access_control=True, owner="detector")
        
        with pytest.raises(AccessControlError):
            doc.set(["parameters", "SYSTEM", "b"], 2)
    
    def test_user_can_write_all(self):
        """User can write to all paths."""
        doc = StepDoc(access_control=True, owner="user")
        
        doc.set(["meta", "id"], "test")
        doc.set(["parameters", "SYSTEM", "ecutwfc"], 60)
        doc.set(["custom_field"], "value")
        
        assert doc.get(["meta", "id"]) == "test"


# =============================================================================
# IO Tests
# =============================================================================


class TestYamlIO:
    """Test YAML IO utilities."""
    
    def test_load_save_roundtrip(self, tmp_path):
        """Load and save preserves data."""
        path = tmp_path / "test.yaml"
        
        original = {"a": 1, "nested": {"b": 2, "list": [1, 2, 3]}}
        _save_yaml_raw(original, path)
        
        loaded = _load_yaml_raw(path)
        
        assert loaded == original
    
    def test_load_nonexistent_raises(self, tmp_path):
        """Loading nonexistent file raises."""
        with pytest.raises(FileNotFoundError):
            _load_yaml_raw(tmp_path / "nonexistent.yaml")
    
    def test_load_yaml_doc(self, tmp_path):
        """load_yaml_doc returns YamlDoc."""
        path = tmp_path / "test.yaml"
        _save_yaml_raw({"a": 1}, path)
        
        doc = load_yaml_doc(path)
        
        assert isinstance(doc, YamlDoc)
        assert doc.get(["a"]) == 1
    
    def test_save_yaml_doc(self, tmp_path):
        """save_yaml_doc writes and commits."""
        path = tmp_path / "test.yaml"
        
        doc = YamlDoc({"a": 1})
        doc.set(["b"], 2)
        
        save_yaml_doc(doc, path)
        
        loaded = _load_yaml_raw(path)
        assert loaded == {"a": 1, "b": 2}
        
        # Snapshot updated after save
        assert doc.get_snapshot() == {"a": 1, "b": 2}
    
    def test_load_step_doc(self, tmp_path):
        """load_step_doc returns StepDoc."""
        path = tmp_path / "test.step.yaml"
        _save_yaml_raw({"system": {"ecutwfc": 60}}, path)
        
        doc = load_step_doc(path)
        
        assert isinstance(doc, StepDoc)
        assert doc.get(["SYSTEM", "ecutwfc"]) == 60
    
    def test_step_doc_save_load_roundtrip(self, tmp_path):
        """StepDoc save/load preserves data."""
        path = tmp_path / "step.yaml"
        
        doc = StepDoc({
            "meta": {"ulid": "test"},
            "step_type_gen": "scf",
            "parameters": {
                "SYSTEM": {"ecutwfc": 60},
            },
        })
        doc.save(path)
        
        loaded = StepDoc.load(path)
        
        assert loaded.get(["step_type"]) == "scf"
        assert loaded.get(["parameters", "SYSTEM", "ecutwfc"]) == 60


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_path_as_tuple(self):
        """Paths can be tuples."""
        doc = YamlDoc({"a": {"b": 1}})
        
        assert doc.get(("a", "b")) == 1
        
        doc.set(("a", "c"), 2)
        assert doc.get(("a", "c")) == 2
    
    def test_intermediate_non_dict_raises(self):
        """Navigating through non-dict raises."""
        doc = YamlDoc({"a": 1})
        
        with pytest.raises(YamlDocError):
            doc.set(["a", "b"], 2)
    
    def test_none_as_explicit_value(self):
        """set(path, None) stores None (not delete)."""
        doc = YamlDoc()
        
        doc.set(["a"], None)
        
        assert doc.has(["a"])
        assert doc.get(["a"]) is None
    
    def test_apply_patch_empty(self):
        """Empty patch is no-op."""
        doc = YamlDoc({"a": 1})
        
        doc.apply_patch({})
        
        assert doc.to_dict() == {"a": 1}
    
    def test_repr(self):
        """Repr shows keys."""
        doc = YamlDoc({"a": 1, "b": 2})
        
        repr_str = repr(doc)
        
        assert "YamlDoc" in repr_str
        assert "a" in repr_str or "b" in repr_str

