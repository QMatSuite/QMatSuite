"""
Precision ParamSpace Variants.

Defines three variants for precision:
- PRECISION_PW_DEFAULT: scf, relax, vc-relax, md, vc-md (with K_POINTS)
- PRECISION_PW_NSCF: nscf (with K_POINTS, denser mesh)
- PRECISION_PW_BANDS_PW: bands_pw (NO K_POINTS, only cutoffs + conv_thr)
"""

from dataclasses import dataclass
from typing import FrozenSet

from quantumvitas.presets.paramspace import (
    ParamSpace,
    ParamKey,
    Cell,
    parse_int,
    parse_float,
    canonicalize_int,
    canonicalize_float,
)


@dataclass(frozen=True)
class PrecisionPolicy:
    """
    Policy constants for a precision level.
    
    These are stored in ParamSpace profile metadata, not as absolute values.
    Resolver uses these to compute concrete values from context.
    """
    cutoff_multiplier: float
    delta_k: float
    conv_thr: float
    nscf_factor: float  # Mesh multiplier for nscf (1.0 for default, 2.0 for nscf)


# Precision policy constants (from precision.py PRECISION_CONSTANTS)
PRECISION_POLICIES = {
    "LOW": PrecisionPolicy(
        cutoff_multiplier=0.8,
        delta_k=0.30,
        conv_thr=1e-6,
        nscf_factor=1.0,  # Will be overridden for nscf variant
    ),
    "MED": PrecisionPolicy(
        cutoff_multiplier=1.0,
        delta_k=0.20,
        conv_thr=1e-8,
        nscf_factor=1.0,
    ),
    "HIGH": PrecisionPolicy(
        cutoff_multiplier=1.2,
        delta_k=0.15,
        conv_thr=1e-10,
        nscf_factor=1.0,
    ),
}


def build_precision_pw_default_space() -> ParamSpace:
    """
    Build ParamSpace for precision default variant (scf, relax, etc.).
    
    Includes: ecutwfc, ecutrho, conv_thr, K_POINTS
    """
    key_ecutwfc = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_ecutrho = ParamKey(
        section="SYSTEM",
        key="ecutrho",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_conv_thr = ParamKey(
        section="ELECTRONS",
        key="conv_thr",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-11,
        default=None,
    )
    
    key_kpoints = ParamKey(
        section="cards",
        key="K_POINTS",
        parser=lambda x: x,
        canonicalizer=lambda x: x,
        default=None,
    )
    
    keys = [key_ecutwfc, key_ecutrho, key_conv_thr, key_kpoints]
    
    # Profiles store policy metadata (will be resolved to concrete values)
    profiles = {
        "LOW": {
            key_ecutwfc: Cell.WILDCARD(),  # Resolved at compile time
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
        "MED": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
        "HIGH": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
    }
    
    return ParamSpace(
        name="precision_pw_default",
        keys=keys,
        profiles=profiles,
    )


def build_precision_pw_nscf_space() -> ParamSpace:
    """
    Build ParamSpace for precision nscf variant.
    
    Same keys as default, but profiles use nscf_factor=2.0 for kmesh.
    """
    # Same keys as default
    key_ecutwfc = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_ecutrho = ParamKey(
        section="SYSTEM",
        key="ecutrho",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_conv_thr = ParamKey(
        section="ELECTRONS",
        key="conv_thr",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-11,
        default=None,
    )
    
    key_kpoints = ParamKey(
        section="cards",
        key="K_POINTS",
        parser=lambda x: x,
        canonicalizer=lambda x: x,
        default=None,
    )
    
    keys = [key_ecutwfc, key_ecutrho, key_conv_thr, key_kpoints]
    
    profiles = {
        "LOW": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
        "MED": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
        "HIGH": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
            key_kpoints: Cell.WILDCARD(),
        },
    }
    
    return ParamSpace(
        name="precision_pw_nscf",
        keys=keys,
        profiles=profiles,
    )


def build_precision_pw_bands_pw_space() -> ParamSpace:
    """
    Build ParamSpace for precision bands_pw variant.
    
    IMPORTANT: Does NOT include K_POINTS key.
    Only: ecutwfc, ecutrho, conv_thr
    """
    key_ecutwfc = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_ecutrho = ParamKey(
        section="SYSTEM",
        key="ecutrho",
        parser=parse_int,
        canonicalizer=canonicalize_int,
        default=None,
    )
    
    key_conv_thr = ParamKey(
        section="ELECTRONS",
        key="conv_thr",
        parser=parse_float,
        canonicalizer=canonicalize_float,
        tolerance=1e-11,
        default=None,
    )
    
    # NO K_POINTS key for bands_pw variant
    
    keys = [key_ecutwfc, key_ecutrho, key_conv_thr]
    
    profiles = {
        "LOW": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
        },
        "MED": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
        },
        "HIGH": {
            key_ecutwfc: Cell.WILDCARD(),
            key_ecutrho: Cell.WILDCARD(),
            key_conv_thr: Cell.WILDCARD(),
        },
    }
    
    return ParamSpace(
        name="precision_pw_bands_pw",
        keys=keys,
        profiles=profiles,
    )


def get_precision_policy(profile_name: str, variant_name: str) -> PrecisionPolicy:
    """
    Get precision policy for a profile and variant.
    
    Args:
        profile_name: "LOW", "MED", or "HIGH"
        variant_name: "PRECISION_PW_DEFAULT", "PRECISION_PW_NSCF", or "PRECISION_PW_BANDS_PW"
    
    Returns:
        PrecisionPolicy with appropriate nscf_factor
    """
    base_policy = PRECISION_POLICIES[profile_name]
    
    # Override nscf_factor for nscf variant
    if variant_name == "PRECISION_PW_NSCF":
        return PrecisionPolicy(
            cutoff_multiplier=base_policy.cutoff_multiplier,
            delta_k=base_policy.delta_k,
            conv_thr=base_policy.conv_thr,
            nscf_factor=2.0,
        )
    
    return base_policy

