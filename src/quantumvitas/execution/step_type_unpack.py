"""
Single choke point for spec→(prefix, gen) unpacking in execution layer.

Constitution §4.3: Runner/dispatch performs exactly ONE spec→(prefix, gen) "unpack"
at a SINGLE choke point before recipe lookup.

This module provides the ONLY permitted place where spec→gen conversion happens
in the execution layer. All execution code MUST use unpack_step_type() instead
of calling gen_from()/prefix_from() directly.

Usage:
    from quantumvitas.execution.step_type_unpack import unpack_step_type

    unpacked = unpack_step_type(step_type_spec)
    engine_prefix = unpacked.prefix
    gen_type = unpacked.gen
"""
from __future__ import annotations

from dataclasses import dataclass

from quantumvitas.workflow.public import gen_from, prefix_from, is_spec


@dataclass(frozen=True)
class UnpackedStepType:
    """
    Result of unpacking a SPEC step type.

    Attributes:
        spec: Original SPEC step type (e.g., "qe_scf", "vasp_relax")
        prefix: Engine prefix (e.g., "qe", "vasp")
        gen: GEN step type (e.g., "scf", "relax")
    """
    spec: str
    prefix: str
    gen: str


def unpack_step_type(step_type_spec: str) -> UnpackedStepType:
    """
    Unpack SPEC step type to (prefix, gen).

    This is the ONLY permitted place where spec→gen conversion happens
    in the execution layer. Constitution §4.3 mandates a single choke point.

    Args:
        step_type_spec: SPEC step type (e.g., "qe_scf", "vasp_relax")

    Returns:
        UnpackedStepType with spec, prefix, and gen

    Raises:
        ValueError: If step_type_spec is not valid SPEC format

    Example:
        >>> unpacked = unpack_step_type("qe_scf")
        >>> unpacked.spec
        'qe_scf'
        >>> unpacked.prefix
        'qe'
        >>> unpacked.gen
        'scf'
    """
    if not is_spec(step_type_spec):
        raise ValueError(
            f"Expected SPEC format (with underscore), got: '{step_type_spec}'. "
            f"Use step_type_spec from step.yaml, not step_type_gen."
        )

    return UnpackedStepType(
        spec=step_type_spec,
        prefix=prefix_from(step_type_spec),
        gen=gen_from(step_type_spec),
    )


def unpack_step_type_safe(step_type_str: str) -> UnpackedStepType:
    """
    Unpack step type, handling both SPEC and GEN formats.

    For SPEC types: Returns full unpacked result
    For GEN types: Returns UnpackedStepType with empty prefix

    This is useful when the input may be either SPEC or GEN format.
    Prefer unpack_step_type() when you know the input is SPEC.

    Args:
        step_type_str: Step type string (SPEC or GEN format)

    Returns:
        UnpackedStepType with spec, prefix, and gen

    Example:
        >>> unpacked = unpack_step_type_safe("qe_scf")
        >>> unpacked.gen
        'scf'
        >>> unpacked = unpack_step_type_safe("scf")
        >>> unpacked.gen
        'scf'
        >>> unpacked.prefix
        ''
    """
    if is_spec(step_type_str):
        return UnpackedStepType(
            spec=step_type_str,
            prefix=prefix_from(step_type_str),
            gen=gen_from(step_type_str),
        )
    else:
        # GEN type - no prefix
        return UnpackedStepType(
            spec="",
            prefix="",
            gen=step_type_str,
        )
