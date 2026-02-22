"""
Dataclasses representing a QMatSuite project on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.core.resolution import ResourceIndex

from qmatsuite.core.resources import (
    ResourceMeta,
    ResourceKind,
    ensure_relative_path,
    meta_from_name,
)


@dataclass(slots=True)
class ProjectSettings:
    """
    Global project settings (parallelism, default tolerances, etc.).

    Stored as a simple dictionary but exposed via a dataclass for type safety.
    """

    data: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.data.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


@dataclass(slots=True)
class StructureRef:
    """
    Reference to a structure file inside the project.

    Structures are resolved relative to ``project.root / "structures"``.
    """

    meta: ResourceMeta
    absolute_path: Path
    format: str = "auto"  # e.g. "cif", "qe_input", "internal"

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class CalculationRef:
    """
    Reference to a calculation folder (which is also the calculation workdir).
    """

    meta: ResourceMeta
    absolute_path: Path

    @property
    def name(self) -> str:
        return self.meta.name

    @property
    def slug(self) -> str:
        return self.meta.slug

    def relative_path(self) -> str:
        return self.meta.path

    @property
    def path(self) -> Path:
        return self.absolute_path

    def resolve_path(self, project_root: Path) -> Path:
        return self.meta.resolved_path(project_root)


@dataclass(slots=True)
class Project:
    """
    Container for structures, calculations, pseudo potentials, and settings.
    """

    root: Path
    meta: ResourceMeta
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    structures: Dict[str, StructureRef] = field(default_factory=dict)
    calculations: Dict[str, CalculationRef] = field(default_factory=dict)

    @classmethod
    def open(cls, project_root: Path | str) -> "Project":
        """
        Load project metadata from ``project.qms.yml``.
        """
        root = Path(project_root).resolve()
        config_file = root / "project.qms.yml"
        if not config_file.exists():
            raise FileNotFoundError(f"project.qms.yml not found under {root}")

        from qmatsuite.core.yamldoc import ProjectDoc
        data = ProjectDoc.load(config_file).to_dict()
        project_section = data.get("project", {})
        project_name = project_section.get("name") or root.name
        project_meta = ResourceMeta.from_dict(
            project_section.get("meta"),
            kind="project",
            default_name=project_name,
            default_path=".",
        )

        settings = ProjectSettings(data.get("settings", {}))

        project = cls(root=root, meta=project_meta, settings=settings)
        # Project.open() is self-contained and builds its own index internally
        # This keeps it simple and avoids issues with mismatched index/project_root
        project.structures = cls._load_structures(
            root, data.get("structures", []), project_section.get("structures_dir", "structures")
        )
        project.calculations = cls._load_calculations(
            root, data.get("calculations", []), project_section.get("calculations_dir", "calculations")
        )
        return project

    @staticmethod
    def _load_structures(
        root: Path, entries: list[dict], default_dir: str
    ) -> Dict[str, StructureRef]:
        """
        Load structures from project entries.
        
        In the new DAG + ID-only model:
        - Entries have structure_ulid (ULID), not file path
        - Structure file location is resolved via ResourceIndex using structure_ulid
        - Structure meta (name, slug, path) is loaded from the structure file itself
        
        Args:
            root: Project root path
            entries: Structure entries from project.qms.yml
            default_dir: Default structures directory name
        """
        structures: Dict[str, StructureRef] = {}
        
        # Build index for this project only
        try:
            from qmatsuite.core.resolution import build_resource_index
            index = build_resource_index(root)
        except Exception:
            index = None
        
        for entry in entries:
            structure_ulid = entry.get("structure_ulid") or entry.get("ulid")
            legacy_file = entry.get("file")
            
            struct_meta: Optional[ResourceMeta] = None
            absolute_path: Optional[Path] = None
            
            # New DAG model: resolve structure_ulid via ResourceIndex
            if structure_ulid and index:
                try:
                    # Find structure in index by ID
                    if structure_ulid in index.by_id:
                        meta = index.by_id[structure_ulid]
                        if meta.kind == "structure":
                            struct_meta = meta
                            # Find absolute path from index
                            for path, path_id in index.by_path.items():
                                if path_id == structure_ulid:
                                    absolute_path = path
                                    break
                except Exception:
                    pass
            
            # Legacy: use file path if available
            if not absolute_path and legacy_file:
                default_path = legacy_file
                absolute_path = (root / default_path).resolve()
                if absolute_path.exists():
                    # Load meta from structure file
                    try:
                        import json
                        data = json.loads(absolute_path.read_text())
                        meta_dict = data.get("__qms_meta__") or data.get("meta") or {}
                        struct_meta = ResourceMeta.from_dict(
                            meta_dict,
                            kind="structure",
                            default_name=Path(legacy_file).stem,
                            default_path=default_path,
                        )
                    except Exception:
                        # Fallback: construct meta from file path
                        default_name = entry.get("name") or Path(legacy_file).stem
                        struct_meta = _entry_to_meta(
                            entry=entry,
                            root=root,
                            kind="structure",
                            default_path=default_path,
                            default_name=default_name,
                        )
            
            # If still no meta, construct from entry (fallback)
            if not struct_meta:
                default_name = entry.get("name") or entry.get("ulid") or Path(
                    legacy_file or "structure"
                ).stem
                default_path = legacy_file or f"{default_dir.rstrip('/')}/{default_name}.json"
                struct_meta = _entry_to_meta(
                    entry=entry,
                    root=root,
                    kind="structure",
                    default_path=default_path,
                    default_name=default_name,
                )
                if not absolute_path:
                    absolute_path = (root / struct_meta.path).resolve()
            
            ref = StructureRef(
                meta=struct_meta,
                absolute_path=absolute_path or (root / struct_meta.path).resolve(),
                format=entry.get("format", "auto"),
            )
            structures[ref.slug] = ref
        return structures

    @staticmethod
    def _load_calculations(
        root: Path, entries: list[dict], default_dir: str
    ) -> Dict[str, CalculationRef]:
        """
        Load calculations from project entries using ID-based resolution.
        
        Resolution strategy (in order):
        1. Try registry-based resolution by calculation_id (preferred for ID-only model)
        2. Fall back to entry["path"] if available (legacy support)
        3. Fall back to scanning calculations/*/calculation.yaml by meta.ulid
        4. Raise error if calculation directory cannot be found
        
        Args:
            root: Project root path
            entries: Calculation entries from project.qms.yml
            default_dir: Default calculations directory name
        """
        from qmatsuite.core.resolution import build_resource_index, require_calculation, ResourceNotFoundError
        from qmatsuite.core.resources import ResourceMeta
        
        calculations: Dict[str, CalculationRef] = {}
        calculations_dir = root / default_dir.rstrip('/')
        
        # Build index for this project only
        try:
            registry = build_resource_index(root)
        except Exception:
            registry = None
        
        for entry in entries:
            calculation_id = entry.get("calculation_id") or entry.get("ulid")
            if not calculation_id:
                # Skip entries without ID (should not happen in ID-only model)
                continue
            
            calculation_dir = None
            calculation_yaml_path = None
            calculation_meta = None
            
            # Strategy 1: Try registry-based resolution (preferred for ID-only model)
            if registry:
                try:
                    resolved = require_calculation(root, calculation_id, index=registry)
                    # resolved.absolute_path points to calculation.yaml, so get parent directory
                    if resolved.absolute_path.name == "calculation.yaml":
                        calculation_dir = resolved.absolute_path.parent
                    else:
                        calculation_dir = resolved.absolute_path
                    calculation_yaml_path = calculation_dir / "calculation.yaml"
                    calculation_meta = resolved.meta
                    # Prefer name from entry (project.qms.yml) over registry if entry has a human-readable name
                    entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                    if entry_name and entry_name != calculation_meta.slug:
                        # Entry has a human-readable name - use it instead of registry name
                        calculation_meta = ResourceMeta(ulid=calculation_meta.ulid,
                            name=entry_name,
                            slug=calculation_meta.slug,
                            path=calculation_meta.path,
                            kind=calculation_meta.kind,
                        )
                except (ResourceNotFoundError, Exception):
                    # Registry resolution failed, try fallback strategies
                    pass
            
            # Strategy 2: Fall back to entry["path"] if available (legacy support)
            if calculation_dir is None:
                entry_path = entry.get("path") or (entry.get("meta") or {}).get("path")
                if entry_path:
                    candidate_dir = (root / entry_path).resolve()
                    candidate_yaml = candidate_dir / "calculation.yaml"
                    if candidate_yaml.exists():
                        try:
                            from qmatsuite.core.yamldoc import CalcDoc
                            wf_data = CalcDoc.load(candidate_yaml).to_dict()
                            wf_meta_dict = wf_data.get("meta") or {}
                            # Verify the ID matches
                            if wf_meta_dict.get("ulid") == calculation_id:
                                calculation_dir = candidate_dir
                                calculation_yaml_path = candidate_yaml
                                # Prefer name from entry (project.qms.yml) over calculation.yaml if entry has a human-readable name
                                entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Calculation")
                                calculation_meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="calculation",
                                    default_name=default_name,
                                    default_path=entry_path,
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != calculation_meta.slug:
                                    calculation_meta.name = entry_name
                                break
                        except Exception:
                            continue
            
            # Strategy 3: Scan calculations/*/calculation.yaml by meta.ulid (last resort)
            if calculation_dir is None and calculations_dir.exists():
                for wf_dir in calculations_dir.iterdir():
                    if not wf_dir.is_dir():
                        continue
                    wf_yaml = wf_dir / "calculation.yaml"
                    if wf_yaml.exists():
                        try:
                            from qmatsuite.core.yamldoc import CalcDoc
                            wf_data = CalcDoc.load(wf_yaml).to_dict()
                            wf_meta_dict = wf_data.get("meta") or {}
                            if wf_meta_dict.get("ulid") == calculation_id:
                                calculation_dir = wf_dir
                                calculation_yaml_path = wf_yaml
                                # Prefer name from entry (project.qms.yml) over calculation.yaml if entry has a human-readable name
                                entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                                default_name = entry_name if entry_name and entry_name != wf_meta_dict.get("slug") else wf_meta_dict.get("name", "Calculation")
                                calculation_meta = ResourceMeta.from_dict(
                                    wf_meta_dict,
                                    kind="calculation",
                                    default_name=default_name,
                                    default_path=wf_meta_dict.get("path") or f"{default_dir.rstrip('/')}/{wf_dir.name}",
                                )
                                # Override with entry name if it's different from slug (preserves human-readable names)
                                if entry_name and entry_name != calculation_meta.slug:
                                    calculation_meta.name = entry_name
                                break
                        except Exception:
                            continue
            
            # Strategy 4: If still not found, raise clear error
            if calculation_dir is None or calculation_yaml_path is None or not calculation_yaml_path.exists():
                raise FileNotFoundError(
                    f"Could not locate calculation directory for id '{calculation_id}' under {calculations_dir}. "
                    "Please ensure the calculation.yaml file exists and contains the correct meta.ulid."
                )
            
            # Ensure calculation_meta is set (should have been set by one of the strategies above)
            if calculation_meta is None:
                # Fallback: construct from entry (should not happen if strategies above worked)
                default_name = entry.get("name") or "calculation"
                default_path = entry.get("path") or f"{default_dir.rstrip('/')}/{default_name}"
                calculation_meta = _entry_to_meta(
                    entry=entry,
                    root=root,
                    kind="calculation",
                    default_path=default_path,
                    default_name=default_name,
                )
                # Try to load from calculation.yaml to get canonical name/slug
                # But prefer name from entry (project.qms.yml) if it exists and is different from slug
                try:
                    from qmatsuite.core.yamldoc import CalcDoc
                    wf_data = CalcDoc.load(calculation_yaml_path).to_dict()
                    wf_meta = wf_data.get("meta") or {}
                    # Prefer name from entry (project.qms.yml) over calculation.yaml if entry has a human-readable name
                    entry_name = entry.get("name") or (entry.get("meta") or {}).get("name")
                    if entry_name and entry_name != calculation_meta.slug:
                        # Entry has a human-readable name - use it instead of calculation.yaml name
                        calculation_meta.name = entry_name
                    elif wf_meta.get("name"):
                        calculation_meta.name = wf_meta["name"]
                    if wf_meta.get("slug"):
                        calculation_meta.slug = wf_meta["slug"]
                    if wf_meta.get("path"):
                        calculation_meta.path = wf_meta["path"]
                except Exception:
                    pass  # Use defaults from entry
            
            # Create CalculationRef
            ref = CalculationRef(
                meta=calculation_meta,
                absolute_path=calculation_dir.resolve(),
            )
            calculations[ref.slug] = ref
        
        return calculations

    @property
    def structures_dir(self) -> Path:
        return self.root / "structures"

    @property
    def calculations_dir(self) -> Path:
        return self.root / "calculations"

    @property
    def pseudo_dir(self) -> Path:
        return self.root / "pseudo"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.yaml"

    def list_structures(self) -> list[str]:
        return [ref.meta.name for ref in self.structures.values()]

    def get_structure(self, structure_ulid: str) -> StructureRef:
        # Accept slug, name, or meta id for ergonomics
        if structure_ulid in self.structures:
            return self.structures[structure_ulid]

        for ref in self.structures.values():
            if ref.meta.ulid == structure_ulid or ref.meta.name == structure_ulid:
                return ref
        raise KeyError(f"Unknown structure '{structure_ulid}'")

    def list_calculations(self) -> list[str]:
        return [ref.meta.name for ref in self.calculations.values()]

    def get_calculation_ref(self, calculation_id: str) -> CalculationRef:
        if calculation_id in self.calculations:
            return self.calculations[calculation_id]
        for ref in self.calculations.values():
            if ref.meta.ulid == calculation_id or ref.meta.name == calculation_id or ref.meta.slug == calculation_id:
                return ref
        raise KeyError(f"Unknown calculation '{calculation_id}'")

    def get_calculation(self, calculation_id: str):
        """
        Load and return a calculation instance for inspection.
        
        This method loads calculations in inspection mode (materialize_steps=False),
        which does not require pseudopotentials or step materialization.
        For execution, use run_calculation or run_step APIs instead.
        """
        from qmatsuite.calculation.calculation import Calculation

        ref = self.get_calculation_ref(calculation_id)
        return Calculation.from_yaml(ref.resolve_path(self.root), self, materialize_steps=False)

    def structure_ref(self, name: str) -> StructureRef:
        """
        Return a structure reference relative to the structures directory.
        """
        structure_path = self.structures_dir / name
        meta = meta_from_name(
            "structure",
            name=name,
            path=ensure_relative_path(structure_path, base=self.root),
        )
        return StructureRef(meta=meta, absolute_path=structure_path.resolve())


def _entry_to_meta(
    *,
    entry: dict,
    root: Path,
    kind: ResourceKind,
    default_path: str,
    default_name: str,
) -> ResourceMeta:
    path_obj = Path(default_path)
    if path_obj.is_absolute():
        try:
            path_obj = path_obj.relative_to(root)
        except ValueError:
            pass
    relative_path = path_obj.as_posix()

    return ResourceMeta.from_dict(
        entry.get("meta"),
        kind=kind,
        default_name=default_name,
        default_path=relative_path,
    )

