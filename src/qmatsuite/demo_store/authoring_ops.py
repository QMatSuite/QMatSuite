"""
Fine-grained authoring operations IR for demo project replay.

Each op maps to exactly one QMSService call. The IR enforces:
- One op per independent scalar leaf parameter (SetField)
- No bulk ops (entire parameters tree as value)
- Lists/tables allowed as single ops (matches one UI widget)

8 op types covering the full authorship vocabulary.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Union


@dataclass(frozen=True)
class InitProject:
    """Initialize a new project."""
    name: str
    op: str = field(default="InitProject", init=False)


@dataclass(frozen=True)
class ImportStructure:
    """Import a structure into the project."""
    name: str
    structure_data: dict  # pymatgen-style dict
    op: str = field(default="ImportStructure", init=False)


@dataclass(frozen=True)
class CreateCalculation:
    """Create a new calculation."""
    name: str
    engine_family: str
    structure_selector: str  # slug or name
    op: str = field(default="CreateCalculation", init=False)


@dataclass(frozen=True)
class AddStep:
    """Add a step to a calculation."""
    calc_selector: str
    step_type_gen: str
    name: str
    op: str = field(default="AddStep", init=False)


@dataclass(frozen=True)
class SetField:
    """Set a single leaf value on a step.

    value must be scalar (str, int, float, bool) or list. Never a dict.
    """
    target: str  # "step:<calc_slug>/<step_slug>"
    pointer: str  # JSON pointer, e.g. "/parameters/CONTROL/calculation"
    value: Any  # scalar or list
    op: str = field(default="SetField", init=False)


@dataclass(frozen=True)
class UnsetField:
    """Remove a field (leaf or branch) from a step."""
    target: str
    pointer: str
    op: str = field(default="UnsetField", init=False)


@dataclass(frozen=True)
class ReplaceMap:
    """Replace a dict sub-tree on a step (e.g., a card or species override)."""
    target: str
    pointer: str
    value: dict
    op: str = field(default="ReplaceMap", init=False)


@dataclass(frozen=True)
class ConfigureSpeciesMap:
    """Set the species map on a calculation."""
    calc_selector: str
    species_map: dict
    op: str = field(default="ConfigureSpeciesMap", init=False)


# Union type for all ops
AuthoringOp = Union[
    InitProject,
    ImportStructure,
    CreateCalculation,
    AddStep,
    SetField,
    UnsetField,
    ReplaceMap,
    ConfigureSpeciesMap,
]

_OP_CLASSES = {
    "InitProject": InitProject,
    "ImportStructure": ImportStructure,
    "CreateCalculation": CreateCalculation,
    "AddStep": AddStep,
    "SetField": SetField,
    "UnsetField": UnsetField,
    "ReplaceMap": ReplaceMap,
    "ConfigureSpeciesMap": ConfigureSpeciesMap,
}


def ops_to_json(ops: list[AuthoringOp]) -> str:
    """Serialize a list of AuthoringOps to JSON."""
    return json.dumps([asdict(op) for op in ops], indent=2)


def ops_from_json(json_str: str) -> list[AuthoringOp]:
    """Deserialize a list of AuthoringOps from JSON."""
    raw = json.loads(json_str)
    result = []
    for item in raw:
        op_type = item.pop("op")
        cls = _OP_CLASSES[op_type]
        result.append(cls(**item))
    return result


def is_bulk_op(op: AuthoringOp) -> bool:
    """Return True if an op carries a full params tree (forbidden).

    Bulk ops are:
    - ReplaceMap where pointer is "/parameters" (replaces entire params tree)
    """
    if isinstance(op, ReplaceMap) and op.pointer == "/parameters":
        return True
    return False
