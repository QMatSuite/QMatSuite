from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from typing import TYPE_CHECKING

import yaml
from pymatgen.core import Structure as PMGStructure

from quantumvitas.core.resources import (
    ResourceMeta,
    ensure_relative_path,
    meta_from_name,
)
from quantumvitas.io import QEInputGenerator, read_structure
from quantumvitas.io.structure_io import qe_input_from_structure
from quantumvitas.io.model import QECardType, QEInput
from quantumvitas.workflow.input_runner import (
    ParameterOverride,
    apply_card_overrides_to_qe_input,
    apply_parameter_overrides,
    apply_species_overrides_to_qe_input,
    parameter_dict_to_overrides,
    set_outdir_to_temp,
    set_pseudo_dir_to_temp,
)

if TYPE_CHECKING:
    from quantumvitas.project.model import Project


@dataclass(slots=True)
class StructureStepSpec:
    """
    Declarative specification for generating a QE input from a stored structure.
    """

    meta: ResourceMeta
    structure: str
    step_type: str = "scf"
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    input_name: Optional[str] = None
    cards: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    species_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_path: Optional[Path] = None) -> "StructureStepSpec":
        structure = data.get("structure")
        if not structure:
            raise ValueError("Step spec is missing required field 'structure'")
        step_type = data.get("step_type", "scf")
        parameters = data.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise ValueError("Step spec 'parameters' must be a mapping")

        input_name = data.get("input_name") or data.get("input")
        cards = data.get("cards") or {}
        if not isinstance(cards, dict):
            raise ValueError("Step spec 'cards' must be a mapping when provided")

        species_overrides = data.get("species_overrides") or {}
        if not isinstance(species_overrides, dict):
            raise ValueError("Step spec 'species_overrides' must be a mapping when provided")

        meta_dict = data.get("meta")
        default_name = data.get("name") or str(step_type)
        default_path = (
            ensure_relative_path(source_path.name, base=source_path.parent)
            if source_path
            else (meta_dict or {}).get("path") or f"{default_name}.step.yaml"
        )
        meta = ResourceMeta.from_dict(
            meta_dict,
            kind="step",
            default_name=default_name,
            default_path=default_path,
        )

        return cls(
            meta=meta,
            structure=structure,
            step_type=str(step_type),
            parameters=parameters,
            input_name=input_name,
            cards=cards,
            species_overrides=species_overrides,
        )

    @classmethod
    def from_yaml(cls, path: Path | str) -> "StructureStepSpec":
        spec_path = Path(path)
        content = yaml.safe_load(spec_path.read_text()) or {}
        if not isinstance(content, dict):
            raise ValueError(f"Step file {path} must contain a mapping at the root")
        return cls.from_dict(content, source_path=spec_path)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "meta": self.meta.to_dict(),
            "structure": self.structure,
            "step_type": self.step_type,
        }
        if self.parameters:
            data["parameters"] = self.parameters
        if self.input_name:
            data["input_name"] = self.input_name
        if self.cards:
            data["cards"] = self.cards
        if self.species_overrides:
            data["species_overrides"] = self.species_overrides
        return data


def generate_qe_input_from_structure(
    structure: PMGStructure,
    step_type: str,
    parameter_overrides: Sequence[ParameterOverride] | None = None,
) -> QEInput:
    """
    Build a QE input from a structure plus step metadata.
    """

    qe_input = qe_input_from_structure(structure)

    overrides: list[ParameterOverride] = []
    if step_type:
        overrides.append(
            ParameterOverride(
                name="calculation",
                value=step_type,
                section="CONTROL",
            )
        )

    if parameter_overrides:
        overrides.extend(parameter_overrides)

    apply_parameter_overrides(qe_input, overrides)
    return qe_input


def generate_qe_input_from_spec(
    structure: PMGStructure,
    spec: StructureStepSpec,
    extra_overrides: Sequence[ParameterOverride] | None = None,
) -> tuple[QEInput, list[ParameterOverride]]:
    """
    Build a QE input from a structure step specification.
    """

    spec_overrides = parameter_dict_to_overrides(spec.parameters)
    combined_overrides: list[ParameterOverride] = list(spec_overrides)
    if extra_overrides:
        combined_overrides.extend(extra_overrides)
    qe_input = generate_qe_input_from_structure(
        structure=structure,
        step_type=spec.step_type,
        parameter_overrides=combined_overrides,
    )
    
    # Check if ibrav != 0 is set in the actual QEInput (after overrides applied)
    # If so, remove CELL_PARAMETERS as it's redundant with ibrav != 0
    system_namelist = qe_input.get_namelist("SYSTEM") or qe_input.get_namelist("system")
    if system_namelist:
        ibrav_value = system_namelist.parameters.get("ibrav")
        int_ibrav = int(ibrav_value) if ibrav_value is not None else 0
        if int_ibrav != 0:
            # Remove CELL_PARAMETERS when using ibrav != 0
            qe_input.cards = [
                card
                for card in qe_input.cards
                if card.card_type != QECardType.CELL_PARAMETERS
            ]
        else:
            # Remove redundant lattice parameters when using ibrav == 0
            lattice_keys = {
                "a",
                "alat",
                "b",
                "c",
                "cosab",
                "cosac",
                "cosbc",
            }
            for key in list(system_namelist.parameters.keys()):
                lower = key.lower()
                if lower.startswith("celldm") or lower in lattice_keys:
                    system_namelist.parameters.pop(key, None)
    
    apply_card_overrides_to_qe_input(qe_input, spec.cards)
    apply_species_overrides_to_qe_input(qe_input, spec.species_overrides)
    return qe_input, combined_overrides


def overrides_from_step_spec(spec: StructureStepSpec) -> list[ParameterOverride]:
    """
    Convenience helper returning overrides declared in a step spec.
    """

    return parameter_dict_to_overrides(spec.parameters)


SpecLike = Union[StructureStepSpec, str, Path]


def materialize_step_spec(
    spec: SpecLike,
    *,
    output_dir: Path | str,
    spec_path: Optional[Path | str] = None,
    workflow_dir: Optional[Path | str] = None,
    project: Optional["Project"] = None,
    input_name: Optional[str] = None,
    project_root: Optional[Path | str] = None,
) -> tuple[Path, StructureStepSpec]:
    """
    Convert a step YAML (or StructureStepSpec) into a QE input file under output_dir.
    
    Args:
        spec: Step spec (YAML path, StructureStepSpec, or path string)
        output_dir: Directory where the generated input file will be written
        spec_path: Optional explicit path to the spec file
        workflow_dir: Optional workflow directory for structure resolution
        project: Optional Project instance for structure resolution
        input_name: Optional name for the generated input file
        project_root: Optional project root for setting outdir and pseudo_dir.
                     If provided, sets outdir to "./outdir" and pseudo_dir to project_root/pseudo.
    
    Returns:
        Tuple of (generated_input_path, StructureStepSpec)
    """

    spec_obj, resolved_spec_path = _load_step_spec(spec, spec_path)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    structure = _resolve_structure_for_spec(
        spec_obj,
        resolved_spec_path,
        workflow_dir=workflow_dir,
        project=project,
    )

    qe_input, _ = generate_qe_input_from_spec(structure, spec_obj)

    # Set outdir and pseudo_dir if project_root is provided
    if project_root:
        project_root_path = Path(project_root).resolve()
        set_outdir_to_temp(qe_input)
        set_pseudo_dir_to_temp(qe_input, project_root_path)

    filename = input_name or spec_obj.input_name or f"{resolved_spec_path.stem}.pw.in"
    generated_input = output_dir / filename
    QEInputGenerator.write_file(qe_input, generated_input)
    return generated_input, spec_obj


def _load_step_spec(
    spec: SpecLike,
    spec_path: Optional[Path | str],
) -> tuple[StructureStepSpec, Path]:
    if isinstance(spec, StructureStepSpec):
        path = Path(spec_path).resolve() if spec_path else Path.cwd()
        return spec, path

    path = Path(spec).resolve()
    return StructureStepSpec.from_yaml(path), path


def _resolve_structure_for_spec(
    spec: StructureStepSpec,
    spec_path: Path,
    *,
    workflow_dir: Optional[Path | str],
    project: Optional["Project"],
) -> PMGStructure:
    search_roots: list[Path] = [spec_path.parent]
    if workflow_dir:
        workflow_dir_path = Path(workflow_dir).resolve()
        search_roots.append(workflow_dir_path)
        search_roots.append(workflow_dir_path.parent)

    structure_value = spec.structure
    candidate = Path(structure_value)

    if candidate.is_absolute() and candidate.exists():
        return read_structure(candidate)

    for root in search_roots:
        candidate_path = (root / candidate).resolve()
        if candidate_path.exists():
            return read_structure(candidate_path)

    if project:
        try:
            struct_ref = project.get_structure(structure_value)
            return read_structure(struct_ref.path)
        except KeyError:
            pass

    raise FileNotFoundError(
        f"Unable to resolve structure '{structure_value}' referenced in {spec_path}"
    )

