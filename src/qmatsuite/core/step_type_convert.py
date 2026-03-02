"""
Pure functions for SPEC↔GEN conversion.

Constitution:
- SPEC = {prefix}_{gen}
- GEN = no underscores (after migration)
- String with '_' is SPEC
- String without '_' is GEN
"""

from typing import FrozenSet

# Known engine prefixes (no underscores allowed)
ENGINE_PREFIXES: FrozenSet[str] = frozenset({
    "qe", "pyscf", "orca", "vasp", "lammps", "cp2k", "w90", "qmcpack",
    "gpaw", "siesta", "xtb", "yambo", "abinit", "gaussian", "mace",
})


def spec_from(prefix: str, gen: str) -> str:
    """
    Create SPEC from prefix + gen.

    Args:
        prefix: Engine prefix (e.g., "qe", "vasp", "w90")
        gen: GEN step name (e.g., "scf", "wannierprep")

    Returns:
        SPEC step type (e.g., "qe_scf", "w90_wannierprep")
    """
    if not prefix:
        raise ValueError("prefix cannot be empty")
    if not gen:
        raise ValueError("gen cannot be empty")
    return f"{prefix}_{gen}"


def gen_from(spec: str) -> str:
    """
    Extract GEN from SPEC.

    If input has no underscore, returns as-is (already GEN).

    Args:
        spec: SPEC step type (e.g., "qe_scf") or GEN (e.g., "scf")

    Returns:
        GEN step name (e.g., "scf")
    """
    if not spec:
        return spec
    if "_" not in spec:
        return spec  # Already GEN
    # Split on first underscore only
    parts = spec.split("_", 1)
    return parts[1]


def prefix_from(spec: str) -> str:
    """
    Extract engine prefix from SPEC.

    Args:
        spec: SPEC step type (e.g., "qe_scf")

    Returns:
        Engine prefix (e.g., "qe")

    Raises:
        ValueError: If spec has no underscore
    """
    if "_" not in spec:
        raise ValueError(f"'{spec}' is not a SPEC (no underscore)")
    return spec.split("_", 1)[0]


def is_spec(s: str) -> bool:
    """Check if string is SPEC format (has underscore)."""
    return bool(s) and "_" in s


def is_gen(s: str) -> bool:
    """Check if string is GEN format (no underscore)."""
    return bool(s) and "_" not in s


def normalize_to_gen(step_type_spec: str) -> str:
    """
    Normalize any step type to GEN format.

    Handles both SPEC (qe_scf) and GEN (scf) inputs.
    This is the canonical replacement for normalize_step_type_to_gen().

    Args:
        step_type_spec: Any step type string (spec or gen)

    Returns:
        GEN step name
    """
    return gen_from(step_type_spec)
