"""QE-specific parameter/structure preflight validation.

Pure functions, no file I/O, no side effects.  Returns a list of
PreflightIssue objects that the MCP layer surfaces to the agent.
"""

from __future__ import annotations

from typing import Any

from qmatsuite.core.driver_protocol import PreflightIssue

# ── Reference sets ──────────────────────────────────────────────────────

_VALID_CALCULATIONS = frozenset({
    "scf", "nscf", "bands", "relax", "vc-relax", "md",
})

_NSCF_LIKE = frozenset({"nscf", "bands"})

_METALLIC_ELEMENTS = frozenset({
    "Li", "Be", "Na", "Mg", "Al", "K", "Ca", "Sc", "Ti", "V",
    "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Rb", "Sr",
    "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
    "In", "Sn", "Cs", "Ba", "La", "Hf", "Ta", "W", "Re", "Os",
    "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi",
})

_MAGNETIC_ELEMENTS = frozenset({"Fe", "Co", "Ni", "Mn", "Cr"})


def _get(params: dict, *keys: str, default: Any = None) -> Any:
    """Dig into a nested param dict (QE uses CONTROL/SYSTEM/ELECTRONS namelists)."""
    for key in keys:
        if isinstance(params, dict):
            # Case-insensitive lookup for QE namelist names
            found = None
            for k, v in params.items():
                if k.lower() == key.lower():
                    found = v
                    break
            if found is None:
                return default
            params = found
        else:
            return default
    return params


class QEPreflightChecker:
    """Deterministic parameter/structure validation for Quantum ESPRESSO.

    20 rules across 3 severity levels: blocking, warning, advisory.
    """

    def check(
        self,
        step_params: dict[str, Any],
        structure_info: dict[str, Any] | None,
        workflow_context: dict[str, Any] | None,
    ) -> list[PreflightIssue]:
        """Run all preflight rules and return any issues found.

        Args:
            step_params: QE parameter dict (e.g. {"SYSTEM": {"ecutwfc": 40}, ...}).
            structure_info: Lightweight structure dict with keys:
                species, n_atoms, elements (set), is_periodic.
                None if no structure is attached.
            workflow_context: Dict with keys:
                gen_steps (list[str]), current_step_index (int),
                current_step_gen (str), other_steps_params (dict).
                None for stateless previews.
        """
        issues: list[PreflightIssue] = []
        if step_params is None:
            step_params = {}
        if workflow_context is None:
            workflow_context = {}

        elements: set[str] = set()
        if structure_info is not None:
            elements = set(structure_info.get("elements", set()))

        calc_type = _get(step_params, "CONTROL", "calculation", default="scf")
        if isinstance(calc_type, str):
            calc_type = calc_type.strip("'\"").lower()

        ecutwfc = _get(step_params, "SYSTEM", "ecutwfc")
        ecutrho = _get(step_params, "SYSTEM", "ecutrho")
        occupations = _get(step_params, "SYSTEM", "occupations")
        if isinstance(occupations, str):
            occupations = occupations.strip("'\"").lower()
        smearing = _get(step_params, "SYSTEM", "smearing")
        degauss = _get(step_params, "SYSTEM", "degauss")
        nspin = _get(step_params, "SYSTEM", "nspin")
        nat = _get(step_params, "SYSTEM", "nat")
        conv_thr = _get(step_params, "ELECTRONS", "conv_thr")
        electron_maxstep = _get(step_params, "ELECTRONS", "electron_maxstep")
        mixing_beta = _get(step_params, "ELECTRONS", "mixing_beta")
        cell_dofree = _get(step_params, "CELL", "cell_dofree")
        tempw = _get(step_params, "IONS", "tempw")
        ion_temperature = _get(step_params, "IONS", "ion_temperature")

        # Check if kpoints are present (may be in KPOINTS key or K_POINTS card)
        has_kpoints = (
            _get(step_params, "KPOINTS") is not None
            or _get(step_params, "K_POINTS") is not None
            or _get(step_params, "kpoints") is not None
        )

        gen_steps = workflow_context.get("gen_steps", [])
        current_idx = workflow_context.get("current_step_index", 0)
        current_gen = workflow_context.get("current_step_gen", "")

        # ── BLOCKING ────────────────────────────────────────────────

        # B1: MISSING_ECUTWFC
        if ecutwfc is None or (isinstance(ecutwfc, (int, float)) and ecutwfc <= 0):
            issues.append(PreflightIssue(
                code="MISSING_ECUTWFC",
                severity="blocking",
                message="ecutwfc is missing or non-positive. QE requires a plane-wave cutoff.",
                parameter="SYSTEM.ecutwfc",
                suggestion="Set ecutwfc to at least 30 Ry (typical: 40-80 Ry depending on pseudopotentials).",
            ))

        # B2: MISSING_KPOINTS
        is_periodic = True
        if structure_info is not None:
            is_periodic = structure_info.get("is_periodic", True)
        if not has_kpoints and structure_info is not None and is_periodic:
            issues.append(PreflightIssue(
                code="MISSING_KPOINTS",
                severity="blocking",
                message="No k-points specified for a periodic structure.",
                parameter="K_POINTS",
                suggestion="Add a K_POINTS card (e.g. automatic 4 4 4 0 0 0).",
            ))

        # B3: INVALID_CALCULATION_TYPE
        if calc_type not in _VALID_CALCULATIONS:
            issues.append(PreflightIssue(
                code="INVALID_CALCULATION_TYPE",
                severity="blocking",
                message=f"calculation='{calc_type}' is not a valid QE calculation type.",
                parameter="CONTROL.calculation",
                suggestion=f"Valid types: {', '.join(sorted(_VALID_CALCULATIONS))}.",
            ))

        # B4: NSCF_WITHOUT_SCF
        if current_gen in _NSCF_LIKE:
            preceding = gen_steps[:current_idx]
            if "scf" not in preceding:
                issues.append(PreflightIssue(
                    code="NSCF_WITHOUT_SCF",
                    severity="blocking",
                    message=f"'{current_gen}' step requires a preceding 'scf' step.",
                    suggestion="Add an 'scf' step before this step in the workflow.",
                ))

        # B5: NEGATIVE_DEGAUSS
        if degauss is not None and isinstance(degauss, (int, float)) and degauss < 0:
            issues.append(PreflightIssue(
                code="NEGATIVE_DEGAUSS",
                severity="blocking",
                message=f"degauss={degauss} is negative.",
                parameter="SYSTEM.degauss",
                suggestion="degauss must be non-negative (typical: 0.01-0.02 Ry).",
            ))

        # B6: ZERO_NAT
        if nat is not None and isinstance(nat, (int, float)) and nat == 0:
            issues.append(PreflightIssue(
                code="ZERO_NAT",
                severity="blocking",
                message="nat is explicitly set to 0.",
                parameter="SYSTEM.nat",
                suggestion="Remove nat or set it to the actual number of atoms.",
            ))

        # ── WARNING ─────────────────────────────────────────────────

        # W1: METAL_FIXED_OCC (advisory — fixed occupations is legitimate for bands/DOS)
        if occupations == "fixed" and elements & _METALLIC_ELEMENTS:
            metals = sorted(elements & _METALLIC_ELEMENTS)
            issues.append(PreflightIssue(
                code="METAL_FIXED_OCC",
                severity="advisory",
                message=f"Fixed occupations with metallic elements ({', '.join(metals)}). "
                        "Consider using smearing for SCF convergence.",
                parameter="SYSTEM.occupations",
                suggestion="Use occupations='smearing' with an appropriate smearing method.",
            ))

        # W2: SPIN_UNPOLARIZED_MAGNETIC
        if nspin is not None and int(nspin) == 1 and elements & _MAGNETIC_ELEMENTS:
            mag = sorted(elements & _MAGNETIC_ELEMENTS)
            issues.append(PreflightIssue(
                code="SPIN_UNPOLARIZED_MAGNETIC",
                severity="warning",
                message=f"nspin=1 (unpolarized) with magnetic elements ({', '.join(mag)}).",
                parameter="SYSTEM.nspin",
                suggestion="Consider nspin=2 for spin-polarized calculation.",
            ))

        # W3: TETRAHEDRA_WITH_RELAX
        if occupations == "tetrahedra" and calc_type in ("relax", "vc-relax", "md"):
            issues.append(PreflightIssue(
                code="TETRAHEDRA_WITH_RELAX",
                severity="warning",
                message=f"Tetrahedra occupations with calculation='{calc_type}'. "
                        "Tetrahedra require fixed k-points, incompatible with moving atoms.",
                parameter="SYSTEM.occupations",
                suggestion="Use smearing for relaxation/MD calculations.",
            ))

        # W4: TETRAHEDRA_METALS
        if occupations == "tetrahedra" and elements & _METALLIC_ELEMENTS:
            metals = sorted(elements & _METALLIC_ELEMENTS)
            issues.append(PreflightIssue(
                code="TETRAHEDRA_METALS",
                severity="warning",
                message=f"Tetrahedra occupations with metallic elements ({', '.join(metals)}). "
                        "Tetrahedra may be poorly converged for metals.",
                parameter="SYSTEM.occupations",
                suggestion="Consider smearing for metals unless using tetrahedra_opt.",
            ))

        # W5: SMEARING_NO_DEGAUSS
        if occupations == "smearing" and degauss is None:
            issues.append(PreflightIssue(
                code="SMEARING_NO_DEGAUSS",
                severity="warning",
                message="occupations='smearing' but degauss is not set. QE will use a default.",
                parameter="SYSTEM.degauss",
                suggestion="Explicitly set degauss (typical: 0.01-0.02 Ry).",
            ))

        # W6: ECUTRHO_TOO_LOW
        if (ecutwfc is not None and ecutrho is not None
                and isinstance(ecutwfc, (int, float))
                and isinstance(ecutrho, (int, float))
                and ecutwfc > 0 and ecutrho > 0
                and ecutrho < 4 * ecutwfc):
            issues.append(PreflightIssue(
                code="ECUTRHO_TOO_LOW",
                severity="warning",
                message=f"ecutrho={ecutrho} < 4*ecutwfc={4*ecutwfc}. "
                        "Charge density cutoff is unusually low.",
                parameter="SYSTEM.ecutrho",
                suggestion="ecutrho should be at least 4*ecutwfc (8-12x for ultrasoft/PAW).",
            ))

        # W7: VC_RELAX_FIXED_CELL
        if calc_type == "vc-relax" and cell_dofree is not None:
            dofree = str(cell_dofree).strip("'\"").lower()
            if dofree not in ("all", ""):
                issues.append(PreflightIssue(
                    code="VC_RELAX_FIXED_CELL",
                    severity="advisory",
                    message=f"vc-relax with cell_dofree='{dofree}' restricts cell degrees of freedom.",
                    parameter="CELL.cell_dofree",
                    suggestion="Ensure this is intentional. Use cell_dofree='all' for full relaxation.",
                ))

        # W8: MD_NO_TEMPERATURE
        if calc_type == "md" and tempw is None and ion_temperature is None:
            issues.append(PreflightIssue(
                code="MD_NO_TEMPERATURE",
                severity="warning",
                message="calculation='md' without tempw or ion_temperature. "
                        "MD needs a target temperature.",
                parameter="IONS.tempw",
                suggestion="Set tempw (in K) or ion_temperature for MD runs.",
            ))

        # ── ADVISORY ────────────────────────────────────────────────

        # A1: LOW_ECUTWFC
        if (ecutwfc is not None and isinstance(ecutwfc, (int, float))
                and 0 < ecutwfc < 20):
            issues.append(PreflightIssue(
                code="LOW_ECUTWFC",
                severity="advisory",
                message=f"ecutwfc={ecutwfc} Ry is very low for production calculations.",
                parameter="SYSTEM.ecutwfc",
                suggestion="Most pseudopotentials need at least 30-40 Ry.",
            ))

        # A2: LOOSE_CONV_THR
        if (conv_thr is not None and isinstance(conv_thr, (int, float))
                and conv_thr > 1e-4):
            issues.append(PreflightIssue(
                code="LOOSE_CONV_THR",
                severity="advisory",
                message=f"conv_thr={conv_thr} is loose. Results may be poorly converged.",
                parameter="ELECTRONS.conv_thr",
                suggestion="Use conv_thr <= 1.0e-6 for production (1.0e-8 for forces).",
            ))

        # A3: LOW_ELECTRON_MAXSTEP
        if (electron_maxstep is not None
                and isinstance(electron_maxstep, (int, float))
                and electron_maxstep < 30):
            issues.append(PreflightIssue(
                code="LOW_ELECTRON_MAXSTEP",
                severity="advisory",
                message=f"electron_maxstep={electron_maxstep} may be too few SCF iterations.",
                parameter="ELECTRONS.electron_maxstep",
                suggestion="Default is 100. Increase for difficult convergence.",
            ))

        # A4: GAUSSIAN_SMEARING_FOR_DOS
        if (smearing is not None
                and isinstance(smearing, str)
                and smearing.strip("'\"").lower() in ("gaussian", "gauss")):
            # Check if dos is in the workflow
            if "dos" in gen_steps:
                issues.append(PreflightIssue(
                    code="GAUSSIAN_SMEARING_FOR_DOS",
                    severity="advisory",
                    message="Gaussian smearing with a DOS workflow. "
                            "Methfessel-Paxton is preferred for DOS accuracy.",
                    parameter="SYSTEM.smearing",
                    suggestion="Use smearing='mp' or 'marzari-vanderbilt' for DOS workflows.",
                ))

        # A5: LARGE_MIXING_BETA
        if (mixing_beta is not None and isinstance(mixing_beta, (int, float))
                and mixing_beta > 0.7):
            issues.append(PreflightIssue(
                code="LARGE_MIXING_BETA",
                severity="advisory",
                message=f"mixing_beta={mixing_beta} is large. SCF may oscillate.",
                parameter="ELECTRONS.mixing_beta",
                suggestion="Typical range: 0.1-0.7. Lower for difficult systems.",
            ))

        # A6: ECUTWFC_VERY_HIGH
        if (ecutwfc is not None and isinstance(ecutwfc, (int, float))
                and ecutwfc > 200):
            issues.append(PreflightIssue(
                code="ECUTWFC_VERY_HIGH",
                severity="advisory",
                message=f"ecutwfc={ecutwfc} Ry is unusually high. May waste compute time.",
                parameter="SYSTEM.ecutwfc",
                suggestion="Check pseudopotential cutoff recommendations.",
            ))

        # A7: PARAM_WRONG_SECTION — check parameters are in the correct namelist
        issues.extend(_check_param_sections(step_params))

        return issues


def _check_param_sections(step_params: dict[str, Any]) -> list[PreflightIssue]:
    """Check that QE pw.x parameters are placed in the correct namelist.

    Returns advisory-level issues for misplaced parameters. Unknown
    parameters (not in metadata) are silently skipped — they may be
    valid in a newer QE version.
    """
    from qmatsuite.drivers.qe.param_registry import (
        get_qe_param_namelist,
        get_pw_namelists,
    )

    issues: list[PreflightIssue] = []
    pw_namelists = get_pw_namelists()

    for current_nl, section_data in step_params.items():
        if current_nl not in pw_namelists:
            continue
        if not isinstance(section_data, dict):
            continue
        for param_name in section_data:
            expected_nl = get_qe_param_namelist(param_name)
            if expected_nl is None:
                continue  # Unknown param — skip silently
            if expected_nl != current_nl:
                issues.append(PreflightIssue(
                    code="PARAM_WRONG_SECTION",
                    severity="warning",
                    message=(
                        f"'{param_name}' is in &{current_nl} but QE expects it in "
                        f"&{expected_nl}. pw.x may crash or silently ignore this parameter."
                    ),
                    parameter=f"{current_nl}.{param_name}",
                    suggestion=f"Move '{param_name}' from {current_nl} to {expected_nl}.",
                ))

    return issues
