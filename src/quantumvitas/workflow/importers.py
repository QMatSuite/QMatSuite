from __future__ import annotations

from dataclasses import asdict, dataclass
import shutil
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

import yaml

from quantumvitas.io import QEInputGenerator, QEInputParser, read_structure, write_structure
from quantumvitas.io.model import QECardType, QEModule, QEInput
from quantumvitas.io.structure_io import structure_from_qe_input
from quantumvitas.project.model import Project
from quantumvitas.workflow.structure_steps import StructureStepSpec


STRUCTURE_CARDS = {
    QECardType.ATOMIC_POSITIONS,
    QECardType.CELL_PARAMETERS,
}


@dataclass(slots=True)
class StepImportResult:
    """Details about an imported QE input step."""

    step_id: str
    structure_id: str
    step_type: str
    parameters: Dict[str, Dict[str, object]]
    spec: StructureStepSpec
    spec_path: Path
    structure_path: Path


@dataclass(slots=True)
class WorkflowImportResult:
    """Summary information for a workflow import."""

    workflow_id: str
    workflow_dir: Path
    workflow_file: Path
    step_results: list[StepImportResult]
    structure_path: Path


def build_step_spec_from_qe_input(
    input_file: Path | str,
    *,
    destination_dir: Path | str,
    structure_dir: Path | str | None = None,
    step_id: Optional[str] = None,
    structure_id: Optional[str] = None,
    reference_structure_by: str = "path",
) -> StepImportResult:
    """
    Convert a QE input file into a StructureStepSpec + structure JSON.

    Args:
        input_file: QE input file to convert.
        destination_dir: Where to place the generated step YAML.
        structure_dir: Directory used to store the extracted structure JSON.
                       Defaults to ``destination_dir / 'structures'``.
        step_id: Optional explicit step id; defaults to ``input_file.stem``.
        structure_id: Optional structure id; defaults to ``input_file.stem``.
        reference_structure_by: Either ``'path'`` or ``'id'``. Controls how the
                                step spec references the structure. When ``id``
                                is used you are responsible for ensuring the
                                structure is registered in ``project.qv.yml``.

    Returns:
        StepImportResult describing the generated assets.
    """

    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"QE input not found: {input_path}")

    destination = Path(destination_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    structure_base = Path(structure_dir).resolve() if structure_dir else (destination / "structures")
    structure_base.mkdir(parents=True, exist_ok=True)

    qe_input = QEInputParser.parse_file(input_path)
    structure = structure_from_qe_input(qe_input)

    step_id = step_id or input_path.stem
    structure_id = structure_id or input_path.stem
    structure_path = (structure_base / f"{structure_id}.json").resolve()
    write_structure(structure, structure_path, format="json")

    parameters = _extract_parameters(qe_input)
    cards = _extract_cards(qe_input)
    step_type = _infer_step_type(qe_input)

    if reference_structure_by not in {"path", "id"}:
        raise ValueError("reference_structure_by must be either 'path' or 'id'")

    if reference_structure_by == "id":
        structure_ref_value = structure_id
    else:
        structure_ref_value = _relative_path_for_spec(structure_path, destination)

    spec = StructureStepSpec(
        structure=str(structure_ref_value),
        step_type=step_type,
        parameters=parameters,
        input_name=input_path.name,
        cards=cards,
    )

    step_file = destination / f"{step_id}.step.yaml"
    step_file.write_text(yaml.safe_dump(asdict(spec), sort_keys=False))

    return StepImportResult(
        step_id=step_id,
        structure_id=structure_id,
        step_type=step_type,
        parameters=parameters,
        spec=spec,
        spec_path=step_file,
        structure_path=structure_path,
    )


def build_workflow_from_qe_inputs(
    input_files: Sequence[Path | str],
    *,
    workflow_dir: Path | str,
    workflow_id: Optional[str] = None,
    structure_id: Optional[str] = None,
    reference_structure_by: str = "path",
    working_dir_name: str = "raw",
    mode: str = "normal",
    project_root: Optional[Path | str] = None,
) -> WorkflowImportResult:
    """
    Convert a series of QE input files into a workflow folder.

    The workflow will contain:
    - ``workflow.yaml`` referencing generated step specs
    - ``steps/<step_id>.step.yaml`` files
    - ``structures/<structure_id>.json`` (unless already present)
    - Optional copies of the original QE inputs under ``<working_dir_name>/original/``

    Args:
        input_files: Iterable of QE input files in execution order.
        workflow_dir: Destination directory for the workflow.
        workflow_id: Optional workflow identifier (defaults to destination name).
        structure_id: Optional structure id shared by all steps (defaults to stem of first input).
        reference_structure_by: ``'path'`` or ``'id'`` (propagated to step specs).
        working_dir_name: Name of the workflow raw directory.
        mode: Workflow mode (e.g., ``normal`` or ``strict``).
        project_root: Optional project root for relative paths.
    """

    files = [Path(p).resolve() for p in input_files]
    if not files:
        raise ValueError("At least one QE input is required to build a workflow")
    for path in files:
        if not path.exists():
            raise FileNotFoundError(f"QE input not found: {path}")

    workflow_dir = Path(workflow_dir).resolve()
    workflow_dir.mkdir(parents=True, exist_ok=True)

    steps_dir = (workflow_dir / "steps").resolve()
    steps_dir.mkdir(parents=True, exist_ok=True)

    project_root_path = Path(project_root).resolve() if project_root else None
    if project_root_path and not workflow_dir.is_relative_to(project_root_path):
        raise ValueError("workflow_dir must live inside the project root when project_root is provided")

    structure_store = (
        (project_root_path / "structures").resolve()
        if project_root_path
        else (workflow_dir / "structures").resolve()
    )
    structure_store.mkdir(parents=True, exist_ok=True)

    workflow_id = workflow_id or workflow_dir.name
    structure_id = structure_id or files[0].stem

    step_results: list[StepImportResult] = []
    for input_path in files:
        step_result = build_step_spec_from_qe_input(
            input_path,
            destination_dir=steps_dir,
            structure_dir=structure_store,
            step_id=input_path.stem,
            structure_id=structure_id,
            reference_structure_by=reference_structure_by,
        )
        step_results.append(step_result)

    raw_dir = (workflow_dir / working_dir_name).resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    originals_dir = raw_dir / "original_inputs"
    originals_dir.mkdir(parents=True, exist_ok=True)
    for input_path in files:
        shutil.copy2(input_path, originals_dir / input_path.name)

    workflow_meta: Dict[str, object] = {"working_dir": working_dir_name}
    if reference_structure_by == "id":
        workflow_meta["structure"] = structure_id
    else:
        workflow_meta["structure"] = str(_relative_path_for_spec(step_results[0].structure_path, workflow_dir))

    steps_section = [
        {
            "id": result.step_id,
            "step_file": str(result.spec_path.relative_to(workflow_dir)),
        }
        for result in step_results
    ]

    workflow_config = {
        "id": workflow_id,
        "mode": mode,
        "workflow": workflow_meta,
        "steps": steps_section,
    }
    workflow_file = workflow_dir / "workflow.yaml"
    workflow_file.write_text(yaml.safe_dump(workflow_config, sort_keys=False))

    return WorkflowImportResult(
        workflow_id=workflow_id,
        workflow_dir=workflow_dir,
        workflow_file=workflow_file,
        step_results=step_results,
        structure_path=step_results[0].structure_path,
    )


def _extract_parameters(qe_input: QEInput) -> Dict[str, Dict[str, object]]:
    parameters: Dict[str, Dict[str, object]] = {}
    for namelist in qe_input.namelists:
        if not namelist.parameters:
            continue
        section = namelist.name.upper()
        parameters.setdefault(section, {})
        parameters[section].update(namelist.parameters)
    _remove_structure_parameters(parameters)
    return parameters


STRUCTURAL_SYSTEM_KEYS = {"ibrav", "nat", "ntyp"}


def _remove_structure_parameters(parameters: Dict[str, Dict[str, object]]) -> None:
    """
    Remove structure-related SYSTEM parameters so they live exclusively in the structure payload.
    """
    system_params = parameters.get("SYSTEM")
    if not system_params:
        return

    keys_to_remove: list[str] = []
    for key in list(system_params.keys()):
        key_str = str(key)
        lower_key = key_str.lower()
        if lower_key in STRUCTURAL_SYSTEM_KEYS or lower_key.startswith("celldm"):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        system_params.pop(key, None)

    if not system_params:
        parameters.pop("SYSTEM", None)


def _extract_cards(qe_input: QEInput) -> Dict[str, Dict[str, object]]:
    cards: Dict[str, Dict[str, object]] = {}
    for card in qe_input.cards:
        if card.card_type in STRUCTURE_CARDS:
            continue
        cards[card.card_type.value] = {
            "option": card.option,
            "data": card.data,
        }
    return cards


def _infer_step_type(qe_input: QEInput) -> str:
    module = qe_input.detect_module()
    if module == QEModule.PW:
        control = qe_input.get_namelist("CONTROL") or qe_input.get_namelist("control")
        calculation = (control.get("calculation") if control else "scf") if control else "scf"
        calculation = str(calculation).lower()
        mapping = {
            "scf": "scf",
            "nscf": "nscf",
            "bands": "bands_pw",
            "relax": "scf",
            "vc-relax": "scf",
            "md": "scf",
            "vc-md": "scf",
        }
        return mapping.get(calculation, calculation)

    module_map = {
        QEModule.DOS: "dos",
        QEModule.BANDS: "bands",
        QEModule.PROJWFC: "projwfc",
        QEModule.PH: "ph",
        QEModule.Q2R: "q2r",
        QEModule.MATDYN: "matdyn",
        QEModule.DYNMAT: "dynmat",
        QEModule.PP: "pp",
        QEModule.GIPAW: "gipaw",
    }
    return module_map.get(module, "custom")


def _relative_path_for_spec(target: Path, base: Path) -> Path:
    try:
        return target.relative_to(base)
    except ValueError:
        return target

