"""
YamlDoc: Unified YAML document abstraction with mutation containment.

This module provides compiler-grade containment for YAML mutations:
- All mutations go through set/delete/apply_patch
- No reference leakage: get() returns deep copies for containers
- Prepared for Journal integration at save boundary

Per docs/yamldoc_refactor_plan.md:
- Delete Semantics A: None/null in patches means delete
- Paths are tokenized: list[str] only, no dotted strings in core
- Branch replacement forbidden: use apply_patch for subtree updates
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional, Union


class _Missing:
    """Sentinel for missing values (distinct from None)."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __repr__(self):
        return "<MISSING>"


MISSING = _Missing()


class YamlDocError(Exception):
    """Base exception for YamlDoc errors."""
    pass


class PathNotFoundError(YamlDocError):
    """Raised when a path doesn't exist."""
    pass


class BranchAccessError(YamlDocError):
    """Raised when trying to get() a branch (dict) without using export_copy()."""
    pass


class AccessControlError(YamlDocError):
    """Raised when access control rules are violated."""
    pass


PathType = Union[list[str], tuple[str, ...]]


def _normalize_path(path: PathType) -> tuple[str, ...]:
    """Convert path to immutable tuple."""
    if isinstance(path, tuple):
        return path
    return tuple(path)


def _deep_copy(value: Any) -> Any:
    """Deep copy a value, handling common types efficiently."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return copy.deepcopy(value)


class YamlDoc:
    """
    Generic YAML document wrapper with mutation containment.
    
    All mutations go through set/delete/apply_patch.
    No reference leakage: get() returns deep copies for containers.
    
    Paths are tokenized (list[str] or tuple[str, ...]).
    """
    
    __slots__ = ("_data", "_snapshot", "_snapshot_enabled")
    
    def __init__(
        self,
        data: Optional[dict] = None,
        *,
        snapshot: bool = True,
    ):
        """
        Initialize document.
        
        Args:
            data: Initial data (deep copied internally)
            snapshot: If True, store initial snapshot for Journal diff
        """
        # Always deep copy incoming data to prevent external mutation
        self._data: dict = _deep_copy(data) if data is not None else {}
        self._snapshot_enabled = snapshot
        self._snapshot: Optional[dict] = None
        
        if snapshot:
            self._snapshot = _deep_copy(self._data)
    
    def _navigate_to_parent(
        self,
        path: PathType,
        *,
        create: bool = False,
    ) -> tuple[dict, str]:
        """
        Navigate to parent dict of the final path component.
        
        Args:
            path: Path to navigate
            create: If True, create intermediate dicts
            
        Returns:
            Tuple of (parent_dict, final_key)
            
        Raises:
            PathNotFoundError: If path doesn't exist and create=False
            YamlDocError: If intermediate path is not a dict
        """
        path = _normalize_path(path)
        if not path:
            raise YamlDocError("Empty path")
        
        current = self._data
        for i, key in enumerate(path[:-1]):
            if key not in current:
                if create:
                    current[key] = {}
                else:
                    raise PathNotFoundError(
                        f"Path not found: {'.'.join(path[:i+1])}"
                    )
            
            next_val = current[key]
            if not isinstance(next_val, dict):
                raise YamlDocError(
                    f"Path component '{key}' is not a dict at {'.'.join(path[:i+1])}"
                )
            current = next_val
        
        return current, path[-1]
    
    def _get_value_at_path(self, path: PathType) -> tuple[bool, Any]:
        """
        Get value at path.
        
        Returns:
            Tuple of (exists, value)
        """
        path = _normalize_path(path)
        if not path:
            return (True, self._data)
        
        try:
            parent, key = self._navigate_to_parent(path, create=False)
            if key in parent:
                return (True, parent[key])
            return (False, None)
        except (PathNotFoundError, YamlDocError):
            # YamlDocError is raised when intermediate path is not a dict
            # Treat this as path not found
            return (False, None)
    
    # =========================================================================
    # Read Operations
    # =========================================================================
    
    def list_keys(self, path: PathType = ()) -> list[str]:
        """
        List keys at a branch path.
        
        Args:
            path: Path to branch (empty for root)
            
        Returns:
            List of key names at that branch
            
        Raises:
            PathNotFoundError: If path doesn't exist
            BranchAccessError: If path is not a dict
        """
        path = _normalize_path(path)
        
        if not path:
            if not isinstance(self._data, dict):
                raise BranchAccessError("Root is not a dict")
            return list(self._data.keys())
        
        try:
            parent, key = self._navigate_to_parent(path, create=False)
            if key not in parent:
                raise PathNotFoundError(f"Path not found: {'.'.join(path)}")
            
            value = parent[key]
            if not isinstance(value, dict):
                raise BranchAccessError(
                    f"Path '{'.'.join(path)}' is not a branch (dict)"
                )
            return list(value.keys())
        except PathNotFoundError:
            raise PathNotFoundError(f"Path not found: {'.'.join(path)}")
    
    def get(
        self,
        path: PathType,
        default: Any = MISSING,
    ) -> Any:
        """
        Get leaf value at path.
        
        - If leaf is list: returns deep copy
        - If leaf is scalar: returns value
        - If path is dict (branch): raises BranchAccessError
        
        Args:
            path: Path to leaf
            default: Default value if path doesn't exist (MISSING raises)
            
        Returns:
            Leaf value (deep copy for containers)
            
        Raises:
            PathNotFoundError: If path doesn't exist and no default
            BranchAccessError: If path points to a dict (use export_copy)
        """
        path = _normalize_path(path)
        if not path:
            raise BranchAccessError(
                "Cannot get() root. Use export_copy() for branch access."
            )
        
        exists, value = self._get_value_at_path(path)
        
        if not exists:
            if default is MISSING:
                raise PathNotFoundError(f"Path not found: {'.'.join(path)}")
            return default
        
        # Prevent branch access via get()
        if isinstance(value, dict):
            raise BranchAccessError(
                f"Path '{'.'.join(path)}' is a branch (dict). Use export_copy() instead."
            )
        
        # Deep copy containers to prevent reference leakage
        if isinstance(value, list):
            return _deep_copy(value)
        
        # Scalars returned directly
        return value
    
    def has(self, path: PathType) -> bool:
        """Check if path exists."""
        exists, _ = self._get_value_at_path(path)
        return exists
    
    def export_copy(self, path: PathType = ()) -> Any:
        """
        Export a deep copy of subtree at path.
        
        This is the ONLY way to read branch (dict) values.
        
        Args:
            path: Path to subtree (empty for entire document)
            
        Returns:
            Deep copy of subtree
            
        Raises:
            PathNotFoundError: If path doesn't exist
        """
        path = _normalize_path(path)
        
        if not path:
            return _deep_copy(self._data)
        
        exists, value = self._get_value_at_path(path)
        if not exists:
            raise PathNotFoundError(f"Path not found: {'.'.join(path)}")
        
        return _deep_copy(value)
    
    def to_dict(self) -> dict:
        """Export entire document as deep copy."""
        return _deep_copy(self._data)
    
    # =========================================================================
    # Write Operations
    # =========================================================================
    
    def set(self, path: PathType, value: Any) -> None:
        """
        Set leaf value at path.
        
        - Creates intermediate dicts as needed
        - Deep copies list values to prevent reference leakage
        - Setting to None is allowed (explicit null value)
        - Setting a dict is FORBIDDEN (use apply_patch for subtree updates)
        
        For delete-on-set behavior, use delete() explicitly or apply_patch().
        
        Args:
            path: Path to set
            value: Value to set (deep copied if list)
            
        Raises:
            YamlDocError: If path is empty, intermediate is not dict, or value is dict
        """
        path = _normalize_path(path)
        if not path:
            raise YamlDocError("Cannot set root. Use apply_patch() for bulk updates.")
        
        # Reject dict values - use apply_patch for subtree updates
        if isinstance(value, dict):
            raise YamlDocError(
                f"Cannot set() a dict at path '{'.'.join(path)}'. "
                "Use apply_patch() for subtree updates."
            )
        
        # Deep copy lists before storing to prevent reference leakage
        if isinstance(value, list):
            value = _deep_copy(value)
        
        parent, key = self._navigate_to_parent(path, create=True)
        parent[key] = value
    
    def delete(self, path: PathType) -> bool:
        """
        Delete value at path (leaf or branch).
        
        Args:
            path: Path to delete
            
        Returns:
            True if deleted, False if path didn't exist
        """
        path = _normalize_path(path)
        if not path:
            raise YamlDocError("Cannot delete root")
        
        try:
            parent, key = self._navigate_to_parent(path, create=False)
            if key in parent:
                del parent[key]
                return True
            return False
        except PathNotFoundError:
            return False
    
    def apply_patch(
        self,
        patch: dict,
        base_path: PathType = (),
    ) -> None:
        """
        Apply a nested patch dict.
        
        Recursively walks patch to leaves:
        - None values trigger delete (Delete Semantics A)
        - Dict values recurse deeper
        - Other values trigger set
        
        Args:
            patch: Nested dict of changes
            base_path: Base path to apply patch at
            
        Example:
            doc.apply_patch({"SYSTEM": {"ecutwfc": 60, "nspin": None}})
            # Sets parameters.SYSTEM.ecutwfc = 60
            # Deletes parameters.SYSTEM.nspin
        """
        base_path = _normalize_path(base_path)
        self._apply_patch_recursive(patch, list(base_path))
    
    def _apply_patch_recursive(self, patch: dict, current_path: list[str]) -> None:
        """Recursively apply patch."""
        for key, value in patch.items():
            path = current_path + [key]
            
            if value is None:
                # Delete Semantics A: None means delete
                self.delete(path)
            elif isinstance(value, dict):
                # Recurse into nested dict
                self._apply_patch_recursive(value, path)
            else:
                # Set leaf value
                self.set(path, value)
    
    # =========================================================================
    # Journal Readiness
    # =========================================================================
    
    def get_snapshot(self) -> Optional[dict]:
        """
        Get initial snapshot (if stored).
        
        Returns None if snapshot was disabled at construction.
        """
        return _deep_copy(self._snapshot) if self._snapshot is not None else None
    
    def commit_changes(self) -> dict:
        """
        Mark save point. Returns the current data.
        
        Journal hook point: before/after can be diffed here.
        Updates snapshot to current state.
        
        Returns:
            Deep copy of current document state
        """
        current = _deep_copy(self._data)
        if self._snapshot_enabled:
            self._snapshot = current
        return current
    
    def reset_to_snapshot(self) -> None:
        """
        Reset document to initial snapshot state.
        
        Raises:
            YamlDocError: If snapshot was not enabled
        """
        if self._snapshot is None:
            raise YamlDocError("No snapshot available (snapshot=False at construction)")
        self._data = _deep_copy(self._snapshot)
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    def __repr__(self) -> str:
        keys = list(self._data.keys()) if isinstance(self._data, dict) else "..."
        return f"<YamlDoc keys={keys}>"
    
    def __contains__(self, path: PathType) -> bool:
        """Check if path exists. Supports `path in doc` syntax."""
        return self.has(path)


# =============================================================================
# Document-Specific Wrappers
# =============================================================================


class StepDoc(YamlDoc):
    """
    Step document with QE-specific normalization.
    
    - Section names uppercase (SYSTEM, ELECTRONS, etc.)
    - Parameter names lowercase for canonical storage
    - Alias normalization (gauss → gaussian)
    - Optional access control for detector/compiler paths
    """
    
    # Sections that should be uppercase
    NAMELIST_SECTIONS = frozenset({"CONTROL", "SYSTEM", "ELECTRONS", "IONS", "CELL"})
    
    # Parameter aliases (lowercase source → lowercase canonical)
    PARAM_ALIASES = {
        "gauss": "gaussian",
    }
    
    # Access control ownership (which paths each role can modify)
    OWNERSHIP = {
        "compiler": {"parameters", "cards", "species_overrides"},
        "detector": set(),  # Read-only
        "user": None,  # All paths (None = no restrictions)
    }
    
    __slots__ = ("_access_control", "_owner")
    
    def __init__(
        self,
        data: Optional[dict] = None,
        *,
        snapshot: bool = True,
        access_control: bool = False,
        owner: Optional[str] = None,
    ):
        """
        Args:
            data: Initial data
            snapshot: Store snapshot for Journal
            access_control: If True, enforce ownership rules
            owner: Owner identity ("compiler", "detector", "user")
        """
        # Normalize data before passing to parent
        if data is not None:
            data = self._normalize_sections(data)
        
        super().__init__(data, snapshot=snapshot)
        self._access_control = access_control
        self._owner = owner or "user"
    
    def _normalize_sections(self, data: dict) -> dict:
        """Normalize section names to uppercase for namelists."""
        result = {}
        for key, value in data.items():
            # Uppercase namelist sections
            if key.upper() in self.NAMELIST_SECTIONS:
                key = key.upper()
            
            if isinstance(value, dict):
                # Recursively normalize nested dicts
                value = self._normalize_sections(value)
            
            result[key] = value
        return result
    
    def _check_access(self, path: PathType, operation: str) -> None:
        """Check if current owner can access path."""
        if not self._access_control:
            return
        
        path = _normalize_path(path)
        if not path:
            return
        
        allowed_paths = self.OWNERSHIP.get(self._owner)
        if allowed_paths is None:
            # None means all paths allowed
            return
        
        # Check if root of path is in allowed paths
        root = path[0]
        if root not in allowed_paths:
            raise AccessControlError(
                f"Owner '{self._owner}' cannot {operation} path '{'.'.join(path)}'. "
                f"Allowed paths: {allowed_paths}"
            )
    
    def set(self, path: PathType, value: Any) -> None:
        """Set with access control and normalization."""
        self._check_access(path, "write to")
        
        # Normalize section name if at root level
        path = list(_normalize_path(path))
        if path and path[0].upper() in self.NAMELIST_SECTIONS:
            path[0] = path[0].upper()
        
        # Normalize parameter aliases
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in self.PARAM_ALIASES:
                value = self.PARAM_ALIASES[value_lower]
        
        super().set(path, value)
    
    def delete(self, path: PathType) -> bool:
        """Delete with access control."""
        self._check_access(path, "delete from")
        return super().delete(path)
    
    @classmethod
    def load(
        cls,
        path: Path,
        *,
        access_control: bool = False,
        owner: Optional[str] = None,
    ) -> "StepDoc":
        """
        Load step document from YAML file.
        
        Args:
            path: Path to step YAML file
            access_control: Enable access control
            owner: Owner identity
            
        Returns:
            StepDoc instance
        """
        from quantumvitas.core.yaml_io import _load_yaml_raw
        
        data = _load_yaml_raw(path)
        return cls(data, access_control=access_control, owner=owner)
    
    def get(self, path: PathType, default: Any = MISSING) -> Any:
        """
        Get value with backward compatibility for step_type.
        
        If reading step_type, converts machine type (qe_scf) to public type (scf)
        for backward compatibility with existing APIs/tests.
        """
        value = super().get(path, default)
        
        # Convert machine type to public type for step_type field
        if path == ("step_type_spec",) or path == ["step_type_spec"]:
            if isinstance(value, str):
                from quantumvitas.workflow.registry import get_registry
                registry = get_registry()
                spec = registry.get(value)
                if spec:
                    return spec.step_type_gen
        
        return value
    
    def save(self, path: Path) -> None:
        """
        Save step document to YAML file.
        
        Delegates to save_yaml_doc() for Journal integration.
        """
        from quantumvitas.core.yaml_io import save_yaml_doc
        
        save_yaml_doc(self, path)


class CalcDoc(YamlDoc):
    """
    Calculation document wrapper.
    
    Provides type-specific loading/saving for calculation.yaml files.
    """
    
    @classmethod
    def load(cls, path: Path) -> "CalcDoc":
        """Load calculation document from YAML file."""
        from quantumvitas.core.yaml_io import _load_yaml_raw
        
        if path.is_dir():
            path = path / "calculation.yaml"
        
        data = _load_yaml_raw(path)
        return cls(data)
    
    def save(self, path: Path) -> None:
        """
        Save calculation document to YAML file.
        
        Delegates to save_yaml_doc() for Journal integration.
        """
        from quantumvitas.core.yaml_io import save_yaml_doc
        
        save_yaml_doc(self, path)


class ProjectDoc(YamlDoc):
    """
    Project document wrapper.
    
    Provides type-specific loading/saving for project.qv.yml files.
    """
    
    @classmethod
    def load(cls, path: Path) -> "ProjectDoc":
        """Load project document from YAML file."""
        from quantumvitas.core.yaml_io import _load_yaml_raw
        
        if path.is_dir():
            path = path / "project.qv.yml"
        
        data = _load_yaml_raw(path)
        return cls(data)
    
    def save(self, path: Path) -> None:
        """
        Save project document to YAML file.
        
        Delegates to save_yaml_doc() for Journal integration.
        """
        from quantumvitas.core.yaml_io import save_yaml_doc
        
        save_yaml_doc(self, path)

